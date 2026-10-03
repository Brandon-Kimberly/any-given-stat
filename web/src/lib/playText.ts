// Plays as people read them: a decoded play (from the compact rows in
// games/<season>/<game_id>.json), a broadcast-style headline built from its structured
// fields, and a regex summarizer for raw descriptions (older files, record lists).

import type { GamePlays, PlayKind, PlayPenalty, PlayRow } from './types';

export interface Play {
	/** Index in GamePlays.plays. */
	i: number;
	qtr: number;
	time: string | null;
	team: string;
	down: number | null;
	togo: number | null;
	/** Yards from the offense's own goal line. */
	yl: number | null;
	type: string | null;
	desc: string;
	epa: number | null;
	/** Home win probability after the play. */
	wp: number | null;
	homeScore: number | null;
	awayScore: number | null;
	flags: string;
	drive: number | null;
	/** Change in home win probability on the play. */
	wpa: number | null;
	yds: number | null;
	ylEnd: number | null;
	kind: PlayKind | null;
	a: string | null;
	b: string | null;
	detail: string | null;
	air: number | null;
	kick: number | null;
	ret: number | null;
	d: string | null;
	pen: PlayPenalty | null;
	fum: string | null;
}

const FIELDS: [keyof Play, string][] = [
	['wpa', 'home_wpa'],
	['yds', 'yds'],
	['ylEnd', 'yl_end'],
	['kind', 'kind'],
	['a', 'a'],
	['b', 'b'],
	['detail', 'detail'],
	['air', 'air'],
	['kick', 'kick'],
	['ret', 'ret'],
	['d', 'd'],
	['pen', 'pen'],
	['fum', 'fum']
];

/** Rows → objects. Structured fields are read by column name, so files written before
 * they existed decode too (those fields are null; the WP swing comes from the previous row). */
export function decodePlays(data: GamePlays): Play[] {
	const at = new Map(data.plays_columns.map((c, i) => [c, i]));
	const cols = FIELDS.map(([key, col]) => [key, at.get(col)] as const);
	const hasWpa = at.has('home_wpa');
	let prevWp: number | null = null;
	return data.plays.map((r: PlayRow, i) => {
		const p: Play = {
			i,
			qtr: r[0],
			time: r[1],
			team: r[2],
			down: r[3],
			togo: r[4],
			yl: r[5],
			type: r[6],
			desc: r[7],
			epa: r[8],
			wp: r[9],
			homeScore: r[10],
			awayScore: r[11],
			flags: r[12] ?? '',
			drive: r[13] ?? null,
			wpa: null,
			yds: null,
			ylEnd: null,
			kind: null,
			a: null,
			b: null,
			detail: null,
			air: null,
			kick: null,
			ret: null,
			d: null,
			pen: null,
			fum: null
		};
		const rec = p as unknown as Record<string, unknown>;
		for (const [key, idx] of cols) if (idx != null) rec[key] = (r as unknown[])[idx] ?? null;
		if (!hasWpa && p.wp != null) {
			p.wpa = prevWp == null ? null : Math.round((p.wp - prevWp) * 1000) / 1000;
		}
		if (p.wp != null) prevWp = p.wp;
		return p;
	});
}

// ---- Names. nflfastR writes "D.Singletary"; in a headline the surname reads better, unless
// two players in the same game share it.

const surname = (n: string) => {
	const dot = n.indexOf('.');
	return dot > 0 && dot < n.length - 1 ? n.slice(dot + 1).trim() : n;
};

/** A name shortener for one game: surname, or the full "D.Singletary" form when ambiguous. */
export function nameStyler(plays: Play[]): (name: string | null) => string {
	const bySurname = new Map<string, Set<string>>();
	for (const p of plays)
		for (const field of [p.a, p.b, p.d, p.fum, p.pen?.[3] ?? null])
			for (const n of splitNames(field)) {
				const s = surname(n);
				if (!bySurname.has(s)) bySurname.set(s, new Set());
				bySurname.get(s)!.add(n);
			}
	return (name) => {
		if (!name) return '';
		return splitNames(name)
			.map((n) => ((bySurname.get(surname(n))?.size ?? 1) > 1 ? n : surname(n)))
			.join(' & ');
	};
}
const splitNames = (v: string | null): string[] => (v ? v.split(' / ').filter(Boolean) : []);

