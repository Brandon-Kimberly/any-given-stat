<script lang="ts">
	// Tale of the tape: two teams or two players side by side, each from any season, on league
	// percentiles within their own season (so a 2017 and a 2025 season compare fairly).
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { favorite } from '$lib/favorite.svelte';
	import { epa, num, pct, pp, signed } from '$lib/format';
	import { gridY, isNarrow, Plot, plotStyle, signedTick, thinTicks } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { resource, seasonResource } from '$lib/resource.svelte';
	import { normCdf, percentileOf } from '$lib/stats';
	import { teamName } from '$lib/teams.svelte';
	import type { QB, Rating, Receiver, Rusher, TeamSeason } from '$lib/types';

	type Mode = 'teams' | 'qbs' | 'receivers' | 'rushers';
	const MODES: { key: Mode; label: string }[] = [
		{ key: 'teams', label: 'Teams' },
		{ key: 'qbs', label: 'Quarterbacks' },
		{ key: 'receivers', label: 'Receivers' },
		{ key: 'rushers', label: 'Rushers' }
	];

	interface Metric {
		key: string;
		label: string;
		fmt: (v: number) => string;
		/** null: descriptive (no better end); bars show raw percentile in a neutral color. */
		better: 'high' | 'low' | null;
		title?: string;
	}
	type Row = Record<string, any>;

	const teamMetrics: Metric[] = [
		{ key: 'net_epa_play', label: 'Net EPA/play', fmt: epa, better: 'high' },
		{ key: 'adj_net_epa', label: 'Opp-adjusted net EPA', fmt: epa, better: 'high' },
		{ key: 'off_epa_play', label: 'Offense EPA/play', fmt: epa, better: 'high' },
		{ key: 'off_pass_epa', label: 'Pass offense EPA', fmt: epa, better: 'high' },
		{ key: 'off_rush_epa', label: 'Rush offense EPA', fmt: epa, better: 'high' },
		{ key: 'off_success_rate', label: 'Offense success rate', fmt: pct, better: 'high' },
		{ key: 'off_explosive_rate', label: 'Explosive play rate', fmt: pct, better: 'high' },
		{
			key: 'off_points_per_drive',
			label: 'Points per drive',
			fmt: (v) => num(v, 2),
			better: 'high'
		},
		{ key: 'off_turnover_rate', label: 'Giveaway rate', fmt: (v) => pct(v, 2), better: 'low' },
		{ key: 'off_sack_rate', label: 'Sack rate (taken)', fmt: pct, better: 'low' },
		{ key: 'off_proe', label: 'Pass rate over expected', fmt: (v) => pp(v), better: null },
		{ key: 'def_epa_play', label: 'Defense EPA/play', fmt: epa, better: 'low' },
		{ key: 'def_pass_epa', label: 'Pass defense EPA', fmt: epa, better: 'low' },
		{ key: 'def_rush_epa', label: 'Run defense EPA', fmt: epa, better: 'low' },
		{ key: 'def_success_rate', label: 'Defense success rate', fmt: pct, better: 'low' },
		{ key: 'def_explosive_rate', label: 'Explosives allowed', fmt: pct, better: 'low' },
		{ key: 'def_turnover_rate', label: 'Takeaway rate', fmt: (v) => pct(v, 2), better: 'high' },
		{ key: 'def_sack_rate', label: 'Sack rate (pass rush)', fmt: pct, better: 'high' },
		{
			key: 'def_points_per_drive',
			label: 'Points per drive allowed',
			fmt: (v) => num(v, 2),
			better: 'low'
		}
	];
	const qbMetrics: Metric[] = [
		{ key: 'epa_db', label: 'EPA per dropback', fmt: epa, better: 'high' },
		{ key: 'success_rate', label: 'Success rate', fmt: pct, better: 'high' },
		{
			key: 'cpoe',
			label: 'CPOE',
			fmt: (v) => signed(v),
			better: 'high',
			title: 'Completion % over expected'
		},
		{ key: 'adot', label: 'Avg depth of target', fmt: (v) => num(v, 1), better: null },
		{ key: 'sack_rate', label: 'Sack rate', fmt: pct, better: 'low' },
		{ key: 'int_rate', label: 'INT rate', fmt: (v) => pct(v, 2), better: 'low' },
		{ key: 'scramble_rate', label: 'Scramble rate', fmt: pct, better: null },
		{
			key: 'designed_run_epa',
			label: 'Designed run EPA (total)',
			fmt: (v) => signed(v),
			better: 'high'
		},
		{ key: 'total_epa', label: 'Total EPA', fmt: (v) => num(v, 1), better: 'high' },
		{ key: 'dropbacks', label: 'Dropbacks', fmt: (v) => num(v), better: null },
		{ key: 'pass_yards', label: 'Pass yards', fmt: (v) => num(v), better: 'high' },
		{ key: 'pass_tds', label: 'Pass TDs', fmt: (v) => num(v), better: 'high' }
	];
	const recMetrics: Metric[] = [
		{ key: 'target_share', label: 'Target share', fmt: pct, better: 'high' },
		{ key: 'air_yards_share', label: 'Air yards share', fmt: pct, better: 'high' },
		{
			key: 'wopr',
			label: 'WOPR',
			fmt: (v) => num(v, 2),
			better: 'high',
			title: 'Weighted opportunity rating'
		},
		{ key: 'adot', label: 'Avg depth of target', fmt: (v) => num(v, 1), better: null },
		{ key: 'epa_target', label: 'EPA per target', fmt: epa, better: 'high' },
		{ key: 'success_rate', label: 'Success rate', fmt: pct, better: 'high' },
		{ key: 'catch_rate_oe', label: 'Catch rate over expected', fmt: (v) => pp(v), better: 'high' },
		{ key: 'yac_oe', label: 'YAC over expected', fmt: (v) => signed(v, 2), better: 'high' },
		{ key: 'total_epa', label: 'Total EPA', fmt: (v) => num(v, 1), better: 'high' },
		{ key: 'targets', label: 'Targets', fmt: (v) => num(v), better: null },
		{ key: 'yards', label: 'Receiving yards', fmt: (v) => num(v), better: 'high' },
		{ key: 'tds', label: 'Receiving TDs', fmt: (v) => num(v), better: 'high' }
	];
	const rushMetrics: Metric[] = [
		{ key: 'epa_rush', label: 'EPA per carry', fmt: epa, better: 'high' },
		{ key: 'success_rate', label: 'Success rate', fmt: pct, better: 'high' },
		{ key: 'explosive_rate', label: 'Explosive run rate', fmt: pct, better: 'high' },
		{ key: 'stuff_rate', label: 'Stuffed at/behind line', fmt: pct, better: 'low' },
		{ key: 'ypc', label: 'Yards per carry', fmt: (v) => num(v, 2), better: 'high' },
		{ key: 'total_epa', label: 'Total EPA', fmt: (v) => num(v, 1), better: 'high' },
		{ key: 'carries', label: 'Carries', fmt: (v) => num(v), better: null },
		{ key: 'yards', label: 'Rush yards', fmt: (v) => num(v), better: 'high' },
		{ key: 'tds', label: 'Rush TDs', fmt: (v) => num(v), better: 'high' }
	];

	const metaRes = resource('meta');
	const teamsRes = resource('teams');
	const predsRes = resource('predictions');
	// Player datasets load only when their mode is opened.
	let qbs = $state.raw<QB[] | null>(null);
	let receivers = $state.raw<Receiver[] | null>(null);
	let rushers = $state.raw<Rusher[] | null>(null);
	let loadError = $state<string | null>(null);

	const params = $derived(page.url.searchParams);
	const mode = $derived<Mode>(
		(MODES.find((m) => m.key === params.get('mode'))?.key ?? 'teams') as Mode
	);
	const seasons = $derived((metaRes.value?.seasons ?? []).map((s) => s.season).reverse());
	const latest = $derived(seasons[0] ?? prefs.season ?? 0);

	$effect(() => {
		const want = mode;
		import('$lib/data').then(({ load }) => {
			const fail = (e: unknown) => (loadError = e instanceof Error ? e.message : String(e));
			if (want === 'qbs' && !qbs) load('qbs').then((v) => (qbs = v), fail);
			if (want === 'receivers' && !receivers) load('receivers').then((v) => (receivers = v), fail);
			if (want === 'rushers' && !rushers) load('rushers').then((v) => (rushers = v), fail);
		});
	});

	/** All rows for the mode (garbage-time scope applied where the data has it). */
	const pool = $derived.by<Row[] | null>(() => {
		if (mode === 'teams') return teamsRes.value?.filter((t) => t.scope === prefs.scope) ?? null;
		if (mode === 'qbs') return qbs?.filter((q) => q.scope === prefs.scope) ?? null;
		if (mode === 'receivers') return receivers;
		return rushers;
	});
	const metrics = $derived(
		mode === 'teams'
			? teamMetrics
			: mode === 'qbs'
				? qbMetrics
				: mode === 'receivers'
					? recMetrics
					: rushMetrics
	);
	const volKey = $derived(
		mode === 'qbs'
			? 'dropbacks'
			: mode === 'receivers'
				? 'targets'
				: mode === 'rushers'
					? 'carries'
					: null
	);
	const idKey = $derived(mode === 'teams' ? 'team' : 'player_id');

	/** Rows of one season, and the qualified peers percentiles are measured against. */
	function seasonPool(season: number): { rows: Row[]; peers: Row[] } {
		const rows = (pool ?? []).filter((r) => r.season === season);
		if (!volKey) return { rows, peers: rows };
		const lead = Math.max(0, ...rows.map((r) => r[volKey]));
		return {
			rows: [...rows].sort((a, b) => b[volKey] - a[volKey]),
			peers: rows.filter((r) => r[volKey] >= lead * 0.4)
		};
	}

	function parseSide(v: string | null): { id: string; season: number } | null {
		if (!v) return null;
		const i = v.lastIndexOf('-');
		const season = Number(v.slice(i + 1));
		return i > 0 && Number.isInteger(season) ? { id: v.slice(0, i), season } : null;
	}

	/** A side from the URL, else a sensible default (your team / the top two by volume or rating). */
	function side(which: 'a' | 'b') {
		const fromUrl = parseSide(params.get(which));
		if (fromUrl) return fromUrl;
		const season = prefs.season ?? latest;
		const { rows } = seasonPool(season);
		let ordered = rows;
		if (mode === 'teams')
			ordered = [...rows].sort((x, y) => (y.net_epa_play ?? 0) - (x.net_epa_play ?? 0));
		const fav = mode === 'teams' && favorite.team ? favorite.team : null;
		const first = fav ?? ordered[0]?.[idKey];
		const second = ordered.find((r) => r[idKey] !== first)?.[idKey];
		return { id: (which === 'a' ? first : second) ?? '', season };
	}
	const A = $derived(side('a'));
	const B = $derived(side('b'));

	function setSide(which: 'a' | 'b', id: string, season: number) {
		const url = new URL(page.url);
		url.searchParams.set('mode', mode);
		url.searchParams.set('a', which === 'a' ? `${id}-${season}` : `${A.id}-${A.season}`);
		url.searchParams.set('b', which === 'b' ? `${id}-${season}` : `${B.id}-${B.season}`);
		goto(url, { keepFocus: true, noScroll: true, replaceState: true });
	}
	function setSeason(which: 'a' | 'b', season: number) {
		const cur = which === 'a' ? A : B;
		const { rows } = seasonPool(season);
		// Keep the same team/player if they played that season, else take the top one.
		const keep = rows.some((r) => r[idKey] === cur.id);
		setSide(which, keep ? cur.id : (rows[0]?.[idKey] ?? ''), season);
	}
	function setMode(m: Mode) {
		const url = new URL(page.url);
		url.searchParams.set('mode', m);
		url.searchParams.delete('a');
		url.searchParams.delete('b');
		goto(url, { keepFocus: true, noScroll: true, replaceState: true });
	}
	function swap() {
		const url = new URL(page.url);
		url.searchParams.set('mode', mode);
		url.searchParams.set('a', `${B.id}-${B.season}`);
		url.searchParams.set('b', `${A.id}-${A.season}`);
		goto(url, { keepFocus: true, noScroll: true, replaceState: true });
	}

	function resolve(s: { id: string; season: number }) {
		const { rows, peers } = seasonPool(s.season);
		const row = rows.find((r) => r[idKey] === s.id) ?? null;
		return { ...s, row, rows, peers };
	}
	const a = $derived(resolve(A));
	const b = $derived(resolve(B));

	// Ratings for each side's season (often the same file, cached once).
	const ratingsA = seasonResource<Rating>('ratings', () => (mode === 'teams' ? A.season : null));
	const ratingsB = seasonResource<Rating>('ratings', () => (mode === 'teams' ? B.season : null));
	const ratingRows = $derived([
		...(ratingsA.value ?? []),
		...(B.season !== A.season ? (ratingsB.value ?? []) : [])
	]);

	function label(s: { id: string; row: Row | null; season: number }): string {
		if (mode === 'teams') return `${s.season} ${teamName(s.id)}`;
		return `${s.row?.full_name ?? s.row?.name ?? s.id} (${s.season})`;
	}
	function shortLabel(s: { id: string; row: Row | null; season: number }): string {
		if (mode === 'teams') return `${s.id} ${s.season}`;
		return `${s.row?.name ?? s.id} '${String(s.season).slice(2)}`;
	}

	interface Line {
		m: Metric;
		av: number | null;
		bv: number | null;
		ap: number | null;
		bp: number | null;
		winner: 'a' | 'b' | null;
	}
	const lines = $derived.by<Line[]>(() =>
		metrics.map((m) => {
			const av = a.row?.[m.key] ?? null;
			const bv = b.row?.[m.key] ?? null;
			// Percentile within each side's own season; flipped so 100 is always the good end.
			const p = (v: number | null, peers: Row[]) => {
				if (v == null) return null;
				const raw = percentileOf(
					v,
					peers.map((r) => r[m.key]).filter((x): x is number => x != null)
				);
				return m.better === 'low' ? 100 - raw : raw;
			};
			const ap = p(av, a.peers);
			const bp = p(bv, b.peers);
			let winner: 'a' | 'b' | null = null;
			if (m.better && ap != null && bp != null && Math.abs(ap - bp) >= 1)
				winner = ap > bp ? 'a' : 'b';
			return { m, av, bv, ap, bp, winner };
		})
	);
	const wins = $derived({
		a: lines.filter((l) => l.winner === 'a').length,
		b: lines.filter((l) => l.winner === 'b').length,
		of: lines.filter((l) => l.m.better).length
	});

	// Teams: neutral-field projection from each side's latest power rating in its season.
	function lastRating(team: string, season: number): Rating | undefined {
		const rs = ratingRows.filter((r) => r.team === team && r.season === season);
		return rs.reduce<Rating | undefined>(
			(best, r) => (!best || r.week > best.week ? r : best),
			undefined
		);
	}
	const proj = $derived.by(() => {
		if (mode !== 'teams') return null;
		const ra = lastRating(a.id, a.season);
		const rb = lastRating(b.id, b.season);
		const sigma = predsRes.value?.params.sigma;
		if (!ra || !rb || !sigma) return null;
		const margin = ra.points - rb.points;
		return { ra, rb, margin, pA: normCdf(margin / sigma) };
	});

	function pathChart(width: number) {
		const rows = [
			...ratingRows
				.filter((r) => r.team === a.id && r.season === a.season)
				.map((r) => ({ ...r, who: shortLabel(a) })),
			...ratingRows
				.filter((r) => r.team === b.id && r.season === b.season)
				.map((r) => ({ ...r, who: shortLabel(b) }))
		];
		const weeks = [...new Set(rows.map((r) => r.week))].sort((x, y) => x - y);
		return Plot.plot({
			width,
			height: 260,
			style: plotStyle,
			marginLeft: 40,
			marginRight: isNarrow(width) ? 10 : 70,
			color: {
				domain: [shortLabel(a), shortLabel(b)],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			x: { label: 'After week →', ticks: thinTicks(weeks, width, 32), tickFormat: 'd' },
			y: { label: '↑ Power rating (points vs average)', tickFormat: signedTick },
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.line(rows, {
					x: 'week',
					y: 'points',
					stroke: 'who',
					strokeWidth: 2.5,
					curve: 'monotone-x'
				}),
				Plot.dot(rows, { x: 'week', y: 'points', fill: 'who', r: 3 }),
				Plot.tip(
					rows,
					Plot.pointer({
						x: 'week',
						y: 'points',
						title: (d: Rating & { who: string }) =>
							`${d.who}, after week ${d.week}\n${signed(d.points)} pts (#${d.rank})`
					})
				)
			]
		});
	}

	const options = (season: number) => seasonPool(season).rows.slice(0, mode === 'teams' ? 32 : 120);
	const status = $derived(
		metaRes.value?.seasons.find((s) => s.season === Math.max(a.season, b.season))
	);
	const ready = $derived(!!pool && !!metaRes.value);
	const error = $derived(metaRes.error ?? teamsRes.error ?? loadError);
