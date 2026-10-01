<script lang="ts">
	import { base } from '$app/paths';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import { load } from '$lib/data';
	import { epa, num, pct, signed } from '$lib/format';
	import { gridX, gridY, Plot, plotStyle } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { median } from '$lib/stats';
	import type { Meta, Rusher } from '$lib/types';

	let meta = $state<Meta>();
	let all = $state<Rusher[]>([]);
	load('meta').then((m) => (meta = m));
	load('rushers').then((r) => (all = r));

	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));
	let minCarries = $state<number | null>(null);
	const threshold = $derived(
		minCarries ?? Math.max(20, Math.round((status?.reg_games ?? 272) / 16) * 6)
	);
	const rows = $derived(all.filter((r) => r.season === prefs.season && r.carries >= threshold));

	function scatter(width: number) {
		return Plot.plot({
			width,
			height: Math.min(520, Math.max(340, width * 0.6)),
			style: plotStyle,
			x: { label: 'Success rate →', tickFormat: '.0%' },
			y: { label: '↑ EPA per carry', tickFormat: '+.2f' },
			marks: [
				gridX(),
				gridY(),
				Plot.ruleX([median(rows.map((r) => r.success_rate))], {
					stroke: 'var(--axis)',
					strokeWidth: 1.5
				}),
				Plot.ruleY([0], { stroke: 'var(--axis)', strokeWidth: 1.5 }),
				Plot.dot(rows, {
					x: 'success_rate',
					y: 'epa_rush',
					r: (d: Rusher) => Math.sqrt(d.carries) / 2.6,
					fill: 'var(--series-1)',
					fillOpacity: 0.6,
					stroke: 'var(--surface)',
					strokeWidth: 1.5
				}),
				Plot.text(rows, {
					x: 'success_rate',
					y: 'epa_rush',
					text: 'name',
					dy: -11,
					fontSize: 10.5,
					fill: 'var(--text-secondary)'
				}),
				Plot.tip(
					rows,
					Plot.pointer({
						x: 'success_rate',
						y: 'epa_rush',
						title: (d: Rusher) =>
							`${d.name} (${d.team})\n${num(d.carries)} carries, ${num(d.yards)} yds\nEPA/carry ${epa(d.epa_rush)}\nSuccess ${pct(d.success_rate)}\nExplosive ${pct(d.explosive_rate)}  Stuffed ${pct(d.stuff_rate)}`
					})
				)
			]
		});
	}

	const columns: Column<Rusher>[] = [
		{ key: 'name', label: 'Player', sticky: true },
		{ key: 'team', label: 'Team' },
		{ key: 'carries', label: 'Car', fmt: num },
		{ key: 'yards', label: 'Yds', fmt: num },
		{ key: 'ypc', label: 'YPC', fmt: (v) => num(v, 1), better: 'high' },
		{ key: 'tds', label: 'TD', fmt: num },
		{ key: 'epa_rush', label: 'EPA/car', fmt: epa, better: 'high' },
		{ key: 'total_epa', label: 'Total EPA', fmt: (v) => signed(v), better: 'high' },
		{ key: 'success_rate', label: 'Success', fmt: pct, better: 'high' },
		{ key: 'explosive_rate', label: '10+ yd%', fmt: pct, better: 'high' },
		{
			key: 'stuff_rate',
			label: 'Stuff%',
			fmt: pct,
			better: 'low',
			title: 'Carries for zero or negative yards'
		}
	];
</script>

<svelte:head><title>Rushers · Any Given Stat</title></svelte:head>

<section>
	<h1>Rushers</h1>
	<p class="lede">
		Designed runs only (scrambles count as dropbacks). Most runs lose expected points, so a rusher
		above zero EPA per carry is doing something real. Rusher efficiency is one of the noisiest stats
		in football, though; check <a href="{base}/stability/">Signal vs noise</a> before you trust it.
	</p>
</section>

{#if meta}
	<div class="toolbar">
		<Controls seasons={meta.seasons} showScope={false} />
		<label class="field">
			Min carries
			<input
				type="number"
				min="0"
				step="10"
				value={threshold}
				oninput={(e) => (minCarries = +(e.currentTarget as HTMLInputElement).value)}
			/>
		</label>
	</div>
	<SampleWarning {status} />
{/if}

{#if rows.length}
	<div class="card">
		<h2>Efficiency vs consistency</h2>
		<p class="sub">Dot size = carries. Success = the run gained expected points.</p>
		<PlotFigure label="Rusher success rate vs EPA per carry" render={scatter} />
	</div>
	<div class="card">
		<DataTable {rows} {columns} sortKey="epa_rush" search="name" />
	</div>
{/if}
