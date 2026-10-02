<script lang="ts">
	import { base } from '$app/paths';
	import PlotFigure from '$lib/components/Plot.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { corr, epa, num, pct, signed, spread, wlt } from '$lib/format';
	import { navGroups } from '$lib/nav';
	import { isNarrow, Plot, plotStyle } from '$lib/plot';
	import { resource } from '$lib/resource.svelte';
	import { teamColor, teamName } from '$lib/teams.svelte';
	import type { GamePrediction, Rating } from '$lib/types';

	const meta = resource('meta');
	const ratings = resource('ratings');
	const preds = resource('predictions');
	const luck = resource('luck');
	const qbs = resource('qbs');
	const stab = resource('stability');

	const latest = $derived(meta.value?.seasons.at(-1));
	const season = $derived(latest?.season ?? 0);
	const inProgress = $derived(latest ? !latest.complete : false);

	// Power ratings now, and a week earlier for movers.
	const seasonRatings = $derived((ratings.value ?? []).filter((r) => r.season === season));
	const lastWeek = $derived(Math.max(0, ...seasonRatings.map((r) => r.week)));
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
</script>

<svelte:head><title>Any Given Stat · NFL analytics</title></svelte:head>

<section class="hero">
	<div class="eyebrow" style="color: rgba(255,255,255,0.75)">
		{season}
		{#if latest}· {inProgress ? `through week ${latest.last_week}` : 'final'}{/if}
	</div>
	<h1>Know which numbers matter.</h1>
	<p class="lede">
		Every NFL play since 2016, turned into opponent-adjusted ratings, win probability charts,
		predictions honestly scored against Vegas, and a running check on which stats are real and which
		are noise.
	</p>
	<div class="hero-actions">
		<a class="hero-btn primary" href="{base}/predictions/">This week's lines</a>
		<a class="hero-btn" href="{base}/learn/">How football works, in numbers</a>
	</div>
</section>

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
				Model track record on held-out seasons: misses by {num(test.model_mae, 1)} pts per game vs Vegas'
				{num(test.vegas_mae, 1)}.
			</p>
		{/if}
	</section>

	<!-- Power ratings -->
	<section class="card power">
		<div class="card-head">
			<h2>Power top 10</h2>
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
			<h2>Moving</h2>
			<a href="{base}/ratings/">Trajectories →</a>
		</div>
		<p class="sub">Rating change from last week.</p>
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
		<p class="sub">Record vs what their point differential says (Pythagorean wins).</p>
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
			<p class="foot-note">Red = winning more than they've earned. Expect a correction.</p>
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
			How well each stat predicts itself within a season (1 = perfectly, 0 = coin flip).
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
		<p class="sub">EPA per dropback with a 95% interval (min {Math.round(minDb)} dropbacks).</p>
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
	.hero h1 {
		font-size: clamp(2rem, 1.3rem + 3vw, 3.25rem);
		max-width: 18ch;
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
	.hero-btn.primary {
		background: #fff;
		color: #0f2a4f !important;
		border-color: #fff;
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
</style>
