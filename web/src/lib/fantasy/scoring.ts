// Fantasy scoring engine: a league's scoring settings (Sleeper keys or ESPN stat items) applied
// to the pipeline's stat lines.
//
// Pages score every line of a season on each scoring change, so a Scoring is compiled once
// (per position) into a flat list of (extractor, multiplier) terms, cached by object identity.
// Each term's points are rounded to cents before summing, so `breakdown` parts always add up
// to `scoreLine` exactly.

import {
	ESPN_SLOTS,
	ESPN_STATS,
	countIn,
	espnApplies,
	espnGroupApplies,
	sumIn,
	type EspnGroup
} from './espnStats';
import type { FantasyPos, StatLine } from './statline';

export type Platform = 'sleeper' | 'espn' | 'preset';

/** One ESPN scoring rule. Override keys are ESPN lineup slot ids as strings ("6" = TE). */
export interface EspnScoringItem {
	statId: number;
	points: number;
	pointsOverrides?: Record<string, number>;
}

export interface Scoring {
	platform: Platform;
	label: string;
	/** Sleeper-format settings (Sleeper leagues and the presets). */
	sleeper?: Record<string, number>;
	/** ESPN scoring items (ESPN leagues). */
	espn?: EspnScoringItem[];
}

/** One line of a points breakdown, e.g. {label: 'Receptions', stat: 6, points: 6}. */
export interface PointPart {
	label: string;
	stat: number;
	points: number;
}

interface Term {
	label: string;
	get: (l: StatLine) => number;
	mult: number;
}

/** Round to cents, halves away from zero, never -0. */
export function round2(x: number): number {
	return (Math.sign(x) * Math.round(Math.abs(x) * 100 + 1e-9)) / 100 + 0;
}

// ---------- Sleeper keys ----------

/** Who a Sleeper key applies to: 'player' = everyone but team defenses, 'def' = team
 * defenses, 'idp' = DL/LB/DB, or an exact position (position bonuses). */
type SleeperScope = 'player' | 'def' | 'idp' | 'all' | FantasyPos;

interface SleeperRule {
	label: string;
	scope: SleeperScope;
	get: (l: StatLine) => number;
}

const n = (v: number | undefined): number => v ?? 0;
const atLeast = (v: number, min: number): number => (v >= min ? 1 : 0);
const inRange = (v: number | undefined, lo: number, hi = Infinity): number =>
	(v ?? 0) >= lo && (v ?? 0) <= hi ? 1 : 0;
const rule = (label: string, scope: SleeperScope, get: (l: StatLine) => number): SleeperRule => ({
	label,
	scope,
	get
});
/** A per-unit player stat read straight off the line. */
const stat = (label: string, key: keyof StatLine): SleeperRule =>
	rule(label, 'player', (l) => n(l[key] as number | undefined));
const defStat = (label: string, key: keyof StatLine): SleeperRule =>
	rule(label, 'def', (l) => n(l[key] as number | undefined));
const idpStat = (label: string, key: keyof StatLine): SleeperRule =>
	rule(label, 'idp', (l) => n(l[key] as number | undefined));
const fgm = (label: string, lo: number, hi = Infinity) =>
	rule(label, 'player', (l) => countIn(l.fgm_dists, lo, hi));
const fgmiss = (label: string, lo: number, hi = Infinity) =>
	rule(label, 'player', (l) => countIn(l.fgmiss_dists, lo, hi));
const ptsAllow = (label: string, lo: number, hi = Infinity) =>
	rule(label, 'def', (l) => inRange(l.pts_allow, lo, hi));
const ydsAllow = (label: string, lo: number, hi = Infinity) =>
	rule(label, 'def', (l) => inRange(l.yds_allow, lo, hi));
const rushRecYd = (l: StatLine) => n(l.rush_yd) + n(l.rec_yd);

