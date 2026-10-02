<script lang="ts">
	import { base } from '$app/paths';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { num, pct } from '$lib/format';
	import { gridX, gridY, isNarrow, Plot, plotStyle, thinTicks } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { resource } from '$lib/resource.svelte';
	import { teamColor, teamName } from '$lib/teams.svelte';
	import type { FourthTeam } from '$lib/types';

	const meta = resource('meta');
	const res = resource('fourth_downs');
	const status = $derived(meta.value?.seasons.find((s) => s.season === prefs.season));

	type Row = FourthTeam & { clear_rate: number | null; lost_per_game: number | null };
	const games = $derived(
		new Map<number, number>((meta.value?.seasons ?? []).map((s) => [s.season, s.reg_games]))
	);
	const rows = $derived<Row[]>(
		(res.value?.teams ?? [])
			.filter((t) => t.season === prefs.season)
			.map((t) => {
				const g = ((games.get(t.season) ?? 0) * 2) / 32; // games per team
				return {
					...t,
					clear_rate: t.clear_go ? t.went_when_clear_go / t.clear_go : null,
					lost_per_game: g ? t.epa_lost / g : null
				};
			})
	);

	// League trend: how often teams went for it in clear-go spots, by season.
	const trend = $derived.by(() => {
		const by = new Map<number, { went: number; clear: number; fourth: number; goes: number }>();
		for (const t of res.value?.teams ?? []) {
			const s = by.get(t.season) ?? { went: 0, clear: 0, fourth: 0, goes: 0 };
			s.went += t.went_when_clear_go;
			s.clear += t.clear_go;
			s.fourth += t.fourth_downs;
			s.goes += t.go_rate * t.fourth_downs;
			by.set(t.season, s);
		}
		return [...by]
			.sort((a, b) => a[0] - b[0])
			.flatMap(([season, s]) => [
				{ season, v: s.clear ? s.went / s.clear : 0, what: 'Went for it when the data says go' },
				{ season, v: s.fourth ? s.goes / s.fourth : 0, what: 'Went for it on any 4th down' }
			]);
	});

	function trendChart(width: number) {
		const narrow = isNarrow(width);
		const last = trend.slice(-2);
		return Plot.plot({
			width,
			height: 280,
			style: plotStyle,
			marginRight: narrow ? 10 : 200,
			x: {
				label: null,
				tickFormat: 'd',
				ticks: thinTicks([...new Set(trend.map((t) => t.season))], width, 42)
			},
			y: {
				label: '↑ Share of 4th downs',
				tickFormat: '.0%',
				domain: [0, Math.max(0.2, ...trend.map((t) => t.v)) * 1.15]
			},
			color: {
				domain: ['Went for it when the data says go', 'Went for it on any 4th down'],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			marks: [
				gridY(),
				Plot.line(trend, { x: 'season', y: 'v', stroke: 'what', strokeWidth: 2 }),
				Plot.dot(trend, {
					x: 'season',
					y: 'v',
					fill: 'what',
					r: 4,
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.text(narrow ? [] : last, {
					x: 'season',
					y: 'v',
					text: (d: { v: number; what: string }) => `${pct(d.v, 0)} ${d.what.toLowerCase()}`,
					dx: 8,
					textAnchor: 'start',
					fill: 'var(--text-secondary)',
					fontSize: 11
				}),
				Plot.tip(
					trend,
					Plot.pointer({
						lineWidth: 40,
						x: 'season',
						y: 'v',
						title: (d: { season: number; v: number; what: string }) =>
							`${d.season}: ${d.what}: ${pct(d.v, 1)}`
					})
				)
			]
		});
	}

	function scatter(width: number) {
		const data = rows.filter((r) => r.clear_rate != null);
		const narrow = isNarrow(width);
		const order = [...data].sort((a, b) => b.epa_lost - a.epa_lost);
		return Plot.plot({
			width,
			height: Math.min(460, Math.max(320, width * 0.6)),
			style: plotStyle,
			x: { label: 'Went for it in clear-go spots →', tickFormat: '.0%' },
			y: { label: '↓ EPA left on the field (lower is better)', reverse: true },
			marks: [
				gridX(),
				gridY(),
				Plot.dot(data, {
					x: 'clear_rate',
					y: 'epa_lost',
					r: narrow ? 5 : 7,
					fill: (d: Row) => teamColor(d.team),
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.text(order, {
					x: 'clear_rate',
					y: 'epa_lost',
					text: 'team',
					dy: -12,
					fontSize: 10.5,
					fontWeight: 600,
					fill: 'var(--text-secondary)',
					className: 'declutter'
				}),
				Plot.tip(
					data,
					Plot.pointer({
						lineWidth: 40,
						x: 'clear_rate',
						y: 'epa_lost',
						title: (d: Row) =>
							`${teamName(d.team)}\nWent for it ${d.went_when_clear_go} of ${d.clear_go} clear-go spots\n${num(d.epa_lost, 1)} EPA left on the field (${num(d.lost_per_game, 2)} per game)`
					})
				)
			]
		});
	}

	const columns: Column<Row>[] = [
		{ key: 'team', label: 'Team', sticky: true, team: true },
		{ key: 'rank', label: 'Rank', title: '1 = least EPA lost to 4th-down decisions' },
		{
			key: 'epa_lost',
			label: 'EPA lost',
			fmt: (v) => num(v, 1),
			better: 'low',
			title: 'Sum over 4th downs of (best decision’s average EPA − chosen decision’s)'
		},
		{ key: 'lost_per_game', label: 'Per game', fmt: (v) => num(v, 2), better: 'low' },
		{ key: 'fourth_downs', label: '4th downs', fmt: (v) => num(v) },
		{ key: 'go_rate', label: 'Go rate', fmt: (v) => pct(v) },
		{
			key: 'clear_go',
			label: 'Clear-go spots',
			fmt: (v) => num(v),
			title: 'Situations where going for it was the best call by 0.3+ EPA'
		},
		{ key: 'clear_rate', label: 'Went when clear', fmt: (v) => pct(v), better: 'high' }
	];
</script>

<svelte:head><title>Fourth downs {prefs.season} · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Teams</div>
	<h1>Fourth downs</h1>
	<p class="lede">
		Every 4th down is a decision: go, punt or kick. Using what each choice actually produced across
		{res.value?.meta.reference_seasons?.join('–') ?? 'recent seasons'}, this page grades every
		team's calls. “EPA left on the field” adds up how much worse each decision was than the best
		option in that spot. The math behind it is on
		<a href="{base}/learn/#fourth">How football works</a>.
	</p>
</section>

{#if meta.value}
	<Controls seasons={meta.value.seasons} showScope={false} />
	<SampleWarning {status} />
{/if}

{#if res.error}
	<LoadError message={res.error} />
{:else if !res.value}
	<Skeleton height={320} />
{:else}
	<div class="card">
		<h2>The analytics revolution, measured</h2>
		<p class="sub">
			League-wide, how often teams went for it in spots where the data clearly favored going, and on
			4th downs overall (competitive game states only).
		</p>
		<PlotFigure label="League 4th down aggressiveness by season" render={trendChart} />
	</div>
	<div class="grid-2">
		<div class="card">
			<h2>Who follows the math, {prefs.season}</h2>
			<p class="sub">Right = aggressive when it's right to be; up = fewer points wasted.</p>
			{#if rows.length}<PlotFigure
					label="Aggressiveness vs EPA lost by team"
					render={scatter}
				/>{/if}
		</div>
		<div class="card">
			<h2>Read this with care</h2>
			<p>{res.value.meta.caveat}</p>
			<p>
				It's also coarse: buckets are a few yards wide, so a 4th and 1 at the opponent's 34 and at
				their 40 count as the same spot, and score and clock only enter through the competitive-game
				filter (win probability between 5% and 95%). Real decision models (like the nflfastR
				4th-down bot) simulate each option exactly.
			</p>
			<p class="muted">
				Still, the direction is robust: on short yardage almost everywhere past a team's own 20,
				going for it has paid off more than kicking it away.
			</p>
		</div>
	</div>
	<div class="card">
		<DataTable
			{rows}
			{columns}
			sortKey="rank"
			sortDesc={false}
			search="team"
			showIndex={false}
			href={(r) => `${base}/team/?t=${r.team}`}
			filename="fourth-downs-{prefs.season}"
		/>
	</div>
{/if}
