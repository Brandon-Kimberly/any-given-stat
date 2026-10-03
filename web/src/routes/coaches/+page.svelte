<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import { setParam } from '$lib/url';
	import { base } from '$app/paths';
	import { page } from '$app/state';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { epa, num, pct, pp } from '$lib/format';
	import { gridX, gridY, Plot, plotStyle, signedTick } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { resource } from '$lib/resource.svelte';
	import { funnelBand } from '$lib/stats';
	import type { CoachCareer, CoachSeason } from '$lib/types';

	const res = resource('coaches');
	const metaRes = resource('meta');
	let view = $state<'career' | 'season'>('career');
	let minGames = $state(34);

	// ?q= pre-filters the table and rings the matching coach in the charts, so other pages can
	// deep-link (/coaches/?q=Dan%20Campbell). The filter box and the URL stay in sync.
	let q = $state(page.url.searchParams.get('q') ?? '');
	afterNavigate(() => (q = page.url.searchParams.get('q') ?? ''));
	$effect(() => setParam('q', q.trim()));
	const matches = (name: string) => {
		const t = q.trim().toLowerCase();
		return !!t && name.toLowerCase().includes(t);
	};

	const careers = $derived(
		(res.value?.careers ?? [])
			.filter((c) => c.games >= minGames)
			.map((c) => ({
				...c,
				record: rec(c),
				ats: `${c.ats_w}–${c.ats_l}${c.ats_push ? `–${c.ats_push}` : ''}`,
				span: c.first === c.last ? `${c.first}` : `${c.first}–${c.last}`
			}))
	);
	const seasonRows = $derived(
		(res.value?.seasons ?? [])
			.filter((c) => c.season === prefs.season)
			.map((c) => ({
				...c,
				record: rec(c),
				ats: `${c.ats_w}–${c.ats_l}${c.ats_push ? `–${c.ats_push}` : ''}`
			}))
	);
	const status = $derived(metaRes.value?.seasons.find((s) => s.season === prefs.season));

	function rec(c: { wins: number; losses: number; ties: number }) {
		return `${c.wins}–${c.losses}${c.ties ? `–${c.ties}` : ''}`;
	}

	type CareerRow = (typeof careers)[number];
	type SeasonRow = (typeof seasonRows)[number];
	const careerCols: Column<CareerRow>[] = [
		{ key: 'coach', label: 'Coach', sticky: true },
		{ key: 'teams', label: 'Teams' },
		{ key: 'span', label: 'Seasons' },
		{ key: 'games', label: 'G', fmt: num, title: 'Games' },
		{ key: 'record', label: 'Record' },
		{ key: 'win_pct', label: 'Win %', fmt: (v) => pct(v), better: 'high' },
		{
			key: 'point_diff',
			label: 'Pt diff',
			fmt: (v) => (v > 0 ? `+${v}` : `${v}`.replace('-', '−')),
			better: 'high'
		},
		{
			key: 'net_epa',
			label: 'Net EPA',
			fmt: epa,
			better: 'high',
			title: 'Net EPA per play over the career'
		},
		{ key: 'ats', label: 'ATS' },
		{
			key: 'ats_pct',
			label: 'ATS %',
			fmt: (v) => pct(v),
			title: 'Against the closing spread, pushes excluded'
		},
		{
			key: 'go_rate_clear',
			label: 'Went for it (clear-go)',
			fmt: (v) => pct(v, 0),
			better: 'high',
			title: 'Share of clear-go 4th downs where they went for it'
		},
		{
			key: 'proe',
			label: 'PROE',
			fmt: (v) => pp(v),
			title: 'Pass rate over expected (style, not quality)'
		}
	];
	const seasonCols: Column<SeasonRow>[] = [
		{ key: 'coach', label: 'Coach', sticky: true },
		{ key: 'team', label: 'Team', team: true },
		{ key: 'record', label: 'Record' },
		{
			key: 'point_diff',
			label: 'Pt diff',
			fmt: (v) => (v > 0 ? `+${v}` : `${v}`.replace('-', '−')),
			better: 'high'
		},
		{ key: 'net_epa', label: 'Net EPA', fmt: epa, better: 'high' },
		{ key: 'ats', label: 'ATS' },
		{ key: 'clear_go', label: 'Clear-go 4ths', fmt: num },
		{
			key: 'go_rate_clear',
			label: 'Went for it (clear-go)',
			fmt: (v) => pct(v, 0),
			better: 'high',
			title: 'Share of clear-go 4th downs where they went for it'
		},
		{ key: 'proe', label: 'PROE', fmt: (v) => pp(v) }
	];

	const lastName = (n: string) => n.split(' ').slice(1).join(' ') || n;

	// Bubble radius in pixels (area ~ games, never under 4 px).
	const radius = (games: number, max: number) => Math.max(4, 11 * Math.sqrt(games / max));

	// Aggressiveness vs results.
	function aggroChart(width: number) {
		const rows = careers.filter((c) => c.go_rate_clear != null && c.clear_go >= 20);
		const maxG = Math.max(1, ...rows.map((r) => r.games));
		const rad = (d: CareerRow) => radius(d.games, maxG);
		// Labels sit just above each bubble: one text mark per pixel radius, biggest careers
		// first, so decluttering still keeps the longest-serving coaches (and a ?q= match first).
		const hit = rows.filter((r) => matches(r.coach));
		const rest = rows.filter((r) => !matches(r.coach));
		const sizes = [...new Set(rest.map((r) => Math.round(rad(r))))].sort((a, b) => b - a);
		const label = (data: CareerRow[], dy: number, strong = false) =>
			Plot.text(data, {
				x: 'go_rate_clear',
				y: 'net_epa',
				text: (d: CareerRow) => lastName(d.coach),
				lineAnchor: 'bottom',
				dy,
				fill: strong ? 'var(--text-primary)' : 'var(--text-secondary)',
				fontWeight: strong ? 700 : 400,
				fontSize: 11,
				className: 'declutter'
			});
		return Plot.plot({
			width,
			height: 380,
			style: plotStyle,
			marginLeft: 48,
			marginRight: 24,
			marginTop: 30,
			x: { label: 'Went for it on clear-go 4th downs →', tickFormat: '.0%', inset: 28 },
			y: { label: '↑ Net EPA per play', tickFormat: signedTick, inset: 12 },
			r: { type: 'identity' }, // radii below are pixels
			marks: [
				gridX(),
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.dot(rows, {
					x: 'go_rate_clear',
					y: 'net_epa',
					r: rad,
					fill: 'var(--series-1)',
					fillOpacity: 0.6,
					stroke: 'var(--surface)'
				}),
				Plot.dot(hit, {
					x: 'go_rate_clear',
					y: 'net_epa',
					r: (d: CareerRow) => rad(d) + 2.5,
					stroke: 'var(--text-primary)',
					strokeWidth: 2
				}),
				...hit.map((d) => label([d], -(rad(d) + 5), true)),
				...sizes.map((px) =>
					label(
						rest.filter((r) => Math.round(rad(r)) === px).sort((a, b) => b.games - a.games),
						-(px + 3)
					)
				),
				Plot.tip(
					rows,
					Plot.pointer({
						x: 'go_rate_clear',
						y: 'net_epa',
						title: (d: CareerRow) =>
							`${d.coach} (${d.teams}, ${d.span})\n${d.record} · went for it ${pct(d.go_rate_clear, 0)} of ${d.clear_go} clear-go 4th downs\nNet EPA ${epa(d.net_epa)}`
					})
				)
			]
		});
	}

	// Against the spread: under pure chance every coach sits inside the funnel 95% of the time.
	const atsRows = $derived(
		careers.filter((c) => c.ats_pct != null).map((c) => ({ ...c, n: c.ats_w + c.ats_l }))
	);
	const outside = $derived(
		atsRows.filter((c) => Math.abs(c.ats_pct! - 0.5) > 1.96 * Math.sqrt(0.25 / c.n))
	);
	function atsChart(width: number) {
		const maxN = Math.max(40, ...atsRows.map((c) => c.n));
		const band = funnelBand(
			0.5,
			Array.from({ length: 60 }, (_, i) => 10 + ((maxN - 10) * i) / 59)
		);
		return Plot.plot({
			width,
			height: 340,
			style: plotStyle,
			marginLeft: 44,
			marginRight: 24,
			x: { label: 'Games against the spread →', inset: 10 },
			y: {
				label: '↑ Cover rate',
				tickFormat: '.0%',
				domain: [
					Math.min(0.3, ...atsRows.map((c) => c.ats_pct! - 0.02)),
					Math.max(0.7, ...atsRows.map((c) => c.ats_pct! + 0.02))
				]
			},
			marks: [
				gridY(),
				Plot.areaY(band, {
					x: 'n',
					y1: 'lo',
					y2: 'hi',
					fill: 'var(--neutral-mark)',
					fillOpacity: 0.15,
					clip: true
				}),
				Plot.ruleY([0.5], { stroke: 'var(--axis)' }),
				Plot.dot(atsRows, {
					x: 'n',
					y: 'ats_pct',
					fill: 'var(--series-1)',
					r: 4,
					fillOpacity: 0.8
				}),
				Plot.dot(
					atsRows.filter((c) => matches(c.coach)),
					{ x: 'n', y: 'ats_pct', r: 7, stroke: 'var(--text-primary)', strokeWidth: 2 }
				),
				Plot.text(
					atsRows.filter((c) => matches(c.coach)),
					{
						x: 'n',
						y: 'ats_pct',
						text: (d: CareerRow) => lastName(d.coach),
						dy: -12,
						fill: 'var(--text-primary)',
						fontWeight: 700,
						className: 'declutter'
					}
				),
				Plot.text(outside, {
					x: 'n',
					y: 'ats_pct',
					text: (d: CareerRow) => lastName(d.coach),
					dy: -10,
					fill: 'var(--text-primary)',
					fontWeight: 600,
					className: 'declutter'
				}),
				Plot.tip(
					atsRows,
					Plot.pointer({
						x: 'n',
						y: 'ats_pct',
						title: (d: (typeof atsRows)[number]) => `${d.coach}: ${d.ats} ATS (${pct(d.ats_pct)})`
					})
				)
			]
		});
	}
