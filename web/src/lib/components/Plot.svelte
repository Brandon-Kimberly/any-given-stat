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
		return () => node.remove();
	});
</script>

<div class="plot" role="figure" aria-label={label} bind:this={el} bind:clientWidth={width}></div>

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
