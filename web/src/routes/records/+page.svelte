<script lang="ts">
	import LoadError from '$lib/components/LoadError.svelte';
	import FantasyRecords from '$lib/components/FantasyRecords.svelte';
	import PageToc from '$lib/components/PageToc.svelte';
	import RecordList, { type RecordItem } from '$lib/components/RecordList.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import { epa, num, pct, signed } from '$lib/format';
	import { resource } from '$lib/resource.svelte';
	import { teamName } from '$lib/teams.svelte';
	import type { RecordGame, RecordPlayer, RecordTeam } from '$lib/types';

	const res = resource('records');

	// A short, readable line for a play-by-play description: no clock, formation or jersey
	// numbers, outcome first ("J.Daniels 52-yd pass to N.Brown for a TD"). The full text stays
	// in the row's tooltip; anything unrecognized falls back to the cleaned description.
	const NAME = String.raw`[A-Z][\w'.-]*(?: (?:Jr\.|Sr\.|II|III|IV|St\. [A-Z][a-z]+|[A-Z][a-z]+))?`;
	function playSummary(desc: string): string {
		const s = desc
			.replace(/^\(\d*:\d+\)\s*/, '')
			.replace(/^(\([^)]*\)\s*)+/, '')
			.replace(/\b[A-Z]{2,3}-(?=\d{1,2}-[A-Z])/g, '')
			.replace(/\b\d{1,2}-(?=[A-Z])/g, '')
			.replace(/\s*\[[^\]]*\]/g, '')
			.replace(/\s*\(Aborted\)/g, '')
			.replace(new RegExp(`${NAME} reported in as eligible\\.\\s*`, 'g'), '');
		const td = /TOUCHDOWN/.test(s) ? ' for a TD' : '';
		const safety = /SAFETY/.test(s) ? ', safety' : '';
		const re = (p: string) => s.match(new RegExp(p));
		let m: RegExpMatchArray | null;
		if ((m = re(`(${NAME}) (\\d+) yard field goal is (GOOD|No Good|BLOCKED)`))) {
			const res = m[3] === 'GOOD' ? 'good' : m[3] === 'BLOCKED' ? 'blocked' : 'no good';
			return `${m[1]} ${m[2]}-yd field goal ${res}${m[3] !== 'GOOD' && td ? ', returned for a TD' : ''}`;
		}
		if ((m = re(`(${NAME}) pass .*?INTERCEPTED by (${NAME})`))) {
			const six = s.match(/INTERCEPTED.*? for (\d+) yards?, TOUCHDOWN/);
			return `${m[2]} intercepts ${m[1]}${six ? `, ${six[1]}-yd pick-six` : td}`;
		}
		if (
			(m = re(
				`(${NAME}) pass (?:[a-z]+ [a-z]+ )?to (${NAME})(?: to [A-Z]{2,3} -?\\d+)? for (-?\\d+) yards?`
			))
		) {
			const lats = [...s.matchAll(new RegExp(`Lateral to (${NAME})`, 'g'))];
			if (lats.length)
				return `${m[1]} pass to ${m[2]}, lateral${lats.length > 1 ? 's' : ''} to ${lats.at(-1)![1]}${td}`;
			return `${m[1]} ${m[3]}-yd pass to ${m[2]}${td}${safety}`;
		}
		if (
			/FUMBLES/.test(s) &&
			(m = re(`(${NAME})\\s.*?FUMBLES.*?RECOVERED by (?:[A-Z]{2,3}-)?(${NAME})`))
		)
			return `${m[1]} fumbles, recovered by ${m[2]}${td}${safety}`;
		if ((m = re(`(${NAME}) sacked`)))
			return `${m[1]} sacked${/FUMBLES/.test(s) ? ', fumble' : ''}${td}${safety}`;
		if ((m = re(`(${NAME}) (?:scrambles )?(?:left|right|up)\\b.*? for (-?\\d+) yards?`)))
			return `${m[1]} ${m[2]}-yd ${/scrambles/.test(s) ? 'scramble' : 'run'}${td}${safety}`;
		return s
			.replace(/\s*The Replay Official.*$/, '')
			.replace(/\s*PENALTY on.*$/, '')
			.replace(/\b(TOUCHDOWN|INTERCEPTED|FUMBLES|RECOVERED|BLOCKED|SAFETY)\b/g, (w) =>
				w.toLowerCase()
			)
			.trim();
	}
	const r = $derived(res.value);

	const record = (t: RecordTeam) => `${t.wins}–${t.losses}${t.ties ? `–${t.ties}` : ''}`;
	const teamItems = (rows: RecordTeam[], stat: (t: RecordTeam) => string): RecordItem[] =>
		rows.map((t) => ({
			key: `${t.season}-${t.team}`,
			href: `/team/?t=${t.team}&season=${t.season}`,
			team: t.team,
			title: `${t.season} ${teamName(t.team)}`,
			sub: `${record(t)} · off ${epa(t.off_epa, 2)} · def ${epa(t.def_epa, 2)}`,
			stat: stat(t)
		}));
	const playerItems = (
		rows: RecordPlayer[],
		sub: (p: RecordPlayer) => string,
		stat: (p: RecordPlayer) => string
	): RecordItem[] =>
		rows.map((p) => ({
			key: `${p.season}-${p.player_id}`,
			href: `/player/?id=${p.player_id}&season=${p.season}`,
			team: p.team,
			title: `${p.full_name ?? p.name}, ${p.season}`,
			sub: sub(p),
			stat: stat(p)
		}));
	const gameLabel = (g: {
		season: number;
		week: number;
		season_type?: string;
		game_type?: string;
	}) =>
		(g.season_type ?? g.game_type) === 'REG'
			? `${g.season} week ${g.week}`
			: `${g.season} playoffs`;
	const gameItems = (rows: RecordGame[], stat: (g: RecordGame) => string): RecordItem[] =>
		rows.map((g) => ({
			key: g.game_id,
			href: `/game/?id=${g.game_id}`,
			team: g.winner ?? g.home,
			title: `${g.away} ${g.away_score} @ ${g.home} ${g.home_score}`,
			sub: gameLabel(g),
			stat: stat(g)
		}));

	const sections = $derived(
		r
			? [
					{
						id: 'teams',
						label: 'Teams',
						lists: [
							{
								title: 'Best teams',
								blurb: `Net EPA per play (offense minus defense), min ${r.thresholds.min_team_games} games.`,
								items: teamItems(r.team_best, (t) => epa(t.net_epa))
							},
							{
								title: 'Worst teams',
								blurb: 'The other end of the same list.',
								items: teamItems(r.team_worst, (t) => epa(t.net_epa))
							},
							{
								title: 'Best offenses',
								blurb: 'Offensive EPA per play.',
								items: teamItems(r.offense_best, (t) => epa(t.off_epa))
							},
							{
								title: 'Best defenses',
								blurb: 'Defensive EPA per play allowed (lower is better).',
								items: teamItems(r.defense_best, (t) => epa(t.def_epa))
							}
						]
					},
					{
						id: 'players',
						label: 'Players',
						lists: [
							{
								title: 'Best QB seasons',
								blurb: `EPA per dropback, min ${r.thresholds.min_qb_dropbacks} dropbacks.`,
								items: playerItems(
									r.qb_best,
									(p) => `${p.team} · ${num(p.dropbacks)} dropbacks · CPOE ${signed(p.cpoe)}`,
									(p) => epa(p.epa_db)
								)
							},
							{
								title: 'Worst QB seasons',
								blurb: 'Lowest EPA per dropback. Someone had to start these games.',
								items: playerItems(
									r.qb_worst,
									(p) => `${p.team} · ${num(p.dropbacks)} dropbacks · CPOE ${signed(p.cpoe)}`,
									(p) => epa(p.epa_db)
								)
							},
							{
								title: 'Best receiving seasons',
								blurb: 'Total EPA on targets.',
								items: playerItems(
									r.receiver_best,
									(p) =>
										`${p.position ?? ''} ${p.team} · ${num(p.targets)} targets · ${num(p.yards)} yds`,
									(p) => num(p.total_epa, 1)
								)
							},
							{
								title: 'Best rushing seasons',
								blurb: `Total EPA on designed runs, min ${r.thresholds.min_rush_carries} carries.`,
								items: playerItems(
									r.rusher_best,
									(p) =>
										`${p.position ?? ''} ${p.team} · ${num(p.carries)} carries · ${num(p.yards)} yds`,
									(p) => num(p.total_epa, 1)
								)
							}
						]
					},
					{
						id: 'games',
						label: 'Games',
						lists: [
							{
								title: 'Biggest upsets',
								blurb: 'Largest closing spreads overcome by the underdog.',
								items: r.upsets.map((u) => ({
									key: u.game_id,
									href: `/game/?id=${u.game_id}`,
									team: u.underdog,
									title: `${u.underdog} over ${u.favorite}, ${Math.max(u.home_score, u.away_score)}–${Math.min(u.home_score, u.away_score)}`,
									sub: gameLabel(u),
									stat: `+${num(Math.abs(u.spread), 1)}`
								}))
							},
							{
								title: 'Most exciting games',
								blurb: 'Total win-probability swing (median game: about 3.7).',
								items: gameItems(r.excitement, (g) => num(g.excitement, 1))
							},
							{
								title: 'Biggest comebacks',
								blurb: "The winner's lowest win probability during the game.",
								items: gameItems(r.comebacks, (g) =>
									g.winner_min_wp != null && g.winner_min_wp < 0.01
										? '<1%'
										: pct(g.winner_min_wp, 1)
								)
							},
							{
								title: 'Biggest plays',
								blurb: 'Largest single-play win-probability swing.',
								items: r.biggest_plays.map((p) => ({
									key: `${p.game_id}-${p.qtr}-${p.time}`,
									href: `/game/?id=${p.game_id}`,
									team: p.wpa >= 0 ? p.posteam : p.defteam,
									title: playSummary(p.desc),
									tip: p.desc,
									sub: `${p.posteam} vs ${p.defteam} · ${gameLabel(p)} · Q${p.qtr > 4 ? 'OT' : p.qtr} ${p.time ?? ''}`,
									stat: `${Math.round(Math.abs(p.wpa) * 100)}% WP`
								}))
							}
						]
					}
				]
			: []
	);
