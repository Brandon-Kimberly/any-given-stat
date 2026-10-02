<script lang="ts">
	// Home-page card for the visitor's team, or a 32-team picker when none is chosen.
	import { base } from '$app/paths';
	import { favorite } from '$lib/favorite.svelte';
	import { signed, spread, wlt, num } from '$lib/format';
	import { teamMeta, teamName } from '$lib/teams.svelte';
	import type { GamePrediction, Luck, Rating } from '$lib/types';
	import CountUp from './CountUp.svelte';
	import TeamBadge from './TeamBadge.svelte';

	let { ratings, luck, upcoming }: { ratings: Rating[]; luck: Luck[]; upcoming: GamePrediction[] } =
		$props();

	const team = $derived(favorite.team);
	const r = $derived(ratings.find((x) => x.team === team));
	const rec = $derived(luck.find((x) => x.team === team));
	const next = $derived(upcoming.find((g) => g.home === team || g.away === team));
	const divisions = $derived.by(() => {
		const by = new Map<string, string[]>();
		for (const t of Object.values(teamMeta.byTeam).sort((a, b) => a.team.localeCompare(b.team))) {
			by.set(t.division, [...(by.get(t.division) ?? []), t.team]);
		}
		return [...by].sort(([a], [b]) => a.localeCompare(b));
	});
	const info = $derived(team ? teamMeta.byTeam[team] : undefined);

	function winProb(g: GamePrediction): number {
		return g.home === team ? g.home_wp : 1 - g.home_wp;
	}
</script>

{#if team}
	<section class="card fav" style="--team: {info?.color ?? 'var(--hero-to)'}">
		<div class="band">
			<TeamBadge {team} size="lg" />
			<div class="who">
				<div class="eyebrow">Your team</div>
				<a class="name" href="{base}/team/?t={team}">{teamName(team)}</a>
			</div>
			<button class="ghost change" onclick={() => favorite.set(null)}>Change</button>
		</div>
		<div class="stats">
			<div>
				<div class="k">Record</div>
				<div class="v"><CountUp text={rec ? wlt(rec.wins, rec.games) : '–'} /></div>
				{#if rec}<div class="n">{signed(rec.wins_over_pythag)} vs Pythagorean</div>{/if}
			</div>
			<div>
				<div class="k">Power rank</div>
				<div class="v"><CountUp text={r ? `#${r.rank}` : '–'} /></div>
				{#if r}<div class="n">{signed(r.points)} pts vs average</div>{/if}
			</div>
			<div>
				<div class="k">Offense / defense</div>
				<div class="v small">
					{r ? `${signed(r.off_points)} / ${signed(r.def_points)}` : '–'}
				</div>
				<div class="n">points per game added</div>
			</div>
		</div>
		{#if next}
			<a class="next" href="{base}/game/?id={next.game_id}">
				<span class="eyebrow">Next · week {next.week}</span>
				<span class="matchup">
					<TeamBadge team={next.away} />
					<span class="muted">{next.neutral ? 'vs' : '@'}</span>
					<TeamBadge team={next.home} />
				</span>
				<span class="lines">
					Model {spread(next.model, next.home, next.away)} · Vegas {spread(
						next.vegas,
						next.home,
						next.away
					)} · {num(winProb(next) * 100)}% to win
				</span>
			</a>
		{/if}
	</section>
{:else}
	<section class="card pick">
		<div class="card-head">
			<h2>Pick your team</h2>
		</div>
		<p class="sub">
			It gets a gold ring everywhere on the site, highlighted rows in every table, and this card.
			Press <kbd>g</kbd> <kbd>m</kbd> to jump to it.
		</p>
		<div class="divs">
			{#each divisions as [div, teams] (div)}
				<div class="div">
					<div class="eyebrow">{div}</div>
					<div class="row">
						{#each teams as t (t)}
							<button
								class="pick-btn"
								onclick={() => favorite.set(t)}
								aria-label="Pick {teamName(t)}"
							>
								<TeamBadge team={t} size="md" />
							</button>
						{/each}
					</div>
				</div>
			{/each}
		</div>
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
		padding: 1rem 1.1rem 0.6rem;
	}
	.k {
		font-size: 0.75rem;
		color: var(--text-secondary);
	}
	.v {
		font: 800 1.45rem/1.15 var(--display);
	}
	.v.small {
		font-size: 1.05rem;
		padding: 0.2rem 0;
	}
	.n {
		font-size: 0.74rem;
		color: var(--text-muted);
	}
	.next {
		display: grid;
		gap: 0.3rem;
		margin: 0 1.1rem 1rem;
		padding: 0.65rem 0.8rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		color: inherit;
		text-decoration: none;
	}
	.next:hover {
		background: var(--surface-2);
	}
	.next .eyebrow {
		margin: 0;
	}
	.matchup {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
	}
	.lines {
		font-size: 0.82rem;
		color: var(--text-secondary);
		font-variant-numeric: tabular-nums;
	}
	.divs {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.6rem 1rem;
	}
	.div .eyebrow {
		margin: 0 0 0.25rem;
	}
	.row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem;
	}
	.pick-btn {
		padding: 2px;
		min-height: 0;
		border: 0;
		background: transparent;
		border-radius: 8px;
		transition: transform 0.12s var(--ease);
	}
	.pick-btn:hover {
		transform: translateY(-2px) scale(1.06);
	}
	@media (min-width: 900px) {
		.fav {
			display: grid;
			grid-template-columns: minmax(260px, 1fr) 1.4fr minmax(260px, 1fr);
			align-items: center;
		}
		.band {
			align-self: stretch;
		}
		.stats {
			padding: 0.8rem 1.1rem;
		}
		.next {
			margin: 0.8rem 1.1rem;
		}
	}
	@media (max-width: 820px) {
		.divs {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (max-width: 480px) {
		.stats {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
