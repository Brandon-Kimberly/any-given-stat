<script lang="ts">
	// The site's forecast (round 3), game by game: each input's contribution in points. The
	// contributions add up to the "Model" line in the week table above.
	import { base } from '$app/paths';
	import { kickoffKey, kickoffLabel } from '$lib/kickoff';
	import { spread } from '$lib/format';
	import type { GamePrediction, Lab3 } from '$lib/types';
	import TeamBadge from './TeamBadge.svelte';

	let {
		games,
		schedule,
		injuriesIn
	}: {
		games: Lab3['upcoming'];
		/** predictions.json rows for the same games: kickoff time, neutral site. */
		schedule: GamePrediction[];
		/** Teams with final injury statuses filed, of those playing (round 2's protocol). */
		injuriesIn?: { filed: number | null; playing: number };
	} = $props();

	const byId = $derived(new Map(schedule.map((g) => [g.game_id, g])));
	const sorted = $derived(
		games
			.map((g) => {
				const s = byId.get(g.game_id);
				return {
					...g,
					neutral: !!s?.neutral,
					kick: s ? kickoffLabel(s.gameday, s.gametime) : '',
					order: s ? kickoffKey(s.gameday, s.gametime) : ''
				};
			})
			.sort((a, b) => a.order.localeCompare(b.order) || a.game_id.localeCompare(b.game_id))
	);
	const scale = $derived(
		Math.max(3, ...games.flatMap((g) => g.factors.map((f) => Math.abs(f.points))))
	);
	const fresh = $derived(
		!injuriesIn || (injuriesIn.filed != null && injuriesIn.filed >= injuriesIn.playing * 0.8)
	);
	// Phones show the first few games until asked: 15 cards are a long scroll at 390px.
	const PHONE = 4;
	let all = $state(false);
	const injuryLine = (list: Lab3['upcoming'][number]['injuries']['home']) =>
		list
			.slice(0, 4)
			.map((x) => `${x.name} (${x.pos}, ${x.status.toLowerCase()})`)
			.join(', ');
</script>

{#if !fresh && injuriesIn}
	<div class="callout info" role="note">
		Final injury statuses are in for {injuriesIn.filed ?? 0} of {injuriesIn.playing} teams. Teams file
		them Friday (Wednesday for Thursday games). Until then, injuries count as 0 here, and lines will move
		when the site rebuilds.
	</div>
{/if}
<div class="legend" aria-hidden="true">
	<span><i class="sw away"></i> Toward the visitor</span>
	<span><i class="sw home"></i> Toward the home team</span>
</div>
<div class="games">
	{#each sorted as g, i (g.game_id)}
		<article class="game" class:extra={i >= PHONE && !all}>
			<header>
				<a href="{base}/game/?id={g.game_id}" class="mu">
					<TeamBadge team={g.away} /> <span class="muted">{g.neutral ? 'vs' : '@'}</span>
					<TeamBadge team={g.home} />
				</a>
				<span class="kick muted">{g.kick}</span>
			</header>
			<dl class="lines">
				<div>
					<dt>Model</dt>
					<dd>{spread(g.model, g.home, g.away)}</dd>
				</div>
				<div>
					<dt>Vegas</dt>
					<dd>{spread(g.vegas, g.home, g.away)}</dd>
				</div>
				<div>
					<dt>Best estimate</dt>
					<dd>{spread(g.blend, g.home, g.away)}</dd>
				</div>
			</dl>
			<ul class="factors">
				{#each g.factors as f (f.feature)}
					<li>
						<span class="fl">{f.label}</span>
						<span class="track" aria-hidden="true">
							<span
								class="fb"
								class:pos={f.points > 0}
								style:width="{(Math.abs(f.points) / scale) * 50}%"
								style:left={f.points >= 0 ? '50%' : `${50 - (Math.abs(f.points) / scale) * 50}%`}
							></span>
						</span>
						<span class="fv"
							>{Math.abs(f.points) < 0.05
								? '0'
								: `${f.points > 0 ? g.home : g.away} +${Math.abs(f.points).toFixed(1)}`}</span
						>
					</li>
				{/each}
			</ul>
			{#if g.injuries.home.length || g.injuries.away.length}
				<p class="inj">
					{#if g.injuries.away.length}<b>{g.away}:</b> {injuryLine(g.injuries.away)}<br />{/if}
					{#if g.injuries.home.length}<b>{g.home}:</b> {injuryLine(g.injuries.home)}{/if}
				</p>
			{/if}
		</article>
	{/each}
</div>

{#if sorted.length > PHONE && !all}
	<button type="button" class="more" onclick={() => (all = true)}
		>Show all {sorted.length} games</button
	>
{/if}

<style>
	.callout {
		margin-bottom: 0.75rem;
	}
	.legend {
		display: flex;
		gap: 1rem;
		margin-bottom: 0.6rem;
		font-size: 0.8rem;
		color: var(--text-secondary);
	}
	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.sw {
		width: 12px;
		height: 10px;
		border-radius: 2px;
		background: var(--series-2);
	}
	.sw.home {
		background: var(--series-1);
	}
	.games {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 320px), 1fr));
		gap: 0.75rem;
	}
	.game {
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 0.75rem 0.85rem;
		display: grid;
		gap: 0.45rem;
		align-content: start;
	}
	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
	}
	.mu {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		text-decoration: none;
		color: inherit;
	}
	.kick {
		font-size: 0.76rem;
		white-space: nowrap;
	}
	.lines {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem 1rem;
		margin: 0;
		font-size: 0.85rem;
		font-variant-numeric: tabular-nums;
	}
	.lines div {
		display: flex;
		gap: 0.3rem;
		align-items: baseline;
	}
	.lines dt {
		color: var(--text-muted);
		font-size: 0.78rem;
	}
	.lines dd {
		margin: 0;
		font-weight: 700;
	}
	.factors {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.2rem;
	}
	.factors li {
		display: grid;
		grid-template-columns: 7rem 1fr 4.6rem;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.76rem;
	}
	.fl {
		color: var(--text-secondary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.track {
		position: relative;
		height: 10px;
		background:
			linear-gradient(var(--axis), var(--axis)) 50% / 1px 100% no-repeat,
			var(--surface-2);
		border-radius: 3px;
	}
	.fb {
		position: absolute;
		top: 1px;
		bottom: 1px;
		border-radius: 2px;
		background: var(--series-2);
	}
	.fb.pos {
		background: var(--series-1);
	}
	.fv {
		text-align: right;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.more {
		display: none;
	}
	@media (max-width: 560px) {
		.extra {
			display: none;
		}
		.more {
			display: block;
			margin: 0.75rem auto 0;
		}
	}
	.inj {
		margin: 0;
		font-size: 0.76rem;
		color: var(--text-secondary);
	}
</style>
