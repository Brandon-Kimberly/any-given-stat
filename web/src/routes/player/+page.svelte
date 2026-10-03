<script lang="ts">
	// /player/?id=<gsis>: QBs, receivers and rushers get the efficiency page; kickers, punters,
	// defenders and everyone else with a stat line a profile built from their game lines
	// (player_index.json says which). Unknown ids fall through to the efficiency page's notice.
	import { page } from '$app/state';
	import PlayerEfficiency from '$lib/components/PlayerEfficiency.svelte';
	import PlayerProfile from '$lib/components/PlayerProfile.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { playerIndex } from '$lib/playerPages.svelte';

	const id = $derived(page.url.searchParams.get('id') ?? '');
	const kind = $derived(playerIndex.value ? (playerIndex.value.get(id)?.[6] ?? 1) : undefined);
</script>

{#if kind === undefined}
	<Skeleton height={300} />
{:else if kind === 0}
	{#key id}<PlayerProfile {id} />{/key}
{:else if kind === 2}
	<PlayerEfficiency>
		{#key id}<PlayerProfile {id} embedded />{/key}
	</PlayerEfficiency>
{:else}
	<PlayerEfficiency />
{/if}
