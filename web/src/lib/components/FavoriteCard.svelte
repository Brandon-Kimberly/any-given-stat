<script lang="ts">
	// Home-page card for the visitor's team (record, power, playoff odds, last result, next game),
	// or a compact prompt that opens a 32-team picker when none is chosen.
	import { base } from '$app/paths';
	import { favorite } from '$lib/favorite.svelte';
	import { num, signed, spread, wlt } from '$lib/format';
	import { confetti } from '$lib/confetti';
	import { kickoffLabel, weekLabel, type TeamRecord } from '$lib/standings';
	import { teamMeta, teamName, teamPalette } from '$lib/teams.svelte';
	import type { GamePrediction, PlayoffOddsRow, Rating, ScheduleGame } from '$lib/types';
	import CountUp from './CountUp.svelte';
	import TeamBadge from './TeamBadge.svelte';
	import TeamLogo from './TeamLogo.svelte';

	let {
		season,
		ratings,
		ratingDelta,
		records,
		odds,
		oddsPrev,
		last,
		next,
		prediction
	}: {
		season: number;
		ratings: Rating[];
		/** Change in power-rating points since the previous week, by team. */
		ratingDelta: Map<string, number>;
		records: Map<string, TeamRecord>;
		odds: PlayoffOddsRow[];
		oddsPrev: PlayoffOddsRow[];
		last: (team: string) => ScheduleGame | undefined;
		next: (team: string) => ScheduleGame | undefined;
		prediction: (gameId: string) => GamePrediction | undefined;
	} = $props();

	const team = $derived(favorite.team);
	const r = $derived(ratings.find((x) => x.team === team));
	const rec = $derived(team ? records.get(team) : undefined);
	const o = $derived(odds.find((x) => x.team === team));
	const oPrev = $derived(oddsPrev.find((x) => x.team === team));
	const lastG = $derived(team ? last(team) : undefined);
	const nextG = $derived(team ? next(team) : undefined);
	const pred = $derived(nextG ? prediction(nextG.game_id) : undefined);
	const q = $derived(`season=${season}`);

	const divisions = $derived.by(() => {
		const by = new Map<string, string[]>();
		for (const t of Object.values(teamMeta.byTeam).sort((a, b) => a.team.localeCompare(b.team))) {
			by.set(t.division, [...(by.get(t.division) ?? []), t.team]);
		}
		return [...by].sort(([a], [b]) => a.localeCompare(b));
	});
	const info = $derived(team ? teamMeta.byTeam[team] : undefined);

	function lastLine(g: ScheduleGame, t: string): string {
		const home = g.home === t;
		const mine = home ? g.home_score! : g.away_score!;
		const theirs = home ? g.away_score! : g.home_score!;
		const res = mine > theirs ? 'W' : mine < theirs ? 'L' : 'T';
		return `${res} ${mine}–${theirs}`;
	}
	const opp = (g: ScheduleGame, t: string) => (g.home === t ? g.away : g.home);
	const at = (g: ScheduleGame, t: string) => (g.neutral ? 'vs' : g.home === t ? 'vs' : '@');
	/** The team's chance to win from the best estimate (market blend), else the model. */
	function winChance(p: GamePrediction, t: string): number {
		const home = p.blend_wp ?? p.home_wp;
		return p.home === t ? home : 1 - home;
	}
	let open = $state(false);
</script>

