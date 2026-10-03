<script lang="ts">
	import { ratingsWeek } from '$lib/season';
	import { base } from '$app/paths';
	import FavoriteCard from '$lib/components/FavoriteCard.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import Ticker, { type TickerItem } from '$lib/components/Ticker.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { epa, num, signed, spread, wlt } from '$lib/format';
	import { Plot, plotStyle } from '$lib/plot';
	import { loadPath } from '$lib/data';
	import { resource, seasonResource } from '$lib/resource.svelte';
	import { hasPlayerPage } from '$lib/playerPages.svelte';
	import {
		kickoffLabel,
		lastGame,
		nextGame,
		played,
		records,
		resultsWeek,
		upset,
		weekLabel
	} from '$lib/standings';
	import { favorite } from '$lib/favorite.svelte';
	import { heroColors, teamColor, teamMeta, teamName } from '$lib/teams.svelte';
	import type { GamePrediction, PlayoffOdds, QBGame, Rating, ScheduleGame } from '$lib/types';

	const meta = resource('meta');
	const up = resource('upcoming');

	const latest = $derived(meta.value?.seasons.at(-1));
	const season = $derived(latest?.season ?? 0);
	const inProgress = $derived(latest ? !latest.complete : false);
	const ratings = seasonResource<Rating>('ratings', () => season || null);
	const schedule = seasonResource<ScheduleGame>('schedule', () => season || null);
	const qbGames = seasonResource<QBGame>('qb_games', () => season || null);

	// Playoff odds: one small file per season (no `odds` for the first simulated season).
	let odds = $state.raw<PlayoffOdds | null>(null);
	$effect(() => {
		if (!season) return;
		loadPath<PlayoffOdds>(`playoff_odds/${season}`)
			.then((o) => (odds = o))
			.catch(() => (odds = null));
	});

	const games = $derived(schedule.value ?? []);
	const recs = $derived(records(games));
	const results = $derived(resultsWeek(games, latest));

	// Predictions (the site's forecast) for every coming game, by id.
	const preds = $derived(
		new Map<string, GamePrediction>(
			[...(up.value?.upcoming ?? []), ...(up.value?.next_games ?? [])].map((g) => [g.game_id, g])
		)
	);
	const test = $derived(up.value?.summary.find((s) => s.split === 'test'));

	// This week: every game of the next week with an unplayed game, Thursday finals included.
	const kick = (g: ScheduleGame) => `${g.gameday} ${g.gametime ?? ''}`;
	const thisWeek = $derived.by(() => {
		const open = games.filter((g) => !played(g));
		if (!open.length) return [];
		const first = [...open].sort((a, b) => kick(a).localeCompare(kick(b)))[0];
		return games
			.filter((g) => g.week === first.week && g.game_type === first.game_type)
			.sort((a, b) => kick(a).localeCompare(kick(b)) || a.home.localeCompare(b.home));
	});
	const slots = $derived.by(() => {
		const out: { label: string; games: ScheduleGame[] }[] = [];
		for (const g of thisWeek) {
			const label = played(g) ? 'Final' : kickoffLabel(g.gameday, g.gametime);
			const last = out.at(-1);
			if (last?.label === label) last.games.push(g);
			else out.push({ label, games: [g] });
		}
		return out;
	});
	const disagree = (p: GamePrediction | undefined) =>
		p && p.vegas != null ? Math.abs(p.model - p.vegas) : 0;

	// Results: the last full week, upsets first.
	const resultRows = $derived(
		[...(results?.games ?? [])].sort((a, b) => Number(upset(b)) - Number(upset(a)))
	);

	const ticker = $derived.by<TickerItem[]>(() => {
		const final = (g: ScheduleGame): TickerItem => {
			const homeWon = g.home_score! >= g.away_score!;
			const [w, l] = homeWon ? [g.home, g.away] : [g.away, g.home];
			const [ws, ls] = homeWon ? [g.home_score!, g.away_score!] : [g.away_score!, g.home_score!];
			const surprise = upset(g);
			return {
				key: g.game_id,
				href: `/game/?id=${g.game_id}`,
				tag: `${weekLabel(g)} ${surprise ? '· upset' : 'final'}`,
				text: `${w} ${ws}, ${l} ${ls}`,
				hot: surprise
			};
		};
		const later = games.filter((g) => played(g) && results && g.week > results.week);
		const lines = thisWeek
			.filter((g) => !played(g))
			.map<TickerItem>((g) => {
				const p = preds.get(g.game_id);
				const best = p?.blend_wp != null ? ` · ${favoredBy(p)}` : '';
				return {
					key: g.game_id,
					href: `/game/?id=${g.game_id}`,
					tag: `${weekLabel(g)} line`,
					text: `${g.away} ${g.neutral ? 'vs' : '@'} ${g.home} · ${spread(g.vegas, g.home, g.away)}${best}`
				};
			});
		return [...resultRows.map(final), ...later.map(final), ...lines];
	});

	/** "NYG 55%": the best estimate's favorite and its win chance. */
	function favoredBy(p: GamePrediction): string {
		const wp = p.blend_wp ?? p.home_wp;
		return wp >= 0.5 ? `${p.home} ${num(wp * 100)}%` : `${p.away} ${num((1 - wp) * 100)}%`;
	}
	function qbNote(p: GamePrediction): string | null {
		const sides = [
			[p.home, p.home_qb_pts, p.home_qb],
			[p.away, p.away_qb_pts, p.away_qb]
		] as const;
		const big = sides.filter(([, pts]) => Math.abs(pts) >= 1.5);
		return big.length
			? big
					.map(
						([t, pts, n]) =>
							`${t} QB ${n ?? 'change'}: ${signed(pts)} pts vs the QBs behind its rating`
					)
					.join(' · ')
			: null;
	}

	// Power ratings now and a week earlier.
	const seasonRatings = $derived((ratings.value ?? []).filter((r) => r.season === season));
	const lastWeek = $derived(
		ratingsWeek(
			seasonRatings.map((r) => r.week),
			latest
		)
	);
	const now = $derived(
		seasonRatings.filter((r) => r.week === lastWeek).sort((a, b) => a.rank - b.rank)
	);
	const ratingDelta = $derived.by(() => {
		const prev = new Map(
			seasonRatings.filter((r) => r.week === lastWeek - 1).map((r) => [r.team, r.points])
		);
		return new Map(
			now.filter((r) => prev.has(r.team)).map((r) => [r.team, r.points - prev.get(r.team)!])
		);
	});
	const movers = $derived(
		now
			.filter((r) => ratingDelta.has(r.team))
			.map((r) => ({ r, delta: ratingDelta.get(r.team)! }))
			.sort((a, b) => b.delta - a.delta)
	);

	// Playoff odds after the same week as everything else, and the week before.
	const oddsWeek = $derived(odds ? ratingsWeek(odds.weeks, latest) : 0);
	const oddsNow = $derived(odds?.rows.filter((r) => r.week === oddsWeek) ?? []);
	const oddsPrev = $derived(
		odds && oddsWeek > 0 ? odds.rows.filter((r) => r.week === oddsWeek - 1) : []
	);
	const oddsBy = $derived(new Map(oddsNow.map((r) => [r.team, r])));
	const prevBy = $derived(new Map(oddsPrev.map((r) => [r.team, r])));
	const favorites = $derived([...oddsNow].sort((a, b) => b.p_sb - a.p_sb).slice(0, 5));

	// Division standings: record, then division odds as the tiebreak stand-in.
	const standings = $derived.by(() => {
		const by = new Map<string, string[]>();
		for (const t of Object.values(teamMeta.byTeam)) {
			by.set(t.division, [...(by.get(t.division) ?? []), t.team]);
		}
		const pctOf = (t: string) => {
			const r = recs.get(t);
			return r && r.games ? r.wins / r.games : 0;
		};
		return [...by]
			.sort(([a], [b]) => a.localeCompare(b))
			.map(([division, teams]) => ({
				division,
				teams: teams.sort(
					(a, b) =>
						pctOf(b) - pctOf(a) ||
						(oddsBy.get(b)?.p_division ?? 0) - (oddsBy.get(a)?.p_division ?? 0)
				)
			}));
	});

	// Luck: wins vs what point differential predicts, from the same schedule.
	const luckRows = $derived(
		[...recs.values()]
			.map((r) => ({ ...r, over: r.wins - r.pythag }))
			.sort((a, b) => b.over - a.over)
	);

	// QBs: the best games of the results week, and season leaders (min ~12 dropbacks a game).
	const qbWeek = $derived(
		(qbGames.value ?? [])
			.filter((q) => results && q.week === results.week && q.dropbacks >= 15)
			.sort((a, b) => b.epa_db - a.epa_db)
			.slice(0, 5)
	);
	const qbLeaders = $derived.by(() => {
		const by = new Map<
			string,
			{ id: string; name: string; team: string; db: number; epa: number; games: number }
		>();
		for (const q of qbGames.value ?? []) {
			const r = by.get(q.player_id) ?? {
				id: q.player_id,
				name: q.name,
				team: q.team,
				db: 0,
				epa: 0,
				games: 0
			};
			r.db += q.dropbacks;
			r.epa += q.epa_db * q.dropbacks;
			r.games += 1;
			r.team = q.team;
			by.set(q.player_id, r);
		}
		// Weeks played (a Thursday game in the next week doesn't count), else the most games.
		const teamGames =
			latest && !latest.complete
				? Math.max(1, latest.last_week)
				: Math.max(1, ...[...recs.values()].map((r) => r.games));
		const min = 12 * teamGames;
		return [...by.values()]
			.filter((r) => r.db >= min)
			.map((r) => ({ ...r, epa: r.epa / r.db, min }))
			.sort((a, b) => b.epa - a.epa)
			.slice(0, 5);
	});
	const playerHref = (id: string) =>
		hasPlayerPage(id) ? `${base}/player/?id=${id}&season=${season}` : null;

	function powerChart(width: number) {
		const top = now.slice(0, 10);
		const narrow = width < 400;
		return Plot.plot({
			width,
			height: top.length * 30 + 10,
			style: plotStyle,
			marginLeft: narrow ? 46 : 150,
			marginRight: 52,
			x: { label: null, axis: null },
			y: {
				domain: top.map((r) => r.team),
				label: null,
				tickFormat: (t: string) => (narrow ? t : teamName(t)),
				tickSize: 0
			},
			marks: [
				Plot.barX(top, {
					y: 'team',
					x: 'points',
					fill: (d: Rating) => teamColor(d.team),
					rx: 4,
					insetTop: 5,
					insetBottom: 5
				}),
				Plot.text(top, {
					y: 'team',
					x: 'points',
					text: (d: Rating) => signed(d.points),
					textAnchor: 'start',
					dx: 6,
					fill: 'var(--text-primary)',
					fontWeight: 600
				}),
				Plot.tip(
					top,
					Plot.pointerY({
						lineWidth: 40,
						y: 'team',
						x: 'points',
						title: (d: Rating) =>
							`#${d.rank} ${teamName(d.team)}: ${signed(d.points)} pts vs average\nOffense ${signed(d.off_points)} · Defense ${signed(d.def_points)}`
					})
				)
			]
		});
	}
	const q = $derived(`season=${season}`);
	const weekNoun = $derived(results ? weekLabel(results.games[0]) : '');

	// Your team's colors light the hero (darkened so white text stays readable).
	const tint = $derived(heroColors(favorite.team));
	// The hero's looping animations pause while it's scrolled out of view.
	let heroEl = $state<HTMLElement>();
	let heroHidden = $state(false);
	$effect(() => {
		if (!heroEl) return;
		const io = new IntersectionObserver(([e]) => (heroHidden = !e.isIntersecting));
		io.observe(heroEl);
		return () => io.disconnect();
	});
