<script lang="ts">
	// Renders an Observable Plot figure at the container's width and re-renders
	// whenever the width or any reactive state read inside `render` changes.
	let { render, label }: { render: (width: number) => SVGElement | HTMLElement; label: string } =
		$props();

	let el: HTMLDivElement;
	let width = $state(0);

	$effect(() => {
		if (!width) return;
		const node = render(width);
		el.replaceChildren(node);
		return () => node.remove();
	});
</script>

<div class="plot" role="figure" aria-label={label} bind:this={el} bind:clientWidth={width}></div>

<style>
	.plot {
		width: 100%;
		min-height: 120px;
	}
</style>
