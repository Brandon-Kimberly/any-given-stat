<script lang="ts">
	// The player page for everyone the efficiency datasets don't cover: kickers, punters,
	// defenders and depth players. Built from players/<id>.json (every game line, box-score
	// keys): season tiles for the role, a weekly chart, the game log, fantasy points and career
	// totals. `embedded` = a two-way player's defense below his efficiency page (no banner).
	import { base } from '$app/paths';
	import Avatar from '$lib/components/Avatar.svelte';
	import { statSummary } from '$lib/components/BoxScore.svelte';
	import CountUp from '$lib/components/CountUp.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import LoadError from '$lib/components/LoadError.svelte';
	import PlayerFantasy from '$lib/components/PlayerFantasy.svelte';
	import PlotFigure from '$lib/components/Plot.svelte';
	import SampleWarning from '$lib/components/SampleWarning.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import TeamBadge from '$lib/components/TeamBadge.svelte';
	import type { NumericStatKey, StatLine } from '$lib/fantasy/statline';
	import { num, pct } from '$lib/format';
	import { loadPlayerProfile } from '$lib/playerPages.svelte';
	import { gridY, isNarrow, Plot, plotStyle } from '$lib/plot';
	import { prefs, savePrefs } from '$lib/prefs.svelte';
	import { resource } from '$lib/resource.svelte';
	import { teamColor, teamName } from '$lib/teams.svelte';
	import type { PlayerProfile } from '$lib/types';

	let { id, embedded = false }: { id: string; embedded?: boolean } = $props();

	let profile = $state.raw<PlayerProfile | null | undefined>(undefined);
	let error = $state.raw<string | null>(null);
	$effect(() => {
		const want = id;
		profile = undefined;
		error = null;
		loadPlayerProfile(want)
			.then((p) => {
				if (id === want) profile = p;
			})
			.catch((e) => {
				if (id !== want) return;
				const msg = e instanceof Error ? e.message : String(e);
				if (/HTTP 404/.test(msg)) profile = null;
				else error = msg;
			});
	});
	const metaRes = resource('meta');

	// ---------- roles and totals ----------
	type Role = 'DEF' | 'K' | 'P' | 'OFF' | 'RET';
	const ROLE_OF: Record<string, Role> = { DL: 'DEF', LB: 'DEF', DB: 'DEF', K: 'K', P: 'P' };
	const GROUP_LABEL: Record<string, string> = {
		DL: 'Defensive line',
		LB: 'Linebackers',
		DB: 'Defensive backs',
		K: 'Kickers',
		P: 'Punters',
		OL: 'Offensive line',
		QB: 'Quarterbacks',
		RB: 'Running backs',
		WR: 'Wide receivers',
		TE: 'Tight ends'
	};
	const SUM: NumericStatKey[] = [
		'tkl_solo',
		'tkl_ast',
		'tkl_loss',
		'sack',
		'sack_yd',
		'qb_hit',
		'def_int',
		'int_ret_yd',
		'def_pd',
		'def_ff',
		'def_fum_rec',
		'def_td',
		'st_td',
		'def_safe',
		'blk_kick',
		'fga',
		'fgm',
		'xpa',
		'xpm',
		'punts',
		'punt_yd',
		'punt_in20',
		'punt_tb',
		'pass_att',
		'pass_cmp',
		'pass_yd',
		'pass_td',
		'pass_int',
		'rush_att',
		'rush_yd',
		'rush_td',
		'rec_tgt',
		'rec',
		'rec_yd',
		'rec_td',
		'kr',
		'kr_yd',
		'kr_td',
		'pr',
		'pr_yd',
		'pr_td',
		'fum',
		'fum_lost'
	];
	const LONGEST: NumericStatKey[] = ['fg_lng', 'punt_lng'];
	type Totals = Record<NumericStatKey, number> & {
		g: number;
		tkl: number;
		td: number;
		k_pts: number;
		punt_avg: number | null;
		scrimmage: number;
		fg_u40: string;
		fg_40s: string;
		fg_50p: string;
		made: number[];
		missed: number[];
	};
	/** Made/attempted field goals between lo and hi yards. */
	function band(made: number[], missed: number[], lo: number, hi: number): [number, number] {
		const m = made.filter((d) => d >= lo && d <= hi).length;
		return [m, m + missed.filter((d) => d >= lo && d <= hi).length];
	}
	const ratio = ([m, a]: [number, number]) => (a ? `${m}/${a}` : '–');
	function totals(lines: StatLine[]): Totals {
		const t = { g: lines.length, made: [] as number[], missed: [] as number[] } as Totals;
		for (const k of [...SUM, ...LONGEST]) t[k] = 0;
		for (const l of lines) {
			for (const k of SUM) t[k] += (l[k] as number | undefined) ?? 0;
			for (const k of LONGEST) t[k] = Math.max(t[k], (l[k] as number | undefined) ?? 0);
			t.made.push(...(l.fgm_dists ?? []));
			t.missed.push(...(l.fgmiss_dists ?? []));
		}
		t.tkl = t.tkl_solo + t.tkl_ast;
		t.td = t.def_td + t.st_td;
		t.k_pts = 3 * t.fgm + t.xpm;
		t.punt_avg = t.punts ? t.punt_yd / t.punts : null;
		t.scrimmage = t.rush_yd + t.rec_yd;
		t.fg_u40 = ratio(band(t.made, t.missed, 0, 39));
		t.fg_40s = ratio(band(t.made, t.missed, 40, 49));
		t.fg_50p = ratio(band(t.made, t.missed, 50, 99));
		return t;
	}
	/** Which roles a set of totals shows stats for. */
	function has(t: Totals, role: Role): boolean {
		switch (role) {
			case 'DEF':
				return t.tkl + t.sack + t.qb_hit + t.def_int + t.def_pd + t.def_ff + t.def_fum_rec > 0;
			case 'K':
				return t.fga + t.xpa > 0;
			case 'P':
				return t.punts > 0;
			case 'OFF':
				return t.pass_att + t.rush_att + t.rec_tgt + t.rec > 0;
			case 'RET':
				return t.kr + t.pr > 0;
		}
	}

	// ---------- the player's games ----------
	type Game = {
		gid: string;
		season: number;
		week: number;
		post: boolean;
		team: string;
		opp: string;
		where: string;
		line: StatLine;
	};
	const games = $derived<Game[]>(
		(profile?.games ?? []).map(([gid, week, post, team, opp, home, line]) => ({
			gid,
			season: Number(gid.slice(0, 4)),
			week,
			post: post === 1,
			team,
			opp,
			where: home ? 'vs' : '@',
			line
		}))
	);
	const seasons = $derived([...new Set(games.map((g) => g.season))].sort((a, b) => a - b));
	const group = $derived(profile?.group ?? null);
	const primary = $derived<Role>(ROLE_OF[group ?? ''] ?? 'OFF');
	// One season for the whole page: the site's season when he played that year, else his
	// latest. Picking one sets the site's season (as on the efficiency pages).
	const season = $derived(
		prefs.season != null && seasons.includes(prefs.season) ? prefs.season : (seasons.at(-1) ?? 0)
	);
	const status = $derived(metaRes.value?.seasons.find((s) => s.season === season));
	function pickSeason(v: number) {
		prefs.season = v;
		savePrefs();
	}
	const teamBySeason = $derived(new Map(profile?.teams ?? []));
	const lastTeam = $derived(profile?.teams.at(-1)?.[1] ?? '');
	const seasonTeam = $derived(teamBySeason.get(season) ?? lastTeam);

	const seasonGames = $derived(games.filter((g) => g.season === season));
	const regular = $derived(seasonGames.filter((g) => !g.post));
	const tot = $derived(totals(regular.map((g) => g.line)));
	const career = $derived(totals(games.filter((g) => !g.post).map((g) => g.line)));
	// The primary role always shows; other roles once he has a stat there (a kicker who punts,
	// a safety who returns kicks). Embedded pages leave offense to the efficiency sections.
	const roles = $derived<Role[]>(
		[primary, ...(['DEF', 'K', 'P', 'OFF', 'RET'] as Role[]).filter((r) => r !== primary)].filter(
			(r) =>
				!(embedded && r === 'OFF') && (r === primary ? !embedded || has(career, r) : has(career, r))
		)
	);

	// ---------- season tiles ----------
	type Tile = { label: string; value: string; note: string };
	const half = (v: number) => num(v, Number.isInteger(v) ? 0 : 1);
	const share = (m: number, a: number) => (a ? pct(m / a, 1) : ' ');
	function tilesFor(role: Role, t: Totals): Tile[] {
		switch (role) {
			case 'DEF':
				return [
					{
						label: 'Tackles',
						value: num(t.tkl),
						note: `${t.tkl_solo} solo, ${t.tkl_ast} assisted`
					},
					{ label: 'Tackles for loss', value: num(t.tkl_loss), note: ' ' },
					{
						label: 'Sacks',
						value: half(t.sack),
						note: t.sack_yd ? `${num(t.sack_yd)} yards lost` : ' '
					},
					{ label: 'QB hits', value: num(t.qb_hit), note: ' ' },
					{
						label: 'Interceptions',
						value: num(t.def_int),
						note: t.def_int ? `${num(t.int_ret_yd)} return yards` : ' '
					},
					{ label: 'Passes defended', value: num(t.def_pd), note: ' ' },
					{ label: 'Forced fumbles', value: num(t.def_ff), note: ' ' },
					{ label: 'Fumble recoveries', value: num(t.def_fum_rec), note: ' ' },
					{
						label: 'Touchdowns',
						value: num(t.td),
						note: t.st_td
							? `${t.def_td} defense, ${t.st_td} special teams`
							: 'INT and fumble returns'
					}
				];
			case 'K': {
				const bands: [string, number, number][] = [
					['FG under 40', 0, 39],
					['FG 40–49', 40, 49],
					['FG 50+', 50, 99]
				];
				return [
					{ label: 'Field goals', value: `${t.fgm}/${t.fga}`, note: share(t.fgm, t.fga) },
					...bands.map(([label, lo, hi]) => {
						const [m, a] = band(t.made, t.missed, lo, hi);
						return { label, value: `${m}/${a}`, note: share(m, a) };
					}),
					{ label: 'Longest FG', value: t.fg_lng ? `${t.fg_lng} yds` : '–', note: ' ' },
					{ label: 'Extra points', value: `${t.xpm}/${t.xpa}`, note: share(t.xpm, t.xpa) },
					{
						label: 'Kicking points',
						value: num(t.k_pts),
						note: t.g ? `${num(t.k_pts / t.g, 1)} per game` : ' '
					}
				];
			}
			case 'P':
				return [
					{
						label: 'Punts',
						value: num(t.punts),
						note: t.g ? `${num(t.punts / t.g, 1)} per game` : ' '
					},
					{
						label: 'Gross average',
						value: t.punt_avg == null ? '–' : `${num(t.punt_avg, 1)} yds`,
						note: `${num(t.punt_yd)} yards`
					},
					{ label: 'Inside the 20', value: num(t.punt_in20), note: share(t.punt_in20, t.punts) },
					{ label: 'Touchbacks', value: num(t.punt_tb), note: share(t.punt_tb, t.punts) },
					{ label: 'Longest punt', value: t.punt_lng ? `${t.punt_lng} yds` : '–', note: ' ' }
				];
			case 'OFF': {
				const out: Tile[] = [];
				if (t.pass_att)
					out.push({
						label: 'Passing yards',
						value: num(t.pass_yd),
						note: `${t.pass_cmp}/${t.pass_att}, ${t.pass_td} TD, ${t.pass_int} INT`
					});
				if (t.rush_att)
					out.push({
						label: 'Rushing yards',
						value: num(t.rush_yd),
						note: `${t.rush_att} carries, ${t.rush_td} TD`
					});
				if (t.rec_tgt || t.rec)
					out.push({
						label: 'Receiving yards',
						value: num(t.rec_yd),
						note: `${t.rec} catches, ${t.rec_tgt} targets, ${t.rec_td} TD`
					});
				if (t.fum) out.push({ label: 'Fumbles', value: num(t.fum), note: `${t.fum_lost} lost` });
				return out;
			}
			case 'RET': {
				const out: Tile[] = [];
				if (t.kr)
					out.push({
						label: 'Kick returns',
						value: `${num(t.kr_yd)} yds`,
						note: `${t.kr} returns, ${t.kr_td} TD`
					});
				if (t.pr)
					out.push({
						label: 'Punt returns',
						value: `${num(t.pr_yd)} yds`,
						note: `${t.pr} returns, ${t.pr_td} TD`
					});
				return out;
			}
		}
	}
	const tiles = $derived<Tile[]>([
		{
			label: 'Games',
			value: num(tot.g),
			note:
				seasonGames.length > regular.length
					? `+${seasonGames.length - regular.length} playoff`
					: 'with a stat'
		},
		// Other roles add only the tiles he has a number in (a kicker's two tackles: one tile).
		...roles.flatMap((r) =>
			r === primary ? tilesFor(r, tot) : tilesFor(r, tot).filter((t) => /[1-9]/.test(t.value))
		)
	]);

	// ---------- weekly chart: the role's headline number per regular-season game ----------
	type Metric = { key: keyof Totals; label: string; text: (t: Totals) => string };
	const METRIC: Record<Role, Metric> = {
		DEF: { key: 'tkl', label: '↑ Tackles', text: (t) => `${t.tkl} tackles` },
		K: { key: 'k_pts', label: '↑ Kicking points', text: (t) => `${t.k_pts} points` },
		P: {
			key: 'punt_avg',
			label: '↑ Gross yards per punt',
			text: (t) => `${num(t.punt_avg, 1)} yards per punt on ${t.punts}`
		},
		OFF: {
			key: 'scrimmage',
			label: '↑ Yards from scrimmage',
			text: (t) => `${t.scrimmage} scrimmage yards`
		},
		RET: { key: 'kr_yd', label: '↑ Return yards', text: (t) => `${t.kr_yd + t.pr_yd} return yards` }
	};
	const metric = $derived(
		primary === 'OFF' && group === 'QB'
			? {
					key: 'pass_yd' as const,
					label: '↑ Passing yards',
					text: (t: Totals) => `${t.pass_yd} passing yards`
				}
			: METRIC[primary]
	);
	type Point = { week: number; y: number; title: string };
	const points = $derived<Point[]>(
		regular
			.map((g) => {
				const t = totals([g.line]);
				const y = t[metric.key];
				return {
					week: g.week,
					y: typeof y === 'number' ? y : NaN,
					title:
						`Week ${g.week} ${g.where} ${g.opp}: ${metric.text(t)}\n${statSummary(g.line) || ''}`.trim()
				};
			})
			.filter((p) => Number.isFinite(p.y))
	);
	const chartable = $derived(points.some((p) => p.y > 0));
	const MARGIN_L = 44;
	const MARGIN_R = 20;
	function weeklyChart(width: number) {
		const n = Math.max(4, ...points.map((p) => p.week));
		const bandW = (width - MARGIN_L - MARGIN_R) / n;
		const inset = Math.max(2, (bandW - 36) / 2);
		return Plot.plot({
			width,
			height: 230,
			style: plotStyle,
			marginLeft: MARGIN_L,
			marginRight: MARGIN_R,
			x: {
				label: 'Week',
				type: 'band',
				padding: 0,
				domain: Array.from({ length: n }, (_, i) => i + 1),
				ticks: isNarrow(width) && n > 8 ? [1, 4, 7, 10, 13, 16].filter((w) => w <= n) : undefined
			},
			y: { label: metric.label, nice: true },
			marks: [
				gridY(),
				Plot.ruleY([0], { stroke: 'var(--axis)' }),
				Plot.barY(points, {
					x: 'week',
					y: 'y',
					fill: 'var(--series-1)',
					rx: 3,
					insetLeft: inset,
					insetRight: inset
				}),
				Plot.tip(
					points,
					Plot.pointerX({ lineWidth: 40, x: 'week', y: 'y', title: (p: Point) => p.title })
				)
			]
		});
	}

	// ---------- tables ----------
	type Row = Totals & {
		gid: string;
		season: number;
		week: number;
		team: string;
		opp: string;
		where: string;
	};
	const lastReg = (s: number) => (s >= 2021 ? 18 : 17);
	const ROUNDS = ['Wild Card', 'Divisional', 'Conference', 'Super Bowl'];
	const weekName = (s: number, w: number) =>
		w > lastReg(s) ? (ROUNDS[w - lastReg(s) - 1] ?? `Week ${w}`) : String(w);
	const COLS: Record<Role, Column<Row>[]> = {
		DEF: [
			{ key: 'tkl', label: 'Tkl', fmt: num, title: 'Tackles (solo + assisted)' },
			{ key: 'tkl_solo', label: 'Solo', fmt: num },
			{ key: 'tkl_ast', label: 'Ast', fmt: num, title: 'Assisted tackles' },
			{ key: 'tkl_loss', label: 'TFL', fmt: num, title: 'Tackles for loss' },
			{ key: 'sack', label: 'Sacks', fmt: half },
			{ key: 'qb_hit', label: 'QB hits', fmt: num },
			{ key: 'def_int', label: 'INT', fmt: num, title: 'Interceptions' },
			{ key: 'def_pd', label: 'PD', fmt: num, title: 'Passes defended' },
			{ key: 'def_ff', label: 'FF', fmt: num, title: 'Forced fumbles' },
			{ key: 'def_fum_rec', label: 'FR', fmt: num, title: 'Fumble recoveries' },
			{ key: 'td', label: 'TD', fmt: num, title: 'Defensive and special-teams touchdowns' }
		],
		K: [
			{ key: 'fgm', label: 'FGM', fmt: num, title: 'Field goals made' },
			{ key: 'fga', label: 'FGA', fmt: num, title: 'Field goals attempted' },
			{ key: 'fg_u40', label: '<40', title: 'Field goals under 40 yards, made/attempted' },
			{ key: 'fg_40s', label: '40–49', title: 'Field goals from 40–49 yards, made/attempted' },
			{ key: 'fg_50p', label: '50+', title: 'Field goals of 50+ yards, made/attempted' },
			{ key: 'fg_lng', label: 'Lng', fmt: num, title: 'Longest field goal' },
			{ key: 'xpm', label: 'XPM', fmt: num, title: 'Extra points made' },
			{ key: 'xpa', label: 'XPA', fmt: num, title: 'Extra points attempted' },
			{
				key: 'k_pts',
				label: 'Pts',
				fmt: num,
				title: 'Kicking points: 3 per field goal, 1 per extra point'
			}
		],
		P: [
			{ key: 'punts', label: 'Punts', fmt: num },
			{ key: 'punt_yd', label: 'Yds', fmt: num, title: 'Gross punting yards' },
			{ key: 'punt_avg', label: 'Avg', fmt: (v) => num(v, 1), title: 'Gross yards per punt' },
			{ key: 'punt_in20', label: 'In 20', fmt: num, title: 'Punts downed inside the 20' },
			{ key: 'punt_tb', label: 'TB', fmt: num, title: 'Touchbacks' },
			{ key: 'punt_lng', label: 'Lng', fmt: num, title: 'Longest punt' }
		],
		OFF: [
			{ key: 'pass_cmp', label: 'Cmp', fmt: num, title: 'Completions' },
			{ key: 'pass_att', label: 'Pass att', fmt: num },
			{ key: 'pass_yd', label: 'Pass yds', fmt: num },
			{ key: 'pass_td', label: 'Pass TD', fmt: num },
			{ key: 'pass_int', label: 'INT', fmt: num, title: 'Interceptions thrown' },
			{ key: 'rush_att', label: 'Car', fmt: num, title: 'Carries' },
			{ key: 'rush_yd', label: 'Rush yds', fmt: num },
			{ key: 'rush_td', label: 'Rush TD', fmt: num },
			{ key: 'rec_tgt', label: 'Tgt', fmt: num, title: 'Targets' },
			{ key: 'rec', label: 'Rec', fmt: num, title: 'Receptions' },
			{ key: 'rec_yd', label: 'Rec yds', fmt: num },
			{ key: 'rec_td', label: 'Rec TD', fmt: num },
			{ key: 'fum_lost', label: 'Fum lost', fmt: num, title: 'Fumbles lost' }
		],
		RET: [
			{ key: 'kr', label: 'KR', fmt: num, title: 'Kick returns' },
			{ key: 'kr_yd', label: 'KR yds', fmt: num },
			{ key: 'pr', label: 'PR', fmt: num, title: 'Punt returns' },
			{ key: 'pr_yd', label: 'PR yds', fmt: num }
		]
	};
	/** The roles' columns: the primary role's in full (offense: only stats he has), other roles'
	 * only where he has a number. */
	function statColumns(rows: Row[]): Column<Row>[] {
		const some = (c: Column<Row>) =>
			rows.some((r) => {
				const v = r[c.key];
				return typeof v === 'number' ? v > 0 : v != null && v !== '–';
			});
		return roles.flatMap((r) => (r === primary && r !== 'OFF' ? COLS[r] : COLS[r].filter(some)));
	}
	const row = (g: Game): Row => ({
		...totals([g.line]),
		gid: g.gid,
		season: g.season,
		week: g.week,
		team: g.team,
		opp: g.opp,
		where: g.where
	});
	const logRows = $derived(seasonGames.map(row));
	const logColumns = $derived<Column<Row>[]>([
		{ key: 'week', label: 'Week', sticky: true, fmt: (w: number) => weekName(season, w) },
		{ key: 'where', label: 'H/A', title: 'vs = home, @ = away' },
		{ key: 'opp', label: 'Opp', team: true },
		...statColumns(logRows)
	]);
	const careerRows = $derived<Row[]>(
		seasons.map((s) => ({
			...totals(games.filter((g) => g.season === s && !g.post).map((g) => g.line)),
			gid: '',
			season: s,
			week: 0,
			team: teamBySeason.get(s) ?? '',
			opp: '',
			where: ''
		}))
	);
	const careerColumns = $derived<Column<Row>[]>([
		{ key: 'season', label: 'Season', sticky: true },
		{ key: 'team', label: 'Team', team: true },
		{ key: 'g', label: 'G', fmt: num, title: 'Regular-season games with a stat' },
		...statColumns(careerRows)
	]);

	// ---------- banner facts ----------
	const height = $derived(
		profile?.height ? `${Math.floor(profile.height / 12)}-${profile.height % 12}` : null
	);
	const title = $derived(embedded ? 'Defense and special teams' : `${season} regular season`);
