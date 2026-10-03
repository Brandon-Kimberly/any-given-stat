<script lang="ts">
	// A small line icon per kind of play. Decorative: the play's text says what happened.
	import type { Glyph } from '$lib/playText';

	let { glyph }: { glyph: Glyph } = $props();

	const PATHS: Record<Glyph, string[]> = {
		pass: ['M4 19C6 11 11 6 19 5', 'M14 4l5 1-1 5'],
		incomplete: ['M4 19C6 12 10 8 14 6', 'M16 3l5 5M21 3l-5 5'],
		run: ['M9 12h11', 'M16 8l4 4-4 4', 'M3 8h4M2 12h4M3 16h4'],
		sack: ['M12 3v5M12 16v5M3 12h5M16 12h5', 'M6 6l3 3M15 15l3 3M6 18l3-3M15 9l3-3'],
		kick: ['M12 21v-8', 'M6 13h12', 'M6 13V3M18 13V3'],
		punt: ['M3 19C6 5 18 5 21 19', 'M17 15l4 4 1-5'],
		kickoff: ['M3 20h6', 'M6 20l1.5-3', 'M8 16C10 6 17 4 21 9'],
		penalty: ['M6 21V3', 'M6 4h11l-2.5 4L17 12H6'],
		turnover: ['M4 8h14', 'M15 4l4 4-4 4', 'M20 16H6', 'M9 12l-4 4 4 4'],
		score: ['M12 3l2.6 5.5 6 .8-4.4 4.2 1.1 6L12 16.6l-5.3 2.9 1.1-6-4.4-4.2 6-.8z'],
		kneel: ['M12 4v11', 'M8 11l4 4 4-4', 'M5 20h14'],
		other: ['M12 12h.01']
	};
</script>

<svg viewBox="0 0 24 24" aria-hidden="true" class="glyph glyph-{glyph}">
	{#each PATHS[glyph] as d (d)}<path {d} />{/each}
</svg>

<style>
	.glyph {
		width: 16px;
		height: 16px;
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.glyph-other {
		stroke-width: 5;
	}
	.glyph-score {
		fill: currentColor;
		stroke-width: 1.5;
	}
</style>
