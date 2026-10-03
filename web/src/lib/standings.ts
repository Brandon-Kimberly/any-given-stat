// Records, results and next games from schedule/<season>.json: what the home page and the
// favorite-team card need without loading the full game files.
import type { ScheduleGame, SeasonStatus } from './types';

/** Same exponent as the pipeline's luck dataset (config.PYTHAG_EXPONENT). */
export const PYTHAG_EXPONENT = 2.37;

export interface TeamRecord {
	team: string;
	games: number;
	/** Ties count half. */
	wins: number;
	pf: number;
	pa: number;
	/** Wins point differential predicts (Pythagorean), over the same games. */
	pythag: number;
}

export const played = (g: ScheduleGame): boolean => g.home_score != null && g.away_score != null;

export function pythagWins(pf: number, pa: number, games: number): number {
	if (!games || pf + pa === 0) return games / 2;
	const a = pf ** PYTHAG_EXPONENT;
	return (games * a) / (a + pa ** PYTHAG_EXPONENT);
}

/** Regular-season records for every team that has played. */
export function records(games: ScheduleGame[]): Map<string, TeamRecord> {
	const out = new Map<string, TeamRecord>();
	const side = (team: string, pf: number, pa: number) => {
		const r = out.get(team) ?? { team, games: 0, wins: 0, pf: 0, pa: 0, pythag: 0 };
		r.games += 1;
		r.wins += pf > pa ? 1 : pf === pa ? 0.5 : 0;
		r.pf += pf;
		r.pa += pa;
		out.set(team, r);
	};
	for (const g of games) {
		if (g.game_type !== 'REG' || !played(g)) continue;
		side(g.home, g.home_score!, g.away_score!);
		side(g.away, g.away_score!, g.home_score!);
	}
	for (const r of out.values()) r.pythag = pythagWins(r.pf, r.pa, r.games);
	return out;
}

const kickoff = (g: ScheduleGame) => `${g.gameday} ${g.gametime ?? ''}`;

/** A team's most recent played game, any game type. */
export function lastGame(games: ScheduleGame[], team: string): ScheduleGame | undefined {
	return games
		.filter((g) => played(g) && (g.home === team || g.away === team))
		.sort((a, b) => kickoff(b).localeCompare(kickoff(a)))[0];
}

/** A team's next unplayed game. */
export function nextGame(games: ScheduleGame[], team: string): ScheduleGame | undefined {
	return games
		.filter((g) => !played(g) && (g.home === team || g.away === team))
		.sort((a, b) => kickoff(a).localeCompare(kickoff(b)))[0];
}

/** The week whose results lead the page: the last fully played regular-season week while the
 * regular season is on (a lone Thursday game doesn't make a week), else the last week with any
 * final (the playoff round so far, or the Super Bowl once the season is over). */
export function resultsWeek(
	games: ScheduleGame[],
	status?: SeasonStatus | null
): { week: number; games: ScheduleGame[] } | null {
	const finals = games.filter(played);
	if (!finals.length) return null;
	const postseason = finals.some((g) => g.game_type !== 'REG');
	const week =
		status && !status.complete && status.last_week > 0 && !postseason
			? status.last_week
			: Math.max(...finals.map((g) => g.week));
	return {
		week,
		games: finals
			.filter((g) => g.week === week)
			.sort((a, b) => kickoff(a).localeCompare(kickoff(b)))
	};
}

/** Did the Vegas underdog win? (vegas > 0 = home favored; a pick'em or tie is no upset.) */
export function upset(g: ScheduleGame): boolean {
	if (!played(g) || g.vegas == null || g.vegas === 0 || g.result == null || g.result === 0)
		return false;
	return Math.sign(g.vegas) !== Math.sign(g.result);
}

/** Week label: playoff rounds by name. */
export function weekLabel(g: Pick<ScheduleGame, 'game_type' | 'week'>): string {
	const rounds: Record<string, string> = {
		WC: 'Wild Card',
		DIV: 'Divisional',
		CON: 'Conference',
		SB: 'Super Bowl'
	};
	return rounds[g.game_type] ?? `Week ${g.week}`;
}

/** "Sun 1:00 PM" from a gameday + "HH:MM" local kickoff (nflverse times are US Eastern). */
export function kickoffLabel(gameday: string, gametime?: string | null): string {
	const d = new Date(`${gameday}T12:00:00`);
	const day = d.toLocaleDateString('en-US', { weekday: 'short' });
	if (!gametime) return day;
	const [h, m] = gametime.split(':').map(Number);
	const h12 = ((h + 11) % 12) + 1;
	return `${day} ${h12}:${String(m).padStart(2, '0')} ${h < 12 ? 'AM' : 'PM'}`;
}
