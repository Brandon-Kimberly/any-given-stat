<script lang="ts">
	// The home page's week at a glance: one aligned grid (a single column template shared by
	// every row through subgrid), grouped by kickoff. Per game: matchup, the best estimate's win
	// chance as text + bar, the Vegas and model lines, and two compact flags (model vs Vegas
	// gap, starting-QB change) whose details live in a tooltip and screen-reader text.
	import { base } from '$app/paths';
	import { num, signed, spread } from '$lib/format';
	import { kickoffLabel, played } from '$lib/standings';
	import { teamColor, teamName } from '$lib/teams.svelte';
	import type { GamePrediction, ScheduleGame } from '$lib/types';
	import TeamBadge from './TeamBadge.svelte';

	let { games, predictions }: { games: ScheduleGame[]; predictions: Map<string, GamePrediction> } =
		$props();

	const slots = $derived.by(() => {
		const out: { label: string; games: ScheduleGame[] }[] = [];
		for (const g of games) {
			const label = played(g) ? 'Final' : kickoffLabel(g.gameday, g.gametime);
			const last = out.at(-1);
			if (last?.label === label) last.games.push(g);
			else out.push({ label, games: [g] });
		}
		return out;
	});

	const gap = (p: GamePrediction | undefined) =>
		p && p.vegas != null ? Math.abs(p.model - p.vegas) : 0;
	function best(p: GamePrediction) {
		const wp = p.blend_wp ?? p.home_wp;
		return wp >= 0.5 ? { team: p.home, wp } : { team: p.away, wp: 1 - wp };
	}
	function qbFlag(p: GamePrediction): string | null {
		const sides = [
			[p.home, p.home_qb_pts, p.home_qb],
			[p.away, p.away_qb_pts, p.away_qb]
		] as const;
		const big = sides.filter(([, pts]) => Math.abs(pts) >= 1.5);
		return big.length
			? big
					.map(
						([t, pts, n]) =>
							`${teamName(t)} start ${n ?? 'a new QB'} (${signed(pts)} pts vs the QBs behind their rating)`
					)
					.join('; ')
			: null;
	}
</script>