// ---- Yardage and field position.

const MINUS = '−';
/** "4 yds", "1 yd", "no gain", "−3 yds". */
export function yards(n: number | null | undefined): string | null {
	if (n == null) return null;
	if (n === 0) return 'no gain';
	const abs = Math.abs(n);
	return `${n < 0 ? MINUS : ''}${abs} yd${abs === 1 ? '' : 's'}`;
}

/** A yard line as broadcast: "NYG 24", "DAL 38", "50". */
export function spot(team: string, yl: number | null, home: string, away: string): string {
	if (yl == null) return '';
	if (yl === 50) return '50';
	const opp = team === home ? away : home;
	return yl < 50 ? `${team} ${yl}` : `${opp} ${100 - yl}`;
}

const ORD = ['', '1st', '2nd', '3rd', '4th'];
/** "1st & 10 · NYG 20", "3rd & Goal · DAL 4", or the play type for untimed downs. */
export function situation(p: Play, home: string, away: string): string {
	const where = spot(p.team, p.yl, home, away);
	if (p.down) {
		const goal = p.yl != null && p.togo != null && 100 - p.yl <= p.togo;
		return `${ORD[p.down]} & ${goal ? 'Goal' : p.togo} · ${where}`;
	}
	const label = KIND_LABEL[p.kind ?? ''] ?? (p.type ?? '').replace('_', ' ');
	return where ? `${label} · ${where}` : label;
}
const KIND_LABEL: Record<string, string> = {
	kickoff: 'Kickoff',
	onside: 'Onside kick',
	xp_good: 'Extra point',
	xp_failed: 'Extra point',
	xp_blocked: 'Extra point',
	'2pt_good': 'Two-point try',
	'2pt_failed': 'Two-point try',
	penalty: 'Penalty'
};

export const quarterLabel = (q: number) => (q > 4 ? (q === 5 ? 'OT' : `OT${q - 4}`) : `Q${q}`);
export const quarterName = (q: number) =>
	q > 4 ? (q === 5 ? 'Overtime' : `Overtime ${q - 4}`) : `${ORD[q]} quarter`;

// ---- Scoring.

export interface ScoreEvent {
	team: string;
	points: number;
	/** Touchdown, Field goal, Safety, Extra point, Two-point try, Defensive two-point. */
	label: string;
	/** A touchdown, field goal or safety: styled as a moment. Tries are quieter. */
	big: boolean;
}

/** What a play scored, from the change in the score against the play before it. */
export function scoreEvent(
	p: Play,
	prev: Play | undefined,
	home: string,
	away: string
): ScoreEvent | null {
	const dh = (p.homeScore ?? 0) - (prev?.homeScore ?? 0);
	const da = (p.awayScore ?? 0) - (prev?.awayScore ?? 0);
	if (p.homeScore == null || p.awayScore == null || (dh <= 0 && da <= 0)) return null;
	const team = dh > 0 ? home : away;
	const points = dh > 0 ? dh : da;
	const tryKind = p.kind?.startsWith('xp_') || p.kind?.startsWith('2pt_');
	let label: string;
	if (points >= 6) label = 'Touchdown';
	else if (points === 3) label = 'Field goal';
	else if (points === 1) label = 'Extra point';
	else if (tryKind || /TWO-POINT/.test(p.desc))
		label = team === p.team ? 'Two-point try' : 'Defensive two-point';
	else label = 'Safety';
	return { team, points, label, big: points >= 6 || points === 3 || label === 'Safety' };
}

// ---- Headlines.

export type Glyph =
	| 'pass'
	| 'incomplete'
	| 'run'
	| 'sack'
	| 'kick'
	| 'punt'
	| 'kickoff'
	| 'penalty'
	| 'turnover'
	| 'score'
	| 'kneel'
	| 'other';

