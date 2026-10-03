<script lang="ts">
	// A drop-in news card: the latest items for a team, a set of players, or everyone.
	//   <NewsFeed team="DET" />                     team news + injury report, "More →" /news/?team=DET
	//   <NewsFeed players={ids} mine={new Set(ids)} />  items tagging those players, marked as yours
	//   <NewsFeed limit={6} compact />              league-wide headlines
	// Two columns once the card is wide enough (container query), one otherwise.
	import { base } from '$app/paths';
	import NewsCard from '$lib/components/NewsCard.svelte';
	import { filterNews, updatedLabel, type NewsKind } from '$lib/news';
	import { newsResource } from '$lib/news.svelte';
	import type { NewsItem } from '$lib/types';

	let {
		team = null,
		players = null,
		kind = 'all',
		filter = null,
		mine = null,
		limit = 6,
		compact = false,
		title = 'Latest news',
		sub = null,
		more,
		empty = null,
		hideEmpty = false,
		id = undefined
	}: {
		team?: string | null;
		/** Only items tagging one of these gsis ids. */
		players?: Iterable<string> | null;
		kind?: NewsKind;
		/** Extra condition on items. */
		filter?: ((i: NewsItem) => boolean) | null;
		/** gsis ids to mark as the visitor's fantasy players. */
		mine?: Set<string> | null;
		limit?: number;
		compact?: boolean;
		title?: string;
		sub?: string | null;
		/** "More →" link: default /news/ (with ?team=); null hides it. */
		more?: string | null;
		/** Text when nothing matches. */
		empty?: string | null;
		/** Render nothing when the feed has loaded and nothing matches (or it failed): for pages
		 * where most subjects have no news, e.g. players. Place it where its arrival can't shift
		 * content above the fold. */
		hideEmpty?: boolean;
		/** Section id (for in-page links). */
		id?: string;
	} = $props();

	const feed = newsResource();
	const playerList = $derived(players ? [...players] : null);
	const items = $derived.by(() => {
		const all = feed.value?.items ?? [];
		const matched = filterNews(all, { team, players: playerList, kind });
		return (filter ? matched.filter(filter) : matched).slice(0, limit);
	});
	const moreHref = $derived(
		more === undefined ? `${base}/news/${team ? `?team=${team}` : ''}` : more
	);
	const report = $derived(feed.value?.injury_report);
	const uid = $props.id();
	const headId = `news-${uid}`;
	// "Updated 5 min ago" stays current while the page is open.
	let now = $state(Date.now());
	$effect(() => {
		const t = setInterval(() => (now = Date.now()), 60_000);
		return () => clearInterval(t);
	});
	const emptyText = $derived(
		empty ??
			(team
				? `No ${kind === 'injury' ? 'injury report items' : 'news'} for ${team} right now.`
				: 'No news right now.')
	);
</script>

{#if !hideEmpty || (feed.value && items.length)}
	<section class="card news-feed" aria-labelledby={headId} {id}>
		<div class="card-head">
			<h2 id={headId}>{title}</h2>
			{#if moreHref}<a href={moreHref}>More news →</a>{/if}
		</div>
		<p class="sub">
			{#if sub}{sub}{/if}
			{#if feed.value}
				<span class="stamp"
					>{updatedLabel(feed.value, now)}{#if report}{' · '}Week {report.week} injury report{/if}{#if feed.value.live}{' · '}live{/if}</span
				>
			{:else if !feed.error}
				<span class="stamp">&nbsp;</span>
			{/if}
		</p>
		{#if feed.error}
			<p class="muted state">News isn’t available yet: it appears after the next data build.</p>
		{:else if !feed.value}
			<div class="list" aria-busy="true" aria-label="Loading news">
				{#each Array(Math.min(limit, 4)) as _, i (i)}
					<div class="ph">
						<div class="skeleton" style="height: 12px; width: 35%"></div>
						<div class="skeleton" style="height: 16px; width: {88 - i * 9}%"></div>
						<div class="skeleton" style="height: 16px; width: 22%"></div>
					</div>
				{/each}
			</div>
		{:else if !items.length}
			<p class="muted state">{emptyText}</p>
		{:else}
			<ul class="list" class:compact>
				{#each items as item (item.id)}
					<li><NewsCard {item} {compact} {mine} {now} hideTeam={team} /></li>
				{/each}
			</ul>
		{/if}
		{#if feed.value && !feed.value.news_fetched_at && kind !== 'injury'}
			<p class="note muted">
				ESPN headlines weren’t reachable at the last data build; injury reports are always included.
			</p>
		{/if}
	</section>
{/if}

<style>
	.news-feed {
		container-type: inline-size;
	}
	.sub {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 0.5rem;
		margin-bottom: 0.25rem;
	}
	.stamp {
		color: var(--text-muted);
		font-size: 0.8rem;
	}
	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		column-gap: 1.5rem;
	}
	@container (min-width: 720px) {
		.list.compact,
		.list[aria-busy='true'] {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	.ph {
		display: grid;
		gap: 0.4rem;
		padding: 0.6rem 0;
		border-bottom: 1px solid var(--grid);
		min-height: 5.25rem;
	}
	.state {
		margin: 0.5rem 0 0;
		font-size: 0.9rem;
	}
	.note {
		margin: 0.6rem 0 0;
		font-size: 0.78rem;
	}
</style>
