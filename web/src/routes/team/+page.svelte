<script lang="ts">
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import CountUp from '$lib/components/CountUp.svelte';
	import { page } from '$app/state';
	import { favorite } from '$lib/favorite.svelte';
	import Controls from '$lib/components/Controls.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { epa, num, pct, signed } from '$lib/format';
	import { loadSeasonGames } from '$lib/games';
	import { gridY, isNarrow, Plot, plotStyle, signedTick, thinTicks } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { resource, seasonResource } from '$lib/resource.svelte';
	import { ranks, rolling } from '$lib/stats';
	import { teamMeta, teamName } from '$lib/teams.svelte';
	import type { GameDetail, Rating, TeamSeason, TeamSplit, TeamWeek } from '$lib/types';

	const metaRes = resource('meta');
	const teamsRes = resource('teams');
	const weeksRes = seasonResource<TeamWeek>('team_weeks', () => prefs.season);
	const luckRes = resource('luck');
	const ratingsRes = seasonResource<Rating>('ratings', () => prefs.season);
	const splitsRes = seasonResource<TeamSplit>('team_splits', () => prefs.season);

	const meta = $derived(metaRes.value);
	const teams = $derived(teamsRes.value ?? []);
	const weeks = $derived(weeksRes.value ?? []);
	const team = $derived(page.url.searchParams.get('t')?.toUpperCase() ?? 'KC');
	const info = $derived(teamMeta.byTeam[team]);
	const allTeams = $derived([...new Set(teams.map((t) => t.team))].sort());
	const status = $derived(meta?.seasons.find((s) => s.season === prefs.season));
	const season = $derived(
		teams.filter((t) => t.season === prefs.season && t.scope === prefs.scope)
	);
	const me = $derived(season.find((t) => t.team === team));
	const rec = $derived(luckRes.value?.find((l) => l.season === prefs.season && l.team === team));
	const games = $derived(weeks.filter((w) => w.season === prefs.season && w.team === team));
	const history = $derived(
		teams
			.filter((t) => t.team === team && t.scope === prefs.scope)
			.sort((a, b) => a.season - b.season)
	);

	// Season game files give game ids (for links to game pages) and home/away.
	let seasonGames = $state.raw<GameDetail[]>([]);
	$effect(() => {
		const s = prefs.season;
		if (s == null) return;
		loadSeasonGames(s)
			.then((g) => {
				if (prefs.season === s) seasonGames = g;
			})
			.catch(() => (seasonGames = []));
	});
	const gameFor = (week: number) =>
		seasonGames.find(
			(g) => g.season_type === 'REG' && g.week === week && (g.home === team || g.away === team)
		);

	// Power ratings after the last completed week.
	const seasonRatings = $derived((ratingsRes.value ?? []).filter((r) => r.season === prefs.season));
	const lastWeek = $derived(Math.max(0, ...seasonRatings.map((r) => r.week)));
	const latest = $derived(
		new Map(seasonRatings.filter((r) => r.week === lastWeek).map((r) => [r.team, r]))
	);
	const myRating = $derived(latest.get(team));
	const myPath = $derived(seasonRatings.filter((r) => r.team === team));

	// Strength of schedule: average current rating of opponents faced so far (one pass).
	const sos = $derived.by(() => {
		const sums = new Map<string, { s: number; n: number }>();
		for (const w of weeks) {
			if (w.season !== prefs.season) continue;
			const p = latest.get(w.opp)?.points;
			if (p == null) continue;
			const cur = sums.get(w.team) ?? { s: 0, n: 0 };
			cur.s += p;
			cur.n += 1;
			sums.set(w.team, cur);
		}
		const avg = new Map([...sums].map(([t, v]) => [t, v.s / v.n]));
		const mine = avg.get(team);
		const rank = mine == null ? null : 1 + [...avg.values()].filter((v) => v > mine).length;
		return { value: mine, rank, of: avg.size };
	});

	function rankOf(key: keyof TeamSeason, higher: boolean) {
		const vals = season.map((t) => t[key] as number | null);
		return ranks(vals, higher)[season.findIndex((t) => t.team === team)];
	}

	// Profile: league rank on the metrics that define a team, best and worst called out.
	const PROFILE: { key: keyof TeamSeason; label: string; higher: boolean }[] = [
		{ key: 'off_pass_epa', label: 'Passing offense', higher: true },
		{ key: 'off_rush_epa', label: 'Rushing offense', higher: true },
		{ key: 'off_explosive_rate', label: 'Explosive plays', higher: true },
		{ key: 'off_turnover_rate', label: 'Ball security', higher: false },
		{ key: 'off_sack_rate', label: 'Pass protection (sacks)', higher: false },
		{ key: 'off_third_down_rate', label: '3rd down offense', higher: true },
		{ key: 'off_rz_td_rate', label: 'Red zone offense', higher: true },
		{ key: 'def_pass_epa', label: 'Pass defense', higher: false },
		{ key: 'def_rush_epa', label: 'Run defense', higher: false },
		{ key: 'def_sack_rate', label: 'Pass rush (sacks)', higher: true },
		{ key: 'def_turnover_rate', label: 'Takeaways', higher: true },
		{ key: 'def_third_down_rate', label: '3rd down defense', higher: false }
	];
	const profile = $derived(
		me
			? PROFILE.map((p) => ({
					...p,
					rank: rankOf(p.key, p.higher),
					value: me[p.key] as number | null
				})).filter((p) => p.rank != null)
			: []
	);
	// Only top-third ranks count as strengths and bottom-third as weaknesses.
	const third = $derived(Math.round(Math.max(3, season.length) / 3));
	const strengths = $derived(
		[...profile]
			.filter((p) => p.rank! <= third)
			.sort((a, b) => a.rank! - b.rank!)
			.slice(0, 3)
	);
	const weaknesses = $derived(
		[...profile]
			.filter((p) => p.rank! > season.length - third)
			.sort((a, b) => b.rank! - a.rank!)
			.slice(0, 3)
	);

	/** W-L(-T) from regular-season game results. */
	function record(t: string): { w: number; l: number; t: number; text: string } {
		let w = 0;
		let l = 0;
		let ties = 0;
		for (const g of weeks) {
			if (g.season !== prefs.season || g.team !== t) continue;
			if (g.pf > g.pa) w++;
			else if (g.pf < g.pa) l++;
			else ties++;
		}
		return { w, l, t: ties, text: `${w}–${l}${ties ? `–${ties}` : ''}` };
	}
	const fmtProfile = (p: (typeof PROFILE)[number], v: number | null) =>
		/rate/.test(String(p.key)) ? pct(v) : epa(v);
	const style = $derived(
		me
			? (me.off_proe ?? 0) > 0.03
				? 'pass-heavy'
				: (me.off_proe ?? 0) < -0.03
					? 'run-heavy'
					: 'balanced'
			: ''
	);

	// Division standings.
	const division = $derived.by(() => {
		if (!info) return [];
		const mates = Object.values(teamMeta.byTeam).filter((t) => t.division === info.division);
		return mates
			.map((t) => {
				const l = luckRes.value?.find((x) => x.season === prefs.season && x.team === t.team);
				return {
					team: t.team,
					rec: record(t.team),
					diff: l ? l.points_for - l.points_against : 0,
					power: latest.get(t.team)?.points ?? null
				};
			})
			.sort((a, b) => b.rec.w + b.rec.t / 2 - (a.rec.w + a.rec.t / 2) || b.diff - a.diff);
	});

	type Series = { week: number; value: number; side: string };
	function weekly(width: number) {
		const narrow = isNarrow(width);
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
		return Plot.plot({
			width,
			height: 300,
			style: plotStyle,
			marginRight: narrow ? 10 : 110,
			x: {
				label: 'Week',
				tickFormat: 'd',
				ticks: thinTicks(
					games.map((g) => g.week),
					width,
					30
				)
			},
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
				Plot.text(narrow ? [] : line.slice(-2), {
					x: 'week',
					y: 'value',
					text: 'side',
					dx: 8,
					textAnchor: 'start',
					fill: 'var(--text-secondary)',
					className: 'declutter'
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
		const narrow = isNarrow(width);
		const data = history.flatMap((h) => [
			{ season: h.season, value: h.off_epa_play!, side: 'Offense' },
			{ season: h.season, value: h.def_epa_play!, side: 'Defense allowed' }
		]);
		return Plot.plot({
			width,
			height: 300,
			style: plotStyle,
			marginRight: narrow ? 10 : 110,
			x: {
				label: null,
				tickFormat: 'd',
				ticks: thinTicks(
					history.map((h) => h.season),
					width,
					40
				)
			},
			y: { label: 'EPA/play', tickFormat: '+.2f' },
			color: {
				domain: ['Offense', 'Defense allowed'],
				range: ['var(--series-1)', 'var(--series-2)'],
				legend: true
			},
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.ruleX([prefs.season], { stroke: 'var(--accent)', strokeDasharray: '3,3' }),
				Plot.line(data, { x: 'season', y: 'value', stroke: 'side', strokeWidth: 2 }),
				Plot.dot(data, {
					x: 'season',
					y: 'value',
					fill: 'side',
					r: 4,
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.text(narrow ? [] : data.slice(-2), {
					x: 'season',
					y: 'value',
					text: 'side',
					dx: 8,
					textAnchor: 'start',
					fill: 'var(--text-secondary)',
					className: 'declutter'
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
			height: 240,
			style: plotStyle,
			marginRight: 30,
			x: {
				label: 'After week',
				tickFormat: 'd',
				ticks: thinTicks(
					myPath.map((r) => r.week),
					width,
					30
				)
			},
			y: { label: '↑ Net rating (points)', tickFormat: signedTick },
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
		(splitsRes.value ?? []).filter(
			(s) => s.season === prefs.season && s.team === team && s.side === splitSide
		)
	);
	const splitGroups = $derived(
		[...new Set(mySplits.map((s) => s.split))].map((name) => ({
			name,
			rows: mySplits.filter((s) => s.split === name).sort((a, b) => a.ord - b.ord)
		}))
	);
	const nTeams = $derived(Math.max(2, allTeams.length));
	function rankWash(rank: number): string {
		const d = 1 - (2 * (rank - 1)) / Math.max(1, nTeams - 1); // +1 best .. -1 worst
		if (Math.abs(d) < 0.2) return '';
		const alpha = Math.round(Math.min(1, (Math.abs(d) - 0.2) / 0.8) * 100);
		return `background: color-mix(in srgb, var(${d > 0 ? '--good-wash' : '--bad-wash'}) ${alpha}%, transparent)`;
	}

	type Game = TeamWeek & {
		result: string;
		opp_rating: number | null;
		where: string;
		game_id: string | null;
	};
	const log = $derived<Game[]>(
		games.map((g) => {
			const gd = gameFor(g.week);
			return {
				...g,
				result: `${g.pf > g.pa ? 'W' : g.pf < g.pa ? 'L' : 'T'} ${g.pf}–${g.pa}`,
				opp_rating: latest.get(g.opp)?.points ?? null,
				where: gd ? (gd.home === team ? 'vs' : '@') : '',
				game_id: gd?.game_id ?? null
			};
		})
	);
	const columns: Column<Game>[] = [
		{ key: 'week', label: 'Week', sticky: true },
		{ key: 'where', label: 'H/A', title: 'vs = home, @ = away' },
		{ key: 'opp', label: 'Opp', team: true },
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

	function switchTeam(t: string) {
		const url = new URL(page.url);
		url.searchParams.set('t', t);
		goto(url, { keepFocus: true, noScroll: true });
	}
</script>

<svelte:head><title>{teamName(team)} {prefs.season} · Any Given Stat</title></svelte:head>

<section
	class="team-hero"
	style="--team: {info?.color ?? 'var(--hero-to)'}; --team2: {info?.color2 ?? 'var(--hero-from)'}"
>
	<div class="crumbs"><a href="{base}/teams/">Teams</a> / {info?.division ?? team}</div>
	<div class="row">
		<TeamBadge {team} size="lg" />
		<div>
			<h1>{teamName(team)}</h1>
			<div class="facts">
				<span>{prefs.season}</span>
				{#if weeks.length}<span><b>{record(team).text}</b></span>{/if}
				{#if myRating}<span>#{myRating.rank} in power ratings</span>{/if}
				{#if style}<span>{style} offense</span>{/if}
			</div>
		</div>
		<button
			class="fav-btn"
			aria-pressed={favorite.team === team}
			onclick={() => favorite.toggle(team)}
			title="Your team gets a gold ring everywhere on the site and a card on the home page"
		>
			<span aria-hidden="true">{favorite.team === team ? '★' : '☆'}</span>
			{favorite.team === team ? 'My team' : 'Make my team'}
		</button>
	</div>
</section>

{#if meta}
	<div class="toolbar">
		<Controls seasons={meta.seasons} />
		<label class="field">
			Team
			<select
				value={team}
				onchange={(e) => switchTeam((e.currentTarget as HTMLSelectElement).value)}
			>
				{#each allTeams as t (t)}<option value={t}>{teamName(t)}</option>{/each}
			</select>
		</label>
	</div>
	<SampleWarning {status} />
{/if}

{#if teamsRes.error}
	<LoadError message={teamsRes.error} />
{:else if !teamsRes.value}
	<Skeleton height={300} />
{:else if me}
	<div class="tiles">
		<div class="card tile">
			<div class="label">Net EPA/play</div>
			<div class="value"><CountUp text={epa(me.net_epa_play)} /></div>
			<div class="note">#{rankOf('net_epa_play', true)} of {season.length}</div>
		</div>
		<div class="card tile">
			<div class="label">Offense EPA/play</div>
			<div class="value"><CountUp text={epa(me.off_epa_play)} /></div>
			<div class="note">#{rankOf('off_epa_play', true)} of {season.length}</div>
		</div>
		<div class="card tile">
			<div class="label">Defense EPA/play</div>
			<div class="value"><CountUp text={epa(me.def_epa_play)} /></div>
			<div class="note">#{rankOf('def_epa_play', false)} of {season.length} (lower is better)</div>
		</div>
		<div class="card tile">
			<div class="label">Power rating</div>
			<div class="value">
				<CountUp text={myRating ? `${signed(myRating.points)} pts` : '–'} />
			</div>
			<div class="note">{myRating ? `#${myRating.rank} after week ${lastWeek}` : ''}</div>
		</div>
		<div class="card tile">
			<div class="label">Schedule so far</div>
			<div class="value">
				<CountUp text={sos.value == null ? '–' : `${signed(sos.value)} pts`} />
			</div>
			<div class="note">
				{sos.rank ? `Avg opponent rating, #${sos.rank} hardest of ${sos.of}` : ''}
			</div>
		</div>
		<div class="card tile">
			<div class="label">Record vs points</div>
			<div class="value"><CountUp text={weeks.length ? record(team).text : '–'} /></div>
			<div class="note">
				{rec ? `Pythagorean ${num(rec.pythag_wins, 1)} wins (${signed(rec.wins_over_pythag)})` : ''}
			</div>
		</div>
	</div>

	<div class="grid-2">
		<div class="card">
			<h2>Team identity</h2>
			<p class="sub">
				League rank on the traits that define a team ({prefs.scope === 'all'
					? 'all plays'
					: 'garbage time excluded'}).
			</p>
			<div class="ident">
				<div>
					<div class="eyebrow">Strengths</div>
					<ul>
						{#if !strengths.length}<li class="muted">Nothing in the top third</li>{/if}
						{#each strengths as p (p.key)}
							<li>
								<span class="chip good">#{p.rank}</span>
								{p.label} <span class="muted tnum">{fmtProfile(p, p.value)}</span>
							</li>
						{/each}
					</ul>
				</div>
				<div>
					<div class="eyebrow" style="color: var(--bad-ink)">Weaknesses</div>
					<ul>
						{#if !weaknesses.length}<li class="muted">Nothing in the bottom third</li>{/if}
						{#each weaknesses as p (p.key)}
							<li>
								<span class="chip bad">#{p.rank}</span>
								{p.label} <span class="muted tnum">{fmtProfile(p, p.value)}</span>
							</li>
						{/each}
					</ul>
				</div>
			</div>
			<div class="bars">
				{#each profile as p (p.key)}
					{@const score = Math.round(
						((season.length - p.rank!) / Math.max(1, season.length - 1)) * 100
					)}
					<div class="bar-row">
						<span>{p.label}</span>
						<span class="track"
							><span
								class="fill"
								class:high={score >= 65}
								class:low={score < 35}
								style="width: {Math.max(3, score)}%"
							></span></span
						>
						<span class="tnum muted">#{p.rank}</span>
					</div>
				{/each}
			</div>
		</div>
		<div class="card">
			<h2>{info?.division ?? 'Division'}</h2>
			<p class="sub">Standings with point differential and current power rating.</p>
			<table class="div">
				<thead><tr><th>Team</th><th>W–L</th><th>Diff</th><th>Power</th></tr></thead>
				<tbody>
					{#each division as d (d.team)}
						<tr class:me={d.team === team}>
							<td><TeamBadge team={d.team} name="nick" link /></td>
							<td class="tnum">{d.rec.text}</td>
							<td class="tnum">{signed(d.diff, 0)}</td>
							<td class="tnum">{signed(d.power)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
			{#if myPath.length}
				<h3 style="margin-top: 1rem">Power rating through {prefs.season}</h3>
				<PlotFigure label="Power rating by week" render={ratingPath} />
			{/if}
		</div>
	</div>

	<div class="grid-2">
		<div class="card">
			<h2>Week by week</h2>
			<p class="sub">Dots are single games; lines are a trailing 4-game average. All plays.</p>
			{#if games.length}<PlotFigure label="Weekly EPA per play" render={weekly} />{/if}
		</div>
		<div class="card">
			<h2>Season by season</h2>
			<p class="sub">Offense and defense EPA/play; the dashed line marks {prefs.season}.</p>
			{#if history.length}<PlotFigure label="Season EPA per play history" render={seasons} />{/if}
		</div>
	</div>

	<div class="card">
		<div class="card-head">
			<h2>Situational splits</h2>
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

	<div class="card">
		<h2>Game log</h2>
		<p class="sub">Click a game for its win-probability chart.</p>
		<DataTable
			rows={log}
			{columns}
			sortKey="week"
			sortDesc={false}
			showIndex={false}
			maxHeight="none"
			filename="{team}-{prefs.season}-games"
			href={(r) => (r.game_id ? `${base}/game/?id=${r.game_id}` : `${base}/games/`)}
		/>
	</div>
{:else}
	<p class="muted">No data for {teamName(team)} in {prefs.season}.</p>
{/if}

<style>
	.team-hero {
		border-radius: calc(var(--radius) + 4px);
		padding: clamp(1.1rem, 0.9rem + 1.5vw, 1.75rem);
		color: #fff;
		background:
			repeating-linear-gradient(
				90deg,
				transparent 0 calc(10% - 1px),
				rgba(255, 255, 255, 0.07) calc(10% - 1px) 10%
			),
			linear-gradient(
				120deg,
				color-mix(in srgb, var(--team) 85%, #000),
				color-mix(in srgb, var(--team2) 60%, #000)
			);
		box-shadow: var(--shadow-md);
	}
	.team-hero :global(.badge) {
		box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.85);
	}
	.team-hero h1 {
		color: #fff;
		margin: 0;
	}
	.crumbs {
		font-size: 0.82rem;
		opacity: 0.85;
		margin-bottom: 0.6rem;
	}
	.crumbs a {
		color: #fff;
	}
	.row {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 1rem;
	}
	.fav-btn {
		margin-left: auto;
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		border-radius: 999px;
		border: 1px solid rgba(255, 255, 255, 0.45);
		background: rgba(0, 0, 0, 0.22);
		color: #fff;
		font-weight: 600;
		font-size: 0.85rem;
		padding: 0.35rem 0.85rem;
	}
	.fav-btn:hover {
		background: rgba(0, 0, 0, 0.35);
	}
	.fav-btn[aria-pressed='true'] span {
		color: #ffd166;
		animation: star 0.4s var(--ease);
	}
	@keyframes star {
		40% {
			transform: scale(1.5) rotate(20deg);
		}
	}
	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1rem;
		opacity: 0.92;
		font-size: 0.92rem;
		/* Room for the record and rank before they load (two lines on phones). */
		min-height: 1.4em;
	}
	@media (max-width: 560px) {
		.facts {
			min-height: 3em;
		}
	}
	.ident {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.5rem 1.5rem;
		margin-bottom: 1rem;
	}
	.ident ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.35rem;
	}
	.ident li {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-weight: 500;
	}
	.bars {
		display: grid;
		gap: 0.35rem;
	}
	.bar-row {
		display: grid;
		grid-template-columns: minmax(130px, 190px) 1fr 2.6rem;
		gap: 0.6rem;
		align-items: center;
		font-size: 0.85rem;
	}
	.track {
		height: 8px;
		background: var(--surface-2);
		border-radius: 999px;
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		border-radius: 999px;
		background: var(--neutral-mark);
		transform-origin: left;
		animation: grow 0.6s var(--ease) both;
	}
	.fill.high {
		background: var(--good);
	}
	.fill.low {
		background: var(--bad);
	}
	@keyframes grow {
		from {
			transform: scaleX(0);
		}
	}
	.div {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	.div th,
	.div td {
		padding: 0.4rem 0.4rem;
		border-bottom: 1px solid var(--grid);
		text-align: right;
	}
	.div th:first-child,
	.div td:first-child {
		text-align: left;
	}
	.div th {
		font-size: 0.75rem;
		color: var(--text-muted);
		font-weight: 600;
	}
	.div tr.me td {
		background: var(--accent-soft);
	}
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
		font-weight: 700;
		padding-bottom: 0.25rem;
	}
	.splits th {
		color: var(--text-muted);
		font-weight: 500;
		font-size: 0.75rem;
	}
	.splits td,
	.splits th {
		padding: 0.25rem 0.4rem;
		border-bottom: 1px solid var(--grid);
		white-space: nowrap;
	}
	.splits .num {
		text-align: right;
	}
</style>
