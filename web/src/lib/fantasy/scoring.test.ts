import { describe, expect, it } from 'vitest';
import espnLeague from './fixtures/espn_league.json';
import {
	PRESETS,
	breakdown,
	round2,
	scoreLine,
	scoringKey,
	unsupported,
	type EspnScoringItem,
	type Scoring
} from './scoring';
import type { FantasyPos, StatLine } from './statline';

const sleeper = (settings: Record<string, number>): Scoring => ({
	platform: 'sleeper',
	label: 'test',
	sleeper: settings
});
const espn = (items: EspnScoringItem[]): Scoring => ({
	platform: 'espn',
	label: 'test',
	espn: items
});
const espnFixture = espn(espnLeague.settings.scoringSettings.scoringItems);

/** breakdown must add up to scoreLine exactly (to the cent). */
function expectConsistent(line: StatLine, pos: FantasyPos, s: Scoring): number {
	const total = scoreLine(line, pos, s);
	const parts = breakdown(line, pos, s);
	expect(round2(parts.reduce((a, p) => a + p.points, 0))).toBe(total);
	return total;
}

const QB: StatLine = {
	pass_att: 35,
	pass_cmp: 24,
	pass_inc: 11,
	pass_yd: 312,
	pass_td: 2,
	pass_td_yds: [45, 12],
	pass_int: 1,
	rush_att: 3,
	rush_yd: 14
};

describe('presets', () => {
	it('scores a 24/35, 312-yard, 2 TD, 1 INT QB under PPR', () => {
		// 312 * 0.04 = 12.48, 2 TD * 4 = 8, INT -1, 14 rush yd * 0.1 = 1.4
		expect(expectConsistent(QB, 'QB', PRESETS.ppr)).toBe(20.88);
		expect(breakdown(QB, 'QB', PRESETS.ppr)).toEqual([
			{ label: 'Passing yards', stat: 312, points: 12.48 },
			{ label: 'Passing TDs', stat: 2, points: 8 },
			{ label: 'Rushing yards', stat: 14, points: 1.4 },
			{ label: 'Interceptions thrown', stat: 1, points: -1 }
		]);
	});

	it('differs by reception value only', () => {
		const wr: StatLine = { rec_tgt: 9, rec: 7, rec_yd: 88, rec_td: 1 };
		expect(scoreLine(wr, 'WR', PRESETS.ppr)).toBe(21.8);
		expect(scoreLine(wr, 'WR', PRESETS.half)).toBe(18.3);
		expect(scoreLine(wr, 'WR', PRESETS.standard)).toBe(14.8);
	});

	it('scores a team defense and keeps offensive and defensive keys apart', () => {
		const def: StatLine = {
			sack: 3,
			def_int: 2,
			def_fum_rec: 1,
			def_ff: 1,
			def_td: 1,
			st_td: 1,
			pts_allow: 17,
			yds_allow: 310,
			kr_yd: 120
		};
		// 3 sacks + 2 INT * 2 + FR 2 + FF 1 + def TD 6 + ST TD 6 (once) + 14-20 allowed 1
		expect(expectConsistent(def, 'DEF', PRESETS.half)).toBe(23);
		// Offensive stats on a DEF line and DEF stats on a player line score nothing.
		expect(scoreLine({ pass_yd: 300, rec: 5 }, 'DEF', PRESETS.ppr)).toBe(10); // 0 allowed
		expect(scoreLine({ sack: 2, def_int: 1, rec: 1 }, 'WR', PRESETS.ppr)).toBe(1);
		// A shutout: pts_allow is omitted when zero.
		expect(scoreLine({}, 'DEF', PRESETS.ppr)).toBe(10);
	});

	it('scores a kicker by distance', () => {
		const k: StatLine = {
			fga: 5,
			fgm: 4,
			fgmiss: 1,
			fgm_dists: [23, 38, 47, 52],
			fgmiss_dists: [55],
			xpa: 4,
			xpm: 3,
			xpmiss: 1
		};
		// 3 + 3 + 4 + 5 - 1 miss + 3 PAT - 1 PAT miss
		expect(expectConsistent(k, 'K', PRESETS.standard)).toBe(16);
	});

	it('have no unsupported rules', () => {
		for (const p of Object.values(PRESETS)) expect(unsupported(p)).toEqual([]);
	});
});

