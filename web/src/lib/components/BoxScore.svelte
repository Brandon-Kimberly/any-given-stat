<script module lang="ts">
	import { hasPlayerPage } from '$lib/playerPages.svelte';
	import type { StatLine as Line } from '$lib/fantasy/statline';

	/** "23/31, 287 yd, 2 TD · 4 car, 12 yd" style summary for the fantasy table. */
	export function statSummary(s: Line): string {
		const g = (k: keyof Line) => (s[k] as number | undefined) ?? 0;
		const parts: string[] = [];
		if (g('pass_att'))
			parts.push(
				`${g('pass_cmp')}/${g('pass_att')}, ${g('pass_yd')} yd` +
					(g('pass_td') ? `, ${g('pass_td')} TD` : '') +
					(g('pass_int') ? `, ${g('pass_int')} INT` : '')
			);
		if (g('rush_att'))
			parts.push(
				`${g('rush_att')} car, ${g('rush_yd')} yd` + (g('rush_td') ? `, ${g('rush_td')} TD` : '')
			);
		if (g('rec_tgt'))
			parts.push(
				`${g('rec')}/${g('rec_tgt')} rec, ${g('rec_yd')} yd` +
					(g('rec_td') ? `, ${g('rec_td')} TD` : '')
			);
		if (g('fga') || g('xpa')) parts.push(`FG ${g('fgm')}/${g('fga')}, XP ${g('xpm')}/${g('xpa')}`);
		if (g('fum_lost')) parts.push(`${g('fum_lost')} fum lost`);
		const tkl = g('tkl_solo') + g('tkl_ast');
		if (tkl || g('sack') || g('def_int'))
			parts.push(
				[tkl && `${tkl} tkl`, g('sack') && `${g('sack')} sk`, g('def_int') && `${g('def_int')} INT`]
					.filter(Boolean)
					.join(', ')
			);
		return parts.join(' · ');
	}
</script>

