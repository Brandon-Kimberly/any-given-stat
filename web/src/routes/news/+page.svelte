<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import { base } from '$app/paths';
	import { page } from '$app/state';
	import LoadError from '$lib/components/LoadError.svelte';
	import NewsCard from '$lib/components/NewsCard.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { fantasyIds } from '$lib/fantasy/data.svelte';
	import { fantasy } from '$lib/fantasy/league.svelte';
	import { FANTASY_POSITIONS, dayLabel, filterNews, groupByDay, updatedLabel } from '$lib/news';
	import { newsResource } from '$lib/news.svelte';
	import { teamMeta, teamName } from '$lib/teams.svelte';
	import type { NewsItem } from '$lib/types';
	import { setParam } from '$lib/url';

	type View = 'all' | 'news' | 'injury' | 'mine';
	const VIEWS: { id: View; label: string }[] = [
		{ id: 'all', label: 'All' },
		{ id: 'news', label: 'Headlines' },
		{ id: 'injury', label: 'Injuries' },
		{ id: 'mine', label: 'My fantasy team' }
	];
	const PAGE = 30;

	const feed = newsResource();
	const ids = fantasyIds();

	// ?team=DET&view=injury: deep links from team pages, kept in sync with the controls.
	const isView = (v: string | null): v is View => VIEWS.some((x) => x.id === v);
	let team = $state(page.url.searchParams.get('team')?.toUpperCase() ?? '');
	let view = $state<View>(
		isView(page.url.searchParams.get('view')) ? (page.url.searchParams.get('view') as View) : 'all'
	);
	let shown = $state(PAGE);
	afterNavigate(() => {
		team = page.url.searchParams.get('team')?.toUpperCase() ?? '';
		const v = page.url.searchParams.get('view');
		view = isView(v) ? v : 'all';
	});
	$effect(() => setParam('team', team || null));
	$effect(() => setParam('view', view === 'all' ? null : view));
	$effect(() => {
		void team;
		void view;
		shown = PAGE;
	});

	// The visitor's fantasy roster (gsis ids), once a league is connected and a team picked.
	const owners = $derived(ids.value ? fantasy.ownership(ids.value) : null);
	const mine = $derived(
		owners ? new Set([...owners].filter(([, o]) => o.mine).map(([id]) => id)) : null
	);
	const hasRoster = $derived(!!fantasy.league && !!fantasy.myTeam);

	let now = $state(Date.now());
	$effect(() => {
		const t = setInterval(() => (now = Date.now()), 60_000);
		return () => clearInterval(t);
	});

	const all = $derived(feed.value?.items ?? []);
	const teams = $derived(
		Object.keys(teamMeta.byTeam).length
			? Object.keys(teamMeta.byTeam).sort()
			: [...new Set(all.flatMap((i) => i.teams))].sort()
	);
	const items = $derived.by<NewsItem[]>(() => {
		if (view === 'mine') {
			if (!mine) return [];
			return filterNews(all, { team: team || null, players: mine });
		}
		return filterNews(all, { team: team || null, kind: view });
	});
	// "All": headlines stay scannable, so each day shows its top injury items (the report is
	// ordered biggest change first) and a link to the rest.
	const INJURY_CAP = 5;
	const listed = $derived.by(() => {
		if (view !== 'all') return { items, hidden: new Map<string, number>() };
		const today = new Date(now);
		const seen = new Map<string, number>();
		const hidden = new Map<string, number>();
		const kept = items.filter((i) => {
			if (i.kind !== 'injury') return true;
			const day = dayLabel(i.published, today);
			const n = (seen.get(day) ?? 0) + 1;
			seen.set(day, n);
			if (n <= INJURY_CAP) return true;
			hidden.set(day, (hidden.get(day) ?? 0) + 1);
			return false;
		});
		return { items: kept, hidden };
	});
	const groups = $derived(groupByDay(listed.items.slice(0, shown), new Date(now)));
	const report = $derived(feed.value?.injury_report ?? null);

	// Injury report summary for the current team filter.
	const injuries = $derived(filterNews(all, { team: team || null, kind: 'injury' }));
	const counts = $derived({
		Out: injuries.filter((i) => i.status === 'Out').length,
		Doubtful: injuries.filter((i) => i.status === 'Doubtful').length,
		Questionable: injuries.filter((i) => i.status === 'Questionable').length,
		Cleared: injuries.filter((i) => i.change === 'cleared').length
	});
	const keyOut = $derived(
		injuries
			.filter(
				(i) =>
					(i.status === 'Out' || i.status === 'Doubtful') && FANTASY_POSITIONS.has(i.position ?? '')
			)
			.slice(0, 10)
	);
	const newsCount = $derived(all.filter((i) => i.kind === 'news').length);

	function emptyText(): string {
		if (view === 'mine') {
			if (!hasRoster) return '';
			return team
				? `Nothing on your players from ${teamName(team)} right now.`
				: 'No news or injury updates for your players right now.';
		}
		if (view === 'news' && !feed.value?.news_fetched_at)
			return 'ESPN headlines weren’t reachable at the last data build. Injury reports are still here.';
		const what = view === 'injury' ? 'injury report items' : view === 'news' ? 'headlines' : 'news';
		return team ? `No ${what} for ${teamName(team)} right now.` : `No ${what} right now.`;
	}
