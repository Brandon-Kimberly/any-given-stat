<script lang="ts" module>
	export const DRIVE_RESULT: Record<string, string> = {
		Touchdown: 'TD',
		'Field goal': 'FG',
		'Missed field goal': 'Missed FG',
		Punt: 'Punt',
		Turnover: 'Turnover',
		'Turnover on downs': 'Downs',
		'End of half': 'End of half',
		'Opp touchdown': 'Return TD',
		Safety: 'Safety'
	};
</script>

<script lang="ts">
	// Every possession on one field: away's end zone on the left, home's on the right, so
	// away drives run left to right and home drives right to left. Clicking a drive opens it
	// in the play-by-play feed; `hot` highlights the drive of the hovered play.
	import type { Drive } from '$lib/types';
	import { quarterLabel } from '$lib/playText';
	import TeamBadge from './TeamBadge.svelte';

	let {
		drives,
		home,
		away,
		colors,
		hot = null,
		onpick,
		onhover
	}: {
		drives: Drive[];
		home: string;
		away: string;
		colors: { home: string; away: string };
		hot?: number | null;
		onpick?: (n: number) => void;
		onhover?: (n: number | null) => void;
	} = $props();

	const colorOf = (t: string) => (t === home ? colors.home : colors.away);
	const pos = (d: Drive, yl: number) => (d.posteam === away ? yl : 100 - yl);
	function bar(d: Drive) {
		if (d.start_yl == null || d.end_yl == null) return null;
		const a = pos(d, d.start_yl);
		const b = pos(d, Math.max(0, Math.min(100, d.end_yl)));
		return { left: Math.min(a, b), width: Math.max(0.8, Math.abs(b - a)), rightward: b >= a };
	}
</script>

<section class="card">
	<div class="card-head">
		<h2>Drive chart</h2>
		<span class="legend muted"
			><TeamBadge team={away} /> drives → · ← <TeamBadge team={home} /> drives</span
		>
	</div>
	<p class="sub">Every possession, start to finish. Select one to open its plays below.</p>
	<ol class="drives" onmouseleave={() => onhover?.(null)}>
		{#each drives as d, i (d.n)}
			{@const b = bar(d)}
			<li>
				<button
					class="drive"
					class:hot={hot === d.n}
					onclick={() => onpick?.(d.n)}
					onmouseenter={() => onhover?.(d.n)}
					onfocus={() => onhover?.(d.n)}
					onblur={() => onhover?.(null)}
				>
					<span class="when">{d.qtr ? quarterLabel(d.qtr) : ''} {d.start_clock ?? ''}</span>
					<TeamBadge team={d.posteam} />
					<span class="field" aria-hidden="true">
						<span class="ez" style:background={colors.away}></span>
						<span class="turf">
							{#if b}
								<span
									class="bar"
									class:rightward={b.rightward}
									style:left="{b.left}%"
									style:width="{b.width}%"
									style:background={colorOf(d.posteam)}
									style:animation-delay="{Math.min(i, 30) * 18}ms"
								></span>
							{/if}
						</span>
						<span class="ez" style:background={colors.home}></span>
					</span>
					<span class="result" class:score={(d.points ?? 0) > 0}
						>{DRIVE_RESULT[d.result ?? ''] ?? d.result ?? '–'}</span
					>
					<span class="stats" title="Plays · yards · time of possession"
						>{d.plays} pl · {d.yards ?? '–'} yd · {d.top ?? '–'}</span
					>
					<span class="sr-only">, show this drive's plays</span>
				</button>
			</li>
		{/each}
	</ol>
</section>

<style>
	.legend {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.8rem;
	}
	.drives {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 2px;
	}
	.drive {
		display: grid;
		grid-template-columns: 5.2rem 2.9rem 1fr 6.5rem 9.5rem;
		align-items: center;
		gap: 0.6rem;
		width: 100%;
		min-height: 0;
		padding: 0.22rem 0.4rem;
		border: 0;
		border-radius: 8px;
		background: transparent;
		color: inherit;
		text-align: left;
		font-size: 0.8rem;
	}
	.drive:hover,
	.drive.hot {
		background: var(--surface-2);
	}
	.drive.hot {
		box-shadow: inset 0 0 0 1px var(--border-strong);
	}
	.when,
	.stats {
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.stats {
		text-align: right;
	}
	.field {
		display: grid;
		grid-template-columns: 6% 1fr 6%;
		height: 18px;
		border-radius: 4px;
		overflow: hidden;
	}
	.ez {
		opacity: 0.5;
	}
	.turf {
		position: relative;
		background:
			repeating-linear-gradient(
				90deg,
				transparent 0 calc(10% - 1px),
				var(--border-strong) calc(10% - 1px) 10%
			),
			var(--surface-2);
	}
	.bar {
		position: absolute;
		top: 4px;
		bottom: 4px;
		border-radius: 3px;
		transform-origin: right;
		animation: drive-in 0.45s var(--ease) both;
		/* Pointed at the end the drive finished. */
		clip-path: polygon(6px 0, 100% 0, 100% 100%, 6px 100%, 0 50%);
	}
	.bar.rightward {
		transform-origin: left;
		clip-path: polygon(0 0, calc(100% - 6px) 0, 100% 50%, calc(100% - 6px) 100%, 0 100%);
	}
	@keyframes drive-in {
		from {
			transform: scaleX(0);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.bar {
			animation: none;
		}
	}
	.result {
		font-weight: 600;
		color: var(--text-secondary);
	}
	.result.score {
		color: var(--text-primary);
		font-weight: 800;
	}
	@media (max-width: 720px) {
		.drive {
			grid-template-columns: 2.9rem minmax(0, 1fr) minmax(4.6rem, auto);
			grid-template-areas: 'badge field result' 'when when stats';
			row-gap: 0.1rem;
		}
		.drive :global(.team) {
			grid-area: badge;
		}
		.field {
			grid-area: field;
		}
		.result {
			grid-area: result;
		}
		.when {
			grid-area: when;
		}
		.stats {
			grid-area: stats;
		}
	}
</style>
