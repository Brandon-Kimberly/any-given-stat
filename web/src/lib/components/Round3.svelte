<script lang="ts">
	// Round 3: the forecast judged on accuracy (RMSE of the margin, log loss of win
	// probability), not on betting. Frozen choice, reused test, sealed live test.
	import { num, signed } from '$lib/format';
	import { gridY, Plot, plotStyle, thinTicks } from '$lib/plot';
	import type { ForecastMetrics, Lab3, PairedDiff } from '$lib/types';
	import DataTable, { type Column } from './DataTable.svelte';
	import PlotFigure from './Plot.svelte';

	let { lab }: { lab: Lab3 } = $props();
	const p = $derived(lab.protocol);

	const MODELS = [
		{ key: 'round3', label: 'Round 3 (frozen)' },
		{ key: 'blend', label: 'Line + model blend' },
		{ key: 'vegas', label: 'Vegas closing line' },
		{ key: 'round2', label: 'Round 2 model' },
		{ key: 'round1', label: 'Round 1 model' }
	] as const;
	const SPLITS = $derived([
		{ key: 'validate', label: `Validation ${p.validate_seasons.join('–')}` },
		{ key: 'test', label: `Reused test ${p.test_seasons.join('–')}` },
		{ key: 'pre_freeze', label: `${p.live_season} before freeze` },
		{ key: 'sealed', label: `${p.live_season} sealed` }
	] as const);
	const best = (split: (typeof SPLITS)[number]['key'], metric: 'rmse' | 'log_loss') =>
		Math.min(...MODELS.map((m) => lab.comparison[split][m.key][metric] ?? Infinity));
	const cell = (m: ForecastMetrics, metric: 'rmse' | 'log_loss') =>
		m[metric] == null ? '–' : num(m[metric], metric === 'rmse' ? 2 : 3);

	/** "beats X (t = -1.1, within noise)" from a paired squared-error difference. */
	function verdict(d: PairedDiff | null, a: string, b: string): string {
		if (!d || !d.se) return `no games yet to compare ${a} and ${b}`;
		const t = d.diff / d.se;
		const who = t < 0 ? a : b;
		const strength = Math.abs(t) >= 2 ? 'a real difference' : 'within noise';
		return `${who} is more accurate (t = ${signed(t, 1)}, ${strength})`;
	}
	const test = $derived(lab.comparison.test);

	function seasonChart(width: number) {
		const rows = lab.by_season
			.flatMap((s) => [
				{ season: s.season, rmse: s.round3, who: 'Round 3' },
				{ season: s.season, rmse: s.vegas, who: 'Vegas closing line' },
				{ season: s.season, rmse: s.round1, who: 'Round 1' }
			])
			.filter((r) => r.rmse != null);
		const seasons = lab.by_season.map((s) => s.season);
		return Plot.plot({
			width,
			height: 280,
			style: plotStyle,
			x: { label: null, tickFormat: 'd', ticks: thinTicks(seasons, width, 40) },
			y: { label: '↓ RMSE of the margin (points, lower is better)', zero: false },
			color: {
				domain: ['Round 3', 'Vegas closing line', 'Round 1'],
				range: ['var(--series-1)', 'var(--series-2)', 'var(--series-3)'],
				legend: true
			},
			marks: [
				gridY(),
				Plot.line(rows, { x: 'season', y: 'rmse', stroke: 'who', strokeWidth: 2 }),
				Plot.dot(rows, { x: 'season', y: 'rmse', fill: 'who', r: 3.5 }),
				Plot.tip(
					rows,
					Plot.pointer({
						x: 'season',
						y: 'rmse',
						title: (d: (typeof rows)[number]) => `${d.season} ${d.who}: ${num(d.rmse, 2)} pts`
					})
				)
			]
		});
	}

	type SelRow = Lab3['selection'][number] & { chosen: boolean };
	const selRows = $derived<SelRow[]>(
		lab.selection.map((r) => ({ ...r, chosen: r.variant === lab.chosen.variant }))
	);
	const selCols: Column<SelRow>[] = [
		{ key: 'variant', label: 'Candidate', sticky: true },
		{ key: 'features', label: 'Inputs' },
		{ key: 'fit_rmse', label: 'Fit RMSE', fmt: (v) => num(v, 2) },
		{ key: 'val_rmse', label: 'Val RMSE', fmt: (v) => num(v, 3), better: 'low' },
		{ key: 'val_log_loss', label: 'Val log loss', fmt: (v) => num(v, 4), better: 'low' },
		{ key: 'val_mae', label: 'Val avg miss', fmt: (v) => num(v, 2) }
	];
</script>

