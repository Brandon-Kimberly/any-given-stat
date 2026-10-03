<script lang="ts">
	import { toast } from '$lib/toast.svelte';
</script>

<div class="toast-host" role="status" aria-live="polite">
	{#if toast.message}
		<div class="toast {toast.tone}">{toast.message}</div>
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
		display: flex;
		align-items: center;
		gap: 0.55rem;
		padding: 0.6rem 1.1rem 0.6rem 0.8rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--surface) 82%, transparent);
		backdrop-filter: blur(18px) saturate(1.6);
		-webkit-backdrop-filter: blur(18px) saturate(1.6);
		border: 1px solid var(--border-strong);
		color: var(--text-primary);
		font-size: 0.88rem;
		font-weight: 600;
		box-shadow:
			var(--shadow-md),
			0 0 0 1px color-mix(in srgb, var(--accent) 14%, transparent);
		animation: toast-in 0.4s cubic-bezier(0.2, 1.3, 0.4, 1);
	}
	/* A small mark before the message: a check for success, "!" for problems. */
	.toast.ok::before,
	.toast.error::before {
		content: '✓';
		display: grid;
		place-items: center;
		width: 1.3rem;
		height: 1.3rem;
		border-radius: 50%;
		background: var(--brand-gradient);
		color: #fff;
		font-size: 0.75rem;
	}
	.toast.error::before {
		content: '!';
		background: var(--bad);
		font-weight: 800;
	}
	@keyframes toast-in {
		from {
			opacity: 0;
			transform: translateY(16px) scale(0.92);
		}
	}
</style>
