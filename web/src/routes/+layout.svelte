<script lang="ts">
	import '../app.css';
	import { base } from '$app/paths';
	import { page } from '$app/state';
	import { load } from '$lib/data';
	import { prefs, restorePrefs } from '$lib/prefs.svelte';
	import type { Meta } from '$lib/types';

	let { children } = $props();

	let meta = $state<Meta | null>(null);
	let error = $state<string | null>(null);

	restorePrefs();
	load('meta')
		.then((m) => {
			meta = m;
			const seasons = m.seasons.map((s) => s.season);
			if (prefs.season == null || !seasons.includes(prefs.season))
				prefs.season = Math.max(...seasons);
		})
		.catch((e) => (error = String(e.message ?? e)));

	const nav = [
		['/', 'Team tiers'],
		['/ratings/', 'Power ratings'],
		['/predictions/', 'Predictions'],
		['/teams/', 'Teams'],
		['/qbs/', 'Quarterbacks'],
		['/receivers/', 'Receivers'],
		['/rushers/', 'Rushers'],
		['/luck/', 'Luck'],
		['/stability/', 'Signal vs noise'],
		['/explore/', 'SQL explorer'],
		['/glossary/', 'Glossary']
	] as const;

	function current(href: string) {
		const path = page.url.pathname.slice(base.length) || '/';
		return href === '/'
			? path === '/'
			: path.startsWith(href) || (href === '/teams/' && path.startsWith('/team/'));
	}

	function toggleTheme() {
		const root = document.documentElement;
		const dark =
			root.dataset.theme === 'dark' ||
			(!root.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
		root.dataset.theme = dark ? 'light' : 'dark';
		try {
			localStorage.setItem('ags-theme', root.dataset.theme);
		} catch {
			/* ignore */
		}
	}
</script>

<svelte:head>
	<title>Any Given Stat</title>
</svelte:head>

<header>
	<div class="bar">
		<a class="brand" href="{base}/">Any Given Stat</a>
		<nav aria-label="Main">
			{#each nav as [href, label] (href)}
				<a href="{base}{href}" aria-current={current(href) ? 'page' : undefined}>{label}</a>
			{/each}
		</nav>
		<button
			class="theme"
			onclick={toggleTheme}
			aria-label="Toggle dark mode"
			title="Toggle dark mode">◐</button
		>
	</div>
</header>

<main>
	{#if error}
		<div class="card">
			<h2>Data not found</h2>
			<p class="muted">{error}</p>
			<p>Build it with <code>cd pipeline &amp;&amp; uv run ags build</code>.</p>
		</div>
	{:else if meta && prefs.season != null}
		{@render children()}
	{:else}
		<p class="muted">Loading…</p>
	{/if}
</main>

<footer>
	<span>
		{#if meta}
			Data: <a href="https://github.com/nflverse/nflverse-data">nflverse</a> play-by-play (EPA, WP,
			CPOE from nflfastR models). Regular season only. Updated
			{new Date(meta.generated_at).toLocaleString()}.
		{/if}
	</span>
	<a href="https://github.com/Brandon-Kimberly/any-given-stat">Source</a>
</footer>

<style>
	header {
		background: var(--surface);
		border-bottom: 1px solid var(--border);
		position: sticky;
		top: 0;
		z-index: 10;
	}
	.bar {
		max-width: 1280px;
		margin: 0 auto;
		display: flex;
		align-items: center;
		gap: 1rem;
		padding: 0 16px;
		height: 52px;
	}
	.brand {
		font-weight: 700;
		color: var(--text-primary);
		text-decoration: none;
		white-space: nowrap;
	}
	nav {
		display: flex;
		gap: 0.15rem;
		overflow-x: auto;
		scrollbar-width: none;
		flex: 1;
	}
	nav a {
		color: var(--text-secondary);
		text-decoration: none;
		padding: 0.35rem 0.6rem;
		border-radius: 6px;
		white-space: nowrap;
		font-size: 0.9rem;
	}
	nav a:hover {
		background: var(--surface-2);
	}
	nav a[aria-current='page'] {
		color: var(--text-primary);
		background: var(--surface-2);
		font-weight: 600;
	}
	@media (max-width: 720px) {
		.bar {
			flex-wrap: wrap;
			height: auto;
			padding-top: 0.5rem;
			gap: 0.25rem 1rem;
		}
		.brand {
			flex: 1;
		}
		nav {
			order: 3;
			flex-basis: 100%;
			flex-wrap: wrap;
			padding-bottom: 0.4rem;
		}
	}
	.theme {
		border: 0;
		font-size: 1.1rem;
		padding: 0.2rem 0.4rem;
	}
	main {
		max-width: 1280px;
		margin: 0 auto;
		padding: 1.25rem 16px 2rem;
		display: grid;
		gap: 1rem;
	}
	footer {
		max-width: 1280px;
		margin: 0 auto;
		padding: 1rem 16px 2rem;
		font-size: 0.8rem;
		color: var(--text-muted);
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
		justify-content: space-between;
	}
	footer a {
		color: inherit;
	}
</style>
