import { describe, expect, it } from 'vitest';
import { epa, pct, pp, signed } from './format';

describe('format', () => {
	it('signs EPA with a true minus and no negative zero', () => {
		expect(epa(0.1424)).toBe('+0.142');
		expect(epa(-0.05)).toBe('−0.050');
		expect(epa(-0.0001)).toBe('0.000');
		expect(signed(-0.03)).toBe('0.0');
	});

	it('formats rates and percentage points', () => {
		expect(pct(0.4567)).toBe('45.7%');
		expect(pp(-0.031)).toBe('−3.1');
		expect(pct(null)).toBe('–');
	});
});
