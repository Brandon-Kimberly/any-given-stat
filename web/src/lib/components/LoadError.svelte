<script lang="ts">
	let { message }: { message: string } = $props();
</script>

<div class="callout" role="alert">
	<strong>Couldn't load this data.</strong>
	{message}
	<span class="muted">If you're running locally, build it with <code>uv run ags build</code>.</span>
</div>
