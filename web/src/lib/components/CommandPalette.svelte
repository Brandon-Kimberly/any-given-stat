<script lang="ts">
	// ⌘K / Ctrl+K (or "/") search across pages, teams and players.
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { load } from '$lib/data';
	import { allPages } from '$lib/nav';
	import { favorite } from '$lib/favorite.svelte';
	import { teamMeta } from '$lib/teams.svelte';
	import { readRecent } from '$lib/recent';
	import { toggleTheme } from '$lib/theme.svelte';
	import Avatar from './Avatar.svelte';
	import TeamLogo from './TeamLogo.svelte';
	import { copyLink } from '$lib/toast.svelte';

	let { open = $bindable(false) }: { open?: boolean } = $props();

	interface Entry {
		kind: 'Page' | 'Team' | 'Player' | 'Action' | 'Recent';
		label: string;
		detail: string;
		href: string;
		run?: () => void;
		/** Lowercased text the query matches against. */
		key: string;
		/** Team code: a logo tile for teams, the ring color for players. */
		team?: string;
		/** Player headshot (players.json). */
		photo?: string | null;
	}

	let query = $state('');
	let active = $state(0);
	let input = $state<HTMLInputElement>();
	let players = $state.raw<Entry[]>([]);
	let loadedPlayers = false;

	const pages = allPages.map<Entry>((p) => ({
		kind: 'Page',
		label: p.label,
		detail: p.blurb,
		href: p.href,
		key: `${p.label} ${p.blurb}`.toLowerCase()
	}));
	const actions = $derived<Entry[]>([
		{
			kind: 'Action',
			label: 'Toggle dark mode',
			detail: 'Shortcut: t',
			href: '#theme',
			key: 'toggle dark light mode theme',
			run: () => toggleTheme()
		},
		{
			kind: 'Action',
			label: 'Copy link to this view',
			detail: 'Season, filters and selections included · c',
			href: '#copy',
			key: 'copy link share url',
			run: () => copyLink()
		},
		...(favorite.team
			? [
					{
						kind: 'Action' as const,
						label: 'Go to my team',
						detail: `${favorite.team} · g then m`,
						href: `/team/?t=${favorite.team}`,
						key: 'my team favorite'
					}
				]
			: [])
	]);
	const teams = $derived(
		Object.values(teamMeta.byTeam).map<Entry>((t) => ({
			kind: 'Team',
			label: t.name,
			detail: `${t.team} · ${t.division}`,
			href: `/team/?t=${t.team}`,
			key: `${t.team} ${t.name} ${t.nick}`.toLowerCase(),
			team: t.team
		}))
	);

	async function loadPlayers() {
		if (loadedPlayers) return;
		loadedPlayers = true;
		// Latest season each player appears in, from the three player datasets.
		const [qbs, rec, rush, directory] = await Promise.all([
			load('qbs').catch(() => []),
			load('receivers').catch(() => []),
			load('rushers').catch(() => []),
			load('players').catch(() => [])
		]);
		const photos = new Map(directory.map((d) => [d.player_id, d.headshot]));
		const best = new Map<string, { name: string; team: string; season: number; role: string }>();
		const add = (id: string, name: string, team: string, season: number, role: string) => {
			const cur = best.get(id);
			if (!cur || season > cur.season) best.set(id, { name, team, season, role });
		};
		for (const q of qbs) add(q.player_id, q.full_name ?? q.name, q.team, q.season, 'QB');
		for (const r of rec)
			add(r.player_id, r.full_name ?? r.name, r.team, r.season, r.position ?? 'Receiver');
		for (const r of rush)
			add(r.player_id, r.full_name ?? r.name, r.team, r.season, r.position ?? 'Rusher');
		players = [...best].map(([id, p]) => ({
			kind: 'Player',
			label: p.name,
			detail: `${p.role} · ${p.team} · last seen ${p.season}`,
			href: `/player/?id=${id}`,
			key: p.name.toLowerCase(),
			team: p.team,
			photo: photos.get(id) ?? null
		}));
	}

	function score(e: Entry, q: string): number {
		if (!q) return e.kind === 'Page' ? 1 : 0;
		const label = e.label.toLowerCase();
		if (label === q) return 100;
		if (label.startsWith(q)) return 80;
		if (label.split(/[\s.]+/).some((w) => w.startsWith(q))) return 60;
		if (e.key.includes(q)) return 30;
		return 0;
	}

	// Empty query: recently opened teams, players and pages first, then every page.
	let recent = $state<string[]>([]);
	const recentEntries = $derived.by(() => {
		const all = [...teams, ...players, ...pages];
		const path = (h: string) => h.split('&')[0];
		return recent.flatMap((h) => {
			const e = all.find((x) => path(x.href) === path(h));
			return e ? [{ ...e, kind: 'Recent' as const, detail: `${e.kind} · ${e.detail}` }] : [];
		});
	});

	const results = $derived.by(() => {
		const q = query.trim().toLowerCase();
		if (!q && recentEntries.length) {
			const seen = new Set(recentEntries.map((e) => e.href));
			return [...recentEntries, ...pages.filter((p) => !seen.has(p.href))].slice(0, 12);
		}
		return [...pages, ...actions, ...teams, ...players]
			.map((e) => ({ e, s: score(e, q) }))
			.filter((r) => r.s > 0)
			.sort((a, b) => b.s - a.s)
			.slice(0, 12)
			.map((r) => r.e);
	});

	$effect(() => {
		if (open) {
			recent = readRecent();
			query = '';
			active = 0;
			loadPlayers();
			queueMicrotask(() => input?.focus());
		}
	});

	$effect(() => {
		void results;
		active = 0;
	});

	function choose(e: Entry | undefined) {
		if (!e) return;
		open = false;
		if (e.run) e.run();
		else goto(`${base}${e.href}`);
	}

	function onkeydown(ev: KeyboardEvent) {
		if (ev.key === 'ArrowDown') {
			ev.preventDefault();
			active = Math.min(results.length - 1, active + 1);
		} else if (ev.key === 'ArrowUp') {
			ev.preventDefault();
			active = Math.max(0, active - 1);
		} else if (ev.key === 'Enter') {
			ev.preventDefault();
			choose(results[active]);
		} else if (ev.key === 'Escape') {
			open = false;
		}
	}

	function onWindowKey(ev: KeyboardEvent) {
		const target = ev.target as HTMLElement;
		const typing = /INPUT|TEXTAREA|SELECT/.test(target?.tagName) || target?.isContentEditable;
		if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === 'k') {
			ev.preventDefault();
			open = !open;
		} else if (ev.key === '/' && !typing && !open) {
			ev.preventDefault();
			open = true;
		}
	}
