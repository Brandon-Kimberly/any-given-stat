import { describe, expect, it } from 'vitest';
import { ratingsWeek } from './season';

const status = (last_week: number, complete = false) => ({
	season: 2026,
	reg_games: 49,
	last_week,
	complete
});

describe('ratingsWeek', () => {
	it('ignores a partial week (a lone Thursday game) in a season in progress', () => {
		expect(ratingsWeek([1, 2, 3, 4], status(3))).toBe(3);
	});
	it('uses the latest week of a complete season', () => {
		expect(ratingsWeek([1, 2, 18], status(18, true))).toBe(18);
	});
	it('falls back sensibly', () => {
		expect(ratingsWeek([], status(3))).toBe(0);
		expect(ratingsWeek([5, 6], status(3))).toBe(5);
		expect(ratingsWeek([2, 1], null)).toBe(2);
	});
});