/** Sleeper scoring keys we can compute. Unknown keys are ignored (see `unsupported`). */
export const SLEEPER_RULES: Record<string, SleeperRule> = {
	// Passing
	pass_att: stat('Pass attempts', 'pass_att'),
	pass_cmp: stat('Completions', 'pass_cmp'),
	pass_inc: stat('Incompletions', 'pass_inc'),
	pass_yd: stat('Passing yards', 'pass_yd'),
	pass_td: stat('Passing TDs', 'pass_td'),
	pass_int: stat('Interceptions thrown', 'pass_int'),
	pass_int_td: stat('Pick-sixes thrown', 'pass_int_td'),
	pass_sack: stat('Times sacked', 'pass_sack'),
	pass_sack_yd: stat('Sack yards lost', 'pass_sack_yd'),
	pass_fd: stat('Passing first downs', 'pass_fd'),
	pass_2pt: stat('2-pt passes', 'pass_2pt'),
	pass_cmp_40p: stat('40+ yard completions', 'pass_cmp_40p'),
	pass_td_40p: rule('40+ yard TD pass bonus', 'player', (l) => countIn(l.pass_td_yds, 40)),
	pass_td_50p: rule('50+ yard TD pass bonus', 'player', (l) => countIn(l.pass_td_yds, 50)),
	bonus_pass_yd_300: rule('300+ passing yard game', 'player', (l) => atLeast(n(l.pass_yd), 300)),
	bonus_pass_yd_400: rule('400+ passing yard game', 'player', (l) => atLeast(n(l.pass_yd), 400)),
	bonus_pass_cmp_25: rule('25+ completion game', 'player', (l) => atLeast(n(l.pass_cmp), 25)),

	// Rushing
	rush_att: stat('Rushing attempts', 'rush_att'),
	rush_yd: stat('Rushing yards', 'rush_yd'),
	rush_td: stat('Rushing TDs', 'rush_td'),
	rush_fd: stat('Rushing first downs', 'rush_fd'),
	rush_2pt: stat('2-pt rushes', 'rush_2pt'),
	rush_40p: stat('40+ yard rushes', 'rush_40p'),
	rush_td_40p: rule('40+ yard TD rush bonus', 'player', (l) => countIn(l.rush_td_yds, 40)),
	rush_td_50p: rule('50+ yard TD rush bonus', 'player', (l) => countIn(l.rush_td_yds, 50)),
	bonus_rush_yd_100: rule('100+ rushing yard game', 'player', (l) => atLeast(n(l.rush_yd), 100)),
	bonus_rush_yd_200: rule('200+ rushing yard game', 'player', (l) => atLeast(n(l.rush_yd), 200)),
	bonus_rush_att_20: rule('20+ carry game', 'player', (l) => atLeast(n(l.rush_att), 20)),

	// Receiving
	rec: stat('Receptions', 'rec'),
	rec_tgt: stat('Targets', 'rec_tgt'),
	rec_yd: stat('Receiving yards', 'rec_yd'),
	rec_td: stat('Receiving TDs', 'rec_td'),
	rec_fd: stat('Receiving first downs', 'rec_fd'),
	rec_2pt: stat('2-pt receptions', 'rec_2pt'),
	rec_40p: stat('40+ yard receptions', 'rec_40p'),
	rec_0_4: stat('0-4 yard receptions', 'rec_0_4'),
	rec_5_9: stat('5-9 yard receptions', 'rec_5_9'),
	rec_10_19: stat('10-19 yard receptions', 'rec_10_19'),
	rec_20_29: stat('20-29 yard receptions', 'rec_20_29'),
	rec_30_39: stat('30-39 yard receptions', 'rec_30_39'),
	rec_td_40p: rule('40+ yard TD reception bonus', 'player', (l) => countIn(l.rec_td_yds, 40)),
	rec_td_50p: rule('50+ yard TD reception bonus', 'player', (l) => countIn(l.rec_td_yds, 50)),
	bonus_rec_yd_100: rule('100+ receiving yard game', 'player', (l) => atLeast(n(l.rec_yd), 100)),
	bonus_rec_yd_200: rule('200+ receiving yard game', 'player', (l) => atLeast(n(l.rec_yd), 200)),
	bonus_rush_rec_yd_100: rule('100+ scrimmage yard game', 'player', (l) =>
		atLeast(rushRecYd(l), 100)
	),
	bonus_rush_rec_yd_200: rule('200+ scrimmage yard game', 'player', (l) =>
		atLeast(rushRecYd(l), 200)
	),

	// Position bonuses
	bonus_rec_rb: rule('RB reception bonus', 'RB', (l) => n(l.rec)),
	bonus_rec_wr: rule('WR reception bonus', 'WR', (l) => n(l.rec)),
	bonus_rec_te: rule('TE reception bonus', 'TE', (l) => n(l.rec)),
	// First-down bonuses: rushing + receiving first downs; for QBs passing + rushing.
	bonus_fd_qb: rule('QB first down bonus', 'QB', (l) => n(l.pass_fd) + n(l.rush_fd)),
	bonus_fd_rb: rule('RB first down bonus', 'RB', (l) => n(l.rush_fd) + n(l.rec_fd)),
	bonus_fd_wr: rule('WR first down bonus', 'WR', (l) => n(l.rush_fd) + n(l.rec_fd)),
	bonus_fd_te: rule('TE first down bonus', 'TE', (l) => n(l.rush_fd) + n(l.rec_fd)),

	// Ball security, returns
	fum: stat('Fumbles', 'fum'),
	fum_lost: stat('Fumbles lost', 'fum_lost'),
	fum_rec_td: stat('Fumble recovery TDs', 'fum_rec_td'),
	kr_yd: stat('Kick return yards', 'kr_yd'),
	pr_yd: stat('Punt return yards', 'pr_yd'),
	// Players: every special-teams TD. Team defenses too, unless the league scores them under
	// def_st_td (Sleeper's DEF key); see compileSleeper.
	st_td: rule('Special teams TDs', 'all', (l) => n(l.st_td)),

	// Kicking
	xpm: stat('PATs made', 'xpm'),
	xpmiss: stat('PATs missed', 'xpmiss'),
	fgm: stat('FGs made', 'fgm'),
	fgmiss: stat('FGs missed', 'fgmiss'),
	fga: rule('FG attempts', 'player', (l) => l.fga ?? n(l.fgm) + n(l.fgmiss)),
	fgm_0_19: fgm('FG made 0-19', 0, 19),
	fgm_20_29: fgm('FG made 20-29', 20, 29),
	fgm_30_39: fgm('FG made 30-39', 30, 39),
	fgm_40_49: fgm('FG made 40-49', 40, 49),
	fgm_50p: fgm('FG made 50+', 50),
	fgm_50_59: fgm('FG made 50-59', 50, 59),
	fgm_60p: fgm('FG made 60+', 60),
	fgmiss_0_19: fgmiss('FG missed 0-19', 0, 19),
	fgmiss_20_29: fgmiss('FG missed 20-29', 20, 29),
	fgmiss_30_39: fgmiss('FG missed 30-39', 30, 39),
	fgmiss_40_49: fgmiss('FG missed 40-49', 40, 49),
	fgmiss_50p: fgmiss('FG missed 50+', 50),
	fgmiss_50_59: fgmiss('FG missed 50-59', 50, 59),
	fgmiss_60p: fgmiss('FG missed 60+', 60),
	fgm_yds: rule('FG yards made', 'player', (l) => sumIn(l.fgm_dists)),
	fgm_yds_over_30: rule('FG yards beyond 30', 'player', (l) => {
		let s = 0;
		for (const d of l.fgm_dists ?? []) if (d > 30) s += d - 30;
		return s;
	}),

	// Team defense
	sack: defStat('Sacks', 'sack'),
	int: defStat('Interceptions', 'def_int'),
	fum_rec: defStat('Fumble recoveries', 'def_fum_rec'),
	ff: defStat('Forced fumbles', 'def_ff'),
	def_td: defStat('Defensive TDs', 'def_td'),
	def_st_td: defStat('Special teams TDs', 'st_td'),
	safe: defStat('Safeties', 'def_safe'),
	blk_kick: defStat('Blocked kicks', 'blk_kick'),
	def_kr_yd: defStat('Kick return yards', 'kr_yd'),
	def_pr_yd: defStat('Punt return yards', 'pr_yd'),
	pts_allow: defStat('Points allowed', 'pts_allow'),
	pts_allow_0: ptsAllow('0 points allowed', 0, 0),
	pts_allow_1_6: ptsAllow('1-6 points allowed', 1, 6),
	pts_allow_7_13: ptsAllow('7-13 points allowed', 7, 13),
	pts_allow_14_20: ptsAllow('14-20 points allowed', 14, 20),
	pts_allow_21_27: ptsAllow('21-27 points allowed', 21, 27),
	pts_allow_28_34: ptsAllow('28-34 points allowed', 28, 34),
	pts_allow_35p: ptsAllow('35+ points allowed', 35),
	yds_allow: defStat('Yards allowed', 'yds_allow'),
	yds_allow_0_100: ydsAllow('Under 100 yards allowed', -Infinity, 99),
	yds_allow_100_199: ydsAllow('100-199 yards allowed', 100, 199),
	yds_allow_200_299: ydsAllow('200-299 yards allowed', 200, 299),
	yds_allow_300_349: ydsAllow('300-349 yards allowed', 300, 349),
	yds_allow_350_399: ydsAllow('350-399 yards allowed', 350, 399),
	yds_allow_400_449: ydsAllow('400-449 yards allowed', 400, 449),
	yds_allow_450_499: ydsAllow('450-499 yards allowed', 450, 499),
	yds_allow_500_549: ydsAllow('500-549 yards allowed', 500, 549),
	yds_allow_550p: ydsAllow('550+ yards allowed', 550),

	// IDP
	idp_tkl: rule('Tackles', 'idp', (l) => n(l.tkl_solo) + n(l.tkl_ast)),
	idp_tkl_solo: idpStat('Solo tackles', 'tkl_solo'),
	idp_tkl_ast: idpStat('Assisted tackles', 'tkl_ast'),
	idp_tkl_loss: idpStat('Tackles for loss', 'tkl_loss'),
	idp_sack: idpStat('Sacks', 'sack'),
	idp_sack_yd: idpStat('Sack yards', 'sack_yd'),
	idp_qb_hit: idpStat('QB hits', 'qb_hit'),
	idp_int: idpStat('Interceptions', 'def_int'),
	idp_int_ret_yd: idpStat('Interception return yards', 'int_ret_yd'),
	idp_ff: idpStat('Forced fumbles', 'def_ff'),
	idp_fum_rec: idpStat('Fumble recoveries', 'def_fum_rec'),
	idp_pass_def: idpStat('Passes defensed', 'def_pd'),
	idp_def_td: idpStat('Defensive TDs', 'def_td'),
	idp_safe: idpStat('Safeties', 'def_safe'),
	idp_blk_kick: idpStat('Blocked kicks', 'blk_kick')
};

