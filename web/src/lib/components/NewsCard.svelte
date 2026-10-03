<script lang="ts">
	// One news or injury-report item. Headlines of ESPN items open the story in a new tab;
	// injury items link to the player's page when one exists. Teams are linked badges, players
	// linked chips (only for players with a page); `mine` rings the visitor's fantasy players.
	import { base } from '$app/paths';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { ago, changeLabel, injuryTone, statusShort } from '$lib/news';
	import { hasPlayerPage } from '$lib/playerPages.svelte';
	import type { NewsItem } from '$lib/types';

	let {
		item,
		compact = false,
		mine = null,
		now = Date.now(),
		hideTeam = null
	}: {
		item: NewsItem;
		compact?: boolean;
		/** gsis ids on the visitor's fantasy roster. */
		mine?: Set<string> | null;
		now?: number;
		/** Leave this team's badge out (a feed already filtered to it). */
		hideTeam?: string | null;
	} = $props();

	const injury = $derived(item.kind === 'injury');
	const tone = $derived(injury ? injuryTone(item) : null);
	const change = $derived(injury ? changeLabel(item) : null);
	const isMine = $derived(!!mine && item.players.some((p) => mine.has(p)));
	const playerHref = (id: string | null) =>
		id && hasPlayerPage(id) ? `${base}/player/?id=${id}` : null;
	const injuryHref = $derived(injury ? playerHref(item.players[0] ?? null) : null);
	const teams = $derived(item.teams.filter((t) => t !== hideTeam).slice(0, compact ? 2 : 4));
	const athletes = $derived(injury ? [] : item.athletes.slice(0, compact ? 2 : 4));
	const when = $derived(
		injury && item.week != null
			? `Week ${item.week} ${item.preliminary ? 'practice report' : 'injury report'}`
			: ago(item.published, now)
	);
	let imageFailed = $state(false);
</script>

