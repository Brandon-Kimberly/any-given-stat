<script lang="ts">
	// "On this page" jump links for long pages. Sticks under the header while scrolling and
	// marks the section in view. Sections need matching ids.
	import { onMount } from 'svelte';

	let { items }: { items: { id: string; label: string }[] } = $props();
	let active = $state<string | null>(null);

	onMount(() => {
		const els = items
			.map((i) => document.getElementById(i.id))
			.filter((e): e is HTMLElement => !!e);
		const io = new IntersectionObserver(
			(entries) => {
				const top = entries
					.filter((e) => e.isIntersecting)
					.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
				if (top) active = top.target.id;
			},
			{ rootMargin: '-80px 0px -60% 0px' }
		);
		for (const e of els) io.observe(e);
		return () => io.disconnect();
	});
</script>

<nav class="toc" aria-label="On this page">
	<span class="lbl">On this page</span>
	{#each items as i (i.id)}
		<a
			href="#{i.id}"
			class:on={active === i.id}
			aria-current={active === i.id ? 'location' : undefined}>{i.label}</a
		>
	{/each}
</nav>

<style>
	.toc {
		position: sticky;
		top: 64px;
		z-index: 30;
		display: flex;
		gap: 0.35rem;
		align-items: center;
		overflow-x: auto;
		padding: 0.45rem 0.55rem;
		border: 1px solid var(--border);
		border-radius: 999px;
		background: color-mix(in srgb, var(--surface) 88%, transparent);
		backdrop-filter: saturate(1.4) blur(10px);
		-webkit-backdrop-filter: saturate(1.4) blur(10px);
		box-shadow: var(--shadow-sm);
		scrollbar-width: none;
	}
	.lbl {
		flex: none;
		padding: 0 0.4rem;
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--text-muted);
	}
	a {
		flex: none;
		padding: 0.3rem 0.7rem;
		border-radius: 999px;
		font-size: 0.84rem;
		font-weight: 600;
		color: var(--text-secondary);
		text-decoration: none;
		white-space: nowrap;
		transition:
			background 0.15s,
			color 0.15s;
	}
	a:hover {
		color: var(--text-primary);
		background: var(--surface-2);
	}
	a.on {
		color: var(--accent-ink);
		background: var(--accent-soft);
	}
	@media (max-width: 560px) {
		.lbl {
			display: none;
		}
	}
</style>
