import { loadPath } from './data';
import type { GameDetail, GameIndexEntry, GamePlays } from './types';

/** All games (REG + POST) of a season, from the per-season file. */
export function loadSeasonGames(season: number): Promise<GameDetail[]> {
	return loadPath<GameDetail[]>(`games/games_${season}`);
}

/** Full play-by-play and drives for one game. */
export function loadGamePlays(gameId: string): Promise<GamePlays> {
	return loadPath<GamePlays>(`games/${seasonFromGameId(gameId)}/${gameId}`);
}

export function seasonFromGameId(id: string): number {
	return Number(id.slice(0, 4));
}

/** Excitement index at every 5th percentile (0, 5, ..., 100) over 2,761 games, 2016–2025. */
const EXCITEMENT_QUANTILES = [
	0.75, 1.54, 1.84, 2.11, 2.35, 2.59, 2.85, 3.07, 3.31, 3.53, 3.73, 3.94, 4.15, 4.36, 4.59, 4.86,
	5.09, 5.39, 5.78, 6.38, 10.58
];

/** Share of 2016–2025 games less exciting than this value (0..1). */
export function excitementPercentile(x: number): number {
	const q = EXCITEMENT_QUANTILES;
	if (x <= q[0]) return 0;
	for (let i = 1; i < q.length; i++) {
		if (x <= q[i]) return (i - 1 + (x - q[i - 1]) / (q[i] - q[i - 1] || 1)) / (q.length - 1);
	}
	return 1;
}

/** Total win-probability movement over the game: a standard "excitement index". */
export function excitement(g: GameDetail): number {
	let total = 0;
	for (let i = 1; i < g.wp.length; i++) total += Math.abs(g.wp[i][1] - g.wp[i - 1][1]);
	return total;
}

/** Lowest win probability the eventual winner had (comebacks have small values). */
export function winnerLow(g: GameDetail): number | null {
	if (g.home_score == null || g.away_score == null || g.home_score === g.away_score) return null;
	const homeWon = g.home_score > g.away_score;
	let low = 1;
	for (const [, wp] of g.wp) low = Math.min(low, homeWon ? wp : 1 - wp);
	return low;
}

/** Seconds elapsed for a play given its quarter and "MM:SS" clock (OT: 10-minute periods). */
export function elapsedAt(qtr: number, clock: string | null): number | null {
	if (!clock) return null;
	const [m, s] = clock.split(':').map(Number);
	if (!Number.isFinite(m) || !Number.isFinite(s)) return null;
	const left = m * 60 + s;
	return qtr <= 4 ? (qtr - 1) * 900 + (900 - left) : 3600 + (qtr - 5) * 600 + (600 - left);
}

/** Home win probability at (or just before) an elapsed time. */
export function wpAt(g: GameDetail, t: number): number {
	let last = g.wp[0]?.[1] ?? 0.5;
	for (const [e, wp] of g.wp) {
		if (e > t) break;
		last = wp;
	}
	return last;
}

/** SVG path for a small win-probability sparkline in a w x h box (home WP up). */
export function sparkPath(g: GameDetail, w: number, h: number): string {
	if (!g.wp.length) return '';
	const end = Math.max(3600, g.wp[g.wp.length - 1][0]);
	return g.wp
		.map(
			([e, wp], i) => `${i ? 'L' : 'M'}${((e / end) * w).toFixed(1)},${((1 - wp) * h).toFixed(1)}`
		)
		.join('');
}

export type { GameDetail, GameIndexEntry };
