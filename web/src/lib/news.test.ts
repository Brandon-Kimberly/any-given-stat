import { describe, expect, it } from 'vitest';
import {
	ago,
	changeLabel,
	dayLabel,
	fantasyRelevant,
	filterNews,
	groupByDay,
	injuryTone,
	statusShort,
	updatedLabel
} from './news';
import type { NewsItem } from './types';

function item(over: Partial<NewsItem>): NewsItem {
	return {
		id: 'x',
		kind: 'news',
		headline: 'Headline',
		description: '',
		published: '2026-10-02T12:00:00Z',
		url: 'https://www.espn.com/nfl/story/_/id/1',
		image: null,
		teams: [],
		players: [],
		athletes: [],
		source: 'ESPN',
		...over
	};
}

const darnold = item({
	id: 'a',
	teams: ['SEA'],
	players: ['P1'],
	athletes: [{ id: 'P1', name: 'Sam Darnold' }]
});
const injury = item({
	id: 'b',
	kind: 'injury',
	url: null,
	teams: ['KC'],
	players: ['K1'],
	athletes: [{ id: 'K1', name: 'Chief Receiver' }],
	status: 'Out',
	change: 'worse',
	position: 'WR'
});
const lineman = { ...injury, id: 'c', position: 'G', players: ['K2'] };
const general = item({ id: 'd', teams: ['DET', 'GB'] });

describe('filterNews', () => {
	const all = [darnold, injury, lineman, general];
	it('filters by team, players and kind', () => {
		expect(filterNews(all, { team: 'KC' }).map((i) => i.id)).toEqual(['b', 'c']);
		expect(filterNews(all, { players: ['P1', 'K2'] }).map((i) => i.id)).toEqual(['a', 'c']);
		expect(filterNews(all, { kind: 'injury' }).map((i) => i.id)).toEqual(['b', 'c']);
		expect(filterNews(all, { kind: 'news', team: 'GB' }).map((i) => i.id)).toEqual(['d']);
		expect(filterNews(all, {}).length).toBe(4);
		expect(filterNews(all, { players: [] })).toEqual([]);
	});
	it('fantasy relevance', () => {
		expect([darnold, injury, lineman, general].map(fantasyRelevant)).toEqual([
			true,
			true,
			false,
			false
		]);
		expect(fantasyRelevant(item({ headline: 'Fantasy football Week 5 rankings' }))).toBe(true);
		expect(fantasyRelevant({ ...injury, status: undefined, change: undefined })).toBe(false);
		expect(fantasyRelevant({ ...injury, status: undefined, change: 'cleared' })).toBe(true);
	});
});

describe('injury labels', () => {
	it('tones and words', () => {
		expect(injuryTone(injury)).toBe('out');
		expect(injuryTone({ ...injury, status: 'Questionable' })).toBe('questionable');
		expect(injuryTone({ ...injury, status: undefined, change: 'cleared' })).toBe('cleared');
		expect(injuryTone({ ...injury, status: undefined, change: undefined })).toBe('info');
		expect(statusShort({ ...injury, status: 'Questionable' })).toBe('Q');
		expect(statusShort({ ...injury, status: undefined, preliminary: true })).toBe('Practice');
		expect(changeLabel(injury)).toBe('Downgraded');
		expect(changeLabel({ ...injury, change: 'cleared' })).toBeNull();
		expect(changeLabel(darnold)).toBeNull();
	});
});

describe('time labels', () => {
	const now = new Date('2026-10-03T18:00:00Z').getTime();
	it('ago', () => {
		expect(ago('2026-10-03T17:59:50Z', now)).toBe('just now');
		expect(ago('2026-10-03T17:48:00Z', now)).toBe('12 min ago');
		expect(ago('2026-10-03T13:00:00Z', now)).toBe('5 h ago');
		expect(ago('2026-09-30T18:00:00Z', now)).toBe('3 days ago');
		expect(ago(null, now)).toBe('');
		expect(ago('nope', now)).toBe('');
	});
	it('updated label', () => {
		expect(updatedLabel({ news_fetched_at: '2026-10-03T17:48:00Z', live: true }, now)).toBe(
			'Updated 12 min ago'
		);
		expect(updatedLabel({ news_fetched_at: null, live: false }, now)).toBe('Headlines unavailable');
		expect(updatedLabel(null, now)).toBe('');
	});
	it('day labels and groups', () => {
		const at = new Date(2026, 9, 3, 15, 0); // Saturday Oct 3, local time
		const iso = (d: number, h = 12) => new Date(2026, 9, d, h).toISOString();
		expect(dayLabel(iso(3, 1), at)).toBe('Today');
		expect(dayLabel(iso(2), at)).toBe('Yesterday');
		expect(dayLabel(iso(1), at)).toBe('Thursday');
		expect(dayLabel(new Date(2026, 8, 24, 12).toISOString(), at)).toBe('Sep 24');
		const groups = groupByDay(
			[
				item({ id: '1', published: iso(3) }),
				item({ id: '2', published: iso(3, 2) }),
				item({ id: '3', published: iso(2) })
			],
			at
		);
		expect(groups.map((g) => [g.label, g.items.length])).toEqual([
			['Today', 2],
			['Yesterday', 1]
		]);
	});
});