export interface Headline {
	glyph: Glyph;
	/** The play in a few words: "Wilson → Nabers", "Singletary run". */
	lead: string;
	/** Supporting facts, shown after the lead: "29 yds", "deep left". */
	facts: string[];
	/** The result that matters, if any: "Touchdown", "Interception", "No good". */
	outcome: string | null;
	tone: 'good' | 'bad' | null;
	/** A flag that stood next to the play ("Flag: Holding, NYG, 10 yds"). */
	flag: string | null;
}

const PASS_KINDS = new Set<PlayKind>(['complete', 'incomplete', 'interception', 'sack']);

/** Headline for a play from its structured fields (or its description in older files). */
export function headline(p: Play, name: (n: string | null) => string): Headline {
	const h: Headline = {
		glyph: 'other',
		lead: '',
		facts: [],
		outcome: null,
		tone: null,
		flag: null
	};
	const td = p.flags.includes('T');
	const defensiveTd = td && p.ylEnd === 0;
	const fumbleLost = p.flags.includes('F');
	const n = name;
	const push = (...xs: (string | null | undefined | false)[]) => {
		for (const x of xs) if (x) h.facts.push(x);
	};
	const turnoverFacts = () => {
		if (fumbleLost) {
			push(p.fum && `${n(p.fum)} fumbles`, p.d && `${n(p.d)} recovers`);
			h.outcome = defensiveTd ? 'Fumble return TD' : 'Fumble lost';
			h.tone = 'bad';
			h.glyph = 'turnover';
		}
	};

	switch (p.kind) {
		case 'complete':
			h.glyph = 'pass';
			h.lead = `${n(p.a)} → ${n(p.b)}`;
			push(yards(p.yds), p.detail);
			break;
		case 'incomplete':
			h.glyph = 'incomplete';
			h.lead = p.b ? `${n(p.a)} → ${n(p.b)}` : `${n(p.a)} pass`;
			push('incomplete', p.detail);
			break;
		case 'interception':
			h.glyph = 'turnover';
			h.lead = p.d ? `${n(p.d)} intercepts ${n(p.a)}` : `${n(p.a)} intercepted`;
			push(p.b && `intended for ${n(p.b)}`, p.detail, p.ret ? `${p.ret}-yd return` : null);
			h.outcome = defensiveTd ? 'Pick-six' : 'Interception';
			h.tone = 'bad';
			break;
		case 'sack':
			h.glyph = 'sack';
			h.lead = p.d ? `${n(p.d)} sacks ${n(p.a)}` : `${n(p.a)} sacked`;
			push(yards(p.yds));
			break;
		case 'run':
		case 'scramble':
			h.glyph = 'run';
			h.lead = `${n(p.a)} ${p.kind === 'run' ? 'run' : 'scramble'}`;
			push(yards(p.yds), p.detail === 'middle' ? 'up the middle' : p.detail);
			break;
		case 'kneel':
			h.glyph = 'kneel';
			h.lead = `${n(p.a)} kneels`;
			push(yards(p.yds));
			break;
		case 'spike':
			h.glyph = 'kneel';
			h.lead = `${n(p.a)} spikes it`;
			break;
		case 'fg_made':
		case 'fg_missed':
		case 'fg_blocked':
			h.glyph = 'kick';
			h.lead = `${n(p.a)} ${p.kick != null ? `${p.kick}-yd ` : ''}field goal`;
			h.outcome = p.kind === 'fg_made' ? 'Good' : p.kind === 'fg_blocked' ? 'Blocked' : 'No good';
			h.tone = p.kind === 'fg_made' ? 'good' : 'bad';
			push(p.kind === 'fg_blocked' && p.d && `by ${n(p.d)}`);
			if (defensiveTd) h.outcome = 'Blocked, returned for a TD';
			break;
		case 'xp_good':
		case 'xp_failed':
		case 'xp_blocked':
			h.glyph = 'kick';
			h.lead = `${n(p.a)} extra point`;
			h.outcome = p.kind === 'xp_good' ? 'Good' : p.kind === 'xp_blocked' ? 'Blocked' : 'No good';
			h.tone = p.kind === 'xp_good' ? 'good' : 'bad';
			break;
		case '2pt_good':
		case '2pt_failed':
			h.glyph = p.b ? 'pass' : 'run';
			h.lead = `Two-point try: ${p.b ? `${n(p.a)} → ${n(p.b)}` : `${n(p.a)} run`}`;
			h.outcome = p.kind === '2pt_good' ? 'Good' : 'No good';
			h.tone = p.kind === '2pt_good' ? 'good' : 'bad';
			break;
		case 'punt':
		case 'punt_blocked':
			h.glyph = 'punt';
			if (p.kind === 'punt_blocked') {
				h.lead = `${n(p.a)} punt blocked`;
				push(p.d && `by ${n(p.d)}`);
				h.tone = 'bad';
			} else {
				h.lead = `${n(p.a)} punt${p.kick ? `, ${p.kick} yds` : ''}`;
				push(p.detail ?? (p.b ? `${n(p.b)} returns ${yards(p.ret ?? 0)}` : null));
			}
			if (defensiveTd) h.outcome = 'Return TD';
			break;
		case 'kickoff':
		case 'onside':
			h.glyph = 'kickoff';
			if (p.kind === 'onside') {
				h.lead = `${n(p.a)} onside kick`;
				h.outcome = 'Kicking team recovers';
			} else {
				h.lead = `${n(p.a)} kickoff${p.kick ? `, ${p.kick} yds` : ''}`;
				push(p.detail ?? (p.b ? `${n(p.b)} returns ${yards(p.ret ?? 0)}` : null));
			}
			if (td && !defensiveTd) h.outcome = 'Return TD';
			break;
		case 'penalty': {
			h.glyph = 'penalty';
			const pen = p.pen;
			h.lead = pen ? `Flag: ${pen[1]}` : 'Penalty';
			if (pen) push(penaltyWho(pen, n), pen[4] ?? (pen[2] != null ? yards(pen[2]) : null));
			push('no play');
			break;
		}
		default:
			h.lead = playSummary(p.desc);
			h.glyph = /sacked/.test(p.desc)
				? 'sack'
				: /field goal|extra point/.test(p.desc)
					? 'kick'
					: / punts /.test(p.desc)
						? 'punt'
						: / kicks /.test(p.desc)
							? 'kickoff'
							: / pass /.test(p.desc)
								? 'pass'
								: p.type === 'run'
									? 'run'
									: /PENALTY/.test(p.desc)
										? 'penalty'
										: 'other';
	}

	if (p.kind && p.kind !== 'interception' && p.kind !== 'penalty' && p.kind !== 'onside')
		turnoverFacts();
	if (td && !h.outcome) {
		h.outcome = defensiveTd && PASS_KINDS.has(p.kind as PlayKind) ? 'Defensive TD' : 'Touchdown';
		h.tone = defensiveTd ? 'bad' : 'good';
	}
	if (td && h.tone === 'good') h.glyph = 'score';
	if (p.kind === 'fg_made') h.glyph = 'kick';
	if (!p.kind && p.flags.includes('I')) {
		h.glyph = 'turnover';
		h.outcome ??= 'Interception';
		h.tone = 'bad';
	}
	if (!p.kind && p.flags.includes('F')) {
		h.glyph = 'turnover';
		h.outcome ??= 'Fumble lost';
		h.tone = 'bad';
	}
	if (p.pen && p.kind !== 'penalty') {
		const [, type, yds, , status] = p.pen;
		const tail = status ?? (yds != null ? yards(yds) : null);
		h.flag = `Flag: ${type}, ${[penaltyWho(p.pen, n), tail].filter(Boolean).join(', ')}`;
	}
	return h;
}