describe('Sleeper settings', () => {
	// nflverse's fantasy_points_ppr formula (the pipeline reproduces it on 99.7% of games).
	const nflversePpr = sleeper({
		pass_yd: 0.04,
		pass_td: 4,
		pass_int: -2,
		rush_yd: 0.1,
		rush_td: 6,
		rec_yd: 0.1,
		rec_td: 6,
		rec: 1,
		pass_2pt: 2,
		rush_2pt: 2,
		rec_2pt: 2,
		fum_lost: -2,
		st_td: 6
	});

	it('reproduces the nflverse PPR formula on realistic lines', () => {
		const rb: StatLine = {
			rush_att: 18,
			rush_yd: 87,
			rush_td: 1,
			rush_td_yds: [3],
			rec_tgt: 5,
			rec: 4,
			rec_yd: 31,
			rec_2pt: 1,
			fum: 1,
			fum_lost: 1
		};
		// 8.7 + 6 + 4 + 3.1 + 2 - 2
		expect(expectConsistent(rb, 'RB', nflversePpr)).toBe(21.8);
		// A kick-return TD counts once: st_td already includes kr_td.
		const returner: StatLine = { rec: 6, rec_yd: 74, kr: 3, kr_yd: 140, kr_td: 1, st_td: 1 };
		expect(expectConsistent(returner, 'WR', nflversePpr)).toBe(19.4);
		expect(expectConsistent(QB, 'QB', nflversePpr)).toBe(19.88);
	});

	it('applies TE premium, 100-yard and 40+ yard TD bonuses by position', () => {
		const s = sleeper({
			...PRESETS.ppr.sleeper,
			bonus_rec_te: 0.5,
			bonus_rec_yd_100: 3,
			rec_td_40p: 2
		});
		const line: StatLine = { rec_tgt: 10, rec: 8, rec_yd: 104, rec_td: 1, rec_td_yds: [41] };
		// 8 rec + 4 TE bonus + 10.4 + 6 TD + 3 (100 yd) + 2 (40+ TD)
		expect(expectConsistent(line, 'TE', s)).toBe(33.4);
		expect(scoreLine(line, 'WR', s)).toBe(29.4);
		const parts = breakdown(line, 'TE', s);
		expect(parts.find((p) => p.label === 'TE reception bonus')).toEqual({
			label: 'TE reception bonus',
			stat: 8,
			points: 4
		});
	});

	it('stacks yardage-game bonuses and counts long TDs', () => {
		const s = sleeper({
			bonus_pass_yd_300: 2,
			bonus_pass_yd_400: 3,
			bonus_pass_cmp_25: 1,
			pass_td_40p: 1,
			pass_td_50p: 1,
			bonus_rush_rec_yd_100: 2
		});
		const line: StatLine = { pass_cmp: 25, pass_yd: 420, pass_td_yds: [8, 44, 61], rush_yd: 100 };
		// 2 + 3 + 1 + (2 TDs >= 40) + (1 TD >= 50) + 2
		expect(expectConsistent(line, 'QB', s)).toBe(11);
		expect(scoreLine({ pass_yd: 299, pass_cmp: 24, rush_yd: 99 }, 'QB', s)).toBe(0);
	});

	it('scores position first-down bonuses', () => {
		const s = sleeper({ bonus_fd_qb: 0.5, bonus_fd_rb: 0.5, rush_fd: 0.25 });
		const line: StatLine = { pass_fd: 10, rush_fd: 2, rec_fd: 3 };
		expect(scoreLine(line, 'QB', s)).toBe(6.5); // (10 + 2) * 0.5 + 2 * 0.25
		expect(scoreLine(line, 'RB', s)).toBe(3); // (2 + 3) * 0.5 + 0.5
		expect(scoreLine(line, 'WR', s)).toBe(0.5);
	});

	it('scores kicker distance and yardage keys', () => {
		const s = sleeper({ fgm_yds_over_30: 0.1, fgm_50_59: 5, fgm_60p: 6, fgmiss_0_19: -3 });
		const k: StatLine = { fgm_dists: [38, 47, 52, 61], fgmiss_dists: [19] };
		// over 30: 8 + 17 + 22 + 31 = 78 -> 7.8; 50-59: 5; 60+: 6; short miss -3
		expect(expectConsistent(k, 'K', s)).toBe(15.8);
	});

	it('scores points/yards-allowed buckets and per-unit allowed', () => {
		const s = sleeper({
			pts_allow: -0.1,
			pts_allow_14_20: 1,
			yds_allow_300_349: 2,
			yds_allow_0_100: 5
		});
		expect(scoreLine({ pts_allow: 20, yds_allow: 349 }, 'DEF', s)).toBe(1);
		expect(scoreLine({ pts_allow: 21, yds_allow: 99 }, 'DEF', s)).toBe(2.9);
	});

	it('falls back to st_td for team defenses only without def_st_td', () => {
		const line: StatLine = { st_td: 1 };
		expect(scoreLine(line, 'DEF', sleeper({ st_td: 6 }))).toBe(6);
		expect(scoreLine(line, 'DEF', sleeper({ st_td: 6, def_st_td: 4 }))).toBe(4);
	});

	it('scores IDP keys for defenders only', () => {
		const s = sleeper({ idp_tkl: 1, idp_tkl_solo: 0.5, idp_sack: 4, idp_int: 3, sack: 1 });
		const lb: StatLine = { tkl_solo: 7, tkl_ast: 3, sack: 1, def_int: 1 };
		// 10 tackles + 3.5 solo bonus + 4 sack + 3 INT; the team-DEF sack key doesn't apply
		expect(expectConsistent(lb, 'LB', s)).toBe(20.5);
		expect(scoreLine(lb, 'WR', s)).toBe(0);
		expect(scoreLine(lb, 'DEF', s)).toBe(1);
	});

	it('reports unknown and untracked non-zero keys', () => {
		const s = sleeper({ pass_yd: 0.04, pass_air_yd: 0.01, def_st_ff: 1, def_st_fum_rec: 0, x: 0 });
		expect(unsupported(s)).toEqual(['pass_air_yd', 'def_st_ff']);
		expect(scoreLine({ pass_yd: 100 }, 'QB', s)).toBe(4);
	});
});

