<script lang="ts">
	// Drive chart (every possession on one field) and a filterable play-by-play feed.
	// Hovering a play reports its elapsed time so the page can mark it on the WP chart.
	import { epa as fmtEpa } from '$lib/format';
	import { elapsedAt } from '$lib/games';
	import { matchupColors } from '$lib/teams.svelte';
	import type { Drive, GamePlays, PlayRow } from '$lib/types';
	import TeamBadge from './TeamBadge.svelte';

	let {
		data,
		home,
		away,
		onhover
	}: {
		data: GamePlays;
		home: string;
		away: string;
		onhover?: (elapsed: number | null) => void;
	} = $props();

	const colors = $derived(matchupColors(away, home));
	const colorOf = (t: string) => (t === home ? colors.home : colors.away);

	// ---- Drive chart. Away's end zone on the left, home's on the right: away drives run
	// left to right, home drives right to left.
	const pos = (d: Drive, yl: number) => (d.posteam === away ? yl : 100 - yl);
	function bar(d: Drive) {
		if (d.start_yl == null || d.end_yl == null) return null;
		const a = pos(d, d.start_yl);
		const b = pos(d, Math.max(0, Math.min(100, d.end_yl)));
		return { left: Math.min(a, b), width: Math.max(0.8, Math.abs(b - a)), rightward: b >= a };
	}
	const RESULT: Record<string, string> = {
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
	let selected = $state<number | null>(null);

	// ---- Play feed.
	type Filter = 'all' | 'score' | 'turnover' | 'big' | 'fourth' | 'penalty';
	const FILTERS: { key: Filter; label: string; test: (p: PlayRow, i: number) => boolean }[] = [
		{ key: 'all', label: 'All', test: () => true },
		{ key: 'score', label: 'Scoring', test: (p, i) => scored(p, i) },
		{ key: 'turnover', label: 'Turnovers', test: (p) => /[IF]/.test(p[12]) },
		{ key: 'big', label: 'Explosive', test: (p) => p[12].includes('X') },
		{ key: 'fourth', label: '4th downs', test: (p) => p[12].includes('4') },
		{ key: 'penalty', label: 'Penalties', test: (p) => p[12].includes('P') }
	];
	let filter = $state<Filter>('all');
	let side = $state<'both' | 'away' | 'home'>('both');

	function scored(p: PlayRow, i: number): boolean {
		const prev = data.plays[i - 1];
		if (!prev) return (p[10] ?? 0) + (p[11] ?? 0) > 0;
		return p[10] !== prev[10] || p[11] !== prev[11];
	}
	const counts = $derived(
		Object.fromEntries(
			FILTERS.map((f) => [f.key, data.plays.filter((p, i) => f.test(p, i)).length])
		) as Record<Filter, number>
	);
	const rows = $derived.by(() => {
		const f = FILTERS.find((x) => x.key === filter)!;
		const out: { p: PlayRow; i: number; scoreChange: boolean }[] = [];
		data.plays.forEach((p, i) => {
			if (!f.test(p, i)) return;
			if (selected != null && p[13] !== selected) return;
			if (side !== 'both' && p[2] !== (side === 'home' ? home : away)) return;
			out.push({ p, i, scoreChange: scored(p, i) });
		});
		return out;
	});

	const ORD = ['', '1st', '2nd', '3rd', '4th'];
	function situation(p: PlayRow): string {
		const [, , team, down, togo, yl, type] = p;
		const opp = team === home ? away : home;
		const spot =
			yl == null ? '' : yl === 50 ? 'midfield' : yl < 50 ? `${team} ${yl}` : `${opp} ${100 - yl}`;
		if (down)
			return `${ORD[down]} & ${yl != null && togo != null && 100 - yl <= togo ? 'Goal' : togo} · ${spot}`;
		const label = (type ?? '').replace('_', ' ');
		return spot ? `${label} · ${spot}` : label;
	}
	const TAGS: [string, string][] = [
		['T', 'TD'],
		['I', 'INT'],
		['F', 'Fumble'],
		['S', 'Sack'],
		['X', 'Explosive'],
		['4', '4th down'],
		['P', 'Flag']
	];
	const quarter = (q: number) => (q > 4 ? 'OT' : `Q${q}`);

	function hover(p: PlayRow | null) {
		onhover?.(p ? elapsedAt(p[0], p[1]) : null);
	}
	function pickDrive(n: number) {
		selected = selected === n ? null : n;
		filter = 'all';
	}
</script>

<section class="card">
	<div class="card-head">
		<h2>Drive chart</h2>
		<span class="legend muted"
			><TeamBadge team={away} /> drives → · ← <TeamBadge team={home} /> drives</span
		>
	</div>
	<p class="sub">Every possession, start to finish. Click one to see its plays below.</p>
	<ol class="drives">
		{#each data.drives as d, i (d.n)}
			{@const b = bar(d)}
			<li>
				<button
					class="drive"
					class:sel={selected === d.n}
					class:dim={selected != null && selected !== d.n}
					aria-pressed={selected === d.n}
					onclick={() => pickDrive(d.n)}
				>
					<span class="when">{d.qtr ? quarter(d.qtr) : ''} {d.start_clock ?? ''}</span>
					<TeamBadge team={d.posteam} />
					<span class="field" aria-hidden="true">
						<span class="ez left" style:background={colors.away}></span>
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
						<span class="ez right" style:background={colors.home}></span>
					</span>
					<span class="result" class:score={(d.points ?? 0) > 0}
						>{RESULT[d.result ?? ''] ?? d.result ?? '–'}</span
					>
					<span class="stats">{d.plays} pl · {d.yards ?? '–'} yd · {d.top ?? '–'}</span>
				</button>
			</li>
		{/each}
	</ol>
</section>

<section class="card">
	<div class="card-head">
		<h2>Play by play</h2>
		{#if selected != null}
			<button class="chip clear" onclick={() => (selected = null)}>Drive {selected} ✕</button>
		{/if}
	</div>
	<div class="toolbar">
		<div class="seg" role="group" aria-label="Filter plays">
			{#each FILTERS as f (f.key)}
				<button aria-pressed={filter === f.key} onclick={() => (filter = f.key)}
					>{f.label} <span class="count">{counts[f.key]}</span></button
				>
			{/each}
		</div>
		<div class="seg" role="group" aria-label="Offense">
			<button aria-pressed={side === 'both'} onclick={() => (side = 'both')}>Both</button>
			<button aria-pressed={side === 'away'} onclick={() => (side = 'away')}>{away}</button>
			<button aria-pressed={side === 'home'} onclick={() => (side = 'home')}>{home}</button>
		</div>
	</div>
	<ol class="feed" onmouseleave={() => hover(null)}>
		{#each rows as { p, i, scoreChange } (i)}
			<li class:scoring={scoreChange} onmouseenter={() => hover(p)} onfocusin={() => hover(p)}>
				<div class="clock">
					<b>{quarter(p[0])}</b>
					{p[1] ?? ''}
				</div>
				<div class="body">
					<div class="head">
						<TeamBadge team={p[2]} />
						<span class="sit">{situation(p)}</span>
						{#each TAGS as [k, label] (k)}
							{#if p[12].includes(k)}<span class="tag tag-{k === '4' ? 'four' : k}">{label}</span
								>{/if}
						{/each}
					</div>
					<p class="desc">{p[7]}</p>
				</div>
				<div class="nums">
					{#if p[8] != null}
						<span
							class="chip {p[8] > 0.05 ? 'good' : p[8] < -0.05 ? 'bad' : ''}"
							title="Expected points added for {p[2]}">{fmtEpa(p[8], 2)} EPA</span
						>
					{/if}
					{#if scoreChange}
						<span class="score-now">{away} {p[11]}, {home} {p[10]}</span>
					{:else if p[9] != null}
						<span class="wp muted"
							>{p[9] >= 0.5 ? home : away}
							{Math.round((p[9] >= 0.5 ? p[9] : 1 - p[9]) * 100)}%</span
						>
					{/if}
				</div>
			</li>
		{:else}
			<li class="empty muted">No plays match.</li>
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
		transition: opacity 0.15s;
	}
	.drive:hover,
	.drive.sel {
		background: var(--surface-2);
	}
	.drive.dim {
		opacity: 0.45;
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
	}
	.bar.rightward {
		transform-origin: left;
	}
	/* Pointed at the end the drive finished. */
	.bar {
		clip-path: polygon(6px 0, 100% 0, 100% 100%, 6px 100%, 0 50%);
	}
	.bar.rightward {
		clip-path: polygon(0 0, calc(100% - 6px) 0, 100% 50%, calc(100% - 6px) 100%, 0 100%);
	}
	@keyframes drive-in {
		from {
			transform: scaleX(0);
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
	.toolbar {
		margin-bottom: 0.75rem;
	}
	.count {
		font-size: 0.72rem;
		color: var(--text-muted);
		margin-left: 0.15rem;
	}
	.clear {
		cursor: pointer;
		min-height: 0;
	}
	.feed {
		list-style: none;
		margin: 0;
		padding: 0;
		max-height: 75vh;
		overflow-y: auto;
		border: 1px solid var(--border);
		border-radius: 10px;
	}
	.feed li {
		display: grid;
		grid-template-columns: 4.2rem 1fr auto;
		gap: 0.75rem;
		padding: 0.55rem 0.75rem;
		border-bottom: 1px solid var(--grid);
		font-size: 0.85rem;
	}
	.feed li:hover {
		background: var(--surface-2);
	}
	.feed li.scoring {
		box-shadow: inset 3px 0 0 var(--fav);
	}
	.feed li.empty {
		display: block;
	}
	.clock {
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		line-height: 1.3;
	}
	.clock b {
		display: block;
		color: var(--text-secondary);
	}
	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
	}
	.sit {
		font-weight: 600;
	}
	.tag {
		font-size: 0.66rem;
		font-weight: 800;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		padding: 0.08rem 0.4rem;
		border-radius: 999px;
		background: var(--surface-3);
		color: var(--text-secondary);
	}
	.tag-T {
		background: var(--good-wash);
		color: var(--text-primary);
	}
	.tag-I,
	.tag-F {
		background: var(--bad-wash);
		color: var(--text-primary);
	}
	.desc {
		margin: 0.2rem 0 0;
		color: var(--text-secondary);
		line-height: 1.4;
	}
	.nums {
		display: grid;
		justify-items: end;
		align-content: start;
		gap: 0.25rem;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
	.score-now {
		font-weight: 800;
	}
	.wp {
		font-size: 0.75rem;
	}
	@media (max-width: 720px) {
		.drive {
			grid-template-columns: 2.9rem 1fr 4.6rem;
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
		.feed li {
			grid-template-columns: 1fr;
			gap: 0.3rem;
		}
		.clock {
			display: flex;
			gap: 0.4rem;
		}
		.nums {
			display: flex;
			justify-content: flex-start;
			gap: 0.6rem;
		}
	}
</style>