</script>

<svelte:head><title>Any Given Stat · NFL analytics</title></svelte:head>

<section
	bind:this={heroEl}
	class="hero"
	class:paused={heroHidden}
	class:team-tint={!!tint}
	style:--hero-from={tint?.from}
	style:--hero-to={tint?.to}
>
	<div class="aurora" aria-hidden="true"><span></span><span></span><span></span></div>
	<div class="turf" aria-hidden="true"></div>
	<div class="eyebrow" style="color: rgba(255,255,255,0.75)">
		{season || ' '}
		{#if latest}· {inProgress ? `through week ${latest.last_week}` : 'final'}{/if}
	</div>
	<h1>Know which numbers <span class="glow">matter.</span></h1>
	<p class="lede">
		Every NFL play since 2016: opponent-adjusted ratings, win probability, forecasts scored honestly
		against Vegas, and which stats are signal.
	</p>
	<dl class="hero-stats">
		<div>
			<dt>Best team</dt>
			<dd>
				{#if now[0]}<a href="{base}/team/?t={now[0].team}&{q}">{now[0].team}</a>
					<span class="num">{signed(now[0].points)}</span>{:else}&nbsp;{/if}
			</dd>
		</div>
		<div>
			<dt>Super Bowl favorite</dt>
			<dd>
				{#if favorites[0]}<a href="{base}/odds/?{q}">{favorites[0].team}</a>
					<span class="num">{num(favorites[0].p_sb * 100)}%</span>{:else}&nbsp;{/if}
			</dd>
		</div>
		<div>
			<dt>{thisWeek[0] ? weekLabel(thisWeek[0]) : 'Next game'}</dt>
			<dd>
				{#if thisWeek.length}
					<a href="{base}/predictions/">{thisWeek.filter((g) => !played(g)).length} games</a>
				{:else if latest}Offseason{:else}&nbsp;{/if}
			</dd>
		</div>
	</dl>
	<svg class="ball" viewBox="0 0 160 100" aria-hidden="true">
		<path class="trail" d="M-70 70h70M-90 52h82M-60 34h58" />
		<path class="hide" d="M8 50C30 8 130 8 152 50 130 92 30 92 8 50Z" />
		<path class="seam" d="M30 26c8 16 8 32 0 48M130 26c-8 16-8 32 0 48" />
		<path class="lace" d="M55 50h50M62 43v14M72 43v14M82 43v14M92 43v14M100 44v12" />
	</svg>
</section>

<Ticker items={ticker} label="Latest scores and lines" />

<SampleWarning status={latest} />

<FavoriteCard
	{season}
	ratings={now}
	{ratingDelta}
	records={recs}
	odds={oddsNow}
	{oddsPrev}
	last={(t) => lastGame(games, t)}
	next={(t) => nextGame(games, t)}
	prediction={(id) => preds.get(id)}
/>

<div class="dash">
	<!-- This week -->
	<section class="card week" aria-labelledby="week-title">
		<div class="card-head">
			<h2 id="week-title">{thisWeek[0] ? weekLabel(thisWeek[0]) : 'This week'}</h2>
			<a href="{base}/predictions/">Forecast details →</a>
		</div>
		{#if thisWeek.length}
			<p class="sub">
				The boxed number is our <b>best estimate</b> of who wins: the model blended with the Vegas
				line, the most accurate forecast we have. <span class="badge-key">Δ</span> marks games where the
				model alone differs from Vegas by 3+ points.
			</p>
			<div class="slots">
				{#each slots as s, i (s.label + i)}
					<h3 class="slot">{s.label}</h3>
					<ul class="games">
						{#each s.games as g (g.game_id)}
							{@const p = preds.get(g.game_id)}
							{@const note = p ? qbNote(p) : null}
							<li>
								<a href="{base}/game/?id={g.game_id}">
									<span class="matchup">
										<TeamBadge team={g.away} />
										{#if played(g)}<b class="score">{g.away_score}</b>{/if}
										<span class="at">{g.neutral ? 'vs' : '@'}</span>
										<TeamBadge team={g.home} />
										{#if played(g)}<b class="score">{g.home_score}</b>{/if}
									</span>
									{#if !played(g)}
										<span class="lines">
											<span><span class="k">Vegas</span> {spread(g.vegas, g.home, g.away)}</span>
											{#if p}<span
													><span class="k">Model</span>
													{spread(p.model, p.home, p.away)}{#if disagree(p) >= 3}
														<span
															class="badge-key"
															title="Model differs from Vegas by {num(disagree(p), 1)} points"
															>Δ {num(disagree(p), 1)}</span
														>{/if}</span
												>{/if}
										</span>
										{#if p?.blend_wp != null}<span class="best" title="Best estimate"
												>{favoredBy(p)}</span
											>{/if}
									{:else}
										<span class="best final">Final</span>
									{/if}
									{#if note}<span class="qb">{note}</span>{/if}
								</a>
							</li>
						{/each}
					</ul>
				{/each}
			</div>
			{#if test}
				<p class="foot-note">
					On held-out test seasons the model misses by {num(test.model_mae, 1)} points a game; Vegas by
					{num(test.vegas_mae, 1)}. The blend is what we trust.
				</p>
			{/if}
		{:else if schedule.value && latest}
			<p class="muted">
				No games left on the {season} schedule. See how the season ended in the
				<a href="{base}/records/">record book</a> and how the forecasts did on
				<a href="{base}/predictions/">Predictions</a>.
			</p>
		{:else}
			<div class="skeleton" style="height: 520px"></div>
		{/if}
	</section>

	<div class="rail">
		<!-- Results -->
		<section class="card results" aria-labelledby="results-title">
			<div class="card-head">
				<h2 id="results-title">{weekNoun ? `${weekNoun} results` : 'Results'}</h2>
				<a href="{base}/games/?{q}{results ? `&week=${results.week}` : ''}">Game charts →</a>
			</div>
			{#if resultRows.length}
				<p class="sub">Upsets (the Vegas underdog won) first.</p>
				<ul class="scores">
					{#each resultRows as g (g.game_id)}
						{@const homeWon = g.home_score! > g.away_score!}
						<li>
							<a href="{base}/game/?id={g.game_id}">
								<span class="side" class:won={!homeWon && g.home_score !== g.away_score}>
									<TeamBadge team={g.away} /><b>{g.away_score}</b>
								</span>
								<span class="side" class:won={homeWon}>
									<TeamBadge team={g.home} /><b>{g.home_score}</b>
								</span>
								{#if upset(g)}<span class="chip upset">Upset</span>{/if}
							</a>
						</li>
					{/each}
				</ul>
			{:else if schedule.value}
				<p class="muted">No games played yet this season.</p>
			{:else}
				<div class="skeleton" style="height: 520px"></div>
			{/if}
		</section>

		<!-- QBs of the week -->
		<section class="card qbs" aria-labelledby="qbweek-title">
			<div class="card-head">
				<h2 id="qbweek-title">{weekNoun ? `${weekNoun}'s best QB games` : 'Best QB games'}</h2>
				<a href="{base}/qbs/?{q}">All QBs →</a>
			</div>
			<p class="sub">EPA per dropback, min 15 dropbacks.</p>
			{#if qbWeek.length}
				<ol class="list ranked">
					{#each qbWeek as g (g.game_id + g.player_id)}
						{@const href = playerHref(g.player_id)}
						<li>
							<span class="who">
								{#if href}<a class="qb-name" {href}>{g.name}</a>{:else}<span class="qb-name"
										>{g.name}</span
									>{/if}
								<a class="muted small" href="{base}/game/?id={g.game_id}"
									>{g.game_id.endsWith(`_${g.team}`) ? 'vs' : '@'} {g.opp}</a
								>
							</span>
							<span class="muted small tnum"
								>{num(g.pass_yards)} yds · {g.tds} TD · {g.ints} INT</span
							>
							<span class="tnum strong">{epa(g.epa_db, 2)}</span>
						</li>
					{/each}
				</ol>
			{:else if qbGames.value}
				<p class="muted">No QB games yet.</p>
			{:else}
				<div class="skeleton" style="height: 220px"></div>
			{/if}
		</section>

		<!-- QB leaders -->
		<section class="card qbs" aria-labelledby="qblead-title">
			<div class="card-head">
				<h2 id="qblead-title">QB efficiency leaders</h2>
				<a href="{base}/qbs/?{q}">With intervals →</a>
			</div>
			<p class="sub">
				Season EPA per dropback{qbLeaders[0] ? `, min ${qbLeaders[0].min} dropbacks` : ''}. The QBs
				page adds confidence intervals and strips garbage time.
			</p>
			{#if qbLeaders.length}
				<ol class="list ranked">
					{#each qbLeaders as r (r.id)}
						{@const href = playerHref(r.id)}
						<li>
							<span class="who">
								{#if href}<a class="qb-name" {href}>{r.name}</a>{:else}<span class="qb-name"
										>{r.name}</span
									>{/if}
								<TeamBadge team={r.team} link {season} />
							</span>
							<span class="muted small tnum">{num(r.db)} dropbacks</span>
							<span class="tnum strong">{epa(r.epa, 2)}</span>
						</li>
					{/each}
				</ol>
			{:else if qbGames.value}
				<p class="muted">Leaders show once QBs reach the dropback minimum.</p>
			{:else}
				<div class="skeleton" style="height: 220px"></div>
			{/if}
		</section>
	</div>
	<!-- Standings + playoff odds -->
	<section class="card standings" aria-labelledby="standings-title">
		<div class="card-head">
			<h2 id="standings-title">Standings and playoff odds</h2>
			<a href="{base}/odds/?{q}">Playoff odds →</a>
		</div>
		<p class="sub">
			Playoff chances from 10,000 simulated seasons{oddsWeek ? ` after week ${oddsWeek}` : ''}, with
			the change since the week before.
			{#if favorites.length}
				Super Bowl favorites:
				{#each favorites as f, i (f.team)}<a href="{base}/team/?t={f.team}&{q}">{f.team}</a>
					{num(f.p_sb * 100)}%{i < favorites.length - 1 ? ', ' : '.'}
				{/each}
			{/if}
		</p>
		{#if schedule.value && standings.length}
			<div class="divisions">
				{#each standings as d (d.division)}
					<table>
						<caption>{d.division}</caption>
						<thead>
							<tr>
								<th scope="col">Team</th>
								<th scope="col" class="r">Record</th>
								<th scope="col" class="r"
									><abbr title="Chance to make the playoffs">Playoffs</abbr></th
								>
								<th scope="col" class="r"
									><abbr title="Change since last week, in points">±</abbr></th
								>
							</tr>
						</thead>
						<tbody>
							{#each d.teams as t (t)}
								{@const r = recs.get(t)}
								{@const o = oddsBy.get(t)}
								{@const pr = prevBy.get(t)}
								{@const delta = o && pr ? (o.p_playoffs - pr.p_playoffs) * 100 : null}
								<tr class:fav={favorite.team === t}>
									<th scope="row"><TeamBadge team={t} name="nick" link {season} /></th>
									<td class="r tnum">{r ? wlt(r.wins, r.games) : '0–0'}</td>
									<td class="r tnum strong">{o ? `${num(o.p_playoffs * 100)}%` : '–'}</td>
									<td
										class="r tnum delta"
										class:up={delta != null && delta >= 1}
										class:down={delta != null && delta <= -1}
									>
										{delta == null ? '' : Math.abs(delta) < 1 ? '·' : signed(delta, 0)}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/each}
			</div>
		{:else}
			<div class="skeleton" style="height: 420px"></div>
		{/if}
	</section>

	<!-- Power ratings -->
	<section class="card power" aria-labelledby="power-title">
		<div class="card-head">
			<h2 id="power-title">Power ratings: top 10</h2>
			<a href="{base}/ratings/?{q}">All 32 →</a>
		</div>
		<p class="sub">
			Points better than an average team on a neutral field{lastWeek
				? `, after week ${lastWeek}`
				: ''}.
		</p>
		{#if now.length}
			<PlotFigure label="Top 10 power ratings" render={powerChart} />
		{:else}
			<div class="skeleton" style="height: 310px"></div>
		{/if}
	</section>

	<!-- Movers -->
	<section class="card movers" aria-labelledby="movers-title">
		<div class="card-head">
			<h2 id="movers-title">Biggest movers</h2>
			<a href="{base}/ratings/?{q}">Trajectories →</a>
		</div>
		<p class="sub">Change in power rating over the last week, in points.</p>
		{#if movers.length}
			<ul class="list">
				{#each [...movers.slice(0, 3), ...movers.slice(-3)] as m (m.r.team)}
					<li>
						<TeamBadge team={m.r.team} name="nick" link {season} />
						<span class="chip {m.delta >= 0 ? 'good' : 'bad'}"
							>{m.delta >= 0 ? '▲' : '▼'} {signed(m.delta)}</span
						>
					</li>
				{/each}
			</ul>
		{:else if ratings.value}
			<p class="muted">Movement shows after the second week of ratings.</p>
		{:else}
			<div class="skeleton" style="height: 240px"></div>
		{/if}
	</section>

	<!-- Luck -->
	<section class="card luck" aria-labelledby="luck-title">
		<div class="card-head">
			<h2 id="luck-title">Regression watch</h2>
			<a href="{base}/luck/?{q}">Luck →</a>
		</div>
		<p class="sub">Wins minus the wins their point differential predicts (Pythagorean).</p>
		{#if luckRows.length}
			<ul class="list">
				{#each [...luckRows.slice(0, 3), ...luckRows.slice(-3)] as l (l.team)}
					<li>
						<TeamBadge team={l.team} name="nick" link {season} />
						<span class="tnum muted">{wlt(l.wins, l.games)}</span>
						<span class="chip neutral tnum">{signed(l.over)} W</span>
					</li>
				{/each}
			</ul>
			<p class="foot-note">
				Plus = more wins than their points earned; history says those gaps close.
				{#if inProgress && latest && latest.last_week < 6}
					After {latest.last_week} weeks, one bounce decides most of this.
				{/if}
			</p>
		{:else if schedule.value}
			<p class="muted">Shows once games are played.</p>
		{:else}
			<div class="skeleton" style="height: 240px"></div>
		{/if}
	</section>
</div>

<style>
	/* ---------- Hero: a stadium under the lights ---------- */
	.hero {
		padding-bottom: clamp(1.25rem, 1rem + 2vw, 2.25rem);
		background:
			radial-gradient(120% 90% at 85% -10%, rgba(255, 255, 255, 0.16), transparent 55%),
			linear-gradient(135deg, var(--hero-from), var(--hero-to));
		box-shadow:
			0 30px 60px -30px color-mix(in srgb, var(--hero-to) 70%, transparent),
			var(--shadow-md);
		transition: background 0.6s var(--ease);
	}
	.hero > :not(.aurora):not(.turf):not(.ball) {
		position: relative;
		z-index: 2;
	}
	.hero h1 {
		font-size: clamp(2rem, 1.3rem + 3vw, 3.4rem);
		font-stretch: 118%;
		line-height: 1.02;
		max-width: 16ch;
		margin-bottom: 0.6rem;
		text-shadow: 0 2px 30px rgba(0, 0, 0, 0.25);
	}
	.hero .lede {
		max-width: 58ch;
	}
	/* Gradient text (light end stays ≥ 7:1 against the dark hero). */
	.glow {
		background: linear-gradient(100deg, #ffffff 10%, #a5f3fc 55%, #c4b5fd 95%);
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
		background-size: 200% 100%;
		animation: glow-pan 8s ease-in-out infinite alternate;
	}
	@keyframes glow-pan {
		to {
			background-position: 100% 0;
		}
	}
	/* Aurora: three blurred lights drifting over the gradient. */
	.aurora {
		position: absolute;
		inset: 0;
		z-index: 0;
		overflow: hidden;
		pointer-events: none;
	}
	.aurora span {
		position: absolute;
		width: 46%;
		aspect-ratio: 1;
		border-radius: 50%;
		filter: blur(60px);
		opacity: 0.55;
		mix-blend-mode: screen;
	}
	.aurora span:nth-child(1) {
		left: -8%;
		top: -30%;
		background: radial-gradient(circle, #22d3ee, transparent 65%);
		animation: drift-a 19s ease-in-out infinite alternate;
	}
	.aurora span:nth-child(2) {
		right: -6%;
		top: -20%;
		background: radial-gradient(circle, #8b5cf6, transparent 65%);
		animation: drift-b 23s ease-in-out infinite alternate;
	}
	.aurora span:nth-child(3) {
		left: 30%;
		bottom: -45%;
		background: radial-gradient(circle, #3b82f6, transparent 65%);
		animation: drift-c 27s ease-in-out infinite alternate;
	}
	.team-tint .aurora span {
		opacity: 0.32;
	}
	@keyframes drift-a {
		to {
			transform: translate(35%, 25%) scale(1.2);
		}
	}
	@keyframes drift-b {
		to {
			transform: translate(-30%, 35%) scale(0.9);
		}
	}
	@keyframes drift-c {
		to {
			transform: translate(20%, -25%) scale(1.15);
		}
	}
	/* The field: yard lines in perspective, receding to the horizon and rolling toward you. */
	.turf {
		position: absolute;
		left: -30%;
		right: -30%;
		bottom: -2px;
		height: 78%;
		z-index: 1;
		pointer-events: none;
		background:
			repeating-linear-gradient(0deg, rgba(255, 255, 255, 0.34) 0 2px, transparent 2px 64px),
			repeating-linear-gradient(
				90deg,
				transparent 0 calc(5% - 1px),
				rgba(255, 255, 255, 0.13) calc(5% - 1px) 5%
			);
		transform: perspective(520px) rotateX(64deg);
		transform-origin: 50% 100%;
		mask-image: linear-gradient(to top, #000 0%, rgba(0, 0, 0, 0.55) 40%, transparent 75%);
		-webkit-mask-image: linear-gradient(to top, #000 0%, rgba(0, 0, 0, 0.55) 40%, transparent 75%);
		animation: roll 5s linear infinite;
	}
	@keyframes roll {
		to {
			background-position:
				0 64px,
				0 0;
		}
	}
	.hero-stats {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 2.25rem;
		margin: 1.1rem 0 0;
	}
	.hero-stats dt {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: rgba(255, 255, 255, 0.78);
	}
	.hero-stats dd {
		margin: 0;
		font: 800 clamp(1.25rem, 1.05rem + 1vw, 1.8rem) / 1.15 var(--display);
		min-height: 1.15em;
	}
	.hero-stats a {
		color: #fff;
		text-decoration: none;
		border-bottom: 2px solid rgba(255, 255, 255, 0.35);
	}
	.hero-stats a:hover {
		border-bottom-color: #fff;
	}
	.hero-stats .num {
		font-variant-numeric: tabular-nums;
		font-weight: 700;
		opacity: 0.92;
	}
	/* A football drifting across the field behind the copy. */
	.ball {
		position: absolute;
		right: 7%;
		top: 16%;
		z-index: 1;
		width: clamp(110px, 14vw, 180px);
		overflow: visible;
		transform: rotate(-28deg);
		animation: spiral 7s ease-in-out infinite;
		pointer-events: none;
		filter: drop-shadow(0 22px 26px rgba(0, 0, 0, 0.3))
			drop-shadow(0 0 30px rgba(165, 243, 252, 0.25));
	}
	.ball .trail {
		fill: none;
		stroke: rgba(255, 255, 255, 0.35);
		stroke-width: 2.5;
		stroke-linecap: round;
		stroke-dasharray: 40 200;
		animation: streak 1.8s linear infinite;
	}
	@keyframes streak {
		to {
			stroke-dashoffset: -240;
		}
	}
	.ball .hide {
		fill: rgba(255, 255, 255, 0.1);
		stroke: rgba(255, 255, 255, 0.45);
		stroke-width: 2.5;
	}
	.ball .seam {
		fill: none;
		stroke: rgba(255, 255, 255, 0.3);
		stroke-width: 3;
	}
	.ball .lace {
		fill: none;
		stroke: rgba(255, 255, 255, 0.7);
		stroke-width: 3;
		stroke-linecap: round;
	}
	@keyframes spiral {
		50% {
			transform: translate(-18px, 10px) rotate(-20deg);
		}
	}
	@media (max-width: 800px) {
		.ball {
			display: none;
		}
	}
	@media (max-width: 560px) {
		.hero .lede {
			font-size: 0.95rem;
		}
		.hero-stats {
			gap: 0.4rem 1.25rem;
		}
	}
	.hero.paused :global(*),
	.hero.paused::before {
		animation-play-state: paused !important;
	}
	@media (prefers-reduced-motion: reduce) {
		.aurora span,
		.turf,
		.glow,
		.ball .trail {
			animation: none;
		}
	}

	/* ---------- Dashboard ---------- */
	.dash {
		display: grid;
		gap: 1rem;
		grid-template-columns: repeat(12, minmax(0, 1fr));
	}
	.week {
		grid-column: span 7;
	}
	.rail {
		grid-column: span 5;
		display: grid;
		gap: 1rem;
		align-content: start;
	}
	.standings {
		grid-column: span 12;
	}
	.power {
		grid-column: span 6;
	}
	.movers,
	.luck {
		grid-column: span 3;
	}
	@media (max-width: 1100px) {
		.week,
		.power {
			grid-column: span 12;
		}
		.rail {
			grid-column: span 12;
			grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr));
		}
		.rail .results {
			grid-column: 1 / -1;
		}
		.movers,
		.luck {
			grid-column: span 6;
		}
	}
	@media (max-width: 760px) {
		.movers,
		.luck {
			grid-column: span 12;
		}
	}
	.card-head a {
		font-size: 0.85rem;
		white-space: nowrap;
	}
	.foot-note {
		font-size: 0.8rem;
		color: var(--text-muted);
		margin: 0.6rem 0 0;
	}

	/* This week */
	.slot {
		margin: 0.7rem 0 0.3rem;
		font: 700 0.72rem/1 var(--sans, inherit);
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-secondary);
	}
	.slots > .slot:first-child {
		margin-top: 0.2rem;
	}
	.games {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.3rem;
	}
	.games a {
		display: grid;
		grid-template-columns: auto 1fr auto;
		grid-template-areas: 'm l b' 'q q q';
		align-items: center;
		gap: 0.15rem 0.9rem;
		padding: 0.45rem 0.7rem;
		border-radius: 10px;
		border: 1px solid var(--border);
		color: inherit;
		text-decoration: none;
		transition:
			background 0.15s,
			border-color 0.15s;
	}
	.games a:hover {
		background: var(--surface-2);
		border-color: var(--border-strong);
	}
	.matchup {
		grid-area: m;
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.score {
		font-variant-numeric: tabular-nums;
		min-width: 1.4em;
	}
	.at {
		color: var(--text-muted);
		font-size: 0.8rem;
	}
	.lines {
		grid-area: l;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.2rem 0.9rem;
		justify-content: flex-end;
		font-size: 0.84rem;
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}
	.best {
		grid-area: b;
		justify-self: end;
		font-size: 0.84rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		min-width: 5.2rem;
		text-align: center;
		padding: 0.1rem 0.45rem;
		border-radius: 6px;
		background: var(--surface-2);
		border: 1px solid var(--border);
	}
	.k {
		font-weight: 500;
		color: var(--text-muted);
		margin-right: 0.2rem;
	}
	.badge-key {
		display: inline-block;
		padding: 0 0.35rem;
		margin-left: 0.25rem;
		border-radius: 5px;
		border: 1px solid var(--fav);
		font-size: 0.74rem;
		font-weight: 700;
		color: var(--text-primary);
	}
	.best.final {
		font-weight: 500;
		color: var(--text-secondary);
		background: none;
		border-color: transparent;
	}
	.qb {
		grid-area: q;
		font-size: 0.76rem;
		color: var(--text-secondary);
	}
	@media (max-width: 520px) {
		.games a {
			grid-template-columns: 1fr auto;
			grid-template-areas: 'm b' 'l l' 'q q';
		}
		.lines {
			justify-content: flex-start;
			font-size: 0.8rem;
		}
	}

	/* Results */
	.scores {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 190px), 1fr));
		gap: 0.8rem 0.5rem;
		padding-top: 0.3rem;
	}
	.scores a {
		position: relative;
		display: grid;
		gap: 0.15rem;
		padding: 0.45rem 0.65rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		color: inherit;
		text-decoration: none;
	}
	.scores a:hover {
		background: var(--surface-2);
		border-color: var(--border-strong);
	}
	.side {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		color: var(--text-secondary);
		font-variant-numeric: tabular-nums;
	}
	.side.won {
		color: var(--text-primary);
	}
	.side.won b::after {
		content: ' ◂';
		font-size: 0.7em;
	}
	.chip.upset {
		position: absolute;
		top: -0.55rem;
		left: 0.6rem;
		padding: 0 0.4rem;
		font-size: 0.66rem;
		line-height: 1.5;
		border: 1px solid var(--fav);
		background: var(--surface);
	}

	/* Standings */
	.divisions {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.9rem 1.2rem;
	}
	.divisions table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.86rem;
	}
	.divisions caption {
		text-align: left;
		font: 700 0.72rem/1 inherit;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-secondary);
		padding-bottom: 0.35rem;
	}
	.divisions thead th {
		font-size: 0.7rem;
		font-weight: 600;
		color: var(--text-muted);
		text-align: left;
		padding: 0 0 0.2rem;
	}
	.divisions abbr {
		text-decoration: none;
	}
	.divisions tbody th,
	.divisions td {
		padding: 0.28rem 0;
		border-top: 1px solid var(--grid);
		font-weight: 400;
		text-align: left;
	}
	.divisions .r {
		text-align: right;
		padding-left: 0.5rem;
	}
	.divisions tr.fav th {
		box-shadow: inset 3px 0 0 var(--fav);
		padding-left: 0.4rem;
	}
	.delta {
		width: 3.1rem;
		white-space: nowrap;
		font-size: 0.78rem;
		color: var(--text-muted);
	}
	.delta.up,
	.delta.down {
		color: var(--text-primary);
		font-weight: 600;
	}
	.delta.up::before {
		content: '▲ ';
		font-size: 0.65em;
		color: var(--good);
	}
	.delta.down::before {
		content: '▼ ';
		font-size: 0.65em;
		color: var(--bad);
	}
	@media (max-width: 1100px) {
		.divisions {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (max-width: 560px) {
		.divisions {
			grid-template-columns: 1fr;
		}
	}

	/* Lists */
	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.15rem;
	}
	.list li {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.4rem 0;
		border-bottom: 1px solid var(--grid);
		font-size: 0.9rem;
	}
	.list li:last-child {
		border-bottom: 0;
	}
	.list li > :first-child {
		flex: 1;
		min-width: 0;
	}
	.ranked {
		counter-reset: rank;
	}
	.ranked li::before {
		counter-increment: rank;
		content: counter(rank);
		width: 1.2rem;
		font-weight: 700;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.ranked li > .who {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.chip.neutral {
		background: var(--surface-2);
		border: 1px solid var(--border);
	}
	.qb-name {
		color: inherit;
		font-weight: 600;
		text-decoration: none;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	a.qb-name:hover {
		text-decoration: underline;
	}
	.strong {
		font-weight: 700;
	}
	.small {
		font-size: 0.78rem;
	}
</style>
