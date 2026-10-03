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
				{ season, v: s.clear ? s.went / s.clear : 0, what: 'Went for it in clear-go spots' },
				{ season, v: s.fourth ? s.goes / s.fourth : 0, what: 'Went for it on any 4th down' }
			]);
	});

	// Seasons still in progress -> their last fully played week. Their points are partial, so
	// they're drawn hollow, joined by a dashed segment and labeled "thru wk N".
	// Only the latest season can be in progress (2022 reads incomplete for its cancelled game).
	const live = $derived.by(() => {
		const cur = meta.value?.seasons.at(-1);
		return new Map(cur && !cur.complete ? [[cur.season, cur.last_week]] : []);
	});
	function trendChart(width: number) {
		const narrow = isNarrow(width);
		const last = trend.slice(-2);
		const done = trend.filter((t) => !live.has(t.season));
		const partial = trend.filter((t) => live.has(t.season));
		const lastDone = Math.max(...done.map((t) => t.season));
		const tail = trend.filter((t) => t.season === lastDone || live.has(t.season));
		return Plot.plot({
			width,
			height: 290,
			style: plotStyle,
			marginRight: narrow ? 24 : 200,
			marginBottom: partial.length ? 42 : 30,
			x: {
				label: null,
				ticks: thinTicks([...new Set(trend.map((t) => t.season))], width, 42),
				tickFormat: (s: number) => (live.has(s) ? `${s}\nthru wk ${live.get(s)}` : `${s}`)
			},
			y: {
				label: '↑ Share of 4th downs',
				tickFormat: '.0%',
				domain: [0, Math.max(0.2, ...trend.map((t) => t.v)) * 1.15]
			},
			color: {
				domain: ['Went for it in clear-go spots', 'Went for it on any 4th down'],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			marks: [
				gridY(),
				Plot.line(done, { x: 'season', y: 'v', stroke: 'what', strokeWidth: 2 }),
				Plot.line(partial.length ? tail : [], {
					x: 'season',
					y: 'v',
					stroke: 'what',
					strokeWidth: 2,
					strokeDasharray: '4,4'
				}),
				Plot.dot(done, {
					x: 'season',
					y: 'v',
					fill: 'what',
					r: 4,
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.dot(partial, {
					x: 'season',
					y: 'v',
					stroke: 'what',
					fill: 'var(--surface)',
					r: 4.5,
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
							`${d.season}${live.has(d.season) ? ` (through week ${live.get(d.season)}, in progress)` : ''}: ${d.what}: ${pct(d.v, 1)}`
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
			height: Math.min(480, Math.max(320, width * 0.45)),
			style: plotStyle,
			marginTop: 32,
			// Insets keep edge dots (and their labels) off the axes' tick labels.
			x: { label: 'Went for it in clear-go spots →', tickFormat: '.0%', inset: 18 },
			y: { label: '↑ Less EPA left on the field (better)', reverse: true, nice: true, inset: 10 },
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
			title:
				'EPA left on the field: sum over 4th downs of (best decision’s average EPA − chosen decision’s)'
		},
		{
			key: 'lost_per_game',
			label: 'Per game',
			fmt: (v) => num(v, 2),
			better: 'low',
			title: 'EPA left on the field per game'
		},
		{ key: 'fourth_downs', label: '4th downs', fmt: (v) => num(v) },
		{
			key: 'go_rate',
			label: 'Go rate',
			fmt: (v) => pct(v),
			title: 'Share of all 4th downs where they went for it'
		},
		{
			key: 'clear_go',
			label: 'Clear-go spots',
			fmt: (v) => num(v),
			title: 'Situations where going for it was the best call by 0.3+ EPA'
		},
		{
			key: 'clear_rate',
			label: 'Went for it (clear-go)',
			fmt: (v) => pct(v),
			better: 'high',
			title: 'Share of clear-go spots where they went for it'
		}
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
			League-wide: how often teams went for it on any 4th down, and in spots where the data clearly
			said go. Competitive games only.
		</p>
		<PlotFigure label="League 4th down aggressiveness by season" render={trendChart} />
	</div>
	<div class="card">
		<h2>Who follows the math, {prefs.season}</h2>
		<p class="sub">Right = goes for it when the math says go. Up = less EPA left on the field.</p>
		{#if rows.length}<PlotFigure label="Aggressiveness vs EPA lost by team" render={scatter} />{/if}
		<aside class="note" aria-label="Read this with care">
			<p><strong>Read this with care.</strong> {res.value.meta.caveat}</p>
			<p>
				It's also coarse. Buckets are a few yards wide, so 4th and 1 at the opponent's 34 and at
				their 40 count as the same spot. Score and clock enter only through the competitive-game
				filter (win probability 5–95%). Real decision models, like the nflfastR 4th-down bot,
				simulate each option exactly. Still, the direction is robust: on short yardage almost
				everywhere past a team's own 20, going for it has paid off more than kicking it away.
			</p>
		</aside>
	</div>
	<div class="card">
		<h2>Every team's 4th-down calls, {prefs.season}</h2>
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

<style>
	.note {
		margin-top: 1rem;
		padding-top: 0.8rem;
		border-top: 1px solid var(--border);
		font-size: 0.86rem;
		color: var(--text-secondary);
	}
	.note p {
		margin: 0 0 0.5rem;
		max-width: 85ch;
	}
	.note p:last-child {
		margin-bottom: 0;
	}
</style>
