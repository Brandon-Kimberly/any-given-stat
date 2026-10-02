<script lang="ts" module>
	export interface RecordItem {
		key: string;
		href: string;
		team?: string;
		title: string;
		sub: string;
		stat: string;
	}
</script>

<script lang="ts">
	// A ranked leaderboard: #1 as a medal row, then the rest, with a show-all toggle.
	import { base } from '$app/paths';
	import TeamBadge from './TeamBadge.svelte';

	let {
		title,
		blurb,
		items,
		show = 10
	}: { title: string; blurb: string; items: RecordItem[]; show?: number } = $props();
	let all = $state(false);
	const shown = $derived(all ? items : items.slice(0, show));
</script>

<section class="card rl">
	<h2>{title}</h2>
	<p class="sub">{blurb}</p>
	<ol>
		{#each shown as it, i (it.key)}
			<li class:first={i === 0} style:animation-delay="{Math.min(i, 12) * 30}ms">
				<span class="rank">{i + 1}</span>
				<a href="{base}{it.href}">
					{#if it.team}<TeamBadge team={it.team} size={i === 0 ? 'md' : 'sm'} />{/if}
					<span class="txt">
						<span class="t">{it.title}</span>
						<span class="s">{it.sub}</span>
					</span>
				</a>
				<span class="stat">{it.stat}</span>
			</li>
		{/each}
	</ol>
	{#if items.length > show}
		<button class="ghost more" onclick={() => (all = !all)}
			>{all ? 'Show fewer' : `Show all ${items.length}`}</button
		>
	{/if}
</section>

<style>
	ol {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	li {
		display: grid;
		grid-template-columns: 1.8rem 1fr auto;
		align-items: center;
		gap: 0.6rem;
		padding: 0.42rem 0.2rem;
		border-bottom: 1px solid var(--grid);
		animation: row-in 0.35s var(--ease) both;
	}
	li:last-child {
		border-bottom: 0;
	}
	li.first {
		padding: 0.7rem 0.6rem;
		margin-bottom: 0.3rem;
		border: 1px solid color-mix(in srgb, var(--fav) 45%, transparent);
		border-radius: 12px;
		background: linear-gradient(
			100deg,
			color-mix(in srgb, var(--fav) 16%, transparent),
			transparent 70%
		);
	}
	.rank {
		font: 800 0.85rem var(--display);
		color: var(--text-muted);
		text-align: center;
	}
	.first .rank {
		display: grid;
		place-items: center;
		width: 1.8rem;
		height: 1.8rem;
		border-radius: 50%;
		background: var(--fav);
		color: #1a1300;
	}
	a {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		min-width: 0;
		color: inherit;
		text-decoration: none;
	}
	a:hover .t {
		text-decoration: underline;
	}
	.txt {
		display: grid;
		min-width: 0;
	}
	.t {
		font-weight: 650;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.first .t {
		font: 800 1.05rem var(--display);
	}
	.s {
		font-size: 0.76rem;
		color: var(--text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.stat {
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.first .stat {
		font: 800 1.2rem var(--display);
	}
	.more {
		margin-top: 0.5rem;
		font-size: 0.85rem;
	}
	@keyframes row-in {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
	}
</style>
