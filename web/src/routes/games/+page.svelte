<script lang="ts">
	import { base } from '$app/paths';
	import { afterNavigate } from '$app/navigation';
	import { setParam } from '$lib/url';
	import { page } from '$app/state';
	import Controls from '$lib/components/Controls.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { pct, spread } from '$lib/format';
	import {
		excitement,
		excitementPercentile,
		loadSeasonGames,
		sparkPath,
		winnerLow
	} from '$lib/games';
	import { prefs } from '$lib/prefs.svelte';
	import { resource } from '$lib/resource.svelte';
	import { teamColor } from '$lib/teams.svelte';
	import type { GameDetail } from '$lib/types';

	const meta = resource('meta');
	const preds = resource('upcoming');
	let games = $state.raw<GameDetail[] | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		const season = prefs.season;
		if (season == null) return;
		games = null;
		error = null;
		loadSeasonGames(season)
			.then((g) => {
				if (prefs.season === season) games = g;
			})
			.catch((e) => {
				error = String(e.message ?? e);
			});
	});

	type Row = GameDetail & { excite: number; low: number | null; label: string };
	const rows = $derived<Row[]>(
		(games ?? []).map((g) => ({
			...g,
			excite: excitement(g),
			low: winnerLow(g),
			label: g.season_type === 'POST' ? 'Playoffs' : `Week ${g.week}`
		}))
	);
	// Games not played yet this week come from the forecast (line, model, kickoff date).
	const upcoming = $derived((preds.value?.upcoming ?? []).filter((u) => u.season === prefs.season));
	const weeks = $derived([
		...new Set([...rows.map((r) => r.label), ...upcoming.map((u) => `Week ${u.week}`)])
	]);
	const shownUpcoming = $derived(upcoming.filter((u) => `Week ${u.week}` === week));
	// The week lives in the URL (?week=4, ?week=post) so a week's scores can be linked. By
	// default: the last fully played week while a season is on, else the last week.
	const status = $derived(meta.value?.seasons.find((s) => s.season === prefs.season));
	const defaultWeek = $derived(
		status && !status.complete && weeks.includes(`Week ${status.last_week}`)
			? `Week ${status.last_week}`
			: (weeks.at(-1) ?? '')
	);
	// The URL's week on arrival (and on back/forward); a click sets `picked` and rewrites the
	// address bar in place, since page.url doesn't follow shallow updates (see $lib/url).
	const urlWeek = $derived(page.url.searchParams.get('week'));
	let picked = $state<string | null>(null);
	afterNavigate(() => (picked = null));
	const week = $derived.by(() => {
		const fromUrl = urlWeek === 'post' ? 'Playoffs' : urlWeek ? `Week ${urlWeek}` : null;
		for (const w of [picked, fromUrl]) if (w && weeks.includes(w)) return w;
		return defaultWeek;
	});
	function pickWeek(w: string) {
		picked = w;
		setParam('week', w === 'Playoffs' ? 'post' : w.replace('Week ', ''));
	}
	const shown = $derived(rows.filter((r) => r.label === week));
	const best = $derived([...rows].sort((a, b) => b.excite - a.excite).slice(0, 8));
	const comebacks = $derived(
		rows
			.filter((r) => r.low != null)
			.sort((a, b) => a.low! - b.low!)
			.slice(0, 6)
	);
	// Excitement = total win-probability movement. Median game ≈ 3.7; top 10% ≥ 5.8.
	const thrill = (x: number) => {
		const p = excitementPercentile(x);
		return p >= 0.9 ? 'Thriller' : p >= 0.75 ? 'Back and forth' : null;
	};
	const SW = 120;
	const SH = 34;
</script>

<svelte:head><title>Games {prefs.season} · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Games</div>
	<h1>Scores & game charts</h1>
	<p class="lede">
		Every game's win probability, play by play. Each card's line is the home team's chance to win;
		the more it swings, the higher the excitement index.
	</p>
</section>

