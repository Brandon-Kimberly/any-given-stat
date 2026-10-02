<script lang="ts">
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { corr, epa, num, pct } from '$lib/format';
	import { gridX, gridY, Plot, plotStyle } from '$lib/plot';
	import { resource } from '$lib/resource.svelte';
	import { ols } from '$lib/stats';
	import { teamColor, teamName } from '$lib/teams.svelte';
	import type { StabilityMetric } from '$lib/types';

	const res = resource('stability');
	const playersRes = resource('players');
	const data = $derived(res.value);
	const names = $derived(new Map((playersRes.value ?? []).map((p) => [p.player_id, p.name])));
	// Units are team codes for team metrics and player ids for player metrics.
	const unitName = (u: string) => names.get(u) ?? teamName(u);

	let selected = $state('off_pass_epa');
	const metrics = $derived(data?.metrics ?? []);
	const current = $derived(metrics.find((m) => m.key === selected));
	const isTeamMetric = $derived(!!current?.group.startsWith('team'));
	const pairs = $derived(data?.yoy_pairs[selected] ?? []);

	function dotplot(width: number) {
		const rows = [...metrics].sort((a, b) => (b.split_half_r ?? -1) - (a.split_half_r ?? -1));
		const long = rows.flatMap((m) => [
			{ label: m.label, r: m.split_half_r, kind: 'Within season (odd vs even weeks)' },
			{ label: m.label, r: m.yoy_r, kind: 'Year over year' }
		]);
		return Plot.plot({
			width,
			height: rows.length * 26 + 70,
			style: plotStyle,
			marginLeft: Math.min(190, width * 0.42),
			x: { domain: [-0.1, 1], label: 'Correlation (0 = pure noise, 1 = perfectly repeatable) →' },
			y: { domain: rows.map((m) => m.label), label: null },
			color: {
				domain: ['Within season (odd vs even weeks)', 'Year over year'],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			marks: [
				gridX(),
				Plot.ruleX([0], { stroke: 'var(--axis)' }),
				Plot.ruleY(rows, {
					y: 'label',
					x1: (m: StabilityMetric) => Math.min(m.split_half_r ?? 0, m.yoy_r ?? 0),
					x2: (m: StabilityMetric) => Math.max(m.split_half_r ?? 0, m.yoy_r ?? 0),
					stroke: 'var(--grid)',
					strokeWidth: 2
				}),
				Plot.dot(
					long.filter((d) => d.r != null),
					{ y: 'label', x: 'r', fill: 'kind', r: 5, stroke: 'var(--surface)', strokeWidth: 2 }
				),
				Plot.tip(
					long.filter((d) => d.r != null),
					Plot.pointer({
						lineWidth: 40,
						y: 'label',
						x: 'r',
						title: (d: { label: string; r: number; kind: string }) =>
							`${d.label}\n${d.kind}: r = ${corr(d.r)}`
					})
				)
			]
		});
	}

	function yoy(width: number) {
		const fit =
			pairs.length > 2
				? ols(
						pairs.map((p) => p.y1),
						pairs.map((p) => p.y2)
					)
				: null;
		const xs = pairs.map((p) => p.y1);
		const x0 = Math.min(...xs);
		const x1 = Math.max(...xs);
		const isRate = !(current?.key.includes('epa') || current?.key.includes('cpoe'));
		return Plot.plot({
			width,
			height: Math.min(440, Math.max(320, width * 0.7)),
			style: plotStyle,
			x: { label: 'Season N →', tickFormat: isRate ? '.0%' : '+.2f' },
			y: { label: '↑ Season N+1', tickFormat: isRate ? '.0%' : '+.2f' },
			marks: [
				gridX(),
				gridY(),
				Plot.dot(pairs, {
					x: 'y1',
					y: 'y2',
					r: 3.5,
					fill: (d: { unit: string }) => (isTeamMetric ? teamColor(d.unit) : 'var(--series-1)'),
					fillOpacity: 0.65
				}),
				fit
					? Plot.line(
							[
								[x0, fit.a + fit.b * x0],
								[x1, fit.a + fit.b * x1]
							],
							{ stroke: 'var(--text-secondary)', strokeWidth: 2 }
						)
					: null,
				Plot.tip(
					pairs,
					Plot.pointer({
						lineWidth: 40,
						x: 'y1',
						y: 'y2',
						title: (d: { unit: string; season: number; y1: number; y2: number }) => {
							const f = (v: number) => (isRate ? pct(v) : epa(v));
							return `${unitName(d.unit)}\n${d.season}: ${f(d.y1)} → ${d.season + 1}: ${f(d.y2)}`;
						}
					})
				)
			]
		});
	}

	const columns: Column<StabilityMetric>[] = [
		{ key: 'label', label: 'Metric', sticky: true },
		{ key: 'group', label: 'Group' },
		{
			key: 'split_half_r',
			label: 'Split-half r',
			fmt: corr,
			better: 'high',
			title: 'Correlation between odd and even weeks of a season'
		},
		{
			key: 'full_season_reliability',
			label: 'Season reliability',
			fmt: corr,
			better: 'high',
			title: 'Spearman-Brown: 2r / (1 + r)'
		},
		{ key: 'yoy_r', label: 'Year-over-year r', fmt: corr, better: 'high' },
		{
			key: 'n_for_half_signal',
			label: 'n for 50% signal',
			fmt: (v) => num(v),
			better: 'low',
			title: 'Sample size at which the stat is half signal, half noise'
		},
		{ key: 'denominator', label: 'Unit' },
		{ key: 'avg_season_n', label: 'Typical season n', fmt: (v) => num(v) },
		{ key: 'yoy_pairs', label: 'Season pairs', fmt: num }
	];
</script>

<svelte:head><title>Signal vs noise · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Learn</div>
	<h1>Signal vs noise</h1>
	<p class="lede">
		The fastest way to sound smart about football is knowing which numbers mean nothing. For each
		stat, this page measures how well it predicts <em>itself</em>, first between odd and even weeks
		of the same season, then from one season to the next. A stat that can't predict itself can't
		predict anything else. Garbage time is excluded, and only complete seasons are used.
	</p>
</section>

{#if res.error}
	<LoadError message={res.error} />
{:else if !data}
	<Skeleton height={500} />
{:else}
	<div class="card">
		<h2>How repeatable is each stat?</h2>
		<p class="sub">Sorted by within-season reliability.</p>
		<PlotFigure label="Split-half and year-over-year correlation by metric" render={dotplot} />
	</div>

	<div class="grid-2">
		<div class="card">
			<h2>Year N vs year N+1</h2>
			<div class="toolbar" style="margin-bottom: 0.5rem">
				<label class="field">
					Metric
					<select bind:value={selected}>
						{#each metrics as m (m.key)}<option value={m.key}>{m.label}</option>{/each}
					</select>
				</label>
			</div>
			<p class="sub">
				{#if current}
					r = {corr(current.yoy_r)} across {current.yoy_pairs}
					{current.group.startsWith('team') ? 'team' : 'player'}-season pairs.
					{#if (current.yoy_r ?? 0) < 0.2}Last year tells you almost nothing about this year.{:else if (current.yoy_r ?? 0) < 0.4}Real
						but heavily regressed: expect most of it to fade back toward average.{:else}A genuine,
						persistent trait.{/if}
				{/if}
			</p>
			<PlotFigure label="Year over year scatter" render={yoy} />
		</div>
		<div class="card">
			<h2>How to read this</h2>
			<p>
				<strong>Split-half r</strong> correlates a stat in odd weeks with the same stat in even weeks.
				Weather, opponents and injuries mix roughly evenly between the two halves, so the correlation
				mostly measures skill, not luck.
			</p>
			<p>
				<strong>Season reliability</strong> scales that up to a full season with the Spearman-Brown formula,
				2r / (1 + r). That's the share of the variation between teams (or players) that is real.
			</p>
			<p>
				<strong>n for 50% signal</strong> is the sample size where a stat is half skill, half noise:
				n<sub>half</sub> × (1 − r) / r, where n<sub>half</sub> is the sample in each half. Below it, regress
				hard toward the league average.
			</p>
			<p>
				<strong>Year-over-year r</strong> also includes real change (roster turnover, coaching), so it's
				a lower bound on how stable the underlying skill is.
			</p>
			<p class="muted">
				The usual pattern: offense is more stable than defense, passing more than rushing, and
				turnovers, red zone TD rate and fumble recoveries are close to random.
			</p>
		</div>
	</div>

	<div class="card">
		<DataTable rows={metrics} {columns} sortKey="split_half_r" />
	</div>
{/if}
