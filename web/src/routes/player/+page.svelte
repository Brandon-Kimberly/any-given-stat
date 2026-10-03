<script lang="ts">
	import { base } from '$app/paths';
	import { page } from '$app/state';
	import Avatar from '$lib/components/Avatar.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import PlayerFantasy from '$lib/components/PlayerFantasy.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import { epa, num, pct, signed } from '$lib/format';
	import { gridY, isNarrow, Plot, plotStyle, signedTick, thinTicks } from '$lib/plot';
	import { resource, seasonResource } from '$lib/resource.svelte';
	import { teamColor, teamName } from '$lib/teams.svelte';
	import type { QB, QBGame, Receiver, Rusher } from '$lib/types';

	const id = $derived(page.url.searchParams.get('id') ?? '');
	const players = resource('players');
	const qbsRes = resource('qbs');
	const recRes = resource('receivers');
	const rushRes = resource('rushers');
	// Game logs load one season at a time (the season picked below).
	const qbGamesRes = seasonResource<QBGame>('qb_games', () => logSeason);

	const info = $derived(players.value?.find((p) => p.player_id === id));
	const qb = $derived(
		(qbsRes.value ?? [])
			.filter((q) => q.player_id === id && q.scope === 'all')
			.sort((a, b) => a.season - b.season)
	);
	const rec = $derived(
		(recRes.value ?? []).filter((r) => r.player_id === id).sort((a, b) => a.season - b.season)
	);
	const rush = $derived(
		(rushRes.value ?? []).filter((r) => r.player_id === id).sort((a, b) => a.season - b.season)
	);
	const loaded = $derived(!!qbsRes.value && !!recRes.value && !!rushRes.value);

	const name = $derived(
		info?.name ??
			qb[0]?.full_name ??
			rec[0]?.full_name ??
			rush[0]?.full_name ??
			qb[0]?.name ??
			rec[0]?.name ??
			rush[0]?.name ??
			'Player'
	);
	const role = $derived<'QB' | 'REC' | 'RUSH' | null>(
		qb.length
			? 'QB'
			: rec.length &&
				  (rush.length === 0 ||
						rec.reduce((a, r) => a + r.targets, 0) >= rush.reduce((a, r) => a + r.carries, 0))
				? 'REC'
				: rush.length
					? 'RUSH'
					: rec.length
						? 'REC'
						: null
	);
	const lastTeam = $derived(qb.at(-1)?.team ?? rec.at(-1)?.team ?? rush.at(-1)?.team ?? '');
	const seasons = $derived([...new Set([...qb, ...rec, ...rush].map((r) => r.season))].sort());

	/** Percentile of `v` among `vals` (0..100), higher = better unless `low`. */
	function pctile(vals: number[], v: number, low = false): number {
		if (!vals.length) return 50;
		const below = vals.filter((x) => (low ? x > v : x < v)).length;
		const equal = vals.filter((x) => x === v).length;
		return Math.round(((below + equal / 2) / vals.length) * 100);
	}

	// Peers qualify with at least 40% of that season's leader's volume, so in-progress seasons work.
	function qualifies<T>(rows: T[], vol: (r: T) => number) {
		const lead = Math.max(0, ...rows.map(vol));
		return (r: T) => vol(r) >= lead * 0.4;
	}
	// A link to a specific season (?season=, e.g. from the record book) opens that profile.
	let pickProfile = $state<number | null>(Number(page.url.searchParams.get('season')) || null);
	const profileSeasons = $derived.by(() => {
		if (role === 'QB') {
			const all = (qbsRes.value ?? []).filter((q) => q.scope === 'all');
			return qb
				.filter((m) =>
					qualifies(
						all.filter((a) => a.season === m.season),
						(r) => r.dropbacks
					)(m)
				)
				.map((m) => m.season);
		}
		if (role === 'REC') {
			const all = recRes.value ?? [];
			return rec
				.filter((m) =>
					qualifies(
						all.filter((a) => a.season === m.season),
						(r) => r.targets
					)(m)
				)
				.map((m) => m.season);
		}
		const all = rushRes.value ?? [];
		return rush
			.filter((m) =>
				qualifies(
					all.filter((a) => a.season === m.season),
					(r) => r.carries
				)(m)
			)
			.map((m) => m.season);
	});
	const profileSeason = $derived(
		(pickProfile != null && profileSeasons.includes(pickProfile) ? pickProfile : null) ??
			profileSeasons.at(-1) ??
			(qb.at(-1) ?? rec.at(-1) ?? rush.at(-1))?.season ??
			0
	);

	// League percentiles for one season, against qualified players at the position.
	const profile = $derived.by(() => {
		if (role === 'QB' && qb.length) {
			const me = qb.find((q) => q.season === profileSeason) ?? qb.at(-1)!;
			const season = (qbsRes.value ?? []).filter(
				(q) => q.season === me.season && q.scope === 'all'
			);
			const peers = season.filter(qualifies(season, (q) => q.dropbacks));
			const v = (k: keyof QB) => peers.map((p) => p[k] as number).filter((x) => x != null);
			return {
				season: me.season,
				n: peers.length,
				who: 'qualified QBs',
				bars: [
					{ label: 'EPA per dropback', p: pctile(v('epa_db'), me.epa_db), text: epa(me.epa_db) },
					{ label: 'CPOE', p: pctile(v('cpoe'), me.cpoe ?? 0), text: signed(me.cpoe) },
					{
						label: 'Success rate',
						p: pctile(v('success_rate'), me.success_rate),
						text: pct(me.success_rate)
					},
					{
						label: 'Avoids sacks',
						p: pctile(v('sack_rate'), me.sack_rate, true),
						text: pct(me.sack_rate) + ' sacked'
					},
					{
						label: 'Avoids interceptions',
						p: pctile(v('int_rate'), me.int_rate, true),
						text: pct(me.int_rate) + ' INT'
					},
					{
						label: 'Throws deep (aDOT, style)',
						p: pctile(v('adot'), me.adot ?? 0),
						text: num(me.adot, 1) + ' yds'
					},
					{
						label: 'Scrambles (style)',
						p: pctile(v('scramble_rate'), me.scramble_rate),
						text: pct(me.scramble_rate)
					}
				]
			};
		}
		if (role === 'REC' && rec.length) {
			const me = rec.find((r) => r.season === profileSeason) ?? rec.at(-1)!;
			const season = (recRes.value ?? []).filter((r) => r.season === me.season);
			const peers = season.filter(qualifies(season, (r) => r.targets));
			const v = (k: keyof Receiver) => peers.map((p) => p[k] as number).filter((x) => x != null);
			return {
				season: me.season,
				n: peers.length,
				who: 'qualified receivers',
				bars: [
					{
						label: 'Target share',
						p: pctile(v('target_share'), me.target_share),
						text: pct(me.target_share)
					},
					{
						label: 'Air yards share',
						p: pctile(v('air_yards_share'), me.air_yards_share ?? 0),
						text: pct(me.air_yards_share)
					},
					{ label: 'WOPR', p: pctile(v('wopr'), me.wopr ?? 0), text: num(me.wopr, 2) },
					{
						label: 'EPA per target',
						p: pctile(v('epa_target'), me.epa_target),
						text: epa(me.epa_target)
					},
					{
						label: 'Catch rate over expected',
						p: pctile(v('catch_rate_oe'), me.catch_rate_oe ?? 0),
						text: signed((me.catch_rate_oe ?? 0) * 100)
					},
					{
						label: 'YAC over expected',
						p: pctile(v('yac_oe'), me.yac_oe ?? 0),
						text: signed(me.yac_oe)
					},
					{
						label: 'Depth (aDOT, style)',
						p: pctile(v('adot'), me.adot ?? 0),
						text: num(me.adot, 1) + ' yds'
					}
				]
			};
		}
		if (role === 'RUSH' && rush.length) {
			const me = rush.find((r) => r.season === profileSeason) ?? rush.at(-1)!;
			const season = (rushRes.value ?? []).filter((r) => r.season === me.season);
			const peers = season.filter(qualifies(season, (r) => r.carries));
			const v = (k: keyof Rusher) => peers.map((p) => p[k] as number).filter((x) => x != null);
			return {
				season: me.season,
				n: peers.length,
				who: 'qualified rushers',
				bars: [
					{ label: 'EPA per carry', p: pctile(v('epa_rush'), me.epa_rush), text: epa(me.epa_rush) },
					{
						label: 'Success rate',
						p: pctile(v('success_rate'), me.success_rate),
						text: pct(me.success_rate)
					},
					{
						label: 'Explosive runs (10+)',
						p: pctile(v('explosive_rate'), me.explosive_rate),
						text: pct(me.explosive_rate)
					},
					{
						label: 'Avoids stuffs',
						p: pctile(v('stuff_rate'), me.stuff_rate, true),
						text: pct(me.stuff_rate) + ' stuffed'
					},
					{ label: 'Volume (carries)', p: pctile(v('carries'), me.carries), text: num(me.carries) }
				]
			};
		}
		return null;
	});

	function careerChart(width: number) {
		const narrow = isNarrow(width);
		if (role === 'QB') {
			return Plot.plot({
				width,
				height: 280,
				style: plotStyle,
				marginRight: narrow ? 10 : 30,
				x: {
					label: null,
					tickFormat: 'd',
					ticks: thinTicks(
						qb.map((q) => q.season),
						width,
						40
					)
				},
				y: { label: '↑ EPA per dropback (95% interval)', tickFormat: '+.2f' },
				marks: [
					gridY(),
					Plot.ruleY([0], { stroke: 'var(--axis)' }),
					Plot.areaY(qb, {
						x: 'season',
						y1: 'epa_db_lo',
						y2: 'epa_db_hi',
						fill: 'var(--series-1)',
						fillOpacity: 0.12
					}),
					Plot.line(qb, { x: 'season', y: 'epa_db', stroke: 'var(--series-1)', strokeWidth: 2 }),
					Plot.dot(qb, {
						x: 'season',
						y: 'epa_db',
						fill: (d: QB) => teamColor(d.team),
						r: 6,
						stroke: 'var(--surface)',
						strokeWidth: 2
					}),
					Plot.tip(
						qb,
						Plot.pointerX({
							lineWidth: 40,
							x: 'season',
							y: 'epa_db',
							title: (d: QB) =>
								`${d.season} ${d.teams}: ${epa(d.epa_db)} per dropback\n95% CI ${epa(d.epa_db_lo)} to ${epa(d.epa_db_hi)}\n${num(d.dropbacks)} dropbacks, CPOE ${signed(d.cpoe)}`
						})
					)
				]
			});
		}
		const rows = role === 'REC' ? rec : rush;
		const y = role === 'REC' ? 'epa_target' : 'epa_rush';
		return Plot.plot({
			width,
			height: 280,
			style: plotStyle,
			x: {
				label: null,
				tickFormat: 'd',
				ticks: thinTicks(
					rows.map((r) => r.season),
					width,
					40
				)
			},
			y: { label: role === 'REC' ? '↑ EPA per target' : '↑ EPA per carry', tickFormat: '+.2f' },
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.line(rows, { x: 'season', y, stroke: 'var(--series-1)', strokeWidth: 2 }),
				Plot.dot(rows, {
					x: 'season',
					y,
					fill: (d: Receiver | Rusher) => teamColor(d.team),
					r: 6,
					stroke: 'var(--surface)',
					strokeWidth: 2
				}),
				Plot.tip(
					rows as (Receiver | Rusher)[],
					Plot.pointerX({
						lineWidth: 40,
						x: 'season',
						y,
						title: (d: Receiver | Rusher) =>
							`${d.season} ${d.team}: ${epa((d as Receiver).epa_target ?? (d as Rusher).epa_rush)}`
					})
				)
			]
		});
	}

	// QB game log for a chosen season.
	let pickSeason = $state<number | null>(null);
	const logSeason = $derived(pickSeason ?? qb.at(-1)?.season ?? 0);
	const log = $derived(
		(qbGamesRes.value ?? [])
			.filter((g) => g.player_id === id && g.season === logSeason)
			.sort((a, b) => a.week - b.week)
	);
	function gameChart(width: number) {
		return Plot.plot({
			width,
			height: 230,
			style: plotStyle,
			x: {
				label: 'Week',
				type: 'band',
				// Weeks played so far (at least 4), not an empty 18-week axis early in a season.
				domain: Array.from({ length: Math.max(4, ...log.map((g) => g.week)) }, (_, i) => i + 1),
				ticks: isNarrow(width) ? [1, 4, 7, 10, 13, 16] : undefined
			},
			y: { label: '↑ EPA per dropback', tickFormat: signedTick },
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.barY(log, {
					x: 'week',
					y: 'epa_db',
					fill: (g: QBGame) => (g.epa_db >= 0 ? 'var(--good)' : 'var(--bad)'),
					rx: 3,
					insetLeft: 2,
					insetRight: 2
				}),
				Plot.tip(
					log,
					Plot.pointerX({
						lineWidth: 40,
						x: 'week',
						y: 'epa_db',
						title: (g: QBGame) =>
							`Week ${g.week} vs ${g.opp}: ${epa(g.epa_db)} per dropback\n${g.dropbacks} dropbacks, ${num(g.pass_yards)} yds, ${g.tds} TD, ${g.ints} INT, ${g.sacks} sacks`
					})
				)
			]
		});
	}
	const logColumns: Column<QBGame>[] = [
		{ key: 'week', label: 'Week', sticky: true },
		{ key: 'opp', label: 'Opp', team: true },
		{ key: 'dropbacks', label: 'Dropbacks', fmt: num },
		{ key: 'epa_db', label: 'EPA/db', fmt: epa, better: 'high' },
		{ key: 'cpoe', label: 'CPOE', fmt: (v) => signed(v), better: 'high' },
		{ key: 'success_rate', label: 'Success', fmt: pct, better: 'high' },
		{ key: 'pass_yards', label: 'Yards', fmt: num },
		{ key: 'tds', label: 'TD', fmt: num },
		{ key: 'ints', label: 'INT', fmt: num },
		{ key: 'sacks', label: 'Sacks', fmt: num }
	];
	const qbColumns: Column<QB>[] = [
		{ key: 'season', label: 'Season', sticky: true },
		{ key: 'teams', label: 'Team' },
		{ key: 'dropbacks', label: 'Dropbacks', fmt: num },
		{ key: 'epa_db', label: 'EPA/db', fmt: epa, better: 'high' },
		{ key: 'cpoe', label: 'CPOE', fmt: (v) => signed(v), better: 'high' },
		{ key: 'success_rate', label: 'Success', fmt: pct, better: 'high' },
		{ key: 'sack_rate', label: 'Sack%', fmt: pct, better: 'low' },
		{ key: 'int_rate', label: 'INT%', fmt: pct, better: 'low' },
		{ key: 'total_epa', label: 'Total EPA', fmt: (v) => signed(v), better: 'high' },
		{ key: 'pass_yards', label: 'Yards', fmt: num },
		{ key: 'pass_tds', label: 'TD', fmt: num },
		{ key: 'ints', label: 'INT', fmt: num }
	];
	const recColumns: Column<Receiver>[] = [
		{ key: 'season', label: 'Season', sticky: true },
		{ key: 'team', label: 'Team', team: true },
		{ key: 'targets', label: 'Tgt', fmt: num },
		{ key: 'receptions', label: 'Rec', fmt: num },
		{ key: 'yards', label: 'Yds', fmt: num },
		{ key: 'tds', label: 'TD', fmt: num },
		{ key: 'target_share', label: 'Tgt share', fmt: pct, better: 'high' },
		{ key: 'wopr', label: 'WOPR', fmt: (v) => num(v, 2), better: 'high' },
		{ key: 'epa_target', label: 'EPA/tgt', fmt: epa, better: 'high' },
		{ key: 'yac_oe', label: 'YAC OE', fmt: (v) => signed(v), better: 'high' }
	];
	const rushColumns: Column<Rusher>[] = [
		{ key: 'season', label: 'Season', sticky: true },
		{ key: 'team', label: 'Team', team: true },
		{ key: 'carries', label: 'Car', fmt: num },
		{ key: 'yards', label: 'Yds', fmt: num },
		{ key: 'tds', label: 'TD', fmt: num },
		{ key: 'epa_rush', label: 'EPA/car', fmt: epa, better: 'high' },
		{ key: 'success_rate', label: 'Success', fmt: pct, better: 'high' },
		{ key: 'explosive_rate', label: '10+ yd%', fmt: pct, better: 'high' },
		{ key: 'stuff_rate', label: 'Stuff%', fmt: pct, better: 'low' }
	];
