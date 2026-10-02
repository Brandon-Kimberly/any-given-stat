<script lang="ts">
	import { toast } from '$lib/toast.svelte';
</script>

<div class="toast-host" role="status" aria-live="polite">
	{#if toast.message}
		<div class="toast">{toast.message}</div>
	{/if}
</div>

<style>
	.toast-host {
		position: fixed;
		left: 50%;
		bottom: 24px;
		transform: translateX(-50%);
		z-index: 150;
		pointer-events: none;
	}
	.toast {
		padding: 0.55rem 1rem;
		border-radius: 999px;
		background: var(--text-primary);
		color: var(--page);
		font-size: 0.88rem;
		font-weight: 600;
		box-shadow: var(--shadow-md);
		animation: toast-in 0.18s var(--ease);
	}
	@keyframes toast-in {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
	}
</style>
