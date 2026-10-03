import { describe, expect, it } from 'vitest';
import {
	decodePlays,
	headline,
	isKey,
	nameStyler,
	playSummary,
	quarterName,
	scoreEvent,
	searchText,
	situation,
	spot,
	yards,
	type Play
} from './playText';
import type { GamePlays, PlayRow } from './types';

const COLUMNS = [
	'qtr',
	'time',
	'posteam',
	'down',
	'ydstogo',
	'yl',
	'play_type',
	'desc',
	'epa',
	'home_wp_after',
	'home_score',
	'away_score',
	'flags',
	'drive',
	'home_wpa',
	'yds',
	'yl_end',
	'kind',
	'a',
	'b',
	'detail',
	'air',
	'kick',
	'ret',
	'd',
	'pen',
	'fum'
];

const file = (rows: unknown[][], cols = COLUMNS): GamePlays => ({
	game_id: '2025_02_NYG_DAL',
	plays_columns: cols,
	flags: {},
	drives: [],
	plays: rows as PlayRow[]
});

const base: Play = {
	i: 0,
	qtr: 1,
	time: '14:48',
	team: 'NYG',
	down: 1,
	togo: 10,
	yl: 20,
	type: 'run',
	desc: '',
	epa: 0,
	wp: 0.5,
	homeScore: 0,
	awayScore: 0,
	flags: '',
	drive: 1,
	wpa: 0,
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
const play = (o: Partial<Play>): Play => ({ ...base, ...o });
const short = (n: string | null) => (n ? n.replace(/^.*\./, '') : '');

describe('decodePlays', () => {
	it('reads structured columns by name and tolerates trimmed rows', () => {
		const [p, q] = decodePlays(
			file([
				[
					1,
					'14:48',
					'NYG',
					1,
					10,
					20,
					'run',
					'x',
					-0.25,
					0.58,
					0,
					0,
					'',
					1,
					0.002,
					4,
					24,
					'run',
					'D.Singletary',
					null,
					'left tackle'
				],
				[1, '14:20', 'NYG', 2, 6, 24, 'pass', 'y', 0.6, 0.58, 0, 0, '', 1]
			])
		);
		expect(p).toMatchObject({
			team: 'NYG',
			yds: 4,
			ylEnd: 24,
			kind: 'run',
			a: 'D.Singletary',
			detail: 'left tackle',
			pen: null
		});
		expect(q).toMatchObject({ i: 1, kind: null, a: null, wpa: null });
	});

	it('derives the WP swing from the previous row in older files', () => {
		const old = COLUMNS.slice(0, 14);
		const plays = decodePlays(
			file(
				[
					[1, '15:00', 'NYG', null, 0, 65, 'kickoff', 'k', 0, 0.5, 0, 0, '', 1],
					[1, '14:48', 'NYG', 1, 10, 20, 'run', 'r', 0, 0.56, 0, 0, '', 1]
				],
				old
			)
		);
		expect(plays[0].wpa).toBeNull();
		expect(plays[1].wpa).toBe(0.06);
	});
});

describe('names', () => {
	it('uses surnames unless two players in the game share one', () => {
		const name = nameStyler([
			play({ a: 'R.Wilson', b: 'M.Nabers' }),
			play({ a: 'J.Williams', d: 'Q.Williams / A.St. Brown' })
		]);
		expect(name('R.Wilson')).toBe('Wilson');
		expect(name('J.Williams')).toBe('J.Williams');
		expect(name('Q.Williams / A.St. Brown')).toBe('Q.Williams & St. Brown');
		expect(name(null)).toBe('');
	});
});

describe('yards and spots', () => {
	it('formats yardage like a broadcast', () => {
		expect(yards(4)).toBe('4 yds');
		expect(yards(1)).toBe('1 yd');
		expect(yards(0)).toBe('no gain');
		expect(yards(-7)).toBe('−7 yds');
		expect(yards(null)).toBeNull();
	});
	it('names yard lines from the offense', () => {
		expect(spot('NYG', 24, 'DAL', 'NYG')).toBe('NYG 24');
		expect(spot('NYG', 62, 'DAL', 'NYG')).toBe('DAL 38');
		expect(spot('NYG', 50, 'DAL', 'NYG')).toBe('50');
		expect(situation(play({ down: 3, togo: 4, yl: 96 }), 'DAL', 'NYG')).toBe('3rd & Goal · DAL 4');
		expect(situation(play({ down: null, kind: 'kickoff', yl: 65 }), 'DAL', 'NYG')).toBe(
			'Kickoff · DAL 35'
		);
		expect(quarterName(2)).toBe('2nd quarter');
		expect(quarterName(5)).toBe('Overtime');
	});
});

describe('headline', () => {
	const h = (o: Partial<Play>) => headline(play(o), short);

	it('builds passes, runs and sacks from fields', () => {
		expect(
			h({
				kind: 'complete',
				a: 'R.Wilson',
				b: 'M.Nabers',
				yds: 29,
				detail: 'deep left',
				flags: 'TX1',
				ylEnd: 100
			})
		).toMatchObject({
			glyph: 'score',
			lead: 'Wilson → Nabers',
			facts: ['29 yds', 'deep left'],
			outcome: 'Touchdown',
			tone: 'good'
		});
		expect(
			h({ kind: 'incomplete', a: 'R.Wilson', b: 'M.Nabers', detail: 'deep right' })
		).toMatchObject({
			glyph: 'incomplete',
			lead: 'Wilson → Nabers',
			facts: ['incomplete', 'deep right']
		});
		expect(h({ kind: 'run', a: 'D.Singletary', yds: 4, detail: 'left tackle' }).lead).toBe(
			'Singletary run'
		);
		expect(h({ kind: 'run', a: 'D.Singletary', yds: 0, detail: 'middle' }).facts).toEqual([
			'no gain',
			'up the middle'
		]);
		expect(h({ kind: 'sack', a: 'R.Wilson', d: 'K.Clark', yds: -9 })).toMatchObject({
			glyph: 'sack',
			lead: 'Clark sacks Wilson',
			facts: ['−9 yds']
		});
	});

	it('marks turnovers and defensive scores', () => {
		expect(
			h({
				kind: 'interception',
				a: 'D.Prescott',
				b: 'C.Lamb',
				d: 'A.Phillips',
				flags: 'I',
				detail: 'deep middle'
			})
		).toMatchObject({
			glyph: 'turnover',
			lead: 'Phillips intercepts Prescott',
			facts: ['intended for Lamb', 'deep middle'],
			outcome: 'Interception',
			tone: 'bad'
		});
		expect(
			h({ kind: 'interception', a: 'J.McCarthy', d: 'N.Wright', flags: 'TI', ylEnd: 0, ret: 74 })
				.outcome
		).toBe('Pick-six');
		expect(
			h({ kind: 'run', a: 'D.Henry', yds: -3, flags: 'F', fum: 'D.Henry', d: 'T.Bernard' })
		).toMatchObject({
			glyph: 'turnover',
			facts: ['−3 yds', 'Henry fumbles', 'Bernard recovers'],
			outcome: 'Fumble lost'
		});
	});

	it('describes kicks', () => {
		expect(h({ kind: 'fg_made', a: 'B.Aubrey', kick: 64 })).toMatchObject({
			glyph: 'kick',
			lead: 'Aubrey 64-yd field goal',
			outcome: 'Good'
		});
		expect(h({ kind: 'fg_blocked', a: 'C.Ryland', kick: 46, d: 'B.Bresee' })).toMatchObject({
			outcome: 'Blocked',
			facts: ['by Bresee']
		});
		expect(h({ kind: 'xp_failed', a: 'G.Gano' })).toMatchObject({
			lead: 'Gano extra point',
			outcome: 'No good',
			tone: 'bad'
		});
		expect(h({ kind: '2pt_good', a: 'T.Tagovailoa', b: 'J.Hill' }).lead).toBe(
			'Two-point try: Tagovailoa → Hill'
		);
		expect(h({ kind: 'punt', a: 'B.Anger', kick: 41, b: 'G.Olszewski', ret: 8 })).toMatchObject({
			glyph: 'punt',
			lead: 'Anger punt, 41 yds',
			facts: ['Olszewski returns 8 yds']
		});
		expect(
			h({ kind: 'punt', a: 'B.Anger', kick: 48, b: 'G.Olszewski', detail: 'fair catch' }).facts
		).toEqual(['fair catch']);
		expect(h({ kind: 'kickoff', a: 'G.Gano', kick: 61, detail: 'touchback' })).toMatchObject({
			lead: 'Gano kickoff, 61 yds',
			facts: ['touchback']
		});
	});

	it('handles flags', () => {
		expect(h({ kind: 'penalty', pen: ['NYG', 'False Start', 5, 'J.Hudson', null] })).toMatchObject({
			glyph: 'penalty',
			lead: 'Flag: False Start',
			facts: ['NYG Hudson', '5 yds', 'no play']
		});
		expect(
			h({
				kind: 'complete',
				a: 'R.Wilson',
				b: 'W.Robinson',
				yds: 50,
				pen: ['NYG', 'Unnecessary Roughness', 15, 'J.Hudson', null]
			}).flag
		).toBe('Flag: Unnecessary Roughness, NYG Hudson, 15 yds');
		expect(
			h({ kind: 'run', a: 'X.Y', yds: 3, pen: ['DAL', 'Offside', 0, null, 'declined'] }).flag
		).toBe('Flag: Offside, DAL, declined');
	});

	it('falls back to the description summarizer', () => {
		expect(
			h({
				desc: '(14:48) (Shotgun) 26-D.Singletary left tackle to NYG 24 for 4 yards (13-D.Fowler).'
			})
		).toMatchObject({
			glyph: 'run',
			lead: 'D.Singletary 4-yd run'
		});
	});
});

describe('scoring and key plays', () => {
	it('labels score changes', () => {
		const prev = play({ homeScore: 3, awayScore: 6 });
		expect(
			scoreEvent(play({ homeScore: 3, awayScore: 12, team: 'NYG', flags: 'T' }), prev, 'DAL', 'NYG')
		).toEqual({
			team: 'NYG',
			points: 6,
			label: 'Touchdown',
			big: true
		});
		expect(scoreEvent(play({ homeScore: 6, awayScore: 6 }), prev, 'DAL', 'NYG')?.label).toBe(
			'Field goal'
		);
		expect(
			scoreEvent(play({ homeScore: 3, awayScore: 7, kind: 'xp_good' }), prev, 'DAL', 'NYG')
		).toMatchObject({ label: 'Extra point', big: false });
		expect(
			scoreEvent(play({ homeScore: 5, awayScore: 6, team: 'NYG' }), prev, 'DAL', 'NYG')?.label
		).toBe('Safety');
		expect(scoreEvent(play({ homeScore: 3, awayScore: 6 }), prev, 'DAL', 'NYG')).toBeNull();
	});
	it('keeps scores, turnovers, failed fourth downs and big swings', () => {
		expect(isKey(play({ flags: 'I' }), null)).toBe(true);
		expect(isKey(play({ wpa: -0.06 }), null)).toBe(true);
		expect(isKey(play({ wpa: 0.01 }), null)).toBe(false);
		expect(isKey(play({ down: 4, togo: 2, yds: 1, type: 'run', kind: 'run' }), null)).toBe(true);
		expect(
			isKey(play({ down: 4, togo: 2, yds: 3, type: 'run', kind: 'run', flags: '41' }), null)
		).toBe(false);
	});
	it('searches names, penalties and the description', () => {
		const p = play({
			kind: 'complete',
			a: 'R.Wilson',
			b: 'M.Nabers',
			yds: 5,
			desc: '3-R.Wilson pass to 1-M.Nabers'
		});
		const text = searchText(p, headline(p, short));
		expect(text).toContain('nabers');
		expect(text).toContain('m.nabers');
	});
});

describe('playSummary', () => {
	it('shortens raw descriptions', () => {
		expect(
			playSummary(
				'(13:03) (Shotgun) 9-J.McCarthy pass short left intended for 18-J.Jefferson INTERCEPTED by 26-N.Wright at CHI 26. 26-N.Wright for 74 yards, TOUCHDOWN.'
			)
		).toBe('N.Wright intercepts J.McCarthy, 74-yd pick-six');
		expect(playSummary('9-G.Gano 38 yard field goal is GOOD, Center-59-C.Kreiter.')).toBe(
			'G.Gano 38-yd field goal good'
		);
		expect(playSummary('5-B.Anger punts 41 yards to NYG 23, Center-44-T.Sieg.')).toBe(
			'B.Anger 41-yd punt'
		);
		expect(
			playSummary(
				'(Shotgun) PENALTY on NYG-55-J.Hudson, False Start, 5 yards, enforced at DAL 15 - No Play.'
			)
		).toBe('Flag on NYG: False Start, 5 yds');
		expect(playSummary('3-R.Wilson pass incomplete deep right to 1-M.Nabers.')).toBe(
			'R.Wilson incomplete to M.Nabers'
		);
	});
});