describe('ESPN items', () => {
	it('scores every-25-yards passing and the 40+ TD bonus', () => {
		// trunc(312 / 25) = 12, 2 TD * 4, INT -2, one 40+ TD * 2, 14 rush yd * 0.1
		expect(expectConsistent(QB, 'QB', espnFixture)).toBe(21.4);
	});

	it('applies lineup-slot overrides (TE receptions)', () => {
		const line: StatLine = { rec: 6, rec_yd: 58, rec_td: 1, rec_td_yds: [12] };
		expect(expectConsistent(line, 'TE', espnFixture)).toBe(20.8); // 6 * 1.5 + 5.8 + 6
		expect(scoreLine(line, 'WR', espnFixture)).toBe(17.8);
	});

	it('scores a D/ST that allowed 17 points (14-17 bucket)', () => {
		const dst: StatLine = {
			sack: 2,
			def_int: 1,
			def_fum_rec: 1,
			def_td: 1,
			st_td: 1,
			pts_allow: 17
		};
		// 1 (14-17) + 2 sacks + INT 2 + FR 2 + return TDs 6 + 6
		expect(expectConsistent(dst, 'DEF', espnFixture)).toBe(19);
		expect(scoreLine({ pts_allow: 18 }, 'DEF', espnFixture)).toBe(0);
		expect(scoreLine({}, 'DEF', espnFixture)).toBe(5); // shutout
		expect(scoreLine({ pts_allow: 46 }, 'DEF', espnFixture)).toBe(-5);
	});

	it('splits field goals by distance', () => {
		const k: StatLine = { fgm: 3, fgmiss: 1, fgm_dists: [52, 44, 30], fgmiss_dists: [48], xpm: 2 };
		expect(expectConsistent(k, 'K', espnFixture)).toBe(13); // 5 + 4 + 3 - 1 + 2
		const long = espn([
			{ statId: 74, points: 5 },
			{ statId: 198, points: 1 },
			{ statId: 201, points: 2 },
			{ statId: 76, points: -1 }
		]);
		// 61 and 55 made: 74 counts both (10), 198 the 55 (1), 201 the 61 (2); one 50+ miss
		expect(scoreLine({ fgm_dists: [61, 55, 33], fgmiss_dists: [57] }, 'K', long)).toBe(12);
	});

	it('scores exclusive yardage-game buckets and TD-length buckets', () => {
		const s = espn([
			{ statId: 17, points: 2 },
			{ statId: 18, points: 4 },
			{ statId: 37, points: 1 },
			{ statId: 38, points: 3 },
			{ statId: 176, points: 1 },
			{ statId: 16, points: 2 }
		]);
		expect(scoreLine({ pass_yd: 420, rush_yd: 150, pass_td_yds: [15, 19, 55] }, 'QB', s)).toBe(9);
		expect(scoreLine({ pass_yd: 300, rush_yd: 200 }, 'QB', s)).toBe(5);
	});

	it('scores player return TDs separately and D/ST TDs at the group average', () => {
		const s = espn([
			{ statId: 101, points: 6 },
			{ statId: 102, points: 6 },
			{ statId: 103, points: 6 },
			{ statId: 104, points: 4 }
		]);
		expect(scoreLine({ kr_td: 1, st_td: 1 }, 'WR', s)).toBe(6);
		expect(scoreLine({ def_td: 2, st_td: 1 }, 'DEF', s)).toBe(16); // 2 * avg(6, 4) + 6
		expect(scoreLine({ def_td: 1 }, 'DB', s)).toBe(5);
		expect(unsupported(s)).toEqual([
			'D/ST INT and fumble return TDs (scored at their average)',
			'IDP INT and fumble return TDs (scored at their average)'
		]);
	});

	it('keeps defensive items off offensive players', () => {
		const s = espn([
			{ statId: 99, points: 1 },
			{ statId: 108, points: 1 },
			{ statId: 120, points: -0.5 }
		]);
		expect(scoreLine({ sack: 1, tkl_solo: 2, pts_allow: 10 }, 'RB', s)).toBe(0);
		expect(scoreLine({ sack: 1, tkl_solo: 2 }, 'LB', s)).toBe(3);
		expect(scoreLine({ sack: 1, pts_allow: 10 }, 'DEF', s)).toBe(-4);
	});

	it('reports unsupported non-zero items', () => {
		expect(unsupported(espnFixture)).toEqual(['Punt average']);
		const s = espn([
			{ statId: 999, points: 1 },
			{ statId: 155, points: 0, pointsOverrides: { '19': 5 } },
			{ statId: 156, points: 0 }
		]);
		expect(unsupported(s)).toEqual(['ESPN stat 999', 'Team win']);
	});
});