<div class="board">
	<div class="row head" aria-hidden="true">
		<span>Game</span>
		<span>Win chance</span>
		<span class="num">Vegas</span>
		<span class="num model">Model</span>
		<span></span>
	</div>
	{#each slots as s, i (s.label + i)}
		<h3 class="row slot"><span>{s.label}</span></h3>
		{#each s.games as g (g.game_id)}
			{@const p = predictions.get(g.game_id)}
			{@const done = played(g)}
			{@const b = p && !done ? best(p) : null}
			{@const qb = p && !done ? qbFlag(p) : null}
			{@const delta = done ? 0 : gap(p)}
			<a class="row game" href="{base}/game/?id={g.game_id}">
				<span class="match" class:done>
					<TeamBadge team={g.away} />
					{#if done}<b class="pts" class:lost={g.away_score! < g.home_score!}>{g.away_score}</b
						>{/if}
					<span class="at">{g.neutral ? 'vs' : '@'}</span>
					<TeamBadge team={g.home} />
					{#if done}<b class="pts" class:lost={g.home_score! < g.away_score!}>{g.home_score}</b
						>{/if}
				</span>
				{#if !done}
					<span class="prob">
						{#if b}
							<span class="pct"
								><span class="sr-only">Win chance </span><span class="who">{b.team}</span>
								{num(b.wp * 100)}%</span
							>
							<span class="bar" aria-hidden="true"
								><span style:width="{b.wp * 100}%" style:background={teamColor(b.team)}
								></span></span
							>
						{:else}
							<span class="muted">–</span>
						{/if}
					</span>
				{/if}
				<span class="num"><span class="sr-only">Vegas </span>{spread(g.vegas, g.home, g.away)}</span
				>
				<span class="num model"
					>{#if p && !done}<span class="sr-only">Model </span>{spread(
							p.model,
							p.home,
							p.away
						)}{/if}</span
				>
				<span class="flags">
					{#if delta >= 3}
						<span
							class="flag gap"
							title="Model and Vegas differ by {num(delta, 1)} points (model {spread(
								p!.model,
								p!.home,
								p!.away
							)})"
							>Δ<span class="sr-only">Model and Vegas differ by {num(delta, 1)} points</span></span
						>
					{/if}
					{#if qb}
						<span class="flag qb" title={qb}>QB<span class="sr-only">: {qb}</span></span>
					{/if}
				</span>
			</a>
		{/each}
	{/each}
</div>
<p class="legend">
	<b>Win chance</b> is our best estimate: the Vegas line nudged toward our model.
	<span class="flag gap" aria-hidden="true">Δ</span> model and Vegas differ by 3+ points.
	<span class="flag qb" aria-hidden="true">QB</span> a starting quarterback change moves the line (hover
	for who).
</p>

<style>
	.board {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 8.6rem 5.6rem 5.6rem 3.6rem;
		font-variant-numeric: tabular-nums;
	}
	.row {
		display: grid;
		grid-template-columns: subgrid;
		grid-column: 1 / -1;
		align-items: center;
		column-gap: 0.75rem;
	}
	.head {
		padding: 0 0.6rem 0.35rem;
		font-size: 0.68rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-muted);
		border-bottom: 1px solid var(--border);
	}
	.slot {
		margin: 0;
		padding: 0.75rem 0.6rem 0.25rem;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-secondary);
	}
	.slot > span {
		grid-column: 1 / -1;
	}
	.game {
		min-height: 2.6rem;
		padding: 0.3rem 0.6rem;
		border-radius: 8px;
		color: inherit;
		text-decoration: none;
		border-bottom: 1px solid var(--grid);
		transition: background 0.12s;
	}
	.game:hover,
	.game:focus-visible {
		background: var(--surface-2);
	}
	.match {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		min-width: 0;
	}
	.match.done {
		grid-column: span 2;
	}
	.at {
		color: var(--text-muted);
		font-size: 0.78rem;
		width: 1.1rem;
		text-align: center;
	}
	.pts {
		min-width: 1.4rem;
		font-weight: 700;
	}
	.pts.lost {
		color: var(--text-muted);
		font-weight: 500;
	}
	.prob {
		display: grid;
		gap: 0.2rem;
	}
	.pct {
		font-size: 0.86rem;
		font-weight: 700;
	}
	.who {
		display: inline-block;
		min-width: 2.4rem;
		font-weight: 600;
		color: var(--text-secondary);
	}
	.bar {
		display: block;
		height: 4px;
		border-radius: 2px;
		background: var(--grid);
		overflow: hidden;
	}
	.bar > span {
		display: block;
		height: 100%;
		border-radius: 2px;
	}
	.num {
		text-align: right;
		font-size: 0.84rem;
	}
	.head .num {
		font-size: 0.68rem;
	}
	.model {
		color: var(--text-secondary);
	}
	.flags {
		display: flex;
		justify-content: flex-end;
		gap: 0.25rem;
	}
	.flag {
		display: inline-grid;
		place-items: center;
		min-width: 1.35rem;
		height: 1.25rem;
		padding: 0 0.25rem;
		border-radius: 5px;
		font-size: 0.66rem;
		font-weight: 800;
		letter-spacing: 0.02em;
		color: var(--text-primary);
		cursor: help;
	}
	.flag.gap {
		border: 1.5px solid var(--fav);
	}
	.flag.qb {
		border: 1.5px solid var(--border-strong);
		background: var(--surface-2);
	}
	.legend {
		margin: 0.7rem 0 0;
		font-size: 0.76rem;
		line-height: 1.7;
		color: var(--text-muted);
	}
	.legend .flag {
		cursor: default;
		margin: 0 0.15rem;
	}
	.num {
		white-space: nowrap;
	}
	@media (max-width: 560px) {
		.board {
			grid-template-columns: minmax(0, 1fr) 5.4rem 4.9rem 1.6rem;
		}
		.row {
			column-gap: 0.45rem;
		}
		.flags {
			flex-direction: column;
			align-items: flex-end;
		}
		.who {
			min-width: 2.1rem;
		}
		.model {
			display: none;
		}
		.game,
		.head,
		.slot {
			padding-inline: 0.2rem;
		}
	}
</style>
