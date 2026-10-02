<script lang="ts">
	// Playoff odds from 10,000 simulations of the rest of the season, at every week, with a
	// replay through the season and an honest check of how calibrated past odds were.
	import { base } from '$app/paths';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { loadPath } from '$lib/data';
	import { favorite } from '$lib/favorite.svelte';
	import { num, signed } from '$lib/format';
	import { calibration, oddsPct, skillByWeek } from '$lib/odds';
	import { gridX, gridY, isNarrow, Plot, plotStyle } from '$lib/plot';
	import { prefs } from '$lib/prefs.svelte';
	import { resource } from '$lib/resource.svelte';
	import { teamColor, teamMeta, teamName, teamNick } from '$lib/teams.svelte';
	import type { PlayoffOdds, PlayoffOddsRow } from '$lib/types';
	import { onDestroy } from 'svelte';
	import { flip } from 'svelte/animate';

	const index = resource('playoff_odds/index');
	const metaRes = resource('meta');

	const seasons = $derived((index.value ?? []).map((s) => s.season));
	const season = $derived(
		seasons.includes(prefs.season ?? -1) ? prefs.season! : (seasons.at(-1) ?? 0)
	);
	const status = $derived(metaRes.value?.seasons.find((s) => s.season === season));

	let odds = $state.raw<PlayoffOdds | null>(null);
	let error = $state<string | null>(null);
	let wi = $state(0);
	$effect(() => {
		const want = season;
		if (!want) return;
		loadPath<PlayoffOdds>(`playoff_odds/${want}`)
			.then((d) => {
				if (want !== season) return;
				odds = d;
				wi = d.weeks.length - 1;
			})
			.catch((e) => (error = String(e.message ?? e)));
	});

	const week = $derived(odds?.weeks[wi] ?? 0);
	const weekLabel = (w: number) => (w === 0 ? 'Preseason' : `After week ${w}`);
	const byWeek = $derived.by(() => {
		const m = new Map<number, Map<string, PlayoffOddsRow>>();
		for (const r of odds?.rows ?? []) {
			if (!m.has(r.week)) m.set(r.week, new Map());
			m.get(r.week)!.set(r.team, r);
		}
		return m;
	});
	const isFinal = $derived(!!odds?.actual && wi === (odds?.weeks.length ?? 0) - 1);
	// After the last regular-season week the field is known: show what happened instead of
	// the simulation's random tiebreaks for playoff and division odds.
	const now = $derived(
		[...(byWeek.get(week)?.values() ?? [])].map((r) => {
			const a = isFinal ? odds?.actual?.[r.team] : undefined;
			return a
				? { ...r, p_playoffs: a.made_playoffs ? 1 : 0, p_division: a.won_division ? 1 : 0 }
				: r;
		})
	);
	const prev = $derived(wi > 0 ? byWeek.get(odds!.weeks[wi - 1]) : undefined);

	const conf = (t: string) => teamMeta.byTeam[t]?.conf ?? '';
	const sorted = (c: string) =>
		now
			.filter((r) => conf(r.team) === c)
			.sort((a, b) => b.p_playoffs - a.p_playoffs || b.mean_wins - a.mean_wins);
	const confs = $derived(['AFC', 'NFC'].map((c) => ({ c, rows: sorted(c) })));

	const movers = $derived.by(() => {
		if (!prev) return [];
		return now
			.map((r) => ({ r, d: r.p_playoffs - (prev.get(r.team)?.p_playoffs ?? r.p_playoffs) }))
			.filter((m) => Math.abs(m.d) >= 0.005)
			.sort((a, b) => b.d - a.d);
	});
	const shownMovers = $derived([
		...movers.filter((m) => m.d > 0).slice(0, 4),
		...movers
			.filter((m) => m.d < 0)
			.slice(-4)
			.reverse()
	]);

	// Replay the season week by week.
	let timer: ReturnType<typeof setInterval> | undefined;
	let playing = $state(false);
	function replay() {
		if (playing) return stop();
		if (!odds) return;
		playing = true;
		wi = 0;
		timer = setInterval(() => {
			if (!odds || wi >= odds.weeks.length - 1) return stop();
			wi++;
		}, 650);
	}
	function stop() {
		playing = false;
		clearInterval(timer);
	}
	onDestroy(stop);

	// Odds over time for one division (4 teams = the 4 validated series colors).
	const divisions = $derived(
		[...new Set(Object.values(teamMeta.byTeam).map((t) => t.division))].sort()
	);
	let division = $state<string | null>(null);
	const activeDivision = $derived(
		division ??
			(favorite.team ? teamMeta.byTeam[favorite.team]?.division : undefined) ??
			divisions[0] ??
			''
	);
	const divTeams = $derived(
		Object.values(teamMeta.byTeam)
			.filter((t) => t.division === activeDivision)
			.map((t) => t.team)
			.sort()
	);

	function pathChart(width: number) {
		const rows = (odds?.rows ?? []).filter((r) => divTeams.includes(r.team));
		const last = rows.filter((r) => r.week === odds!.weeks.at(-1));
		const narrow = isNarrow(width);
		return Plot.plot({
			width,
			height: 280,
			style: plotStyle,
			marginLeft: 44,
			marginRight: narrow ? 12 : 48,
			color: {
				domain: divTeams,
				range: ['var(--series-1)', 'var(--series-2)', 'var(--series-3)', 'var(--series-4)'],
				legend: true,
				tickFormat: (t: string) => teamNick(t)
			},
			x: {
				label: null,
				ticks: odds!.weeks.filter((w) => w % (narrow ? 4 : 2) === 0),
				tickFormat: (w: number) => (w === 0 ? 'Pre' : `Wk ${w}`)
			},
			y: { domain: [0, 1], label: '↑ Chance to make the playoffs', tickFormat: '.0%' },
			marks: [
				gridY(),
				Plot.ruleX([week], { stroke: 'var(--axis)', strokeDasharray: '3,3' }),
				Plot.line(rows, {
					x: 'week',
					y: 'p_playoffs',
					stroke: 'team',
					strokeWidth: 2.5,
					curve: 'monotone-x'
				}),
				...(narrow
					? []
					: [
							Plot.text(last, {
								x: 'week',
								y: 'p_playoffs',
								text: 'team',
								dx: 8,
								textAnchor: 'start',
								fill: 'var(--text-primary)',
								fontWeight: 700,
								className: 'declutter'
							})
						]),
				Plot.tip(
					rows,
					Plot.pointer({
						x: 'week',
						y: 'p_playoffs',
						title: (d: PlayoffOddsRow) =>
							`${teamName(d.team)}, ${weekLabel(d.week).toLowerCase()}\nPlayoffs ${oddsPct(d.p_playoffs)} · Division ${oddsPct(d.p_division)}\nProjected ${num(d.mean_wins, 1)} wins`
					})
				)
			]
		});
	}

	function titleChart(width: number) {
		const top = [...now].sort((a, b) => b.p_sb - a.p_sb).slice(0, 10);
		const narrow = width < 420;
		return Plot.plot({
			width,
			height: top.length * 28 + 24,
			style: plotStyle,
			marginLeft: narrow ? 46 : 140,
			marginRight: 48,
			x: { axis: null, domain: [0, Math.max(0.05, top[0]?.p_sb ?? 0)] },
			y: {
				domain: top.map((r) => r.team),
				label: null,
				tickSize: 0,
				tickFormat: (t: string) => (narrow ? t : teamName(t))
			},
			marks: [
				Plot.barX(top, {
					y: 'team',
					x: 'p_sb',
					fill: (d: PlayoffOddsRow) => teamColor(d.team),
					rx: 4,
					insetTop: 4,
					insetBottom: 4
				}),
				Plot.text(top, {
					y: 'team',
					x: 'p_sb',
					text: (d: PlayoffOddsRow) => oddsPct(d.p_sb),
					dx: 6,
					textAnchor: 'start',
					fill: 'var(--text-primary)',
					fontWeight: 700
				})
			]
		});
	}

	// Track record: every completed season, loaded once the page has its own data.
	let history = $state.raw<PlayoffOdds[]>([]);
	$effect(() => {
		const list = index.value;
		if (!list || !odds) return;
		Promise.all(
			list
				.filter((s) => s.season !== season || odds?.actual)
				.map((s) => loadPath<PlayoffOdds>(`playoff_odds/${s.season}`).catch(() => null))
		).then((all) => (history = all.filter((x): x is PlayoffOdds => !!x?.actual)));
	});
	const skill = $derived(skillByWeek(history));
	let calWeek = $state(0);
	const cal = $derived(calibration(history, calWeek));
	const pre = $derived(skill.find((s) => s.week === 0));
	const mid = $derived(skill.find((s) => s.week === 8));

	function calChart(width: number) {
		return Plot.plot({
			width,
			height: Math.min(360, width * 0.8),
			style: plotStyle,
			marginLeft: 44,
			x: { domain: [0, 1], label: 'Forecast chance →', tickFormat: '.0%' },
			y: { domain: [0, 1], label: '↑ Actually made it', tickFormat: '.0%' },
			r: { range: [3, 14] },
			marks: [
				gridX(),
				gridY(),
				Plot.line(
					[
						[0, 0],
						[1, 1]
					],
					{ stroke: 'var(--axis)', strokeDasharray: '4,4' }
				),
				Plot.dot(cal, {
					x: 'predicted',
					y: 'actual',
					r: 'n',
					fill: 'var(--series-1)',
					fillOpacity: 0.75,
					stroke: 'var(--surface)'
				}),
				Plot.tip(
					cal,
					Plot.pointer({
						x: 'predicted',
						y: 'actual',
						title: (d: (typeof cal)[number]) =>
							`Forecast ${Math.round(d.lo * 100)}–${Math.round(d.hi * 100)}% (avg ${Math.round(d.predicted * 100)}%)\nMade it: ${Math.round(d.actual * 100)}% of ${d.n} teams`
					})
				)
			]
		});
	}
	function skillChart(width: number) {
		return Plot.plot({
			width,
			height: 260,
			style: plotStyle,
			marginLeft: 44,
			x: { label: 'Weeks played →', tickFormat: (w: number) => (w === 0 ? 'Pre' : `${w}`) },
			y: { domain: [0, 1], label: '↑ Skill vs base rate', tickFormat: '.0%' },
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.line(skill, { x: 'week', y: 'skill', stroke: 'var(--series-1)', strokeWidth: 2.5 }),
				Plot.dot(skill, { x: 'week', y: 'skill', fill: 'var(--series-1)', r: 3 }),
				Plot.tip(
					skill,
					Plot.pointerX({
						x: 'week',
						y: 'skill',
						title: (d: (typeof skill)[number]) =>
							`${weekLabel(d.week)}: skill ${Math.round(d.skill * 100)}%\nBrier ${d.brier.toFixed(3)} vs ${d.baseline.toFixed(3)} for the base rate (${d.n} team-seasons)`
					})
				)
			]
		});
	}