</script>

<svelte:head><title>{name} · Any Given Stat</title></svelte:head>

{#if !loaded}
	<Skeleton height={300} />
{:else if !role}
	<div class="callout">
		No player with id <code>{id}</code> in the data. Press <kbd>/</kbd> to search, or browse
		<a href="{base}/qbs/">quarterbacks</a>.
	</div>
{:else}
	<section class="card head" style="--team: {teamColor(lastTeam)}">
		<div class="stripe"></div>
		<Avatar {name} src={info?.headshot} team={lastTeam} size={92} />
		<div class="who">
			<div class="eyebrow">
				{info?.position ?? (role === 'QB' ? 'QB' : role === 'REC' ? 'Receiver' : 'Rusher')}
			</div>
			<h1>{name}</h1>
			<div class="facts">
				<TeamBadge team={lastTeam} name link />
				{#if info?.draft_round}<span
						>Drafted {info.draft_year}, round {info.draft_round}, pick {info.draft_pick}</span
					>
				{:else if info?.rookie_season}<span>Rookie season {info.rookie_season}</span>{/if}
				{#if info?.college}<span>{info.college}</span>{/if}
				<span>In the data: {seasons[0]}–{seasons.at(-1)}</span>
			</div>
		</div>
	</section>

	<PlayerFantasy {id} {seasons} />

	{#if profile}
		<div class="card">
			<div class="card-head">
				<h2>{profile.season} profile</h2>
				{#if profileSeasons.length > 1}
					<label class="field">
						Season
						<select
							value={profile.season}
							onchange={(e) => (pickProfile = +(e.currentTarget as HTMLSelectElement).value)}
						>
							{#each [...profileSeasons].reverse() as s (s)}<option value={s}>{s}</option>{/each}
						</select>
					</label>
				{/if}
			</div>
			<p class="sub">
				Percentile among the {profile.n}
				{profile.who} that season (100 = best). Qualified = at least 40% of the leader's volume.
			</p>
			<div class="bars">
				{#each profile.bars as b (b.label)}
					<div class="bar-row">
						<span class="bl">{b.label}</span>
						<span class="track"
							><span
								class="fill"
								class:low={b.p < 35}
								class:high={b.p >= 65}
								style="width: {Math.max(2, b.p)}%"
							></span></span
						>
						<span class="bp tnum">{b.p}</span>
						<span class="bv tnum muted">{b.text}</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<div class="card">
		<h2>Career arc</h2>
		<p class="sub">
			{role === 'QB'
				? 'EPA per dropback by season, with the 95% interval shaded. Dot color = team.'
				: `EPA per ${role === 'REC' ? 'target' : 'carry'} by season. Dot color = team. Remember that per-play receiver and rusher efficiency is noisy year to year.`}
		</p>
		<PlotFigure label="Career efficiency by season" render={careerChart} />
	</div>

	{#if role === 'QB'}
		<div class="card">
			<div class="card-head">
				<h2>Game log</h2>
				<label class="field">
					Season
					<select
						value={logSeason}
						onchange={(e) => (pickSeason = +(e.currentTarget as HTMLSelectElement).value)}
					>
						{#each [...qb].reverse() as q (q.season)}<option value={q.season}>{q.season}</option
							>{/each}
					</select>
				</label>
			</div>
			{#if log.length}
				<PlotFigure label="EPA per dropback by game" render={gameChart} />
				{#key logSeason}
					<DataTable
						rows={log}
						columns={logColumns}
						sortKey="week"
						sortDesc={false}
						showIndex={false}
						filename="{name}-{logSeason}-games"
						maxHeight="none"
					/>
				{/key}
			{:else}
				<p class="muted">No games with 5+ dropbacks in {logSeason}.</p>
			{/if}
		</div>
		<div class="card">
			<h2>By season</h2>
			<DataTable
				rows={qb}
				columns={qbColumns}
				sortKey="season"
				sortDesc={false}
				showIndex={false}
				filename="{name}-seasons"
				maxHeight="none"
			/>
		</div>
	{/if}
	{#if rec.length}
		<div class="card">
			<h2>Receiving by season</h2>
			<DataTable
				rows={rec}
				columns={recColumns}
				sortKey="season"
				sortDesc={false}
				showIndex={false}
				filename="{name}-receiving"
				maxHeight="none"
			/>
		</div>
	{/if}
	{#if rush.length}
		<div class="card">
			<h2>Rushing by season</h2>
			<DataTable
				rows={rush}
				columns={rushColumns}
				sortKey="season"
				sortDesc={false}
				showIndex={false}
				filename="{name}-rushing"
				maxHeight="none"
			/>
		</div>
	{/if}
	<p class="muted small">
		{teamName(lastTeam)} is the most recent team in the data, not necessarily his current team.
	</p>
{/if}

<style>
	/* Player banner: headshot (or initials) in a team-colored ring, the team's glow behind. */
	.head {
		position: relative;
		overflow: hidden;
		isolation: isolate;
		display: flex;
		align-items: center;
		gap: 1.25rem;
		padding: 1.25rem 1.25rem 1.25rem 1.6rem;
	}
	.head::after {
		content: '';
		position: absolute;
		inset: 0;
		z-index: -1;
		background: radial-gradient(
			70% 160% at 0% 50%,
			color-mix(in srgb, var(--team) 24%, transparent),
			transparent 70%
		);
		pointer-events: none;
	}
	.head h1 {
		font-size: clamp(1.8rem, 1.2rem + 2.4vw, 2.8rem);
		font-stretch: 116%;
	}
	@media (max-width: 480px) {
		.head :global(.avatar) {
			--size: 64px !important;
		}
	}
	.stripe {
		position: absolute;
		inset: 0 auto 0 0;
		width: 6px;
		background: var(--team);
	}
	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.2rem;
		align-items: center;
		color: var(--text-secondary);
		font-size: 0.9rem;
	}
	.bars {
		display: grid;
		gap: 0.45rem;
	}
	.bar-row {
		display: grid;
		grid-template-columns: minmax(120px, 190px) 1fr 2.5rem minmax(90px, auto);
		gap: 0.75rem;
		align-items: center;
		font-size: 0.9rem;
	}
	@media (max-width: 560px) {
		.bar-row {
			grid-template-columns: 1fr 2.2rem;
		}
		.track {
			grid-column: 1 / -1;
			grid-row: 2;
		}
		.bv {
			display: none;
		}
	}
	.track {
		height: 10px;
		background: var(--surface-2);
		border-radius: 999px;
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		border-radius: 999px;
		background: var(--neutral-mark);
		animation: grow 0.6s var(--ease) both;
		transform-origin: left;
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
	.bp {
		font-weight: 800;
		text-align: right;
	}
	.small {
		font-size: 0.8rem;
	}
</style>
