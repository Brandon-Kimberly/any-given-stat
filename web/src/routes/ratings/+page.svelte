<script lang="ts">
	import { base } from '$app/paths';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import { load } from '$lib/data';
	import { signed } from '$lib/format';
	import { gridY, Plot, plotStyle } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import type { Meta, Rating } from '$lib/types';

	let meta = $state<Meta>();
	let all = $state<Rating[]>([]);
	load('meta').then((m) => (meta = m));
	let error = $state<string | null>(null);
	load('ratings')
		.then((r) => (all = r))
		.catch(() => (error = 'Ratings need seasons 2016–2020 in the build (uv run ags build).'));

	const season = $derived(all.filter((r) => r.season === prefs.season));
	const lastWeek = $derived(Math.max(0, ...season.map((r) => r.week)));
	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));

	type Row = Rating & { change: number | null };
	const current = $derived<Row[]>(
		season
			.filter((r) => r.week === lastWeek)
			.map((r) => {
				const prev = season.find((p) => p.team === r.team && p.week === lastWeek - 1);
				return { ...r, change: prev ? prev.rank - r.rank : null };
			})
	);

	// Up to four highlighted teams get categorical colors; the rest stay neutral context.
	const SLOTS = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)'];
	let picked = $state<string[]>([]);
	const highlighted = $derived(
		picked.length
			? picked
			: [...current]
					.sort((a, b) => a.rank - b.rank)
					.slice(0, 3)
					.map((r) => r.team)
	);
	function toggle(team: string) {
		const base = picked.length ? picked : highlighted;
		picked = base.includes(team) ? base.filter((t) => t !== team) : [...base, team].slice(-4);
	}

	function trajectories(width: number) {
		const focus = season.filter((r) => highlighted.includes(r.team));
		const rest = season.filter((r) => !highlighted.includes(r.team));
		const ends = focus.filter((r) => r.week === lastWeek);
		// Direct-label line ends, skipping any that would overprint a label already placed;
		// the legend still identifies every highlighted team.
		const span =
			Math.max(...season.map((r) => r.points)) - Math.min(...season.map((r) => r.points));
		const labelled: Rating[] = [];
		for (const r of [...ends].sort((a, b) => b.points - a.points)) {
			if (labelled.every((l) => Math.abs(l.points - r.points) > span * 0.05)) labelled.push(r);
		}
		return Plot.plot({
			width,
			height: 380,
			style: plotStyle,
			marginRight: 50,
			x: { label: 'After week', tickFormat: 'd', ticks: [...new Set(season.map((r) => r.week))] },
			y: { label: '↑ Net rating (points vs average team, neutral field)', tickFormat: '+.0f' },
			color: { domain: highlighted, range: SLOTS.slice(0, highlighted.length), legend: true },
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.line(rest, {
					x: 'week',
					y: 'points',
					z: 'team',
					stroke: 'var(--neutral-mark)',
					strokeOpacity: 0.25,
					strokeWidth: 1
				}),
				Plot.line(focus, { x: 'week', y: 'points', stroke: 'team', strokeWidth: 2.5 }),
				Plot.dot(ends, {
					x: 'week',
					y: 'points',
					fill: 'team',
					r: 4.5,
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.text(labelled, {
					x: 'week',
					y: 'points',
					text: 'team',
					dx: 8,
					textAnchor: 'start',
					fill: 'var(--text-secondary)',
					fontWeight: 600
				}),
				Plot.tip(
					season,
					Plot.pointer({
						lineWidth: 40,
						x: 'week',
						y: 'points',
						title: (d: Rating) =>
							`${d.team} after week ${d.week}: #${d.rank}\n${signed(d.points)} pts (offense ${signed(d.off_points)}, defense ${signed(d.def_points)})`
					})
				)
			]
		});
	}

	const columns: Column<Row>[] = [
		{ key: 'rank', label: 'Rank' },
		{ key: 'team', label: 'Team', sticky: true },
		{
			key: 'points',
			label: 'Net (pts)',
			fmt: (v) => signed(v),
			better: 'high',
			title: 'Expected margin vs an average team on a neutral field'
		},
		{
			key: 'off_points',
			label: 'Offense (pts)',
			fmt: (v) => signed(v),
			better: 'high',
			title: "Offense's share of the net rating, in points"
		},
		{
			key: 'def_points',
			label: 'Defense (pts)',
			fmt: (v) => signed(v),
			better: 'high',
			title: "Defense's share of the net rating, in points (positive = good)"
		},
		{
			key: 'change',
			label: 'Δ rank',
			fmt: (v) => (v == null ? '–' : v === 0 ? '0' : signed(v, 0)),
			title: 'Change since the previous week'
		}
	];
</script>

<svelte:head><title>Power ratings · Any Given Stat</title></svelte:head>

<section>
	<h1>Power ratings</h1>
	<p class="lede">
		Predictive ratings: each team's offense and defense, adjusted for who they played and where,
		with recent games weighted more and last season fading in early on. These drive the
		<a href="{base}/predictions/">predicted spreads</a>. A rating of +3 means the team would be
		favored by about 3 points over an average team on a neutral field.
	</p>
</section>

{#if meta}
	<Controls seasons={meta.seasons} showScope={false} />
	<SampleWarning {status} />
{/if}

{#if current.length}
	<div class="card">
		<h2>Through week {lastWeek}</h2>
		<p class="sub">Click teams in the table to compare their paths (up to four).</p>
		<PlotFigure label="Power rating by week" render={trajectories} />
	</div>
	<div class="card">
		<DataTable
			rows={current}
			{columns}
			sortKey="rank"
			sortDesc={false}
			search="team"
			highlight={(r) => highlighted.includes(r.team)}
			onrowclick={(r) => toggle(r.team)}
		/>
	</div>
{:else if error}
	<p class="muted">{error}</p>
{:else if all.length}
	<p class="muted">
		No ratings for {prefs.season} (the first season in the data has no prior year).
	</p>
{/if}
