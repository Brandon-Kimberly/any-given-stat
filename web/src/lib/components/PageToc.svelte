<script lang="ts">
	// "On this page" jump links for long pages. Sticks under the header while scrolling and
	// marks the section in view. Sections need matching ids.
	let { items }: { items: { id: string; label: string }[] } = $props();
	let active = $state<string | null>(null);
	let nav: HTMLElement;

	// Keep the active pill visible when the bar overflows (phones); scroll only the bar.
	$effect(() => {
		if (!nav) return;
		// Back at the top (nothing active): show the bar from its start again.
		if (!active) return void nav.scrollTo({ left: 0, behavior: 'smooth' });
		const a = nav.querySelector<HTMLElement>(`a[href="#${active}"]`);
		if (a)
			nav.scrollTo({
				left: a.offsetLeft - nav.clientWidth / 2 + a.offsetWidth / 2,
				behavior: 'smooth'
			});
	});

	// The active section is the last one whose top has passed under the bar. A clicked link stays
	// active while its section is on screen (sections near the bottom can't scroll to the top)
	// until the user scrolls by hand. Items can arrive late, so this is an effect, not onMount.
	let pinned: string | null = null;
	let reached = false;
	$effect(() => {
		const ids = items.map((i) => i.id);
		let frame = 0;
		const compute = () => {
			frame = 0;
			if (pinned) {
				// Held through the smooth scroll; released once reached and then scrolled away.
				const r = document.getElementById(pinned)?.getBoundingClientRect();
				const onScreen = !!r && r.top < innerHeight && r.bottom > 120;
				if (onScreen) reached = true;
				if (onScreen || (r && !reached)) return void (active = pinned);
				pinned = null;
			}
			let cur: string | null = null;
			for (const id of ids) {
				const e = document.getElementById(id);
				if (e && e.getBoundingClientRect().top <= 140) cur = id;
			}
			active = cur;
		};
		const onScroll = () => (frame ||= requestAnimationFrame(compute));
		const unpin = () => (pinned = null);
		compute();
		addEventListener('scroll', onScroll, { passive: true });
		for (const t of ['wheel', 'touchstart', 'keydown'])
			addEventListener(t, unpin, { passive: true });
		return () => {
			cancelAnimationFrame(frame);
			removeEventListener('scroll', onScroll);
			for (const t of ['wheel', 'touchstart', 'keydown']) removeEventListener(t, unpin);
		};
	});

	function pick(id: string) {
		pinned = id;
		reached = false;
		active = id;
	}
</script>

<nav class="toc" aria-label="On this page" bind:this={nav}>
	<span class="lbl">On this page</span>
	{#each items as i (i.id)}
		<a
			href="#{i.id}"
			onclick={() => pick(i.id)}
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
