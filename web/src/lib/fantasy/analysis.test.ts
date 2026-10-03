import { describe, expect, it } from 'vitest';
import { pointsAllowed, scoreSeason, startersByPosition, type Lineup } from './analysis';
import { PRESETS } from './scoring';
import type { FantasySeason } from './statline';

// Two weeks, two games each week. Standard scoring: rush/rec yards 0.1, TDs 6.
const fs: FantasySeason = {
	season: 2024,
	players: {
		R1: ['Run One', 'RB'],
		R2: ['Run Two', 'RB'],
		R3: ['Run Three', 'RB'],
		W1: ['Wide One', 'WR'],
		W2: ['Wide Two', 'WR']
	},
	games: {
		g1: [1, 'REG', 'AAA', 'BBB'],
		g2: [1, 'REG', 'CCC', 'DDD'],
		g3: [2, 'REG', 'AAA', 'CCC'],
		p1: [19, 'POST', 'AAA', 'BBB']
	},
	lines: [
		['g1', 'R1', 'AAA', { rush_yd: 100, rush_td: 1 }], // 16
		['g1', 'W1', 'BBB', { rec_yd: 80 }], // 8
		['g2', 'R2', 'CCC', { rush_yd: 50 }], // 5
		['g2', 'R3', 'DDD', { rush_yd: 20 }], // 2
		['g2', 'W2', 'CCC', { rec_yd: 30 }], // 3
		['g3', 'R1', 'AAA', { rush_yd: 40 }], // 4
		['g3', 'R2', 'CCC', { rush_yd: 90 }], // 9
		['g3', 'W1', 'AAA', { rec_yd: 120, rec_td: 1 }], // 18 (traded to AAA)
		['p1', 'R1', 'AAA', { rush_yd: 200 }] // playoffs: scored per game, not in season totals
	]
};
const lineup: Lineup = { teams: 1, starters: { RB: 1, WR: 1 } };

describe('scoreSeason', () => {
	const r = scoreSeason(fs, PRESETS.standard, lineup);
	const p = (id: string) => r.players.find((x) => x.id === id)!;

	it('totals the regular season only, with weekly points and latest team', () => {
		expect(p('R1')).toMatchObject({ points: 20, games: 2, ppg: 10, weeks: [16, 4], best: 16 });
		expect(p('W1')).toMatchObject({ points: 26, team: 'AAA', weeks: [8, 18] });
		expect(r.byGame.get('p1')?.get('R1')).toBe(20);
		expect(r.weeksPlayed).toBe(2);
	});

	it('ranks within position and counts starter weeks', () => {
		// RB totals: R1 20, R2 14, R3 2. One RB starter: week 1 R1 (16), week 2 R2 (9).
		expect([p('R1').posRank, p('R2').posRank, p('R3').posRank]).toEqual([1, 2, 3]);
		expect(p('R1').starterRate).toBe(0.5);
		expect(p('R2').starterRate).toBe(0.5);
		expect(p('R3').starterRate).toBe(0);
	});

	it('values players over replacement (mean ppg of the next three after the starters)', () => {
		// RB replacement = mean(R2 7, R3 2) = 4.5 ppg; R1: 20 - 4.5 * 2 = 11.
		expect(r.replacement.RB).toBe(4.5);
		expect(p('R1').vor).toBe(11);
		expect(p('R1').vorPerGame).toBe(5.5);
		// WR replacement = W2 3 ppg; W1: 26 - 3 * 2 = 20.
		expect(p('W1').vor).toBe(20);
	});
});

describe('startersByPosition', () => {
	it('gives each flex slot to the best remaining eligible player', () => {
		const n = startersByPosition(
			{ teams: 2, starters: { RB: 1, WR: 1, FLEX: 1 } },
			{ RB: [30, 25, 20], WR: [28, 22, 10], TE: [12] }
		);
		// Dedicated: RB 2, WR 2. Flex picks: next RB 20 vs next WR 10 vs TE 12 -> RB; then
		// RB (none left) vs WR 10 vs TE 12 -> TE.
		expect(n).toMatchObject({ RB: 3, WR: 2, TE: 1 });
	});
});

describe('pointsAllowed', () => {
	it('averages points allowed per game to each position, ranked most-allowed first', () => {
		const r = scoreSeason(fs, PRESETS.standard, lineup);
		const pa = pointsAllowed(fs, r);
		const ccc = pa.find((x) => x.team === 'CCC')!;
		// CCC faced DDD in g2 (R3 2 RB) and AAA in g3 (R1 4 RB, W1 18 WR): 2 games.
		expect(ccc.perGame.RB).toBe(3);
		expect(ccc.perGame.WR).toBe(9);
		const bbb = pa.find((x) => x.team === 'BBB')!;
		expect(bbb.perGame.RB).toBe(16);
		expect(bbb.rank.RB).toBe(1);
	});
});
