<script lang="ts">
	// Drive chart (every possession on one field) and a play-by-play feed grouped by drive.
	// Each play gets a headline built from its structured fields (playText.ts), a mini field
	// and its EPA / win-probability swing; the official description is one click away.
	// Hovering a play reports its elapsed time so the page can mark it on the WP chart, and
	// highlights its drive in the chart; selecting a drive in the chart opens it in the feed.
	import { tick } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';
	import { elapsedAt } from '$lib/games';
	import {
		decodePlays,
		headline,
		isKey,
		nameStyler,
		quarterLabel,
		quarterName,
		scoreEvent,
		searchText,
		situation,
		spot,
		yards,
		type Play
	} from '$lib/playText';
	import { matchupColors } from '$lib/teams.svelte';
	import type { Drive, GamePlays } from '$lib/types';
	import DriveChart from './DriveChart.svelte';
	import PlayRow, { type FeedItem } from './PlayRow.svelte';
	import TeamBadge from './TeamBadge.svelte';

	let {
		data,
		home,
		away,
		onhover
	}: {
		data: GamePlays;
		home: string;
		away: string;
		onhover?: (elapsed: number | null) => void;
	} = $props();

	const colors = $derived(matchupColors(away, home));
	const colorOf = (t: string) => (t === home ? colors.home : colors.away);

	// ---- Plays → feed items (headline, score, search text), built once per game.
	const plays = $derived(decodePlays(data));
	const items = $derived.by((): (FeedItem & { end: boolean })[] => {
		const name = nameStyler(plays);
		return plays.map((p, k) => {
			const h = headline(p, name);
			const score = scoreEvent(p, plays[k - 1], home, away);
			const end = p.kind === 'end' || (!p.kind && /^END (QUARTER|GAME|OF)/.test(p.desc));
			return {
				p,
				h,
				score,
				sit: situation(p, home, away),
				key: isKey(p, score),
				text: searchText(p, h),
				end
			};
		});
	});

	// ---- Drives: consecutive plays with the same drive number.
	type Group = { gi: number; n: number | null; drive: Drive | null; items: typeof items };
	const driveByN = $derived(new Map(data.drives.map((d) => [d.n, d])));
	const groups = $derived.by(() => {
		const out: Group[] = [];
		for (const it of items) {
			const last = out.at(-1);
			const n = it.p.drive ?? last?.n ?? null;
			if (!last || last.n !== n)
				out.push({
					gi: out.length,
					n,
					drive: n == null ? null : (driveByN.get(n) ?? null),
					items: []
				});
			out.at(-1)!.items.push(it);
		}
		return out;
	});

	// ---- Filters.
	type Filter = 'all' | 'key' | 'score' | 'turnover' | 'big' | 'fourth' | 'penalty';
	const FILTERS: { key: Filter; label: string; test: (it: FeedItem) => boolean }[] = [
		{ key: 'all', label: 'All', test: () => true },
		{ key: 'key', label: 'Key plays', test: (it) => it.key },
		{ key: 'score', label: 'Scoring', test: (it) => it.score != null },
		{ key: 'turnover', label: 'Turnovers', test: (it) => /[IF]/.test(it.p.flags) },
		{ key: 'big', label: 'Explosive', test: (it) => it.p.flags.includes('X') },
		{ key: 'fourth', label: '4th downs', test: (it) => it.p.flags.includes('4') },
		{ key: 'penalty', label: 'Penalties', test: (it) => it.p.flags.includes('P') }
	];
	let filter = $state<Filter>('all');
	let side = $state<'both' | 'away' | 'home'>('both');
	let query = $state('');
	const q = $derived(query.trim().toLowerCase());
	const filtering = $derived(filter !== 'all' || side !== 'both' || q !== '');

	const counts = $derived(
		Object.fromEntries(
			FILTERS.map((f) => [f.key, items.filter((it) => !it.end && f.test(it)).length])
		) as Record<Filter, number>
	);
	const shown = $derived.by(() => {
		const f = FILTERS.find((x) => x.key === filter)!;
		const team = side === 'home' ? home : side === 'away' ? away : null;
		const test = (it: FeedItem & { end: boolean }) =>
			!it.end && f.test(it) && (!team || it.p.team === team) && (!q || it.text.includes(q));
		return groups
			.map((g) => ({ ...g, visible: filtering ? g.items.filter(test) : g.items }))
			.filter((g) => g.visible.some((it) => !it.end));
	});
	const matchCount = $derived(
		shown.reduce((s, g) => s + g.visible.filter((it) => !it.end).length, 0)
	);

	// ---- Open drives and plays. Unfiltered, the latest drive starts open; while filtering,
	// every drive with a match is open unless closed.
	const open = new SvelteSet<number>();
	const closedWhileFiltering = new SvelteSet<number>();
	const openPlays = new SvelteSet<number>();
	let openedFor: GamePlays | null = null;
	$effect.pre(() => {
		if (data === openedFor) return;
		openedFor = data;
		open.clear();
		openPlays.clear();
		if (groups.length) open.add(groups.length - 1);
	});
	const isOpen = (gi: number) => (filtering ? !closedWhileFiltering.has(gi) : open.has(gi));
	function toggleDrive(gi: number) {
		const set = filtering ? closedWhileFiltering : open;
		if (set.has(gi)) set.delete(gi);
		else set.add(gi);
	}
	const allOpen = $derived(shown.every((g) => isOpen(g.gi)));
	function toggleAll() {
		const wantOpen = !allOpen;
		for (const g of shown) {
			if (filtering) {
				if (wantOpen) closedWhileFiltering.delete(g.gi);
				else closedWhileFiltering.add(g.gi);
			} else if (wantOpen) open.add(g.gi);
			else open.delete(g.gi);
		}
	}
	function togglePlay(i: number) {
		if (openPlays.has(i)) openPlays.delete(i);
		else openPlays.add(i);
	}
	function setFilter(f: Filter) {
		filter = f;
		closedWhileFiltering.clear();
	}
	function setSide(s: typeof side) {
		side = s;
		closedWhileFiltering.clear();
	}

	// ---- Cross-links with the drive chart and the WP chart.
	let hotDrive = $state<number | null>(null);
	let flash = $state<number | null>(null);
	let feed = $state<HTMLElement>();
	let flashTimer: ReturnType<typeof setTimeout> | undefined;

	function hoverPlay(p: Play | null) {
		hotDrive = p?.drive ?? null;
		onhover?.(p ? elapsedAt(p.qtr, p.time) : null);
	}
	async function pickDrive(n: number) {
		const g = groups.find((x) => x.n === n);
		if (!g) return;
		if (filtering && !shown.some((x) => x.gi === g.gi)) {
			filter = 'all';
			side = 'both';
			query = '';
		}
		if (filtering) closedWhileFiltering.delete(g.gi);
		else open.add(g.gi);
		await tick();
		const el = feed?.querySelector<HTMLElement>(`#pbp-drive-${g.gi}`);
		if (!el) return;
		const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
		el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
		el.querySelector<HTMLElement>('.drive-head')?.focus({ preventScroll: true });
		flash = g.gi;
		clearTimeout(flashTimer);
		flashTimer = setTimeout(() => (flash = null), 1600);
	}

	// Arrow keys move between drive headers and plays.
	function nav(e: KeyboardEvent) {
		if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
		const all = [...(feed?.querySelectorAll<HTMLElement>('[data-nav]') ?? [])];
		const k = all.indexOf(e.currentTarget as HTMLElement);
		const next = all[k + (e.key === 'ArrowDown' ? 1 : -1)];
		if (!next) return;
		e.preventDefault();
		next.focus();
	}

	// ---- Drive headers.
	function driveResult(g: Group): string {
		const r = g.drive?.result;
		if (!r) return g.n == null ? 'Plays' : 'Drive';
		if (r === 'Turnover') {
			const last = [...g.items].reverse().find((it) => /[IF]/.test(it.p.flags));
			return last?.p.flags.includes('I') ? 'Interception' : last ? 'Fumble' : 'Turnover';
		}
		return (
			{
				'Opp touchdown': 'Defensive TD',
				'Missed field goal': 'Missed FG',
				'Turnover on downs': 'Turnover on downs'
			}[r] ?? r
		);
	}
	function driveStats(d: Drive): string {
		const yds = d.yards == null ? null : yards(d.yards)!.replace('no gain', '0 yds');
		return [`${d.plays} play${d.plays === 1 ? '' : 's'}`, yds, d.top].filter(Boolean).join(' · ');
	}
	const scoreAfter = (g: Group) =>
		[...g.items].reverse().find((it) => it.p.homeScore != null && it.p.awayScore != null)?.p;
	/** Quarter of a group's first real play. */
	const groupQtr = (g: Group) => (g.items.find((it) => !it.end) ?? g.items[0]).p.qtr;
	/** Score before the first play of quarter q. */
	function scoreBefore(q: number): Play | undefined {
		let last: Play | undefined;
		for (const p of plays) {
			if (p.qtr >= q) break;
			if (p.homeScore != null && p.awayScore != null) last = p;
		}
		return last;
	}
