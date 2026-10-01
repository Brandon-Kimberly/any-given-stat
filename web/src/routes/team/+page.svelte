<script lang="ts">
	import { base } from '$app/paths';
	import { page } from '$app/state';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import { load } from '$lib/data';
	import { epa, num, pct, signed } from '$lib/format';
	import { gridY, Plot, plotStyle } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { ranks, rolling } from '$lib/stats';
	import type { Luck, Meta, Rating, TeamSeason, TeamSplit, TeamWeek } from '$lib/types';

	let meta = $state<Meta>();
	let teams = $state<TeamSeason[]>([]);
	let weeks = $state<TeamWeek[]>([]);
	let luck = $state<Luck[]>([]);
	load('meta').then((m) => (meta = m));
	load('teams').then((t) => (teams = t));
	load('team_weeks').then((w) => (weeks = w));
	load('luck').then((l) => (luck = l));
	let ratings = $state<Rating[]>([]);
	let splits = $state<TeamSplit[]>([]);
	load('ratings')
		.then((r) => (ratings = r))
		.catch(() => {}); // optional: absent in partial builds
	load('team_splits').then((s) => (splits = s));

	const team = $derived(page.url.searchParams.get('t')?.toUpperCase() ?? 'KC');
	const allTeams = $derived([...new Set(teams.map((t) => t.team))].sort());
	const season = $derived(
		teams.filter((t) => t.season === prefs.season && t.scope === prefs.scope)
	);
	const me = $derived(season.find((t) => t.team === team));
	const rec = $derived(luck.find((l) => l.season === prefs.season && l.team === team));
	const games = $derived(weeks.filter((w) => w.season === prefs.season && w.team === team));
	const history = $derived(
		teams
			.filter((t) => t.team === team && t.scope === prefs.scope)
			.sort((a, b) => a.season - b.season)
	);

	// Latest power ratings for this season (ratings after the last completed week).
	const seasonRatings = $derived(ratings.filter((r) => r.season === prefs.season));
	const lastWeek = $derived(Math.max(0, ...seasonRatings.map((r) => r.week)));
	const latest = $derived(
		new Map(seasonRatings.filter((r) => r.week === lastWeek).map((r) => [r.team, r]))
	);
	const myRating = $derived(latest.get(team));
	const myPath = $derived(seasonRatings.filter((r) => r.team === team));

	// Strength of schedule: average current rating of opponents faced so far.
	const sos = $derived.by(() => {
		const byTeam = new Map<string, number>();
		for (const t of new Set(weeks.filter((w) => w.season === prefs.season).map((w) => w.team))) {
			const opps = weeks.filter((w) => w.season === prefs.season && w.team === t);
			const vals = opps.map((o) => latest.get(o.opp)?.points).filter((v) => v != null);
			if (vals.length) byTeam.set(t, vals.reduce((a, b) => a + b, 0) / vals.length);
		}
		const mine = byTeam.get(team);
		const rank = mine == null ? null : 1 + [...byTeam.values()].filter((v) => v > mine).length;
		return { value: mine, rank, of: byTeam.size };
	});

	function rankOf(key: keyof TeamSeason, higher: boolean) {
		const vals = season.map((t) => t[key] as number | null);
		return ranks(vals, higher)[season.findIndex((t) => t.team === team)];
	}
	const tiles = $derived(
		me
			? [
					{
						label: 'Net EPA/play',
						value: epa(me.net_epa_play),
						rank: rankOf('net_epa_play', true)
					},
					{
						label: 'Offense EPA/play',
						value: epa(me.off_epa_play),
						rank: rankOf('off_epa_play', true)
					},
					{
						label: 'Defense EPA/play',
						value: epa(me.def_epa_play),
						rank: rankOf('def_epa_play', false)
					},
					{
						label: 'Power rating',
						value: myRating ? `${signed(myRating.points)} pts` : '–',
						note: myRating ? `#${myRating.rank} after week ${lastWeek}` : ''
					},
					{
						label: 'Schedule so far',
						value: sos.value == null ? '–' : `${signed(sos.value)} pts`,
						note: sos.rank ? `Avg opponent rating, #${sos.rank} hardest of ${sos.of}` : ''
					},
					{
						label: 'Record',
						value: rec ? `${rec.wins}–${rec.games - rec.wins}` : '–',
						note: rec
							? `Pythagorean ${num(rec.pythag_wins, 1)} wins (${signed(rec.wins_over_pythag)})`
							: ''
					}
				]
			: []
	);

	type Series = { week: number; value: number; side: string };
	function weekly(width: number) {
		const off = rolling(
			games.map((g) => g.off_epa),
			4
		);
		const def = rolling(
			games.map((g) => g.def_epa),
			4
		);
		const line: Series[] = games.flatMap((g, i) => [
			{ week: g.week, value: off[i], side: 'Offense' },
			{ week: g.week, value: def[i], side: 'Defense allowed' }
		]);
		const pts: Series[] = games.flatMap((g) => [
			{ week: g.week, value: g.off_epa, side: 'Offense' },
			{ week: g.week, value: g.def_epa, side: 'Defense allowed' }
		]);
		const last = line.slice(-2);
		return Plot.plot({
			width,
			height: 300,
			style: plotStyle,
			marginRight: 110,
			x: { label: 'Week', tickFormat: 'd', ticks: games.map((g) => g.week) },
			y: { label: 'EPA/play', tickFormat: '+.2f' },
			color: {
				domain: ['Offense', 'Defense allowed'],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.dot(pts, { x: 'week', y: 'value', fill: 'side', r: 3.5, fillOpacity: 0.45 }),
				Plot.line(line, {
					x: 'week',
					y: 'value',
					stroke: 'side',
					strokeWidth: 2,
					curve: 'monotone-x'
				}),
				Plot.text(last, {
					x: 'week',
					y: 'value',
					text: 'side',
					dx: 8,
					textAnchor: 'start',
					fill: 'var(--text-secondary)'
				}),
				Plot.tip(
					pts,
					Plot.pointer({
						lineWidth: 40,
						x: 'week',
						y: 'value',
						title: (d: Series) => `Week ${d.week}\n${d.side}: ${epa(d.value)}`
					})
				)
			]
		});
	}

	function seasons(width: number) {
		const data = history.flatMap((h) => [
			{ season: h.season, value: h.off_epa_play!, side: 'Offense' },
			{ season: h.season, value: h.def_epa_play!, side: 'Defense allowed' }
		]);
		return Plot.plot({
			width,
			height: 260,
			style: plotStyle,
			marginRight: 110,
			x: { label: null, tickFormat: 'd', ticks: history.map((h) => h.season) },
			y: { label: 'EPA/play', tickFormat: '+.2f' },
			color: {
				domain: ['Offense', 'Defense allowed'],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.line(data, { x: 'season', y: 'value', stroke: 'side', strokeWidth: 2 }),
				Plot.dot(data, {
					x: 'season',
					y: 'value',
					fill: 'side',
					r: 4,
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.text(data.slice(-2), {
					x: 'season',
					y: 'value',
					text: 'side',
					dx: 8,
					textAnchor: 'start',
					fill: 'var(--text-secondary)'
				}),
				Plot.tip(
					data,
					Plot.pointer({
						lineWidth: 40,
						x: 'season',
						y: 'value',
						title: (d: { season: number; value: number; side: string }) =>
							`${d.season} ${d.side}: ${epa(d.value)}`
					})
				)
			]
		});
	}

	function ratingPath(width: number) {
		return Plot.plot({
			width,
			height: 260,
			style: plotStyle,
			marginRight: 30,
			x: { label: 'After week', tickFormat: 'd', ticks: myPath.map((r) => r.week) },
			y: { label: '↑ Net rating (points)', tickFormat: '+.0f' },
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.line(myPath, { x: 'week', y: 'points', stroke: 'var(--series-1)', strokeWidth: 2 }),
				Plot.dot(myPath, {
					x: 'week',
					y: 'points',
					fill: 'var(--series-1)',
					r: 4,
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.tip(
					myPath,
					Plot.pointer({
						lineWidth: 40,
						x: 'week',
						y: 'points',
						title: (d: Rating) => `After week ${d.week}: ${signed(d.points)} pts, #${d.rank}`
					})
				)
			]
		});
	}

	let splitSide = $state<'off' | 'def'>('off');
	const mySplits = $derived(
		splits.filter((s) => s.season === prefs.season && s.team === team && s.side === splitSide)
	);
	const splitGroups = $derived(
		[...new Set(mySplits.map((s) => s.split))].map((name) => ({
			name,
			rows: mySplits.filter((s) => s.split === name).sort((a, b) => a.ord - b.ord)
		}))
	);
	const nTeams = $derived(
		new Set(splits.filter((s) => s.season === prefs.season).map((s) => s.team)).size
	);
	function rankWash(rank: number): string {
		const d = 1 - (2 * (rank - 1)) / Math.max(1, nTeams - 1); // +1 best .. -1 worst
		if (Math.abs(d) < 0.2) return '';
		const alpha = Math.round(Math.min(1, (Math.abs(d) - 0.2) / 0.8) * 100);
		return `background: color-mix(in srgb, var(${d > 0 ? '--good-wash' : '--bad-wash'}) ${alpha}%, transparent)`;
	}

	type Game = TeamWeek & { result: string; opp_rating: number | null };
	const log = $derived<Game[]>(
		games.map((g) => ({
			...g,
			result: `${g.pf > g.pa ? 'W' : g.pf < g.pa ? 'L' : 'T'} ${g.pf}–${g.pa}`,
			opp_rating: latest.get(g.opp)?.points ?? null
		}))
	);
	const columns: Column<Game>[] = [
		{ key: 'week', label: 'Week', sticky: true },
		{ key: 'opp', label: 'Opp' },
		{ key: 'result', label: 'Result' },
		{
			key: 'opp_rating',
			label: 'Opp rating',
			fmt: (v) => signed(v),
			title: "Opponent's current power rating in points"
		},
		{ key: 'off_epa', label: 'Off EPA', fmt: epa, better: 'high' },
		{ key: 'def_epa', label: 'Def EPA', fmt: epa, better: 'low' },
		{ key: 'off_plays', label: 'Off plays', fmt: num },
		{ key: 'def_plays', label: 'Def plays', fmt: num }
	];
</script>

<svelte:head><title>{team} · Any Given Stat</title></svelte:head>

<section>
	<p class="muted"><a href="{base}/teams/">Teams</a> / {team}</p>
	<h1>{team} {prefs.season}</h1>
</section>

{#if meta}
	<div class="toolbar">
		<Controls seasons={meta.seasons} />
		<label class="field">
			Team
			<select
				value={team}
				onchange={(e) => (location.search = `?t=${(e.currentTarget as HTMLSelectElement).value}`)}
			>
				{#each allTeams as t (t)}<option value={t}>{t}</option>{/each}
			</select>
		</label>
	</div>
{/if}

{#if me}
	<div class="tiles">
		{#each tiles as t (t.label)}
			<div class="card tile">
				<div class="label">{t.label}</div>
				<div class="value">{t.value}</div>
				<div class="note">{t.rank ? `#${t.rank} of ${season.length}` : (t.note ?? '')}</div>
			</div>
		{/each}
	</div>

	<div class="grid-2">
		<div class="card">
			<h2>Week by week</h2>
			<p class="sub">
				Dots are single games; lines are a trailing 4-game average. All plays, not just neutral
				ones.
			</p>
			{#if games.length}<PlotFigure label="Weekly EPA per play" render={weekly} />{/if}
		</div>
		<div class="card">
			<h2>Season by season</h2>
			<p class="sub">
				Offense and defense EPA/play, {prefs.scope === 'all'
					? 'all plays'
					: 'garbage time excluded'}.
			</p>
			{#if history.length}<PlotFigure label="Season EPA per play history" render={seasons} />{/if}
		</div>
	</div>

	<div class="card">
		<div class="toolbar" style="margin-bottom: 0.25rem">
			<h2 style="margin: 0">Situational splits</h2>
			<div class="seg" role="group" aria-label="Side of the ball">
				<button aria-pressed={splitSide === 'off'} onclick={() => (splitSide = 'off')}
					>Offense</button
				>
				<button aria-pressed={splitSide === 'def'} onclick={() => (splitSide = 'def')}
					>Defense</button
				>
			</div>
		</div>
		<p class="sub">
			EPA/play by situation with league rank (1 = best{splitSide === 'def'
				? ', i.e. allowed the least'
				: ''}). All regulation plays. Score is from the {splitSide === 'off'
				? 'offense'
				: 'defense'}'s point of view. Small buckets are noisy; check the play counts.
		</p>
		<div class="splits">
			{#each splitGroups as g (g.name)}
				<table>
					<caption>{g.name}</caption>
					<thead>
						<tr
							><th></th><th class="num">Plays</th><th class="num">EPA</th><th class="num">SR</th><th
								class="num">Rank</th
							></tr
						>
					</thead>
					<tbody>
						{#each g.rows as r (r.bucket)}
							<tr>
								<td>{r.bucket}</td>
								<td class="num">{num(r.plays)}</td>
								<td class="num">{epa(r.epa)}</td>
								<td class="num">{pct(r.success, 0)}</td>
								<td class="num" style={rankWash(r.rank)}>{r.rank}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/each}
		</div>
	</div>

	{#if myPath.length}
		<div class="card">
			<h2>Power rating through {prefs.season}</h2>
			<p class="sub">
				Opponent-adjusted, recency-weighted rating in points vs an average team on a neutral field.
				Early weeks lean on last season.
			</p>
			<PlotFigure label="Power rating by week" render={ratingPath} />
		</div>
	{/if}

	<div class="card">
		<h2>Game log</h2>
		<DataTable rows={log} {columns} sortKey="week" sortDesc={false} />
	</div>
{:else if teams.length}
	<p class="muted">No data for {team} in {prefs.season}.</p>
{/if}

<style>
	.splits {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr));
		gap: 1rem 1.25rem;
	}
	.splits table {
		border-collapse: collapse;
		width: 100%;
		font-size: 0.85rem;
		font-variant-numeric: tabular-nums;
	}
	.splits caption {
		text-align: left;
		font-weight: 600;
		padding-bottom: 0.25rem;
	}
	.splits th {
		color: var(--text-muted);
		font-weight: 500;
		font-size: 0.75rem;
	}
	.splits td,
	.splits th {
		padding: 0.2rem 0.4rem;
		border-bottom: 1px solid var(--grid);
		white-space: nowrap;
	}
	.splits .num {
		text-align: right;
	}
</style>
