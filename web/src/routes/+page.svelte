<script lang="ts">
	import { ratingsWeek } from '$lib/season';
	import { base } from '$app/paths';
	import CountUp from '$lib/components/CountUp.svelte';
	import FavoriteCard from '$lib/components/FavoriteCard.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import Ticker, { type TickerItem } from '$lib/components/Ticker.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { corr, epa, num, pct, signed, spread, wlt } from '$lib/format';
	import { navGroups } from '$lib/nav';
	import { isNarrow, Plot, plotStyle } from '$lib/plot';
	import { resource, seasonResource } from '$lib/resource.svelte';
	import { excitement, excitementPercentile, loadSeasonGames } from '$lib/games';
	import { favorite } from '$lib/favorite.svelte';
	import { heroColors, teamColor, teamName } from '$lib/teams.svelte';
	import type { GameDetail, GamePrediction, Rating } from '$lib/types';

	const meta = resource('meta');
	const oddsIndex = resource('playoff_odds/index');
	const preds = resource('predictions');
	const luck = resource('luck');
	const qbs = resource('qbs');
	const stab = resource('stability');
	const gameIndex = resource('games/index');

	const latest = $derived(meta.value?.seasons.at(-1));
	const season = $derived(latest?.season ?? 0);
	const inProgress = $derived(latest ? !latest.complete : false);
	const ratings = seasonResource<Rating>('ratings', () => season || null);
	const simulated = $derived(
		(oddsIndex.value ?? []).reduce((a, s) => a + s.weeks.length, 0) * 10000
	);

	// This season's games, for the ticker's latest finals.
	let seasonGames = $state.raw<GameDetail[]>([]);
	$effect(() => {
		if (!season) return;
		loadSeasonGames(season)
			.then((g) => (seasonGames = g))
			.catch(() => (seasonGames = []));
	});
	const totalGames = $derived((gameIndex.value ?? []).reduce((a, s) => a + s.games, 0));

	const ticker = $derived.by<TickerItem[]>(() => {
		const finals = seasonGames.filter((g) => g.home_score != null && g.season_type === 'REG');
		const lastWk = Math.max(0, ...finals.map((g) => g.week));
		const recent = finals
			.filter((g) => g.week === lastWk)
			.map((g) => ({ g, ex: excitementPercentile(excitement(g)) }))
			.sort((a, b) => b.ex - a.ex)
			.map<TickerItem>(({ g, ex }) => {
				const homeWon = g.home_score! > g.away_score!;
				const w = homeWon ? g.home : g.away;
				const l = homeWon ? g.away : g.home;
				const ws = Math.max(g.home_score!, g.away_score!);
				const ls = Math.min(g.home_score!, g.away_score!);
				return {
					key: g.game_id,
					href: `/game/?id=${g.game_id}`,
					tag: ex >= 0.85 ? `Wk ${g.week} · thriller` : `Wk ${g.week} final`,
					text: `${w} ${ws}, ${l} ${ls}`,
					hot: ex >= 0.85
				};
			});
		const next = (preds.value?.upcoming ?? []).map<TickerItem>((g) => ({
			key: g.game_id,
			href: `/game/?id=${g.game_id}`,
			tag: `Wk ${g.week} line`,
			text: `${g.away} ${g.neutral ? 'vs' : '@'} ${g.home} · ${spread(g.vegas, g.home, g.away)} (model ${spread(g.model, g.home, g.away)})`
		}));
		return [...recent, ...next];
	});

	// Power ratings now, and a week earlier for movers.
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
	const movers = $derived.by(() => {
		const prev = new Map(
			seasonRatings.filter((r) => r.week === lastWeek - 1).map((r) => [r.team, r])
		);
		return now
			.map((r) => ({ r, delta: prev.has(r.team) ? r.points - prev.get(r.team)!.points : 0 }))
			.sort((a, b) => b.delta - a.delta);
	});

	const games = $derived(
		[...(preds.value?.upcoming ?? [])].sort(
			(a, b) => Math.abs(b.model - (b.vegas ?? b.model)) - Math.abs(a.model - (a.vegas ?? a.model))
		)
	);
	const test = $derived(preds.value?.summary.find((s) => s.split === 'test'));

	const luckRows = $derived(
		(luck.value ?? [])
			.filter((l) => l.season === season)
			.sort((a, b) => b.wins_over_pythag - a.wins_over_pythag)
	);
	const minDb = $derived(Math.max(40, ((latest?.reg_games ?? 272) / 16) * 12));
	const topQbs = $derived(
		(qbs.value ?? [])
			.filter((q) => q.season === season && q.scope === 'no_garbage' && q.dropbacks >= minDb)
			.sort((a, b) => b.epa_db - a.epa_db)
			.slice(0, 6)
	);
	const noise = $derived(
		[...(stab.value?.metrics ?? [])]
			.filter((m) => m.split_half_r != null)
			.sort((a, b) => (a.split_half_r ?? 0) - (b.split_half_r ?? 0))
	);

	function qbNote(g: GamePrediction): string | null {
		const sides = [
			[g.home, g.home_qb_pts, g.home_qb],
			[g.away, g.away_qb_pts, g.away_qb]
		] as const;
		const big = sides.filter(([, p]) => Math.abs(p) >= 1.5);
		return big.length
			? big.map(([t, p, n]) => `${t} ${signed(p)} (${n ?? 'QB change'})`).join(' · ')
			: null;
	}

	function powerChart(width: number) {
		const top = now.slice(0, 10);
		const narrow = width < 400;
		return Plot.plot({
			width,
			height: top.length * 30 + 30,
			style: plotStyle,
			marginLeft: narrow ? 46 : 150,
			marginRight: 44,
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
		{season}
		{#if latest}· {inProgress ? `through week ${latest.last_week}` : 'final'}{/if}
	</div>
	<h1>Know which numbers <span class="glow">matter.</span></h1>
	<p class="lede">
		Every NFL play since 2016, turned into opponent-adjusted ratings, win probability charts,
		predictions honestly scored against Vegas, and a running check on which stats are real and which
		are noise.
	</p>
	<div class="hero-actions">
		<a class="hero-btn primary" href="{base}/predictions/">This week's lines</a>
		<a class="hero-btn" href="{base}/learn/">How football works, in numbers</a>
	</div>
	<dl class="hero-stats">
		<div>
			<dt>Games charted</dt>
			<dd><CountUp text={totalGames ? num(totalGames) : '0'} duration={1100} /></dd>
		</div>
		<div>
			<dt>Seasons</dt>
			<dd><CountUp text={String(meta.value?.seasons.length ?? 0)} duration={1100} /></dd>
		</div>
		<div>
			<dt>Seasons simulated</dt>
			<dd><CountUp text={num(simulated)} duration={1100} /></dd>
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

<FavoriteCard ratings={now} luck={luckRows} upcoming={preds.value?.upcoming ?? []} />

<div class="dash">
	<!-- This week -->
	<section class="card week">
		<div class="card-head">
			<h2>{games[0] ? `Week ${games[0].week}` : 'This week'}: model vs Vegas</h2>
			<a href="{base}/predictions/">All games →</a>
		</div>
		<p class="sub">Biggest disagreements first. The line usually wins; ask what it knows.</p>
		{#if games.length}
			<ul class="games">
				{#each games.slice(0, 7) as g (g.game_id)}
					{@const note = qbNote(g)}
					<li>
						<a href="{base}/game/?id={g.game_id}">
							<span class="matchup">
								<TeamBadge team={g.away} />
								<span class="at">{g.neutral ? 'vs' : '@'}</span>
								<TeamBadge team={g.home} />
							</span>
							<span class="lines">
								<span><span class="k">Model</span> {spread(g.model, g.home, g.away)}</span>
								<span><span class="k">Vegas</span> {spread(g.vegas, g.home, g.away)}</span>
							</span>
							{#if note}<span class="qb">{note}</span>{/if}
						</a>
					</li>
				{/each}
			</ul>
		{:else if preds.value}
			<p class="muted">No upcoming games in the data (offseason or end of the regular season).</p>
		{:else if !preds.error}
			<div class="skeleton" style="height: 240px"></div>
		{/if}
		{#if test}
			<p class="foot-note">
				Test seasons ({preds.value?.params.test_seasons.join('–')}): the model misses by {num(
					test.model_mae,
					1
				)} pts a game on average; Vegas by
				{num(test.vegas_mae, 1)}.
			</p>
		{/if}
	</section>

	<!-- Power ratings -->
	<section class="card power">
		<div class="card-head">
			<h2>Power ratings: top 10</h2>
			<a href="{base}/ratings/">All 32 →</a>
		</div>
		<p class="sub">Points better than an average team on a neutral field, after week {lastWeek}.</p>
		{#if now.length}
			<PlotFigure label="Top 10 power ratings" render={powerChart} />
		{:else}
			<div class="skeleton" style="height: 300px"></div>
		{/if}
	</section>

	<!-- Movers -->
	<section class="card movers">
		<div class="card-head">
			<h2>Biggest movers</h2>
			<a href="{base}/ratings/">Trajectories →</a>
		</div>
		<p class="sub">Change in power rating since last week, in points.</p>
		{#if movers.length}
			<ul class="list">
				{#each [...movers.slice(0, 3), ...movers.slice(-3)] as m (m.r.team)}
					<li>
						<TeamBadge team={m.r.team} name="nick" link />
						<span class="chip {m.delta >= 0 ? 'good' : 'bad'}"
							>{m.delta >= 0 ? '▲' : '▼'} {signed(m.delta)}</span
						>
					</li>
				{/each}
			</ul>
		{:else}
			<div class="skeleton" style="height: 180px"></div>
		{/if}
	</section>

	<!-- Luck -->
	<section class="card luck">
		<div class="card-head">
			<h2>Regression watch</h2>
			<a href="{base}/luck/">Luck →</a>
		</div>
		<p class="sub">Wins vs what point differential predicts (Pythagorean wins).</p>
		{#if luckRows.length}
			<ul class="list">
				{#each [...luckRows.slice(0, 3), ...luckRows.slice(-3)] as l (l.team)}
					<li>
						<TeamBadge team={l.team} name="nick" link />
						<span class="tnum muted">{wlt(l.wins, l.games)}</span>
						<span class="chip {l.wins_over_pythag > 0 ? 'bad' : 'good'}"
							>{signed(l.wins_over_pythag)} W</span
						>
					</li>
				{/each}
			</ul>
			<p class="foot-note">Plus = more wins than their points earned. Expect a correction.</p>
		{:else}
			<div class="skeleton" style="height: 180px"></div>
		{/if}
	</section>

	<!-- Noise -->
	<section class="card noise">
		<div class="card-head">
			<h2>Stats to stop quoting</h2>
			<a href="{base}/stability/">Signal vs noise →</a>
		</div>
		<p class="sub">
			How well each stat predicts itself within a season (1 = perfectly, 0 = pure noise). The four
			noisiest, then the two steadiest.
		</p>
		{#if noise.length}
			<ul class="list">
				{#each noise.slice(0, 4) as m (m.key)}
					<li>
						<span>{m.label}</span>
						<span class="chip bad">r = {corr(m.split_half_r)}</span>
					</li>
				{/each}
				{#each noise.slice(-2).reverse() as m (m.key)}
					<li>
						<span>{m.label}</span>
						<span class="chip good">r = {corr(m.split_half_r)}</span>
					</li>
				{/each}
			</ul>
		{:else}
			<div class="skeleton" style="height: 180px"></div>
		{/if}
	</section>
	<!-- QBs -->
	<section class="card qbs">
		<div class="card-head">
			<h2>QB efficiency leaders</h2>
			<a href="{base}/qbs/">All QBs →</a>
		</div>
		<p class="sub">
			EPA per dropback, no garbage time, with a 95% interval (min {Math.round(minDb)} dropbacks).
		</p>
		{#if topQbs.length}
			<ul class="list qb-list">
				{#each topQbs as q (q.player_id)}
					<li>
						<a class="qb-name" href="{base}/player/?id={q.player_id}">{q.full_name ?? q.name}</a>
						<TeamBadge team={q.team} />
						<span class="tnum strong">{epa(q.epa_db)}</span>
						<span class="tnum muted small">{epa(q.epa_db_lo, 2)} to {epa(q.epa_db_hi, 2)}</span>
					</li>
				{/each}
			</ul>
		{:else}
			<div class="skeleton" style="height: 200px"></div>
		{/if}
	</section>
</div>

<section class="explore">
	<h2>Explore</h2>
	<div class="grid-3">
		{#each navGroups as g (g.label)}
			{#each g.items as item (item.href)}
				<a class="card tile-link" href="{base}{item.href}">
					<span class="eyebrow">{g.label}</span>
					<span class="t">{item.label}</span>
					<span class="b">{item.blurb}</span>
				</a>
			{/each}
		{/each}
	</div>
</section>

<style>
	/* ---------- Hero: a stadium under the lights ---------- */
	.hero {
		min-height: 400px;
		padding-bottom: clamp(1.5rem, 1rem + 3vw, 3rem);
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
		font-size: clamp(2.2rem, 1.3rem + 3.6vw, 3.9rem);
		font-stretch: 118%;
		line-height: 1.02;
		max-width: 16ch;
		margin-bottom: 0.7rem;
		text-shadow: 0 2px 30px rgba(0, 0, 0, 0.25);
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
		gap: 0.5rem 2rem;
		margin: 1.4rem 0 0;
	}
	.hero-stats dt {
		font-size: 0.72rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: rgba(255, 255, 255, 0.75);
	}
	.hero-stats dd {
		margin: 0;
		font: 800 clamp(1.4rem, 1.1rem + 1.2vw, 2rem) / 1.1 var(--display);
	}
	/* A football drifting across the field behind the copy. */
	.ball {
		position: absolute;
		right: 7%;
		top: 14%;
		z-index: 1;
		width: clamp(120px, 16vw, 210px);
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
	@media (max-width: 640px) {
		.ball {
			display: none;
		}
	}
	.hero-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		margin-top: 1rem;
	}
	.hero-btn {
		display: inline-flex;
		align-items: center;
		padding: 0.55rem 1rem;
		border-radius: 10px;
		font-weight: 600;
		text-decoration: none;
		background: rgba(255, 255, 255, 0.12);
		border: 1px solid rgba(255, 255, 255, 0.25);
		transition:
			background 0.15s,
			transform 0.15s;
	}
	.hero-btn:hover {
		background: rgba(255, 255, 255, 0.2);
		transform: translateY(-1px);
	}
	.hero-btn {
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
	}
	.hero-btn.primary {
		background: #fff;
		color: #0f2a4f !important;
		border-color: #fff;
		box-shadow: 0 10px 30px -10px rgba(165, 243, 252, 0.6);
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
	.dash {
		display: grid;
		gap: 1rem;
		grid-template-columns: repeat(12, minmax(0, 1fr));
	}
	.week {
		grid-column: span 7;
	}
	.power {
		grid-column: span 5;
	}
	.movers,
	.luck,
	.noise {
		grid-column: span 4;
	}
	.qbs {
		grid-column: span 12;
	}
	@media (max-width: 1100px) {
		.week,
		.power {
			grid-column: span 12;
		}
		.movers,
		.luck,
		.noise {
			grid-column: span 6;
		}
	}
	@media (max-width: 640px) {
		.movers,
		.luck,
		.qbs,
		.noise {
			grid-column: span 12;
		}
	}
	.card-head a {
		font-size: 0.85rem;
		white-space: nowrap;
	}
	.games {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.35rem;
	}
	.games a {
		display: grid;
		grid-template-columns: auto 1fr;
		align-items: center;
		gap: 0.15rem 1rem;
		padding: 0.55rem 0.7rem;
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
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.at {
		color: var(--text-muted);
		font-size: 0.8rem;
	}
	.lines {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 1rem;
		justify-content: flex-end;
		font-size: 0.85rem;
		font-variant-numeric: tabular-nums;
		font-weight: 600;
	}
	.k {
		font-weight: 500;
		color: var(--text-muted);
		margin-right: 0.2rem;
	}
	.qb {
		grid-column: 1 / -1;
		font-size: 0.78rem;
		color: var(--text-secondary);
	}
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
	.qb-name {
		color: inherit;
		font-weight: 600;
		text-decoration: none;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.qb-name:hover {
		text-decoration: underline;
	}
	.qb-list {
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 330px), 1fr));
		column-gap: 2rem;
	}
	.strong {
		font-weight: 700;
	}
	.small {
		font-size: 0.75rem;
	}
	.foot-note {
		font-size: 0.8rem;
		color: var(--text-muted);
		margin: 0.6rem 0 0;
	}
	.explore h2 {
		margin-bottom: 0.6rem;
	}
	.tile-link {
		display: grid;
		gap: 0.15rem;
	}
	.tile-link .eyebrow {
		margin: 0;
	}
	.t {
		font: 700 1.05rem var(--display);
	}
	.b {
		color: var(--text-secondary);
		font-size: 0.875rem;
	}
	/* Phones: a compact two-column index (the footer site map repeats it with groups). */
	@media (max-width: 640px) {
		.explore .grid-3 {
			grid-template-columns: 1fr 1fr;
			gap: 0.5rem;
		}
		.tile-link {
			padding: 0.65rem 0.8rem;
			min-height: 44px;
			align-content: center;
		}
		.tile-link .eyebrow,
		.b {
			display: none;
		}
		.t {
			font-size: 0.95rem;
		}
	}
</style>
