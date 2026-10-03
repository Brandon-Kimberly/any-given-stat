<script lang="ts">
	// A team's logo tile (served with the data, see pipeline fetch.fetch_logos) with a soft
	// glow in the team's color; falls back to the text badge when there's no logo.
	import { base } from '$app/paths';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { teamMeta, teamName } from '$lib/teams.svelte';

	let {
		team,
		size = 44,
		glow = true,
		label = false
	}: {
		team: string;
		size?: number;
		glow?: boolean;
		/** Give the image its team name as alt text (when no text label sits next to it). */
		label?: boolean;
	} = $props();

	const meta = $derived(teamMeta.byTeam[team]);
	let failed = $state(false);
</script>

{#if meta?.logo && !failed}
	<img
		class="logo"
		class:glow
		src="{base}/data/{meta.logo}"
		alt={label ? teamName(team) : ''}
		width={size}
		height={size}
		loading="lazy"
		decoding="async"
		style:--c={meta.color}
		onerror={() => (failed = true)}
	/>
{:else}
	<TeamBadge {team} size={size >= 56 ? 'lg' : size >= 32 ? 'md' : 'sm'} />
{/if}

<style>
	.logo {
		display: block;
		flex: none;
		border-radius: 24%;
		object-fit: cover;
		background: var(--c);
		box-shadow:
			inset 0 0 0 1px rgba(255, 255, 255, 0.18),
			0 0 0 1px rgba(0, 0, 0, 0.06);
		transition:
			transform 0.3s cubic-bezier(0.3, 1.3, 0.5, 1),
			box-shadow 0.3s var(--ease);
	}
	.logo.glow {
		box-shadow:
			0 0 0 1px rgba(255, 255, 255, 0.14),
			0 10px 28px -10px color-mix(in srgb, var(--c) 85%, transparent);
	}
</style>
