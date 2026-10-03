// Season-level fantasy analysis from a season's stat lines and one scoring: totals, weekly
// points, how often a player gave a starter-quality week, value over replacement, and
// fantasy points allowed by each defense. Pure functions; pages memoize per scoring.

import { scoreLine, scoringKey, type Scoring } from './scoring';
import type { FantasyPos, FantasySeason } from './statline';

/** Positions a fantasy page ranks (IDP only when the league starts them). */
export const OFFENSE: FantasyPos[] = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];
export const IDP: FantasyPos[] = ['DL', 'LB', 'DB'];

/** A typical 12-team league (1 QB, 2 RB, 2 WR, 1 TE, 1 FLEX, K, DEF) when none is connected. */
export const DEFAULT_LINEUP: Lineup = {
	teams: 12,
	starters: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DEF: 1 }
};

export interface Lineup {
	teams: number;
	/** Normalized slot counts (QB RB WR TE FLEX SUPER_FLEX K DEF DL LB DB IDP_FLEX, BN). */
	starters: Record<string, number>;
}

/** Which positions each flexible slot accepts. */
const FLEX_SLOTS: Record<string, FantasyPos[]> = {
	FLEX: ['RB', 'WR', 'TE'],
	SUPER_FLEX: ['QB', 'RB', 'WR', 'TE'],
	IDP_FLEX: ['DL', 'LB', 'DB']
};

export interface PlayerSeason {
	id: string;
	name: string;
	pos: FantasyPos;
	/** Team in the player's most recent game. */
	team: string;
	games: number;
	points: number;
	ppg: number;
	/** Points by regular-season week (index = week − 1); null = didn't play. */
	weeks: (number | null)[];
	/** Standard deviation of game scores. */
	sd: number;
	best: number;
	/** Share of games finishing inside the league's starters at the position that week. */
	starterRate: number;
	/** Season rank at the position by total points (1 = best). */
	posRank: number;
	/** Points above a replacement-level player over the same games. */
	vor: number;
	vorPerGame: number;
}

export interface SeasonResult {
	season: number;
	players: PlayerSeason[];
	/** Replacement-level points per game, by position. */
	replacement: Partial<Record<FantasyPos, number>>;
	/** Weekly starters at each position across the league (teams × slots, flex shared out). */
	starters: Partial<Record<FantasyPos, number>>;
	/** Points per game in game id → player id → points (regular season and playoffs). */
	byGame: Map<string, Map<string, number>>;
	weeksPlayed: number;
}

const round1 = (x: number) => Math.round(x * 10) / 10;

/** Starters per position: dedicated slots × teams, then each flex slot shared among its
 * eligible positions by who'd actually fill it (the best remaining players by points). */
export function startersByPosition(
	lineup: Lineup,
	pointsByPos: Partial<Record<FantasyPos, number[]>>
): Partial<Record<FantasyPos, number>> {
	const n: Partial<Record<FantasyPos, number>> = {};
	for (const pos of [...OFFENSE, ...IDP]) {
		n[pos] = (lineup.starters[pos] ?? 0) * lineup.teams;
	}
	for (const [slot, eligible] of Object.entries(FLEX_SLOTS)) {
		const count = (lineup.starters[slot] ?? 0) * lineup.teams;
		for (let i = 0; i < count; i++) {
			let pick: FantasyPos | null = null;
			let best = -Infinity;
			for (const pos of eligible) {
				const next = pointsByPos[pos]?.[n[pos] ?? 0];
				if (next != null && next > best) {
					best = next;
					pick = pos;
				}
			}
			if (!pick) break;
			n[pick] = (n[pick] ?? 0) + 1;
		}
	}
	return n;
}

