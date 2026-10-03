<script lang="ts" module>
	export interface HeroStat {
		label: string;
		value: string;
		/** Small trailing figure, e.g. "+4.7" or "12%". */
		figure?: string;
		href?: string;
	}
</script>

<script lang="ts">
	// The home page's opening: the headline, three live numbers, and last week's wildest game
	// drawn as its win-probability trace (real data, drawn once, then still). The trace sits
	// behind the copy, faded under it, so text contrast never depends on it.
	import { base } from '$app/paths';
	import { excitementPercentile } from '$lib/games';
	import { teamName } from '$lib/teams.svelte';
	import type { Highlight } from '$lib/types';

	let {
		eyebrow,
		highlight,
		stats,
		tint
	}: {
		eyebrow: string;
		highlight: Highlight | null | undefined;
		stats: HeroStat[];
		tint: { from: string; to: string } | null;
	} = $props();

	const W = 1000;
	const H = 400;
	const PAD = 34;
	const y = (wp: number) => PAD + (1 - wp) * (H - 2 * PAD);

	/** Catmull-Rom through the points as cubic Béziers: the same data, drawn as a curve. */
	function curve(p: [number, number][]): string {
		let d = `M${p[0][0].toFixed(1)} ${p[0][1].toFixed(1)}`;
		for (let i = 0; i < p.length - 1; i++) {
			const [p0, p1, p2, p3] = [p[i - 1] ?? p[i], p[i], p[i + 1], p[i + 2] ?? p[i + 1]];
			const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
			const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
			d += `C${c1[0].toFixed(1)} ${c1[1].toFixed(1)} ${c2[0].toFixed(1)} ${c2[1].toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
		}
		return d;
	}

	const trace = $derived.by(() => {
		const pts = highlight?.wp ?? [];
		if (pts.length < 2) return null;
		const end = Math.max(3600, pts.at(-1)![0]);
		const x = (t: number) => (t / end) * W;
		// Light smoothing (a 3-play running mean) so a decorative trace reads as a story, not
		// noise; the first and last points stay exact.
		const sm = pts.map(([t, wp], i): [number, number] => {
			if (i === 0 || i === pts.length - 1) return [x(t), y(wp)];
			const win = pts.slice(Math.max(0, i - 1), i + 2).map((q) => q[1]);
			return [x(t), y(win.reduce((a, b) => a + b, 0) / win.length)];
		});
		const d = curve(sm);
		const mid = y(0.5);
		const last = sm.at(-1)!;
		return {
			d,
			area: `${d}L${last[0].toFixed(1)} ${mid}L0 ${mid}Z`,
			mid,
			quarters: [900, 1800, 2700, ...(end > 3600 ? [3600] : [])].map(x),
			endX: (last[0] / W) * 100,
			endY: (last[1] / H) * 100,
			homeWon: highlight!.home_score > highlight!.away_score
		};
	});
	const pctile = $derived(highlight ? excitementPercentile(highlight.excitement) : 0);

	// Loops (the end-dot pulse) pause while the hero is off screen.
	let el = $state<HTMLElement>();
	let hidden = $state(false);
	$effect(() => {
		if (!el) return;
		const io = new IntersectionObserver(([e]) => (hidden = !e.isIntersecting));
		io.observe(el);
		return () => io.disconnect();
	});
</script>

<section
	bind:this={el}
	class="hero home-hero"
	class:paused={hidden}
	class:tinted={!!tint}
	style:--hero-from={tint?.from}
	style:--hero-to={tint?.to}
>
	<div class="backdrop" aria-hidden="true"></div>

	{#if trace && highlight}
		<div class="trace-wrap" aria-hidden="true">
			<svg class="trace" viewBox="0 0 {W} {H}" preserveAspectRatio="none">
				<defs>
					<linearGradient id="hh-stroke" x1="0" x2="1" y1="0" y2="0">
						<stop offset="0" stop-color="#7dd3fc" stop-opacity="0.35" />
						<stop offset="0.55" stop-color="#a5f3fc" />
						<stop offset="1" stop-color="#ffffff" />
					</linearGradient>
					<linearGradient id="hh-fill" x1="0" x2="0" y1="0" y2="1">
						<stop offset="0" stop-color="#67e8f9" stop-opacity="0.26" />
						<stop offset="0.5" stop-color="#67e8f9" stop-opacity="0.02" />
						<stop offset="0.5" stop-color="#c4b5fd" stop-opacity="0.02" />
						<stop offset="1" stop-color="#c4b5fd" stop-opacity="0.24" />
					</linearGradient>
				</defs>
				{#each trace.quarters as qx (qx)}
					<line class="q" x1={qx} x2={qx} y1="0" y2={H} />
				{/each}
				<line class="mid" x1="0" x2={W} y1={trace.mid} y2={trace.mid} />
				<path class="area" d={trace.area} fill="url(#hh-fill)" />
				<path class="glow" d={trace.d} pathLength="1" />
				<path class="line" d={trace.d} pathLength="1" stroke="url(#hh-stroke)" />
			</svg>
			<span class="side top" style:top="calc({(trace.mid / H) * 100}% - 1.35rem)"
				>{highlight.home} favored ↑</span
			>
			<span class="side bottom" style:top="calc({(trace.mid / H) * 100}% + 0.45rem)"
				>{highlight.away} favored ↓</span
			>
			<span class="end" style:left="{trace.endX}%" style:top="{trace.endY}%"></span>
		</div>
	{/if}

	<div class="copy">
		<div class="eyebrow">{eyebrow}</div>
		<h1>Know which numbers <span class="accent">matter.</span></h1>
		<p class="lede">
			Every NFL play since 2016: opponent-adjusted ratings, win probability, forecasts scored
			honestly against Vegas, and which stats are signal.
		</p>
	</div>

	<dl class="stats">
		{#each stats as s (s.label)}
			<div class="stat">
				<dt>{s.label}</dt>
				<dd>
					{#if s.href}<a href="{base}{s.href}">{s.value}</a>{:else}{s.value}{/if}
					{#if s.figure}<span class="fig">{s.figure}</span>{/if}
				</dd>
			</div>
		{/each}
	</dl>

	{#if highlight}
		<a class="gotw" href="{base}/game/?id={highlight.game_id}">
			<span class="kicker">Game of the week · Week {highlight.week}</span>
			<span class="score">
				<span class:won={!trace?.homeWon}>{highlight.away} {highlight.away_score}</span>
				<span class="at">@</span>
				<span class:won={trace?.homeWon}>{highlight.home} {highlight.home_score}</span>
			</span>
			<span class="why">
				The favorite flipped {highlight.favorite_changes} times. Wilder than {Math.min(
					99,
					Math.round(pctile * 100)
				)}% of games since 2016.
			</span>
			<span class="cta"
				>See how {teamName(trace?.homeWon ? highlight.home : highlight.away)} won it
				<span aria-hidden="true">→</span></span
			>
		</a>
	{/if}
</section>

<style>
	.home-hero {
		display: grid;
		grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
		grid-template-areas:
			'copy gotw'
			'stats gotw';
		align-items: end;
		gap: 1.5rem 2rem;
		min-height: 360px;
		padding: clamp(1.4rem, 1rem + 2.4vw, 2.6rem);
		isolation: isolate;
		background: #0a1426;
	}
	/* Base: deep night navy (or the favorite team's darkened colors), a soft key light, a
	   faint yard-line grid, and fine grain so the gradient never bands. */
	.backdrop {
		position: absolute;
		inset: 0;
		z-index: -2;
		background:
			radial-gradient(70% 90% at 78% 30%, rgba(125, 211, 252, 0.16), transparent 60%),
			radial-gradient(60% 80% at 0% 100%, rgba(167, 139, 250, 0.14), transparent 60%),
			linear-gradient(150deg, #0b1830 0%, #0d1f3d 45%, #102a52 100%);
	}
	.tinted .backdrop {
		background:
			radial-gradient(70% 90% at 78% 30%, rgba(255, 255, 255, 0.12), transparent 60%),
			linear-gradient(150deg, color-mix(in srgb, var(--hero-from) 80%, #000), var(--hero-to));
	}
	.backdrop::before {
		content: '';
		position: absolute;
		inset: 0;
		background: repeating-linear-gradient(
			90deg,
			transparent 0 calc(10% - 1px),
			rgba(255, 255, 255, 0.045) calc(10% - 1px) 10%
		);
		mask-image: linear-gradient(to bottom, transparent, #000 30%, #000 70%, transparent);
		-webkit-mask-image: linear-gradient(to bottom, transparent, #000 30%, #000 70%, transparent);
	}
	.backdrop::after {
		content: '';
		position: absolute;
		inset: 0;
		opacity: 0.18;
		mix-blend-mode: overlay;
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
	}

	/* The trace: right side, fading out under the copy. */
	.trace-wrap {
		position: absolute;
		z-index: -1;
		top: 10%;
		bottom: 34%;
		right: 3.5%;
		width: 64%;
		mask-image: linear-gradient(to right, transparent 0%, #000 34%);
		-webkit-mask-image: linear-gradient(to right, transparent 0%, #000 34%);
		pointer-events: none;
	}
	.trace {
		width: 100%;
		height: 100%;
		overflow: visible;
	}
	.q {
		stroke: rgba(255, 255, 255, 0.07);
		stroke-width: 1;
		vector-effect: non-scaling-stroke;
	}
	.mid {
		stroke: rgba(255, 255, 255, 0.22);
		stroke-width: 1;
		stroke-dasharray: 3 5;
		vector-effect: non-scaling-stroke;
	}
	.line,
	.glow {
		fill: none;
		stroke-linejoin: round;
		stroke-linecap: round;
		vector-effect: non-scaling-stroke;
	}
	.line {
		stroke-width: 2.25;
	}
	.glow {
		stroke: #67e8f9;
		stroke-width: 9;
		opacity: 0.18;
		filter: blur(6px);
	}
	.side {
		position: absolute;
		left: 40%;
		font: 600 0.66rem/1 var(--sans, inherit);
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: rgba(255, 255, 255, 0.5);
	}
	.end {
		position: absolute;
		width: 10px;
		height: 10px;
		margin: -5px 0 0 -5px;
		border-radius: 50%;
		background: #fff;
		box-shadow:
			0 0 0 3px rgba(103, 232, 249, 0.35),
			0 0 18px 4px rgba(103, 232, 249, 0.55);
	}

	/* Copy */
	.copy {
		grid-area: copy;
		max-width: 36rem;
	}
	.copy .eyebrow {
		color: rgba(255, 255, 255, 0.72);
	}
	.home-hero h1 {
		margin: 0.35rem 0 0.7rem;
		font-size: clamp(2.05rem, 1.35rem + 2.9vw, 3.5rem);
		font-stretch: 112%;
		line-height: 1;
		letter-spacing: -0.025em;
		max-width: 14ch;
	}
	/* Light end ≥ 7:1 on the navy; static, no animation. */
	.accent {
		background: linear-gradient(95deg, #ffffff 0%, #a5f3fc 70%);
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
	}
	/* On a team's colors a cyan end can sit too close to the background: keep it near-white. */
	.tinted .accent {
		background-image: linear-gradient(95deg, #ffffff 0%, #e0f2fe 80%);
		text-shadow: none;
		filter: drop-shadow(0 2px 14px rgba(0, 0, 0, 0.25));
	}
	.lede {
		margin: 0;
		max-width: 46ch;
		font-size: 1rem;
		line-height: 1.55;
	}

	/* Live numbers: a quiet strip under the copy. */
	.stats {
		grid-area: stats;
		display: grid;
		grid-template-columns: repeat(3, minmax(0, auto));
		justify-content: start;
		gap: 0 2.25rem;
		margin: 0;
		padding-top: 1.1rem;
		border-top: 1px solid rgba(255, 255, 255, 0.14);
	}
	.stat dt {
		font-size: 0.68rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: rgba(255, 255, 255, 0.68);
	}
	.stat dd {
		margin: 0.25rem 0 0;
		font: 800 clamp(1.15rem, 1rem + 0.8vw, 1.55rem) / 1.1 var(--display);
		font-stretch: 105%;
		white-space: nowrap;
	}
	.stat a {
		text-decoration: none;
		background-image: linear-gradient(rgba(255, 255, 255, 0.4), rgba(255, 255, 255, 0.4));
		background-size: 100% 2px;
		background-position: 0 100%;
		background-repeat: no-repeat;
		transition: background-size 0.2s;
	}
	.stat a:hover {
		background-image: linear-gradient(#fff, #fff);
	}
	.fig {
		margin-left: 0.3rem;
		font-family: var(--sans, inherit);
		font-weight: 600;
		font-size: 0.8em;
		color: rgba(255, 255, 255, 0.78);
		font-variant-numeric: tabular-nums;
	}

	/* Game of the week: a glass card over the trace's end. */
	.gotw {
		grid-area: gotw;
		justify-self: end;
		align-self: end;
		display: grid;
		gap: 0.3rem;
		width: min(100%, 22rem);
		padding: 0.9rem 1rem;
		border-radius: 14px;
		border: 1px solid rgba(255, 255, 255, 0.16);
		background: rgba(9, 18, 36, 0.62);
		backdrop-filter: blur(10px) saturate(1.2);
		-webkit-backdrop-filter: blur(10px) saturate(1.2);
		text-decoration: none;
		box-shadow: 0 18px 40px -20px rgba(0, 0, 0, 0.6);
		transition:
			transform 0.2s var(--ease),
			border-color 0.2s;
	}
	.gotw:hover {
		transform: translateY(-2px);
		border-color: rgba(255, 255, 255, 0.32);
	}
	.kicker {
		font-size: 0.66rem;
		font-weight: 700;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #a5f3fc;
	}
	.score {
		display: flex;
		align-items: baseline;
		gap: 0.45rem;
		font: 800 1.2rem/1.15 var(--display);
		font-variant-numeric: tabular-nums;
		color: rgba(255, 255, 255, 0.72);
	}
	.score .won {
		color: #fff;
	}
	.score .at {
		font: 500 0.8rem/1 var(--sans, inherit);
		color: rgba(255, 255, 255, 0.6);
	}
	.why {
		font-size: 0.8rem;
		line-height: 1.4;
		color: rgba(255, 255, 255, 0.8);
	}
	.cta {
		margin-top: 0.15rem;
		font-size: 0.8rem;
		font-weight: 600;
		color: #fff;
	}

	/* Motion: the line draws once; the end dot breathes while on screen. */
	@media (prefers-reduced-motion: no-preference) {
		.line,
		.glow {
			stroke-dasharray: 1;
			stroke-dashoffset: 1;
			animation: draw 2.4s cubic-bezier(0.55, 0.1, 0.25, 1) 0.15s forwards;
		}
		.area {
			opacity: 0;
			animation: fade 1.2s ease 1.6s forwards;
		}
		.end {
			opacity: 0;
			animation:
				fade 0.4s ease 2.45s forwards,
				breathe 3.2s ease-in-out 2.9s infinite;
		}
		.paused .end {
			animation-play-state: paused;
		}
	}
	@keyframes draw {
		to {
			stroke-dashoffset: 0;
		}
	}
	@keyframes fade {
		to {
			opacity: 1;
		}
	}
	@keyframes breathe {
		50% {
			box-shadow:
				0 0 0 7px rgba(103, 232, 249, 0.12),
				0 0 26px 8px rgba(103, 232, 249, 0.4);
		}
	}

	@media (max-width: 860px) {
		.home-hero {
			grid-template-columns: 1fr;
			grid-template-areas: 'copy' 'gotw' 'stats';
			min-height: 0;
			gap: 1.1rem;
		}
		.trace-wrap {
			top: auto;
			bottom: 0;
			right: 0;
			height: 58%;
			width: 100%;
			opacity: 0.55;
			mask-image: linear-gradient(to bottom, transparent, #000 45%);
			-webkit-mask-image: linear-gradient(to bottom, transparent, #000 45%);
		}
		.side {
			display: none;
		}
		.gotw {
			justify-self: stretch;
			width: auto;
		}
	}
	@media (max-width: 520px) {
		.lede {
			font-size: 0.92rem;
		}
		.stats {
			gap: 0 1.1rem;
		}
	}
</style>
