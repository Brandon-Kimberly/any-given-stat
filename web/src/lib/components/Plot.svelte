<script lang="ts">
	// Renders an Observable Plot figure at the container's width and re-renders whenever the
	// width or any reactive state read inside `render` changes. Text marks with
	// className: 'declutter' have overlapping labels hidden, keeping earlier data first (so
	// callers sort label data by importance).
	import { declutter } from '$lib/plot';

	let { render, label }: { render: (width: number) => SVGElement | HTMLElement; label: string } =
		$props();

	let el: HTMLDivElement;
	let width = $state(0);

	$effect(() => {
		if (!width) return;
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

<div class="plot" bind:this={el} bind:clientWidth={width}></div>

<style>
	.plot {
		width: 100%;
		min-height: 120px;
		animation: plot-in 0.4s var(--ease) both;
	}
	@keyframes plot-in {
		from {
			opacity: 0;
		}
	}
</style>