/** Score every line of a season and summarize the regular season per player. */
export function scoreSeason(
	fs: FantasySeason,
	scoring: Scoring,
	lineup: Lineup = DEFAULT_LINEUP
): SeasonResult {
	const byGame = new Map<string, Map<string, number>>();
	type Acc = {
		pts: number;
		weeks: (number | null)[];
		scores: number[];
		team: string;
		last: number;
	};
	const acc = new Map<string, Acc>();
	// Weekly scores by position, for "starter week" ranks.
	const weekly = new Map<string, { id: string; pts: number }[]>();
	let weeksPlayed = 0;
	for (const [gid, pid, team, line] of fs.lines) {
		const g = fs.games[gid];
		const meta = fs.players[pid];
		if (!g || !meta) continue;
		const pos = meta[1];
		const pts = scoreLine(line, pos, scoring);
		let gm = byGame.get(gid);
		if (!gm) byGame.set(gid, (gm = new Map()));
		gm.set(pid, pts);
		const [week, type] = g;
		if (type !== 'REG') continue;
		weeksPlayed = Math.max(weeksPlayed, week);
		let a = acc.get(pid);
		if (!a) acc.set(pid, (a = { pts: 0, weeks: [], scores: [], team, last: 0 }));
		a.pts += pts;
		a.weeks[week - 1] = pts;
		a.scores.push(pts);
		if (week >= a.last) {
			a.last = week;
			a.team = team;
		}
		const key = `${week}|${pos}`;
		let w = weekly.get(key);
		if (!w) weekly.set(key, (w = []));
		w.push({ id: pid, pts });
	}

	// Season totals ranked within position, to size each position's starters.
	const rows: PlayerSeason[] = [];
	for (const [id, a] of acc) {
		const [name, pos] = fs.players[id];
		const n = a.scores.length;
		const ppg = a.pts / n;
		const sd = Math.sqrt(a.scores.reduce((s, x) => s + (x - ppg) ** 2, 0) / Math.max(1, n - 1));
		const weeks = Array.from({ length: weeksPlayed }, (_, i) => a.weeks[i] ?? null);
		rows.push({
			id,
			name,
			pos,
			team: a.team,
			games: n,
			points: round1(a.pts),
			ppg: round1(ppg),
			weeks,
			sd: round1(sd),
			best: Math.max(...a.scores),
			starterRate: 0,
			posRank: 0,
			vor: 0,
			vorPerGame: 0
		});
	}
	const byPos = new Map<FantasyPos, PlayerSeason[]>();
	for (const r of rows) {
		let list = byPos.get(r.pos);
		if (!list) byPos.set(r.pos, (list = []));
		list.push(r);
	}
	const pointsByPos: Partial<Record<FantasyPos, number[]>> = {};
	for (const [pos, list] of byPos) {
		list.sort((a, b) => b.points - a.points);
		list.forEach((r, i) => (r.posRank = i + 1));
		pointsByPos[pos] = list.map((r) => r.points);
	}
	const starters = startersByPosition(lineup, pointsByPos);

	// Starter weeks: finished inside the position's weekly starter count.
	const startWeeks = new Map<string, number>();
	for (const [key, list] of weekly) {
		const pos = key.split('|')[1] as FantasyPos;
		const cut = starters[pos] ?? 0;
		if (!cut) continue;
		list.sort((a, b) => b.pts - a.pts);
		for (const { id } of list.slice(0, cut)) startWeeks.set(id, (startWeeks.get(id) ?? 0) + 1);
	}

	// Replacement level: the points per game of the next three players after the starters.
	const replacement: Partial<Record<FantasyPos, number>> = {};
	for (const [pos, list] of byPos) {
		const cut = starters[pos] ?? 0;
		if (!cut) continue;
		const next = list.slice(cut, cut + 3);
		if (!next.length) continue;
		replacement[pos] = next.reduce((s, r) => s + r.points / r.games, 0) / next.length;
	}
	for (const r of rows) {
		r.starterRate = (startWeeks.get(r.id) ?? 0) / r.games;
		const rep = replacement[r.pos];
		if (rep != null) {
			r.vor = round1(r.points - rep * r.games);
			r.vorPerGame = round1(r.ppg - rep);
		}
	}
	rows.sort((a, b) => b.points - a.points);
	return { season: fs.season, players: rows, replacement, starters, byGame, weeksPlayed };
}

export interface PointsAllowed {
	team: string;
	games: number;
	/** Average fantasy points per game allowed to each position's players combined. */
	perGame: Partial<Record<FantasyPos, number>>;
	/** Rank among defenses (1 = allows the most = best matchup). */
	rank: Partial<Record<FantasyPos, number>>;
}

/** Fantasy points each defense allowed per game to opposing QBs, RBs, WRs, TEs and Ks. */
export function pointsAllowed(fs: FantasySeason, result: SeasonResult): PointsAllowed[] {
	const positions: FantasyPos[] = ['QB', 'RB', 'WR', 'TE', 'K'];
	const sums = new Map<string, { games: Set<string>; pts: Partial<Record<FantasyPos, number>> }>();
	for (const [gid, pid, team] of fs.lines) {
		const g = fs.games[gid];
		const pos = fs.players[pid]?.[1];
		if (!g || g[1] !== 'REG' || !pos || !positions.includes(pos)) continue;
		const defense = team === g[2] ? g[3] : g[2];
		let s = sums.get(defense);
		if (!s) sums.set(defense, (s = { games: new Set(), pts: {} }));
		s.games.add(gid);
		s.pts[pos] = (s.pts[pos] ?? 0) + (result.byGame.get(gid)?.get(pid) ?? 0);
	}
	const out: PointsAllowed[] = [...sums].map(([team, s]) => {
		const perGame: Partial<Record<FantasyPos, number>> = {};
		for (const p of positions) perGame[p] = round1((s.pts[p] ?? 0) / s.games.size);
		return { team, games: s.games.size, perGame, rank: {} };
	});
	for (const p of positions) {
		const sorted = [...out].sort((a, b) => (b.perGame[p] ?? 0) - (a.perGame[p] ?? 0));
		sorted.forEach((r, i) => (r.rank[p] = i + 1));
	}
	return out.sort((a, b) => a.team.localeCompare(b.team));
}

// ---------- memoization ----------

const memo = new WeakMap<FantasySeason, Map<string, SeasonResult>>();

/** scoreSeason, cached per season file, scoring rules and lineup. */
export function scored(fs: FantasySeason, scoring: Scoring, lineup: Lineup = DEFAULT_LINEUP) {
	let m = memo.get(fs);
	if (!m) memo.set(fs, (m = new Map()));
	const key = `${scoringKey(scoring)}#${lineup.teams}:${JSON.stringify(lineup.starters)}`;
	let r = m.get(key);
	if (!r) m.set(key, (r = scoreSeason(fs, scoring, lineup)));
	return r;
}

/** Does this lineup start individual defensive players? */
export const startsIdp = (lineup: Lineup) =>
	['DL', 'LB', 'DB', 'IDP_FLEX'].some((s) => (lineup.starters[s] ?? 0) > 0);
