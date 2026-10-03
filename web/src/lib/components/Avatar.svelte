<script lang="ts">
	// A player's headshot on a team-colored backdrop, or their initials when there's no photo
	// (or it can't load). Decorative: the player's name is always shown next to it.
	import { nightShade, teamMeta } from '$lib/teams.svelte';

	let {
		name,
		src = null,
		team = '',
		size = 40
	}: { name: string; src?: string | null; team?: string; size?: number } = $props();

	let failed = $state(false);
	const color = $derived(teamMeta.byTeam[team]?.color ?? '#3b4a66');
	const deep = $derived(nightShade(color, 7) ?? '#0b1220');
	const initials = $derived(
		name
			.replace(/\b(Jr|Sr|II|III|IV)\.?$/i, '')
			.split(/\s+/)
			.filter(Boolean)
			.map((w) => w[0])
			.slice(0, 2)
			.join('')
			.toUpperCase()
	);
	$effect(() => {
		void src;
		failed = false;
	});
</script>

<span
	class="avatar"
	style:--size="{size}px"
	style:--c={color}
	style:--deep={deep}
	aria-hidden="true"
>
	{#if src && !failed}
		<img {src} alt="" loading="lazy" decoding="async" onerror={() => (failed = true)} />
	{:else}
		<span class="initials">{initials}</span>
	{/if}
</span>

<style>
	.avatar {
		position: relative;
		display: inline-grid;
		place-items: center;
		flex: none;
		width: var(--size);
		height: var(--size);
		border-radius: 50%;
		overflow: hidden;
		background:
			radial-gradient(
				circle at 50% 120%,
				color-mix(in srgb, var(--c) 85%, #fff 0%),
				transparent 70%
			),
			linear-gradient(160deg, var(--deep), color-mix(in srgb, var(--deep) 70%, #000));
		box-shadow:
			0 0 0 2px color-mix(in srgb, var(--c) 70%, transparent),
			0 8px 22px -10px color-mix(in srgb, var(--c) 80%, transparent);
	}
	img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: 50% 15%;
		transform: translateY(6%) scale(1.08);
	}
	.initials {
		color: #fff;
		font: 800 calc(var(--size) * 0.36) / 1 var(--display);
		font-stretch: 110%;
		letter-spacing: 0.02em;
	}
</style>
