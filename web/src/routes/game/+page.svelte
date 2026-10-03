<script lang="ts">
	import { ratingsWeek } from '$lib/season';
	import { base } from '$app/paths';
	import BoxScore from '$lib/components/BoxScore.svelte';
	import { fantasyIds, scoringLabel } from '$lib/fantasy/data.svelte';
	import { fantasy } from '$lib/fantasy/league.svelte';
	import { scoreLine } from '$lib/fantasy/scoring';
	import CountUp from '$lib/components/CountUp.svelte';
	import { page } from '$app/state';
	import GameFlow from '$lib/components/GameFlow.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import TeamLogo from '$lib/components/TeamLogo.svelte';
	import { epa, num, pct, signed, spread } from '$lib/format';
	import {
		elapsedAt,
		excitementPercentile,
		excitement,
		loadGamePlays,
		loadSeasonGames,
		seasonFromGameId,
		winnerLow,
		wpAt
	} from '$lib/games';
	import { gridY, isNarrow, Plot, plotStyle } from '$lib/plot';
	import { theme } from '$lib/theme.svelte';
	import { resource, seasonResource } from '$lib/resource.svelte';
	import { matchupColors, teamName, teamNick } from '$lib/teams.svelte';
	import { load, loadPath } from '$lib/data';
	import { kickoffLabel, played as isPlayed, records, weekLabel } from '$lib/standings';
	import { wlt } from '$lib/format';
	import type {
		BoxSide,
		GameDetail,
		GamePlays,
		GamePrediction,
		PlayoffOdds,
		Predictions,
		Rating,
		ScheduleGame,
		TeamSeason
	} from '$lib/types';

	const id = $derived(page.url.searchParams.get('id') ?? '');
	const season = $derived(seasonFromGameId(id));
	// Forecasts for coming games come from the slim upcoming.json; the 800 KB backtest file
	// (model lines for played games) loads only for a finished game.
	const up = resource('upcoming');
	let backtest = $state.raw<Predictions | null>(null);
	let backtestDone = $state(false);
	const ratings = seasonResource<Rating>('ratings', () => season);
	const teams = resource('teams');
	const meta = resource('meta');
	const schedule = seasonResource<ScheduleGame>('schedule', () => season);
	const ids = fantasyIds();
	// The schedule row: kickoff, stadium, coaches, referee, and whether it's been played.
	const row = $derived(schedule.value?.find((g) => g.game_id === id));

	let game = $state.raw<GameDetail | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	$effect(() => {
		const want = id;
		loading = true;
		error = null;
		game = null;
		if (!Number.isFinite(season)) {
			loading = false;
			return;
		}
		loadSeasonGames(season)
			.then((all) => {
				if (want === id) game = all.find((g) => g.game_id === want) ?? null;
			})
			.catch((e) => (error = String(e.message ?? e)))
			.finally(() => (loading = false));
	});

	// Full play-by-play (optional: older builds don't have it; the page works without). Waits for
	// the schedule so an unplayed game doesn't request a file that can't exist yet.
	let plays = $state.raw<GamePlays | null>(null);
	$effect(() => {
		const want = id;
		plays = null;
		if (!want || !schedule.value) return;
		const r = schedule.value.find((g) => g.game_id === want);
		if (r && !isPlayed(r)) return;
		loadGamePlays(want)
			.then((p) => {
				if (want === id) plays = p;
			})
			.catch(() => {});
	});

	// Hovered play → a marker on the WP chart, positioned with the chart's own x scale.
	let hoverT = $state<number | null>(null);
	let wpX = null as ((v: number) => number) | null;
	const markerX = $derived(hoverT != null && wpX ? wpX(hoverT / 60) : null);

	// The model/Vegas line for this game: a backtest row if played, a forecast if upcoming.
	const line = $derived<GamePrediction | undefined>(
		backtest?.games.find((g) => g.game_id === id) ??
			up.value?.upcoming.find((g) => g.game_id === id) ??
			up.value?.next_games?.find((g) => g.game_id === id)
	);
	const home = $derived(game?.home ?? row?.home ?? line?.home ?? '');
	const away = $derived(game?.away ?? row?.away ?? line?.away ?? '');
	const week = $derived(game?.week ?? row?.week ?? line?.week);
	const when = $derived(row ?? line);
	const roundLabel = $derived(
		row ? weekLabel(row) : game?.season_type === 'POST' ? 'Playoffs' : `Week ${week}`
	);
	const tq = $derived(`season=${season}`);
	// Other games the same week, for moving on.
	const sameWeek = $derived(
		(schedule.value ?? []).filter(
			(g) => g.week === week && g.game_type === (row?.game_type ?? 'REG') && g.game_id !== id
		)
	);
	const recs = $derived(records(schedule.value ?? []));
	// Playoff odds after the latest simulated week, for the preview.
	let odds = $state.raw<PlayoffOdds | null>(null);
	$effect(() => {
		const s = season;
		odds = null;
		if (!Number.isFinite(s)) return;
		loadPath<PlayoffOdds>(`playoff_odds/${s}`)
			.then((o) => (odds = o))
			.catch(() => {});
	});
	const oddsNow = $derived.by(() => {
		if (!odds) return new Map();
		const wk = Math.max(...odds.weeks.filter((w) => week == null || w < week));
		return new Map(odds.rows.filter((r) => r.week === wk).map((r) => [r.team, r]));
	});
	/** Best estimate (market blend) if there is one, else the model: "NYG 55%". */
	function favored(l: GamePrediction): string {
		const wp = l.blend_wp ?? l.home_wp;
		return wp >= 0.5 ? `${l.home} ${pct(wp, 0)}` : `${l.away} ${pct(1 - wp, 0)}`;
	}
	const people = (name: string) => encodeURIComponent(name);
	const sideColors = $derived(matchupColors(away, home));
	const exPct = $derived(game ? excitementPercentile(excitement(game)) : 0);
	const played = $derived(!!game && game.home_score != null && game.wp.length > 1);
	// The header can show the final from the schedule before the game file arrives.
	const final = $derived(played || (!!row && isPlayed(row)));
	const awayPts = $derived(game?.away_score ?? row?.away_score ?? null);
	const homePts = $derived(game?.home_score ?? row?.home_score ?? null);
	const homeWon = $derived((homePts ?? 0) > (awayPts ?? 0));
	$effect(() => {
		if (!final || backtest) return;
		load('predictions')
			.then((p) => (backtest = p))
			.catch(() => {})
			.finally(() => (backtestDone = true));
	});

	type Marked = GameDetail['top_plays'][number] & { n: number; t: number; wp: number };
	const marked = $derived<Marked[]>(
		(game?.top_plays ?? []).flatMap((p, i) => {
			const t = elapsedAt(p.qtr, p.time);
			return t == null ? [] : [{ ...p, n: i + 1, t, wp: wpAt(game!, t) }];
		})
	);

	// Plays with their elapsed second, for the WP tooltip (score + what happened).
	type Moment = { e: number; qtr: number; time: string; hs: number; as: number; desc: string };
	const moments = $derived.by<Moment[]>(() => {
		const out: Moment[] = [];
		for (const p of plays?.plays ?? []) {
			const e = elapsedAt(p[0], p[1]);
			if (e == null || !p[1]) continue;
			out.push({ e, qtr: p[0], time: p[1], hs: p[10] ?? 0, as: p[11] ?? 0, desc: p[7] });
		}
		return out;
	});
	function momentAt(sec: number): Moment | undefined {
		let lo = 0;
		let hi = moments.length - 1;
		let found: Moment | undefined;
		while (lo <= hi) {
			const mid = (lo + hi) >> 1;
			if (moments[mid].e <= sec) {
				found = moments[mid];
				lo = mid + 1;
			} else hi = mid - 1;
		}
		return found;
	}
	const clip = (t: string, n: number) => (t.length > n ? t.slice(0, n - 1).trimEnd() + '…' : t);

	const WP_MARGIN = { top: 16, right: 16, bottom: 30, left: 44 };
	type Placed = Marked & { lx: number; ly: number };

	/** Numbered badges sit off the line in the direction of the swing; each takes the first
	 * slot (stepping away from the line, then the other side) that clears every badge already
	 * placed, so close plays never stack. Works in pixels, returns data coordinates. */
	function placeMarkers(width: number, height: number, end: number): Placed[] {
		const m = WP_MARGIN;
		const iw = width - m.left - m.right;
		const ih = height - m.top - m.bottom;
		const px = (t: number) => m.left + (t / end) * iw;
		const py = (wp: number) => m.top + (1 - wp) * ih;
		const placed: { x: number; y: number }[] = [];
		const out: Placed[] = [];
		for (const d of [...marked].sort((a, b) => a.t - b.t)) {
			const x = px(d.t);
			const y0 = py(d.wp);
			const dir = d.home_wpa > 0 ? -1 : 1; // home swing pushes the line up
			const tries = [26, 46, 66, 86].flatMap((o) => [y0 + dir * o, y0 - dir * o]);
			const fits = (y: number) =>
				y > m.top + 10 &&
				y < height - m.bottom - 10 &&
				placed.every((p) => Math.hypot(p.x - x, p.y - y) > 21);
			const y = tries.find(fits) ?? y0 + dir * 26;
			placed.push({ x, y });
			out.push({ ...d, lx: d.t / 60, ly: 1 - (y - m.top) / ih });
		}
		return out;
	}

	function wpChart(width: number) {
		const g = game!;
		const narrow = isNarrow(width);
		const height = narrow ? 280 : 380;
		const end = Math.max(3600, g.wp.at(-1)![0]);
		const pts = g.wp.map(([t, wp]) => ({ t: t / 60, wp }));
		const { home: hc, away: ac } = matchupColors(g.away, g.home);
		const ot = end > 3600;
		const bounds = [15, 30, 45, ...(ot ? [60] : [])];
		const periods = [
			{ x: 7.5, label: narrow ? 'Q1' : '1st' },
			{ x: 22.5, label: narrow ? 'Q2' : '2nd' },
			{ x: 37.5, label: narrow ? 'Q3' : '3rd' },
			{ x: 52.5, label: narrow ? 'Q4' : '4th' },
			...(ot ? [{ x: (60 + end / 60) / 2, label: 'OT' }] : [])
		];
		const fade = theme.dark ? 0.34 : 0.2;
		const badges = placeMarkers(width, height, end);
		const last = pts.at(-1)!;
		const chart = Plot.plot({
			width,
			height,
			style: plotStyle,
			marginTop: WP_MARGIN.top,
			marginRight: WP_MARGIN.right,
			marginBottom: WP_MARGIN.bottom,
			marginLeft: WP_MARGIN.left,
			x: { domain: [0, end / 60], label: null, axis: null },
			y: {
				domain: [0, 1],
				label: null,
				ticks: [0, 0.25, 0.5, 0.75, 1],
				tickSize: 0,
				tickFormat: (v: number) => `${Math.round(Math.max(v, 1 - v) * 100)}%`
			},
			marks: [
				gridY(),
				Plot.ruleX(bounds, {
					stroke: 'var(--grid)',
					strokeWidth: (d: number) => (d === 30 ? 2 : 1)
				}),
				Plot.axisX(
					periods.map((p) => p.x),
					{
						tickSize: 0,
						label: null,
						tickFormat: (x: number) => periods.find((p) => p.x === x)?.label ?? ''
					}
				),
				Plot.areaY(pts, {
					x: 't',
					y1: 0.5,
					y2: (d) => Math.max(d.wp, 0.5),
					fill: hc,
					fillOpacity: fade,
					curve: 'step-after',
					className: 'wp-area-home'
				}),
				Plot.areaY(pts, {
					x: 't',
					y1: 0.5,
					y2: (d) => Math.min(d.wp, 0.5),
					fill: ac,
					fillOpacity: fade,
					curve: 'step-after',
					className: 'wp-area-away'
				}),
				Plot.ruleY([0.5], { stroke: 'var(--axis)', strokeWidth: 1.5 }),
				Plot.line(pts, {
					x: 't',
					y: 'wp',
					stroke: 'var(--text-primary)',
					strokeWidth: 1.75,
					strokeLinejoin: 'round',
					curve: 'step-after'
				}),
				// Final result: a dot in the winner's color where the line ends.
				Plot.dot([last], {
					x: 't',
					y: 'wp',
					r: 4.5,
					fill: last.wp >= 0.5 ? hc : ac,
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				// Swing markers: a dot on the line, a leader, and the numbered badge.
				Plot.link(badges, {
					x1: 'lx',
					y1: (d: Placed) => d.wp,
					x2: 'lx',
					y2: 'ly',
					stroke: (d: Placed) => (d.home_wpa > 0 ? hc : ac),
					strokeWidth: 1.5
				}),
				Plot.dot(badges, {
					x: 'lx',
					y: 'wp',
					r: 4,
					fill: (d: Placed) => (d.home_wpa > 0 ? hc : ac),
					stroke: 'var(--surface)',
					strokeWidth: 1.5
				}),
				Plot.dot(badges, {
					x: 'lx',
					y: 'ly',
					r: 9.5,
					fill: 'var(--surface)',
					stroke: (d: Placed) => (d.home_wpa > 0 ? hc : ac),
					strokeWidth: 2.5
				}),
				Plot.text(badges, {
					x: 'lx',
					y: 'ly',
					text: 'n',
					fill: 'var(--text-primary)',
					fontWeight: 700,
					fontSize: 11
				}),
				Plot.tip(
					pts,
					Plot.pointerX({
						x: 't',
						y: 'wp',
						maxRadius: 60,
						title: (d: { t: number; wp: number }) => {
							const mo = momentAt(d.t * 60);
							const lead =
								d.wp >= 0.5 ? `${g.home} ${pct(d.wp, 0)}` : `${g.away} ${pct(1 - d.wp, 0)}`;
							if (!mo) return `${lead} to win`;
							const q = mo.qtr > 4 ? 'OT' : `Q${mo.qtr}`;
							return `${q} ${mo.time} · ${g.away} ${mo.as}, ${g.home} ${mo.hs}\n${lead} to win\n${clip(mo.desc, narrow ? 70 : 110)}`;
						}
					})
				)
			]
		});
		const x = chart.scale('x');
		wpX = x?.apply ? (v: number) => x.apply!(v) as number : null;
		// Gradient fills: each side is strongest at certainty and fades into the 50% line.
		const yS = chart.scale('y');
		if (yS?.apply) {
			const y = (v: number) => yS.apply!(v) as number;
			const ns = 'http://www.w3.org/2000/svg';
			const svg = chart.tagName.toLowerCase() === 'svg' ? chart : chart.querySelector('svg');
			const defs = document.createElementNS(ns, 'defs');
			const uid = Math.random().toString(36).slice(2, 8);
			const gradient = (id: string, color: string, from: number, to: number) => {
				const g = document.createElementNS(ns, 'linearGradient');
				g.setAttribute('id', id);
				g.setAttribute('gradientUnits', 'userSpaceOnUse');
				g.setAttribute('x1', '0');
				g.setAttribute('x2', '0');
				g.setAttribute('y1', String(y(from)));
				g.setAttribute('y2', String(y(to)));
				const strong = Math.min(0.75, fade * 2.6);
				for (const [offset, op] of [
					['0', strong],
					['1', fade * 0.25]
				] as const) {
					const stop = document.createElementNS(ns, 'stop');
					stop.setAttribute('offset', offset);
					// Style, not attributes: the color may be a CSS variable (series fallback).
					stop.style.stopColor = color;
					stop.style.stopOpacity = String(op);
					g.appendChild(stop);
				}
				defs.appendChild(g);
			};
			gradient(`wp-h-${uid}`, hc, 1, 0.5);
			gradient(`wp-a-${uid}`, ac, 0, 0.5);
			svg?.prepend(defs);
			for (const [cls, id] of [
				['wp-area-home', `wp-h-${uid}`],
				['wp-area-away', `wp-a-${uid}`]
			]) {
				for (const path of chart.querySelectorAll(`.${cls} path`)) {
					path.setAttribute('fill', `url(#${id})`);
					path.setAttribute('fill-opacity', '1');
				}
			}
		}
		return chart;
	}

	const boxRows: {
		key: keyof BoxSide;
		label: string;
		fmt: (v: number | null) => string;
		better: 'high' | 'low';
	}[] = [
		{ key: 'epa_play', label: 'EPA per play', fmt: (v) => epa(v), better: 'high' },
		{ key: 'success_rate', label: 'Success rate', fmt: (v) => pct(v), better: 'high' },
		{ key: 'pass_epa', label: 'Pass EPA/play', fmt: (v) => epa(v), better: 'high' },
		{ key: 'rush_epa', label: 'Rush EPA/play', fmt: (v) => epa(v), better: 'high' },
		{ key: 'yards', label: 'Yards', fmt: (v) => num(v), better: 'high' },
		{ key: 'turnovers', label: 'Turnovers', fmt: (v) => num(v), better: 'low' }
	];
	// The box score's team table already has yards and turnovers.
	const effRows = $derived(
		boxRows.filter((r) => !plays?.box || !['yards', 'turnovers'].includes(r.key))
	);
	function edge(r: (typeof boxRows)[number], side: 'home' | 'away'): boolean {
		const a = game?.box.home?.[r.key];
		const b = game?.box.away?.[r.key];
		if (a == null || b == null || a === b || r.key === 'plays') return false;
		const homeBetter = r.better === 'high' ? a > b : a < b;
		return side === 'home' ? homeBetter : !homeBetter;
	}

	// Matchup preview for upcoming games: latest power ratings and season unit stats.
	const latestRatings = $derived.by(() => {
		const rs = (ratings.value ?? []).filter((r) => r.season === season);
		const wk = ratingsWeek(
			rs.map((r) => r.week),
			meta.value?.seasons.find((s) => s.season === season)
		);
		return new Map<string, Rating>(rs.filter((r) => r.week === wk).map((r) => [r.team, r]));
	});
	const unit = $derived(
		new Map<string, TeamSeason>(
			(teams.value ?? [])
				.filter((t) => t.season === season && t.scope === 'no_garbage')
				.map((t) => [t.team, t])
		)
	);
	const rankIn = (key: keyof TeamSeason, team: string, higher: boolean) => {
		const vals = [...unit.values()].map((t) => t[key] as number);
		const v = unit.get(team)?.[key] as number | undefined;
		if (v == null) return null;
		return 1 + vals.filter((x) => (higher ? x > v : x < v)).length;
	};
	const matchups = $derived([
		{ label: `${away} offense vs ${home} defense`, o: away, d: home },
		{ label: `${home} offense vs ${away} defense`, o: home, d: away }
	]);
</script>

<svelte:head
	><title>{away && home ? `${away} @ ${home}` : 'Game'} · Any Given Stat</title></svelte:head
>

{#if (!schedule.value && !game) || (loading && !line && !row)}
	<!-- Wait for the (small) schedule so the scoreboard renders final or upcoming once. -->
	<Skeleton height={190} rows={0} />
{:else if error}
	<LoadError message={error} />
{:else if !game && !line && !row}
	<div class="callout">
		No game with id <code>{id}</code>. <a href="{base}/games/">Browse games</a>.
	</div>
{:else}
	<section class="scoreboard card" style:--away={sideColors.away} style:--home={sideColors.home}>
		<nav class="crumbs" aria-label="Breadcrumb">
			<a href="{base}/games/?{tq}">Games</a>
			<span aria-hidden="true">›</span>
			<a href="{base}/games/?{tq}{week != null ? `&week=${week}` : ''}">{season} {roundLabel}</a>
			{#if when?.gameday}<span class="when"
					>· {new Date(`${when.gameday}T12:00:00`).toLocaleDateString('en-US', {
						month: 'short',
						day: 'numeric'
					})}, {kickoffLabel(when.gameday, when.gametime)}</span
				>{/if}
			{#if row?.neutral ?? line?.neutral}<span>· neutral site</span>{/if}
		</nav>
		<h1 class="sr-only">{teamName(away)} at {teamName(home)}, {season} {roundLabel}</h1>
		<div class="teams">
			<div class="side" class:dim={final && homeWon}>
				<a class="logo-link" href="{base}/team/?t={away}&{tq}" aria-label={teamName(away)}
					><TeamLogo team={away} size={64} /></a
				>
				<div>
					<a class="name" href="{base}/team/?t={away}&{tq}">{teamName(away)}</a>
					<div class="muted small">Away</div>
				</div>
				{#if final}<div class="pts">
						<CountUp text={String(awayPts ?? '')} duration={900} />
					</div>{/if}
			</div>
			<div class="vs">{final ? 'Final' : '@'}</div>
			<div class="side right" class:dim={final && !homeWon}>
				{#if final}<div class="pts">
						<CountUp text={String(homePts ?? '')} duration={900} />
					</div>{/if}
				<div>
					<a class="name" href="{base}/team/?t={home}&{tq}">{teamName(home)}</a>
					<div class="muted small">Home</div>
				</div>
				<a class="logo-link" href="{base}/team/?t={home}&{tq}" aria-label={teamName(home)}
					><TeamLogo team={home} size={64} /></a
				>
			</div>
		</div>
		{#if line || row}
			{@const vegas = line?.vegas ?? row?.vegas ?? null}
			{@const pending = backtestDone ? '–' : '…'}
			<!-- Rendered from the schedule first so the row doesn't pop in when the forecast loads. -->
			<div class="lines">
				{#if !final && line?.blend_wp != null}
					<div>
						<span class="k" title="Our model blended with the Vegas line">Best estimate</span>
						<b>{favored(line)} to win</b>
					</div>
				{/if}
				<div><span class="k">Vegas</span> <b>{spread(vegas, home, away)}</b></div>
				{#if line || final}
					<div>
						<span class="k">Model</span>
						<b>{line ? spread(line.model, line.home, line.away) : pending}</b>
					</div>
				{:else}
					<div class="muted small">The model's line posts the week of the game.</div>
				{/if}
				{#if final}
					<div>
						<span class="k">Model win prob</span>
						<b
							>{!line
								? pending
								: line.home_wp >= 0.5
									? `${line.home} ${pct(line.home_wp, 0)}`
									: `${line.away} ${pct(1 - line.home_wp, 0)}`}</b
						>
					</div>
					{#if vegas != null}
						{@const r = (homePts ?? 0) - (awayPts ?? 0)}
						<div>
							<span class="k">Against the spread</span>
							<b>{r === vegas ? 'Push' : (r > vegas ? home : away) + ' covered'}</b>
						</div>
					{/if}
				{/if}
			</div>
		{/if}
	</section>

	{#if played && game}
		<div class="tiles">
			<div class="card tile">
				<div class="label">Excitement index</div>
				<div class="value"><CountUp text={excitement(game).toFixed(1)} /></div>
				<div class="note">
					Total win-probability swing. {exPct >= 0.99
						? 'One of the most exciting games since 2016 (top 1%).'
						: `More exciting than ${Math.round(exPct * 100)}% of games since 2016.`}
				</div>
			</div>
			<div class="card tile">
				<div class="label">Winner's lowest win prob</div>
				<div class="value"><CountUp text={pct(winnerLow(game), 0)} /></div>
				<div class="note">How close they came to losing</div>
			</div>
			<div class="card tile">
				<div class="label">EPA per play</div>
				<div class="value">
					{epa(game.box.away?.epa_play, 2)} / {epa(game.box.home?.epa_play, 2)}
				</div>
				<div class="note">{away} / {home}</div>
			</div>
		</div>

		<div class="card">
			<h2>Win probability</h2>
			<p class="sub">
				Above the line, the {teamNick(home)} were favored; below it, the {teamNick(away)}. Numbered
				circles mark the plays that swung it most (listed below). Hover for the score and the play
				at any moment. Win probability from the nflfastR model, which includes the pre-game Vegas
				line.
			</p>
			<div class="wp-wrap">
				<div class="wp-side top" aria-hidden="true">
					<TeamBadge team={home} /> <span>favored</span>
				</div>
				<div class="wp-side bottom" aria-hidden="true">
					<TeamBadge team={away} /> <span>favored</span>
				</div>
				<PlotFigure label="Win probability over the game" render={wpChart} />
				{#if markerX != null}
					<div class="wp-marker" style:left="{markerX}px" aria-hidden="true"></div>
				{/if}
			</div>
		</div>

		<div class="card">
			<h2>Plays that decided it</h2>
			<p class="sub">The biggest swings in win probability, numbered as on the chart.</p>
			<ol class="plays">
				{#each game.top_plays as p, i (i)}
					<li>
						<span
							class="n"
							style="border-color: {p.home_wpa > 0 ? sideColors.home : sideColors.away}"
							>{i + 1}</span
						>
						<div>
							<div class="play-head">
								<TeamBadge team={p.posteam} />
								<span class="muted small">Q{p.qtr > 4 ? 'OT' : p.qtr} · {p.time}</span>
								<span
									class="chip swing"
									style="border-color: {p.home_wpa > 0 ? sideColors.home : sideColors.away}"
									>{p.home_wpa > 0 ? home : away} +{Math.round(Math.abs(p.home_wpa) * 100)}% WP</span
								>
							</div>
							<p class="desc">{p.desc}</p>
						</div>
					</li>
				{/each}
			</ol>
		</div>

		{#if plays}
			<GameFlow data={plays} {home} {away} onhover={(t) => (hoverT = t)} />
		{:else if schedule.value}
			<Skeleton height={200} />
		{/if}

		<div class="grid-2">
			<div class="card">
				<h2>Efficiency</h2>
				<p class="sub">Scrimmage plays only. Bold = better side.</p>
				<table class="box">
					<thead>
						<tr><th></th><th><TeamBadge team={away} /></th><th><TeamBadge team={home} /></th></tr>
					</thead>
					<tbody>
						{#each effRows as r (r.key)}
							<tr>
								<td>{r.label}</td>
								<td class:win={edge(r, 'away')}>{r.fmt(game.box.away?.[r.key] ?? null)}</td>
								<td class:win={edge(r, 'home')}>{r.fmt(game.box.home?.[r.key] ?? null)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{@render info()}
		</div>

		{#if plays?.box}
			<BoxScore
				box={plays.box}
				{away}
				{home}
				{season}
				awayScore={game.away_score}
				homeScore={game.home_score}
				fantasy={{
					label: scoringLabel(),
					score: (line, pos) => scoreLine(line, pos, fantasy.scoring)
				}}
				owners={ids.value ? fantasy.ownership(ids.value) : null}
			/>
		{/if}
	{:else if final && loading}
		<Skeleton height={900} />
	{:else if final}
		<div class="callout">No play-by-play for this game yet.</div>
	{:else}
		<div class="callout info">
			Not played yet. Here's how the two teams match up on the season so far{line
				? ''
				: '; the forecast posts the week of the game'}.
			{#if line}<a href="{base}/predictions/">How the forecast is built →</a>{/if}
		</div>
		<div class="grid-3">
			{#each [away, home] as t (t)}
				{@const r = latestRatings.get(t)}
				{@const rec = recs.get(t)}
				{@const o = oddsNow.get(t)}
				{@const qb = line ? (t === line.home ? line.home_qb : line.away_qb) : null}
				{@const qbPts = line ? (t === line.home ? line.home_qb_pts : line.away_qb_pts) : 0}
				<div class="card">
					<div class="card-head">
						<h2><TeamBadge team={t} name link {season} /></h2>
						{#if r}<a class="chip" href="{base}/ratings/?{tq}">Power #{r.rank}</a>{/if}
					</div>
					<div class="split">
						<div><span class="k">Record</span> <b>{rec ? wlt(rec.wins, rec.games) : '0–0'}</b></div>
						<div>
							<span class="k">Playoffs</span>
							{#if o}<a href="{base}/odds/?{tq}"><b>{pct(o.p_playoffs, 0)}</b></a>{:else}<b>–</b
								>{/if}
						</div>
						<!-- Always rendered (– until ratings load) so the card keeps its size. -->
						<div><span class="k">Net</span> <b>{r ? `${signed(r.points)} pts` : '–'}</b></div>
						<div><span class="k">Offense</span> <b>{r ? signed(r.off_points) : '–'}</b></div>
						<div><span class="k">Defense</span> <b>{r ? signed(r.def_points) : '–'}</b></div>
					</div>
					{#if qb}
						<p class="muted small qbline">
							Starting QB <b>{qb}</b>{Math.abs(qbPts) >= 0.5
								? `: ${signed(qbPts)} pts vs the QBs behind the team's rating`
								: ''}
						</p>
					{/if}
				</div>
			{/each}
			{@render info()}
		</div>
		<div class="grid-2">
			{#each matchups as m (m.label)}
				{@const o = unit.get(m.o)}
				{@const d = unit.get(m.d)}
				<div class="card">
					<h2>{m.label}</h2>
					<p class="sub">Season EPA/play (no garbage time) and league rank (1 = best).</p>
					{#if o && d}
						<table class="box">
							<thead
								><tr
									><th></th><th><TeamBadge team={m.o} /> offense</th><th
										><TeamBadge team={m.d} /> defense</th
									></tr
								></thead
							>
							<tbody>
								<tr>
									<td>Overall</td>
									<td
										>{epa(o.off_epa_play)}
										<span class="muted">#{rankIn('off_epa_play', m.o, true)}</span></td
									>
									<td
										>{epa(d.def_epa_play)}
										<span class="muted">#{rankIn('def_epa_play', m.d, false)}</span></td
									>
								</tr>
								<tr>
									<td>Passing</td>
									<td
										>{epa(o.off_pass_epa)}
										<span class="muted">#{rankIn('off_pass_epa', m.o, true)}</span></td
									>
									<td
										>{epa(d.def_pass_epa)}
										<span class="muted">#{rankIn('def_pass_epa', m.d, false)}</span></td
									>
								</tr>
								<tr>
									<td>Rushing</td>
									<td
										>{epa(o.off_rush_epa)}
										<span class="muted">#{rankIn('off_rush_epa', m.o, true)}</span></td
									>
									<td
										>{epa(d.def_rush_epa)}
										<span class="muted">#{rankIn('def_rush_epa', m.d, false)}</span></td
									>
								</tr>
								<tr>
									<td>Success rate</td>
									<td
										>{pct(o.off_success_rate)}
										<span class="muted">#{rankIn('off_success_rate', m.o, true)}</span></td
									>
									<td
										>{pct(d.def_success_rate)}
										<span class="muted">#{rankIn('def_success_rate', m.d, false)}</span></td
									>
								</tr>
							</tbody>
						</table>
					{:else}
						<p class="muted">No season stats yet.</p>
					{/if}
				</div>
			{/each}
		</div>
	{/if}

	{#if sameWeek.length}
		<section class="card more" aria-labelledby="more-title">
			<div class="card-head">
				<h2 id="more-title">More {season} {roundLabel.toLowerCase()} games</h2>
				<a href="{base}/games/?{tq}{week != null ? `&week=${week}` : ''}">Game charts →</a>
			</div>
			<ul class="more-games">
				{#each sameWeek as g (g.game_id)}
					<li>
						<a href="{base}/game/?id={g.game_id}">
							<TeamBadge team={g.away} />
							{#if isPlayed(g)}<b>{g.away_score}</b>{/if}
							<span class="muted">{g.neutral ? 'vs' : '@'}</span>
							<TeamBadge team={g.home} />
							{#if isPlayed(g)}<b>{g.home_score}</b>{:else}<span class="muted small"
									>{kickoffLabel(g.gameday, g.gametime)}</span
								>{/if}
						</a>
					</li>
				{/each}
			</ul>
		</section>
	{/if}
{/if}

{#snippet info()}
	{#if row}
		<div class="card">
			<h2>Game info</h2>
			<dl class="info">
				{#if row.gameday}
					<dt>Kickoff</dt>
					<dd>
						{new Date(`${row.gameday}T12:00:00`).toLocaleDateString('en-US', {
							weekday: 'long',
							month: 'long',
							day: 'numeric'
						})}{row.gametime
							? `, ${kickoffLabel(row.gameday, row.gametime).split(' ').slice(1).join(' ')} ET`
							: ''}
					</dd>
				{/if}
				{#if row.stadium}
					<dt>Stadium</dt>
					<dd>
						{row.stadium}{row.roof
							? ` (${row.roof === 'outdoors' ? 'outdoors' : row.roof === 'dome' ? 'dome' : `${row.roof} roof`})`
							: ''}
					</dd>
				{/if}
				{#if row.away_coach || row.home_coach}
					<dt>Head coaches</dt>
					<dd>
						{#each [[away, row.away_coach], [home, row.home_coach]] as [t, c], i (t)}
							{#if c}{i ? ' · ' : ''}<a href="{base}/coaches/?q={people(c)}">{c}</a>
								<span class="muted">({t})</span>{/if}
						{/each}
					</dd>
				{/if}
				{#if row.referee}
					<dt>Referee</dt>
					<dd><a href="{base}/referees/?q={people(row.referee)}">{row.referee}</a></dd>
				{/if}
			</dl>
		</div>
	{/if}
{/snippet}

<style>
	.wp-wrap {
		position: relative;
	}
	/* Which side of the 50% line belongs to which team, in the plot's top and bottom corners
	   (left clears the chart's 44px axis margin). */
	.wp-side {
		position: absolute;
		left: 52px;
		z-index: 1;
		display: flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.15rem 0.5rem 0.15rem 0.2rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--surface) 82%, transparent);
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--text-secondary);
		pointer-events: none;
	}
	.wp-side.top {
		top: 20px;
	}
	.wp-side.bottom {
		bottom: 34px;
	}
	.wp-marker {
		position: absolute;
		top: 10px;
		bottom: 28px;
		width: 2px;
		margin-left: -1px;
		background: var(--accent);
		border-radius: 2px;
		pointer-events: none;
		box-shadow: 0 0 0 3px var(--accent-soft);
	}
	/* Each side of the scoreboard is lit in its team's color. */
	.scoreboard {
		display: grid;
		gap: 0.9rem;
		position: relative;
		overflow: hidden;
		isolation: isolate;
	}
	.scoreboard::before {
		content: '';
		position: absolute;
		inset: 0;
		z-index: -1;
		background:
			radial-gradient(
				60% 140% at 0% 50%,
				color-mix(in srgb, var(--away) 22%, transparent),
				transparent 70%
			),
			radial-gradient(
				60% 140% at 100% 50%,
				color-mix(in srgb, var(--home) 22%, transparent),
				transparent 70%
			);
		pointer-events: none;
	}
	.logo-link {
		display: block;
		border-radius: 24%;
	}
	@media (prefers-reduced-motion: no-preference) {
		.logo-link:hover :global(.logo) {
			transform: translateY(-3px) rotate(-3deg) scale(1.05);
		}
	}
	.crumbs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem 0.45rem;
		font-size: 0.85rem;
		color: var(--text-muted);
	}
	.name {
		color: inherit;
		text-decoration: none;
	}
	a.name:hover {
		text-decoration: underline;
	}
	.info {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.45rem 1rem;
		margin: 0;
		font-size: 0.9rem;
	}
	.info dt {
		color: var(--text-secondary);
	}
	.info dd {
		margin: 0;
	}
	.qbline {
		margin: 0.6rem 0 0;
	}
	.more-games {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 200px), 1fr));
		gap: 0.4rem;
	}
	.more-games a {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.6rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		color: inherit;
		text-decoration: none;
		font-variant-numeric: tabular-nums;
	}
	.more-games a:hover {
		background: var(--surface-2);
		border-color: var(--border-strong);
	}
	@media (min-width: 1000px) {
		.plays {
			grid-template-columns: 1fr 1fr;
			column-gap: 2rem;
		}
	}
	.teams {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		gap: 1rem;
	}
	.side {
		display: flex;
		align-items: center;
		gap: 0.8rem;
	}
	.side.right {
		justify-content: flex-end;
		text-align: right;
	}
	.side.dim .pts,
	.side.dim .name {
		color: var(--text-muted);
	}
	.name {
		font: 800 clamp(1rem, 0.8rem + 1vw, 1.4rem) var(--display);
	}
	.pts {
		font: 800 clamp(2.4rem, 1.5rem + 3.6vw, 4rem) / 1 var(--display);
		font-stretch: 112%;
		font-variant-numeric: tabular-nums;
		letter-spacing: -0.03em;
		margin: 0 0.5rem;
	}
	.side:not(.dim) .pts {
		text-shadow: 0 6px 30px color-mix(in srgb, var(--accent) 35%, transparent);
	}
	.side:not(.right) .pts {
		margin-left: auto;
	}
	.side.right .pts {
		margin-right: auto;
	}
	.vs {
		font: 700 0.72rem var(--display);
		text-transform: uppercase;
		letter-spacing: 0.12em;
		color: var(--text-secondary);
		padding: 0.25rem 0.6rem;
		border: 1px solid var(--border-strong);
		border-radius: 999px;
		background: var(--surface-2);
	}
	@media (max-width: 640px) {
		.teams {
			grid-template-columns: 1fr;
		}
		.side.right {
			flex-direction: row-reverse;
			justify-content: flex-end;
			text-align: left;
		}
		.side.right .pts,
		.side:not(.right) .pts {
			margin: 0 0 0 auto;
		}
		.vs {
			display: none;
		}
	}
	.lines,
	.split {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1.6rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--border);
		font-variant-numeric: tabular-nums;
	}
	.split {
		border-top: 0;
		padding-top: 0.25rem;
	}
	.k {
		color: var(--text-muted);
		font-size: 0.85rem;
		margin-right: 0.25rem;
	}
	.small {
		font-size: 0.78rem;
	}
	.plays {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.75rem;
	}
	.plays li {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.75rem;
	}
	.n {
		display: grid;
		place-items: center;
		width: 26px;
		height: 26px;
		border-radius: 50%;
		border: 2.5px solid;
		font-weight: 700;
		font-size: 0.8rem;
	}
	.play-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	.swing {
		border-width: 1.5px;
	}
	.desc {
		margin: 0.25rem 0 0;
		font-size: 0.87rem;
		color: var(--text-secondary);
	}
	.box {
		width: 100%;
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
		font-size: 0.9rem;
	}
	.box th,
	.box td {
		padding: 0.45rem 0.5rem;
		border-bottom: 1px solid var(--grid);
		text-align: right;
	}
	.box th:first-child,
	.box td:first-child {
		text-align: left;
		color: var(--text-secondary);
	}
	.box td.win {
		font-weight: 800;
		color: var(--text-primary);
	}
</style>
