import { describe, expect, it } from 'vitest';
import { thinTicks } from './plot';

describe('thinTicks', () => {
	it('keeps everything when there is room', () => {
		expect(thinTicks([1, 2, 3], 1000)).toEqual([1, 2, 3]);
	});

	it('thins evenly and keeps the last tick', () => {
		const out = thinTicks(
			Array.from({ length: 18 }, (_, i) => i + 1),
			200,
			44
		);
		expect(out.length).toBeLessThanOrEqual(5);
		expect(out[0]).toBe(1);
		expect(out.at(-1)).toBe(18);
	});
});
