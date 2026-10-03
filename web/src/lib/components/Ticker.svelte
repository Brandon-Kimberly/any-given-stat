<script lang="ts" module>
	export interface TickerItem {
		key: string;
		href: string;
		tag: string;
		text: string;
		hot?: boolean;
	}
</script>

<script lang="ts">
	// Scrolling score/line ticker. Pauses on hover and focus, has an explicit pause button
	// (WCAG 2.2.2), and sits still under prefers-reduced-motion (it scrolls by hand instead).
	import { base } from '$app/paths';

	let { items, label }: { items: TickerItem[]; label: string } = $props();
	let paused = $state(false);
	// ~5.5 s per item keeps reading speed constant however many games there are.
	const duration = $derived(Math.max(30, items.length * 5.5));
</script>

{#if items.length}
	<div class="ticker" class:paused aria-label={label} role="region">
		<button
			class="pause"
			onclick={() => (paused = !paused)}
			aria-label={paused ? 'Play ticker' : 'Pause ticker'}
			aria-pressed={paused}
		>
			{#if paused}
				<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
			{:else}
				<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5h3v14H7zM14 5h3v14h-3z" /></svg>
			{/if}
		</button>
		<div class="viewport">
			<div class="track" style:animation-duration="{duration}s">
				{#each [0, 1] as copy (copy)}
					<ul aria-hidden={copy === 1 ? 'true' : undefined}>
						{#each items as it (it.key)}
							<li>
								<a href="{base}{it.href}" tabindex={copy === 1 ? -1 : undefined}>
									<span class="tag" class:hot={it.hot}
										>{#if it.hot}<svg viewBox="0 0 16 16" aria-hidden="true"
												><path d="M9.2 1 3 9.1h4.3L6.4 15l6.6-8.6H8.6z" /></svg
											>{/if}{it.tag}</span
									>
									<span class="text">{it.text}</span>
								</a>
							</li>
						{/each}
					</ul>
				{/each}
			</div>
		</div>
	</div>
{/if}

<style>
	.ticker {
		display: flex;
		align-items: stretch;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--surface);
		overflow: hidden;
		box-shadow: var(--shadow-sm);
	}
	.pause {
		flex: none;
		display: grid;
		place-items: center;
		width: 40px;
		min-height: 0;
		padding: 0;
		border: 0;
		border-right: 1px solid var(--border);
		border-radius: 0;
		background: var(--surface-2);
		color: var(--text-secondary);
	}
	.pause svg {
		width: 14px;
		height: 14px;
		fill: currentColor;
	}
	.viewport {
		flex: 1;
		overflow: hidden;
		mask-image: linear-gradient(90deg, transparent, #000 24px, #000 calc(100% - 24px), transparent);
	}
	.track {
		display: flex;
		width: max-content;
		animation: scroll linear infinite;
	}
	.ticker:hover .track,
	.ticker:focus-within .track,
	.paused .track {
		animation-play-state: paused;
	}
	ul {
		display: flex;
		list-style: none;
		margin: 0;
		padding: 0;
	}
	li {
		border-right: 1px solid var(--border);
	}
	a {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.55rem 1rem;
		color: var(--text-primary);
		text-decoration: none;
		white-space: nowrap;
		font-size: 0.85rem;
		font-variant-numeric: tabular-nums;
	}
	a:hover {
		background: var(--surface-2);
	}
	.tag {
		font-size: 0.66rem;
		font-weight: 800;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--text-muted);
	}
	/* Upsets: the same gold bolt as the home page's results, on ordinary ink. */
	.tag.hot {
		color: var(--text-primary);
	}
	.tag svg {
		width: 0.8em;
		height: 0.8em;
		margin-right: 0.3em;
		vertical-align: -0.05em;
		fill: var(--fav);
	}
	.text {
		font-weight: 600;
	}
	@keyframes scroll {
		to {
			transform: translateX(-50%);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.viewport {
			overflow-x: auto;
		}
		.track {
			animation: none;
		}
		ul[aria-hidden='true'] {
			display: none;
		}
		.pause {
			display: none;
		}
	}
</style>
