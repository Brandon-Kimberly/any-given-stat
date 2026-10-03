<script lang="ts">
	// Renders an Observable Plot figure at the container's width and re-renders whenever the
	// width or any reactive state read inside `render` changes. Charts render only once they
	// come near the viewport, so below-the-fold charts cost nothing until you scroll to them.
	// The first render wipes in; re-renders (filters, toggles) are instant.
	// Text marks with className: 'declutter' have overlapping labels hidden, keeping earlier
	// data first (so callers sort label data by importance).
	import { chartPng, download, slug } from '$lib/exportChart';
	import { declutter } from '$lib/plot';
	import { toast } from '$lib/toast.svelte';
	import { onMount } from 'svelte';

	let {
		render,
		label,
		minHeight = 240,
		tools = true
	}: {
		render: (width: number) => SVGElement | HTMLElement;
		label: string;
		minHeight?: number;
		/** Show the PNG download button on hover. */
		tools?: boolean;
	} = $props();

	let el: HTMLDivElement;
	let width = $state(0);
	let seen = $state(false);
	let renders = 0;
	let intro = $state(false);
	let busy = $state(false);

	onMount(() => {
		// Charts already on (or near) screen render before the first paint, so their
		// placeholder never shows and nothing below them jumps.
		width = el.clientWidth;
		if (!('IntersectionObserver' in window) || el.getBoundingClientRect().top < innerHeight + 400) {
			seen = true;
			return;
		}
		const io = new IntersectionObserver(
			(entries) => {
				if (entries.some((e) => e.isIntersecting)) {
					seen = true;
					io.disconnect();
				}
			},
			{ rootMargin: '400px 0px' }
		);
		io.observe(el);
		return () => io.disconnect();
	});

	$effect(() => {
		if (!width || !seen) return;
		const node = render(width);
		el.replaceChildren(node);
		declutter(el);
		// Expose each chart as one labeled image; Plot's per-mark aria-labels on <g> have no role.
		for (const svg of el.querySelectorAll('svg')) {
			svg.setAttribute('role', 'img');
			svg.setAttribute('aria-label', label);
			for (const g of svg.querySelectorAll('[aria-label]')) g.removeAttribute('aria-label');
		}
		if (renders++ === 0) intro = true;
		return () => node.remove();
	});

	async function savePng() {
		busy = true;
		try {
			download(await chartPng(el, label), `${slug(label)}.png`);
			toast.show('Chart saved as PNG', 2200, 'ok');
		} catch (e) {
			toast.show(e instanceof Error ? e.message : 'Export failed', 3000, 'error');
		} finally {
			busy = false;
		}
	}
</script>

<div class="wrap">
	<div
		class="plot"
		class:pending={!seen}
		class:intro
		style:min-height="{seen ? 120 : minHeight}px"
		bind:this={el}
		bind:clientWidth={width}
		onanimationend={() => (intro = false)}
	></div>
	{#if tools && seen}
		<button
			class="png"
			onclick={savePng}
			disabled={busy}
			aria-label="Download chart as PNG: {label}"
			title="Download PNG"
		>
			<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" /></svg
			>
		</button>
	{/if}
</div>

<style>
	.wrap {
		position: relative;
	}
	.plot {
		width: 100%;
	}
	.plot.pending {
		border-radius: var(--radius-sm);
		background: var(--surface-2);
	}
	.plot.intro :global(svg) {
		animation: wipe 0.55s var(--ease) both;
	}
	@keyframes wipe {
		from {
			clip-path: inset(0 100% 0 0);
			opacity: 0.3;
		}
		to {
			clip-path: inset(0 -10% 0 0);
			opacity: 1;
		}
	}
	.png {
		position: absolute;
		top: -6px;
		right: -6px;
		display: grid;
		place-items: center;
		width: 30px;
		height: 30px;
		min-height: 0;
		padding: 0;
		border-radius: 8px;
		background: var(--surface);
		border: 1px solid var(--border-strong);
		color: var(--text-secondary);
		opacity: 0;
		transition: opacity 0.12s;
	}
	.wrap:hover .png,
	.png:focus-visible {
		opacity: 1;
	}
	@media (hover: none) {
		.png {
			display: none;
		}
	}
	.png svg {
		width: 16px;
		height: 16px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