<script lang="ts">
	// Full box score: team stats as mirrored bars, then each team's player tables (passing,
	// rushing, receiving, defense, kicking, punting, returns). Built from the per-game stat
	// lines (pipeline statlines.py), the same lines fantasy scoring reads.
	import { base } from '$app/paths';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import type { FantasyPos, StatLine } from '$lib/fantasy/statline';
	import { num, signed } from '$lib/format';
	import { matchupColors, teamName } from '$lib/teams.svelte';
	import type { GameBox, TeamBox } from '$lib/types';

	let {
		box,
		away,
		home,
		awayScore,
		homeScore,
		fantasy,
		owners,
		season
	}: {
		box: GameBox;
		away: string;
		home: string;
		awayScore: number | null;
		homeScore: number | null;
		/** Optional fantasy scoring: a points column and a "Fantasy" table. */
		fantasy?: { label: string; score: (line: StatLine, pos: FantasyPos) => number } | null;
		/** Fantasy roster owners (gsis id or team code), when a league is connected. */
		owners?: Map<string, { teamName: string; mine: boolean }> | null;
		/** The game's season, so player links open that season. */
		season?: number;
	} = $props();

	let side = $state<'away' | 'home'>('away');
	const team = $derived(side === 'away' ? away : home);
	const colors = $derived(matchupColors(away, home));

	type Row = { id: string; name: string; pos: FantasyPos; s: StatLine; fp: number | null };
	const rows = $derived<Row[]>(
		box.lines
			.filter(([id, t]) => t === team && box.players[id]?.[1] !== 'DEF')
			.map(([id, , s]) => {
				const [name, pos] = box.players[id] ?? [id, 'OL'];
				return { id, name, pos, s, fp: fantasy ? fantasy.score(s, pos) : null };
			})
	);
	const v = (s: StatLine, k: keyof StatLine) => (s[k] as number | undefined) ?? 0;
	const pick = (k: keyof StatLine, by: keyof StatLine = k) =>
		rows.filter((r) => v(r.s, k) > 0).sort((a, b) => v(b.s, by) - v(a.s, by));

	const passers = $derived(pick('pass_att'));
	const rushers = $derived(pick('rush_att', 'rush_yd'));
	const receivers = $derived(
		rows
			.filter((r) => v(r.s, 'rec_tgt') > 0)
			.sort((a, b) => v(b.s, 'rec_yd') - v(a.s, 'rec_yd') || v(b.s, 'rec') - v(a.s, 'rec'))
	);
	const defenders = $derived(
		rows
			.filter((r) =>
				(['tkl_solo', 'tkl_ast', 'sack', 'def_int', 'def_pd', 'def_ff'] as const).some(
					(k) => v(r.s, k) > 0
				)
			)
			.sort(
				(a, b) =>
					v(b.s, 'tkl_solo') + v(b.s, 'tkl_ast') - (v(a.s, 'tkl_solo') + v(a.s, 'tkl_ast')) ||
					v(b.s, 'sack') - v(a.s, 'sack')
			)
	);
	const kickers = $derived(rows.filter((r) => v(r.s, 'fga') + v(r.s, 'xpa') > 0));
	const punters = $derived(pick('punts'));
	const returners = $derived(
		rows
			.filter((r) => v(r.s, 'kr') + v(r.s, 'pr') > 0)
			.sort((a, b) => v(b.s, 'kr_yd') + v(b.s, 'pr_yd') - (v(a.s, 'kr_yd') + v(a.s, 'pr_yd')))
	);
	// Fantasy: every player with points, plus the team defense.
	const scorers = $derived.by<Row[]>(() => {
		if (!fantasy) return [];
		const dst = box.lines
			.filter(([id, t]) => t === team && box.players[id]?.[1] === 'DEF')
			.map(([id, , s]) => ({
				id,
				name: `${teamName(id)} D/ST`,
				pos: 'DEF' as FantasyPos,
				s,
				fp: fantasy.score(s, 'DEF')
			}));
		return [...rows, ...dst].filter((r) => r.fp).sort((a, b) => b.fp! - a.fp!);
	});
	let showAllDef = $state(false);
	let showAllFp = $state(false);
	const shownDefenders = $derived(showAllDef ? defenders : defenders.slice(0, 8));

	const sum = (list: Row[], k: keyof StatLine) => list.reduce((a, r) => a + v(r.s, k), 0);
	const avg = (yds: number, n: number) => (n ? num(yds / n, 1) : '–');
	const long = (x: number) => (x ? num(x) : '–');

	/** NFL passer rating. */
	function rating(s: StatLine): string {
		const att = v(s, 'pass_att');
		if (!att) return '–';
		const clamp = (x: number) => Math.max(0, Math.min(2.375, x));
		const a = clamp((v(s, 'pass_cmp') / att - 0.3) * 5);
		const b = clamp((v(s, 'pass_yd') / att - 3) * 0.25);
		const c = clamp((v(s, 'pass_td') / att) * 20);
		const d = clamp(2.375 - (v(s, 'pass_int') / att) * 25);
		return (((a + b + c + d) / 6) * 100).toFixed(1);
	}
	const sacks = (x: number) => (Number.isInteger(x) ? String(x) : x.toFixed(1));
	const playerHref = (r: Row) =>
		hasPlayerPage(r.id) ? `${base}/player/?id=${r.id}${season ? `&season=${season}` : ''}` : null;

	// Team stats, away vs home: [label, away, home, display(away), display(home), better].
	type TeamStat = {
		label: string;
		a: number;
		h: number;
		fa: string;
		fh: string;
		better: 'high' | 'low' | null;
	};
	const clock = (sec: number) => `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
	const rate = ([c, n]: [number, number]) => (n ? c / n : 0);
	const teamStats = $derived.by<TeamStat[]>(() => {
		const A = box.teams[away];
		const H = box.teams[home];
		if (!A || !H) return [];
		const frac = (x: [number, number]) => `${x[0]}/${x[1]}`;
		const ypp = (t: TeamBox) => (t.plays ? t.yards / t.plays : 0);
		const list: TeamStat[] = [
			{ label: 'Total yards', a: A.yards, h: H.yards, fa: num(A.yards), fh: num(H.yards), better: 'high' },
			{ label: 'Passing yards', a: A.pass_yds, h: H.pass_yds, fa: num(A.pass_yds), fh: num(H.pass_yds), better: 'high' },
			{ label: 'Rushing yards', a: A.rush_yds, h: H.rush_yds, fa: num(A.rush_yds), fh: num(H.rush_yds), better: 'high' },
			{ label: 'Yards per play', a: ypp(A), h: ypp(H), fa: ypp(A).toFixed(1), fh: ypp(H).toFixed(1), better: 'high' },
			{ label: 'First downs', a: A.first_downs, h: H.first_downs, fa: num(A.first_downs), fh: num(H.first_downs), better: 'high' },
			{ label: 'Third downs', a: rate(A.third), h: rate(H.third), fa: frac(A.third), fh: frac(H.third), better: 'high' },
			{ label: 'Fourth downs', a: rate(A.fourth), h: rate(H.fourth), fa: frac(A.fourth), fh: frac(H.fourth), better: 'high' },
			{ label: 'Red zone TDs', a: rate(A.red_zone), h: rate(H.red_zone), fa: frac(A.red_zone), fh: frac(H.red_zone), better: 'high' },
			{ label: 'Turnovers', a: A.turnovers, h: H.turnovers, fa: num(A.turnovers), fh: num(H.turnovers), better: 'low' },
			{ label: 'Sacks allowed', a: A.sacked[0], h: H.sacked[0], fa: `${A.sacked[0]} (${A.sacked[1]} yd)`, fh: `${H.sacked[0]} (${H.sacked[1]} yd)`, better: 'low' },
			{ label: 'Penalties', a: A.penalties[1], h: H.penalties[1], fa: `${A.penalties[0]} for ${A.penalties[1]}`, fh: `${H.penalties[0]} for ${H.penalties[1]}`, better: 'low' },
			{ label: 'Plays', a: A.plays, h: H.plays, fa: num(A.plays), fh: num(H.plays), better: null },
			{ label: 'Possession', a: A.top_sec, h: H.top_sec, fa: clock(A.top_sec), fh: clock(H.top_sec), better: null }
		]; // prettier-ignore
		return list;
	});
	// Each bar is that side's share of the pair, so equal values draw equal half bars.
	const width = (x: number, y: number) => (x + y > 0 ? (x / (x + y)) * 100 : 0);
	const wins = (t: TeamStat, mine: number, theirs: number) =>
		t.better != null && mine !== theirs && (t.better === 'high' ? mine > theirs : mine < theirs);
</script>

<section class="card box-score" aria-labelledby="box-title">
	<div class="card-head">
		<h2 id="box-title">Box score</h2>
	</div>

	{#if teamStats.length}
		<table class="team-stats">
			<caption class="sr-only">Team stats, {teamName(away)} vs {teamName(home)}</caption>
			<thead>
				<tr>
					<th scope="col" class="a"><TeamBadge team={away} /></th>
					<th scope="col" class="lbl"><span class="sr-only">Stat</span></th>
					<th scope="col" class="h"><TeamBadge team={home} /></th>
				</tr>
			</thead>
			<tbody>
				{#each teamStats as t (t.label)}
					<tr>
						<td class="a">
							<div class="cell">
								<span class="bar" aria-hidden="true"
									><i style:width="{width(t.a, t.h)}%" style:background={colors.away}></i></span
								>
								<span class="val" class:win={wins(t, t.a, t.h)}>{t.fa}</span>
							</div>
						</td>
						<th scope="row" class="lbl">{t.label}</th>
						<td class="h">
							<div class="cell">
								<span class="val" class:win={wins(t, t.h, t.a)}>{t.fh}</span>
								<span class="bar" aria-hidden="true"
									><i style:width="{width(t.h, t.a)}%" style:background={colors.home}></i></span
								>
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
		<p class="muted small note">Bold = better side. Passing yards are net of sacks.</p>
	{/if}

	<div class="switch" role="group" aria-label="Team">
		{#each [['away', away, awayScore], ['home', home, homeScore]] as const as [k, t, pts] (k)}
			<button
				type="button"
				class:on={side === k}
				aria-pressed={side === k}
				style:--team={k === 'away' ? colors.away : colors.home}
				onclick={() => (side = k)}
			>
				<TeamBadge team={t} />
				<span class="tn">{teamName(t)}</span>
				{#if pts != null}<span class="pts">{pts}</span>{/if}
			</button>
		{/each}
	</div>

	{#snippet who(r: Row)}
		<th scope="row" class="who">
			{#if owners?.get(r.id)?.mine}<span class="yours" title="On your fantasy team"
					><span class="sr-only">Your player:</span></span
				>{/if}
			{#if playerHref(r)}<a href={playerHref(r)}>{r.name}</a>{:else}{r.name}{/if}
			<span class="pos">{r.pos}</span>
		</th>
	{/snippet}

	<div class="sections">
		{#if passers.length}
			<div class="sec">
				<h3>Passing</h3>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (scrollable: keyboard users need focus) -->
				<div class="scroll" tabindex="0" role="region" aria-label="Passing table">
					<table>
						<thead>
							<tr>
								<th scope="col">Player</th>
								<th scope="col"><abbr title="Completions / attempts">C/Att</abbr></th>
								<th scope="col">Yds</th>
								<th scope="col"><abbr title="Yards per attempt">Avg</abbr></th>
								<th scope="col">TD</th>
								<th scope="col">Int</th>
								<th scope="col"><abbr title="Sacks taken (yards lost)">Sck</abbr></th>
								<th scope="col"><abbr title="NFL passer rating">Rtg</abbr></th>
								<th scope="col"><abbr title="Expected points added on dropbacks">EPA</abbr></th>
							</tr>
						</thead>
						<tbody>
							{#each passers as r (r.id)}
								<tr>
									{@render who(r)}
									<td>{v(r.s, 'pass_cmp')}/{v(r.s, 'pass_att')}</td>
									<td class="strong">{num(v(r.s, 'pass_yd'))}</td>
									<td>{avg(v(r.s, 'pass_yd'), v(r.s, 'pass_att'))}</td>
									<td>{v(r.s, 'pass_td')}</td>
									<td>{v(r.s, 'pass_int')}</td>
									<td>{v(r.s, 'pass_sack')}-{v(r.s, 'pass_sack_yd')}</td>
									<td>{rating(r.s)}</td>
									<td>{signed(v(r.s, 'pass_epa'), 1)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		{#if rushers.length}
			<div class="sec">
				<h3>Rushing</h3>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (scrollable: keyboard users need focus) -->
				<div class="scroll" tabindex="0" role="region" aria-label="Rushing table">
					<table>
						<thead>
							<tr>
								<th scope="col">Player</th>
								<th scope="col"><abbr title="Carries">Car</abbr></th>
								<th scope="col">Yds</th>
								<th scope="col"><abbr title="Yards per carry">Avg</abbr></th>
								<th scope="col">TD</th>
								<th scope="col"><abbr title="Longest run">Lng</abbr></th>
								<th scope="col"><abbr title="Expected points added on carries">EPA</abbr></th>
							</tr>
						</thead>
						<tbody>
							{#each rushers as r (r.id)}
								<tr>
									{@render who(r)}
									<td>{v(r.s, 'rush_att')}</td>
									<td class="strong">{num(v(r.s, 'rush_yd'))}</td>
									<td>{avg(v(r.s, 'rush_yd'), v(r.s, 'rush_att'))}</td>
									<td>{v(r.s, 'rush_td')}</td>
									<td>{long(v(r.s, 'rush_lng'))}</td>
									<td>{signed(v(r.s, 'rush_epa'), 1)}</td>
								</tr>
							{/each}
						</tbody>
						<tfoot>
							<tr>
								<th scope="row">Team</th>
								<td>{sum(rushers, 'rush_att')}</td>
								<td class="strong">{num(sum(rushers, 'rush_yd'))}</td>
								<td>{avg(sum(rushers, 'rush_yd'), sum(rushers, 'rush_att'))}</td>
								<td>{sum(rushers, 'rush_td')}</td>
								<td></td>
								<td>{signed(sum(rushers, 'rush_epa'), 1)}</td>
							</tr>
						</tfoot>
					</table>
				</div>
			</div>
		{/if}

		{#if receivers.length}
			<div class="sec">
				<h3>Receiving</h3>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (scrollable: keyboard users need focus) -->
				<div class="scroll" tabindex="0" role="region" aria-label="Receiving table">
					<table>
						<thead>
							<tr>
								<th scope="col">Player</th>
								<th scope="col"><abbr title="Targets">Tgt</abbr></th>
								<th scope="col">Rec</th>
								<th scope="col">Yds</th>
								<th scope="col"><abbr title="Yards per reception">Avg</abbr></th>
								<th scope="col">TD</th>
								<th scope="col"><abbr title="Longest reception">Lng</abbr></th>
								<th scope="col"><abbr title="Yards after the catch">YAC</abbr></th>
								<th scope="col"><abbr title="Expected points added on targets">EPA</abbr></th>
							</tr>
						</thead>
						<tbody>
							{#each receivers as r (r.id)}
								<tr>
									{@render who(r)}
									<td>{v(r.s, 'rec_tgt')}</td>
									<td>{v(r.s, 'rec')}</td>
									<td class="strong">{num(v(r.s, 'rec_yd'))}</td>
									<td>{avg(v(r.s, 'rec_yd'), v(r.s, 'rec'))}</td>
									<td>{v(r.s, 'rec_td')}</td>
									<td>{long(v(r.s, 'rec_lng'))}</td>
									<td>{num(v(r.s, 'rec_yac'))}</td>
									<td>{signed(v(r.s, 'rec_epa'), 1)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}

		{#if defenders.length}
			<div class="sec">
				<h3>Defense</h3>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (scrollable: keyboard users need focus) -->
				<div class="scroll" tabindex="0" role="region" aria-label="Defense table">
					<table>
						<thead>
							<tr>
								<th scope="col">Player</th>
								<th scope="col"><abbr title="Total tackles (solo + assisted)">Tkl</abbr></th>
								<th scope="col">Solo</th>
								<th scope="col">Sacks</th>
								<th scope="col"><abbr title="Tackles for loss">TFL</abbr></th>
								<th scope="col"><abbr title="Quarterback hits">QB hit</abbr></th>
								<th scope="col"><abbr title="Passes defensed">PD</abbr></th>
								<th scope="col"><abbr title="Interceptions">Int</abbr></th>
								<th scope="col"><abbr title="Forced fumbles">FF</abbr></th>
							</tr>
						</thead>
						<tbody>
							{#each shownDefenders as r (r.id)}
								<tr>
									{@render who(r)}
									<td class="strong">{v(r.s, 'tkl_solo') + v(r.s, 'tkl_ast')}</td>
									<td class:z={!v(r.s, 'tkl_solo')}>{v(r.s, 'tkl_solo')}</td>
									<td class:z={!v(r.s, 'sack')}>{sacks(v(r.s, 'sack'))}</td>
									<td class:z={!v(r.s, 'tkl_loss')}>{v(r.s, 'tkl_loss')}</td>
									<td class:z={!v(r.s, 'qb_hit')}>{v(r.s, 'qb_hit')}</td>
									<td class:z={!v(r.s, 'def_pd')}>{v(r.s, 'def_pd')}</td>
									<td class:z={!v(r.s, 'def_int')}>{v(r.s, 'def_int')}</td>
									<td class:z={!v(r.s, 'def_ff')}>{v(r.s, 'def_ff')}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				{#if defenders.length > 8}
					<button type="button" class="more" onclick={() => (showAllDef = !showAllDef)}
						>{showAllDef ? 'Show fewer' : `Show all ${defenders.length}`}</button
					>
				{/if}
			</div>
		{/if}

		{#if kickers.length || punters.length}
			<div class="sec two">
				{#if kickers.length}
					<div>
						<h3>Kicking</h3>
						<!-- svelte-ignore a11y_no_noninteractive_tabindex (scrollable: keyboard users need focus) -->
						<div class="scroll" tabindex="0" role="region" aria-label="Kicking table">
							<table>
								<thead>
									<tr>
										<th scope="col">Player</th>
										<th scope="col"><abbr title="Field goals made / attempted">FG</abbr></th>
										<th scope="col"><abbr title="Longest field goal">Lng</abbr></th>
										<th scope="col"><abbr title="Extra points made / attempted">XP</abbr></th>
										<th scope="col">Pts</th>
									</tr>
								</thead>
								<tbody>
									{#each kickers as r (r.id)}
										<tr>
											{@render who(r)}
											<td>{v(r.s, 'fgm')}/{v(r.s, 'fga')}</td>
											<td>{long(v(r.s, 'fg_lng'))}</td>
											<td>{v(r.s, 'xpm')}/{v(r.s, 'xpa')}</td>
											<td class="strong">{v(r.s, 'fgm') * 3 + v(r.s, 'xpm')}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</div>
				{/if}
				{#if punters.length}
					<div>
						<h3>Punting</h3>
						<!-- svelte-ignore a11y_no_noninteractive_tabindex (scrollable: keyboard users need focus) -->
						<div class="scroll" tabindex="0" role="region" aria-label="Punting table">
							<table>
								<thead>
									<tr>
										<th scope="col">Player</th>
										<th scope="col"><abbr title="Punts">No</abbr></th>
										<th scope="col"><abbr title="Gross yards per punt">Avg</abbr></th>
										<th scope="col"><abbr title="Downed inside the 20">In 20</abbr></th>
										<th scope="col"><abbr title="Longest punt">Lng</abbr></th>
									</tr>
								</thead>
								<tbody>
									{#each punters as r (r.id)}
										<tr>
											{@render who(r)}
											<td>{v(r.s, 'punts')}</td>
											<td class="strong">{avg(v(r.s, 'punt_yd'), v(r.s, 'punts'))}</td>
											<td>{v(r.s, 'punt_in20')}</td>
											<td>{long(v(r.s, 'punt_lng'))}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</div>
				{/if}
			</div>
		{/if}

		{#if returners.length}
			<div class="sec">
				<h3>Returns</h3>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (scrollable: keyboard users need focus) -->
				<div class="scroll" tabindex="0" role="region" aria-label="Returns table">
					<table>
						<thead>
							<tr>
								<th scope="col">Player</th>
								<th scope="col"><abbr title="Kickoff returns">KR</abbr></th>
								<th scope="col"><abbr title="Kickoff return yards">Yds</abbr></th>
								<th scope="col"><abbr title="Longest kickoff return">Lng</abbr></th>
								<th scope="col"><abbr title="Punt returns">PR</abbr></th>
								<th scope="col"><abbr title="Punt return yards">Yds</abbr></th>
								<th scope="col"><abbr title="Longest punt return">Lng</abbr></th>
								<th scope="col"><abbr title="Return touchdowns">TD</abbr></th>
							</tr>
						</thead>
						<tbody>
							{#each returners as r (r.id)}
								<tr>
									{@render who(r)}
									<td>{v(r.s, 'kr')}</td>
									<td>{num(v(r.s, 'kr_yd'))}</td>
									<td>{long(v(r.s, 'kr_lng'))}</td>
									<td>{v(r.s, 'pr')}</td>
									<td>{num(v(r.s, 'pr_yd'))}</td>
									<td>{long(v(r.s, 'pr_lng'))}</td>
									<td>{v(r.s, 'kr_td') + v(r.s, 'pr_td')}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
		{#if fantasy && scorers.length}
			<div class="sec">
				<h3>Fantasy <span class="muted">· {fantasy.label}</span></h3>
				<!-- svelte-ignore a11y_no_noninteractive_tabindex (scrollable: keyboard users need focus) -->
				<div class="scroll" tabindex="0" role="region" aria-label="Fantasy table">
					<table>
						<thead
							><tr
								><th scope="col">Player</th><th scope="col">Points</th><th scope="col" class="left"
									>Line</th
								></tr
							></thead
						>
						<tbody>
							{#each showAllFp ? scorers : scorers.slice(0, 8) as r (r.id)}
								<tr>
									{@render who(r)}
									<td class="strong">{r.fp!.toFixed(1)}</td>
									<td class="line">
										{statSummary(r.s)}
										{#if owners}
											{@const o = owners.get(r.id)}
											<span class="owner" class:mine={o?.mine}
												>{o ? (o.mine ? 'Your team' : o.teamName) : 'Available'}</span
											>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				{#if scorers.length > 8}
					<button type="button" class="more" onclick={() => (showAllFp = !showAllFp)}
						>{showAllFp ? 'Show fewer' : `Show all ${scorers.length}`}</button
					>
				{/if}
			</div>
		{/if}
	</div>
</section>

<style>
	.box-score {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 1rem;
	}
	.card-head {
		margin-bottom: 0;
	}
	/* Team stats: away bar grows left toward the label, home bar grows right. */
	.team-stats {
		width: 100%;
		max-width: 760px;
		margin-inline: auto;
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
		font-size: 0.9rem;
	}
	.team-stats th,
	.team-stats td {
		padding: 0.3rem 0;
	}
	.team-stats thead th {
		padding-bottom: 0.55rem;
	}
	.team-stats thead .a {
		text-align: right;
	}
	.team-stats thead .h {
		text-align: left;
	}
	.team-stats .lbl {
		width: 9.5rem;
		padding-inline: 0.85rem;
		text-align: center;
		font-weight: 500;
		font-size: 0.82rem;
		color: var(--text-secondary);
		white-space: nowrap;
	}
	.cell {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	td.a .cell {
		justify-content: flex-end;
	}
	.val {
		flex: none;
		min-width: 4.75rem;
		color: var(--text-secondary);
		white-space: nowrap;
	}
	td.a .val {
		text-align: right;
	}
	.val.win {
		color: var(--text-primary);
		font-weight: 800;
	}
	.bar {
		display: flex;
		flex: 1;
		height: 8px;
		border-radius: 999px;
		background: var(--surface-2);
		overflow: hidden;
	}
	td.a .bar {
		justify-content: flex-end;
	}
	.bar i {
		display: block;
		height: 100%;
		border-radius: 999px;
		transition: width 0.4s cubic-bezier(0.2, 0.7, 0.2, 1);
	}
	.note {
		margin: -0.4rem 0 0;
	}
	@media (max-width: 560px) {
		.team-stats .lbl {
			width: auto;
			padding-inline: 0.4rem;
			white-space: normal;
		}
		.bar {
			display: none;
		}
		.val {
			min-width: 0;
		}
	}

	/* Team switch: a segmented control, the active side underlined in its color. */
	.switch {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 0.4rem;
		padding: 0.3rem;
		border-radius: 12px;
		background: var(--surface-2);
	}
	.switch button {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-height: 44px;
		padding: 0.4rem 0.75rem;
		border: 0;
		border-radius: 9px;
		background: transparent;
		color: var(--text-secondary);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
		box-shadow: inset 0 -3px 0 transparent;
		transition:
			background 0.15s,
			box-shadow 0.15s,
			color 0.15s;
	}
	.switch button:hover {
		color: var(--text-primary);
	}
	.switch button.on {
		background: var(--surface);
		color: var(--text-primary);
		box-shadow:
			inset 0 -3px 0 var(--team),
			var(--shadow-sm);
	}
	@media (max-width: 480px) {
		.tn {
			display: none;
		}
	}
	.tn {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.pts {
		margin-left: auto;
		font: 800 1.15rem var(--display);
		font-variant-numeric: tabular-nums;
	}

	.sections {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 1.25rem;
	}
	.sec h3 {
		margin: 0 0 0.4rem;
		font: 700 0.78rem var(--display);
		text-transform: uppercase;
		letter-spacing: 0.07em;
		color: var(--text-muted);
	}
	.sec.two {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 1.25rem;
	}
	@media (max-width: 760px) {
		.sec.two {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.scroll {
		overflow-x: auto;
		border: 1px solid var(--border);
		border-radius: 10px;
	}
	.sections table {
		width: 100%;
		border-collapse: collapse;
		font-variant-numeric: tabular-nums;
		font-size: 0.875rem;
	}
	.sections th,
	.sections td {
		padding: 0.45rem 0.6rem;
		text-align: right;
		white-space: nowrap;
	}
	.sections thead th {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--text-muted);
		background: var(--surface-2);
		border-bottom: 1px solid var(--border);
	}
	.sections thead th:first-child,
	.sections .who,
	.sections tfoot th {
		text-align: left;
	}
	.sections tbody tr + tr td,
	.sections tbody tr + tr th {
		border-top: 1px solid var(--grid);
	}
	.sections tbody tr:hover td,
	.sections tbody tr:hover th {
		background: var(--surface-2);
	}
	/* Names stay put while the numbers scroll on narrow screens. */
	.who,
	.sections thead th:first-child,
	tfoot th {
		position: sticky;
		left: 0;
		z-index: 1;
		background: var(--surface);
	}
	.sections thead th:first-child {
		background: var(--surface-2);
	}
	.who {
		font-weight: 600;
		max-width: 12rem;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.who a {
		color: var(--text-primary);
		text-decoration: none;
	}
	.who a:hover {
		text-decoration: underline;
	}
	.yours {
		display: inline-block;
		width: 8px;
		height: 8px;
		margin-right: 0.35rem;
		border-radius: 50%;
		background: var(--fav);
		vertical-align: 1px;
	}
	.owner {
		margin-left: 0.5rem;
		padding: 0.05rem 0.4rem;
		border-radius: 999px;
		background: var(--surface-2);
		font-size: 0.72rem;
		font-weight: 600;
		color: var(--text-secondary);
	}
	.owner.mine {
		box-shadow: inset 0 0 0 1.5px var(--fav);
		color: var(--text-primary);
	}
	.pos {
		margin-left: 0.3rem;
		font-size: 0.68rem;
		font-weight: 700;
		color: var(--text-muted);
	}
	.strong {
		font-weight: 700;
		color: var(--text-primary);
	}
	td {
		color: var(--text-secondary);
	}
	td.z {
		color: var(--text-muted);
		opacity: 0.6;
	}
	.sections thead th.left {
		text-align: left;
	}
	td.line {
		text-align: left;
		color: var(--text-secondary);
		font-size: 0.82rem;
	}
	tfoot th,
	tfoot td {
		border-top: 1px solid var(--border);
		font-weight: 700;
		background: var(--surface-2);
	}
	abbr {
		text-decoration: none;
		cursor: help;
	}
	.more {
		margin-top: 0.4rem;
		min-height: 32px;
		padding: 0.3rem 0.8rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--surface);
		color: var(--text-secondary);
		font: inherit;
		font-size: 0.82rem;
		cursor: pointer;
	}
	.more:hover {
		color: var(--text-primary);
		border-color: var(--border-strong);
	}
	.small {
		font-size: 0.78rem;
	}
</style>