/** Sleeper keys we recognize but can't compute (special-teams forced fumbles and recoveries
 * aren't split out of the team totals). They score 0 and are reported when non-zero. */
const SLEEPER_UNTRACKED = new Set(['def_st_ff', 'def_st_fum_rec']);

const IDP: ReadonlySet<FantasyPos> = new Set(['DL', 'LB', 'DB']);

function sleeperApplies(scope: SleeperScope, pos: FantasyPos): boolean {
	switch (scope) {
		case 'all':
			return true;
		case 'player':
			return pos !== 'DEF';
		case 'def':
			return pos === 'DEF';
		case 'idp':
			return IDP.has(pos);
		default:
			return scope === pos;
	}
}

function compileSleeper(settings: Record<string, number>, pos: FantasyPos): Term[] {
	const terms: Term[] = [];
	// Sleeper scores team-defense return TDs under def_st_td; st_td is the player key. Only a
	// league without def_st_td (e.g. hand-written settings) falls back to st_td for DEF.
	const defHasStKey = 'def_st_td' in settings;
	for (const [key, mult] of Object.entries(settings)) {
		const r = SLEEPER_RULES[key];
		if (!r || !mult || !Number.isFinite(mult)) continue;
		if (!sleeperApplies(r.scope, pos)) continue;
		if (key === 'st_td' && pos === 'DEF' && defHasStKey) continue;
		terms.push({ label: r.label, get: r.get, mult });
	}
	return terms;
}

