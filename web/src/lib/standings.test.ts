import { describe, expect, it } from 'vitest';
import {
	kickoffLabel,
	lastGame,
	nextGame,
	pythagWins,
	records,
	resultsWeek,
	upset
} from './standings';
import type { ScheduleGame } from './types';

function g(
	week: number,
	away: string,
	home: string,
	score: [number, number] | null,
	vegas: number | null = null,
	day = `2026-09-${String(10 + week * 7).padStart(2, '0')}`
): ScheduleGame {
	return {
		game_id: `2026_${String(week).padStart(2, '0')}_${away}_${home}`,
		season: 2026,
		game_type: 'REG',
		week,
		gameday: day,
		gametime: '13:00',
		away,
		home,
		away_score: score ? score[0] : null,
		home_score: score ? score[1] : null,
		result: score ? score[1] - score[0] : null,
		vegas,
		roof: null,
		stadium: null,
		neutral: false,
		away_coach: null,
		home_coach: null,
		referee: null
	};
}

const season = [
	g(1, 'DET', 'GB', [24, 20], 3),
	g(1, 'CHI', 'MIN', [17, 17], -1),
	g(2, 'GB', 'CHI', [10, 31], 2),
	g(2, 'MIN', 'DET', [21, 14]),
	g(3, 'DET', 'CHI', [27, 3], null, '2026-10-01'),
	g(3, 'GB', 'MIN', null),
	g(4, 'MIN', 'GB', null)
];

describe('records', () => {
	it('counts ties as half a win and sums points', () => {
		const r = records(season);
		expect(r.get('DET')).toMatchObject({ games: 3, wins: 2, pf: 65, pa: 44 });
		expect(r.get('MIN')).toMatchObject({ games: 2, wins: 1.5 });
		expect(r.has('GB')).toBe(true);
	});
	it('pythagorean wins match the 2.37 exponent', () => {
		// 30 for, 20 against over 2 games: 2 * 30^2.37 / (30^2.37 + 20^2.37)
		expect(pythagWins(30, 20, 2)).toBeCloseTo(2 * (1 / (1 + (20 / 30) ** 2.37)), 6);
		expect(pythagWins(0, 0, 4)).toBe(2);
	});
});

describe('results and next games', () => {
	it('leads with the last fully played week while the season is on', () => {
		const status = { season: 2026, reg_games: 5, last_week: 2, complete: false };
		const res = resultsWeek(season, status)!;
		expect(res.week).toBe(2);
		expect(res.games.map((x) => x.home)).toEqual(['CHI', 'DET']);
		expect(resultsWeek(season, { ...status, complete: true })!.week).toBe(3);
	});
	it('finds a team’s last and next game', () => {
		expect(lastGame(season, 'DET')!.week).toBe(3);
		expect(nextGame(season, 'GB')!.week).toBe(3);
		expect(nextGame(season, 'DET')).toBeUndefined();
	});
	it('an upset is the Vegas underdog winning', () => {
		expect(upset(season[0])).toBe(true); // GB favored by 3, DET won
		expect(upset(season[2])).toBe(false); // CHI favored and won
		expect(upset(season[1])).toBe(false); // tie
	});
	it('formats kickoffs in 12-hour time', () => {
		expect(kickoffLabel('2026-10-04', '13:00')).toBe('Sun 1:00 PM');
		expect(kickoffLabel('2026-10-05', '20:15')).toBe('Mon 8:15 PM');
		expect(kickoffLabel('2026-10-04', '09:30')).toBe('Sun 9:30 AM');
	});
});
