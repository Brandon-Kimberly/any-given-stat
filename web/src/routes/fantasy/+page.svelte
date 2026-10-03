<script lang="ts">
	import { hasPlayerPage } from '$lib/playerPages.svelte';
	import { base } from '$app/paths';
	import Controls from '$lib/components/Controls.svelte';
	import CountUp from '$lib/components/CountUp.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import LeagueConnect from '$lib/components/LeagueConnect.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import {
		IDP,
		OFFENSE,
		pointsAllowed,
		startsIdp,
		type PlayerSeason,
		type PointsAllowed
	} from '$lib/fantasy/analysis';
	import {
		currentLineup,
		fantasyIds,
		fantasySeason,
		scoredSeason,
		scoringLabel
	} from '$lib/fantasy/data.svelte';
	import { fantasy } from '$lib/fantasy/league.svelte';
	import type { FantasyPos } from '$lib/fantasy/statline';
	import { num, pct, signed } from '$lib/format';
	import { gridY, isNarrow, Plot, plotStyle } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { resource } from '$lib/resource.svelte';

	const metaRes = resource('meta');
	const meta = $derived(metaRes.value);
	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));
	const fs = fantasySeason(() => prefs.season);
	const ids = fantasyIds();
	const result = $derived(scoredSeason(fs.value));
	const lineup = $derived(currentLineup());
	const owners = $derived(ids.value ? fantasy.ownership(ids.value) : null);
	const label = $derived(scoringLabel());

	const positions = $derived<FantasyPos[]>(startsIdp(lineup) ? [...OFFENSE, ...IDP] : OFFENSE);
	let position = $state<'All' | FantasyPos>('All');
	let available = $state(false);

	type Row = PlayerSeason & { owner: string; mine: boolean };
	const allRows = $derived<Row[]>(
		(result?.players ?? [])
			.filter((p) => positions.includes(p.pos))
			.map((p) => {
				const o = owners?.get(p.id);
				return {
					...p,
					owner: o ? (o.mine ? 'Your team' : o.teamName) : owners ? 'Available' : '',
					mine: !!o?.mine
				};
			})
	);
	const rows = $derived(
		allRows.filter(
			(r) =>
				(position === 'All' || r.pos === position) &&
				(!available || r.owner === 'Available') &&
				r.games > 0
		)
	);
	const myRows = $derived(allRows.filter((r) => r.mine).sort((a, b) => b.points - a.points));
	const hrefFor = (r: Row) =>
		r.pos === 'DEF'
			? `${base}/team/?t=${r.id}`
			: hasPlayerPage(r.id)
				? `${base}/player/?id=${r.id}&season=${prefs.season}`
				: '';

	const columns = $derived<Column<Row>[]>([
		{ key: 'name', label: 'Player', sticky: true },
		{ key: 'pos', label: 'Pos' },
		{ key: 'team', label: 'Team', team: true },
		{ key: 'games', label: 'G', fmt: num, title: 'Regular-season games with a stat line' },
		{ key: 'points', label: 'Points', fmt: (v) => num(v, 1), better: 'high' },
		{ key: 'ppg', label: 'Per game', fmt: (v) => num(v, 1), better: 'high' },
		{ key: 'posRank', label: 'Pos rank', fmt: num, title: 'Season rank at the position by points' },
		{
			key: 'vorPerGame',
			label: 'Over repl.',
			fmt: (v) => signed(v, 1),
			better: 'high',
			title:
				'Points per game above a replacement-level player at the position (the next players after every team’s starters)'
		},
		{
			key: 'starterRate',
			label: 'Starter weeks',
			fmt: (v) => pct(v, 0),
			better: 'high',
			title: 'Share of games finishing as a weekly starter at the position for this league size'
		},
		{
			key: 'sd',
			label: 'Swing',
			fmt: (v) => num(v, 1),
			title: 'Standard deviation of weekly points: how boom-or-bust'
		},
		...(owners ? [{ key: 'owner', label: 'Manager' } as Column<Row>] : [])
	]);

	// Tiles: the most valuable player at each main position (total points over replacement).
	const TILE_POS = ['QB', 'RB', 'WR', 'TE'] as const;
	const topByPos = $derived(
		TILE_POS.flatMap((pos) => {
			const minGames = Math.min(3, result?.weeksPlayed ?? 3);
			const top = allRows
				.filter((r) => r.pos === pos && r.games >= minGames)
				.sort((a, b) => b.vor - a.vor)[0];
			return top ? [{ pos, row: top, rep: result?.replacement[pos] ?? null }] : [];
		})
	);

	// Positional value curves: points per game by positional rank, QB/RB/WR/TE.
	const CURVE: FantasyPos[] = ['QB', 'RB', 'WR', 'TE'];
	const CURVE_H = 400;
	// Side by side, the matchups table scrolls within the chart card's height so the pair ends
	// level (the tools row above the table is about TOOLS_H px).
	const TOOLS_H = 57;
	let pairW = $state(0);
	let valueH = $state(0);
	let headH = $state(0);
	const tableCap = $derived(
		pairW >= 860 && valueH > headH ? `${Math.max(280, valueH - headH - TOOLS_H)}px` : '460px'
	);
	const SERIES = ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)'];
	function curveChart(width: number) {
		const narrow = isNarrow(width);
		const minGames = Math.max(2, Math.round((result?.weeksPlayed ?? 0) / 2));
		const depth = narrow ? 36 : 48;
		const pts = CURVE.flatMap((pos) =>
			allRows
				.filter((r) => r.pos === pos && r.games >= minGames)
				.sort((a, b) => b.ppg - a.ppg)
				.slice(0, depth)
				.map((r, i) => ({ pos, rank: i + 1, ppg: r.ppg, name: r.name }))
		);
		const cuts = CURVE.flatMap((pos) => {
			const n = result?.starters[pos] ?? 0;
			const p = pts.find((d) => d.pos === pos && d.rank === n);
			return p ? [{ ...p, label: `${pos}${n}` }] : [];
		});
		const ends = CURVE.flatMap((pos) => {
			const last = pts.filter((d) => d.pos === pos).at(-1);
			return last ? [last] : [];
		});
		return Plot.plot({
			width,
			height: narrow ? 300 : CURVE_H,
			style: plotStyle,
			marginRight: narrow ? 12 : 40,
			x: { label: 'Rank at position →', domain: [1, depth], ticks: narrow ? 5 : 8 },
			y: { label: '↑ Points per game', grid: false, nice: true },
			color: { domain: CURVE, range: SERIES, legend: true },
			marks: [
				gridY(),
				Plot.line(pts, { x: 'rank', y: 'ppg', stroke: 'pos', strokeWidth: 2, curve: 'linear' }),
				Plot.dot(cuts, {
					x: 'rank',
					y: 'ppg',
					r: 4.5,
					fill: 'pos',
					stroke: 'var(--surface)',
					strokeWidth: 1.5
				}),
				Plot.text(cuts, {
					x: 'rank',
					y: 'ppg',
					text: 'label',
					dy: -11,
					fill: 'var(--text-secondary)',
					fontSize: 11,
					fontWeight: 600,
					className: 'declutter'
				}),
				...(narrow
					? []
					: [
							Plot.text(ends, {
								x: 'rank',
								y: 'ppg',
								text: 'pos',
								dx: 8,
								textAnchor: 'start',
								fill: 'var(--text-secondary)',
								fontWeight: 600,
								className: 'declutter'
							})
						]),
				Plot.tip(
					pts,
					Plot.pointer({
						x: 'rank',
						y: 'ppg',
						title: (d: (typeof pts)[number]) => `${d.name}\n${d.pos}${d.rank} · ${d.ppg} per game`
					})
				)
			]
		});
	}

	// Matchups: fantasy points allowed per game by position.
	const allowed = $derived<PointsAllowed[]>(
		fs.value && result ? pointsAllowed(fs.value, result) : []
	);
	type AllowedRow = {
		team: string;
		games: number;
		QB: number;
		RB: number;
		WR: number;
		TE: number;
		K: number;
	};
	const allowedRows = $derived<AllowedRow[]>(
		allowed.map((a) => ({
			team: a.team,
			games: a.games,
			QB: a.perGame.QB ?? 0,
			RB: a.perGame.RB ?? 0,
			WR: a.perGame.WR ?? 0,
			TE: a.perGame.TE ?? 0,
			K: a.perGame.K ?? 0
		}))
	);
	const allowedCols: Column<AllowedRow>[] = [
		{ key: 'team', label: 'Defense', team: true, sticky: true },
		{ key: 'games', label: 'G', fmt: num },
		...(['QB', 'RB', 'WR', 'TE', 'K'] as const).map((p): Column<AllowedRow> => ({
			key: p,
			label: `vs ${p}`,
			fmt: (v) => num(v, 1),
			better: 'high',
			title: `Fantasy points per game this defense allowed to opposing ${p}s (higher = better matchup)`
		}))
	];