{#if meta.value}<Controls seasons={meta.value.seasons} showScope={false} />{/if}

{#if error}
	<LoadError message={error} />
{:else if !games}
	<Skeleton height={300} />
{:else}
	<div class="weeks" role="tablist" aria-label="Week">
		{#each weeks as w (w)}
			<button
				role="tab"
				aria-selected={w === week}
				class:on={w === week}
				onclick={() => pickWeek(w)}>{w.replace('Week ', 'Wk ')}</button
			>
		{/each}
	</div>

	<div class="cards">
		{#each shown as g (g.game_id)}
			{@const homeWon = (g.home_score ?? 0) > (g.away_score ?? 0)}
			{@const tag = thrill(g.excite)}
			<a class="card game interactive" href="{base}/game/?id={g.game_id}">
				<div class="row" class:lost={homeWon}>
					<TeamBadge team={g.away} name="nick" />
					<span class="score">{g.away_score}</span>
				</div>
				<div class="row" class:lost={!homeWon}>
					<TeamBadge team={g.home} name="nick" />
					<span class="score">{g.home_score}</span>
				</div>
				<svg class="spark" viewBox="0 0 {SW} {SH}" preserveAspectRatio="none" aria-hidden="true">
					<line x1="0" x2={SW} y1={SH / 2} y2={SH / 2} class="mid" />
					<path d={sparkPath(g, SW, SH)} stroke={teamColor(g.home)} />
				</svg>
				<div class="foot">
					<span>{g.gameday ?? ''}</span>
					{#if tag}<span class="chip good">{tag}</span>{/if}
				</div>
			</a>
		{/each}
		{#each shownUpcoming as u (u.game_id)}
			{@const wp = u.blend_wp ?? u.home_wp}
			<a class="card game interactive upcoming" href="{base}/game/?id={u.game_id}">
				<div class="row"><TeamBadge team={u.away} name="nick" /></div>
				<div class="row"><TeamBadge team={u.home} name="nick" /></div>
				<div class="preview">
					<span><span class="k">Vegas</span> {spread(u.vegas, u.home, u.away)}</span>
					<span><span class="k">Model</span> {spread(u.model, u.home, u.away)}</span>
					<span title="Our model blended with the Vegas line"
						><span class="k">Best estimate</span>
						{wp >= 0.5 ? u.home : u.away}
						{pct(wp >= 0.5 ? wp : 1 - wp, 0)}</span
					>
				</div>
				<div class="foot">
					<span>{u.gameday}</span>
					<span class="chip">Upcoming</span>
				</div>
			</a>
		{/each}
	</div>

	<div class="grid-2">
		<div class="card">
			<h2>Most exciting games of {prefs.season}</h2>
			<p class="sub">Ranked by total win-probability movement (median game ≈ 3.7).</p>
			<ol class="rank">
				{#each best as g (g.game_id)}
					<li>
						<a href="{base}/game/?id={g.game_id}">
							<span class="who"
								><TeamBadge team={g.away} />
								{g.away_score}–{g.home_score}
								<TeamBadge team={g.home} /></span
							>
							<span class="muted">{g.label}</span>
							<span class="tnum strong">{g.excite.toFixed(1)}</span>
						</a>
					</li>
				{/each}
			</ol>
		</div>
		<div class="card">
			<h2>Biggest comebacks</h2>
			<p class="sub">The winner's lowest win probability during the game.</p>
			<ol class="rank">
				{#each comebacks as g (g.game_id)}
					<li>
						<a href="{base}/game/?id={g.game_id}">
							<span class="who"
								><TeamBadge team={g.away} />
								{g.away_score}–{g.home_score}
								<TeamBadge team={g.home} /></span
							>
							<span class="muted">{g.label}</span>
							<span class="tnum strong">{pct(g.low, 1)}</span>
						</a>
					</li>
				{/each}
			</ol>
		</div>
	</div>
{/if}

<style>
	.weeks {
		display: flex;
		gap: 0.3rem;
		overflow-x: auto;
		padding-bottom: 0.25rem;
		scrollbar-width: thin;
	}
	.weeks button {
		flex: none;
		border-radius: 999px;
		padding: 0.2rem 0.7rem;
		min-height: 30px;
		font-size: 0.82rem;
	}
	.weeks button.on {
		background: var(--accent-fill);
		border-color: var(--accent-fill);
		color: #fff;
		font-weight: 600;
	}
	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 230px), 1fr));
		gap: 0.75rem;
	}
	.game {
		display: grid;
		gap: 0.35rem;
		padding: 0.8rem 0.9rem;
	}
	.row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.92rem;
	}
	.row.lost {
		color: var(--text-muted);
	}
	.row.lost .score {
		font-weight: 500;
	}
	.score {
		font: 800 1.15rem var(--display);
		font-variant-numeric: tabular-nums;
	}
	.spark {
		width: 100%;
		height: 34px;
		margin-top: 0.15rem;
	}
	.spark path {
		fill: none;
		stroke-width: 1.8;
		vector-effect: non-scaling-stroke;
	}
	.spark .mid {
		stroke: var(--grid);
		stroke-width: 1;
		vector-effect: non-scaling-stroke;
	}
	.foot {
		display: flex;
		justify-content: space-between;
		align-items: center;
		font-size: 0.75rem;
		color: var(--text-muted);
		min-height: 22px;
	}
	.rank {
		margin: 0;
		padding-left: 1.4rem;
		display: grid;
		gap: 0.1rem;
	}
	.rank a {
		display: grid;
		grid-template-columns: 1fr auto auto;
		gap: 0.8rem;
		align-items: center;
		padding: 0.35rem 0.4rem;
		border-radius: 8px;
		color: inherit;
		text-decoration: none;
		font-variant-numeric: tabular-nums;
	}
	.rank a:hover {
		background: var(--surface-2);
	}
	.who {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 600;
	}
	.strong {
		font-weight: 700;
	}
	.upcoming {
		border-style: dashed;
	}
	.preview {
		display: grid;
		gap: 0.15rem;
		margin: 0.45rem 0 0.2rem;
		font-size: 0.82rem;
		font-variant-numeric: tabular-nums;
	}
	.preview .k {
		color: var(--text-muted);
		margin-right: 0.25rem;
	}
</style>