// ---------- ESPN items ----------

/** Points an item awards a position: the first matching lineup-slot override, else points. */
function espnPoints(item: EspnScoringItem, pos: FantasyPos): number {
	const o = item.pointsOverrides;
	if (o) for (const slot of ESPN_SLOTS[pos]) if (o[slot] != null) return o[slot];
	return item.points;
}

const GROUP_TERMS: Record<EspnGroup, Omit<Term, 'mult'>> = {
	st_td: { label: 'Special teams TDs', get: (l) => n(l.st_td) },
	def_td: { label: 'INT/fumble return TDs', get: (l) => n(l.def_td) }
};

/** Points per item of each group present for a position (see EspnGroup). */
function espnGroups(items: EspnScoringItem[], pos: FantasyPos): Map<EspnGroup, number[]> {
	const groups = new Map<EspnGroup, number[]>();
	for (const item of items) {
		const s = ESPN_STATS[item.statId];
		if (!s?.group || !espnGroupApplies(s.group, pos)) continue;
		const pts = espnPoints(item, pos);
		if (!pts) continue;
		groups.set(s.group, [...(groups.get(s.group) ?? []), pts]);
	}
	return groups;
}

const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

function compileEspn(items: EspnScoringItem[], pos: FantasyPos): Term[] {
	const terms: Term[] = [];
	for (const item of items) {
		const s = ESPN_STATS[item.statId];
		if (!s) continue;
		if (s.group && espnGroupApplies(s.group, pos)) continue; // scored below
		if (!s.get || !espnApplies(s.scope, pos)) continue;
		const mult = espnPoints(item, pos);
		if (!mult || !Number.isFinite(mult)) continue;
		terms.push({ label: s.label, get: s.get, mult });
	}
	for (const [group, pts] of espnGroups(items, pos)) {
		terms.push({ ...GROUP_TERMS[group], mult: mean(pts) });
	}
	return terms;
}