<section class="card" id="round3">
	<div class="eyebrow">Round 3 · the forecast this page shows</div>
	<h2>As accurate as public data gets</h2>
	<p class="sub">
		Rounds 1 and 2 asked whether we can beat the line. Round 3 asks how close a forecast can get to
		what happens, scored by root-mean-square error of the margin and log loss of the win
		probability. {lab.selection.length} candidates were fit on {p.fit_seasons.join('–')}; the lowest
		validation error won and was
		<a href="https://github.com/Brandon-Kimberly/any-given-stat/commit/9589541">frozen</a>
		on {p.freeze_date}: <b>{lab.chosen.variant}</b>. Points ratings are a second team rating built
		from final scores, which catch what EPA misses (special teams, the full value of turnovers).
	</p>

	<div class="scroll">
		<table class="score">
			<thead>
				<tr>
					<th rowspan="2" scope="col">Forecast</th>
					{#each SPLITS as s (s.key)}<th colspan="2" scope="colgroup">{s.label}</th>{/each}
				</tr>
				<tr>
					{#each SPLITS as s (s.key)}<th scope="col">RMSE</th><th scope="col">Log loss</th>{/each}
				</tr>
			</thead>
			<tbody>
				{#each MODELS as m (m.key)}
					<tr class:chosen={m.key === 'round3'}>
						<th scope="row">{m.label}</th>
						{#each SPLITS as s (s.key)}
							{@const v = lab.comparison[s.key][m.key]}
							<td class:best={v.rmse != null && v.rmse === best(s.key, 'rmse')}
								>{cell(v, 'rmse')}</td
							>
							<td class:best={v.log_loss != null && v.log_loss === best(s.key, 'log_loss')}
								>{cell(v, 'log_loss')}</td
							>
						{/each}
					</tr>
				{/each}
			</tbody>
			<tfoot>
				<tr>
					<th scope="row">Games</th>
					{#each SPLITS as s (s.key)}<td colspan="2">{lab.comparison[s.key].round3.games}</td
						>{/each}
				</tr>
			</tfoot>
		</table>
	</div>
	<ul class="verdicts">
		<li>
			Round 3 vs round 1, reused test: {verdict(test.round3_vs_round1, 'round 3', 'round 1')}.
		</li>
		<li>Round 3 vs Vegas, reused test: {verdict(test.round3_vs_vegas, 'round 3', 'Vegas')}.</li>
		<li>
			Blend vs Vegas, reused test: {verdict(test.blend_vs_vegas, 'the blend', 'Vegas')}. The blend
			is the line plus {Math.round(lab.blend_k * 100)}% of the model's disagreement, the weight the
			fit seasons support.
		</li>
	</ul>
</section>

<div class="grid-2">
	<section class="card">
		<h2>Accuracy by season</h2>
		<p class="sub">
			Every season predicted walk-forward. {p.fit_seasons.join('–')} is in-sample for the coefficients.
		</p>
		<PlotFigure label="Forecast error by season: round 3, Vegas and round 1" render={seasonChart} />
	</section>
	<section class="card">
		<h2>What the forecast weighs</h2>
		<p class="sub">
			Coefficients refit on every completed season before {p.live_season}. "Typical" is how far a
			factor moves a line (one standard deviation). Win probabilities use σ = {num(lab.sigma, 1)} points.
		</p>
		<table class="coef">
			<thead
				><tr><th scope="col">Input</th><th scope="col">Per unit</th><th scope="col">Typical</th></tr
				></thead
			>
			<tbody>
				{#each lab.coefficients as c (c.feature)}
					<tr>
						<td>{c.label}</td>
						<td class="num"
							>{signed(c.beta, 2)} <span class="muted">± {num(1.96 * c.se, 2)}</span></td
						>
						<td class="num">{num(c.typical_points, 1)} pts</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</section>
</div>

<section class="card">
	<h2>The {selRows.length} round-3 candidates on validation</h2>
	<p class="sub">Lowest validation RMSE was chosen (ties go to fewer inputs).</p>
	<DataTable
		rows={selRows}
		columns={selCols}
		sortKey="val_rmse"
		sortDesc={false}
		highlight={(r) => r.chosen}
		filename="round3-selection"
	/>
</section>

<style>
	.scroll {
		overflow-x: auto;
	}
	.score {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
		font-variant-numeric: tabular-nums;
		min-width: 640px;
	}
	.score th,
	.score td {
		padding: 0.4rem 0.5rem;
		border-bottom: 1px solid var(--grid);
		text-align: right;
	}
	.score th[scope='row'] {
		text-align: left;
		font-weight: 600;
	}
	.score thead th {
		font-size: 0.75rem;
		color: var(--text-secondary);
		font-weight: 600;
	}
	.score th[scope='colgroup'] {
		text-align: center;
		border-bottom: 1px solid var(--border);
	}
	.score tr.chosen {
		background: var(--accent-soft);
	}
	.score td.best {
		font-weight: 800;
	}
	.score tfoot td,
	.score tfoot th {
		color: var(--text-muted);
		font-size: 0.75rem;
		text-align: center;
	}
	.score tfoot th {
		text-align: left;
	}
	.verdicts {
		margin: 0.75rem 0 0;
		padding-left: 1.1rem;
		font-size: 0.88rem;
		color: var(--text-secondary);
	}
	.coef {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}
	.coef th {
		text-align: left;
		font-size: 0.75rem;
		color: var(--text-secondary);
		border-bottom: 1px solid var(--border);
		padding: 0 0.3rem 0.35rem;
	}
	.coef td {
		padding: 0.35rem 0.3rem;
		border-bottom: 1px solid var(--grid);
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
</style>
