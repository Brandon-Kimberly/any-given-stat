<script lang="ts">
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import { load } from '$lib/data';
	import { corr, num, pct, signed } from '$lib/format';
	import { gridX, gridY, Plot, plotStyle } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { mean, ols } from '$lib/stats';
	import type { Luck, Meta } from '$lib/types';

	let meta = $state<Meta>();
	let all = $state<Luck[]>([]);
	load('meta').then((m) => (meta = m));
	load('luck').then((l) => (all = l));

	type Row = Luck & { one_score: string; losses: number };
	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));
	const rows = $derived<Row[]>(
		all
			.filter((l) => l.season === prefs.season)
			.map((l) => ({
				...l,
				losses: l.games - l.wins,
				one_score: `${l.one_score_wins ?? 0}–${l.one_score_games - (l.one_score_wins ?? 0)}`
			}))
	);
	const lucky = $derived(
		[...rows].sort((a, b) => b.wins_over_pythag - a.wins_over_pythag).slice(0, 3)
	);
	const unlucky = $derived(
		[...rows].sort((a, b) => a.wins_over_pythag - b.wins_over_pythag).slice(0, 3)
	);

	// History: does beating your Pythagorean record carry over? Pair each complete season with the next.
	const complete = $derived(new Set(meta?.seasons.filter((s) => s.complete).map((s) => s.season)));
	const pairs = $derived.by(() => {
		const key = new Map(all.map((l) => [`${l.season}|${l.team}`, l]));
		return all
			.filter((l) => complete.has(l.season) && complete.has(l.season + 1))
			.flatMap((l) => {
				const next = key.get(`${l.season + 1}|${l.team}`);
				if (!next) return [];
				// Scale to 17 games so 16-game seasons compare cleanly.
				const per17 = (x: number, g: number) => (x / g) * 17;
				return [
					{
						team: l.team,
						season: l.season,
						over: per17(l.wins_over_pythag, l.games),
						change: per17(next.wins, next.games) - per17(l.wins, l.games)
					}
				];
			});
	});
	const fit = $derived(
		pairs.length > 2
			? ols(
					pairs.map((p) => p.over),
					pairs.map((p) => p.change)
				)
			: null
	);
	const bigOver = $derived(pairs.filter((p) => p.over >= 2));
	const bigUnder = $derived(pairs.filter((p) => p.over <= -2));

	function expected(width: number) {
		const lo = Math.min(...rows.map((r) => Math.min(r.wins, r.pythag_wins))) - 0.5;
		const hi = Math.max(...rows.map((r) => Math.max(r.wins, r.pythag_wins))) + 0.5;
		return Plot.plot({
			width,
			height: Math.min(520, Math.max(340, width * 0.65)),
			style: plotStyle,
			x: { domain: [lo, hi], label: 'Pythagorean wins (from points scored and allowed) →' },
			y: { domain: [lo, hi], label: '↑ Actual wins' },
			marks: [
				gridX(),
				gridY(),
				Plot.line(
					[
						[lo, lo],
						[hi, hi]
					],
					{ stroke: 'var(--axis)', strokeWidth: 1.5 }
				),
				Plot.text(['Luckier than their points'], {
					frameAnchor: 'top-left',
					dx: 4,
					dy: 4,
					fill: 'var(--text-muted)',
					fontSize: 11
				}),
				Plot.text(['Unluckier'], {
					frameAnchor: 'bottom-right',
					dx: -4,
					dy: -4,
					fill: 'var(--text-muted)',
					fontSize: 11
				}),
				Plot.dot(rows, {
					x: 'pythag_wins',
					y: 'wins',
					r: 5,
					fill: 'var(--neutral-mark)',
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.text(rows, {
					x: 'pythag_wins',
					y: 'wins',
					text: 'team',
					dy: -11,
					fontSize: 10.5,
					fill: 'var(--text-secondary)'
				}),
				Plot.tip(
					rows,
					Plot.pointer({
						x: 'pythag_wins',
						y: 'wins',
						title: (d: Row) =>
							`${d.team}: ${d.wins}–${d.losses}\nPythagorean ${num(d.pythag_wins, 1)} (${signed(d.wins_over_pythag)})\nOne-score games ${d.one_score}\nPoint diff ${signed(d.points_for - d.points_against, 0)}`
					})
				)
			]
		});
	}

	function regression(width: number) {
		const xs = pairs.map((p) => p.over);
		const x0 = Math.min(...xs);
		const x1 = Math.max(...xs);
		return Plot.plot({
			width,
			height: 320,
			style: plotStyle,
			x: { label: 'Wins over Pythagorean, season N (per 17 games) →', tickFormat: '+.0f' },
			y: { label: '↑ Change in wins, season N+1', tickFormat: '+.0f' },
			marks: [
				gridX(),
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.ruleX([0], { stroke: 'var(--axis)' }),
				Plot.dot(pairs, {
					x: 'over',
					y: 'change',
					r: 3,
					fill: 'var(--neutral-mark)',
					fillOpacity: 0.55
				}),
				fit
					? Plot.line(
							[
								[x0, fit.a + fit.b * x0],
								[x1, fit.a + fit.b * x1]
							],
							{ stroke: 'var(--series-1)', strokeWidth: 2 }
						)
					: null,
				Plot.tip(
					pairs,
					Plot.pointer({
						x: 'over',
						y: 'change',
						title: (d: (typeof pairs)[number]) =>
							`${d.team} ${d.season}: ${signed(d.over)} over Pythag\nNext season: ${signed(d.change)} wins`
					})
				)
			]
		});
	}

	const columns: Column<Row>[] = [
		{ key: 'team', label: 'Team', sticky: true },
		{ key: 'wins', label: 'W', fmt: (v) => num(v, v % 1 ? 1 : 0) },
		{ key: 'losses', label: 'L', fmt: (v) => num(v, v % 1 ? 1 : 0) },
		{ key: 'pythag_wins', label: 'Pythag W', fmt: (v) => num(v, 1) },
		{
			key: 'wins_over_pythag',
			label: 'W over Pythag',
			fmt: (v) => signed(v),
			title: 'Positive = record better than point differential implies'
		},
		{ key: 'one_score', label: 'One-score', title: 'Record in games decided by 8 or fewer' },
		{
			key: 'fumble_recovery_rate',
			label: 'Fumble rec%',
			fmt: pct,
			title: 'Share of all fumbles in their games that they recovered. ~50% is normal.'
		},
		{ key: 'fumbles', label: 'Fumbles', fmt: num },
		{ key: 'turnover_margin', label: 'TO margin', fmt: (v) => signed(v, 0) },
		{ key: 'points_for', label: 'PF', fmt: num },
		{ key: 'points_against', label: 'PA', fmt: num }
	];
</script>

<svelte:head><title>Luck · Any Given Stat</title></svelte:head>

<section>
	<h1>Luck</h1>
	<p class="lede">
		A team's record is its point differential plus noise. The Pythagorean formula (points scored and
		allowed, exponent 2.37) estimates how many games a team “should” have won. Close-game records
		and fumble recoveries are mostly coin flips, so teams that beat their expectation usually come
		back to earth.
	</p>
</section>

{#if meta}
	<Controls seasons={meta.seasons} showScope={false} />
	<SampleWarning {status} />
{/if}

{#if rows.length}
	<div class="tiles">
		<div class="card tile">
			<div class="label">Luckiest {prefs.season}</div>
			<div class="value">{lucky.map((r) => r.team).join(', ')}</div>
			<div class="note">
				{lucky.map((r) => signed(r.wins_over_pythag)).join(' · ')} wins vs Pythag
			</div>
		</div>
		<div class="card tile">
			<div class="label">Unluckiest {prefs.season}</div>
			<div class="value">{unlucky.map((r) => r.team).join(', ')}</div>
			<div class="note">
				{unlucky.map((r) => signed(r.wins_over_pythag)).join(' · ')} wins vs Pythag
			</div>
		</div>
		{#if bigOver.length}
			<div class="card tile">
				<div class="label">Beat Pythag by 2+ wins → next year</div>
				<div class="value">{signed(mean(bigOver.map((p) => p.change)))} wins</div>
				<div class="note">
					average change, {bigOver.length} teams since {Math.min(...pairs.map((p) => p.season))}
				</div>
			</div>
		{/if}
		{#if bigUnder.length}
			<div class="card tile">
				<div class="label">Missed Pythag by 2+ wins → next year</div>
				<div class="value">{signed(mean(bigUnder.map((p) => p.change)))} wins</div>
				<div class="note">average change, {bigUnder.length} teams</div>
			</div>
		{/if}
	</div>

	<div class="grid-2">
		<div class="card">
			<h2>Record vs points</h2>
			<p class="sub">Teams above the diagonal won more than their scoring margin implies.</p>
			<PlotFigure label="Actual wins vs Pythagorean wins" render={expected} />
		</div>
		<div class="card">
			<h2>Does luck carry over?</h2>
			<p class="sub">
				Every team-season since {Math.min(...pairs.map((p) => p.season))}.
				{#if fit}
					Slope {signed(fit.b, 2)}, r = {corr(fit.r)}. A negative slope means luck reverses: each
					win of luck in season N predicts about {num(Math.abs(fit.b), 2)} fewer wins the next season.
				{/if}
			</p>
			{#if pairs.length}<PlotFigure
					label="Wins over Pythagorean vs next-season change in wins"
					render={regression}
				/>{/if}
		</div>
	</div>

	<div class="card">
		<DataTable {rows} {columns} sortKey="wins_over_pythag" search="team" />
	</div>
{/if}
