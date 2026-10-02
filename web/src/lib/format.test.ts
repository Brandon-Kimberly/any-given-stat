import { describe, expect, it } from 'vitest';
import { epa, pct, pp, signed, spread, wlt } from './format';

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

describe('spread', () => {
	it('names the favorite with a negative line', () => {
		expect(spread(3.46, 'KC', 'BUF')).toBe('KC −3.5');
		expect(spread(-7, 'KC', 'BUF')).toBe('BUF −7.0');
		expect(spread(0.01, 'KC', 'BUF')).toBe('PK');
		expect(spread(null, 'KC', 'BUF')).toBe('–');
	});
});

describe('wlt', () => {
	it('shows a tie only when there is one', () => {
		expect(wlt(9, 17)).toBe('9–8');
		expect(wlt(9.5, 17)).toBe('9–7–1');
		expect(wlt(null, 17)).toBe('–');
	});
});
