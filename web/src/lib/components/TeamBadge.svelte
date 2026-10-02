<script lang="ts">
	import { base } from '$app/paths';
	import { favorite } from '$lib/favorite.svelte';
	import { teamMeta } from '$lib/teams.svelte';

	let {
		team,
		name = false,
		size = 'sm',
		link = false
	}: {
		team: string;
		name?: boolean | 'nick';
		size?: 'sm' | 'md' | 'lg';
		link?: boolean;
	} = $props();

	const meta = $derived(teamMeta.byTeam[team]);
	const style = $derived(meta ? `--badge-bg:${meta.color};--badge-fg:${meta.badge_fg}` : '');
	const label = $derived(name === 'nick' ? (meta?.nick ?? team) : (meta?.name ?? team));
</script>

{#if link}
	<a class="team {size}" href="{base}/team/?t={team}" title={meta?.name ?? team}>
		<span class="badge" class:fav={favorite.team === team} {style}>{team}</span>{#if name}<span
				class="name">{label}</span
			>{/if}
	</a>
{:else}
	<span class="team {size}" title={meta?.name ?? team}>
		<span class="badge" class:fav={favorite.team === team} {style}>{team}</span>{#if name}<span
				class="name">{label}</span
			>{/if}
	</span>
{/if}

<style>
	.team {
		display: inline-flex;
		align-items: center;
		gap: 0.45em;
		color: inherit;
		text-decoration: none;
		white-space: nowrap;
	}
	a.team:hover .name {
		text-decoration: underline;
	}
	.badge {
		--badge-bg: var(--surface-3);
		--badge-fg: var(--text-primary);
		display: inline-grid;
		place-items: center;
		min-width: 2.6em;
		height: 1.75em;
		padding: 0 0.35em;
		border-radius: 6px;
		background: var(--badge-bg);
		color: var(--badge-fg);
		font: 800 0.72em/1 var(--display);
		letter-spacing: 0.02em;
		box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.12);
	}
	.badge.fav {
		box-shadow:
			0 0 0 1.5px var(--surface),
			0 0 0 3px var(--fav, #e8b100);
	}
	.md .badge {
		font-size: 0.85em;
	}
	.lg .badge {
		font-size: 1.15em;
		border-radius: 10px;
		height: 2.1em;
		min-width: 3em;
	}
	.name {
		font-weight: 600;
	}
</style>