// ---------- compile + score ----------

const compiled = new WeakMap<Scoring, Map<FantasyPos, Term[]>>();

function terms(scoring: Scoring, pos: FantasyPos): Term[] {
	let byPos = compiled.get(scoring);
	if (!byPos) compiled.set(scoring, (byPos = new Map()));
	let t = byPos.get(pos);
	if (!t) {
		t =
			scoring.platform === 'espn'
				? compileEspn(scoring.espn ?? [], pos)
				: compileSleeper(scoring.sleeper ?? {}, pos);
		byPos.set(pos, t);
	}
	return t;
}

/** Fantasy points for one stat line, rounded to cents. */
export function scoreLine(line: StatLine, pos: FantasyPos, scoring: Scoring): number {
	let sum = 0;
	for (const t of terms(scoring, pos)) {
		const v = t.get(line);
		if (v) sum += round2(v * t.mult);
	}
	return round2(sum);
}

/** Where the points came from: non-zero parts, largest |points| first. Parts sum to scoreLine. */
export function breakdown(line: StatLine, pos: FantasyPos, scoring: Scoring): PointPart[] {
	const parts: PointPart[] = [];
	for (const t of terms(scoring, pos)) {
		const v = t.get(line);
		const points = v ? round2(v * t.mult) : 0;
		if (points) parts.push({ label: t.label, stat: v, points });
	}
	return parts.sort((a, b) => Math.abs(b.points) - Math.abs(a.points));
}

/** Scoring rules (non-zero) this engine can't compute or only approximates, for a
 * "N scoring rules not supported" note. Sleeper: the raw keys; ESPN: readable labels. */
