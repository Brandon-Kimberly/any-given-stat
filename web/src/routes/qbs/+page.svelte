<script lang="ts">
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import { base } from '$app/paths';
	import LoadError from '$lib/components/LoadError.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { epa, num, pct, signed } from '$lib/format';
	import { gridX, gridY, isNarrow, Plot, plotStyle, signedTick } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { resource } from '$lib/resource.svelte';
	import { median } from '$lib/stats';
	import { teamColor } from '$lib/teams.svelte';
	import type { QB } from '$lib/types';

	const metaRes = resource('meta');
	const qbsRes = resource('qbs');
	const meta = $derived(metaRes.value);
	const qbs = $derived(qbsRes.value ?? []);
	type Row = QB & { display: string };

	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));
	// Default bar: 10 dropbacks per week played (170 for a full season), floor of 50.
	let minDb = $state<number | null>(null);
	const threshold = $derived(
		minDb ?? Math.max(50, Math.round(((status?.reg_games ?? 272) / 16) * 10))
	);
	const rows = $derived<Row[]>(
		qbs
			.filter(
				(q) => q.season === prefs.season && q.scope === prefs.scope && q.dropbacks >= threshold
			)
			.map((q) => ({ ...q, display: q.full_name ?? q.name }))
	);
	const short = (q: QB) => q.name; // "P.Mahomes": compact chart labels

	function scatter(width: number) {
		const data = rows.filter((r) => r.cpoe != null);
		const narrow = isNarrow(width);
		// Label priority: the most-used QBs first, so decluttering keeps starters.
		const labels = [...data].sort((a, b) => b.dropbacks - a.dropbacks);
		return Plot.plot({
			width,
			height: Math.min(560, Math.max(360, width * 0.6)),
			style: plotStyle,
			r: { type: 'identity' }, // radii below are pixels; Plot would rescale them
			marginRight: 30,
			x: { label: 'CPOE (completion % over expected) →', tickFormat: signedTick },
			y: { label: '↑ EPA per dropback', tickFormat: '+.2f' },
			marks: [
				gridX(),
				gridY(),
				Plot.ruleX([median(data.map((d) => d.cpoe!))], { stroke: 'var(--axis)', strokeWidth: 1.5 }),
				Plot.ruleY([median(data.map((d) => d.epa_db))], {
					stroke: 'var(--axis)',
					strokeWidth: 1.5
				}),
				Plot.dot(data, {
					x: 'cpoe',
					y: 'epa_db',
					r: (d: QB) => Math.max(3.5, Math.sqrt(d.dropbacks) / (narrow ? 3.4 : 2.6)),
					fill: (d: QB) => teamColor(d.team),
					fillOpacity: 0.9,
					stroke: 'var(--surface)',
					strokeWidth: 1.5
				}),
				Plot.text(narrow ? [] : ['Accurate and efficient'], {
					frameAnchor: 'top-right',
					dx: -4,
					dy: 4,
					fill: 'var(--text-muted)',
					fontSize: 11
				}),
				Plot.text(labels, {
					x: 'cpoe',
					y: 'epa_db',
					text: short,
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
						x: 'cpoe',
						y: 'epa_db',
						title: (d: QB) =>
							`${d.full_name ?? d.name} (${d.teams})\nEPA/db ${epa(d.epa_db)}  [${epa(d.epa_db_lo)}, ${epa(d.epa_db_hi)}]\nCPOE ${signed(d.cpoe)}\n${num(d.dropbacks)} dropbacks`
					})
				)
			]
		});
	}

	function intervals(width: number) {
		const data = [...rows].sort((a, b) => b.epa_db - a.epa_db);
		const mid = median(data.map((d) => d.epa_db));
		return Plot.plot({
			width,
			height: Math.max(240, data.length * 18 + 50),
			style: plotStyle,
			marginLeft: Math.min(130, width * 0.36),
			x: {
				label: 'EPA per dropback, 95% interval',
				tickFormat: '+.2f',
				ticks: Math.max(3, Math.floor(width / 110))
			},
			y: { domain: data.map((d) => `${d.name} ${d.team}`), label: null },
			marks: [
				gridX(),
				Plot.ruleX([0], { stroke: 'var(--axis)' }),
				Plot.ruleX([mid], { stroke: 'var(--accent)', strokeDasharray: '3,3' }),
				Plot.ruleY(data, {
					y: (d: QB) => `${d.name} ${d.team}`,
					x1: 'epa_db_lo',
					x2: 'epa_db_hi',
					stroke: 'var(--series-1)',
					strokeWidth: 2,
					strokeOpacity: 0.45
				}),
				Plot.dot(data, {
					y: (d: QB) => `${d.name} ${d.team}`,
					x: 'epa_db',
					r: 4.5,
					fill: (d: QB) => teamColor(d.team),
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.tip(
					data,
					Plot.pointerY({
						lineWidth: 40,
						y: (d: QB) => `${d.name} ${d.team}`,
						x: 'epa_db',
						title: (d: QB) =>
							`${d.full_name ?? d.name}: ${epa(d.epa_db)} per dropback\n95% CI ${epa(d.epa_db_lo)} to ${epa(d.epa_db_hi)}\n${num(d.dropbacks)} dropbacks`
					})
				)
			]
		});
	}

	const columns: Column<Row>[] = [
		{ key: 'display', label: 'QB', sticky: true },
		{ key: 'team', label: 'Team', team: true },
		{ key: 'dropbacks', label: 'Dropbacks', fmt: num },
		{
			key: 'epa_db',
			label: 'EPA/db',
			fmt: epa,
			better: 'high',
			title: 'QB EPA per dropback (incl. sacks & scrambles)'
		},
		{ key: 'epa_db_lo', label: 'CI low', fmt: epa, title: '95% confidence interval, lower bound' },
		{ key: 'epa_db_hi', label: 'CI high', fmt: epa },
		{
			key: 'cpoe',
			label: 'CPOE',
			fmt: (v) => signed(v),
			better: 'high',
			title: 'Completion % over expected'
		},
		{ key: 'success_rate', label: 'Success', fmt: pct, better: 'high' },
		{ key: 'adot', label: 'aDOT', fmt: (v) => num(v, 1) },
		{ key: 'sack_rate', label: 'Sack%', fmt: pct, better: 'low' },
		{ key: 'int_rate', label: 'INT%', fmt: pct, better: 'low' },
		{ key: 'scramble_rate', label: 'Scramble%', fmt: pct },
		{ key: 'designed_runs', label: 'Designed runs', fmt: num },
		{
			key: 'designed_run_epa',
			label: 'Run EPA',
			fmt: (v) => signed(v),
			title: 'Total EPA on designed QB runs'
		},
		{
			key: 'total_epa',
			label: 'Total EPA',
			fmt: (v) => signed(v),
			better: 'high',
			title: 'Dropback + designed-run EPA'
		},
		{ key: 'pass_yards', label: 'Yards', fmt: num },
		{ key: 'pass_tds', label: 'TD', fmt: num },
		{ key: 'ints', label: 'INT', fmt: num }
	];
</script>

<svelte:head><title>Quarterbacks {prefs.season} · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Players</div>
	<h1>Quarterbacks</h1>
	<p class="lede">
		EPA per dropback counts everything a QB does on a pass play, including sacks and scrambles. CPOE
		is completion percentage over what's expected given the throw's depth, location and pressure.
		The interval chart shows the honest answer to “is this QB actually better?”: where two bars
		overlap, the data can't tell those QBs apart yet. The dashed line is the median among QBs shown.
	</p>
</section>

{#if meta}
	<div class="toolbar">
		<Controls seasons={meta.seasons} />
		<label class="field">
			Min dropbacks
			<input
				type="number"
				min="0"
				step="25"
				value={threshold}
				oninput={(e) => (minDb = +(e.currentTarget as HTMLInputElement).value)}
			/>
		</label>
	</div>
	<SampleWarning {status} />
{/if}

{#if qbsRes.error}
	<LoadError message={qbsRes.error} />
{:else if !qbsRes.value}
	<Skeleton height={400} />
{:else if rows.length}
	<div class="grid-2">
		<div class="card">
			<h2>Efficiency vs accuracy</h2>
			<p class="sub">Dot size = dropbacks. Lines are the medians among QBs shown.</p>
			<PlotFigure label="QB EPA per dropback vs CPOE" render={scatter} />
		</div>
		<div class="card">
			<h2>How sure are we?</h2>
			<p class="sub">EPA/dropback with 95% confidence intervals (normal approximation).</p>
			<PlotFigure label="QB EPA per dropback with confidence intervals" render={intervals} />
		</div>
	</div>
	<div class="card">
		<DataTable
			{rows}
			{columns}
			sortKey="epa_db"
			search="display"
			href={(r) => `${base}/player/?id=${r.player_id}`}
			filename="quarterbacks-{prefs.season}"
		/>
	</div>
{:else}
	<p class="muted">No quarterbacks meet the dropback minimum.</p>
{/if}
