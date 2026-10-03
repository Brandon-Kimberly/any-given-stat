<script lang="ts">
	// A player's fantasy season under the current scoring: totals, rank, value over
	// replacement, every week as a bar against replacement level, and the game log.
	import { base } from '$app/paths';
	import { statSummary } from '$lib/components/BoxScore.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import { fantasyIds, fantasySeason, scoredSeason, scoringLabel } from '$lib/fantasy/data.svelte';
	import { fantasy } from '$lib/fantasy/league.svelte';
	import { IDP } from '$lib/fantasy/analysis';
	import { breakdown, scoreLine } from '$lib/fantasy/scoring';
	import type { StatLine } from '$lib/fantasy/statline';
	import { num, pct, signed } from '$lib/format';
	import { gridY, isNarrow, Plot, plotStyle } from '$lib/plot';

	// The season comes from the page (one season control for the whole player page).
	// openLog: show the game log expanded (players with no QB game log above it).
	let { id, season, openLog = false }: { id: string; season: number; openLog?: boolean } = $props();
	const fs = fantasySeason(() => season);
	const ids = fantasyIds();
	const result = $derived(scoredSeason(fs.value));
	const me = $derived(result?.players.find((p) => p.id === id) ?? null);
	const owner = $derived(ids.value ? fantasy.ownership(ids.value).get(id) : undefined);
	const rep = $derived(me ? (result?.replacement[me.pos] ?? null) : null);
	// Defensive players under a scoring without IDP rules (the presets, most leagues): say so
	// instead of charting a season of zeros (a two-way player's offense still scores).
	const idpUnscored = $derived(
		!!me &&
			IDP.includes(me.pos) &&
			me.points === 0 &&
			scoreLine(
				{ tkl_solo: 1, tkl_ast: 1, sack: 1, def_int: 1, def_pd: 1 },
				me.pos,
				fantasy.scoring
			) === 0
	);

	type Game = {
		gid: string;
		week: number;
		post: boolean;
		opp: string;
		home: boolean;
		points: number;
		line: StatLine;
		summary: string;
	};
	const games = $derived.by<Game[]>(() => {
		const f = fs.value;
		if (!f || !result || !me) return [];
		const out: Game[] = [];
		for (const [gid, pid, team, line] of f.lines) {
			if (pid !== id) continue;
			const g = f.games[gid];
			if (!g) continue;
			const home = team === g[2];
			out.push({
				gid,
				week: g[0],
				post: g[1] !== 'REG',
				opp: home ? g[3] : g[2],
				home,
				points: result.byGame.get(gid)?.get(id) ?? 0,
				line,
				summary: statSummary(line)
			});
		}
		return out.sort((a, b) => a.week - b.week);
	});

	function weeklyChart(width: number) {
		const narrow = isNarrow(width);
		const reg = games.filter((g) => !g.post);
		// Weeks so far (at least 4), as in the QB game log: not 18 slots for 3 games.
		const maxWeek = Math.max(4, ...reg.map((g) => g.week));
		// Bars at most ~36px wide.
		const band = (width - 44) / maxWeek;
		const inset = Math.max(band * 0.1, (band - 36) / 2);
		return Plot.plot({
			width,
			height: narrow ? 220 : 260,
			style: plotStyle,
			marginLeft: 36,
			marginRight: 8,
			x: {
				label: null,
				domain: Array.from({ length: maxWeek }, (_, i) => i + 1),
				tickFormat: (w: number) => (narrow && maxWeek > 9 && w % 2 === 0 ? '' : `${w}`),
				padding: 0
			},
			y: { label: '↑ Points', nice: true, grid: false },
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.barY(reg, {
					x: 'week',
					y: 'points',
					fill: (d: Game) =>
						rep != null && d.points >= rep ? 'var(--series-1)' : 'var(--neutral-mark)',
					rx: 3,
					insetLeft: inset,
					insetRight: inset
				}),
				...(rep != null
					? [
							Plot.ruleY([rep], { stroke: 'var(--text-secondary)', strokeDasharray: '4 3' }),
							Plot.text([rep], {
								y: (d: number) => d,
								frameAnchor: 'right',
								textAnchor: 'end',
								dy: -8,
								text: () => 'Replacement',
								fill: 'var(--text-secondary)',
								fontSize: 11
							})
						]
					: []),
				Plot.tip(
					reg,
					Plot.pointerX({
						x: 'week',
						y: 'points',
						title: (d: Game) => {
							const parts = me
								? breakdown(d.line, me.pos, fantasy.scoring)
										.slice(0, 4)
										.map((p) => `${p.label}: ${signed(p.points, 1)}`)
										.join('\n')
								: '';
							return `Week ${d.week} ${d.home ? 'vs' : '@'} ${d.opp}: ${d.points.toFixed(1)} pts\n${parts}`;
						}
					})
				)
			]
		});
	}

	type Row = Game & { where: string };
	const rows = $derived<Row[]>(games.map((g) => ({ ...g, where: g.home ? 'vs' : '@' })));
	const cols: Column<Row>[] = [
		{ key: 'week', label: 'Week', fmt: (v) => String(v), sticky: true },
		{ key: 'where', label: 'H/A', title: 'vs = home, @ = away' },
		{ key: 'opp', label: 'Opp', team: true },
		{ key: 'points', label: 'Points', fmt: (v) => num(v, 1), better: 'high' },
		{ key: 'summary', label: 'Line' }
	];