</script>

<DriveChart
	drives={data.drives}
	{home}
	{away}
	{colors}
	hot={hotDrive}
	onpick={pickDrive}
	onhover={(n) => (hotDrive = n)}
/>

<section class="card" id="play-by-play">
	<div class="card-head">
		<h2>Play by play</h2>
		<button class="ghost toggle-all" onclick={toggleAll} disabled={!shown.length}
			>{allOpen ? 'Collapse all' : 'Expand all'}</button
		>
	</div>
	<p class="sub">
		Drive by drive. Select a play for the official description. Field bars run like the drive chart: <TeamBadge
			team={away}
		/> →, ← <TeamBadge team={home} />; the gold line is the line to gain.
	</p>
	<div class="toolbar">
		<div class="seg" role="group" aria-label="Filter plays">
			{#each FILTERS as f (f.key)}
				<button aria-pressed={filter === f.key} onclick={() => setFilter(f.key)}
					>{f.label} <span class="count">{counts[f.key]}</span></button
				>
			{/each}
		</div>
		<div class="seg" role="group" aria-label="Offense">
			<button aria-pressed={side === 'both'} onclick={() => setSide('both')}>Both</button>
			<button aria-pressed={side === 'away'} onclick={() => setSide('away')}>{away}</button>
			<button aria-pressed={side === 'home'} onclick={() => setSide('home')}>{home}</button>
		</div>
		<input
			type="search"
			class="search"
			placeholder="Search plays: player, penalty…"
			aria-label="Search plays"
			bind:value={query}
			oninput={() => closedWhileFiltering.clear()}
		/>
	</div>
	<p class="sr-only" aria-live="polite">
		{filtering ? `${matchCount} play${matchCount === 1 ? '' : 's'} match` : ''}
	</p>

	<ol class="feed" bind:this={feed} onmouseleave={() => hoverPlay(null)}>
		{#each shown as g, k (g.gi)}
			{@const d = g.drive}
			{@const qtr = groupQtr(g)}
			{@const prevQtr = k > 0 ? groupQtr(shown[k - 1]) : null}
			{@const after = scoreAfter(g)}
			{@const scored = (d?.points ?? 0) > 0}
			{@const team = d?.posteam ?? g.items[0].p.team}
			{@const gOpen = isOpen(g.gi)}
			{#if qtr !== prevQtr}
				{@const before = qtr > 1 ? scoreBefore(qtr) : undefined}
				<li class="quarter">
					<h3>{qtr === 3 && prevQtr != null ? 'Halftime · ' : ''}{quarterName(qtr)}</h3>
					{#if before}<span class="qscore"
							>{away} {before.awayScore} · {home} {before.homeScore}</span
						>{/if}
				</li>
			{/if}
			<li
				class="group"
				class:flash={flash === g.gi}
				class:hot={hotDrive != null && hotDrive === g.n}
				id="pbp-drive-{g.gi}"
				style:--team={colorOf(team)}
			>
				<h4>
					<button
						class="drive-head"
						data-nav
						aria-expanded={gOpen}
						aria-controls={gOpen ? `pbp-drive-${g.gi}-plays` : undefined}
						onclick={() => toggleDrive(g.gi)}
						onkeydown={nav}
						onmouseenter={() => (hotDrive = g.n)}
						onmouseleave={() => (hotDrive = null)}
					>
						<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
						<TeamBadge {team} />
						<span class="dres" class:scored>{driveResult(g)}</span>
						<span class="dmeta">
							{#if d}<span class="dstats">{driveStats(d)}</span>{/if}
							<span class="dwhen"
								>{d?.qtr ? quarterLabel(d.qtr) : quarterLabel(qtr)}
								{d?.start_clock ?? g.items[0].p.time ?? ''}{d?.start_yl != null
									? ` · from ${spot(team, d.start_yl, home, away)}`
									: ''}</span
							>
							{#if filtering}<span class="dmatch"
									>{g.visible.filter((it) => !it.end).length} of {g.items.filter((it) => !it.end)
										.length} plays</span
								>{/if}
						</span>
						<span class="dside">
							{#if scored && after}
								<span class="dscore"
									><span class:lead-side={team === away}>{away} {after.awayScore}</span>
									<span class:lead-side={team === home}>{home} {after.homeScore}</span></span
								>
							{/if}
						</span>
					</button>
				</h4>
				{#if gOpen}
					<ol class="plays" id="pbp-drive-{g.gi}-plays">
						{#each g.visible as it (it.p.i)}
							{#if it.end}
								<li class="qend">
									{it.p.desc
										.replace(/^END QUARTER (\d)/, (_, n) => `End of ${quarterName(+n)}`)
										.replace('END GAME', 'End of game')}
									{#if it.p.awayScore != null}· {away}
										{it.p.awayScore}, {home}
										{it.p.homeScore}{/if}
								</li>
							{:else}
								<PlayRow
									item={it}
									{home}
									{away}
									{colors}
									open={openPlays.has(it.p.i)}
									showTeam={it.p.team !== team}
									ontoggle={() => togglePlay(it.p.i)}
									onnav={nav}
									onhover={hoverPlay}
								/>
							{/if}
						{/each}
					</ol>
				{/if}
			</li>
		{:else}
			<li class="empty muted">No plays match.</li>
		{/each}
	</ol>
</section>

<style>
	.toggle-all {
		font-size: 0.8rem;
		min-height: 28px;
		color: var(--text-secondary);
	}
	.sub :global(.team) {
		vertical-align: -0.1em;
	}
	.toolbar {
		margin-bottom: 0.85rem;
	}
	.count {
		font-size: 0.72rem;
		color: var(--text-muted);
		margin-left: 0.15rem;
	}
	.search {
		flex: 1 1 14rem;
		min-width: 0;
		max-width: 22rem;
	}
	.feed {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.4rem;
	}
	.quarter {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.75rem;
		margin-top: 0.6rem;
		padding: 0 0.2rem 0.2rem;
		border-bottom: 1px solid var(--border-strong);
	}
	.quarter:first-child {
		margin-top: 0;
	}
	.quarter h3 {
		margin: 0;
		font-size: 0.75rem;
		font-weight: 800;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-secondary);
	}
	.qscore {
		font-size: 0.78rem;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.group {
		border: 1px solid var(--border);
		border-left: 3px solid var(--team);
		border-radius: 10px;
		overflow: hidden;
		scroll-margin-top: 5.5rem;
		transition: box-shadow 0.2s;
	}
	.group.hot {
		box-shadow: 0 0 0 1px var(--border-strong);
	}
	.group.flash {
		box-shadow:
			0 0 0 3px var(--accent-soft),
			0 0 0 1px var(--accent);
	}
	h4 {
		margin: 0;
		font: inherit;
	}
	.drive-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 0.65rem;
		width: 100%;
		min-height: 44px;
		padding: 0.45rem 0.75rem 0.45rem 0.5rem;
		border: 0;
		border-radius: 0;
		background: var(--surface);
		color: inherit;
		text-align: left;
		font-size: 0.85rem;
	}
	.drive-head:hover {
		background: var(--surface-2);
	}
	.drive-head:active {
		transform: none;
	}
	.drive-head:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
	.chev {
		width: 16px;
		height: 16px;
		fill: none;
		stroke: var(--text-muted);
		stroke-width: 2.2;
		stroke-linecap: round;
		stroke-linejoin: round;
		transition: transform 0.15s var(--ease);
	}
	[aria-expanded='true'] .chev {
		transform: rotate(90deg);
	}
	.dres {
		min-width: 0;
		font-weight: 650;
		color: var(--text-secondary);
	}
	.dres.scored {
		font-weight: 800;
		color: var(--text-primary);
	}
	.dstats,
	.dwhen,
	.dmatch {
		color: var(--text-muted);
		font-size: 0.8rem;
		font-variant-numeric: tabular-nums;
	}
	.dmeta,
	.dside {
		display: contents;
	}
	.dwhen {
		margin-left: auto;
	}
	.dscore {
		display: inline-flex;
		gap: 0.3rem;
		font-size: 0.78rem;
		font-variant-numeric: tabular-nums;
	}
	.dscore span {
		padding: 0 0.4rem;
		border-radius: 5px;
		border: 1px solid var(--border);
		color: var(--text-secondary);
	}
	.dscore .lead-side {
		color: var(--text-primary);
		font-weight: 800;
		border-color: var(--team);
	}
	.dmatch {
		padding: 0 0.4rem;
		border-radius: 999px;
		background: var(--surface-2);
	}
	.plays {
		list-style: none;
		margin: 0;
		padding: 0;
		border-top: 1px solid var(--border);
	}
	.qend {
		padding: 0.35rem 0.75rem;
		font-size: 0.72rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--text-muted);
		background: var(--surface-2);
		border-top: 1px solid var(--grid);
	}
	.empty {
		padding: 1rem;
		text-align: center;
	}
	@media (max-width: 720px) {
		.search {
			max-width: none;
			flex-basis: 100%;
		}
		.drive-head {
			display: grid;
			grid-template-columns: 16px auto minmax(0, 1fr) auto;
			grid-template-areas: 'chev badge res side' '. meta meta meta';
			gap: 0.2rem 0.5rem;
		}
		.chev {
			grid-area: chev;
		}
		.drive-head > :global(.team) {
			grid-area: badge;
		}
		.dres {
			grid-area: res;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
		.dmeta {
			grid-area: meta;
			display: flex;
			flex-wrap: wrap;
			gap: 0 0.5rem;
		}
		.dmeta .dwhen {
			margin-left: 0;
		}
		.dmeta .dstats::after {
			content: ' ·';
		}
		.dside {
			grid-area: side;
			display: inline-flex;
			gap: 0.3rem;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.chev {
			transition: none;
		}
	}
</style>
