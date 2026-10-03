// ESPN fantasy scoring stat ids -> labels and stat-line extractors.
//
// ESPN league settings list scoring as `{statId, points, pointsOverrides?}` items. Ids and labels
// follow the `espn-api` package's SETTINGS_SCORING_FORMAT_MAP. Every id ESPN can send has a
// label (so unsupported rules can be named); ids we can compute from a StatLine also have `get`.
//
// Semantics, as ESPN scores them:
// - "Every N yards/completions/..." items award points per full N: trunc(total / N).
// - Yardage-game items are exclusive buckets: 17 = a 300-399 yard passing game, 18 = 400+.
// - TD-length items (15/16, 35/36, 45/46 and 175-186) count TDs in that length range.
// - Points/yards-allowed items are indicators for the bucket the defense's game falls in.

import type { FantasyPos, StatLine } from './statline';

/** Which lines an item applies to: 'player' = everyone but team defenses; 'def' = team
 * defenses only; 'defense' = team defenses and IDP players; 'all' = every line. */
export type EspnScope = 'player' | 'def' | 'defense' | 'all';

/** Items ESPN tracks separately but our team lines don't split. On a line where the group
 * applies they are scored together on the combined stat, at the average of their points. */
export type EspnGroup = 'st_td' | 'def_td';

export interface EspnStat {
	label: string;
	scope?: EspnScope; // default 'player'
	get?: (l: StatLine) => number;
	group?: EspnGroup;
}

const IDP: ReadonlySet<FantasyPos> = new Set(['DL', 'LB', 'DB']);

export function espnApplies(scope: EspnScope | undefined, pos: FantasyPos): boolean {
	switch (scope ?? 'player') {
		case 'player':
			return pos !== 'DEF';
		case 'def':
			return pos === 'DEF';
		case 'defense':
			return pos === 'DEF' || IDP.has(pos);
		default:
			return true;
	}
}

export function espnGroupApplies(group: EspnGroup, pos: FantasyPos): boolean {
	return group === 'st_td' ? pos === 'DEF' : pos === 'DEF' || IDP.has(pos);
}

/** ESPN lineup slot ids to look up in `pointsOverrides`, most specific first. IDP positions
 * are coarser here than on ESPN (DL covers DT/DE, DB covers CB/S): best effort. */
export const ESPN_SLOTS: Record<FantasyPos, string[]> = {
	QB: ['0'],
	RB: ['2'],
	WR: ['4'],
	TE: ['6'],
	K: ['17'],
	P: ['18'],
	DEF: ['16'],
	DL: ['11', '9', '8', '15'],
	LB: ['10', '15'],
	DB: ['14', '12', '13', '15'],
	OL: []
};

// ---------- extractor helpers ----------

const n = (v: number | undefined): number => v ?? 0;
const per = (v: number | undefined, size: number): number => Math.trunc((v ?? 0) / size);
const between = (v: number | undefined, lo: number, hi = Infinity): number =>
	(v ?? 0) >= lo && (v ?? 0) <= hi ? 1 : 0;

/** Entries of a distance list within [lo, hi]. */
export function countIn(list: number[] | undefined, lo: number, hi = Infinity): number {
	if (!list) return 0;
	let c = 0;
	for (const d of list) if (d >= lo && d <= hi) c++;
	return c;
}

/** Sum of distances within [lo, hi]. */
export function sumIn(list: number[] | undefined, lo = 0, hi = Infinity): number {
	if (!list) return 0;
	let s = 0;
	for (const d of list) if (d >= lo && d <= hi) s += d;
	return s;
}

const fgMade = (l: StatLine, lo: number, hi = Infinity) => countIn(l.fgm_dists, lo, hi);
const fgMiss = (l: StatLine, lo: number, hi = Infinity) => countIn(l.fgmiss_dists, lo, hi);
const fgAtt = (l: StatLine, lo: number, hi = Infinity) => fgMade(l, lo, hi) + fgMiss(l, lo, hi);
const fgMadeYds = (l: StatLine) => sumIn(l.fgm_dists);
const fgMissYds = (l: StatLine) => sumIn(l.fgmiss_dists);
const fgAttYds = (l: StatLine) => fgMadeYds(l) + fgMissYds(l);
const tackles = (l: StatLine) => n(l.tkl_solo) + n(l.tkl_ast);
const pa = (l: StatLine) => n(l.pts_allow);
const ya = (l: StatLine) => n(l.yds_allow);

