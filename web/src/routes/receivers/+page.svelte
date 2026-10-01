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
	import type { Meta, Receiver } from '$lib/types';

	let meta = $state<Meta>();
	let all = $state<Receiver[]>([]);
	load('meta').then((m) => (meta = m));
	load('receivers').then((r) => (all = r));

	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));
	let minTargets = $state<number | null>(null);
	const threshold = $derived(
		minTargets ?? Math.max(10, Math.round((status?.reg_games ?? 272) / 16) * 3)
	);
	const rows = $derived(all.filter((r) => r.season === prefs.season && r.targets >= threshold));

	function usage(width: number) {
		const data = rows.filter((r) => r.air_yards_share != null);
		const labelled = [...data].sort((a, b) => (b.wopr ?? 0) - (a.wopr ?? 0)).slice(0, 12);
		return Plot.plot({
			width,
			height: Math.min(520, Math.max(340, width * 0.6)),
			style: plotStyle,
			x: { label: 'Target share →', tickFormat: '.0%' },
			y: { label: '↑ Air yards share', tickFormat: '.0%' },
			marks: [
				gridX(),
				gridY(),
				Plot.dot(data, {
					x: 'target_share',
					y: 'air_yards_share',
					r: 4,
					fill: 'var(--series-1)',
					fillOpacity: 0.6,
					stroke: 'var(--surface)',
					strokeWidth: 1.5
				}),
				Plot.text(labelled, {
					x: 'target_share',
					y: 'air_yards_share',
					text: 'name',
					dy: -10,
					fontSize: 10.5,
					fill: 'var(--text-secondary)'
				}),
				Plot.tip(
					data,
					Plot.pointer({
						lineWidth: 40,
						x: 'target_share',
						y: 'air_yards_share',
						title: (d: Receiver) =>
							`${d.name} (${d.team})\nTarget share ${pct(d.target_share)}\nAir yards share ${pct(d.air_yards_share)}\nWOPR ${num(d.wopr, 2)}\nEPA/target ${epa(d.epa_target)}`
					})
				)
			]
		});
	}

	const columns: Column<Receiver>[] = [
		{ key: 'name', label: 'Player', sticky: true },
		{ key: 'team', label: 'Team' },
		{ key: 'targets', label: 'Tgt', fmt: num },
		{ key: 'receptions', label: 'Rec', fmt: num },
		{ key: 'yards', label: 'Yds', fmt: num },
		{ key: 'tds', label: 'TD', fmt: num },
		{ key: 'target_share', label: 'Tgt share', fmt: pct, better: 'high' },
		{ key: 'air_yards_share', label: 'Air share', fmt: pct, better: 'high' },
		{
			key: 'wopr',
			label: 'WOPR',
			fmt: (v) => num(v, 2),
			better: 'high',
			title: 'Weighted opportunity: 1.5 × target share + 0.7 × air yards share'
		},
		{ key: 'adot', label: 'aDOT', fmt: (v) => num(v, 1) },
		{ key: 'epa_target', label: 'EPA/tgt', fmt: epa, better: 'high' },
		{ key: 'total_epa', label: 'Total EPA', fmt: (v) => signed(v), better: 'high' },
		{ key: 'success_rate', label: 'Success', fmt: pct, better: 'high' },
		{
			key: 'catch_rate_oe',
			label: 'Catch% OE',
			fmt: (v) => signed(v == null ? null : v * 100),
			better: 'high',
			title: 'Catch rate over expected (nflfastR cp), percentage points'
		},
		{
			key: 'yac_oe',
			label: 'YAC OE',
			fmt: (v) => signed(v),
			better: 'high',
			title: 'Yards after catch over expected (xYAC), per reception'
		}
	];
</script>

<svelte:head><title>Receivers · Any Given Stat</title></svelte:head>

<section>
	<h1>Receivers</h1>
	<p class="lede">
		Usage is a role: target share and air yards share (combined as WOPR) describe how an offense is
		built around a player. Per-target efficiency is one of the noisiest stats measured on
		<a href="{base}/stability/">Signal vs noise</a>, so don't over-read a great EPA per target on a
		small sample.
	</p>
</section>

{#if meta}
	<div class="toolbar">
		<Controls seasons={meta.seasons} showScope={false} />
		<label class="field">
			Min targets
			<input
				type="number"
				min="0"
				step="5"
				value={threshold}
				oninput={(e) => (minTargets = +(e.currentTarget as HTMLInputElement).value)}
			/>
		</label>
	</div>
	<SampleWarning {status} />
{/if}

{#if rows.length}
	<div class="card">
		<h2>Who gets the ball, and how far downfield</h2>
		<p class="sub">Labels mark the 12 highest WOPR.</p>
		<PlotFigure label="Target share vs air yards share" render={usage} />
	</div>
	<div class="card">
		<DataTable {rows} {columns} sortKey="wopr" search="name" />
	</div>
{/if}
