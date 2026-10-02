import { describe, expect, it } from 'vitest';
import { calibration, oddsPct, skillByWeek } from './odds';
import type { PlayoffOdds, PlayoffOddsRow } from './types';

const row = (team: string, week: number, p: number): PlayoffOddsRow => ({
	team,
	week,
	mean_wins: 8,
	wins_p10: 6,
	wins_p90: 10,
	p_playoffs: p,
	p_division: 0,
	p_bye: 0,
	p_conf: 0,
	p_sb: 0,
	mean_seed_if_in: null
});
const out = (made: boolean) => ({ made_playoffs: made, won_division: false, sb_winner: false });

const season: PlayoffOdds = {
	season: 2020,
	sims: 100,
	seeds: 7,
	byes: 1,
	weeks: [0],
	rows: [row('A', 0, 0.8), row('B', 0, 0.85), row('C', 0, 0.2), row('D', 0, 0.1)],
	actual: { A: out(true), B: out(false), C: out(false), D: out(false) }
};

describe('calibration', () => {
	it('bins forecasts and reports the realized rate', () => {
		const bins = calibration([season], 0);
		const high = bins.find((b) => b.lo === 0.8)!;
		expect(high.n).toBe(2);
		expect(high.predicted).toBeCloseTo(0.825);
		expect(high.actual).toBe(0.5);
	});
	it('ignores seasons without outcomes', () => {
		expect(calibration([{ ...season, actual: null }], 0)).toEqual([]);
	});
});

describe('skillByWeek', () => {
	it('compares the Brier score with always forecasting the base rate', () => {
		const [p] = skillByWeek([season]);
		// Forecast: (0.2² + 0.85² + 0.2² + 0.1²) / 4; base rate 0.25: (0.75² + 3·0.25²) / 4.
		expect(p.brier).toBeCloseTo((0.04 + 0.7225 + 0.04 + 0.01) / 4);
		expect(p.baseline).toBeCloseTo((0.5625 + 3 * 0.0625) / 4);
		expect(p.skill).toBeCloseTo(1 - p.brier / p.baseline);
	});
});

describe('oddsPct', () => {
	it('marks certainties and rounds the rest', () => {
		expect([1, 0, 0.004, 0.996, 0.734].map(oddsPct)).toEqual(['✓', '–', '<1%', '>99%', '73%']);
	});
});