function penaltyWho(pen: PlayPenalty, n: (s: string | null) => string): string {
	const [team, , , player] = pen;
	return [team, player ? n(player) : null].filter(Boolean).join(' ');
}

/** Lowercased text a play-feed search matches against. */
export function searchText(p: Play, h: Headline): string {
	return [h.lead, ...h.facts, h.outcome, h.flag, p.desc, p.a, p.b, p.d, p.fum]
		.filter(Boolean)
		.join(' ')
		.toLowerCase();
}

/** A play worth seeing when skimming: a score, a turnover, a failed fourth down or a swing
 * of 5+ points of win probability. */
export function isKey(p: Play, score: ScoreEvent | null): boolean {
	if (score?.big) return true;
	if (/[IF]/.test(p.flags)) return true;
	if (p.down === 4 && (p.type === 'pass' || p.type === 'run') && !/[1T]/.test(p.flags) && p.kind) {
		if ((p.yds ?? 0) < (p.togo ?? 0)) return true;
	}
	return Math.abs(p.wpa ?? 0) >= 0.05;
}

// ---- Raw descriptions.

// A short, readable line for a play-by-play description: no clock, formation or jersey
// numbers, outcome first ("J.Daniels 52-yd pass to N.Brown for a TD"). Anything unrecognized
// falls back to the cleaned description.
const NAME = String.raw`[A-Z][\w'.-]*(?: (?:Jr\.|Sr\.|II|III|IV|St\. [A-Z][a-z]+|[A-Z][a-z]+))?`;
export function playSummary(desc: string): string {
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
	if ((m = re(`(${NAME}) extra point is (GOOD|No Good|BLOCKED|Aborted)`)))
		return `${m[1]} extra point ${m[2] === 'GOOD' ? 'good' : m[2].toLowerCase()}`;
	if (/^TWO-POINT CONVERSION ATTEMPT/.test(s))
		return `Two-point try ${/ATTEMPT SUCCEEDS/.test(s) ? 'good' : 'no good'}`;
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
	if ((m = re(`(${NAME}) pass incomplete(?: [a-z]+ [a-z]+)?(?: to (${NAME}))?`)))
		return `${m[1]} incomplete${m[2] ? ` to ${m[2].replace(/\.$/, '')}` : ''}`;
	if (
		/FUMBLES/.test(s) &&
		(m = re(`(${NAME})\\s.*?FUMBLES.*?RECOVERED by (?:[A-Z]{2,3}-)?(${NAME})`))
	)
		return `${m[1]} fumbles, recovered by ${m[2]}${td}${safety}`;
	if ((m = re(`(${NAME}) sacked`)))
		return `${m[1]} sacked${/FUMBLES/.test(s) ? ', fumble' : ''}${td}${safety}`;
	if ((m = re(`(${NAME}) punts (\\d+) yards?`)))
		return `${m[1]} ${m[2]}-yd punt${td ? ', returned for a TD' : ''}`;
	if ((m = re(`(${NAME}) kicks (?:onside )?(\\d+) yards?`)))
		return `${m[1]} ${m[2]}-yd kickoff${td ? ', returned for a TD' : ''}`;
	if ((m = re(`(${NAME}) kneels`))) return `${m[1]} kneels`;
	if ((m = re(`(${NAME}) spiked the ball`))) return `${m[1]} spikes it`;
	if ((m = re(`(${NAME}) (?:scrambles )?(?:left|right|up)\\b.*? for (-?\\d+) yards?`)))
		return `${m[1]} ${m[2]}-yd ${/scrambles/.test(s) ? 'scramble' : 'run'}${td}${safety}`;
	if (
		/^PENALTY on/.test(s) &&
		(m = desc.match(/PENALTY on ([A-Z]{2,3})\b[^,]*, ([^,]+), (\d+) yards?/))
	)
		return `Flag on ${m[1]}: ${m[2]}, ${m[3]} yds`;
	return s
		.replace(/\s*The Replay Official.*$/, '')
		.replace(/\s*PENALTY on.*$/, '')
		.replace(/\b(TOUCHDOWN|INTERCEPTED|FUMBLES|RECOVERED|BLOCKED|SAFETY)\b/g, (w) =>
			w.toLowerCase()
		)
		.trim();
}