</script>

<svelte:head><title>NFL news · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">News</div>
	<h1>NFL news and injury reports</h1>
	<p class="lede">
		The latest headlines from ESPN next to every status on this week’s official injury report, with
		what changed since the last one. Filter to a team, or to the players on your fantasy roster.
	</p>
</section>

<div class="toolbar">
	<div class="seg" role="group" aria-label="Show">
		{#each VIEWS as v (v.id)}
			<button type="button" aria-pressed={view === v.id} onclick={() => (view = v.id)}
				>{v.label}</button
			>
		{/each}
	</div>
	<label class="field">
		Team
		<select bind:value={team} class="team-select">
			<option value="">All teams</option>
			{#each teams as t (t)}<option value={t}>{teamName(t)}</option>{/each}
		</select>
	</label>
	<span class="stamp" aria-live="polite">
		{#if feed.value}
			{updatedLabel(feed.value, now)}{#if report}{' · '}Week {report.week} injury report{/if}
		{/if}
	</span>
</div>

{#if feed.error}
	<LoadError message={feed.error} />
{:else if !feed.value}
	<div class="layout">
		<Skeleton height={640} rows={4} />
		<Skeleton height={260} rows={2} />
	</div>
{:else}
	<div class="layout">
		<div class="feed">
			{#if view === 'mine' && !hasRoster}
				<div class="callout info">
					{#if fantasy.league}
						Pick your team on the <a href="{base}/fantasy/">Fantasy page</a> to see news for your players.
					{:else}
						Connect your Sleeper or ESPN league on the <a href="{base}/fantasy/">Fantasy page</a> to see
						news and injury updates for the players on your roster.
					{/if}
				</div>
			{:else if !items.length}
				<div class="card empty">
					<p class="muted">{emptyText()}</p>
					{#if team || view !== 'all'}
						<button
							type="button"
							class="ghost"
							onclick={() => {
								team = '';
								view = 'all';
							}}>Show all news</button
						>
					{/if}
				</div>
			{:else}
				{#each groups as g, gi (g.label)}
					<section class="card day" aria-labelledby="day-{gi}">
						<h2 class="day-label" id="day-{gi}">{g.label}</h2>
						<ul>
							{#each g.items as item (item.id)}
								<li><NewsCard {item} {mine} {now} hideTeam={team || null} /></li>
							{/each}
						</ul>
						{#if listed.hidden.get(g.label)}
							<button
								type="button"
								class="ghost rest"
								onclick={() => {
									view = 'injury';
									scrollTo({ top: 0 });
								}}>{listed.hidden.get(g.label)} more injury report items →</button
							>
						{/if}
					</section>
				{/each}
				{#if listed.items.length > shown}
					<button type="button" class="more" onclick={() => (shown += PAGE)}>
						Show more ({listed.items.length - shown} left)
					</button>
				{/if}
			{/if}
		</div>

		<aside class="side">
			<section class="card" aria-labelledby="report-title">
				<h2 id="report-title">
					{report ? `Week ${report.week} injury report` : 'Injury report'}
				</h2>
				<p class="sub">
					{team ? teamName(team) : 'All teams'}: game statuses on the latest official report.
				</p>
				{#if injuries.length}
					<dl class="counts">
						{#each Object.entries(counts) as [label, n] (label)}
							<div data-tone={label.toLowerCase()}>
								<dt>{label}</dt>
								<dd class="tnum">{n}</dd>
							</div>
						{/each}
					</dl>
					{#if keyOut.length}
						<h3>Skill players out or doubtful</h3>
						<ul class="key">
							{#each keyOut as i (i.id)}
								<li>
									<TeamBadge team={i.teams[0]} link />
									<span class="who">{i.athletes[0]?.name}</span>
									<span class="muted">{i.position}</span>
									<span class="st" data-tone={i.status?.toLowerCase()}>{i.status}</span>
								</li>
							{/each}
						</ul>
					{/if}
					<button
						type="button"
						class="ghost rest"
						onclick={() => {
							view = 'injury';
							scrollTo({ top: 0 });
						}}
						disabled={view === 'injury'}>All injury items →</button
					>
				{:else}
					<p class="muted">No injury report items{team ? ` for ${teamName(team)}` : ''}.</p>
				{/if}
			</section>
			<section class="card about">
				<h2>Sources</h2>
				<p>
					Headlines: ESPN ({newsCount} stories{feed.value.live
						? ', refreshed every 10 minutes while the local app runs'
						: ', as of the last data build'}). Injury reports: the NFL’s official report via
					nflverse. Report times are estimates: game statuses come out two days before a game (one
					for Thursday games).
				</p>
			</section>
		</aside>
	</div>
{/if}

<style>
	.stamp {
		margin-left: auto;
		font-size: 0.82rem;
		color: var(--text-muted);
		min-height: 1.2em;
	}
	.team-select {
		min-width: 12rem;
	}
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 20rem;
		gap: 1rem;
		align-items: start;
	}
	@media (max-width: 960px) {
		.layout {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.feed {
		display: grid;
		gap: 1rem;
		min-width: 0;
	}
	.day {
		padding-top: 0.75rem;
		padding-bottom: 0.25rem;
	}
	.day-label {
		margin: 0;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-muted);
	}
	.day ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.day li:last-child :global(.item) {
		border-bottom: 0;
	}
	.rest {
		margin: 0.25rem 0 0.6rem;
		font-size: 0.85rem;
		color: var(--accent-ink);
	}
	.empty {
		display: grid;
		gap: 0.75rem;
		justify-items: start;
	}
	.empty p {
		margin: 0;
	}
	.more {
		justify-self: center;
		min-height: 36px;
		padding: 0.35rem 1.1rem;
		border-radius: 999px;
		border: 1px solid var(--border-strong);
		background: var(--surface);
		cursor: pointer;
	}
	.more:hover {
		background: var(--surface-2);
	}
	.side {
		display: grid;
		gap: 1rem;
		position: sticky;
		top: 5rem;
	}
	@media (max-width: 960px) {
		.side {
			position: static;
		}
	}
	.side h2 {
		margin: 0 0 0.25rem;
	}
	.side h3 {
		margin: 1rem 0 0.4rem;
		font-size: 0.85rem;
	}
	.counts {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.4rem;
		margin: 0;
	}
	.counts div {
		padding: 0.45rem 0.4rem;
		border-radius: var(--radius-sm);
		background: color-mix(in srgb, var(--tone, var(--border-strong)) 16%, var(--surface));
		border: 1px solid color-mix(in srgb, var(--tone, var(--border-strong)) 40%, transparent);
		text-align: center;
	}
	[data-tone='out'] {
		--tone: var(--bad);
	}
	[data-tone='doubtful'] {
		--tone: color-mix(in srgb, var(--bad) 70%, var(--warning));
	}
	[data-tone='questionable'] {
		--tone: var(--warning);
	}
	[data-tone='cleared'] {
		--tone: var(--good);
	}
	.counts dt {
		font-size: 0.68rem;
		font-weight: 700;
		color: var(--text-secondary);
	}
	.counts dd {
		margin: 0;
		font: 800 1.35rem/1.1 var(--display);
		color: var(--text-primary);
	}
	.key {
		list-style: none;
		margin: 0 0 0.75rem;
		padding: 0;
	}
	.key li {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.3rem 0;
		border-bottom: 1px solid var(--grid);
		font-size: 0.86rem;
	}
	.who {
		font-weight: 600;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.st {
		margin-left: auto;
		padding: 0.05rem 0.45rem;
		border-radius: 999px;
		font-size: 0.7rem;
		font-weight: 700;
		background: color-mix(in srgb, var(--tone) 22%, var(--surface));
		color: var(--text-primary);
	}
	.about p {
		margin: 0;
		font-size: 0.82rem;
		color: var(--text-secondary);
	}
</style>
