<script lang="ts">
	import { ratingsWeek } from '$lib/season';
	import { base } from '$app/paths';
	import FavoriteCard from '$lib/components/FavoriteCard.svelte';
	import HomeHero, { type HeroStat } from '$lib/components/HomeHero.svelte';
	import WeekBoard from '$lib/components/WeekBoard.svelte';
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
	const highlight = resource('highlight');
	const heroStats = $derived<HeroStat[]>([
		now[0]
			? {
					label: 'Best team',
					value: now[0].team,
					figure: signed(now[0].points),
					href: `/team/?t=${now[0].team}&${q}`
				}
			: { label: 'Best team', value: '–' },
		favorites[0]
			? {
					label: 'Super Bowl favorite',
					value: favorites[0].team,
					figure: `${num(favorites[0].p_sb * 100)}%`,
					href: `/odds/?${q}`
				}
			: { label: 'Super Bowl favorite', value: '–' },
		thisWeek.length
			? {
					label: weekLabel(thisWeek[0]),
					value: `${thisWeek.filter((g) => !played(g)).length} games`,
					href: '/predictions/'
				}
			: { label: 'Next game', value: latest ? 'Offseason' : '–' }
	]);
</script>

<svelte:head><title>Any Given Stat · NFL analytics</title></svelte:head>

<HomeHero
	eyebrow={season
		? `${season} · ${inProgress ? `through week ${latest?.last_week}` : 'final'}`
		: ' '}
	highlight={highlight.value}
	stats={heroStats}
	{tint}
/>

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
			<WeekBoard games={thisWeek} predictions={preds} />
			{#if test}
				<p class="foot-note">
					On held-out test seasons the model misses by {num(test.model_mae, 1)} points a game and Vegas
					by {num(test.vegas_mae, 1)}; the blend ties Vegas. Nothing here beats the line.
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
						{@const surprise = upset(g)}
						{@const line = g.vegas == null ? null : Math.abs(g.vegas)}
						<li>
							<a href="{base}/game/?id={g.game_id}" class:upset={surprise}>
								<span class="side" class:won={!homeWon && g.home_score !== g.away_score}>
									<TeamBadge team={g.away} /><b>{g.away_score}</b>
								</span>
								<span class="side" class:won={homeWon}>
									<TeamBadge team={g.home} /><b>{g.home_score}</b>
								</span>
								<span class="note">
									{#if surprise}
										<svg viewBox="0 0 16 16" aria-hidden="true"
											><path d="M9.2 1 3 9.1h4.3L6.4 15l6.6-8.6H8.6z" /></svg
										>
										<span
											title={line != null ? `Won as a ${num(line, 1)}-point underdog` : undefined}
											><b>Upset</b>{#if line != null}
												{` · +${num(line, 1)}`}<span class="sr-only">-point underdog</span
												>{/if}</span
										>
									{:else if line != null && line > 0}
										<span>Favorite by {num(line, 1)} won</span>
									{:else}
										<span>Pick'em</span>
									{/if}
								</span>
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
	/* ---------- Dashboard ---------- */
	.dash {
		display: grid;
		gap: 1rem;
		grid-template-columns: repeat(12, minmax(0, 1fr));
	}
	.week {
		grid-column: span 7;
		align-self: start;
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

	/* Results */
	.scores {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 150px), 1fr));
		gap: 0.5rem;
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
	/* The card's footer says how the result relates to the line; an upset gets a gold edge and
	   a bolt, built into the card rather than stuck on it. */
	.note {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		margin-top: 0.2rem;
		padding-top: 0.3rem;
		border-top: 1px solid var(--grid);
		font-size: 0.72rem;
		color: var(--text-muted);
	}
	.scores a.upset {
		border-color: color-mix(in srgb, var(--fav) 55%, var(--border));
		box-shadow: inset 3px 0 0 var(--fav);
	}
	.upset .note {
		color: var(--text-secondary);
	}
	.upset .note b {
		color: var(--text-primary);
		letter-spacing: 0.02em;
	}
	.note svg {
		width: 0.85rem;
		height: 0.85rem;
		flex: none;
		fill: var(--fav);
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