</script>

<svelte:head><title>Fantasy {prefs.season} · Any Given Stat</title></svelte:head>

<section class="page-head">
	<div class="eyebrow">Fantasy</div>
	<h1>Fantasy football, scored your way</h1>
	<p class="lede">
		Every player's fantasy points, built play by play from the same stat lines as the box scores,
		under your league's exact scoring. Value over replacement and "starter weeks" use your league's
		size and lineup, so a superflex or TE-premium league ranks players the way it should.
	</p>
</section>

<LeagueConnect />

{#if meta}
	<div class="toolbar">
		<Controls seasons={meta.seasons} showScope={false} />
		<div class="seg" role="group" aria-label="Position">
			{#each ['All', ...positions] as p (p)}
				<button
					type="button"
					aria-pressed={position === p}
					onclick={() => (position = p as typeof position)}>{p}</button
				>
			{/each}
		</div>
		{#if owners}
			<label class="check">
				<input type="checkbox" bind:checked={available} /> Available players only
			</label>
		{/if}
	</div>
	<SampleWarning {status} />
{/if}

{#if fs.error}
	<LoadError message={fs.error} />
{:else if !result}
	<Skeleton height={420} />
{:else}
	<div class="tiles">
		{#each topByPos as t (t.pos)}
			<div class="card tile">
				<div class="label">Top {t.pos} over replacement</div>
				<div class="value"><CountUp text={signed(t.row.vor, 0)} /></div>
				<div class="note">
					{t.row.name} · {num(t.row.ppg, 1)} a game{t.rep != null
						? ` vs ${num(t.rep, 1)} on waivers`
						: ''}
				</div>
			</div>
		{/each}
	</div>

	{#if myRows.length}
		<section class="card mine">
			<div class="card-head">
				<h2>Your roster</h2>
				<span class="muted small"
					>{num(
						myRows.reduce((s, r) => s + r.points, 0),
						1
					)} points this season</span
				>
			</div>
			<ul class="roster">
				{#each myRows as r (r.id)}
					<li>
						<span class="pos-chip">{r.pos}</span>
						{#if hrefFor(r)}<a href={hrefFor(r)}>{r.name}</a>{:else}<span>{r.name}</span>{/if}
						<TeamBadge team={r.team} />
						<span class="num">{num(r.ppg, 1)} <span class="muted">/ g</span></span>
						<span class="num muted">{r.pos}{r.posRank}</span>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<section class="card">
		<div class="card-head">
			<h2>Leaderboard</h2>
			<span class="muted small"
				>{label} · {lineup.teams} teams{fantasy.league ? '' : ' (typical lineup)'} · regular season</span
			>
		</div>
		<DataTable
			{rows}
			{columns}
			sortKey="points"
			search="name"
			filename="fantasy-{prefs.season}"
			href={hrefFor}
			highlight={(r) => r.mine}
		/>
	</section>

	<div class="grid-2" bind:clientWidth={pairW}>
		<section class="card">
			<div bind:clientHeight={valueH}>
				<h2>Where the value is</h2>
				<p class="sub">
					Points per game by rank at each position. Dots mark the last weekly starter in a league
					this size: a steep curve before the dot means scarce talent worth drafting early; a flat
					one means you can wait.
				</p>
				<PlotFigure
					label="Fantasy points per game by positional rank"
					render={curveChart}
					minHeight={CURVE_H + 30}
				/>
			</div>
		</section>
		<section class="card">
			<div bind:clientHeight={headH}>
				<h2>Matchups: points allowed</h2>
				<p class="sub">
					Fantasy points per game each defense allowed to each position, under your scoring. The
					stronger the shading, the more it gives up: a better matchup for your players.
				</p>
			</div>
			<DataTable
				rows={allowedRows}
				columns={allowedCols}
				sortKey="RB"
				showIndex={false}
				maxHeight={tableCap}
				filename="fantasy-points-allowed-{prefs.season}"
				href={(r) => `${base}/team/?t=${r.team}`}
			/>
		</section>
	</div>

	<section class="card method">
		<h2>How this is computed</h2>
		<p>
			Each player's stat line for each game is counted from nflverse play-by-play (passing, rushing,
			receiving, kicking, returns, defense), checked against nflverse's official weekly stats. Your
			scoring is applied to those lines in your browser. Team defenses allow the opponent's points
			minus any return touchdowns the opponent's own defense or special teams scored. Replacement
			level is the average points per game of the three players just after the league's starters at
			each position (flex spots go to whoever would fill them). Starter weeks count games where a
			player finished inside that weekly starter count.
		</p>
	</section>
{/if}

<style>
	.check {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 32px;
		font-size: 0.9rem;
		color: var(--text-secondary);
		cursor: pointer;
	}
	.roster {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
		gap: 0.25rem 1.5rem;
	}
	.roster li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.4rem 0;
		border-bottom: 1px solid var(--grid);
		font-size: 0.9rem;
	}
	.roster a,
	.roster span:not(.pos-chip):not(.num) {
		font-weight: 600;
		color: var(--text-primary);
	}
	.roster .num {
		margin-left: auto;
		font-variant-numeric: tabular-nums;
	}
	.roster .num + .num {
		margin-left: 0.5rem;
		min-width: 3.2rem;
		text-align: right;
	}
	.pos-chip {
		min-width: 2.4rem;
		padding: 0.1rem 0.35rem;
		border-radius: 6px;
		background: var(--surface-2);
		font-size: 0.72rem;
		font-weight: 700;
		text-align: center;
		color: var(--text-secondary);
	}
	.mine {
		box-shadow:
			inset 3px 0 0 var(--fav),
			var(--shadow-sm);
	}
	.method p {
		margin: 0;
		max-width: 80ch;
		color: var(--text-secondary);
	}
	.small {
		font-size: 0.82rem;
	}
</style>
