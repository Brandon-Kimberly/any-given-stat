<script lang="ts">
	import { base } from '$app/paths';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { epa, pct } from '$lib/format';
	import { gridX, gridY, isNarrow, Plot, plotStyle } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { resource } from '$lib/resource.svelte';
	import { median } from '$lib/stats';
	import { teamColor, teamName } from '$lib/teams.svelte';
	import type { TeamSeason } from '$lib/types';

	const metaRes = resource('meta');
	const teamsRes = resource('teams');
	const meta = $derived(metaRes.value);
	const teams = $derived(teamsRes.value ?? []);

	let focus = $state('');
	let adjusted = $state(false);
	const xKey = $derived(adjusted ? 'adj_off_epa' : 'off_epa_play');
	const yKey = $derived(adjusted ? 'adj_def_epa' : 'def_epa_play');
	const rows = $derived(teams.filter((t) => t.season === prefs.season && t.scope === prefs.scope));
	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));

	function render(width: number) {
		const xs = rows.map((r) => r[xKey]!);
		const ys = rows.map((r) => r[yKey]!);
		const pad = 0.03;
		const x0 = Math.min(...xs) - pad;
		const x1 = Math.max(...xs) + pad;
		const y0 = Math.min(...ys) - pad;
		const y1 = Math.max(...ys) + pad;
		// Net EPA iso-lines: off - def = c  ->  def = off - c.
		const tiers = [-0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3].map((c) => ({
			c,
			x1: x0,
			y1: x0 - c,
			x2: x1,
			y2: x1 - c
		}));
		// Label each iso-line where it leaves the plot through the top edge (best defense), if it does.
		const tierLabels = tiers
			.map((t) => ({ c: t.c, x: y0 + t.c, y: y0 }))
			.filter((t) => t.x > x0 + (x1 - x0) * 0.04 && t.x < x1 - (x1 - x0) * 0.22);
		const narrow = isNarrow(width);
		const height = Math.min(520, Math.max(360, width * 0.72));
		// Labels: the highlighted team first, then the extremes, so decluttering keeps those.
		const labelOrder = [...rows].sort(
			(a, b) =>
				Number(b.team === focus) - Number(a.team === focus) ||
				Math.abs(b.net_epa_play) - Math.abs(a.net_epa_play)
		);
		return Plot.plot({
			width,
			height,
			style: plotStyle,
			r: { type: 'identity' }, // radii below are pixels; Plot would rescale them
			marginRight: 20,
			x: {
				domain: [x0, x1],
				label: `${adjusted ? 'Adjusted offense' : 'Offense'} EPA/play (better →)`,
				tickFormat: '+.2f'
			},
			y: {
				domain: [y0, y1],
				reverse: true,
				label: `↑ ${adjusted ? 'Adjusted defense' : 'Defense'} EPA/play allowed (better up)`,
				tickFormat: '+.2f',
				ticks: 8
			},
			marks: [
				gridX(),
				gridY(),
				Plot.link(tiers, {
					x1: 'x1',
					y1: 'y1',
					x2: 'x2',
					y2: 'y2',
					stroke: 'var(--axis)',
					strokeWidth: 1,
					clip: true
				}),
				Plot.text(narrow ? [] : tierLabels, {
					x: 'x',
					y: 'y',
					text: (t: { c: number }) => `net ${epa(t.c, 1)}`,
					textAnchor: 'start',
					dx: 6,
					dy: 10,
					fontSize: 10,
					fill: 'var(--text-muted)'
				}),
				Plot.ruleX([median(xs)], { stroke: 'var(--axis)', strokeWidth: 1.5 }),
				Plot.ruleY([median(ys)], { stroke: 'var(--axis)', strokeWidth: 1.5 }),
				Plot.text(narrow ? [] : ['Good offense · good defense'], {
					frameAnchor: 'top-right',
					dx: -4,
					dy: 4,
					fill: 'var(--text-muted)',
					fontSize: 11
				}),
				Plot.text(narrow ? [] : ['Bad offense · bad defense'], {
					frameAnchor: 'bottom-left',
					dx: 4,
					dy: -4,
					fill: 'var(--text-muted)',
					fontSize: 11
				}),
				Plot.dot(rows, {
					x: xKey,
					y: yKey,
					r: (d: TeamSeason) => (d.team === focus ? 10 : narrow ? 5 : 7),
					fill: (d: TeamSeason) => teamColor(d.team),
					fillOpacity: (d: TeamSeason) => (focus && d.team !== focus ? 0.35 : 1),
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.text(labelOrder, {
					x: xKey,
					y: yKey,
					text: 'team',
					dy: narrow ? -10 : -13,
					fontSize: narrow ? 10 : 11,
					fontWeight: 600,
					fill: 'var(--text-secondary)',
					className: 'declutter'
				}),
				Plot.tip(
					rows,
					Plot.pointer({
						lineWidth: 40,
						x: xKey,
						y: yKey,
						title: (d: TeamSeason) =>
							`${teamName(d.team)}\nNet EPA/play  ${epa(d.net_epa_play)}\nOffense  ${epa(d.off_epa_play)}  (pass ${epa(d.off_pass_epa)}, rush ${epa(d.off_rush_epa)})\nDefense  ${epa(d.def_epa_play)}  (pass ${epa(d.def_pass_epa)}, rush ${epa(d.def_rush_epa)})\nOpponent-adjusted: off ${epa(d.adj_off_epa)}, def ${epa(d.adj_def_epa)}, net ${epa(d.adj_net_epa)}`
					})
				)
			]
		});
	}

	const columns: Column<TeamSeason>[] = [
		{ key: 'team', label: 'Team', sticky: true, team: true },
		{
			key: 'net_epa_play',
			label: 'Net EPA',
			fmt: epa,
			better: 'high',
			title: 'Offense EPA/play minus defense EPA/play allowed'
		},
		{
			key: 'adj_net_epa',
			label: 'Adj net',
			fmt: epa,
			better: 'high',
			title: 'Net EPA/play adjusted for opponents faced and home field'
		},
		{
			key: 'off_epa_play',
			label: 'Off EPA',
			fmt: epa,
			better: 'high',
			title: 'Offense EPA per play'
		},
		{ key: 'off_pass_epa', label: 'Off pass', fmt: epa, better: 'high' },
		{ key: 'off_rush_epa', label: 'Off rush', fmt: epa, better: 'high' },
		{
			key: 'off_success_rate',
			label: 'Off success',
			fmt: pct,
			better: 'high',
			title: 'Success rate: share of plays with EPA > 0'
		},
		{
			key: 'def_epa_play',
			label: 'Def EPA',
			fmt: epa,
			better: 'low',
			title: 'EPA per play allowed (lower is better)'
		},
		{ key: 'def_pass_epa', label: 'Def pass', fmt: epa, better: 'low' },
		{ key: 'def_rush_epa', label: 'Def rush', fmt: epa, better: 'low' },
		{
			key: 'def_success_rate',
			label: 'Def success',
			fmt: pct,
			better: 'low',
			title: 'Success rate allowed (lower is better)'
		}
	];
</script>

<svelte:head><title>Team tiers · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Teams</div>
	<h1>Team tiers</h1>
	<p class="lede">
		Every team's offense against its defense, in expected points added per play. Up and to the right
		is good. The diagonal lines mark equal net EPA, so teams on the same line are about equally
		good, just built differently. <strong>Opponent-adjusted</strong> removes schedule strength and home
		field, which matters most early in the season when schedules are lopsided.
	</p>
</section>

{#if meta}
	<div class="toolbar">
		<Controls seasons={meta.seasons} />
		<div class="seg" role="group" aria-label="Adjustment">
			<button aria-pressed={!adjusted} onclick={() => (adjusted = false)}>Raw</button>
			<button
				aria-pressed={adjusted}
				title="Adjusted for opponents faced and home field"
				onclick={() => (adjusted = true)}>Opponent-adjusted</button
			>
		</div>
		<label class="field">
			Highlight
			<select bind:value={focus}>
				<option value="">None</option>
				{#each [...rows].sort((a, b) => a.team.localeCompare(b.team)) as r (r.team)}
					<option value={r.team}>{r.team}</option>
				{/each}
			</select>
		</label>
	</div>
	<SampleWarning {status} />
{/if}

{#if teamsRes.error}
	<LoadError message={teamsRes.error} />
{:else if !rows.length}
	<Skeleton height={420} />
{:else}
	<div class="card">
		<PlotFigure label="Scatter of offense vs defense EPA per play by team" {render} />
		<p class="muted chart-note">
			Dots use team colors; overlapping labels are hidden, so hover a dot or use Highlight to find a
			team.
		</p>
	</div>
{/if}

<div class="card">
	<h2>Net EPA rankings</h2>
	<p class="sub">Click a team for its weekly trend and game log.</p>
	<DataTable
		{rows}
		{columns}
		sortKey="net_epa_play"
		search="team"
		highlight={(r) => r.team === focus}
		href={(r) => `${base}/team/?t=${r.team}`}
		filename="team-tiers-{prefs.season}"
	/>
</div>

<style>
	.chart-note {
		font-size: 0.8rem;
		margin: 0.5rem 0 0;
	}
</style>