{#if team}
	<section
		class="card fav"
		style="--team: {info?.color ?? 'var(--hero-to)'}"
		aria-label="Your team"
	>
		<div class="band">
			<TeamLogo {team} size={56} />
			<div class="who">
				<div class="eyebrow">Your team</div>
				<a class="name" href="{base}/team/?t={team}&{q}">{teamName(team)}</a>
			</div>
			<button class="ghost change" onclick={() => favorite.set(null)}>Change</button>
		</div>
		<div class="stats">
			<div>
				<div class="k">Record</div>
				<div class="v"><CountUp text={rec ? wlt(rec.wins, rec.games) : '0–0'} /></div>
				<div class="n">
					{#if rec}{signed(rec.wins - rec.pythag)} wins vs points{:else}No games yet{/if}
				</div>
			</div>
			<a class="stat-link" href="{base}/ratings/?{q}">
				<div class="k">Power rank</div>
				<div class="v"><CountUp text={r ? `#${r.rank}` : '–'} /></div>
				{#if r}
					<div class="n">
						{signed(r.points)} pts{#if ratingDelta.has(team)}&nbsp;· {signed(ratingDelta.get(team))} this
							week{/if}
					</div>
				{/if}
			</a>
			<a class="stat-link" href="{base}/odds/?{q}">
				<div class="k">Playoff odds</div>
				<div class="v"><CountUp text={o ? `${num(o.p_playoffs * 100)}%` : '–'} /></div>
				{#if o && oPrev}
					<div class="n">
						{signed((o.p_playoffs - oPrev.p_playoffs) * 100, 0)} pts since last week
					</div>
				{:else if o}
					<div class="n">{num(o.p_sb * 100, 1)}% to win it all</div>
				{/if}
			</a>
		</div>
		<div class="games">
			{#if lastG}
				<a class="game" href="{base}/game/?id={lastG.game_id}">
					<span class="eyebrow">Last · {weekLabel(lastG)}</span>
					<span class="row">
						<strong class="res">{lastLine(lastG, team)}</strong>
						<span class="muted">{at(lastG, team)}</span>
						<TeamBadge team={opp(lastG, team)} />
					</span>
				</a>
			{/if}
			{#if nextG}
				<a class="game" href="{base}/game/?id={nextG.game_id}">
					<span class="eyebrow"
						>Next · {weekLabel(nextG)} · {kickoffLabel(nextG.gameday, nextG.gametime)}</span
					>
					<span class="row">
						<span class="muted">{at(nextG, team)}</span>
						<TeamBadge team={opp(nextG, team)} />
						{#if pred}
							<strong class="tnum">{num(winChance(pred, team) * 100)}% to win</strong>
						{/if}
					</span>
					{#if nextG.vegas != null || pred}
						<span class="lines">
							Vegas {spread(nextG.vegas, nextG.home, nextG.away)}{pred
								? ` · model ${spread(pred.model, pred.home, pred.away)}`
								: ''}
						</span>
					{/if}
				</a>
			{:else if lastG}
				<p class="muted small">No more games scheduled this season.</p>
			{/if}
		</div>
	</section>
{:else}
	<section class="card pick" class:open aria-labelledby="pick-title">
		<div class="pick-head">
			<div>
				<h2 id="pick-title">Pick your team</h2>
				<p class="sub">
					Its record, odds and next game land here, and it gets a gold ring across the site.
				</p>
			</div>
			<button
				class="ghost"
				aria-expanded={open}
				aria-controls="team-picker"
				onclick={() => (open = !open)}>{open ? 'Close' : 'Choose a team'}</button
			>
		</div>
		{#if open}
			<div class="divs" id="team-picker">
				{#each divisions as [div, teams] (div)}
					<div class="div">
						<div class="eyebrow">{div}</div>
						<div class="picks">
							{#each teams as t (t)}
								<button
									class="pick-btn"
									onclick={(e) => {
										favorite.set(t);
										confetti(e.clientX, e.clientY, teamPalette(t));
									}}
									aria-label="Pick {teamName(t)}"
								>
									<TeamLogo team={t} size={42} />
									<span class="abbr">{t}</span>
								</button>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</section>
{/if}

<style>
	.fav {
		padding: 0;
		overflow: hidden;
	}
	.band {
		display: flex;
		align-items: center;
		gap: 0.9rem;
		padding: 1rem 1.1rem;
		color: #fff;
		background:
			radial-gradient(120% 160% at 100% 0%, rgba(255, 255, 255, 0.18), transparent 55%),
			linear-gradient(120deg, var(--team), color-mix(in srgb, var(--team) 50%, #000));
	}
	.band .eyebrow {
		color: rgba(255, 255, 255, 0.8);
		margin: 0;
	}
	.who {
		flex: 1;
		min-width: 0;
	}
	.name {
		color: #fff;
		font: 800 1.35rem/1.1 var(--display);
		text-decoration: none;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
	}
	.name:hover {
		text-decoration: underline;
	}
	.change {
		color: #fff;
		border-color: rgba(255, 255, 255, 0.4);
		background: rgba(0, 0, 0, 0.2);
		font-size: 0.8rem;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 0.75rem;
		padding: 1rem 1.1rem 0.4rem;
	}
	.stat-link {
		color: inherit;
		text-decoration: none;
		border-radius: 8px;
	}
	.stat-link:hover .k {
		text-decoration: underline;
	}
	.k {
		font-size: 0.75rem;
		color: var(--text-secondary);
	}
	.v {
		font: 800 1.45rem/1.15 var(--display);
	}
	.n {
		font-size: 0.74rem;
		color: var(--text-muted);
	}
	.games {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr));
		gap: 0.5rem;
		padding: 0.6rem 1.1rem 1rem;
	}
	.game {
		display: grid;
		gap: 0.25rem;
		align-content: start;
		padding: 0.55rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		color: inherit;
		text-decoration: none;
	}
	.game:hover {
		background: var(--surface-2);
		border-color: var(--border-strong);
	}
	.game .eyebrow {
		margin: 0;
	}
	.row {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
	}
	.res {
		font-variant-numeric: tabular-nums;
	}
	.lines {
		font-size: 0.8rem;
		color: var(--text-secondary);
		font-variant-numeric: tabular-nums;
	}
	.small {
		font-size: 0.82rem;
		margin: 0.4rem 0;
	}
	@media (min-width: 1000px) {
		.fav {
			display: grid;
			grid-template-columns: minmax(240px, 0.9fr) 1.3fr 1.3fr;
			align-items: center;
		}
		.band {
			align-self: stretch;
		}
		.stats {
			padding: 0.8rem 1.1rem;
		}
		.games {
			padding: 0.8rem 1.1rem 0.8rem 0;
		}
	}
	/* Picker: a one-line prompt until opened. */
	.pick {
		padding-block: 0.8rem;
	}
	.pick-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem 1rem;
	}
	.pick-head h2 {
		margin: 0;
		font-size: 1.05rem;
	}
	.pick-head .sub {
		margin: 0.1rem 0 0;
	}
	.divs {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.6rem 1rem;
		margin-top: 0.9rem;
	}
	.div .eyebrow {
		margin: 0 0 0.25rem;
	}
	.picks {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.pick-btn {
		display: grid;
		justify-items: center;
		gap: 0.2rem;
		padding: 4px 2px;
		min-height: 0;
		border: 0;
		background: transparent;
		border-radius: 12px;
	}
	.pick-btn:hover {
		background: transparent;
	}
	.abbr {
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		color: var(--text-muted);
		transition: color 0.2s;
	}
	@media (prefers-reduced-motion: no-preference) {
		.pick-btn:hover :global(.logo),
		.pick-btn:focus-visible :global(.logo) {
			transform: translateY(-4px) scale(1.08) rotate(-3deg);
		}
	}
	.pick-btn:hover .abbr {
		color: var(--text-primary);
	}
	@media (max-width: 820px) {
		.divs {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (max-width: 480px) {
		.stats {
			gap: 0.5rem;
		}
		.v {
			font-size: 1.2rem;
		}
	}
</style>
