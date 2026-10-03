<script lang="ts">
	import { base } from '$app/paths';
	import { page } from '$app/state';
	const missing = $derived(page.status === 404);
</script>

<svelte:head><title>{page.status} · Any Given Stat</title></svelte:head>

<section class="hero oops">
	<div class="copy">
		<div class="eyebrow" style="color: rgba(255,255,255,0.75)">Flag on the play</div>
		<div class="code" aria-hidden="true">{page.status}</div>
		<h1>{missing ? 'No good. Wide right.' : 'Something broke.'}</h1>
		<p class="lede">
			{missing
				? "That page isn't on the field. It may have moved when the site was reorganized."
				: (page.error?.message ?? 'Unexpected error.')}
		</p>
		<p class="actions">
			<a class="back" href="{base}/">Back to the home page</a>
			<span>or press <kbd>/</kbd> to search</span>
		</p>
	</div>
	<!-- Goalposts with a kick sailing wide right, on a loop. -->
	<svg class="posts" viewBox="0 0 220 220" aria-hidden="true">
		<path class="upright" d="M60 20V120M160 20V120M60 120H160M110 120V205" />
		<path class="arc" d="M100 215 C120 120 170 60 205 18" />
		<g class="kick">
			<ellipse rx="11" ry="7" />
			<path d="M-5 0h10M-3-2.5v5M0-2.5v5M3-2.5v5" />
		</g>
	</svg>
</section>

<style>
	.oops {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		gap: 1rem;
		min-height: 360px;
	}
	.copy {
		position: relative;
		z-index: 1;
	}
	.code {
		font: 800 clamp(4.5rem, 3rem + 7vw, 8rem) / 0.9 var(--display);
		font-stretch: 125%;
		letter-spacing: -0.04em;
		background: linear-gradient(100deg, #fff 20%, #a5f3fc 60%, #c4b5fd);
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
		filter: drop-shadow(0 10px 40px rgba(165, 243, 252, 0.35));
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem;
		margin-top: 1rem;
	}
	.back {
		display: inline-flex;
		padding: 0.55rem 1rem;
		border-radius: 10px;
		background: #fff;
		color: #0f2a4f !important;
		font-weight: 700;
		text-decoration: none;
	}
	.posts {
		width: clamp(140px, 22vw, 240px);
		overflow: visible;
	}
	.upright {
		fill: none;
		stroke: #fde68a;
		stroke-width: 6;
		stroke-linecap: round;
		filter: drop-shadow(0 0 10px rgba(253, 230, 138, 0.5));
	}
	.arc {
		fill: none;
		stroke: rgba(255, 255, 255, 0.35);
		stroke-width: 2;
		stroke-dasharray: 4 7;
	}
	.kick ellipse {
		fill: #9a5b2c;
		stroke: #fff;
		stroke-width: 1.5;
	}
	.kick path {
		stroke: #fff;
		stroke-width: 1.2;
	}
	.kick {
		offset-path: path('M100 215 C120 120 170 60 205 18');
		offset-rotate: auto;
		animation: kick 2.6s cubic-bezier(0.3, 0.6, 0.4, 1) infinite;
	}
	@keyframes kick {
		0% {
			offset-distance: 0%;
			opacity: 0;
		}
		10% {
			opacity: 1;
		}
		85% {
			opacity: 1;
		}
		100% {
			offset-distance: 100%;
			opacity: 0;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.kick {
			animation: none;
			offset-distance: 70%;
		}
	}
	@media (max-width: 560px) {
		.oops {
			grid-template-columns: 1fr;
		}
		.posts {
			display: none;
		}
	}
</style>
