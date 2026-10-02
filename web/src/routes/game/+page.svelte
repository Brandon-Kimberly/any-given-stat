<script lang="ts">
	import { base } from '$app/paths';
	import CountUp from '$lib/components/CountUp.svelte';
	import { page } from '$app/state';
	import GameFlow from '$lib/components/GameFlow.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
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
	import { resource } from '$lib/resource.svelte';
	import { matchupColors, teamName } from '$lib/teams.svelte';
	import type {
		BoxSide,
		GameDetail,
		GamePlays,
		GamePrediction,
		Rating,
		TeamSeason
	} from '$lib/types';

	const id = $derived(page.url.searchParams.get('id') ?? '');
	const season = $derived(seasonFromGameId(id));
	const preds = resource('predictions');
	const ratings = resource('ratings');
	const teams = resource('teams');

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

	// Full play-by-play (optional: older builds don't have it; the page works without).
	let plays = $state.raw<GamePlays | null>(null);
	$effect(() => {
		const want = id;
		plays = null;
		if (!want) return;
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
		preds.value?.games.find((g) => g.game_id === id) ??
			preds.value?.upcoming.find((g) => g.game_id === id)
	);
	const home = $derived(game?.home ?? line?.home ?? '');
	const away = $derived(game?.away ?? line?.away ?? '');
	const sideColors = $derived(matchupColors(away, home));
	const played = $derived(!!game && game.home_score != null && game.wp.length > 1);
	const homeWon = $derived((game?.home_score ?? 0) > (game?.away_score ?? 0));

	type Marked = GameDetail['top_plays'][number] & { n: number; t: number; wp: number };
	const marked = $derived<Marked[]>(
		(game?.top_plays ?? []).flatMap((p, i) => {
			const t = elapsedAt(p.qtr, p.time);
			return t == null ? [] : [{ ...p, n: i + 1, t, wp: wpAt(game!, t) }];
		})
	);

	function wpChart(width: number) {
		const g = game!;
		const narrow = isNarrow(width);
		const end = Math.max(3600, g.wp.at(-1)![0]);
		const pts = g.wp.map(([t, wp]) => ({ t: t / 60, wp }));
		const { home: hc, away: ac } = matchupColors(g.away, g.home);
		const quarters = [15, 30, 45, ...(end > 3600 ? [60] : [])];
		const chart = Plot.plot({
			width,
			height: narrow ? 260 : 360,
			style: plotStyle,
			marginLeft: 44,
			marginRight: narrow ? 10 : 56,
			x: {
				domain: [0, end / 60],
				label: null,
				ticks: [0, 15, 30, 45, 60],
				tickFormat: (m: number) => (m === 60 ? 'End' : m === 0 ? 'Kick' : `Q${m / 15 + 1}`)
			},
			y: {
				domain: [0, 1],
				label: null,
				ticks: [0, 0.25, 0.5, 0.75, 1],
				tickFormat: (v: number) =>
					v === 0.5
						? '50%'
						: v > 0.5
							? `${g.home} ${Math.round(v * 100)}%`
							: `${g.away} ${Math.round((1 - v) * 100)}%`
			},
			marks: [
				gridY(),
				Plot.ruleX(quarters, { stroke: 'var(--grid)' }),
				Plot.areaY(pts, {
					x: 't',
					y1: 0.5,
					y2: (d) => Math.max(d.wp, 0.5),
					fill: hc,
					fillOpacity: 0.22,
					curve: 'step-after'
				}),
				Plot.areaY(pts, {
					x: 't',
					y1: 0.5,
					y2: (d) => Math.min(d.wp, 0.5),
					fill: ac,
					fillOpacity: 0.22,
					curve: 'step-after'
				}),
				Plot.ruleY([0.5], { stroke: 'var(--axis)', strokeWidth: 1.5 }),
				Plot.line(pts, {
					x: 't',
					y: 'wp',
					stroke: 'var(--text-primary)',
					strokeWidth: 2,
					curve: 'step-after'
				}),
				Plot.dot(marked, {
					x: (d: Marked) => d.t / 60,
					y: 'wp',
					r: 9,
					fill: 'var(--surface)',
					stroke: (d: Marked) => (d.home_wpa > 0 ? hc : ac),
					strokeWidth: 2.5
				}),
				Plot.text(marked, {
					x: (d: Marked) => d.t / 60,
					y: 'wp',
					text: 'n',
					fill: 'var(--text-primary)',
					fontWeight: 700,
					fontSize: 11
				}),
				Plot.tip(
					pts,
					Plot.pointerX({
						lineWidth: 40,
						x: 't',
						y: 'wp',
						title: (d: { t: number; wp: number }) =>
							`${Math.floor(d.t)}' elapsed\n${g.home} ${pct(d.wp, 0)} · ${g.away} ${pct(1 - d.wp, 0)}`
					})
				)
			]
		});
		const x = chart.scale('x');
		wpX = x?.apply ? (v: number) => x.apply!(v) as number : null;
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
		{ key: 'plays', label: 'Plays', fmt: (v) => num(v), better: 'high' },
		{ key: 'turnovers', label: 'Turnovers', fmt: (v) => num(v), better: 'low' }
	];
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
		const wk = Math.max(0, ...rs.map((r) => r.week));
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

{#if loading && !line}
	<Skeleton height={360} />
{:else if error}
	<LoadError message={error} />
{:else if !game && !line}
	<div class="callout">
		No game with id <code>{id}</code>. <a href="{base}/games/">Browse games</a>.
	</div>
{:else}
	<section class="scoreboard card">
		<div class="meta-line">
			<a href="{base}/games/?season={season}">{season}</a> ·
			{game?.season_type === 'POST' ? 'Playoffs' : `Week ${game?.week ?? line?.week}`}
			{#if game?.gameday ?? line?.gameday}· {game?.gameday ?? line?.gameday}{/if}
			{#if line?.neutral}· neutral site{/if}
		</div>
		<div class="teams">
			<div class="side" class:dim={played && homeWon}>
				<TeamBadge team={away} size="lg" link />
				<div>
					<div class="name">{teamName(away)}</div>
					<div class="muted small">Away</div>
				</div>
				{#if played}<div class="pts">{game?.away_score}</div>{/if}
			</div>
			<div class="vs">{played ? 'Final' : '@'}</div>
			<div class="side right" class:dim={played && !homeWon}>
				{#if played}<div class="pts">{game?.home_score}</div>{/if}
				<div>
					<div class="name">{teamName(home)}</div>
					<div class="muted small">Home</div>
				</div>
				<TeamBadge team={home} size="lg" link />
			</div>
		</div>
		{#if line}
			<div class="lines">
				<div><span class="k">Model</span> <b>{spread(line.model, line.home, line.away)}</b></div>
				<div><span class="k">Vegas</span> <b>{spread(line.vegas, line.home, line.away)}</b></div>
				<div>
					<span class="k">Model win prob</span>
					<b
						>{line.home_wp >= 0.5
							? `${line.home} ${pct(line.home_wp, 0)}`
							: `${line.away} ${pct(1 - line.home_wp, 0)}`}</b
					>
				</div>
				{#if played && line.vegas != null}
					{@const r = (game?.home_score ?? 0) - (game?.away_score ?? 0)}
					<div>
						<span class="k">Against the spread</span>
						<b
							>{r === line.vegas
								? 'Push'
								: (r > line.vegas ? line.home : line.away) + ' covered'}</b
						>
					</div>
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
					Total win-probability swing. More exciting than {Math.round(
						excitementPercentile(excitement(game)) * 100
					)}% of games since 2016.
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
				Shaded toward the team that was favored at that moment. Numbered circles mark the plays that
				moved it most (listed below). Win probability from the nflfastR model, which includes the
				pre-game Vegas line.
			</p>
			<div class="wp-wrap">
				<PlotFigure label="Win probability over the game" render={wpChart} />
				{#if markerX != null}
					<div class="wp-marker" style:left="{markerX}px" aria-hidden="true"></div>
				{/if}
			</div>
		</div>

		<div class="grid-2">
			<div class="card">
				<h2>Plays that decided it</h2>
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
			<div class="card">
				<h2>Box score, the efficient way</h2>
				<p class="sub">Scrimmage plays only. Bold = better side.</p>
				<table class="box">
					<thead>
						<tr><th></th><th><TeamBadge team={away} /></th><th><TeamBadge team={home} /></th></tr>
					</thead>
					<tbody>
						{#each boxRows as r (r.key)}
							<tr>
								<td>{r.label}</td>
								<td class:win={edge(r, 'away')}>{r.fmt(game.box.away?.[r.key] ?? null)}</td>
								<td class:win={edge(r, 'home')}>{r.fmt(game.box.home?.[r.key] ?? null)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		{#if plays}
			<GameFlow data={plays} {home} {away} onhover={(t) => (hoverT = t)} />
		{:else}
			<Skeleton height={200} />
		{/if}
	{:else}
		<div class="callout info">
			Not played yet. Here's how the two teams match up on the season so far.
		</div>
		<div class="grid-2">
			{#each [away, home] as t (t)}
				{@const r = latestRatings.get(t)}
				<div class="card">
					<div class="card-head">
						<h2><TeamBadge team={t} name link /></h2>
						{#if r}<span class="chip">#{r.rank} power</span>{/if}
					</div>
					{#if r}
						<div class="split">
							<div><span class="k">Net</span> <b>{signed(r.points)} pts</b></div>
							<div><span class="k">Offense</span> <b>{signed(r.off_points)}</b></div>
							<div><span class="k">Defense</span> <b>{signed(r.def_points)}</b></div>
						</div>
					{/if}
				</div>
			{/each}
		</div>
		<div class="grid-2">
			{#each matchups as m (m.label)}
				{@const o = unit.get(m.o)}
				{@const d = unit.get(m.d)}
				<div class="card">
					<h2>{m.label}</h2>
					<p class="sub">Season EPA/play, garbage time excluded, with league rank (1 = best).</p>
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
{/if}

<style>
	.wp-wrap {
		position: relative;
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
	.scoreboard {
		display: grid;
		gap: 0.9rem;
	}
	.meta-line {
		font-size: 0.85rem;
		color: var(--text-muted);
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
		font: 800 clamp(2rem, 1.4rem + 3vw, 3.25rem) / 1 var(--display);
		font-variant-numeric: tabular-nums;
		margin: 0 0.5rem;
	}
	.side:not(.right) .pts {
		margin-left: auto;
	}
	.side.right .pts {
		margin-right: auto;
	}
	.vs {
		font: 700 0.8rem var(--display);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-muted);
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