</script>

<svelte:head><title>Compare · Any Given Stat</title></svelte:head>

<div class="page-head">
	<div class="eyebrow">Compare</div>
	<h1>Tale of the tape</h1>
	<p class="lede">
		Any two teams or players, each from any season since 2016. Bars are league percentiles within
		that player's or team's own season (100 = best), so different eras compare fairly.
	</p>
</div>

<div class="toolbar">
	<div class="seg" role="group" aria-label="What to compare">
		{#each MODES as m (m.key)}
			<button aria-pressed={mode === m.key} onclick={() => setMode(m.key)}>{m.label}</button>
		{/each}
	</div>
	{#if mode === 'teams' || mode === 'qbs'}
		<div class="seg" role="group" aria-label="Play filter">
			<button
				aria-pressed={prefs.scope === 'no_garbage'}
				onclick={() => (prefs.scope = 'no_garbage')}>No garbage time</button
			>
			<button aria-pressed={prefs.scope === 'all'} onclick={() => (prefs.scope = 'all')}
				>All plays</button
			>
		</div>
	{/if}
</div>

{#if error}
	<LoadError message={error} />
{:else if !ready}
	<Skeleton height={420} />
{:else}
	<SampleWarning {status} />
	<div class="pickers">
		{#each [{ s: a, k: 'a' as const }, { s: b, k: 'b' as const }] as { s, k } (k)}
			<div class="picker card side-{k}">
				<span class="dot" aria-hidden="true"></span>
				<label class="field">
					Season
					<select value={s.season} onchange={(e) => setSeason(k, Number(e.currentTarget.value))}>
						{#each seasons as y (y)}<option value={y}>{y}</option>{/each}
					</select>
				</label>
				<label class="field grow">
					{mode === 'teams' ? 'Team' : 'Player'}
					<select value={s.id} onchange={(e) => setSide(k, e.currentTarget.value, s.season)}>
						{#if !s.row}<option value={s.id}>{s.id || '—'}</option>{/if}
						{#each options(s.season) as r (r[idKey])}
							<option value={r[idKey]}
								>{mode === 'teams'
									? teamName(r.team)
									: `${r.full_name ?? r.name} · ${r.team} · ${num(r[volKey!])} ${volKey}`}</option
							>
						{/each}
					</select>
				</label>
			</div>
			{#if k === 'a'}
				<button class="ghost swap" onclick={swap} aria-label="Swap sides" title="Swap sides"
					>⇄</button
				>
			{/if}
		{/each}
	</div>

	<section class="card tape">
		<div class="tape-head">
			<div class="who a">
				{#if mode === 'teams'}<TeamBadge team={a.id} size="lg" />{:else if a.row}<TeamBadge
						team={a.row.team}
						size="md"
					/>{/if}
				<div>
					<div class="name">{label(a)}</div>
					<div class="score"><b>{wins.a}</b> of {wins.of} categories</div>
				</div>
			</div>
			<div class="vs" aria-hidden="true">VS</div>
			<div class="who b">
				<div>
					<div class="name">{label(b)}</div>
					<div class="score"><b>{wins.b}</b> of {wins.of} categories</div>
				</div>
				{#if mode === 'teams'}<TeamBadge team={b.id} size="lg" />{:else if b.row}<TeamBadge
						team={b.row.team}
						size="md"
					/>{/if}
			</div>
		</div>

		{#if proj}
			{@const fav = proj.margin >= 0 ? a : b}
			<p class="proj">
				On a neutral field the ratings make <b>{shortLabel(fav)}</b> a
				<b>{num(Math.abs(proj.margin), 1)}-point</b> favorite, winning
				<b>{num(Math.max(proj.pA, 1 - proj.pA) * 100)}%</b> of the time
				<span class="muted"
					>(each season's final ratings; assumes a typical miss of {num(
						predsRes.value?.params.sigma,
						1
					)} pts)</span
				>.
			</p>
		{/if}

		<ul class="rows" aria-label="Category by category">
			{#each lines as l (l.m.key)}
				<li class:neutral={!l.m.better}>
					<span class="val a" class:win={l.winner === 'a'}
						>{l.av == null ? '–' : l.m.fmt(l.av)}{#if l.winner === 'a'}<span class="sr-only">
								(better)</span
							>{/if}</span
					>
					<span class="bar a" aria-hidden="true"><span style:width="{l.ap ?? 0}%"></span></span>
					<span class="metric" title={l.m.title}>{l.m.label}</span>
					<span class="bar b" aria-hidden="true"><span style:width="{l.bp ?? 0}%"></span></span>
					<span class="val b" class:win={l.winner === 'b'}
						>{l.bv == null ? '–' : l.m.fmt(l.bv)}{#if l.winner === 'b'}<span class="sr-only">
								(better)</span
							>{/if}</span
					>
				</li>
			{/each}
		</ul>
		<p class="foot muted">
			Bar length = percentile in that season{volKey
				? ` among players with at least 40% of the leader's ${volKey}`
				: ''}; flipped where lower is better, so longer is always better. Gray rows are style, not
			quality, and don't count toward the category score.
		</p>
	</section>

	{#if mode === 'teams'}
		<section class="card">
			<h2>Power rating, week by week</h2>
			<p class="sub">
				Each team through its own season. Points better than an average team on a neutral field.
			</p>
			<PlotFigure
				label="Power rating paths of {shortLabel(a)} and {shortLabel(b)}"
				render={pathChart}
			/>
		</section>
	{/if}
{/if}

<style>
	.pickers {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		gap: 0.75rem;
		align-items: center;
		margin-bottom: 1rem;
	}
	.picker {
		display: flex;
		align-items: end;
		gap: 0.6rem;
		padding: 0.75rem 0.9rem;
	}
	.picker .grow {
		flex: 1;
		min-width: 0;
	}
	.picker select {
		min-width: 0;
		max-width: 100%;
	}
	.toolbar .seg {
		flex-wrap: wrap;
	}
	.picker .grow select {
		width: 100%;
	}
	.dot {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		align-self: center;
		flex: none;
	}
	.side-a .dot {
		background: var(--series-1);
	}
	.side-b .dot {
		background: var(--series-2);
	}
	.swap {
		font-size: 1.2rem;
		width: 44px;
		height: 44px;
		padding: 0;
		border-radius: 50%;
	}
	.tape-head {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		gap: 1rem;
		margin-bottom: 0.75rem;
	}
	.who {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		min-width: 0;
	}
	.who.b {
		justify-content: flex-end;
		text-align: right;
	}
	.name {
		font: 800 clamp(1rem, 0.9rem + 0.6vw, 1.35rem) / 1.15 var(--display);
	}
	.score {
		font-size: 0.82rem;
		color: var(--text-secondary);
	}
	.score b {
		color: var(--text-primary);
	}
	.vs {
		font: 900 1.4rem var(--display);
		letter-spacing: 0.05em;
		background: linear-gradient(135deg, var(--series-1), var(--series-2));
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
	}
	.proj {
		margin: 0 0 1rem;
		padding: 0.6rem 0.8rem;
		border-radius: 10px;
		background: var(--surface-2);
		font-size: 0.92rem;
	}
	.rows {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.rows li {
		display: grid;
		grid-template-columns: 5.5rem 1fr minmax(9rem, 12rem) 1fr 5.5rem;
		align-items: center;
		gap: 0.6rem;
		padding: 0.32rem 0;
		border-bottom: 1px solid var(--grid);
		font-size: 0.88rem;
	}
	.rows li:last-child {
		border-bottom: 0;
	}
	.metric {
		text-align: center;
		color: var(--text-secondary);
		font-weight: 500;
	}
	.val {
		font-variant-numeric: tabular-nums;
		color: var(--text-secondary);
	}
	.val.a {
		text-align: right;
	}
	.val.win {
		color: var(--text-primary);
		font-weight: 800;
	}
	.bar {
		display: flex;
		height: 12px;
		border-radius: 6px;
		background: var(--surface-2);
		overflow: hidden;
	}
	.bar.a {
		justify-content: flex-end;
	}
	.bar span {
		display: block;
		height: 100%;
		border-radius: 6px;
		animation: grow 0.6s var(--ease) both;
		transition: width 0.35s var(--ease);
	}
	.bar.a span {
		background: var(--series-1);
		transform-origin: right;
	}
	.bar.b span {
		background: var(--series-2);
		transform-origin: left;
	}
	.neutral .bar span {
		background: var(--neutral-mark);
	}
	@keyframes grow {
		from {
			transform: scaleX(0);
		}
	}
	.foot {
		font-size: 0.78rem;
		margin: 0.75rem 0 0;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
	@media (max-width: 720px) {
		.pickers {
			grid-template-columns: 1fr;
		}
		.swap {
			justify-self: center;
		}
		.picker {
			flex-wrap: wrap;
		}
		.rows li {
			grid-template-columns: 4.5rem 1fr 4.5rem;
			grid-template-areas: 'metric metric metric' 'va bars vb';
			row-gap: 0.2rem;
		}
		.rows li .metric {
			grid-area: metric;
		}
		.rows li .val.a {
			grid-area: va;
		}
		.rows li .val.b {
			grid-area: vb;
		}
		.rows li .bar.a {
			grid-area: bars;
			margin-right: 50%;
		}
		.rows li .bar.b {
			grid-area: bars;
			margin-left: 50%;
		}
		.tape-head {
			grid-template-columns: 1fr;
			text-align: center;
		}
		.who,
		.who.b {
			justify-content: center;
			text-align: center;
		}
		.vs {
			justify-self: center;
		}
	}
</style>
