<script lang="ts">
	import { base } from '$app/paths';
	import { page } from '$app/state';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import { load } from '$lib/data';
	import { epa, num, signed } from '$lib/format';
	import { gridY, Plot, plotStyle } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { ranks, rolling } from '$lib/stats';
	import type { Luck, Meta, TeamSeason, TeamWeek } from '$lib/types';

	let meta = $state<Meta>();
	let teams = $state<TeamSeason[]>([]);
	let weeks = $state<TeamWeek[]>([]);
	let luck = $state<Luck[]>([]);
	load('meta').then((m) => (meta = m));
	load('teams').then((t) => (teams = t));
	load('team_weeks').then((w) => (weeks = w));
	load('luck').then((l) => (luck = l));

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

	type Game = TeamWeek & { result: string };
	const log = $derived<Game[]>(
		games.map((g) => ({
			...g,
			result: `${g.pf > g.pa ? 'W' : g.pf < g.pa ? 'L' : 'T'} ${g.pf}–${g.pa}`
		}))
	);
	const columns: Column<Game>[] = [
		{ key: 'week', label: 'Week', sticky: true },
		{ key: 'opp', label: 'Opp' },
		{ key: 'result', label: 'Result' },
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
		<h2>Game log</h2>
		<DataTable rows={log} {columns} sortKey="week" sortDesc={false} />
	</div>
{:else if teams.length}
	<p class="muted">No data for {team} in {prefs.season}.</p>
{/if}
