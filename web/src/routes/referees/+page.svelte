<script lang="ts">
	// Referee crews: penalty volume and home/away lean, with funnels showing how much of the
	// spread between crews is just sample size.
	import { afterNavigate } from '$app/navigation';
	import { setParam } from '$lib/url';
	import { page } from '$app/state';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { num, pct } from '$lib/format';
	import { gridY, Plot, plotStyle } from '$lib/plot';
	import { resource } from '$lib/resource.svelte';
	import { funnelBand } from '$lib/stats';
	import type { RefCareer } from '$lib/types';

	const res = resource('referees');
	let minGames = $state(48);

	// ?q= pre-filters the table and rings the matching referee in the charts, so other pages
	// can deep-link (/referees/?q=Hochuli). The filter boxes and the URL stay in sync.
	let q = $state(page.url.searchParams.get('q') ?? '');
	afterNavigate(() => (q = page.url.searchParams.get('q') ?? ''));
	$effect(() => setParam('q', q.trim()));
	const matches = (name: string) => {
		const t = q.trim().toLowerCase();
		return !!t && name.toLowerCase().includes(t);
	};

	const careers = $derived(
		(res.value?.careers ?? [])
			.filter((r) => r.games >= minGames)
			.map((r) => ({
				...r,
				span: r.first === r.last ? `${r.first}` : `${r.first}–${r.last}`,
				flags: Math.round(r.penalties_pg * r.games)
			}))
	);
	type Row = (typeof careers)[number];

	// League rates, weighted by volume, from every crew (not just the filtered ones).
	const all = $derived(res.value?.careers ?? []);
	const leaguePenShare = $derived.by(() => {
		const n = all.reduce((a, r) => a + r.penalties_pg * r.games, 0);
		return all.reduce((a, r) => a + r.home_penalty_share * r.penalties_pg * r.games, 0) / (n || 1);
	});
	const leagueHomeWin = $derived.by(() => {
		const n = all.reduce((a, r) => a + r.games, 0);
		return all.reduce((a, r) => a + r.home_win_pct * r.games, 0) / (n || 1);
	});
	const outsidePen = $derived(
		careers.filter(
			(r) =>
				Math.abs(r.home_penalty_share - leaguePenShare) >
				1.96 * Math.sqrt((leaguePenShare * (1 - leaguePenShare)) / r.flags)
		)
	);
	const outsideWin = $derived(
		careers.filter(
			(r) =>
				Math.abs(r.home_win_pct - leagueHomeWin) >
				1.96 * Math.sqrt((leagueHomeWin * (1 - leagueHomeWin)) / r.games)
		)
	);

	const lastName = (n: string) => n.split(' ').slice(1).join(' ') || n;

	function funnel(
		width: number,
		opts: {
			x: (r: Row) => number;
			y: (r: Row) => number;
			p: number;
			xLabel: string;
			yLabel: string;
			out: Row[];
			tip: (r: Row) => string;
		}
	) {
		const xs = careers.map(opts.x);
		const lo = Math.max(5, Math.min(...xs) * 0.9);
		const hi = Math.max(...xs) * 1.05;
		const band = funnelBand(
			opts.p,
			Array.from({ length: 60 }, (_, i) => lo + ((hi - lo) * i) / 59)
		);
		const ys = careers.map(opts.y);
		const pad = 0.02;
		const hit = careers.filter((r) => matches(r.referee));
		return Plot.plot({
			width,
			height: 340,
			style: plotStyle,
			marginLeft: 44,
			marginRight: 28,
			marginTop: 28,
			x: { label: opts.xLabel, domain: [lo, hi], inset: 10 },
			y: {
				label: opts.yLabel,
				tickFormat: '.0%',
				domain: [
					Math.min(...ys, ...band.map((b) => b.lo)) - pad,
					Math.max(...ys, ...band.map((b) => b.hi)) + pad
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
				Plot.ruleY([opts.p], { stroke: 'var(--axis)', strokeDasharray: '4,3' }),
				Plot.dot(careers, {
					x: opts.x,
					y: opts.y,
					r: 4,
					fill: 'var(--series-1)',
					fillOpacity: 0.8
				}),
				Plot.dot(hit, {
					x: opts.x,
					y: opts.y,
					r: 7,
					stroke: 'var(--text-primary)',
					strokeWidth: 2
				}),
				Plot.text(hit, {
					x: opts.x,
					y: opts.y,
					text: (d: Row) => lastName(d.referee),
					dy: -13,
					fill: 'var(--text-primary)',
					fontWeight: 700,
					className: 'declutter'
				}),
				Plot.text(opts.out, {
					x: opts.x,
					y: opts.y,
					text: (d: Row) => lastName(d.referee),
					dy: -11,
					fill: 'var(--text-primary)',
					fontWeight: 600,
					className: 'declutter'
				}),
				Plot.tip(careers, Plot.pointer({ x: opts.x, y: opts.y, title: opts.tip }))
			]
		});
	}
	const penChart = (width: number) =>
		funnel(width, {
			x: (r) => r.flags,
			y: (r) => r.home_penalty_share,
			p: leaguePenShare,
			xLabel: 'Penalties called (career) →',
			yLabel: '↑ Share on the home team',
			out: outsidePen,
			tip: (r) =>
				`${r.referee} (${r.span})\n${pct(r.home_penalty_share)} of ${num(r.flags)} penalties on the home team`
		});
	const winChart = (width: number) =>
		funnel(width, {
			x: (r) => r.games,
			y: (r) => r.home_win_pct,
			p: leagueHomeWin,
			xLabel: 'Games worked →',
			yLabel: '↑ Home team won',
			out: outsideWin,
			tip: (r) =>
				`${r.referee} (${r.span})\nHome teams won ${pct(r.home_win_pct)} of ${r.games} games`
		});

	const cols: Column<Row>[] = [
		{ key: 'referee', label: 'Referee', sticky: true },
		{ key: 'span', label: 'Seasons' },
		{ key: 'games', label: 'Games', fmt: num },
		{
			key: 'penalties_pg',
			label: 'Flags/game',
			fmt: (v) => num(v, 1),
			title: 'Flagged plays per game, both teams (declined included)'
		},
		{
			key: 'penalty_yards_pg',
			label: 'Yards/game',
			fmt: (v) => num(v, 1),
			title: 'Penalty yards per game, both teams'
		},
		{
			key: 'home_penalty_share',
			label: 'On home team',
			fmt: (v) => pct(v),
			title: 'Share of flags called on the home team'
		},
		{ key: 'home_win_pct', label: 'Home win %', fmt: (v) => pct(v) },
		{ key: 'points_pg', label: 'Points/game', fmt: (v) => num(v, 1), title: 'Both teams combined' }
	];
	const expected = (n: number) => Math.round(n * 0.05);
</script>

<svelte:head><title>Referees · Any Given Stat</title></svelte:head>

<div class="page-head">
	<div class="eyebrow">History</div>
	<h1>Referees</h1>
	<p class="lede">
		Which crews throw the most flags, and is any of them really tilting games toward the home team?
		The funnels show how far from average a crew can drift by luck alone.
	</p>
</div>

{#if res.error}
	<LoadError message={res.error} />
{:else if !res.value}
	<Skeleton height={480} />
{:else}
	<div class="toolbar">
		<label class="field">
			Min games
			<select bind:value={minGames}>
				{#each [1, 16, 48, 96] as g (g)}<option value={g}>{g}</option>{/each}
			</select>
		</label>
		<label class="field">
			Find a referee
			<input type="search" placeholder="e.g. Hochuli" bind:value={q} />
		</label>
	</div>
	<div class="grid-2">
		<section class="card">
			<h2>Who gets flagged: home or away?</h2>
			<p class="sub">
				League: {pct(leaguePenShare)} of penalties fall on the home team. Shaded: the 95% range for a
				crew calling it straight. {outsidePen.length} of {careers.length} crews fall outside (chance:
				about {expected(careers.length)}).
			</p>
			<PlotFigure label="Home penalty share by referee, with a 95% funnel" render={penChart} />
		</section>
		<section class="card">
			<h2>Do home teams win more with certain crews?</h2>
			<p class="sub">
				League home win rate {pct(leagueHomeWin)}. {outsideWin.length} of {careers.length} crews fall
				outside the 95% funnel (chance: about {expected(careers.length)}). Crews don't pick their
				games, so even an outlier here says little about the referee.
			</p>
			<PlotFigure label="Home win rate by referee, with a 95% funnel" render={winChart} />
		</section>
	</div>

	<section class="card" id="table">
		<h2>Every crew chief, {minGames}+ games</h2>
		<DataTable
			rows={careers}
			columns={cols}
			sortKey="penalties_pg"
			search="referee"
			bind:query={q}
			filename="referees"
		/>
		<p class="muted small">
			Regular-season games the referee led since 2016. Penalties are plays flagged in play-by-play,
			including declined and offsetting ones.
		</p>
	</section>
{/if}

<style>
	.small {
		font-size: 0.8rem;
		margin-top: 0.75rem;
	}
</style>
