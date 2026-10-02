<script lang="ts">
	import { base } from '$app/paths';
	import { page } from '$app/state';
</script>

<svelte:head><title>{page.status} · Any Given Stat</title></svelte:head>

<section class="hero">
	<div class="eyebrow" style="color: rgba(255,255,255,0.75)">Flag on the play · {page.status}</div>
	<h1>{page.status === 404 ? 'Incomplete pass.' : 'Something broke.'}</h1>
	<p class="lede">
		{page.status === 404
			? "That page isn't on the field. It may have moved when the site was reorganized."
			: (page.error?.message ?? 'Unexpected error.')}
	</p>
	<p><a href="{base}/">Back to the home page</a> or press <kbd>/</kbd> to search.</p>
</section>