export function unsupported(scoring: Scoring): string[] {
	const out: string[] = [];
	if (scoring.platform === 'espn') {
		const items = scoring.espn ?? [];
		for (const item of items) {
			const nonZero =
				item.points !== 0 || Object.values(item.pointsOverrides ?? {}).some((v) => v !== 0);
			if (!nonZero) continue;
			const s = ESPN_STATS[item.statId];
			if (!s) out.push(`ESPN stat ${item.statId}`);
			else if (!s.get && !s.group) out.push(s.label);
		}
		// Grouped items scored at their average: say so when they differ.
		for (const pos of ['DEF', 'DL', 'LB', 'DB'] as FantasyPos[]) {
			for (const [group, pts] of espnGroups(items, pos)) {
				if (new Set(pts).size < 2) continue;
				const note =
					group === 'st_td'
						? 'D/ST return TDs (kick, punt and blocked-kick TDs differ; scored at their average)'
						: `${pos === 'DEF' ? 'D/ST' : 'IDP'} INT and fumble return TDs (scored at their average)`;
				if (!out.includes(note)) out.push(note);
			}
		}
	} else {
		for (const [key, v] of Object.entries(scoring.sleeper ?? {})) {
			if (v && (!SLEEPER_RULES[key] || SLEEPER_UNTRACKED.has(key))) out.push(key);
		}
	}
	return out;
}

// ---------- presets ----------

// Sleeper's default league scoring. Choices worth noting: pass_int -1 (Sleeper's current
// default; many older leagues use -2); team-defense return TDs under def_st_td and player
// return TDs under st_td (Sleeper's split); ff 1 for team defenses. Sleeper's defaults also
// include def_st_ff / def_st_fum_rec, which our team lines can't separate, so the presets
// leave them out.
const BASE: Record<string, number> = {
	pass_yd: 0.04,
	pass_td: 4,
	pass_int: -1,
	pass_2pt: 2,
	rush_yd: 0.1,
	rush_td: 6,
	rush_2pt: 2,
	rec_yd: 0.1,
	rec_td: 6,
	rec_2pt: 2,
	fum_lost: -2,
	fum_rec_td: 6,
	st_td: 6,
	fgm_0_19: 3,
	fgm_20_29: 3,
	fgm_30_39: 3,
	fgm_40_49: 4,
	fgm_50p: 5,
	fgmiss: -1,
	xpm: 1,
	xpmiss: -1,
	sack: 1,
	int: 2,
	fum_rec: 2,
	ff: 1,
	def_td: 6,
	def_st_td: 6,
	safe: 2,
	blk_kick: 2,
	pts_allow_0: 10,
	pts_allow_1_6: 7,
	pts_allow_7_13: 4,
	pts_allow_14_20: 1,
	pts_allow_21_27: 0,
	pts_allow_28_34: -1,
	pts_allow_35p: -4
};

export type PresetName = 'ppr' | 'half' | 'standard';

export const PRESETS: Record<PresetName, Scoring> = {
	ppr: { platform: 'preset', label: 'PPR', sleeper: { ...BASE, rec: 1 } },
	half: { platform: 'preset', label: 'Half PPR', sleeper: { ...BASE, rec: 0.5 } },
	standard: { platform: 'preset', label: 'Standard', sleeper: { ...BASE } }
};

export function isPresetName(v: unknown): v is PresetName {
	return v === 'ppr' || v === 'half' || v === 'standard';
}

// ---------- identity ----------

const keys = new WeakMap<Scoring, string>();

/** A stable string for a scoring's rules (key order and zero rules ignored), for memoizing
 * per-scoring results. Two Scorings with the same rules get the same key. */
export function scoringKey(scoring: Scoring): string {
	let k = keys.get(scoring);
	if (k == null) {
		if (scoring.platform === 'espn') {
			const items = (scoring.espn ?? [])
				.map((i) => {
					const o = Object.entries(i.pointsOverrides ?? {})
						.sort(([a], [b]) => a.localeCompare(b))
						.map(([s, p]) => `${s}=${p}`)
						.join(',');
					return `${i.statId}:${i.points}${o ? `[${o}]` : ''}`;
				})
				.sort();
			k = `espn|${items.join(';')}`;
		} else {
			const entries = Object.entries(scoring.sleeper ?? {})
				.filter(([, v]) => v)
				.sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
				.map(([key, v]) => `${key}:${v}`);
			k = `sleeper|${entries.join(';')}`;
		}
		keys.set(scoring, k);
	}
	return k;
}
