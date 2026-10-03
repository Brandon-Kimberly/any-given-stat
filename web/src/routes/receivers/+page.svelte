<script lang="ts">
	import { base } from '$app/paths';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { epa, num, pct, signed } from '$lib/format';
	import { gridX, gridY, isNarrow, Plot, plotStyle } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { resource } from '$lib/resource.svelte';
	import { teamColor } from '$lib/teams.svelte';
	import type { Receiver } from '$lib/types';

	const metaRes = resource('meta');
	const res = resource('receivers');
	const meta = $derived(metaRes.value);
	const all = $derived(res.value ?? []);
	type Row = Receiver & { display: string };
	const POSITIONS = ['All', 'WR', 'TE', 'RB'] as const;
	let position = $state<(typeof POSITIONS)[number]>('All');

	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));
	let minTargets = $state<number | null>(null);
	const threshold = $derived(
		minTargets ?? Math.max(10, Math.round((status?.reg_games ?? 272) / 16) * 3)
	);
	const rows = $derived<Row[]>(
		all
			.filter(
				(r) =>
					r.season === prefs.season &&
					r.targets >= threshold &&
					(position === 'All' || r.position === position)
			)
			.map((r) => ({ ...r, display: r.full_name ?? r.name }))
	);

	function usage(width: number) {
		const data = rows.filter((r) => r.air_yards_share != null);
		const labelled = [...data].sort((a, b) => (b.wopr ?? 0) - (a.wopr ?? 0));
		const narrow = isNarrow(width);
		return Plot.plot({
			width,
			height: Math.min(520, Math.max(340, width * 0.6)),
			style: plotStyle,
			// Margin + insets keep names on edge dots inside the card and off the tick labels.
			marginRight: narrow ? 24 : 48,
			x: { label: 'Target share →', tickFormat: '.0%', inset: narrow ? 18 : 28 },
			y: { label: '↑ Air yards share', tickFormat: '.0%', insetTop: 16, insetBottom: 8 },
			marks: [
				gridX(),
				gridY(),
				Plot.dot(data, {
					x: 'target_share',
					y: 'air_yards_share',
					r: narrow ? 4 : 4.5,
					fill: (d: Receiver) => teamColor(d.team),
					fillOpacity: 0.85,
					stroke: 'var(--surface)',
					strokeWidth: 1.5
				}),
				Plot.text(labelled, {
					x: 'target_share',
					y: 'air_yards_share',
					text: 'name',
					dy: -10,
					fontSize: 10.5,
					fontWeight: 600,
					fill: 'var(--text-secondary)',
					className: 'declutter'
				}),
				Plot.tip(
					data,
					Plot.pointer({
						lineWidth: 40,
						x: 'target_share',
						y: 'air_yards_share',
						title: (d: Receiver) =>
							`${d.full_name ?? d.name}, ${d.position ?? ''} (${d.team})\nTarget share ${pct(d.target_share)}\nAir yards share ${pct(d.air_yards_share)}\nWOPR ${num(d.wopr, 2)}\nEPA/target ${epa(d.epa_target)}`
					})
				)
			]
		});
	}

	const columns: Column<Row>[] = [
		{ key: 'display', label: 'Player', sticky: true },
		{ key: 'position', label: 'Pos' },
		{ key: 'team', label: 'Team', team: true },
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
		{ key: 'epa_target', label: 'EPA/tgt', fmt: epa, better: 'high', title: 'EPA per target' },
		{ key: 'total_epa', label: 'Total EPA', fmt: (v) => signed(v), better: 'high' },
		{
			key: 'success_rate',
			label: 'Success',
			fmt: pct,
			better: 'high',
			title: 'Share of targets with positive EPA'
		},
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

<svelte:head><title>Receivers {prefs.season} · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Players</div>
	<h1>Receivers</h1>
	<p class="lede">
		Usage reflects role: target share and air yards share (combined as WOPR) describe how an offense
		is built around a player. Per-target efficiency is one of the noisiest stats measured on
		<a href="{base}/stability/">Signal vs noise</a>, so don't over-read a great EPA per target on a
		small sample.
	</p>
</section>

{#if meta}
	<div class="toolbar">
		<Controls seasons={meta.seasons} showScope={false} />
		<div class="seg" role="group" aria-label="Position">
			{#each POSITIONS as p (p)}
				<button aria-pressed={position === p} onclick={() => (position = p)}>{p}</button>
			{/each}
		</div>
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

{#if res.error}
	<LoadError message={res.error} />
{:else if !res.value}
	<Skeleton height={400} />
{:else if rows.length}
	<div class="card">
		<h2>Who gets the ball, and how far downfield</h2>
		<p class="sub">
			Dot color = team. Labels favor the highest WOPR; overlapping ones are hidden (hover any dot).
			Top right is a true number one: lots of targets, and the valuable deep ones.
		</p>
		<PlotFigure label="Target share vs air yards share" render={usage} />
	</div>
	<div class="card">
		<DataTable
			{rows}
			{columns}
			sortKey="wopr"
			search="display"
			href={(r) => `${base}/player/?id=${r.player_id}`}
			filename="receivers-{prefs.season}"
		/>
	</div>
{:else}
	<p class="muted">No receivers match these filters.</p>
{/if}
