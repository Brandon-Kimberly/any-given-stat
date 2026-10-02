<script lang="ts">
	// Floating "back to top" button, shown after scrolling past about two screens.
	let show = $state(false);
	function onscroll() {
		show = window.scrollY > window.innerHeight * 1.8;
	}
	function top() {
		window.scrollTo({ top: 0 });
		document.getElementById('main')?.focus({ preventScroll: true });
	}
</script>

<svelte:window {onscroll} />

{#if show}
	<button class="to-top" onclick={top} aria-label="Back to top" title="Back to top">
		<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5m0 0-6 6m6-6 6 6" /></svg>
	</button>
{/if}

<style>
	.to-top {
		position: fixed;
		right: 20px;
		bottom: 20px;
		z-index: 40;
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		padding: 0;
		border-radius: 50%;
		background: var(--surface);
		border: 1px solid var(--border-strong);
		color: var(--text-secondary);
		box-shadow: var(--shadow-md);
		animation: pop-in 0.2s var(--ease);
	}
	.to-top:hover {
		color: var(--text-primary);
		border-color: var(--accent);
	}
	.to-top svg {
		width: 20px;
		height: 20px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	@keyframes pop-in {
		from {
			opacity: 0;
			transform: translateY(8px) scale(0.9);
		}
	}
	@media print {
		.to-top {
			display: none;
		}
	}
</style>
