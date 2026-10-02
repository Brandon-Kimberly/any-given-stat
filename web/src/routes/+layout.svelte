<script lang="ts">
	import '../app.css';
	import { afterNavigate, replaceState } from '$app/navigation';
	import { base } from '$app/paths';
	import { navigating, page } from '$app/state';
	import CommandPalette from '$lib/components/CommandPalette.svelte';
	import Shortcuts from '$lib/components/Shortcuts.svelte';
	import BackToTop from '$lib/components/BackToTop.svelte';
	import { pushRecent } from '$lib/recent';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import SyncControl from '$lib/components/SyncControl.svelte';
	import Toast from '$lib/components/Toast.svelte';
	import { load } from '$lib/data';
	import { groupFor, navGroups } from '$lib/nav';
	import { prefs, prefsFromUrl, prefsUrl, restorePrefs, savePrefs } from '$lib/prefs.svelte';
	import { loadTeamMeta } from '$lib/teams.svelte';
	import { initTheme, theme, toggleTheme } from '$lib/theme.svelte';
	import { copyLink } from '$lib/toast.svelte';
	import type { Meta } from '$lib/types';
	import { untrack } from 'svelte';

	let { children } = $props();

	let meta = $state.raw<Meta | null>(null);
	let error = $state<string | null>(null);
	let openGroup = $state<string | null>(null);
	let drawer = $state(false);
	let search = $state(false);
	let keys = $state(false);
	let ready = $state(false);

	restorePrefs(page.url);
	initTheme();
	loadTeamMeta();
	load('meta')
		.then((m) => {
			meta = m;
			const seasons = m.seasons.map((s) => s.season);
			if (prefs.season == null || !seasons.includes(prefs.season))
				prefs.season = Math.max(...seasons);
		})
		.catch((e) => (error = String(e.message ?? e)));

	const path = $derived(page.url.pathname.slice(base.length) || '/');
	const activeGroup = $derived(groupFor(path));
	const latest = $derived(meta?.seasons.at(-1));

	// Keep ?season=&scope= in the address bar so any view can be shared as a link.
	function syncUrl() {
		if (!ready || prefs.season == null) return;
		const next = prefsUrl(page.url);
		if (next.href !== page.url.href) replaceState(next, page.state);
	}
	$effect(() => {
		void prefs.season;
		void prefs.scope;
		savePrefs();
		untrack(syncUrl);
	});
	afterNavigate((nav) => {
		if (ready && nav.type !== 'enter') prefsFromUrl(page.url);
		// Remember teams, players and pages (not home or games) for the search palette.
		const p = page.url.pathname.slice(base.length);
		const q = page.url.searchParams;
		if (p.startsWith('/team/') && q.get('t')) pushRecent(`/team/?t=${q.get('t')}`);
		else if (p.startsWith('/player/') && q.get('id')) pushRecent(`/player/?id=${q.get('id')}`);
		else if (p !== '/' && !p.startsWith('/game/')) pushRecent(p);
		ready = true;
		openGroup = null;
		drawer = false;
		syncUrl();
	});

	function onWindowClick(e: MouseEvent) {
		if (!(e.target as HTMLElement).closest('.menus')) openGroup = null;
	}
	function onWindowKey(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			openGroup = null;
			drawer = false;
		}
	}
	const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

	function ago(iso: string): string {
		const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
		if (mins < 60) return `${Math.max(1, mins)} min ago`;
		const hrs = Math.round(mins / 60);
		if (hrs < 48) return `${hrs} hr ago`;
		return new Date(iso).toLocaleDateString();
	}
</script>

<svelte:window onclick={onWindowClick} onkeydown={onWindowKey} />

<svelte:head>
	<title>Any Given Stat</title>
</svelte:head>

<a class="skip" href="#main">Skip to content</a>

