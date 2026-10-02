<script lang="ts">
	import { base } from '$app/paths';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { load } from '$lib/data';
	import { num, pct, signed, spread } from '$lib/format';
	import { gridX, gridY, Plot, plotStyle, thinTicks } from '$lib/plot';
	import type { BacktestStats, GamePrediction, Lab, LabRow, Predictions } from '$lib/types';

	let data = $state.raw<Predictions>();
	let lab = $state.raw<Lab>();
	let error = $state<string | null>(null);
	load('predictions')
		.then((p) => (data = p))
		.catch(() => (error = 'Predictions need seasons 2016–2021 in the build (uv run ags build).'));
	load('lab')
		.then((l) => (lab = l))
		.catch(() => {}); // optional: absent in partial builds

	const test = $derived(data?.summary.find((s) => s.split === 'test'));
	const [t0, t1] = $derived(data?.params.test_seasons ?? [0, 0]);
	// Everything from the validation seasons on was never used to fit coefficients.
	const oos0 = $derived(data?.params.validate_seasons[0] ?? 0);
	const atsPct = (s: BacktestStats) => s.ats_w / (s.ats_w + s.ats_l);
	// Standard -110 pricing: you must win 110/210 of bets to break even.
	const BREAKEVEN = 110 / 210;

	type Pick = GamePrediction & {
		matchup: string;
		model_line: string;
		vegas_line: string;
		diff: number | null;
		favorite_wp: string;
		qb_note: string;
	};

	/** e.g. "BAL −6.7 (C. Rush)": only sides where the starter moves the line by 1+ point. */
	function qbNote(g: GamePrediction): string {
		const parts = [
			[g.home, g.home_qb_pts, g.home_qb],
			[g.away, g.away_qb_pts, g.away_qb]
		] as const;
		return (
			parts
				.filter(([, pts]) => Math.abs(pts) >= 1)
				.map(([team, pts, name]) => `${team} ${signed(pts)}${name ? ` (${name})` : ''}`)
				.join(', ') || '–'
		);
	}
	const picks = $derived<Pick[]>(
		(data?.upcoming ?? []).map((g) => ({
			...g,
			matchup: `${g.away} ${g.neutral ? 'vs' : '@'} ${g.home}`,
			model_line: spread(g.model, g.home, g.away),
			vegas_line: spread(g.vegas, g.home, g.away),
			diff: g.vegas == null ? null : Math.abs(g.model - g.vegas),
			favorite_wp:
				g.home_wp >= 0.5 ? `${g.home} ${pct(g.home_wp, 0)}` : `${g.away} ${pct(1 - g.home_wp, 0)}`,
			qb_note: qbNote(g)
		}))
	);
	const nextWeek = $derived(data?.upcoming[0]);

	const pickColumns: Column<Pick>[] = [
		{ key: 'matchup', label: 'Game', sticky: true },
		{ key: 'gameday', label: 'Date' },
		{ key: 'model_line', label: 'Model line' },
		{ key: 'vegas_line', label: 'Vegas line' },
		{
			key: 'diff',
			label: 'Disagreement',
			fmt: (v) => (v == null ? '–' : `${num(v, 1)} pts`),
			title: 'Absolute gap between the model and the closing line'
		},
		{ key: 'favorite_wp', label: 'Model win prob' },
		{
			key: 'qb_note',
			label: 'QB adjustment',
			title:
				"Points added for the listed starter vs the QBs behind the team's rating (injury, rest, return)"
		}
	];

	function maeChart(width: number) {
		const rows = (data?.by_season ?? []).flatMap((s) => [
			{ season: s.season, mae: s.model_mae, who: 'Model' },
			{ season: s.season, mae: s.vegas_mae, who: 'Vegas closing line' }
		]);
		const seasons = data!.by_season.map((s) => s.season);
		return Plot.plot({
			width,
			height: 300,
			style: plotStyle,
			marginRight: 120,
			x: { label: null, tickFormat: 'd', ticks: thinTicks(seasons, width, 40) },
			y: { label: '↓ Average miss (points, lower is better)', zero: false },
			color: {
				domain: ['Model', 'Vegas closing line'],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			marks: [
				Plot.rectX([0], {
					x1: oos0 - 0.5,
					x2: Math.max(t1, ...seasons) + 0.5,
					fill: 'var(--surface-2)'
				}),
				Plot.text(['Out of sample'], {
					x: (oos0 + Math.max(t1, ...seasons)) / 2,
					frameAnchor: 'top',
					dy: 4,
					fill: 'var(--text-muted)',
					fontSize: 11
				}),
				gridY(),
				Plot.line(rows, { x: 'season', y: 'mae', stroke: 'who', strokeWidth: 2 }),
				Plot.dot(rows, {
					x: 'season',
					y: 'mae',
					fill: 'who',
					r: 4,
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.text(rows.slice(-2), {
					x: 'season',
					y: 'mae',
					text: 'who',
					dx: 8,
					textAnchor: 'start',
					fill: 'var(--text-secondary)'
				}),
				Plot.tip(
					rows,
					Plot.pointer({
						lineWidth: 40,
						x: 'season',
						y: 'mae',
						title: (d: { season: number; mae: number; who: string }) =>
							`${d.season} ${d.who}: misses by ${num(d.mae, 2)} pts on average`
					})
				)
			]
		});
	}

	// Calibration: bucket test-season home win probabilities, compare with how often home won.
	const calibration = $derived.by(() => {
		const games = (data?.games ?? []).filter(
			(g) => g.season >= t0 && g.season <= t1 && g.result !== 0
		);
		const bins = new Map<number, { n: number; wins: number; p: number }>();
		for (const g of games) {
			const b = Math.min(9, Math.floor(g.home_wp * 10));
			const cur = bins.get(b) ?? { n: 0, wins: 0, p: 0 };
			cur.n += 1;
			cur.wins += g.result > 0 ? 1 : 0;
			cur.p += g.home_wp;
			bins.set(b, cur);
		}
		return [...bins.values()]
			.filter((b) => b.n >= 10)
			.map((b) => ({ predicted: b.p / b.n, actual: b.wins / b.n, n: b.n }));
	});

	function calibrationChart(width: number) {
		return Plot.plot({
			width,
			height: Math.min(360, width * 0.8),
			style: plotStyle,
			x: { domain: [0, 1], label: 'Model home win probability →', tickFormat: '.0%' },
			y: { domain: [0, 1], label: '↑ Home team actually won', tickFormat: '.0%' },
			r: { range: [3, 12] },
			marks: [
				gridX(),
				gridY(),
				Plot.line(
					[
						[0, 0],
						[1, 1]
					],
					{ stroke: 'var(--axis)', strokeWidth: 1.5 }
				),
				Plot.dot(calibration, {
					x: 'predicted',
					y: 'actual',
					r: 'n',
					fill: 'var(--series-1)',
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.tip(
					calibration,
					Plot.pointer({
						lineWidth: 40,
						x: 'predicted',
						y: 'actual',
						title: (d: { predicted: number; actual: number; n: number }) =>
							`Predicted ${pct(d.predicted, 0)}, home won ${pct(d.actual, 0)}\n${d.n} games`
					})
				)
			]
		});
	}

	let season = $state<number | null>(null);
	const backtestSeasons = $derived([...new Set((data?.games ?? []).map((g) => g.season))].sort());
	const shownSeason = $derived(season ?? backtestSeasons.at(-1) ?? 0);
	type Past = Pick & { final: string; model_err: number; vegas_err: number | null; ats: string };
	const past = $derived<Past[]>(
		(data?.games ?? [])
			.filter((g) => g.season === shownSeason)
			.map((g) => {
				const side = g.vegas == null ? 0 : Math.sign(g.model - g.vegas);
				const actual = g.vegas == null ? 0 : Math.sign(g.result - g.vegas);
				return {
					...g,
					matchup: `Wk ${g.week}: ${g.away} ${g.neutral ? 'vs' : '@'} ${g.home}`,
					model_line: spread(g.model, g.home, g.away),
					vegas_line: spread(g.vegas, g.home, g.away),
					diff: g.vegas == null ? null : Math.abs(g.model - g.vegas),
					favorite_wp: '',
					qb_note: qbNote(g),
					final:
						g.result === 0 ? 'Tie' : `${g.result > 0 ? g.home : g.away} by ${Math.abs(g.result)}`,
					model_err: Math.abs(g.model - g.result),
					vegas_err: g.vegas == null ? null : Math.abs(g.vegas - g.result),
					ats: !side || !actual ? 'No bet / push' : side === actual ? 'Win' : 'Loss'
				};
			})
	);
	const pastColumns: Column<Past>[] = [
		{ key: 'matchup', label: 'Game', sticky: true },
		{ key: 'model_line', label: 'Model' },
		{ key: 'vegas_line', label: 'Vegas' },
		{ key: 'qb_note', label: 'QB adj' },
		{ key: 'final', label: 'Final' },
		{ key: 'model_err', label: 'Model miss', fmt: (v) => num(v, 1), better: 'low' },
		{ key: 'vegas_err', label: 'Vegas miss', fmt: (v) => num(v, 1), better: 'low' },
		{ key: 'ats', label: 'Model ATS' }
	];

	type LabView = LabRow & { label: string; chosen: boolean; mae_gap: number };
	const labRows = $derived<LabView[]>(
		(lab?.selection ?? []).map((r) => ({
			...r,
			label: r.threshold ? `${r.variant}, ${r.threshold}+ pt gap` : `${r.variant}, every game`,
			chosen: r.variant === lab?.chosen?.variant && r.threshold === lab?.chosen?.threshold,
			mae_gap: r.val_mae - r.val_vegas_mae
		}))
	);
	const labColumns: Column<LabView>[] = [
		{ key: 'label', label: 'Variant', sticky: true },
		{ key: 'val_bets', label: 'Bets', fmt: num },
		{
			key: 'val_win_rate',
			label: 'Win rate',
			fmt: (v) => pct(v),
			title: 'Against the closing spread, pushes excluded'
		},
		{
			key: 'val_p_value',
			label: 'p-value',
			fmt: (v) => (v == null ? '–' : num(v, 2)),
			title: 'Chance of doing at least this well with no edge (one-sided, vs 52.4%)'
		},
		{
			key: 'mae_gap',
			label: 'Miss vs Vegas',
			fmt: (v) => `${signed(v, 2)} pts`,
			better: 'low',
			title:
				'Average miss minus the closing line’s average miss (negative = more accurate than Vegas)'
		}
	];
</script>

<svelte:head><title>Predictions · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Games</div>
	<h1>Predictions vs Vegas</h1>
	<p class="lede">
		Point spreads from opponent-adjusted EPA <a href="{base}/ratings/">power ratings</a> plus a
		starting-quarterback adjustment, next to the Vegas line. Every game is predicted using only
		games played before it.
		{#if data}
			Coefficients were fit on {data.params.fit_seasons.join('–')}, choices made on
			{data.params.validate_seasons.join('–')}, and {t0}–{t1} was held back as a final test.
		{/if}
		The honest result: it gets closer to the closing line but doesn't beat it. See
		<a href="#lab">the attempt</a> below.
	</p>
</section>

{#if error}
	<LoadError message={error} />
{:else if !data}
	<Skeleton height={360} />
{:else}
	{#if nextWeek}
		<div class="card">
			<h2>Week {nextWeek.week}, {nextWeek.season}</h2>
			<p class="sub">
				Sorted by disagreement with Vegas. Win probabilities assume the final margin varies around
				the prediction with a standard deviation of {num(data.params.sigma, 1)} points.
			</p>
			<DataTable
				rows={picks}
				columns={pickColumns}
				sortKey="diff"
				showIndex={false}
				filename="predictions-week-{nextWeek.week}"
				href={(r) => `${base}/game/?id=${r.game_id}`}
			/>
		</div>
	{/if}

	{#if test}
		<div class="tiles">
			<div class="card tile">
				<div class="label">Average miss, {t0}–{t1} (held out)</div>
				<div class="value">{num(test.model_mae, 2)} pts</div>
				<div class="note">Vegas: {num(test.vegas_mae, 2)} pts ({test.games} games)</div>
			</div>
			<div class="card tile">
				<div class="label">Picked the winner</div>
				<div class="value">{pct(test.model_su)}</div>
				<div class="note">Vegas favorite won {pct(test.vegas_su)}</div>
			</div>
			<div class="card tile">
				<div class="label">Against the spread</div>
				<div class="value">{test.ats_w}–{test.ats_l}</div>
				<div class="note">
					{pct(atsPct(test))}; break-even at −110 is {pct(BREAKEVEN)}
				</div>
			</div>
			<div class="card tile">
				<div class="label">When it disagrees by 3+ points</div>
				<div class="value">{test.edge3_w}–{test.edge3_l}</div>
				<div class="note">
					{pct(test.edge3_w / (test.edge3_w + test.edge3_l))}: big disagreements aren't an edge
				</div>
			</div>
		</div>
	{/if}

	<div class="grid-2">
		<div class="card">
			<h2>Model vs the market, by season</h2>
			<p class="sub">
				Average absolute error of the predicted margin. The shaded seasons were never used for
				tuning.
			</p>
			<PlotFigure label="Model and Vegas average error by season" render={maeChart} />
		</div>
		<div class="card">
			<h2>Are the win probabilities honest?</h2>
			<p class="sub">
				Out-of-sample games grouped by predicted home win probability. Points on the diagonal mean a
				“70%” really wins about 70% of the time. Dot size = games.
			</p>
			{#if calibration.length}<PlotFigure
					label="Calibration of predicted win probabilities"
					render={calibrationChart}
				/>{/if}
		</div>
	</div>

	{#if lab}
		<div class="card" id="lab">
			<h2>Can anything here beat Vegas?</h2>
			<p class="sub">
				An attempt with rules fixed before looking at results. Six model variants, each fit on
				{lab.protocol.fit_seasons.join('–')} and scored on {lab.protocol.validate_seasons.join(
					'–'
				)}, betting every game or only when the model and the closing line disagree by
				{lab.protocol.thresholds.filter((t) => t).join(', ')}+ points. The best validation win rate
				(with at least {lab.protocol.min_validate_bets} bets) earned one look at
				{lab.protocol.test_seasons.join('–')}. Break-even at −110 is {pct(lab.protocol.breakeven)}.
			</p>
			{#if lab.chosen && lab.test}
				<div class="tiles" style="margin-bottom: 1rem">
					<div class="card tile">
						<div class="label">Chosen on validation</div>
						<div class="value" style="font-size: 1.15rem">{lab.chosen.variant}</div>
						<div class="note">
							{lab.chosen.threshold
								? `bet only ${lab.chosen.threshold}+ point disagreements`
								: 'bet every game'}
						</div>
					</div>
					<div class="card tile">
						<div class="label">Final test, {lab.protocol.test_seasons.join('–')}</div>
						<div class="value">{lab.test.wins}–{lab.test.bets - lab.test.wins}</div>
						<div class="note">
							{pct(lab.test.win_rate)}, p = {num(lab.test.p_value, 2)}:
							{(lab.test.win_rate ?? 0) > lab.protocol.breakeven && (lab.test.p_value ?? 1) < 0.05
								? 'beat the line'
								: 'no evidence of an edge'}
						</div>
					</div>
				</div>
			{/if}
			<DataTable
				rows={labRows}
				columns={labColumns}
				sortKey="val_win_rate"
				highlight={(r) => r.chosen}
			/>
			<p class="muted" style="margin-top: 0.75rem">
				“Market” variants use the closing line itself as an input and ask whether EPA, the QB
				change, rest or division games add anything to it. They give the line about 95% of the
				weight and end up within a few hundredths of a point of it: whatever those factors know, the
				line already knows. The QB adjustment does make the stats-only model more accurate, but not
				more accurate than the market.
			</p>
		</div>
	{/if}

	<div class="card">
		<div class="toolbar" style="margin-bottom: 0.5rem">
			<h2 style="margin: 0">Every prediction</h2>
			<label class="field">
				Season
				<select
					value={shownSeason}
					onchange={(e) => (season = +(e.currentTarget as HTMLSelectElement).value)}
				>
					{#each [...backtestSeasons].reverse() as s (s)}<option value={s}>{s}</option>{/each}
				</select>
			</label>
		</div>
		{#key shownSeason}
			<DataTable
				rows={past}
				columns={pastColumns}
				sortKey="week"
				sortDesc={false}
				search="matchup"
				showIndex={false}
				filename="predictions-{shownSeason}"
				href={(r) => `${base}/game/?id=${r.game_id}`}
			/>
		{/key}
	</div>

	<div class="card">
		<h2>How the model works</h2>
		<p>
			Each team-game becomes a row: the offense's EPA/play, explained by an offense rating, the
			opposing defense's rating and home field. A ridge regression (penalty {num(
				data.params.lambda
			)}
			plays, the equivalent of padding every team with that many plays of average football) fits it, weighting
			recent games more (half-life
			{data.params.half_life_weeks ? `${data.params.half_life_weeks} weeks` : 'none'}, with last
			season fading in). Ratings convert to points at
			{num(data.params.points_per_epa, 0)} points per EPA/play of rating gap, plus
			{num(data.params.home_points, 1)} points for home field. Garbage time is excluded.
		</p>
		<p>
			<strong>Quarterback adjustment.</strong> Team ratings bake in whoever played QB recently. For
			each game the model compares the listed starter's EPA per dropback (shrunk toward a
			below-average prior by 430 dropbacks, where QB EPA becomes half signal) with the
			dropback-weighted QBs behind the rating, times 35 dropbacks, with a fitted weight of
			{num(data.params.qb_weight, 2)}. That catches backups starting, stars resting and stars
			returning. Only adjustments of 1+ point are listed.
		</p>
		<p class="muted">
			What the market still knows that this doesn't: other injuries, weather, motivation, and the
			collective information of everyone betting. That's why the line still wins.
		</p>
	</div>
{/if}
