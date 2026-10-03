<script lang="ts">
	// Round 3: the forecast judged on accuracy (RMSE of the margin, log loss of win
	// probability), not on betting. Frozen choice, reused test, sealed live test. The
	// predictions page shows it in parts: the scorecard and the weights under "Accuracy", how
	// it was chosen under "Experiments".
	import { num, signed } from '$lib/format';
	import type { ForecastMetrics, Lab3, PairedDiff } from '$lib/types';
	import DataTable, { type Column } from './DataTable.svelte';

	let { lab, part }: { lab: Lab3; part: 'scorecard' | 'weights' | 'candidates' } = $props();
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
		{ key: 'sealed', label: `${p.live_season} after freeze` }
	] as const);
	const best = (split: (typeof SPLITS)[number]['key'], metric: 'rmse' | 'log_loss') =>
		Math.min(...MODELS.map((m) => lab.comparison[split][m.key][metric] ?? Infinity));
	const cell = (m: ForecastMetrics, metric: 'rmse' | 'log_loss') =>
		m[metric] == null ? '–' : num(m[metric], metric === 'rmse' ? 2 : 3);

	/** "X misses less (t = -1.1: could be noise)" from a paired squared-error difference. */
	function verdict(d: PairedDiff | null, a: string, b: string): string {
		if (!d || !d.se) return `no games yet to compare ${a} and ${b}`;
		const t = d.diff / d.se;
		const who = t < 0 ? a : b;
		const strength = Math.abs(t) >= 2 ? 'likely real' : 'could be noise';
		return `${who} misses less (t = ${signed(t, 1)}: ${strength})`;
	}
	const test = $derived(lab.comparison.test);

	type SelRow = Lab3['selection'][number] & { chosen: boolean };
	const selRows = $derived<SelRow[]>(
		lab.selection.map((r) => ({ ...r, chosen: r.variant === lab.chosen.variant }))
	);
	const selCols: Column<SelRow>[] = [
		{ key: 'variant', label: 'Candidate', sticky: true },
		{ key: 'features', label: 'Inputs' },
		{
			key: 'fit_rmse',
			label: 'Fit RMSE',
			fmt: (v) => num(v, 2),
			title: 'Typical miss on the fitting seasons, in points'
		},
		{
			key: 'val_rmse',
			label: 'Val RMSE',
			fmt: (v) => num(v, 3),
			better: 'low',
			title: 'Typical miss on validation, in points (the model was chosen on this)'
		},
		{
			key: 'val_log_loss',
			label: 'Val log loss',
			fmt: (v) => num(v, 4),
			better: 'low',
			title: 'Win-probability error on validation; lower is better'
		},
		{
			key: 'val_mae',
			label: 'Val avg miss',
			fmt: (v) => num(v, 2),
			title: 'Average miss on validation, in points'
		}
	];
</script>

{#if part === 'scorecard'}
	<section class="card" id="round3">
		<div class="eyebrow">Round 3 · the forecast this page shows</div>
		<h2>How close it gets, split by split</h2>
		<p class="sub">
			Scored on margin error (RMSE: the typical miss in points, with big misses counting extra) and
			win-probability error (log loss); lower is better on both, and the best in each column is
			bold. “Reused test” seasons were already seen by earlier rounds; games after the
			{p.freeze_date} freeze are the clean test.
		</p>
		<!-- Scrolls sideways on phones, so keyboard users need to reach it. -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
		<div class="scroll" tabindex="0" role="region" aria-label="Forecast scorecard by split">
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
				(the “best estimate”) moves the line {Math.round(lab.blend_k * 100)}% of the way toward the
				model, the weight that fit best on {p.fit_seasons.join('–')}.
			</li>
		</ul>
	</section>
{:else if part === 'weights'}
	<section class="card">
		<h2>What the forecast weighs</h2>
		<p class="sub">
			Coefficients refit on every completed season before {p.live_season}. “Per unit” is one unit's
			effect (± 95% range). “Typical” is how many points it moves a usual game (one standard
			deviation). Win probabilities assume a typical miss of {num(lab.sigma, 1)} points.
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
{:else}
	<section class="card">
		<h2>Built for accuracy, not betting</h2>
		<p class="sub">
			Rounds 1 and 2 asked whether we can beat the line. Round 3 asks how close a forecast can get
			to the actual result. {lab.selection.length} candidates were fit on {p.fit_seasons.join('–')};
			the one with the lowest validation RMSE was
			<a href="https://github.com/Brandon-Kimberly/any-given-stat/commit/9589541">frozen</a>
			on {p.freeze_date}: <b>{lab.chosen.variant}</b> (ties go to fewer inputs). Points ratings are a
			second team rating built from final scores. They catch what EPA misses: special teams and the full
			value of turnovers.
		</p>
		{#if !lab.selection_agrees}
			<div class="callout" role="note">
				Re-running the selection on today's data picks a different candidate (data revisions). The
				frozen choice is still the one shown.
			</div>
		{/if}
		<DataTable
			rows={selRows}
			columns={selCols}
			sortKey="val_rmse"
			sortDesc={false}
			highlight={(r) => r.chosen}
			filename="round3-selection"
		/>
	</section>
{/if}

<style>
	.scroll {
		overflow-x: auto;
	}
	.callout {
		margin-bottom: 0.75rem;
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
		max-width: 640px;
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