</script>

<section class="card fantasy" aria-labelledby="fantasy-title">
	<div class="card-head">
		<h2 id="fantasy-title">{season} fantasy <span class="muted">· {scoringLabel()}</span></h2>
		<div class="right">
			{#if owner}
				<span class="owner" class:mine={owner.mine}
					>{owner.mine ? 'On your team' : `Rostered: ${owner.teamName}`}</span
				>
			{:else if fantasy.league && ids.value}
				<span class="owner">Available in your league</span>
			{/if}
		</div>
	</div>
	{#if fs.error}
		<p class="muted">Fantasy data isn't available for {season}.</p>
	{:else if !result}
		<div class="placeholder" aria-hidden="true"></div>
	{:else if !me}
		<p class="muted">No regular-season fantasy points in {season}.</p>
	{:else if idpUnscored}
		<p class="muted">
			{scoringLabel()} scoring doesn't count defensive players (IDP).
			<a href="{base}/fantasy/">Connect a league</a> that starts IDP to see his points.
		</p>
	{:else}
		<div class="stats">
			<div><span class="k">Points</span><b>{num(me.points, 1)}</b></div>
			<div><span class="k">Per game</span><b>{num(me.ppg, 1)}</b></div>
			<div><span class="k">Rank</span><b>{me.pos}{me.posRank}</b></div>
			<div>
				<span class="k" title="Points per game above a replacement-level {me.pos}">Over repl.</span
				><b>{signed(me.vorPerGame, 1)}</b>
			</div>
			<div>
				<span class="k" title="Share of games finishing as a weekly starter at {me.pos}"
					>Starter weeks</span
				><b>{pct(me.starterRate, 0)}</b>
			</div>
			<div><span class="k">Best game</span><b>{num(me.best, 1)}</b></div>
		</div>
		<p class="sub">
			Each regular-season week; colored bars beat a replacement-level {me.pos}{rep != null
				? ` (${rep.toFixed(1)} per game, dashed)`
				: ''}. Hover a week for where the points came from.
			<a href="{base}/fantasy/">Change scoring</a>.
		</p>
		<PlotFigure label="Fantasy points by week" render={weeklyChart} />
		<details open={openLog}>
			<summary>Game log</summary>
			<DataTable
				{rows}
				columns={cols}
				sortKey="week"
				sortDesc={false}
				showIndex={false}
				filename="fantasy-{id}-{season}"
				href={(g) => `${base}/game/?id=${g.gid}`}
			/>
		</details>
	{/if}
</section>

<style>
	.fantasy {
		display: grid;
		gap: 0.75rem;
	}
	.card-head {
		margin-bottom: 0;
	}
	.right {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(7rem, 1fr));
		gap: 0.6rem;
	}
	.stats div {
		display: grid;
		gap: 0.1rem;
		padding: 0.55rem 0.7rem;
		border-radius: 10px;
		background: var(--surface-2);
	}
	.k {
		font-size: 0.75rem;
		color: var(--text-muted);
	}
	.stats b {
		font: 800 1.25rem var(--display);
		font-variant-numeric: tabular-nums;
	}
	.sub {
		margin: 0;
	}
	.owner {
		padding: 0.15rem 0.6rem;
		border-radius: 999px;
		background: var(--surface-2);
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--text-secondary);
	}
	.owner.mine {
		box-shadow: inset 0 0 0 1.5px var(--fav);
		color: var(--text-primary);
	}
	.placeholder {
		height: 340px;
	}
	details summary {
		cursor: pointer;
		font-weight: 600;
		min-height: 32px;
	}
</style>