</script>

<svelte:window onkeydown={onWindowKey} />

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="backdrop" onclick={() => (open = false)}>
		<div
			class="palette"
			role="dialog"
			aria-modal="true"
			aria-label="Search"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="search">
				<svg viewBox="0 0 24 24" aria-hidden="true"
					><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg
				>
				<input
					bind:this={input}
					bind:value={query}
					{onkeydown}
					placeholder="Search teams, players, pages…"
					aria-label="Search"
					role="combobox"
					aria-expanded="true"
					aria-controls="palette-results"
					aria-activedescendant={results.length ? `palette-${active}` : undefined}
				/>
				<kbd>Esc</kbd>
			</div>
			<ul id="palette-results" role="listbox">
				{#each results as r, i (r.kind + r.href)}
					<li
						id="palette-{i}"
						role="option"
						aria-selected={i === active}
						class:active={i === active}
						onmouseenter={() => (active = i)}
						onclick={() => choose(r)}
					>
						<span class="media" aria-hidden="true">
							{#if r.photo !== undefined}<Avatar
									name={r.label}
									src={r.photo}
									team={r.team}
									size={34}
								/>
							{:else if r.team}<TeamLogo team={r.team} size={34} glow={false} />
							{:else}<span class="glyph">{r.kind === 'Action' ? '›' : '#'}</span>{/if}
						</span>
						<span class="kind">{r.kind}</span>
						<span class="label">{r.label}</span>
						<span class="detail">{r.detail}</span>
					</li>
				{:else}
					<li class="empty">No matches for “{query}”.</li>
				{/each}
			</ul>
			<div class="hint">
				<span><kbd>↑</kbd> <kbd>↓</kbd> to move</span><span><kbd>↵</kbd> to open</span>
			</div>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 100;
		background: rgba(5, 10, 20, 0.5);
		backdrop-filter: blur(6px);
		display: grid;
		justify-items: center;
		align-items: start;
		padding: 12vh 16px 16px;
		animation: fade 0.15s ease-out;
	}
	.palette {
		width: min(640px, 100%);
		background: color-mix(in srgb, var(--surface) 90%, transparent);
		backdrop-filter: blur(24px) saturate(1.6);
		-webkit-backdrop-filter: blur(24px) saturate(1.6);
		border: 1px solid var(--border-strong);
		border-radius: 18px;
		box-shadow:
			0 40px 100px -24px rgba(0, 0, 0, 0.6),
			0 0 0 1px color-mix(in srgb, var(--accent) 18%, transparent);
		overflow: hidden;
		animation: pop 0.26s cubic-bezier(0.2, 1.2, 0.4, 1);
	}
	.search {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.8rem 1rem;
		border-bottom: 1px solid var(--border);
	}
	.search svg {
		width: 18px;
		height: 18px;
		fill: none;
		stroke: var(--text-muted);
		stroke-width: 2;
		stroke-linecap: round;
	}
	.search input {
		flex: 1;
		border: 0;
		background: transparent;
		font-size: 1.05rem;
		padding: 0.2rem 0;
		min-height: 0;
		box-shadow: none;
	}
	.search input:focus-visible {
		box-shadow: none;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0.4rem;
		max-height: min(60vh, 460px);
		overflow-y: auto;
	}
	li {
		position: relative;
		display: grid;
		grid-template-columns: 2.4rem 1fr auto;
		grid-template-areas: 'media label kind' 'media detail kind';
		column-gap: 0.7rem;
		align-items: center;
		padding: 0.45rem 0.65rem;
		border-radius: 10px;
		cursor: pointer;
	}
	li.active {
		background: var(--accent-soft);
	}
	li.active::before {
		content: '';
		position: absolute;
		left: 0;
		top: 22%;
		bottom: 22%;
		width: 3px;
		border-radius: 3px;
		background: var(--brand-gradient);
	}
	.media {
		grid-area: media;
		display: grid;
		place-items: center;
	}
	.glyph {
		display: grid;
		place-items: center;
		width: 34px;
		height: 34px;
		border-radius: 10px;
		background: var(--surface-2);
		border: 1px solid var(--border);
		font-weight: 700;
		color: var(--accent-ink);
	}
	.kind {
		grid-area: kind;
		font-size: 0.66rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--text-muted);
		padding: 0.1rem 0.45rem;
		border: 1px solid var(--border);
		border-radius: 999px;
	}
	.label {
		grid-area: label;
		font-weight: 600;
	}
	.detail {
		grid-area: detail;
		font-size: 0.8rem;
		color: var(--text-secondary);
	}
	li.empty {
		display: block;
		color: var(--text-muted);
		cursor: default;
	}
	.hint {
		display: flex;
		gap: 1rem;
		padding: 0.55rem 1rem;
		border-top: 1px solid var(--border);
		font-size: 0.75rem;
		color: var(--text-muted);
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
	@keyframes pop {
		from {
			opacity: 0;
			transform: translateY(-10px) scale(0.96);
		}
	}
</style>