</script>

<svelte:head>
	{#if !embedded}<title>{profile?.name ?? 'Player'} · Any Given Stat</title>{/if}
</svelte:head>

{#if error}
	<LoadError message={error} />
{:else if profile === undefined}
	{#if !embedded}<Skeleton height={300} />{/if}
{:else if profile === null || !games.length}
	{#if !embedded}
		<div class="callout">
			No player with id <code>{id}</code> in the data. Press <kbd>/</kbd> to search, or browse
			<a href="{base}/qbs/">quarterbacks</a>.
		</div>
	{/if}
{:else}
	{#if !embedded}
		<section class="card head" style="--team: {teamColor(seasonTeam)}">
			<div class="stripe"></div>
			<Avatar name={profile.name} src={profile.headshot} team={seasonTeam} size={92} />
			<div class="who">
				<nav class="eyebrow crumbs" aria-label="Breadcrumb">
					<span>Players</span>
					<span aria-hidden="true">/</span>
					<span>{GROUP_LABEL[group ?? ''] ?? 'Players'}</span>
					{#if profile.position}<span aria-hidden="true">·</span><span>{profile.position}</span
						>{/if}
				</nav>
				<h1>{profile.name}</h1>
				<div class="facts">
					<TeamBadge team={seasonTeam} name link {season} />
					{#if profile.jersey}<span>#{profile.jersey}</span>{/if}
					{#if height || profile.weight}<span
							>{[height, profile.weight ? `${profile.weight} lb` : null]
								.filter(Boolean)
								.join(', ')}</span
						>{/if}
					{#if profile.draft_round}<span
							>Drafted {profile.draft_year}, round {profile.draft_round}, pick {profile.draft_pick}</span
						>
					{:else if profile.rookie_season}<span>Rookie season {profile.rookie_season}</span>{/if}
					{#if profile.college}<span>{profile.college}</span>{/if}
					<span>In the data: {seasons[0]}–{seasons.at(-1)}</span>
				</div>
			</div>
			<div class="actions">
				{#if seasons.length > 1}
					<label class="field">
						Season
						<select
							value={season}
							onchange={(e) => pickSeason(+(e.currentTarget as HTMLSelectElement).value)}
						>
							{#each [...seasons].reverse() as s (s)}<option value={s}>{s}</option>{/each}
						</select>
					</label>
				{/if}
			</div>
		</section>
		<SampleWarning {status} />
	{/if}

	<section class="season" aria-labelledby="season-title-{id}">
		<h2 id="season-title-{id}">
			{title}{#if embedded}<span class="muted">{` · ${season} regular season`}</span>{/if}
		</h2>
		<div class="tiles">
			{#each tiles as t (t.label)}
				<div class="card tile">
					<div class="label">{t.label}</div>
					<div class="value"><CountUp text={t.value} /></div>
					<div class="note">{t.note}</div>
				</div>
			{/each}
		</div>
	</section>

	<div class="card">
		<h2>{season} game log</h2>
		{#if chartable}
			<p class="sub">
				{metric.label.replace('↑ ', '')} in each regular-season game. Click a game for its play-by-play.
			</p>
			<PlotFigure label="{metric.label.replace('↑ ', '')} by week" render={weeklyChart} />
		{:else}
			<p class="sub">Click a game for its play-by-play.</p>
		{/if}
		{#key season}
			<DataTable
				rows={logRows}
				columns={logColumns}
				sortKey="week"
				sortDesc={false}
				showIndex={false}
				filename="{profile.name}-{season}-games"
				maxHeight="none"
				href={(g) => `${base}/game/?id=${g.gid}`}
			/>
		{/key}
	</div>

	{#if !embedded && primary !== 'P'}
		<PlayerFantasy {id} {season} />
	{/if}

	<div class="card">
		<h2>Career by season</h2>
		<p class="sub">Regular season. Team = the one he played the most games for that season.</p>
		<DataTable
			rows={careerRows}
			columns={careerColumns}
			sortKey="season"
			sortDesc={false}
			showIndex={false}
			filename="{profile.name}-seasons"
			maxHeight="none"
		/>
	</div>
	{#if !embedded}
		<p class="muted small">
			Stats are credited from the play-by-play, so they can differ slightly from official totals.
			The team badge is his team in {season}; {teamName(lastTeam)} is the most recent team in the data,
			not necessarily his current one.
		</p>
	{/if}
{/if}

<style>
	/* Player banner, as on the efficiency pages: headshot in a team-colored ring, team glow. */
	.head {
		position: relative;
		overflow: hidden;
		isolation: isolate;
		display: flex;
		flex-wrap: wrap;
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
	.who {
		flex: 1 1 12rem;
		min-width: 0;
	}
	.crumbs {
		gap: 0.4rem;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		align-self: flex-start;
	}
	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.2rem;
		align-items: center;
		color: var(--text-secondary);
		font-size: 0.9rem;
	}
	.season h2 {
		margin: 0 0 0.75rem;
	}
	.small {
		font-size: 0.8rem;
	}
</style>
