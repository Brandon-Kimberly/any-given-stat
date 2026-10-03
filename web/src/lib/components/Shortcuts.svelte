<script lang="ts">
	// Keyboard shortcuts: "g" then a letter jumps to a page, [ and ] step the season, t toggles
	// the theme, c copies the link, ? shows this list. Ignored while typing in a field.
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { favorite } from '$lib/favorite.svelte';
	import { prefs, savePrefs } from '$lib/prefs.svelte';
	import { toggleTheme } from '$lib/theme.svelte';
	import { copyLink, toast } from '$lib/toast.svelte';
	import type { SeasonStatus } from '$lib/types';

	let { seasons, open = $bindable(false) }: { seasons: SeasonStatus[]; open?: boolean } = $props();
	const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

	const jumps: { key: string; label: string; href: string }[] = [
		{ key: 'h', label: 'Home', href: '/' },
		{ key: 't', label: 'Team tiers', href: '/tiers/' },
		{ key: 'r', label: 'Power ratings', href: '/ratings/' },
		{ key: 'o', label: 'Playoff odds', href: '/odds/' },
		{ key: 's', label: 'Team stats', href: '/teams/' },
		{ key: 'q', label: 'Quarterbacks', href: '/qbs/' },
		{ key: 'w', label: 'Receivers', href: '/receivers/' },
		{ key: 'u', label: 'Rushers', href: '/rushers/' },
		{ key: 'a', label: 'Fantasy', href: '/fantasy/' },
		{ key: 'g', label: 'Games', href: '/games/' },
		{ key: 'p', label: 'Predictions', href: '/predictions/' },
		{ key: 'c', label: 'Compare', href: '/compare/' },
		{ key: 'f', label: 'Fourth downs', href: '/fourth/' },
		{ key: 'l', label: 'Luck', href: '/luck/' },
		{ key: 'b', label: 'Record book', href: '/records/' },
		{ key: 'k', label: 'Coaches', href: '/coaches/' },
		{ key: 'e', label: 'Referees', href: '/referees/' },
		{ key: 'n', label: 'How football works', href: '/learn/' },
		{ key: 'v', label: 'Signal vs noise', href: '/stability/' },
		{ key: 'd', label: 'Glossary', href: '/glossary/' },
		{ key: 'x', label: 'SQL explorer', href: '/explore/' }
	];
	const byKey = new Map(jumps.map((j) => [j.key, j]));

	let pending = false;
	let timer: ReturnType<typeof setTimeout> | undefined;

	function stepSeason(d: number) {
		const list = seasons.map((s) => s.season);
		const i = list.indexOf(prefs.season ?? list.at(-1)!);
		const next = list[Math.max(0, Math.min(list.length - 1, i + d))];
		if (next !== prefs.season) {
			prefs.season = next;
			savePrefs();
			toast.show(`Season ${next}`, 1200);
		}
	}

	function onkeydown(e: KeyboardEvent) {
		if (e.metaKey || e.ctrlKey || e.altKey || e.defaultPrevented) return;
		const t = e.target as HTMLElement;
		if (/INPUT|TEXTAREA|SELECT/.test(t?.tagName) || t?.isContentEditable) return;
		if (document.querySelector('[role="dialog"]:not(.shortcuts)')) return;
		const k = e.key;
		if (pending) {
			pending = false;
			clearTimeout(timer);
			if (k === 'm' && favorite.team) {
				e.preventDefault();
				goto(`${base}/team/?t=${favorite.team}`);
				return;
			}
			const j = byKey.get(k.toLowerCase());
			if (j) {
				e.preventDefault();
				open = false;
				goto(`${base}${j.href}`);
			}
			return;
		}
		if (k === '?') {
			e.preventDefault();
			open = !open;
		} else if (k === 'Escape') open = false;
		else if (k === 'g') {
			pending = true;
			timer = setTimeout(() => (pending = false), 1200);
		} else if (k === '[') stepSeason(-1);
		else if (k === ']') stepSeason(1);
		else if (k === 't') toggleTheme();
		else if (k === 'c') copyLink();
	}
</script>

<svelte:window {onkeydown} />

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="backdrop" onclick={() => (open = false)}>
		<div
			class="shortcuts card"
			role="dialog"
			aria-modal="true"
			aria-labelledby="kbd-title"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="head">
				<h2 id="kbd-title">Keyboard shortcuts</h2>
				<button class="ghost" onclick={() => (open = false)} aria-label="Close">Esc</button>
			</div>
			<div class="cols">
				<section>
					<h3>Anywhere</h3>
					<dl>
						<dt><kbd>/</kbd> or <kbd>{isMac ? '⌘' : 'Ctrl'}</kbd> <kbd>K</kbd></dt>
						<dd>Search pages, teams, players, games, coaches, glossary</dd>
						<dt><kbd>↑</kbd> <kbd>↓</kbd> <kbd>↵</kbd></dt>
						<dd>Move and open in search results</dd>
						<dt><kbd>[</kbd> <kbd>]</kbd></dt>
						<dd>Previous / next season</dd>
						<dt><kbd>t</kbd></dt>
						<dd>Toggle dark mode</dd>
						<dt><kbd>c</kbd></dt>
						<dd>Copy a link to this exact view</dd>
						<dt><kbd>g</kbd> <kbd>m</kbd></dt>
						<dd>My team{favorite.team ? ` (${favorite.team})` : ' (star one first)'}</dd>
						<dt><kbd>?</kbd></dt>
						<dd>This list</dd>
						<dt><kbd>Esc</kbd></dt>
						<dd>Close search, menus and this list</dd>
					</dl>
				</section>
				<section>
					<h3>Go to <span class="muted">(press g, then)</span></h3>
					<dl>
						{#each jumps as j (j.key)}
							<dt><kbd>{j.key}</kbd></dt>
							<dd>{j.label}</dd>
						{/each}
					</dl>
				</section>
			</div>
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 100;
		background: rgba(5, 10, 20, 0.45);
		backdrop-filter: blur(4px);
		display: grid;
		place-items: center;
		padding: 16px;
		animation: fade 0.15s ease-out;
	}
	.shortcuts {
		width: min(680px, 100%);
		max-height: 85vh;
		overflow: auto;
		animation: pop 0.18s var(--ease);
	}
	.head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.5rem;
	}
	.head h2 {
		margin: 0;
	}
	.cols {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 1.25rem;
	}
	h3 {
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--text-secondary);
		margin: 0 0 0.5rem;
	}
	dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.4rem 0.8rem;
		margin: 0;
		font-size: 0.88rem;
	}
	dt {
		white-space: nowrap;
	}
	dd {
		margin: 0;
		color: var(--text-secondary);
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
	@keyframes pop {
		from {
			opacity: 0;
			transform: translateY(-6px) scale(0.98);
		}
	}
</style>
