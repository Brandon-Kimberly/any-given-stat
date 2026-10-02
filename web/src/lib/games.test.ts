import { describe, expect, it } from 'vitest';
import { elapsedAt, excitement, excitementPercentile, sparkPath, winnerLow, wpAt } from './games';
import type { GameDetail } from './types';

const game = (wp: [number, number][], home = 24, away = 17): GameDetail => ({
	game_id: '2025_01_AAA_BBB',
	season: 2025,
	week: 1,
	season_type: 'REG',
	home: 'BBB',
	away: 'AAA',
	home_score: home,
	away_score: away,
	gameday: null,
	wp,
	top_plays: [],
	box: { home: null, away: null }
});

describe('games', () => {
	it('excitement sums absolute win-probability moves', () => {
		expect(
			excitement(
				game([
					[0, 0.5],
					[60, 0.8],
					[120, 0.3],
					[3600, 1]
				])
			)
		).toBeCloseTo(0.3 + 0.5 + 0.7);
	});

	it('winnerLow is the eventual winner’s worst moment', () => {
		expect(
			winnerLow(
				game([
					[0, 0.5],
					[100, 0.1],
					[3600, 1]
				])
			)
		).toBeCloseTo(0.1);
		expect(
			winnerLow(
				game(
					[
						[0, 0.5],
						[100, 0.9],
						[3600, 0]
					],
					10,
					20
				)
			)
		).toBeCloseTo(0.1);
		expect(winnerLow(game([[0, 0.5]], 20, 20))).toBeNull();
	});

	it('elapsedAt converts quarter + clock, including overtime', () => {
		expect(elapsedAt(1, '15:00')).toBe(0);
		expect(elapsedAt(2, '02:07')).toBe(900 + 900 - 127);
		expect(elapsedAt(5, '10:00')).toBe(3600);
		expect(elapsedAt(3, null)).toBeNull();
	});

	it('wpAt returns the last value at or before a time', () => {
		const g = game([
			[0, 0.5],
			[100, 0.6],
			[200, 0.7]
		]);
		expect(wpAt(g, 150)).toBe(0.6);
		expect(wpAt(g, 200)).toBe(0.7);
	});

	it('excitement percentile is monotone and bounded', () => {
		expect(excitementPercentile(0)).toBe(0);
		expect(excitementPercentile(3.73)).toBeCloseTo(0.5, 1);
		expect(excitementPercentile(50)).toBe(1);
		expect(excitementPercentile(5)).toBeGreaterThan(excitementPercentile(4));
	});

	it('sparkPath spans the box', () => {
		expect(
			sparkPath(
				game([
					[0, 1],
					[3600, 0]
				]),
				100,
				20
			)
		).toBe('M0.0,0.0L100.0,20.0');
	});
});
