<script lang="ts">
	import { base } from '$app/paths';
	import type { SeasonStatus } from '$lib/types';
	let { status }: { status: SeasonStatus | undefined } = $props();
</script>

{#if status && !status.complete && status.last_week <= 8}
	<div class="callout" role="note">
		<strong>Small sample.</strong>
		{status.season} is only through week {status.last_week}. Most team stats don't settle until
		roughly mid-season. See <a href="{base}/stability/">Signal vs noise</a> for how many plays each metric
		needs.
	</div>
{/if}