</script>

<svelte:head><title>Coaches · Any Given Stat</title></svelte:head>

<div class="page-head">
	<div class="eyebrow">History</div>
	<h1>Head coaches</h1>
	<p class="lede">
		Records, efficiency, how often each coach goes for it when the math says go, and the question
		bettors ask: does anyone beat the spread for real?
	</p>
</div>

{#if res.error}
	<LoadError message={res.error} />
{:else if !res.value || !metaRes.value}
	<Skeleton height={480} />
{:else}
	<div class="toolbar">
		<label class="field">
			Min games
			<select bind:value={minGames}>
				{#each [1, 17, 34, 68] as g (g)}<option value={g}>{g}</option>{/each}
			</select>
		</label>
		<label class="field">
			Find a coach
			<input type="search" placeholder="e.g. Dan Campbell" bind:value={q} />
		</label>
	</div>
	<div class="grid-2">
		<section class="card">
			<h2>Who trusts the math on 4th down?</h2>
			<p class="sub">
				Careers with {minGames}+ games. Dot size = games. Clear-go = spots where going for it beat
				kicking by 0.3+ EPA in the <a href="{base}/fourth/">4th-down model</a>.
			</p>
			<PlotFigure label="Coach 4th-down aggressiveness vs net EPA" render={aggroChart} />
		</section>
		<section class="card">
			<h2>Does anyone beat the spread?</h2>
			<p class="sub">
				Shaded: where 95% of coaches would land if covering were a coin flip.
				{outside.length} of {atsRows.length} fall outside; chance alone would put about {Math.round(
					atsRows.length * 0.05
				)} there.
			</p>
			<PlotFigure
				label="Coach cover rate vs games, with a 95% coin-flip funnel"
				render={atsChart}
			/>
		</section>
	</div>

	<section class="card" id="table">
		<div class="card-head">
			<h2>
				{view === 'career'
					? `Every head coach, ${minGames}+ games`
					: `Head coaches, ${prefs.season}`}
			</h2>
			<div class="toolbar tight">
				<div class="seg" role="group" aria-label="View">
					<button aria-pressed={view === 'career'} onclick={() => (view = 'career')}>Careers</button
					>
					<button aria-pressed={view === 'season'} onclick={() => (view = 'season')}
						>One season</button
					>
				</div>
				{#if view === 'season'}
					<Controls seasons={metaRes.value.seasons} showScope={false} />
				{/if}
			</div>
		</div>
		{#if view === 'career'}
			<DataTable
				rows={careers}
				columns={careerCols}
				sortKey="win_pct"
				search="coach"
				bind:query={q}
				filename="coaches"
			/>
		{:else}
			<SampleWarning {status} />
			<DataTable
				rows={seasonRows}
				columns={seasonCols}
				sortKey="net_epa"
				search="coach"
				bind:query={q}
				filename="coaches-{prefs.season}"
			/>
		{/if}
		<p class="muted small">
			Regular season, 2016 on. ATS uses the closing line. Net EPA is the team's, which reflects the
			roster as much as the coach.
		</p>
	</section>
{/if}

<style>
	.tight {
		margin: 0;
	}
	.small {
		font-size: 0.8rem;
		margin-top: 0.75rem;
	}
</style>
