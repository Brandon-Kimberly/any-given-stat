<script lang="ts">
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import { load } from '$lib/data';
	import { epa, num, pct, signed } from '$lib/format';
	import { gridX, gridY, Plot, plotStyle } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { median } from '$lib/stats';
	import type { Meta, QB } from '$lib/types';

	let meta = $state<Meta>();
	let qbs = $state<QB[]>([]);
	load('meta').then((m) => (meta = m));
	load('qbs').then((q) => (qbs = q));

	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));
	// Default bar: 10 dropbacks per week played (170 for a full season), floor of 50.
	let minDb = $state<number | null>(null);
	const threshold = $derived(
		minDb ?? Math.max(50, Math.round(((status?.reg_games ?? 272) / 16) * 10))
	);
	const rows = $derived(
		qbs.filter(
			(q) => q.season === prefs.season && q.scope === prefs.scope && q.dropbacks >= threshold
		)
	);

	function scatter(width: number) {
		const data = rows.filter((r) => r.cpoe != null);
		return Plot.plot({
			width,
			height: Math.min(560, Math.max(360, width * 0.6)),
			style: plotStyle,
			marginRight: 30,
			x: { label: 'CPOE (completion % over expected) →', tickFormat: '+.0f' },
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
					r: (d: QB) => Math.sqrt(d.dropbacks) / 3.2,
					fill: 'var(--series-1)',
					fillOpacity: 0.75,
					stroke: 'var(--surface)',
					strokeWidth: 1.5
				}),
				Plot.text(data, {
					x: 'cpoe',
					y: 'epa_db',
					text: 'name',
					dy: -11,
					fontSize: 10.5,
					fill: 'var(--text-secondary)'
				}),
				Plot.tip(
					data,
					Plot.pointer({
						lineWidth: 40,
						x: 'cpoe',
						y: 'epa_db',
						title: (d: QB) =>
							`${d.name} (${d.teams})\nEPA/db ${epa(d.epa_db)}  [${epa(d.epa_db_lo)}, ${epa(d.epa_db_hi)}]\nCPOE ${signed(d.cpoe)}\n${num(d.dropbacks)} dropbacks`
					})
				)
			]
		});
	}

	function intervals(width: number) {
		const data = [...rows].sort((a, b) => b.epa_db - a.epa_db);
		return Plot.plot({
			width,
			height: Math.max(240, data.length * 18 + 50),
			style: plotStyle,
			marginLeft: 120,
			x: {
				label: 'EPA per dropback, 95% interval',
				tickFormat: '+.2f',
				ticks: Math.max(3, Math.floor(width / 110))
			},
			y: { domain: data.map((d) => `${d.name} ${d.team}`), label: null },
			marks: [
				gridX(),
				Plot.ruleX([0], { stroke: 'var(--axis)' }),
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
					fill: 'var(--series-1)',
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
							`${d.name}: ${epa(d.epa_db)} per dropback\n95% CI ${epa(d.epa_db_lo)} to ${epa(d.epa_db_hi)}\n${num(d.dropbacks)} dropbacks`
					})
				)
			]
		});
	}

	const columns: Column<QB>[] = [
		{ key: 'name', label: 'QB', sticky: true },
		{ key: 'teams', label: 'Team' },
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

<svelte:head><title>Quarterbacks · Any Given Stat</title></svelte:head>

<section>
	<h1>Quarterbacks</h1>
	<p class="lede">
		EPA per dropback counts everything a QB does on a pass play, including sacks and scrambles. CPOE
		is completion percentage over what's expected given the throw's depth, location and pressure.
		The interval chart shows the honest answer to “is he actually better?”: where two bars overlap,
		the data can't tell those QBs apart yet.
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

{#if rows.length}
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
		<DataTable {rows} {columns} sortKey="epa_db" search="name" />
	</div>
{:else if qbs.length}
	<p class="muted">No quarterbacks meet the dropback minimum.</p>
{/if}