/** Points-allowed buckets shared by ids 89-92/121-125 and their D/ST twins 188-196. */
const PA_BUCKETS: [string, number, number][] = [
	['0 points allowed', 0, 0],
	['1-6 points allowed', 1, 6],
	['7-13 points allowed', 7, 13],
	['14-17 points allowed', 14, 17],
	['18-21 points allowed', 18, 21],
	['22-27 points allowed', 22, 27],
	['28-34 points allowed', 28, 34],
	['35-45 points allowed', 35, 45],
	['46+ points allowed', 46, Infinity]
];
const paBucket = (i: number): EspnStat => {
	const [label, lo, hi] = PA_BUCKETS[i];
	return { label, scope: 'def', get: (l) => between(pa(l), lo, hi) };
};
const yaBucket = (label: string, lo: number, hi = Infinity): EspnStat => ({
	label,
	scope: 'def',
	get: (l) => between(ya(l), lo, hi)
});
/** Every-N-yards item on a StatLine field. */
const every = (label: string, size: number, get: (l: StatLine) => number): EspnStat => ({
	label,
	get: (l) => per(get(l), size)
});
const unsupported = (label: string, scope?: EspnScope): EspnStat => ({ label, scope });

export const ESPN_STATS: Record<number, EspnStat> = {
	// Passing
	0: { label: 'Pass attempts', get: (l) => n(l.pass_att) },
	1: { label: 'Completions', get: (l) => n(l.pass_cmp) },
	2: { label: 'Incompletions', get: (l) => n(l.pass_inc) },
	3: { label: 'Passing yards', get: (l) => n(l.pass_yd) },
	4: { label: 'Passing TDs', get: (l) => n(l.pass_td) },
	5: every('Every 5 passing yards', 5, (l) => n(l.pass_yd)),
	6: every('Every 10 passing yards', 10, (l) => n(l.pass_yd)),
	7: every('Every 20 passing yards', 20, (l) => n(l.pass_yd)),
	8: every('Every 25 passing yards', 25, (l) => n(l.pass_yd)),
	9: every('Every 50 passing yards', 50, (l) => n(l.pass_yd)),
	10: every('Every 100 passing yards', 100, (l) => n(l.pass_yd)),
	11: every('Every 5 completions', 5, (l) => n(l.pass_cmp)),
	12: every('Every 10 completions', 10, (l) => n(l.pass_cmp)),
	13: every('Every 5 incompletions', 5, (l) => n(l.pass_inc)),
	14: every('Every 10 incompletions', 10, (l) => n(l.pass_inc)),
	15: { label: '40+ yard TD pass bonus', get: (l) => countIn(l.pass_td_yds, 40) },
	16: { label: '50+ yard TD pass bonus', get: (l) => countIn(l.pass_td_yds, 50) },
	17: { label: '300-399 yard passing game', get: (l) => between(l.pass_yd, 300, 399) },
	18: { label: '400+ yard passing game', get: (l) => between(l.pass_yd, 400) },
	19: { label: '2-pt passing conversions', get: (l) => n(l.pass_2pt) },
	20: { label: 'Interceptions thrown', get: (l) => n(l.pass_int) },
	21: unsupported('Passing completion pct'),
	22: unsupported('Passing yards per game'),

	// Rushing
	23: { label: 'Rushing attempts', get: (l) => n(l.rush_att) },
	24: { label: 'Rushing yards', get: (l) => n(l.rush_yd) },
	25: { label: 'Rushing TDs', get: (l) => n(l.rush_td) },
	26: { label: '2-pt rushing conversions', get: (l) => n(l.rush_2pt) },
	27: every('Every 5 rushing yards', 5, (l) => n(l.rush_yd)),
	28: every('Every 10 rushing yards', 10, (l) => n(l.rush_yd)),
	29: every('Every 20 rushing yards', 20, (l) => n(l.rush_yd)),
	30: every('Every 25 rushing yards', 25, (l) => n(l.rush_yd)),
	31: every('Every 50 rushing yards', 50, (l) => n(l.rush_yd)),
	32: every('Every 100 rushing yards', 100, (l) => n(l.rush_yd)),
	33: every('Every 5 rushing attempts', 5, (l) => n(l.rush_att)),
	34: every('Every 10 rushing attempts', 10, (l) => n(l.rush_att)),
	35: { label: '40+ yard TD rush bonus', get: (l) => countIn(l.rush_td_yds, 40) },
	36: { label: '50+ yard TD rush bonus', get: (l) => countIn(l.rush_td_yds, 50) },
	37: { label: '100-199 yard rushing game', get: (l) => between(l.rush_yd, 100, 199) },
	38: { label: '200+ yard rushing game', get: (l) => between(l.rush_yd, 200) },
	39: unsupported('Rushing yards per attempt'),
	40: unsupported('Rushing yards per game'),

	// Receiving
	41: { label: 'Receptions', get: (l) => n(l.rec) },
	42: { label: 'Receiving yards', get: (l) => n(l.rec_yd) },
	43: { label: 'Receiving TDs', get: (l) => n(l.rec_td) },
	44: { label: '2-pt receiving conversions', get: (l) => n(l.rec_2pt) },
	45: { label: '40+ yard TD reception bonus', get: (l) => countIn(l.rec_td_yds, 40) },
	46: { label: '50+ yard TD reception bonus', get: (l) => countIn(l.rec_td_yds, 50) },
	47: every('Every 5 receiving yards', 5, (l) => n(l.rec_yd)),
	48: every('Every 10 receiving yards', 10, (l) => n(l.rec_yd)),
	49: every('Every 20 receiving yards', 20, (l) => n(l.rec_yd)),
	50: every('Every 25 receiving yards', 25, (l) => n(l.rec_yd)),
	51: every('Every 50 receiving yards', 50, (l) => n(l.rec_yd)),
	52: every('Every 100 receiving yards', 100, (l) => n(l.rec_yd)),
	53: { label: 'Each reception', get: (l) => n(l.rec) },
	54: every('Every 5 receptions', 5, (l) => n(l.rec)),
	55: every('Every 10 receptions', 10, (l) => n(l.rec)),
	56: { label: '100-199 yard receiving game', get: (l) => between(l.rec_yd, 100, 199) },
	57: { label: '200+ yard receiving game', get: (l) => between(l.rec_yd, 200) },
	58: { label: 'Targets', get: (l) => n(l.rec_tgt) },
	59: { label: 'Yards after catch', get: (l) => n(l.rec_yac) },
	60: unsupported('Receiving yards per catch'),
	61: unsupported('Receiving yards per game'),

	// Misc offense
	62: { label: '2-pt conversions', get: (l) => n(l.pass_2pt) + n(l.rush_2pt) + n(l.rec_2pt) },
	63: { label: 'Fumble recovered for TD', get: (l) => n(l.fum_rec_td) },
	64: { label: 'Times sacked', get: (l) => n(l.pass_sack) },
	65: unsupported('Passing fumbles'),
	66: unsupported('Rushing fumbles'),
	67: unsupported('Receiving fumbles'),
	68: { label: 'Fumbles', get: (l) => n(l.fum) },
	69: unsupported('Passing fumbles lost'),
	70: unsupported('Rushing fumbles lost'),
	71: unsupported('Receiving fumbles lost'),
	72: { label: 'Fumbles lost', get: (l) => n(l.fum_lost) },
	73: { label: 'Turnovers', get: (l) => n(l.pass_int) + n(l.fum_lost) },

	// Kicking
	74: { label: 'FG made (50+)', get: (l) => fgMade(l, 50) },
	75: { label: 'FG attempted (50+)', get: (l) => fgAtt(l, 50) },
	76: { label: 'FG missed (50+)', get: (l) => fgMiss(l, 50) },
	77: { label: 'FG made (40-49)', get: (l) => fgMade(l, 40, 49) },
	78: { label: 'FG attempted (40-49)', get: (l) => fgAtt(l, 40, 49) },
	79: { label: 'FG missed (40-49)', get: (l) => fgMiss(l, 40, 49) },
	80: { label: 'FG made (0-39)', get: (l) => fgMade(l, 0, 39) },
	81: { label: 'FG attempted (0-39)', get: (l) => fgAtt(l, 0, 39) },
	82: { label: 'FG missed (0-39)', get: (l) => fgMiss(l, 0, 39) },
	83: { label: 'FG made', get: (l) => n(l.fgm) },
	84: { label: 'FG attempted', get: (l) => l.fga ?? n(l.fgm) + n(l.fgmiss) },
	85: { label: 'FG missed', get: (l) => n(l.fgmiss) },
	86: { label: 'PAT made', get: (l) => n(l.xpm) },
	87: { label: 'PAT attempted', get: (l) => l.xpa ?? n(l.xpm) + n(l.xpmiss) },
	88: { label: 'PAT missed', get: (l) => n(l.xpmiss) },

	// Team defense / special teams and IDP
	89: paBucket(0),
	90: paBucket(1),
	91: paBucket(2),
	92: paBucket(3),
	93: { label: 'Blocked punt or FG return TD', scope: 'def', group: 'st_td' },
	94: { label: 'INT/fumble return TDs', scope: 'defense', get: (l) => n(l.def_td) },
	95: { label: 'Interceptions', scope: 'defense', get: (l) => n(l.def_int) },
	96: { label: 'Fumbles recovered', scope: 'defense', get: (l) => n(l.def_fum_rec) },
	97: { label: 'Blocked kicks', scope: 'defense', get: (l) => n(l.blk_kick) },
	98: { label: 'Safeties', scope: 'defense', get: (l) => n(l.def_safe) },
	99: { label: 'Sacks', scope: 'defense', get: (l) => n(l.sack) },
	100: unsupported('1/2 sack', 'defense'),
	101: { label: 'Kickoff return TDs', get: (l) => n(l.kr_td), group: 'st_td' },
	102: { label: 'Punt return TDs', get: (l) => n(l.pr_td), group: 'st_td' },
	103: { label: 'Interception return TD', scope: 'defense', group: 'def_td' },
	104: { label: 'Fumble return TD', scope: 'defense', group: 'def_td' },
	105: {
		label: 'Return TDs',
		scope: 'all',
		// st_td already includes a player's kick/punt return TDs
		get: (l) => n(l.def_td) + n(l.st_td)
	},
	106: { label: 'Forced fumbles', scope: 'defense', get: (l) => n(l.def_ff) },
	107: { label: 'Assisted tackles', scope: 'defense', get: (l) => n(l.tkl_ast) },
	108: { label: 'Solo tackles', scope: 'defense', get: (l) => n(l.tkl_solo) },
	109: { label: 'Total tackles', scope: 'defense', get: tackles },
	110: { label: 'Every 3 tackles', scope: 'defense', get: (l) => per(tackles(l), 3) },
	111: { label: 'Every 5 tackles', scope: 'defense', get: (l) => per(tackles(l), 5) },
	112: unsupported('Stuffs', 'defense'),
	113: { label: 'Passes defensed', scope: 'defense', get: (l) => n(l.def_pd) },
	114: { label: 'Kickoff return yards', scope: 'all', get: (l) => n(l.kr_yd) },
	115: { label: 'Punt return yards', scope: 'all', get: (l) => n(l.pr_yd) },
	116: { label: 'Every 10 kickoff return yards', scope: 'all', get: (l) => per(l.kr_yd, 10) },
	117: { label: 'Every 25 kickoff return yards', scope: 'all', get: (l) => per(l.kr_yd, 25) },
	118: { label: 'Every 10 punt return yards', scope: 'all', get: (l) => per(l.pr_yd, 10) },
	119: { label: 'Every 25 punt return yards', scope: 'all', get: (l) => per(l.pr_yd, 25) },
	120: { label: 'Points allowed', scope: 'def', get: pa },
	121: paBucket(4),
	122: paBucket(5),
	123: paBucket(6),
	124: paBucket(7),
	125: paBucket(8),
	126: unsupported('Points allowed per game', 'def'),
	127: { label: 'Yards allowed', scope: 'def', get: ya },
	128: yaBucket('Under 100 yards allowed', -Infinity, 99),
	129: yaBucket('100-199 yards allowed', 100, 199),
	130: yaBucket('200-299 yards allowed', 200, 299),
	131: yaBucket('300-349 yards allowed', 300, 349),
	132: yaBucket('350-399 yards allowed', 350, 399),
	133: yaBucket('400-449 yards allowed', 400, 449),
	134: yaBucket('450-499 yards allowed', 450, 499),
	135: yaBucket('500-549 yards allowed', 500, 549),
	136: yaBucket('550+ yards allowed', 550),
	137: unsupported('Yards allowed per game', 'def'),

	// Punting
	138: { label: 'Punts', get: (l) => n(l.punts) },
	139: { label: 'Punt yards', get: (l) => n(l.punt_yd) },
	140: unsupported('Punts inside the 10'),
	141: { label: 'Punts inside the 20', get: (l) => n(l.punt_in20) },
	142: unsupported('Blocked punts'),
	143: unsupported('Punts returned'),
	144: unsupported('Punt return yards allowed'),
	145: { label: 'Punt touchbacks', get: (l) => n(l.punt_tb) },
	146: unsupported('Fair catches'),
	147: unsupported('Punt average'),
	148: unsupported('Punt average 44.0+'),
	149: unsupported('Punt average 42.0-43.9'),
	150: unsupported('Punt average 40.0-41.9'),
	151: unsupported('Punt average 38.0-39.9'),
	152: unsupported('Punt average 36.0-37.9'),
	153: unsupported('Punt average 34.0-35.9'),
	154: unsupported('Punt average 33.9 or less'),

	// Head coach (team results): not computed
	155: unsupported('Team win', 'all'),
	156: unsupported('Team loss', 'all'),
	157: unsupported('Team tie', 'all'),
	158: unsupported('Points scored', 'all'),
	159: unsupported('Points scored per game', 'all'),
	160: unsupported('Margin of victory', 'all'),
	161: unsupported('25+ point win margin', 'all'),
	162: unsupported('20-24 point win margin', 'all'),
	163: unsupported('15-19 point win margin', 'all'),
	164: unsupported('10-14 point win margin', 'all'),
	165: unsupported('5-9 point win margin', 'all'),
	166: unsupported('1-4 point win margin', 'all'),
	167: unsupported('1-4 point loss margin', 'all'),
	168: unsupported('5-9 point loss margin', 'all'),
	169: unsupported('10-14 point loss margin', 'all'),
	170: unsupported('15-19 point loss margin', 'all'),
	171: unsupported('20-24 point loss margin', 'all'),
	172: unsupported('25+ point loss margin', 'all'),
	173: unsupported('Margin of victory per game', 'all'),
	174: unsupported('Winning pct', 'all'),

	// TD length buckets
	175: { label: '0-9 yard TD pass bonus', get: (l) => countIn(l.pass_td_yds, 0, 9) },
	176: { label: '10-19 yard TD pass bonus', get: (l) => countIn(l.pass_td_yds, 10, 19) },
	177: { label: '20-29 yard TD pass bonus', get: (l) => countIn(l.pass_td_yds, 20, 29) },
	178: { label: '30-39 yard TD pass bonus', get: (l) => countIn(l.pass_td_yds, 30, 39) },
	179: { label: '0-9 yard TD rush bonus', get: (l) => countIn(l.rush_td_yds, 0, 9) },
	180: { label: '10-19 yard TD rush bonus', get: (l) => countIn(l.rush_td_yds, 10, 19) },
	181: { label: '20-29 yard TD rush bonus', get: (l) => countIn(l.rush_td_yds, 20, 29) },
	182: { label: '30-39 yard TD rush bonus', get: (l) => countIn(l.rush_td_yds, 30, 39) },
	183: { label: '0-9 yard TD reception bonus', get: (l) => countIn(l.rec_td_yds, 0, 9) },
	184: { label: '10-19 yard TD reception bonus', get: (l) => countIn(l.rec_td_yds, 10, 19) },
	185: { label: '20-29 yard TD reception bonus', get: (l) => countIn(l.rec_td_yds, 20, 29) },
	186: { label: '30-39 yard TD reception bonus', get: (l) => countIn(l.rec_td_yds, 30, 39) },

	// D/ST-specific points allowed: same stat as 120 and the 89-125 buckets
	187: { label: 'D/ST points allowed', scope: 'def', get: pa },
	188: paBucket(0),
	189: paBucket(1),
	190: paBucket(2),
	191: paBucket(3),
	192: paBucket(4),
	193: paBucket(5),
	194: paBucket(6),
	195: paBucket(7),
	196: paBucket(8),
	197: unsupported('D/ST points allowed per game', 'def'),

	// Long field goals
	198: { label: 'FG made (50-59)', get: (l) => fgMade(l, 50, 59) },
	199: { label: 'FG attempted (50-59)', get: (l) => fgAtt(l, 50, 59) },
	200: { label: 'FG missed (50-59)', get: (l) => fgMiss(l, 50, 59) },
	201: { label: 'FG made (60+)', get: (l) => fgMade(l, 60) },
	202: { label: 'FG attempted (60+)', get: (l) => fgAtt(l, 60) },
	203: { label: 'FG missed (60+)', get: (l) => fgMiss(l, 60) },

	// 2-pt returns and 1-pt safeties: not in our play data
	204: unsupported('Offensive 2-pt return', 'all'),
	205: unsupported('Defensive 2-pt return', 'all'),
	206: unsupported('2-pt return', 'all'),
	207: unsupported('Offensive 1-pt safety', 'all'),
	208: unsupported('Defensive 1-pt safety', 'all'),
	209: unsupported('1-pt safety', 'all'),
	210: { label: 'Games played', scope: 'all', get: () => 1 },

	// First downs
	211: { label: 'Passing first downs', get: (l) => n(l.pass_fd) },
	212: { label: 'Rushing first downs', get: (l) => n(l.rush_fd) },
	213: { label: 'Receiving first downs', get: (l) => n(l.rec_fd) },

	// Field goal yardage (on the game's total distance)
	214: { label: 'FG made yards', get: fgMadeYds },
	215: { label: 'FG missed yards', get: fgMissYds },
	216: { label: 'FG attempt yards', get: fgAttYds },
	217: every('Every 5 FG made yards', 5, fgMadeYds),
	218: every('Every 10 FG made yards', 10, fgMadeYds),
	219: every('Every 20 FG made yards', 20, fgMadeYds),
	220: every('Every 25 FG made yards', 25, fgMadeYds),
	221: every('Every 50 FG made yards', 50, fgMadeYds),
	222: every('Every 100 FG made yards', 100, fgMadeYds),
	223: every('Every 5 FG missed yards', 5, fgMissYds),
	224: every('Every 10 FG missed yards', 10, fgMissYds),
	225: every('Every 20 FG missed yards', 20, fgMissYds),
	226: every('Every 25 FG missed yards', 25, fgMissYds),
	227: every('Every 50 FG missed yards', 50, fgMissYds),
	228: every('Every 100 FG missed yards', 100, fgMissYds),
	229: every('Every 5 FG attempt yards', 5, fgAttYds),
	230: every('Every 10 FG attempt yards', 10, fgAttYds),
	231: every('Every 20 FG attempt yards', 20, fgAttYds),
	232: every('Every 25 FG attempt yards', 25, fgAttYds),
	233: every('Every 50 FG attempt yards', 50, fgAttYds),
	234: every('Every 100 FG attempt yards', 100, fgAttYds)
};

/** ESPN `proTeamId` -> our team codes (nflverse: LA = Rams, WAS = Washington). */
export const ESPN_PRO_TEAMS: Record<number, string> = {
	1: 'ATL',
	2: 'BUF',
	3: 'CHI',
	4: 'CIN',
	5: 'CLE',
	6: 'DAL',
	7: 'DEN',
	8: 'DET',
	9: 'GB',
	10: 'TEN',
	11: 'IND',
	12: 'KC',
	13: 'LV',
	14: 'LA',
	15: 'MIA',
	16: 'MIN',
	17: 'NE',
	18: 'NO',
	19: 'NYG',
	20: 'NYJ',
	21: 'PHI',
	22: 'ARI',
	23: 'PIT',
	24: 'LAC',
	25: 'SF',
	26: 'SEA',
	27: 'TB',
	28: 'WAS',
	29: 'CAR',
	30: 'JAX',
	33: 'BAL',
	34: 'HOU'
};
