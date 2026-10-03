<script lang="ts">
	// A team's fantasy season under the current scoring: who scores the points, and how
	// generous the defense is to each position (rank among 32: 1 = gives up the most).
	import { base } from '$app/paths';
	import { pointsAllowed } from '$lib/fantasy/analysis';
	import { fantasyIds, fantasySeason, scoredSeason, scoringLabel } from '$lib/fantasy/data.svelte';
	import { fantasy } from '$lib/fantasy/league.svelte';
	import type { FantasyPos } from '$lib/fantasy/statline';
	import { num } from '$lib/format';

	let { team, season }: { team: string; season: number } = $props();

	const fs = fantasySeason(() => season);
	const ids = fantasyIds();
	const result = $derived(scoredSeason(fs.value));
	const owners = $derived(ids.value ? fantasy.ownership(ids.value) : null);
	const top = $derived(
		(result?.players ?? [])
			.filter((p) => p.team === team && ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'].includes(p.pos))
			.slice(0, 8)
	);
	const allowed = $derived(
		fs.value && result ? pointsAllowed(fs.value, result).find((a) => a.team === team) : undefined
	);
	const POS: FantasyPos[] = ['QB', 'RB', 'WR', 'TE', 'K'];
	const href = (pos: FantasyPos, id: string) =>
		['QB', 'RB', 'WR', 'TE'].includes(pos) ? `${base}/player/?id=${id}` : null;
	const tone = (rank: number) => (rank <= 8 ? 'soft' : '');
</script>

{#if !result && !fs.error}
	<!-- Holds the card's space while the season file loads, so the game log doesn't jump. -->
	<div class="card placeholder" aria-hidden="true"></div>
{:else if result && (top.length || allowed)}
	<div class="card tf">
		<div class="card-head">
			<h2>Fantasy <span class="muted">· {scoringLabel()}</span></h2>
			<a href="{base}/fantasy/?season={season}">All players →</a>
		</div>
		<div class="cols">
			<div>
				<h3>Top scorers</h3>
				<ol class="scorers">
					{#each top as p (p.id)}
						{@const o = owners?.get(p.id)}
						<li>
							<span class="pos">{p.pos}</span>
							{#if href(p.pos, p.id)}<a href={href(p.pos, p.id)}>{p.name}</a>{:else}<span class="nm"
									>{p.pos === 'DEF' ? 'Defense / ST' : p.name}</span
								>{/if}
							{#if o}<span class="owner" class:mine={o.mine}>{o.mine ? 'Yours' : o.teamName}</span
								>{/if}
							<span class="pts">{num(p.points, 1)}</span>
							<span class="ppg muted">{num(p.ppg, 1)}/g</span>
						</li>
					{/each}
				</ol>
			</div>
			{#if allowed}
				<div>
					<h3>Defense vs position</h3>
					<p class="muted small">
						Fantasy points allowed per game, and rank among 32 defenses (1 = gives up the most =
						best matchup for opponents). Highlighted: a top-8 matchup to target.
					</p>
					<div class="vs">
						{#each POS as p (p)}
							<div class="vs-cell {tone(allowed.rank[p] ?? 16)}">
								<span class="k">vs {p}</span>
								<b>{num(allowed.perGame[p], 1)}</b>
								<span class="r">#{allowed.rank[p]}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.placeholder {
		min-height: 382px;
	}
	@media (max-width: 760px) {
		.placeholder {
			min-height: 592px;
		}
	}
	.cols {
		display: grid;
		grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
		gap: 1.5rem;
	}
	@media (max-width: 760px) {
		.cols {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	h3 {
		margin: 0 0 0.5rem;
		font: 700 0.78rem var(--display);
		text-transform: uppercase;
		letter-spacing: 0.07em;
		color: var(--text-muted);
	}
	.scorers {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.scorers li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0;
		border-bottom: 1px solid var(--grid);
		font-size: 0.9rem;
	}
	.scorers a,
	.nm {
		font-weight: 600;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.pos {
		min-width: 2.3rem;
		padding: 0.1rem 0.3rem;
		border-radius: 6px;
		background: var(--surface-2);
		font-size: 0.7rem;
		font-weight: 700;
		text-align: center;
		color: var(--text-secondary);
	}
	.pts {
		margin-left: auto;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.ppg {
		min-width: 3.4rem;
		text-align: right;
		font-size: 0.8rem;
		font-variant-numeric: tabular-nums;
	}
	.owner {
		padding: 0.05rem 0.4rem;
		border-radius: 999px;
		background: var(--surface-2);
		font-size: 0.7rem;
		font-weight: 600;
		color: var(--text-secondary);
		white-space: nowrap;
	}
	.owner.mine {
		box-shadow: inset 0 0 0 1.5px var(--fav);
		color: var(--text-primary);
	}
	.vs {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 0.4rem;
	}
	.vs-cell {
		display: grid;
		justify-items: center;
		gap: 0.1rem;
		padding: 0.55rem 0.2rem;
		border-radius: 10px;
		background: var(--surface-2);
		font-variant-numeric: tabular-nums;
	}
	/* Top-8 most generous: a matchup to target. */
	.vs-cell.soft {
		background: var(--accent-soft);
	}
	.vs-cell b {
		font: 800 1.1rem var(--display);
	}
	.k,
	.r {
		font-size: 0.72rem;
		color: var(--text-secondary);
	}
	.small {
		font-size: 0.8rem;
		margin: -0.2rem 0 0.6rem;
	}
</style>