</script>

<svelte:head><title>Playoff odds {season} · Any Given Stat</title></svelte:head>

<div class="page-head">
	<div class="eyebrow">Teams</div>
	<h1>Playoff odds</h1>
	<p class="lede">
		The rest of the season played out {num(odds?.sims ?? 10000)} times from the power ratings, week by
		week. Scrub or replay to watch the race take shape, then see how well past odds held up.
	</p>
</div>

{#if index.error || error}
	<LoadError message={index.error ?? error ?? ''} />
{:else if !odds || !index.value}
	<Skeleton height={480} />
{:else}
	<div class="toolbar">
		<label class="field">
			Season
			<select value={season} onchange={(e) => (prefs.season = Number(e.currentTarget.value))}>
				{#each [...seasons].reverse() as s (s)}<option value={s}>{s}</option>{/each}
			</select>
		</label>
		<div class="scrub">
			<label for="week-scrub">{weekLabel(week)}</label>
			<input
				id="week-scrub"
				type="range"
				min="0"
				max={odds.weeks.length - 1}
				bind:value={wi}
				oninput={stop}
				aria-valuetext={weekLabel(week)}
			/>
		</div>
		<button class="primary replay" onclick={replay}
			>{playing ? '❚❚ Pause' : '▶ Replay season'}</button
		>
	</div>
	<SampleWarning {status} />
	{#if isFinal}
		<div class="callout info" role="note">
			Regular season over: playoff and division columns show what actually happened (✓). Bye and
			title odds are still simulated, and the simulation breaks ties in the standings at random (the
			NFL's tiebreakers aren't modeled).
		</div>
	{/if}

	<div class="grid-2">
		{#each confs as { c, rows } (c)}
			<section class="card">
				<div class="card-head">
					<h2>{c}</h2>
					<span class="muted small"
						>{odds.seeds} seeds · {odds.byes} bye{odds.byes > 1 ? 's' : ''}</span
					>
				</div>
				<table class="odds">
					<thead>
						<tr>
							<th scope="col">Team</th>
							<th scope="col" class="num">Wins</th>
							<th scope="col">Playoffs</th>
							<th scope="col" class="opt">Division</th>
							<th scope="col" class="opt">Bye</th>
							<th scope="col" class="num">Title</th>
						</tr>
					</thead>
					<tbody>
						{#each rows as r, i (r.team)}
							{@const made = odds.actual?.[r.team]}
							<tr animate:flip={{ duration: 450 }} class:cut={i === odds.seeds - 1}>
								<td>
									<a class="tm" href="{base}/team/?t={r.team}&season={season}">
										<TeamBadge team={r.team} />
										<span class="nick">{teamNick(r.team)}</span>
										{#if made?.sb_winner}<span class="won" title="Won the Super Bowl">🏆</span
											>{:else if made?.made_playoffs}<span class="won" title="Made the playoffs"
												>✓</span
											>{/if}
									</a>
								</td>
								<td class="num" title="80% range: {r.wins_p10}–{r.wins_p90} wins"
									>{num(r.mean_wins, 1)}
									<span class="range">{r.wins_p10}–{r.wins_p90}</span></td
								>
								<td>
									<span class="pbar"
										><span class="track"
											><span
												style:width="{r.p_playoffs * 100}%"
												style:background={teamColor(r.team)}
											></span></span
										><b>{oddsPct(r.p_playoffs)}</b></span
									>
								</td>
								<td class="opt num">{oddsPct(r.p_division)}</td>
								<td class="opt num">{oddsPct(r.p_bye)}</td>
								<td class="num">{oddsPct(r.p_sb)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</section>
		{/each}
	</div>

	<div class="grid-2">
		<section class="card">
			<h2>Title odds</h2>
			<p class="sub">Chance to win the Super Bowl, {weekLabel(week).toLowerCase()}.</p>
			<PlotFigure label="Super Bowl odds, top 10" render={titleChart} />
		</section>
		<section class="card">
			<h2>Biggest moves</h2>
			{#if movers.length}
				<p class="sub">Change in playoff odds from the previous week.</p>
				<ul class="moves">
					{#each shownMovers as m (m.r.team)}
						<li>
							<TeamBadge team={m.r.team} name="nick" link />
							<span class="muted tnum">{oddsPct(m.r.p_playoffs)}</span>
							<span class="chip {m.d >= 0 ? 'good' : 'bad'}"
								>{m.d >= 0 ? '▲' : '▼'} {signed(m.d * 100, 0)} pts</span
							>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="muted">Move the slider past the preseason to see week-over-week changes.</p>
			{/if}
		</section>
	</div>

	<section class="card">
		<div class="card-head">
			<h2>The division race</h2>
		</div>
		<div class="seg divs" role="group" aria-label="Division">
			{#each divisions as d (d)}
				<button aria-pressed={activeDivision === d} onclick={() => (division = d)}>{d}</button>
			{/each}
		</div>
		<PlotFigure label="Playoff odds over the season, {activeDivision}" render={pathChart} />
	</section>

	<section class="card">
		<h2>Should you trust these odds?</h2>
		{#if skill.length}
			<p class="sub">
				Every forecast from {history[0]?.season}–{history.at(-1)?.season}, scored against what
				happened. Skill is the Brier-score improvement over saying every team has the league-wide
				playoff rate; 0% means no better than that.
			</p>
			<p>
				{#if pre}Preseason odds have a skill of <b>{Math.round(pre.skill * 100)}%</b>: barely better
					than knowing nothing about the teams.{/if}
				{#if mid}By week 8 it's <b>{Math.round(mid.skill * 100)}%</b>.{/if}
				The ratings are held fixed for the rest of each simulated season, so the odds are a little overconfident
				at the extremes: dots below the diagonal on the right mean "favorites" made it less often than
				forecast.
			</p>
			<div class="grid-2">
				<div>
					<div class="seg" role="group" aria-label="Forecast week">
						{#each [0, 4, 8, 12] as w (w)}
							<button aria-pressed={calWeek === w} onclick={() => (calWeek = w)}
								>{w === 0 ? 'Preseason' : `Week ${w}`}</button
							>
						{/each}
					</div>
					<PlotFigure label="Calibration of playoff odds" render={calChart} />
				</div>
				<div>
					<PlotFigure label="Forecast skill by week" render={skillChart} />
				</div>
			</div>
		{:else}
			<div class="skeleton" style="height: 260px"></div>
		{/if}
	</section>

	<p class="muted small method">
		How it works: each unplayed game's margin is drawn from a normal distribution centered on the
		<a href="{base}/predictions/">spread model</a>'s rating difference plus home field (σ = the
		model's error), using ratings fit only on games already played. Seeding uses win percentage with
		random tiebreaks; the bracket reseeds. The starting-QB adjustment is left out because future
		starters are unknown.
	</p>
{/if}

<style>
	.scrub {
		display: grid;
		gap: 0.15rem;
		flex: 1;
		min-width: 200px;
		max-width: 420px;
		font-size: 0.82rem;
		font-weight: 600;
	}
	.scrub input {
		width: 100%;
		accent-color: var(--accent);
	}
	.replay {
		white-space: nowrap;
	}
	.small {
		font-size: 0.8rem;
	}
	.odds {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
		font-variant-numeric: tabular-nums;
	}
	.odds th {
		text-align: left;
		font-size: 0.72rem;
		font-weight: 600;
		color: var(--text-secondary);
		padding: 0 0.35rem 0.4rem;
		border-bottom: 1px solid var(--border);
	}
	.odds td {
		padding: 0.3rem 0.35rem;
		border-bottom: 1px solid var(--grid);
	}
	.odds tr.cut td {
		border-bottom: 2px dashed var(--border-strong);
	}
	.num {
		text-align: right;
	}
	th.num {
		text-align: right;
	}
	.tm {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		color: inherit;
		text-decoration: none;
		white-space: nowrap;
	}
	.tm:hover .nick {
		text-decoration: underline;
	}
	.won {
		font-size: 0.8rem;
	}
	.range {
		display: block;
		font-size: 0.7rem;
		color: var(--text-muted);
	}
	.pbar {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		min-width: 110px;
	}
	.track {
		flex: 1;
		height: 10px;
		border-radius: 5px;
		background: var(--surface-2);
		overflow: hidden;
	}
	.track span {
		display: block;
		height: 100%;
		border-radius: 5px;
		transition: width 0.45s var(--ease);
	}
	.pbar b {
		width: 2.6rem;
		text-align: right;
		font-size: 0.8rem;
	}
	.moves {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.moves li {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.4rem 0;
		border-bottom: 1px solid var(--grid);
	}
	.moves li > :first-child {
		flex: 1;
	}
	.divs {
		margin-bottom: 0.75rem;
	}
	.method {
		max-width: 75ch;
	}
	@media (max-width: 560px) {
		.opt {
			display: none;
		}
		.nick {
			display: none;
		}
	}
</style>