<header>
	{#if navigating.to}<div class="nav-progress" aria-hidden="true"></div>{/if}
	<div class="bar">
		<a class="brand" href="{base}/" aria-label="Any Given Stat home">
			<svg viewBox="0 0 32 32" aria-hidden="true"
				><rect width="32" height="32" rx="8" fill="url(#g)" /><defs
					><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"
						><stop offset="0" stop-color="#1c5cab" /><stop
							offset="1"
							stop-color="#0f2a4f"
						/></linearGradient
					></defs
				><ellipse
					cx="16"
					cy="16"
					rx="10.5"
					ry="6.5"
					fill="none"
					stroke="#fff"
					stroke-width="2.2"
					transform="rotate(-35 16 16)"
				/><path
					d="M12.5 19.5l7-7M13.6 15.4l3 3M15.6 13.4l3 3"
					stroke="#fff"
					stroke-width="1.8"
					stroke-linecap="round"
				/></svg
			>
			<span>Any Given <b>Stat</b></span>
		</a>

		<nav class="menus" aria-label="Main">
			{#each navGroups as g (g.label)}
				<div class="menu">
					<button
						class="menu-btn"
						class:current={activeGroup === g.label}
						aria-expanded={openGroup === g.label}
						aria-haspopup="true"
						onclick={() => (openGroup = openGroup === g.label ? null : g.label)}
						>{g.label}<svg viewBox="0 0 12 12" aria-hidden="true"
							><path d="M3 4.5 6 7.5 9 4.5" /></svg
						></button
					>
					{#if openGroup === g.label}
						<div class="panel" role="menu">
							{#each g.items as item (item.href)}
								<a
									role="menuitem"
									href="{base}{item.href}"
									aria-current={path.startsWith(item.href) ? 'page' : undefined}
								>
									<span class="item-label">{item.label}</span>
									<span class="item-blurb">{item.blurb}</span>
								</a>
							{/each}
						</div>
					{/if}
				</div>
			{/each}
		</nav>

		<div class="actions">
			<SyncControl generatedAt={meta?.generated_at} />
			<button class="search-btn" onclick={() => (search = true)} aria-label="Search">
				<svg viewBox="0 0 24 24" aria-hidden="true"
					><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg
				>
				<span class="search-text">Search</span>
				<kbd class="search-kbd">{isMac ? '⌘' : 'Ctrl'} K</kbd>
			</button>
			<button
				class="icon-btn wide-only"
				onclick={() => copyLink()}
				aria-label="Copy a link to this view"
				title="Copy link (c)"
			>
				<svg viewBox="0 0 24 24" aria-hidden="true"
					><path
						d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1"
					/></svg
				>
			</button>
			<button
				class="icon-btn wide-only"
				onclick={() => (keys = true)}
				aria-label="Keyboard shortcuts"
				title="Keyboard shortcuts (?)"
			>
				<svg viewBox="0 0 24 24" aria-hidden="true"
					><rect x="2.5" y="6" width="19" height="12" rx="2" /><path
						d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"
					/></svg
				>
			</button>
			<button
				class="icon-btn"
				onclick={toggleTheme}
				aria-label={theme.dark ? 'Switch to light mode' : 'Switch to dark mode'}
				title={theme.dark ? 'Light mode' : 'Dark mode'}
			>
				{#if theme.dark}
					<svg viewBox="0 0 24 24" aria-hidden="true"
						><circle cx="12" cy="12" r="4.5" /><path
							d="M12 2v2.5M12 19.5V22M4.2 4.2l1.8 1.8M18 18l1.8 1.8M2 12h2.5M19.5 12H22M4.2 19.8 6 18M18 6l1.8-1.8"
						/></svg
					>
				{:else}
					<svg viewBox="0 0 24 24" aria-hidden="true"
						><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11Z" /></svg
					>
				{/if}
			</button>
			<button
				class="icon-btn hamburger"
				onclick={() => (drawer = !drawer)}
				aria-label="Menu"
				aria-expanded={drawer}
			>
				<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
			</button>
		</div>
	</div>
</header>

{#if drawer}
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="drawer-backdrop" onclick={() => (drawer = false)}></div>
	<nav class="drawer" aria-label="Main">
		<button class="icon-btn drawer-close" onclick={() => (drawer = false)} aria-label="Close menu">
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
		</button>
		<a class="drawer-home" href="{base}/" aria-current={path === '/' ? 'page' : undefined}>Home</a>
		{#each navGroups as g (g.label)}
			<div class="drawer-group">
				<div class="eyebrow">{g.label}</div>
				{#each g.items as item (item.href)}
					<a href="{base}{item.href}" aria-current={path.startsWith(item.href) ? 'page' : undefined}
						>{item.label}</a
					>
				{/each}
			</div>
		{/each}
	</nav>
{/if}

<CommandPalette bind:open={search} />
{#if meta}<Shortcuts seasons={meta.seasons} bind:open={keys} />{/if}
<Toast />

<main id="main" tabindex="-1">
	{#if error}
		<div class="card">
			<h2>The data couldn't load</h2>
			<p class="muted">{error}</p>
			<p>
				Try reloading the page. Running the site yourself? Build the data first with
				<code>.\start.cmd</code> (Windows) or <code>./start.sh</code>.
			</p>
		</div>
	{:else if meta && prefs.season != null}
		{#key path}
			<div class="page rise">
				{@render children()}
			</div>
		{/key}
	{:else}
		<Skeleton />
	{/if}
</main>

<BackToTop />

<footer>
	<nav class="sitemap" aria-label="Site map">
		{#each navGroups as g (g.label)}
			<div>
				<div class="eyebrow">{g.label}</div>
				<ul>
					{#each g.items as item (item.href)}
						<li><a href="{base}{item.href}">{item.label}</a></li>
					{/each}
				</ul>
			</div>
		{/each}
	</nav>
	<div class="foot">
		<div>
			<div class="foot-brand">Any Given <b>Stat</b></div>
			<p class="muted">
				NFL analytics from every play since 2016. Data from <a
					href="https://github.com/nflverse/nflverse-data">nflverse</a
				>; EPA, win probability, CPOE and xYAC from the nflfastR models. Regular season unless
				noted.
			</p>
		</div>
		<div class="foot-meta">
			{#if meta && latest}
				<span class="chip"
					><span class="dot"></span>
					{latest.season}{latest.complete ? '' : ` · through week ${latest.last_week}`}</span
				>
				<span class="muted">Updated {ago(meta.generated_at)}</span>
			{/if}
			<a href="{base}/glossary/">Glossary</a>
			<a href="https://github.com/Brandon-Kimberly/any-given-stat">Source</a>
		</div>
	</div>
</footer>

<style>
	.skip {
		position: absolute;
		left: 16px;
		top: -48px;
		z-index: 200;
		background: var(--accent-ink);
		color: #fff;
		padding: 0.5rem 0.8rem;
		border-radius: 8px;
		transition: top 0.15s;
	}
	.skip:focus {
		top: 10px;
	}
	.nav-progress {
		position: absolute;
		left: 0;
		top: 0;
		height: 3px;
		width: 100%;
		background: linear-gradient(90deg, var(--series-1), var(--series-3), var(--series-4));
		transform-origin: left;
		animation: nav-load 1.2s var(--ease) forwards;
		animation-delay: 80ms;
		transform: scaleX(0);
	}
	@keyframes nav-load {
		to {
			transform: scaleX(0.85);
		}
	}
	header {
		position: sticky;
		top: 0;
		z-index: 50;
		background: var(--header-bg);
		backdrop-filter: saturate(1.6) blur(14px);
		-webkit-backdrop-filter: saturate(1.6) blur(14px);
		border-bottom: 1px solid var(--border);
	}
	.bar {
		max-width: 1280px;
		margin: 0 auto;
		display: flex;
		align-items: center;
		gap: 1.25rem;
		padding: 0 16px;
		height: 58px;
	}
	.brand {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		color: var(--text-primary);
		text-decoration: none;
		font: 600 1.05rem var(--display);
		letter-spacing: -0.01em;
		white-space: nowrap;
	}
	.brand svg {
		width: 30px;
		height: 30px;
		flex: none;
	}
	.brand b {
		font-weight: 800;
		color: var(--accent-ink);
	}
	.menus {
		display: flex;
		gap: 0.15rem;
		flex: 1;
	}
	.menu {
		position: relative;
	}
	.menu-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		border: 0;
		background: transparent;
		color: var(--text-secondary);
		font-weight: 500;
		font-size: 0.92rem;
		padding: 0.4rem 0.7rem;
		border-radius: 8px;
	}
	.menu-btn svg {
		width: 12px;
		height: 12px;
		fill: none;
		stroke: currentColor;
		stroke-width: 1.6;
		transition: transform 0.15s;
	}
	.menu-btn[aria-expanded='true'] svg {
		transform: rotate(180deg);
	}
	.menu-btn:hover,
	.menu-btn[aria-expanded='true'] {
		background: var(--surface-2);
		color: var(--text-primary);
	}
	.menu-btn.current {
		color: var(--text-primary);
		font-weight: 650;
		box-shadow: inset 0 -2px 0 var(--accent);
		border-radius: 8px 8px 2px 2px;
	}
	.panel {
		position: absolute;
		top: calc(100% + 8px);
		left: 0;
		min-width: 300px;
		padding: 0.4rem;
		background: var(--surface);
		border: 1px solid var(--border-strong);
		border-radius: 14px;
		box-shadow: var(--shadow-md);
		display: grid;
		gap: 2px;
		animation: drop 0.16s var(--ease);
	}
	.panel a {
		display: grid;
		padding: 0.55rem 0.7rem;
		border-radius: 10px;
		text-decoration: none;
		color: var(--text-primary);
	}
	.panel a:hover,
	.panel a[aria-current='page'] {
		background: var(--accent-soft);
	}
	.item-label {
		font-weight: 600;
		font-size: 0.92rem;
	}
	.item-blurb {
		font-size: 0.8rem;
		color: var(--text-secondary);
	}
	.actions {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-left: auto;
	}
	.search-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--text-muted);
		background: var(--surface-2);
		border-color: var(--border);
		border-radius: 10px;
		padding: 0.3rem 0.5rem 0.3rem 0.65rem;
		min-width: 180px;
	}
	.search-btn:hover {
		border-color: var(--accent);
	}
	.search-btn svg,
	.icon-btn svg {
		width: 18px;
		height: 18px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.search-text {
		flex: 1;
		text-align: left;
		font-size: 0.88rem;
	}
	.icon-btn {
		display: grid;
		place-items: center;
		width: 36px;
		height: 36px;
		padding: 0;
		border: 0;
		background: transparent;
		color: var(--text-secondary);
		border-radius: 10px;
	}
	.icon-btn:hover {
		background: var(--surface-2);
		color: var(--text-primary);
	}
	.hamburger {
		display: none;
	}
	/* Mid widths: full menus, but a compact search and no secondary buttons. */
	@media (max-width: 1180px) {
		.search-btn {
			min-width: 0;
		}
		.search-text {
			display: none;
		}
		.wide-only {
			display: none;
		}
		.menu-btn {
			padding-inline: 0.5rem;
		}
	}
	@media (max-width: 960px) {
		.menus {
			display: none;
		}
		.hamburger {
			display: grid;
		}
		.search-btn {
			min-width: 0;
		}
		.search-text,
		.search-kbd {
			display: none;
		}
		.wide-only {
			display: none;
		}
		.search-btn {
			border: 0;
			background: transparent;
			width: 36px;
			height: 36px;
			padding: 0;
			justify-content: center;
		}
	}
	.drawer-backdrop {
		position: fixed;
		inset: 0;
		z-index: 60;
		background: rgba(5, 10, 20, 0.4);
		animation: fade 0.15s ease-out;
	}
	.drawer {
		position: fixed;
		top: 0;
		right: 0;
		bottom: 0;
		z-index: 70;
		width: min(320px, 86vw);
		overflow-y: auto;
		padding: 1rem;
		background: var(--surface);
		border-left: 1px solid var(--border-strong);
		box-shadow: var(--shadow-md);
		animation: slide 0.22s var(--ease);
		display: grid;
		align-content: start;
		gap: 1rem;
	}
	.drawer a {
		display: block;
		padding: 0.45rem 0.6rem;
		border-radius: 8px;
		text-decoration: none;
		color: var(--text-primary);
		font-weight: 500;
	}
	.drawer a[aria-current='page'] {
		background: var(--accent-soft);
		font-weight: 650;
	}
	.drawer-close {
		justify-self: end;
		margin-bottom: -0.5rem;
	}
	.drawer-home {
		font-family: var(--display);
		font-weight: 700 !important;
	}
	.drawer-group .eyebrow {
		padding: 0 0.6rem;
	}
	main {
		max-width: 1280px;
		margin: 0 auto;
		padding: 1.5rem 16px 2.5rem;
		outline: none;
		/* Keep the footer below the fold while data loads, so it doesn't jump. */
		min-height: calc(100vh - 60px);
	}
	.page {
		display: grid;
		gap: 1.1rem;
	}
	footer {
		border-top: 1px solid var(--border);
		background: var(--surface);
	}
	.sitemap {
		max-width: 1280px;
		margin: 0 auto;
		padding: 1.75rem 16px 0;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 1rem 1.5rem;
	}
	.sitemap .eyebrow {
		margin-bottom: 0.35rem;
	}
	.sitemap ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.1rem;
	}
	.sitemap a {
		display: inline-block;
		padding: 0.2rem 0;
		color: var(--text-secondary);
		text-decoration: none;
		font-size: 0.88rem;
	}
	.sitemap a:hover {
		color: var(--text-primary);
		text-decoration: underline;
	}
	.foot {
		max-width: 1280px;
		margin: 0 auto;
		padding: 1.5rem 16px 2rem;
		display: flex;
		flex-wrap: wrap;
		gap: 1rem 2rem;
		justify-content: space-between;
		align-items: flex-end;
		font-size: 0.85rem;
	}
	.foot p {
		max-width: 60ch;
		margin: 0.3rem 0 0;
	}
	.foot-brand {
		font: 600 1rem var(--display);
	}
	.foot-brand b {
		font-weight: 800;
		color: var(--accent-ink);
	}
	.foot-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem 1rem;
		align-items: center;
	}
	.foot-meta a {
		color: var(--text-secondary);
	}
	.dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #1baf7a;
		box-shadow: 0 0 0 3px rgba(27, 175, 122, 0.2);
	}
	@keyframes drop {
		from {
			opacity: 0;
			transform: translateY(-4px);
		}
	}
	@keyframes slide {
		from {
			transform: translateX(100%);
		}
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
</style>
