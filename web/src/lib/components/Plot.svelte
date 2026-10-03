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
		clearAxisLabels(el);
		// Expose each chart as one labeled image; Plot's per-mark aria-labels on <g> have no role.
		const strip = () => {
			for (const svg of el.querySelectorAll('svg')) {
				if (svg.getAttribute('role') !== 'img') svg.setAttribute('role', 'img');
				if (svg.getAttribute('aria-label') !== label) svg.setAttribute('aria-label', label);
				for (const g of svg.querySelectorAll('[aria-label]')) g.removeAttribute('aria-label');
			}
		};
		strip();
		// Plot's pointer tip re-adds aria-label="tip" on its <g> after every hover; strip it again
		// so the chart stays one labeled image (aria-label on a role-less <g> is prohibited).
		const mo = new MutationObserver(strip);
		mo.observe(el, {
			subtree: true,
			childList: true,
			attributes: true,
			attributeFilter: ['aria-label']
		});
		if (renders++ === 0) intro = true;
		return () => {
			mo.disconnect();
			node.remove();
		};
	});

	/** Plot puts the x-axis label in the bottom margin, right-aligned, where it overprints the
	 * last tick labels unless the margin is generous. Move any label that collides with its tick
	 * labels clear of them (below a bottom axis, above a top one) and grow the SVG to fit, so no
	 * chart has to remember a bigger marginBottom. Runs before paint, so nothing shifts. */
	function clearAxisLabels(root: HTMLElement) {
		for (const svg of root.querySelectorAll<SVGSVGElement>('svg')) {
			const label = svg.querySelector<SVGGElement>(':scope > g[aria-label="x-axis label"]');
			const ticks = [
				...svg.querySelectorAll<SVGTextElement>(':scope > g[aria-label="x-axis tick label"] text')
			]
				.map((t) => t.getBoundingClientRect())
				.filter((r) => r.width);
			if (!label || !ticks.length) continue;
			const lr = label.getBoundingClientRect();
			if (!lr.width) continue;
			const pad = 2;
			const hit = ticks.some(
				(r) =>
					r.left < lr.right + pad &&
					r.right > lr.left - pad &&
					r.top < lr.bottom &&
					r.bottom > lr.top
			);
			if (!hit) continue;
			const vb = svg.viewBox.baseVal;
			const box = svg.getBoundingClientRect();
			if (!vb || !vb.height || !box.height) continue;
			const k = vb.height / box.height; // screen px -> SVG units
			const tickMid = ticks.reduce((a, r) => a + (r.top + r.bottom) / 2, 0) / ticks.length;
			const below = (lr.top + lr.bottom) / 2 >= tickMid;
			const shift = below
				? (Math.max(...ticks.map((r) => r.bottom)) + pad - lr.top) * k
				: (Math.min(...ticks.map((r) => r.top)) - pad - lr.bottom) * k;
			label.setAttribute(
				'transform',
				`translate(0,${shift}) ${label.getAttribute('transform') ?? ''}`
			);
			// Grow the SVG by however far the label now pokes out.
			const grow = below
				? (lr.bottom - box.bottom) * k + shift + pad
				: (box.top - lr.top) * k - shift + pad;
			if (grow > 0) {
				const h = vb.height + grow;
				svg.setAttribute('viewBox', `${vb.x} ${below ? vb.y : vb.y - grow} ${vb.width} ${h}`);
				svg.setAttribute('height', String(h));
			}
		}
	}

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
