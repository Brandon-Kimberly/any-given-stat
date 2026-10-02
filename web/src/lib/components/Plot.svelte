<script lang="ts">
	// Renders an Observable Plot figure at the container's width and re-renders whenever the
	// width or any reactive state read inside `render` changes. Charts render only once they
	// come near the viewport, so below-the-fold charts cost nothing until you scroll to them.
	// Text marks with className: 'declutter' have overlapping labels hidden, keeping earlier
	// data first (so callers sort label data by importance).
	import { declutter } from '$lib/plot';
	import { onMount } from 'svelte';

	let {
		render,
		label,
		minHeight = 240
	}: {
		render: (width: number) => SVGElement | HTMLElement;
		label: string;
		minHeight?: number;
	} = $props();

	let el: HTMLDivElement;
	let width = $state(0);
	let seen = $state(false);

	onMount(() => {
		if (!('IntersectionObserver' in window)) {
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
		return () => node.remove();
	});
</script>

<div
	class="plot"
	class:pending={!seen}
	style:min-height="{seen ? 120 : minHeight}px"
	bind:this={el}
	bind:clientWidth={width}
></div>

<style>
	.plot {
		width: 100%;
		animation: plot-in 0.2s var(--ease) both;
	}
	.plot.pending {
		border-radius: var(--radius-sm);
		background: var(--surface-2);
	}
	@keyframes plot-in {
		from {
			opacity: 0.4;
		}
	}
</style>
