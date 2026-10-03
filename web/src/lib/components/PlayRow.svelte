<script lang="ts" module>
	import type { Headline, Play, ScoreEvent } from '$lib/playText';

	export interface FeedItem {
		p: Play;
		h: Headline;
		score: ScoreEvent | null;
		/** "1st & 10 · NYG 20" */
		sit: string;
		key: boolean;
		/** Lowercased text for search. */
		text: string;
	}
</script>

<script lang="ts">
	// One play in the feed: glyph, clock, situation, a headline built from the play's fields,
	// a mini field, EPA and the win-probability swing. Selecting it shows the official
	// description and the numbers behind the row.
	import { epa as fmtEpa } from '$lib/format';
	import { quarterLabel, spot } from '$lib/playText';
	import PlayField from './PlayField.svelte';
	import PlayGlyph from './PlayGlyph.svelte';
	import TeamBadge from './TeamBadge.svelte';

	let {
		item,
		home,
		away,
		colors,
		open = false,
		showTeam = false,
		ontoggle,
		onnav,
		onhover
	}: {
		item: FeedItem;
		home: string;
		away: string;
		colors: { home: string; away: string };
		open?: boolean;
		showTeam?: boolean;
		ontoggle?: () => void;
		onnav?: (e: KeyboardEvent) => void;
		onhover?: (p: Play | null) => void;
	} = $props();

	const p = $derived(item.p);
	const h = $derived(item.h);
	const score = $derived(item.score);
	const id = $derived(`play-${p.i}`);
	// Win-probability swing for the offense, in points of percentage.
	const swing = $derived(p.wpa == null ? null : (p.team === home ? p.wpa : -p.wpa) * 100);
	const swingText = $derived(
		swing == null || Math.abs(swing) < 0.5
			? null
			: `${swing > 0 ? '+' : '−'}${Math.abs(swing) < 9.95 ? Math.abs(swing).toFixed(1) : Math.round(Math.abs(swing))}%`
	);
	const fd = $derived(p.flags.includes('1') && !p.flags.includes('T'));
	const big = $derived(p.flags.includes('X'));
	const moment = $derived(score?.big ?? false);
	const scorerColor = $derived(score ? (score.team === home ? colors.home : colors.away) : null);
	const wpAfter = $derived(
		p.wp == null
			? null
			: `${p.wp >= 0.5 ? home : away} ${Math.round((p.wp >= 0.5 ? p.wp : 1 - p.wp) * 100)}%`
	);
	const ballPath = $derived.by(() => {
		if (p.yl == null || p.ylEnd == null || p.kind?.startsWith('fg_')) return null;
		const end =
			p.ylEnd >= 100
				? 'end zone'
				: p.ylEnd <= 0
					? 'own end zone'
					: spot(p.team, p.ylEnd, home, away);
		return `${spot(p.team, p.yl, home, away)} → ${end}`;
	});
</script>

<li
	class="play"
	class:moment
	class:open
	class:try={score && !score.big}
	style:--scorer={scorerColor}
	onmouseenter={() => onhover?.(p)}
	onfocusin={() => onhover?.(p)}