describe('engine', () => {
	it('rounds to cents without float noise or negative zero', () => {
		expect(round2(12.299999999)).toBe(12.3);
		expect(round2(0.1 + 0.2)).toBe(0.3);
		expect(Object.is(round2(-0.001), 0)).toBe(true);
		expect(scoreLine({ pass_yd: 7 }, 'QB', PRESETS.ppr)).toBe(0.28);
	});

	it('breakdown is sorted by size and always sums to scoreLine', () => {
		const keys: (keyof StatLine)[] = [
			'pass_yd',
			'pass_td',
			'pass_int',
			'rush_yd',
			'rush_td',
			'rec',
			'rec_yd',
			'rec_td',
			'fum_lost',
			'sack',
			'def_int',
			'pts_allow',
			'tkl_solo'
		];
		const scorings = [
			PRESETS.ppr,
			espnFixture,
			sleeper({ pass_yd: 1 / 30, rec: 0.333, rush_yd: 0.07, pts_allow: -0.17 })
		];
		const positions: FantasyPos[] = ['QB', 'RB', 'WR', 'TE', 'DEF', 'LB'];
		let seed = 7;
		const rand = (max: number) => {
			seed = (seed * 16807) % 2147483647;
			return seed % max;
		};
		for (let i = 0; i < 300; i++) {
			const line: StatLine = {};
			for (const k of keys) if (rand(2)) (line as Record<string, number>)[k] = rand(150);
			const pos = positions[rand(positions.length)];
			for (const s of scorings) {
				expectConsistent(line, pos, s);
				const pts = breakdown(line, pos, s).map((p) => Math.abs(p.points));
				expect(pts).toEqual([...pts].sort((a, b) => b - a));
			}
		}
	});

	it('scores a season of lines quickly', () => {
		const line: StatLine = { ...QB, rec: 3, rec_yd: 20 };
		const t0 = performance.now();
		let sum = 0;
		for (let i = 0; i < 8000; i++) sum += scoreLine(line, 'QB', espnFixture);
		expect(sum).toBeGreaterThan(0);
		expect(performance.now() - t0).toBeLessThan(200);
	});

	it('gives equivalent scorings the same key', () => {
		const a = sleeper({ pass_yd: 0.04, rec: 1, fum: 0 });
		const b = sleeper({ rec: 1, pass_yd: 0.04 });
		expect(scoringKey(a)).toBe(scoringKey(b));
		expect(scoringKey(PRESETS.ppr)).not.toBe(scoringKey(PRESETS.half));
		const e1 = espn([
			{ statId: 53, points: 1, pointsOverrides: { '6': 1.5, '2': 1 } },
			{ statId: 3, points: 0.04 }
		]);
		const e2 = espn([
			{ statId: 3, points: 0.04 },
			{ statId: 53, points: 1, pointsOverrides: { '2': 1, '6': 1.5 } }
		]);
		expect(scoringKey(e1)).toBe(scoringKey(e2));
		expect(scoringKey(e1)).not.toBe(scoringKey(espn([{ statId: 53, points: 1 }])));
	});
});