</script>

<svelte:head><title>Record book · Any Given Stat</title></svelte:head>

<div class="page-head">
	<div class="eyebrow">History</div>
	<h1>The record book</h1>
	<p class="lede">
		The best and worst of every season since {r?.seasons[0] ?? 2016}, by efficiency rather than
		box-score totals, plus the wildest games and plays.
	</p>
</div>

{#if res.error}
	<LoadError message={res.error} />
{:else if !r}
	<Skeleton height={500} />
{:else}
	<PageToc
		items={[
			...sections.map((s) => ({ id: s.id, label: s.label })),
			{ id: 'fantasy', label: 'Fantasy' }
		]}
	/>
	{#each sections as s (s.id)}
		<h2 class="section" id={s.id}>{s.label}</h2>
		<div class="grid-2">
			{#each s.lists as l (l.title)}
				<RecordList title={l.title} blurb={l.blurb} items={l.items} />
			{/each}
		</div>
	{/each}
	<p class="muted small">
		Season lists are regular season only; game lists include the playoffs. {r.wp_note}
	</p>
	<h2 class="section" id="fantasy">Fantasy</h2>
	<FantasyRecords
		seasons={Array.from(
			{ length: r.seasons[r.seasons.length - 1] - r.seasons[0] + 1 },
			(_, i) => r.seasons[0] + i
		)}
	/>
{/if}

<style>
	/* Section titles with a brand-gradient rule fading out to the right. */
	.section {
		display: flex;
		align-items: center;
		gap: 0.9rem;
		font-size: 1.5rem;
		font-stretch: 112%;
		margin: 1.75rem 0 0.85rem;
		scroll-margin-top: 7.5rem; /* clear the header and the sticky "On this page" bar */
	}
	.section::after {
		content: '';
		flex: 1;
		height: 2px;
		border-radius: 2px;
		background: linear-gradient(90deg, var(--brand-a), var(--brand-b) 30%, transparent);
		opacity: 0.6;
	}
	.small {
		font-size: 0.8rem;
		max-width: 80ch;
	}
</style>
