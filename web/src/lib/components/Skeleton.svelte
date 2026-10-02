<script lang="ts">
	// Placeholder shown while datasets load: a header bar plus a few block rows.
	let { rows = 3, height = 220 }: { rows?: number; height?: number } = $props();
</script>

<div class="wrap" aria-busy="true" aria-label="Loading">
	<div class="skeleton" style="height: 28px; width: 40%"></div>
	<div class="skeleton" style="height: {height}px"></div>
	{#each Array(rows) as _, i (i)}
		<div class="skeleton" style="height: 18px; width: {90 - i * 12}%"></div>
	{/each}
</div>

<style>
	.wrap {
		display: grid;
		gap: 0.75rem;
		padding: 1rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius);
	}
</style>