>
	<button
		class="row"
		data-nav
		aria-expanded={open}
		aria-controls={open ? `${id}-more` : undefined}
		onclick={() => ontoggle?.()}
		onkeydown={(e) => onnav?.(e)}
	>
		<span class="glyph tone-{h.tone ?? 'none'}" class:scored={moment}
			><PlayGlyph glyph={h.glyph} /></span
		>
		<span class="when"><b>{quarterLabel(p.qtr)}</b> {p.time ?? ''}</span>
		<span class="main">
			<span class="sit"
				><span class="mclock">{quarterLabel(p.qtr)} {p.time ?? ''} ·</span>
				{#if showTeam}<TeamBadge team={p.team} />{/if}
				{item.sit}</span
			>
			<span class="line"
				><span class="lead">{h.lead}</span>{#each h.facts as f, k (k)}<span class="dot"
						>&nbsp;·</span
					>
					<span class="fact">{f}</span>{/each}
				{#if h.outcome && h.outcome !== score?.label}<span
						class="pill outcome tone-{h.tone ?? 'none'}">{h.outcome}</span
					>{/if}
				{#if fd}<span class="pill mk fd" title="First down">1st down</span>{/if}
				{#if big}<span class="pill mk" title="Explosive: pass of 20+ or run of 10+ yards"
						>Explosive</span
					>{/if}
			</span>
			{#if h.flag}<span class="flag">{h.flag}</span>{/if}
			{#if score}
				<span class="bug" class:quiet={!score.big}>
					<span class="bug-label">{score.label}</span>
					<span class="bug-score" class:lead-side={score.team === away}>{away} {p.awayScore}</span>
					<span class="bug-score" class:lead-side={score.team === home}>{home} {p.homeScore}</span>
				</span>
			{/if}
		</span>
		<span class="viz"><PlayField play={p} {home} {away} {colors} /></span>
		<span class="nums">
			{#if p.epa != null}
				<span
					class="chip {p.epa > 0.05 ? 'good' : p.epa < -0.05 ? 'bad' : ''}"
					title="Expected points added for {p.team}">{fmtEpa(p.epa, 2)} EPA</span
				>
			{/if}
			{#if swingText && swing != null}
				<span class="swing" title="Change in {p.team}'s win probability">
					<span class="sbar" aria-hidden="true"
						><span
							class="sfill"
							class:neg={swing < 0}
							style:width="{Math.min(50, (Math.abs(swing) / 25) * 50)}%"
						></span></span
					>
					<span class="sval">{swingText} WP</span>
				</span>
			{/if}
		</span>
	</button>
	{#if open}
		<div class="more" id="{id}-more">
			<p class="desc">{p.desc}</p>
			<p class="facts">
				{#if ballPath}<span>Ball: {ballPath}</span>{/if}
				{#if p.air != null}<span>Air yards: {p.air}</span>{/if}
				{#if wpAfter}<span>Win probability after: {wpAfter}</span>{/if}
				{#if p.awayScore != null && p.homeScore != null}<span
						>Score: {away} {p.awayScore}, {home} {p.homeScore}</span
					>{/if}
			</p>
		</div>
	{/if}
</li>

<style>
	.play {
		border-top: 1px solid var(--grid);
	}
	.play:first-child {
		border-top: 0;
	}
	.row {
		display: grid;
		grid-template-columns: 28px 3.3rem minmax(0, 1fr) 9rem 6.6rem;
		align-items: start;
		gap: 0.7rem;
		width: 100%;
		min-height: 0;
		padding: 0.55rem 0.75rem;
		border: 0;
		border-radius: 0;
		background: transparent;
		color: inherit;
		text-align: left;
		font-size: 0.85rem;
		line-height: 1.35;
	}
	.row:hover,
	.open .row {
		background: var(--surface-2);
	}
	.row:active {
		transform: none;
	}
	.row:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}
	.moment {
		background: color-mix(in srgb, var(--scorer) 9%, var(--surface));
		box-shadow: inset 4px 0 0 var(--scorer);
	}
	.try {
		box-shadow: inset 2px 0 0 var(--scorer);
	}
	.glyph {
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: var(--surface-2);
		color: var(--text-secondary);
	}
	.row:hover .glyph,
	.open .glyph {
		background: var(--surface-3);
	}
	.glyph.tone-bad {
		background: var(--bad-wash);
		color: var(--text-primary);
	}
	.glyph.scored,
	.row:hover .glyph.scored {
		background: var(--scorer);
		color: var(--surface);
	}
	.when {
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		line-height: 1.3;
		padding-top: 0.1rem;
	}
	.when b {
		display: block;
		color: var(--text-secondary);
	}
	.mclock {
		display: none;
	}
	.main {
		display: grid;
		gap: 0.15rem;
		min-width: 0;
	}
	.sit {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		color: var(--text-muted);
		font-size: 0.76rem;
		font-variant-numeric: tabular-nums;
	}
	.line {
		display: block;
	}
	.dot {
		color: var(--text-muted);
	}
	.pill {
		display: inline-block;
		margin-left: 0.35rem;
		vertical-align: 0.1em;
		line-height: 1.4;
	}
	.lead {
		font-weight: 650;
		color: var(--text-primary);
	}
	.fact {
		color: var(--text-secondary);
	}
	.outcome {
		font-size: 0.7rem;
		font-weight: 800;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		padding: 0.05rem 0.45rem;
		border-radius: 999px;
		background: var(--surface-3);
		color: var(--text-primary);
	}
	.outcome.tone-good {
		background: var(--good-wash);
	}
	.outcome.tone-bad {
		background: var(--bad-wash);
	}
	.mk {
		font-size: 0.66rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--text-secondary);
		border: 1px solid var(--border-strong);
		border-radius: 4px;
		padding: 0 0.3rem;
	}
	.mk.fd {
		border-color: var(--warning);
	}
	.flag {
		font-size: 0.76rem;
		color: var(--text-secondary);
	}
	.bug {
		display: inline-flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.25rem 0.5rem;
		margin-top: 0.2rem;
		font-size: 0.78rem;
		font-variant-numeric: tabular-nums;
	}
	.bug-label {
		font-weight: 800;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		font-size: 0.7rem;
		color: var(--text-primary);
	}
	.bug-score {
		color: var(--text-secondary);
		padding: 0 0.4rem;
		border-radius: 5px;
		background: var(--surface);
		border: 1px solid var(--border);
	}
	.bug-score.lead-side {
		color: var(--text-primary);
		font-weight: 800;
		border-color: var(--scorer);
	}
	.bug.quiet .bug-label {
		color: var(--text-secondary);
	}
	.viz {
		padding-top: 0.3rem;
	}
	.nums {
		display: grid;
		justify-items: end;
		align-content: start;
		gap: 0.25rem;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
	.swing {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.72rem;
		color: var(--text-secondary);
	}
	.sbar {
		position: relative;
		width: 30px;
		height: 6px;
		border-radius: 3px;
		background: var(--surface-3);
	}
	.sbar::after {
		content: '';
		position: absolute;
		left: 50%;
		top: -1px;
		bottom: -1px;
		width: 1px;
		background: var(--axis);
	}
	.sfill {
		position: absolute;
		top: 0;
		bottom: 0;
		left: 50%;
		border-radius: 0 3px 3px 0;
		background: var(--good);
	}
	.sfill.neg {
		left: auto;
		right: 50%;
		border-radius: 3px 0 0 3px;
		background: var(--bad);
	}
	.more {
		padding: 0.1rem 0.75rem 0.7rem calc(0.75rem + 28px + 0.7rem);
		background: var(--surface-2);
		font-size: 0.8rem;
	}
	.desc {
		margin: 0 0 0.3rem;
		color: var(--text-secondary);
		line-height: 1.45;
	}
	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem 1rem;
		margin: 0;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	@media (max-width: 720px) {
		.row {
			grid-template-columns: 28px minmax(0, 1fr) auto;
			grid-template-areas: 'glyph main main' '. viz nums';
			align-items: center;
			gap: 0.35rem 0.6rem;
			padding: 0.55rem 0.6rem;
		}
		.glyph {
			grid-area: glyph;
		}
		.when {
			display: none;
		}
		.mclock {
			display: inline;
		}
		.main {
			grid-area: main;
		}
		.viz {
			grid-area: viz;
			padding-top: 0;
		}
		.nums {
			grid-area: nums;
			display: flex;
			align-items: center;
			gap: 0.5rem;
		}
		.main {
			align-self: start;
		}
		.more {
			padding-left: calc(0.6rem + 28px + 0.6rem);
		}
	}
</style>
