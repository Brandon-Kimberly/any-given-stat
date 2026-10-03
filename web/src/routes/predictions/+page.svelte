<script lang="ts">
	// The forecast leads: next week's lines (round 3, the site's forecast) and what drives each
	// one, then how accurate it is, then the ledger, then the beat-the-line experiments (collapsed).
	import { base } from '$app/paths';
	import CountUp from '$lib/components/CountUp.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import ForecastFactors from '$lib/components/ForecastFactors.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import PageToc from '$lib/components/PageToc.svelte';
	import Round2 from '$lib/components/Round2.svelte';
	import Round3 from '$lib/components/Round3.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { load } from '$lib/data';
	import { num, pct, signed, spread } from '$lib/format';
	import { kickoffKey, kickoffLabelFromKey } from '$lib/kickoff';
	import { gridX, gridY, Plot, plotStyle } from '$lib/plot';
	import { prefs, savePrefs } from '$lib/prefs.svelte';
	import type {
		BacktestStats,
		BetScore,
		GamePrediction,
		Lab,
		Lab2,
		Lab3,
		LabRow,
		Meta,
		Predictions
	} from '$lib/types';
	import { onMount } from 'svelte';

	let data = $state.raw<Predictions>();
	let lab = $state.raw<Lab>();
	let lab2 = $state.raw<Lab2>();
	let lab3 = $state.raw<Lab3>();
	let meta = $state.raw<Meta>();
	let error = $state<string | null>(null);
	load('predictions')
		.then((p) => (data = p))
		.catch(() => (error = 'Couldn’t load predictions.'));
	load('lab')
		.then((l) => (lab = l))
		.catch(() => {}); // optional: absent in partial builds
	load('lab2')
		.then((l) => (lab2 = l))
		.catch(() => {});
	load('lab3')
		.then((l) => (lab3 = l))
		.catch(() => {});
	load('meta')
		.then((m) => (meta = m))
		.catch(() => {});

	const test = $derived(data?.summary.find((s) => s.split === 'test'));
	const [t0, t1] = $derived(data?.params.test_seasons ?? [0, 0]);
	// Everything from the validation seasons on was never used to fit coefficients.
	const oos0 = $derived(data?.params.validate_seasons[0] ?? 0);
	const atsPct = (s: BacktestStats) => s.ats_w / (s.ats_w + s.ats_l);
	// Standard -110 pricing: you must win 110/210 of bets to break even.
	const BREAKEVEN = 110 / 210;

	type Pick = GamePrediction & {
		matchup: string;
		kick: string;
		model_line: string;
		vegas_line: string;
		best_line: string;
		diff: number | null;
		best_wp: string;
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
	/** "NYG 55%": the favored side and its win probability. */
	const favWp = (g: GamePrediction, homeWp: number) =>
		homeWp >= 0.5 ? `${g.home} ${pct(homeWp, 0)}` : `${g.away} ${pct(1 - homeWp, 0)}`;
	const matchup = (g: GamePrediction) => `${g.away} ${g.neutral ? 'vs' : '@'} ${g.home}`;

	const nextWeek = $derived(data?.upcoming[0]);
	// This week's games, plus the next game of teams that already played this week (Thursday).
	const picks = $derived<Pick[]>(
		[...(data?.upcoming ?? []), ...(data?.next_games ?? [])].map((g) => ({
			...g,
			matchup: g.week === nextWeek?.week ? matchup(g) : `Wk ${g.week}: ${matchup(g)}`,
			kick: kickoffKey(g.gameday, g.gametime),
			model_line: spread(g.model, g.home, g.away),
			vegas_line: spread(g.vegas, g.home, g.away),
			best_line: g.blend == null ? '–' : spread(g.blend, g.home, g.away),
			diff: g.vegas == null ? null : Math.abs(g.model - g.vegas),
			best_wp: favWp(g, g.blend_wp ?? g.home_wp),
			qb_note: qbNote(g)
		}))
	);
	const blendK = $derived(data?.params.blend_k ?? lab3?.blend_k);
	const factorGames = $derived(lab3?.upcoming ?? []);

	const tocItems = $derived(
		[
			nextWeek && { id: 'this-week', label: `Week ${nextWeek.week}` },
			factorGames.length && { id: 'factors', label: 'Factor by factor' },
			test && { id: 'accuracy', label: 'Accuracy' },
			{ id: 'every', label: 'Every pick' },
			(lab || lab2 || lab3) && { id: 'experiments', label: 'Experiments' },
			{ id: 'how', label: 'How it works' }
		].filter((i): i is { id: string; label: string } => !!i)
	);

	const pickColumns = $derived<Column<Pick>[]>([
		{ key: 'matchup', label: 'Game', sticky: true },
		{
			key: 'model_line',
			label: 'Model',
			title: 'The site’s forecast: team ratings, starting QB, injuries and home field'
		},
		{ key: 'vegas_line', label: 'Vegas', title: 'The latest Vegas line' },
		{
			key: 'best_line',
			label: 'Best estimate',
			title: `The Vegas line moved ${blendK == null ? 'partway' : `${Math.round(blendK * 100)}% of the way`} toward the model. In tests, about as accurate as the line alone.`
		},
		{
			key: 'best_wp',
			label: 'Win prob',
			title: 'The favorite’s chance to win under the best estimate'
		},
		{ key: 'kick', label: 'Kickoff (ET)', fmt: kickoffLabelFromKey },
		{
			key: 'diff',
			label: 'Model vs Vegas',
			fmt: (v) => (v == null ? '–' : `${num(v, 1)} pts`),
			title: 'Gap between the model and the Vegas line, in points'
		},
		{
			key: 'qb_note',
			label: 'QB adjustment',
			title:
				"Points added for the listed starter vs the QBs behind the team's rating (injury, rest, return)"
		}
	]);

	// Accuracy by season (RMSE): the forecast, Vegas and round 1. A season in progress gets a
	// hollow point, a dashed segment and a "thru wk N" label.
	// Only the latest season can be in progress (2022 reads as incomplete: one game was cancelled).
	const liveStatus = $derived.by(() => {
		const s = meta?.seasons.at(-1);
		return s && !s.complete ? s : undefined;
	});
	const WHO = ['Forecast (round 3)', 'Vegas closing line', 'Round 1 model'];
	function seasonChart(width: number) {
		const by = lab3!.by_season;
		const rows = by
			.flatMap((s) => [
				{ season: s.season, rmse: s.round3, who: WHO[0] },
				{ season: s.season, rmse: s.vegas, who: WHO[1] },
				{ season: s.season, rmse: s.round1, who: WHO[2] }
			])
			.filter((r): r is { season: number; rmse: number; who: string } => r.rmse != null);
		const seasons = by.map((s) => s.season);
		const first = Math.min(...seasons);
		const last = Math.max(...seasons);
		const live = liveStatus && seasons.includes(liveStatus.season) ? liveStatus.season : null;
		const prev = live == null ? null : Math.max(...seasons.filter((s) => s < live));
		const done = rows.filter((r) => r.season !== live);
		const partial = rows.filter((r) => r.season === live);
		const bridge = rows.filter((r) => r.season === live || r.season === prev);
		const tickStep = Math.max(1, Math.ceil((seasons.length * 40) / Math.max(1, width - 70)));
		const liveTop = partial.length ? Math.max(...partial.map((r) => r.rmse)) : 0;
		return Plot.plot({
			width,
			height: 300,
			style: plotStyle,
			marginRight: 16,
			x: {
				label: null,
				tickFormat: 'd',
				// Every season that fits, counting back from the latest so it always has a tick.
				ticks: seasons.filter((s) => (last - s) % tickStep === 0),
				domain: [first - 0.4, last + 0.4]
			},
			y: { label: '↓ Typical miss, RMSE (points; lower is better)', nice: true },
			color: {
				domain: WHO,
				range: ['var(--series-1)', 'var(--series-2)', 'var(--series-3)'],
				legend: true
			},
			marks: [
				Plot.rectX([0], { x1: oos0 - 0.5, x2: last + 0.4, fill: 'var(--surface-2)' }),
				Plot.text(['Out of sample'], {
					x: (oos0 - 0.5 + last + 0.4) / 2,
					frameAnchor: 'bottom',
					dy: -6,
					fill: 'var(--text-muted)',
					fontSize: 11
				}),
				gridY(),
				Plot.line(done, { x: 'season', y: 'rmse', stroke: 'who', strokeWidth: 2 }),
				Plot.line(bridge, {
					x: 'season',
					y: 'rmse',
					stroke: 'who',
					strokeWidth: 2,
					strokeDasharray: '4 3'
				}),
				Plot.dot(done, {
					x: 'season',
					y: 'rmse',
					fill: 'who',
					r: 4,
					stroke: 'var(--surface)',
					strokeWidth: 1.5
				}),
				Plot.dot(partial, {
					x: 'season',
					y: 'rmse',
					stroke: 'who',
					fill: 'var(--surface)',
					r: 4,
					strokeWidth: 2
				}),
				...(live != null && liveStatus
					? [
							Plot.text([`thru wk ${liveStatus.last_week}`], {
								x: live,
								y: liveTop,
								dy: -13,
								dx: 6,
								textAnchor: 'end',
								fill: 'var(--text-secondary)',
								fontSize: 11
							})
						]
					: []),
				Plot.tip(
					rows,
					Plot.pointer({
						x: 'season',
						y: 'rmse',
						title: (d: (typeof rows)[number]) =>
							`${d.season} ${d.who}: typical miss ${num(d.rmse, 2)} pts` +
							(d.season === live ? `\nThrough week ${liveStatus?.last_week} only` : '')
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
			height: Math.min(300, width * 0.8),
			style: plotStyle,
			x: { domain: [0, 1], label: 'Model home win probability →', tickFormat: '.0%' },
			y: { domain: [0, 1], label: '↑ Home team actually won', tickFormat: '.0%' },
			r: { range: [4, 12] },
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

	// The ledger follows the site-wide season (prefs.season), falling back to the latest season
	// with predictions when that one has none (e.g. 2016, before the first predicted season).
	const backtestSeasons = $derived([...new Set((data?.games ?? []).map((g) => g.season))].sort());
	const shownSeason = $derived(
		prefs.season != null && backtestSeasons.includes(prefs.season)
			? prefs.season
			: (backtestSeasons.at(-1) ?? 0)
	);
	const shownStatus = $derived(meta?.seasons.find((s) => s.season === shownSeason));
	type Past = Pick & { final: string; model_err: number; vegas_err: number | null; ats: string };
	const past = $derived<Past[]>(
		(data?.games ?? [])
			.filter((g) => g.season === shownSeason)
			.map((g) => {
				const side = g.vegas == null ? 0 : Math.sign(g.model - g.vegas);
				const actual = g.vegas == null ? 0 : Math.sign(g.result - g.vegas);
				return {
					...g,
					matchup: `Wk ${g.week}: ${matchup(g)}`,
					kick: kickoffKey(g.gameday, g.gametime),
					model_line: spread(g.model, g.home, g.away),
					vegas_line: spread(g.vegas, g.home, g.away),
					best_line: g.blend == null ? '–' : spread(g.blend, g.home, g.away),
					diff: g.vegas == null ? null : Math.abs(g.model - g.vegas),
					best_wp: '',
					qb_note: qbNote(g),
					final:
						g.result === 0 ? 'Tie' : `${g.result > 0 ? g.home : g.away} by ${Math.abs(g.result)}`,
					model_err: Math.abs(g.model - g.result),
					vegas_err: g.vegas == null ? null : Math.abs(g.vegas - g.result),
					ats: !side || !actual ? 'Push / no pick' : side === actual ? 'Won' : 'Lost'
				};
			})
	);
	const pastColumns: Column<Past>[] = [
		{ key: 'matchup', label: 'Game', sticky: true },
		{ key: 'model_line', label: 'Model' },
		{ key: 'vegas_line', label: 'Vegas' },
		{
			key: 'qb_note',
			label: 'QB adj',
			title: 'Points added for the listed starter vs the QBs behind the team’s rating'
		},
		{ key: 'final', label: 'Final' },
		{ key: 'model_err', label: 'Model miss', fmt: (v) => num(v, 1), better: 'low' },
		{ key: 'vegas_err', label: 'Vegas miss', fmt: (v) => num(v, 1), better: 'low' },
		{
			key: 'ats',
			label: 'Model ATS',
			title: 'Would a bet on the model’s side of the Vegas line have won?'
		}
	];

	type LabView = LabRow & { label: string; chosen: boolean; mae_gap: number };
	const labRows = $derived<LabView[]>(
		(lab?.selection ?? []).map((r) => ({
			...r,
			label: r.threshold ? `${r.variant}, ${r.threshold}+ pt gap` : `${r.variant}, every game`,
			chosen: r.variant === lab?.chosen?.variant && r.threshold === lab?.chosen?.threshold,
			mae_gap: (r.val_mae ?? 0) - (r.val_vegas_mae ?? 0)
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

	// Experiments are collapsed; their contents render on first open. A link to one (#lab,
	// #round2, #round3-chosen) opens it.
	let open = $state<Record<string, boolean>>({});
	const EXPERIMENTS = ['round3-chosen', 'lab', 'round2'];
	function openFromHash() {
		const id = location.hash.slice(1);
		if (!EXPERIMENTS.includes(id)) return;
		open[id] = true;
		requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView());
	}
	onMount(() => {
		openFromHash();
		addEventListener('hashchange', openFromHash);
		return () => removeEventListener('hashchange', openFromHash);
	});
	const record = (s: BetScore) => `${s.wins}–${s.bets - s.wins}`;
</script>

<svelte:head><title>Predictions · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Games</div>
	<h1>Predictions vs Vegas</h1>
	<p class="lede">
		This week's point spreads from two opponent-adjusted <a href="{base}/ratings/">team ratings</a>
		(EPA per play and final scores), the starting quarterback and the injury report, next to the Vegas
		line. Every game is predicted using only games played before it. The honest result: it gets close
		to the closing line but doesn't beat it. See <a href="#accuracy">how accurate it is</a> and
		<a href="#experiments">the attempts to beat the line</a>.
	</p>
</section>

{#if error}
	<LoadError message={error} />
{:else if !data}
	<Skeleton height={360} />
{:else}
	<PageToc items={tocItems} />

	{#if nextWeek}
		<section class="card" id="this-week">
			<h2>Week {nextWeek.week}, {nextWeek.season}</h2>
			<p class="sub">
				<b>Model</b> is the site's forecast; <b>best estimate</b> moves the Vegas line
				{blendK == null ? 'partway' : `${Math.round(blendK * 100)}%`} toward it, and its win probability
				assumes the real margin misses by about {num(data.params.sigma, 1)} points (one standard deviation).
				In order of kickoff{data.next_games?.length
					? '; teams that already played this week show their next game'
					: ''}.
			</p>
			<DataTable
				rows={picks}
				columns={pickColumns}
				sortKey="kick"
				sortDesc={false}
				showIndex={false}
				filename="predictions-week-{nextWeek.week}"
				href={(r) => `${base}/game/?id=${r.game_id}`}
			/>
		</section>
	{/if}

	{#if factorGames.length}
		<section class="card" id="factors">
			<h2>Week {factorGames[0].week}, factor by factor</h2>
			<p class="sub">
				What moves each model line, in points toward the home team or the visitor. The factors add
				up to the Model column above.
			</p>
			<ForecastFactors
				games={factorGames}
				schedule={data.upcoming}
				injuriesIn={lab2 && {
					filed: lab2.protocol.teams_with_final_statuses,
					playing: lab2.protocol.teams_playing
				}}
			/>
		</section>
	{/if}

	{#if test}
		<div class="stack" id="accuracy">
			<div class="part-head">
				<div class="eyebrow">Accuracy</div>
				<h2>Close to the line, not better</h2>
			</div>
			<div class="tiles">
				<div class="card tile">
					<div class="label">Average miss, {t0}–{t1} test seasons</div>
					<div class="value"><CountUp text={`${num(test.model_mae, 2)} pts`} /></div>
					<div class="note">Vegas: {num(test.vegas_mae, 2)} pts ({test.games} games)</div>
				</div>
				<div class="card tile">
					<div class="label">Picked the winner</div>
					<div class="value"><CountUp text={pct(test.model_su)} /></div>
					<div class="note">Vegas favorite won {pct(test.vegas_su)}</div>
				</div>
				<div class="card tile">
					<div class="label">Against the spread</div>
					<div class="value"><CountUp text={`${test.ats_w}–${test.ats_l}`} /></div>
					<div class="note">
						{pct(atsPct(test))}; {pct(BREAKEVEN)} needed to profit at −110
					</div>
				</div>
				<div class="card tile">
					<div class="label">When it disagrees by 3+ points</div>
					<div class="value"><CountUp text={`${test.edge3_w}–${test.edge3_l}`} /></div>
					<div class="note">
						{pct(test.edge3_w / (test.edge3_w + test.edge3_l))}, vs {pct(BREAKEVEN)} needed to profit
					</div>
				</div>
			</div>

			{#if lab3}<Round3 lab={lab3} part="scorecard" />{/if}

			<div class="grid-2">
				{#if lab3}
					<section class="card">
						<h2>Accuracy by season</h2>
						<p class="sub">
							Each season is predicted using only earlier games. {lab3.protocol.fit_seasons.join(
								'–'
							)} also set the coefficients, so those years flatter the model; shaded seasons didn't.
						</p>
						<PlotFigure
							label="Forecast error by season: the forecast, Vegas and round 1"
							render={seasonChart}
						/>
					</section>
				{/if}
				<section class="card">
					<h2>Are the win probabilities honest?</h2>
					<p class="sub">
						Test-season games ({t0}–{t1}), grouped by the model's home win probability. Dots on the
						diagonal mean 70% picks won about 70% of the time. Dot size = games.
					</p>
					{#if calibration.length}<PlotFigure
							label="Calibration of predicted win probabilities"
							render={calibrationChart}
						/>{/if}
				</section>
			</div>

			{#if lab3}<Round3 lab={lab3} part="weights" />{/if}
		</div>
	{/if}

	<section class="card" id="every">
		<div class="toolbar" style="margin-bottom: 0.5rem">
			<h2 style="margin: 0">Every prediction</h2>
			<label class="field">
				Season
				<select
					value={shownSeason}
					onchange={(e) => {
						prefs.season = +(e.currentTarget as HTMLSelectElement).value;
						savePrefs();
					}}
				>
					{#each [...backtestSeasons].reverse() as s (s)}<option value={s}>{s}</option>{/each}
				</select>
			</label>
		</div>
		<SampleWarning status={shownStatus} />
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
	</section>

	{#if lab || lab2 || lab3}
		<div class="stack" id="experiments">
			<div class="part-head">
				<div class="eyebrow">Experiments</div>
				<h2>Trying to beat the line</h2>
				<p class="sub">
					Three pre-registered rounds, each with its rules fixed before the results were seen.
					Rounds 1 and 2 hunted for bets against the closing line; round 3 built the forecast above.
				</p>
			</div>

			{#if lab3}
				<details class="exp" id="round3-chosen" bind:open={open['round3-chosen']}>
					<summary class="card">
						<span class="eyebrow">Round 3</span>
						<span class="t">How the forecast was chosen</span>
						<span class="v"
							>{lab3.selection.length} candidates; frozen {lab3.protocol.freeze_date}: {lab3.chosen
								.variant}</span
						>
					</summary>
					{#if open['round3-chosen']}
						<div class="stack"><Round3 lab={lab3} part="candidates" /></div>
					{/if}
				</details>
			{/if}

			{#if lab}
				<details class="exp" id="lab" bind:open={open.lab}>
					<summary class="card">
						<span class="eyebrow">Round 1</span>
						<span class="t">Can anything here beat Vegas?</span>
						{#if lab.test}<span class="v"
								>Final test {lab.protocol.test_seasons.join('–')}: {lab.test.wins}–{lab.test.bets -
									lab.test.wins}, {pct(lab.test.win_rate)}
								{(lab.test.win_rate ?? 0) > lab.protocol.breakeven && (lab.test.p_value ?? 1) < 0.05
									? '(beat the line)'
									: '(no evidence of an edge)'}</span
							>{/if}
					</summary>
					{#if open.lab}
						<div class="stack">
							<section class="card">
								<p class="sub">
									Round 1 fixed its rules before looking at results. {Object.keys(lab.variants)
										.length}
									model variants were fit on {lab.protocol.fit_seasons.join('–')} and scored on
									{lab.protocol.validate_seasons.join('–')}, betting every game or only when the
									model and the closing line disagreed by {lab.protocol.thresholds
										.filter((t) => t)
										.join(', ')}+ points. The variant with the best validation win rate (min {lab
										.protocol.min_validate_bets} bets) got one look at {lab.protocol.test_seasons.join(
										'–'
									)}. Break-even at −110 is {pct(lab.protocol.breakeven)}.
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
											<div class="value">
												<CountUp text={`${lab.test.wins}–${lab.test.bets - lab.test.wins}`} />
											</div>
											<div class="note">
												{pct(lab.test.win_rate)}, p = {num(lab.test.p_value, 2)}:
												{(lab.test.win_rate ?? 0) > lab.protocol.breakeven &&
												(lab.test.p_value ?? 1) < 0.05
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
									“Market” variants use the closing line itself as an input and ask whether EPA, the
									QB change, rest or division games add anything to it. They give the line about 95%
									of the weight and end up within a few hundredths of a point of it: whatever those
									factors know, the line already knows. The QB adjustment does make the stats-only
									model more accurate, but not more accurate than the market.
								</p>
							</section>
						</div>
					{/if}
				</details>
			{/if}

			{#if lab2}
				<details class="exp" id="round2" bind:open={open.round2}>
					<summary class="card">
						<span class="eyebrow">Round 2</span>
						<span class="t">Injuries, travel, weather, stakes</span>
						<span class="v"
							>Live test after the freeze: {lab2.live.sealed.bets
								? record(lab2.live.sealed)
								: 'no bets yet'}; reused test {record(lab2.test)}</span
						>
					</summary>
					{#if open.round2}
						<div class="stack"><Round2 lab={lab2} /></div>
					{/if}
				</details>
			{/if}
		</div>
	{/if}

	<section class="card" id="how">
		<h2>How the model works</h2>
		<p>
			<strong>EPA ratings.</strong> Each team-game becomes a row: the offense's EPA/play, explained
			by an offense rating, the opposing defense's rating and home field. A ridge regression fits
			it. Ridge pulls every team toward average, as if each had {num(data.params.lambda)} extra plays
			of average football.
			{#if data.params.half_life_weeks}Recent games count more (a game {data.params.half_life_weeks}
				weeks old counts half), and last season's games carry weight early in the year.{/if}
			Garbage time is excluded.
		</p>
		<p>
			<strong>Points ratings.</strong> The same idea on final margins: each game's home margin, explained
			by team strengths and home field, with recent games counting more. Noisier than EPA, but it measures
			the thing being predicted, including special teams and the full value of turnovers.
		</p>
		<p>
			<strong>Injuries.</strong> Players listed Out or Doubtful count fully; Questionable players count
			a quarter. Each is weighted by his usual snap share and by how much of the team's recent play he
			was on the field for. That way a long absence the ratings already reflect isn't counted twice.
		</p>
		<p>
			<strong>Quarterback adjustment.</strong> Team ratings bake in whoever played QB recently. For
			each game, the model compares the listed starter's EPA per dropback with that of the QBs
			behind the rating, scaled to 35 dropbacks and a fitted weight of {num(
				data.params.qb_weight,
				2
			)}. The starter's number is pulled toward a below-average baseline as if he had 430 extra
			dropbacks, the sample at which QB EPA is half signal. That catches backups starting, stars
			resting and stars returning. Only adjustments of 1+ point are listed.
		</p>
		<p>
			<strong>Putting it together.</strong> A regression of the final margin on both rating gaps,
			the QB adjustment, injuries and home field turns them into points{#if lab3}{' '}(weights under
				<a href="#accuracy">accuracy</a>){/if}. Win probabilities assume the real margin misses that
			by about {num(data.params.sigma, 1)} points (one standard deviation). The best estimate moves the
			Vegas line partway toward the model; the weight was fit on
			{data.params.fit_seasons.join('–')}.
		</p>
		<p class="muted">
			Travel, rest, weather and late-season stakes were tested in <a href="#round2">round 2</a>.
			What no public dataset has: the pooled knowledge of everyone betting, and the early lines
			sharp bettors beat before the market settles.
		</p>
	</section>
{/if}

<style>
	.part-head {
		margin-top: 0.75rem;
	}
	.part-head h2 {
		margin: 0.15rem 0 0;
		font-stretch: 108%;
		font-size: 1.45rem;
	}
	.part-head .sub {
		margin: 0.35rem 0 0;
		max-width: 75ch;
	}
	.exp > .stack {
		margin-top: 1.1rem;
	}
	.exp > summary {
		list-style: none;
		cursor: pointer;
		display: grid;
		grid-template-columns: 1fr auto;
		grid-template-areas: 'eyebrow chev' 't chev' 'v chev';
		align-items: center;
		column-gap: 1rem;
	}
	.exp > summary::-webkit-details-marker {
		display: none;
	}
	.exp > summary::after {
		content: '';
		grid-area: chev;
		width: 9px;
		height: 9px;
		border-right: 2px solid var(--text-secondary);
		border-bottom: 2px solid var(--text-secondary);
		transform: rotate(45deg);
		transition: transform 0.15s;
	}
	.exp[open] > summary::after {
		transform: rotate(-135deg);
	}
	.exp > summary:hover {
		border-color: var(--border-strong);
	}
	.exp .eyebrow {
		grid-area: eyebrow;
	}
	.exp .t {
		grid-area: t;
		font: 700 1.1rem var(--display);
		color: var(--text-primary);
	}
	.exp .v {
		grid-area: v;
		font-size: 0.85rem;
		color: var(--text-secondary);
	}
</style>
