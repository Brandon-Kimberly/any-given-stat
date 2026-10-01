import { describe, expect, it } from 'vitest';
import { median, ols, ranks, rolling, sd } from './stats';

describe('stats', () => {
	it('median handles even and odd lengths', () => {
		expect(median([3, 1, 2])).toBe(2);
		expect(median([4, 1, 2, 3])).toBe(2.5);
	});

	it('sd is the sample standard deviation', () => {
		expect(sd([2, 4, 4, 4, 5, 5, 7, 9])).toBeCloseTo(2.138, 3);
	});

	it('ranks share ties and respect direction', () => {
		expect(ranks([0.1, 0.3, 0.3, null])).toEqual([3, 1, 1, null]);
		expect(ranks([0.1, 0.3, -0.2], false)).toEqual([2, 3, 1]);
	});

	it('ols recovers an exact line', () => {
		const { a, b, r } = ols([0, 1, 2, 3], [1, 3, 5, 7]);
		expect(a).toBeCloseTo(1);
		expect(b).toBeCloseTo(2);
		expect(r).toBeCloseTo(1);
	});

	it('rolling uses a shorter window at the start', () => {
		expect(rolling([1, 2, 3, 4], 2)).toEqual([1, 1.5, 2.5, 3.5]);
	});
});