<article class="item" class:compact class:injury class:mine={isMine} data-tone={tone}>
	{#if !compact}
		<div class="thumb" aria-hidden="true">
			{#if injury}
				{@const word = item.status ?? statusShort(item)}
				<span class="status" class:long={word.length > 5}>{word}</span>
				{#if item.position}<span class="pos">{item.position}</span>{/if}
			{:else if item.image && !imageFailed}
				<img
					src={item.image}
					alt=""
					loading="lazy"
					decoding="async"
					referrerpolicy="no-referrer"
					onerror={() => (imageFailed = true)}
				/>
			{:else}
				<span class="mark">{item.label ?? 'NFL'}</span>
			{/if}
		</div>
	{/if}
	<div class="body">
		<div class="meta">
			{#if injury}
				{#if compact}<span class="status-chip">{statusShort(item)}</span>{/if}
			{:else}
				<span class="kind">{item.source}</span>
				{#if item.label}<span class="tag">{item.label}</span>{/if}
				{#if item.premium}<span class="tag">ESPN+</span>{/if}
			{/if}
			{#if !injury}<span class="dot" aria-hidden="true">·</span>{/if}
			<time
				class:kind={injury}
				datetime={item.published}
				title={new Date(item.published).toLocaleString()}>{when}</time
			>
			{#if change}<span class="change" data-change={item.change}>{change}</span>{/if}
			{#if isMine}<span class="yours">Your player</span>{/if}
		</div>
		<h3 class="headline">
			{#if item.url}
				<a href={item.url} target="_blank" rel="noopener"
					>{item.headline}<span class="sr-only"> (opens in a new tab)</span><span
						class="ext"
						aria-hidden="true">↗</span
					></a
				>
			{:else if injuryHref}
				<a href={injuryHref}>{item.headline}</a>
			{:else}
				{item.headline}
			{/if}
		</h3>
		{#if item.description && (!compact || injury)}
			<p class="desc" class:one={compact}>{item.description}</p>
		{/if}
		{#if teams.length || athletes.length}
			<div class="tags">
				{#each teams as t (t)}
					<TeamBadge team={t} link />
				{/each}
				{#each athletes as a (a.name)}
					{@const href = playerHref(a.id)}
					{#if href}
						<a class="player" class:own={!!a.id && !!mine?.has(a.id)} {href}>{a.name}</a>
					{:else}
						<span class="player" class:own={!!a.id && !!mine?.has(a.id)}>{a.name}</span>
					{/if}
				{/each}
			</div>
		{/if}
	</div>
</article>

<style>
	.item {
		--tone: var(--border-strong);
		display: grid;
		grid-template-columns: 7.5rem minmax(0, 1fr);
		gap: 0.9rem;
		padding: 0.85rem 0;
		border-bottom: 1px solid var(--grid);
	}
	.item.compact {
		grid-template-columns: minmax(0, 1fr);
		padding: 0.6rem 0;
	}
	.item[data-tone='out'] {
		--tone: var(--bad);
	}
	.item[data-tone='doubtful'] {
		--tone: color-mix(in srgb, var(--bad) 70%, var(--warning));
	}
	.item[data-tone='questionable'] {
		--tone: var(--warning);
	}
	.item[data-tone='cleared'] {
		--tone: var(--good);
	}
	.item.compact.injury {
		padding-left: 0.65rem;
		box-shadow: inset 3px 0 0 var(--tone);
	}
	.item.mine {
		background: linear-gradient(
			90deg,
			color-mix(in srgb, var(--fav) 10%, transparent),
			transparent 70%
		);
	}
	.thumb {
		position: relative;
		aspect-ratio: 16 / 9;
		border-radius: var(--radius-sm);
		overflow: hidden;
		background:
			radial-gradient(120% 120% at 0% 0%, var(--accent-soft), transparent 60%), var(--surface-2);
		border: 1px solid var(--border);
		display: grid;
		place-items: center;
		align-self: start;
	}
	.thumb img {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	.mark {
		font: 800 0.8rem/1 var(--display);
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-muted);
	}
	.injury .thumb {
		background: color-mix(in srgb, var(--tone) 22%, var(--surface));
		border-color: color-mix(in srgb, var(--tone) 45%, transparent);
		align-content: center;
		gap: 0.15rem;
	}
	.status {
		font: 800 1.05rem/1 var(--display);
		font-stretch: 112%;
		color: var(--text-primary);
		text-transform: uppercase;
		letter-spacing: 0.02em;
	}
	.status.long {
		font-size: 0.78rem;
	}
	.pos {
		font-size: 0.72rem;
		font-weight: 700;
		color: var(--text-secondary);
	}
	.body {
		min-width: 0;
		display: grid;
		gap: 0.3rem;
		align-content: start;
	}
	.meta {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.25rem 0.45rem;
		font-size: 0.76rem;
		color: var(--text-muted);
	}
	.kind {
		font-weight: 700;
		color: var(--text-secondary);
	}
	.tag,
	.change,
	.yours,
	.status-chip {
		padding: 0.05rem 0.4rem;
		border-radius: 999px;
		font-size: 0.7rem;
		font-weight: 700;
		background: var(--surface-2);
		border: 1px solid var(--border);
		color: var(--text-secondary);
	}
	.status-chip {
		background: color-mix(in srgb, var(--tone) 24%, var(--surface));
		border-color: color-mix(in srgb, var(--tone) 50%, transparent);
		color: var(--text-primary);
	}
	.change[data-change='worse'],
	.change[data-change='new'] {
		background: var(--bad-wash);
		color: var(--text-primary);
	}
	.change[data-change='better'] {
		background: var(--good-wash);
		color: var(--text-primary);
	}
	.yours {
		background: color-mix(in srgb, var(--fav) 20%, var(--surface));
		border-color: color-mix(in srgb, var(--fav) 55%, transparent);
		color: var(--text-primary);
	}
	.headline {
		margin: 0;
		font: 650 1rem/1.3 var(--font);
		letter-spacing: -0.005em;
		color: var(--text-primary);
		display: -webkit-box;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.compact .headline {
		font-size: 0.92rem;
		-webkit-line-clamp: 2;
		line-clamp: 2;
	}
	.headline a {
		color: inherit;
		text-decoration: none;
	}
	.headline a:hover {
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.ext {
		margin-left: 0.25em;
		font-size: 0.8em;
		color: var(--text-muted);
	}
	.desc {
		margin: 0;
		font-size: 0.86rem;
		color: var(--text-secondary);
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.desc.one {
		font-size: 0.8rem;
		-webkit-line-clamp: 1;
		line-clamp: 1;
	}
	.tags {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.85rem;
	}
	.player {
		display: inline-flex;
		align-items: center;
		min-height: 24px;
		padding: 0 0.5rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		background: var(--surface-2);
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--text-secondary);
		text-decoration: none;
		white-space: nowrap;
	}
	a.player {
		color: var(--accent-ink);
	}
	a.player:hover {
		border-color: var(--border-strong);
		text-decoration: underline;
	}
	.player.own {
		box-shadow: 0 0 0 1.5px var(--fav);
	}
	@media (max-width: 560px) {
		.item:not(.compact) {
			grid-template-columns: 5.5rem minmax(0, 1fr);
			gap: 0.7rem;
		}
		.status {
			font-size: 0.9rem;
		}
		.status.long {
			font-size: 0.66rem;
		}
	}
</style>
