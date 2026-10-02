<script lang="ts">
	import { base } from '$app/paths';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { signed } from '$lib/format';
	import { gridY, isNarrow, Plot, plotStyle, thinTicks } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { resource, seasonResource } from '$lib/resource.svelte';
	import { teamName } from '$lib/teams.svelte';
	import type { Rating } from '$lib/types';

	const metaRes = resource('meta');
	const ratingsRes = seasonResource<Rating>('ratings', () => prefs.season);
	const meta = $derived(metaRes.value);
	const all = $derived(ratingsRes.value ?? []);

	const season = $derived(all.filter((r) => r.season === prefs.season));
	const weeks = $derived([...new Set(season.map((r) => r.week))].sort((a, b) => a - b));
	const lastWeek = $derived(weeks.at(-1) ?? 0);
	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));
	// Scrub the table back through the season; null = latest.
	let scrub = $state<number | null>(null);
	const shownWeek = $derived(scrub != null && weeks.includes(scrub) ? scrub : lastWeek);

	type Row = Rating & { change: number | null };
	const current = $derived<Row[]>(
		season
			.filter((r) => r.week === shownWeek)
			.map((r) => {
				const prev = season.find((p) => p.team === r.team && p.week === shownWeek - 1);
				return { ...r, change: prev ? prev.rank - r.rank : null };
			})
	);
	const allTeams = $derived([...new Set(season.map((r) => r.team))].sort());

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
	function add(e: Event) {
		const sel = e.currentTarget as HTMLSelectElement;
		if (sel.value && !highlighted.includes(sel.value)) toggle(sel.value);
		sel.value = '';
	}

	function trajectories(width: number) {
		const focus = season.filter((r) => highlighted.includes(r.team));
		const rest = season.filter((r) => !highlighted.includes(r.team));
		const ends = focus.filter((r) => r.week === lastWeek);
		const narrow = isNarrow(width);
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
			height: narrow ? 300 : 400,
			style: plotStyle,
			marginRight: narrow ? 12 : 50,
			x: { label: 'After week', tickFormat: 'd', ticks: thinTicks(weeks, width, 34) },
			y: { label: '↑ Net rating (points vs average team, neutral field)', tickFormat: '+.0f' },
			color: { domain: highlighted, range: SLOTS.slice(0, highlighted.length), legend: true },
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				shownWeek !== lastWeek
					? Plot.ruleX([shownWeek], { stroke: 'var(--accent)', strokeDasharray: '3,3' })
					: null,
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
				Plot.text(narrow ? [] : labelled, {
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
							`${teamName(d.team)} after week ${d.week}: #${d.rank}\n${signed(d.points)} pts (offense ${signed(d.off_points)}, defense ${signed(d.def_points)})`
					})
				)
			]
		});
	}

	const columns: Column<Row>[] = [
		{ key: 'team', label: 'Team', sticky: true, team: true },
		{ key: 'rank', label: 'Rank' },
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

<svelte:head><title>Power ratings {prefs.season} · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Teams</div>
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

{#if ratingsRes.error}
	<LoadError message="Ratings need seasons 2016–2021 in the build." />
{:else if !ratingsRes.value}
	<Skeleton height={380} />
{:else if current.length}
	<div class="card">
		<div class="card-head">
			<h2>Through week {lastWeek}</h2>
			<div class="picker">
				{#each highlighted as t (t)}
					<button class="pick" onclick={() => toggle(t)} aria-label="Remove {teamName(t)}">
						<TeamBadge team={t} /> <span aria-hidden="true">×</span>
					</button>
				{/each}
				{#if highlighted.length < 4}
					<select onchange={add} aria-label="Add a team to compare">
						<option value="">+ Compare team</option>
						{#each allTeams.filter((t) => !highlighted.includes(t)) as t (t)}
							<option value={t}>{teamName(t)}</option>
						{/each}
					</select>
				{/if}
			</div>
		</div>
		<p class="sub">Up to four teams in color; the rest of the league in grey for context.</p>
		<PlotFigure label="Power rating by week" render={trajectories} />
	</div>
	<div class="card">
		<div class="card-head">
			<h2>Standings after week {shownWeek}</h2>
			{#if weeks.length > 1}
				<label class="field scrub">
					Week
					<input
						type="range"
						min={weeks[0]}
						max={lastWeek}
						value={shownWeek}
						oninput={(e) => (scrub = +(e.currentTarget as HTMLInputElement).value)}
					/>
					<span class="tnum">{shownWeek}</span>
				</label>
			{/if}
		</div>
		<p class="sub">
			Click a team to add or remove it from the chart. Drag the slider to replay the season.
		</p>
		{#key shownWeek}
			<DataTable
				rows={current}
				{columns}
				sortKey="rank"
				sortDesc={false}
				search="team"
				showIndex={false}
				filename="power-ratings-{prefs.season}-wk{shownWeek}"
				highlight={(r) => highlighted.includes(r.team)}
				onrowclick={(r) => toggle(r.team)}
			/>
		{/key}
	</div>
{:else}
	<p class="muted">
		No ratings for {prefs.season} (the first season in the data has no prior year).
	</p>
{/if}

<style>
	.picker {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
	}
	.pick {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.15rem 0.45rem;
		min-height: 30px;
		border-radius: 999px;
	}
	.scrub input {
		width: min(240px, 40vw);
		accent-color: var(--accent);
	}
</style>
