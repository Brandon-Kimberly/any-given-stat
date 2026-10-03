import { describe, expect, it } from 'vitest';
import { colorsClash } from './teams.svelte';

describe('colorsClash', () => {
	it('flags two navies and passes navy vs red', () => {
		expect(colorsClash('#0b2265', '#041e42')).toBe(true);
		expect(colorsClash('#0b2265', '#e31837')).toBe(false);
	});
	it('treats unparseable colors as clashing', () => {
		expect(colorsClash('var(--x)', '#ffffff')).toBe(true);
	});
});

describe('nightShade', () => {
	it('keeps white text readable on any team color', async () => {
		const { nightShade } = await import('./teams.svelte');
		for (const c of ['#ffb612', '#a5acaf', '#ffffff', '#97233f', '#0b162a']) {
			const out = nightShade(c)!;
			const n = parseInt(out.slice(1), 16);
			const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
				const x = v / 255;
				return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
			});
			const L = 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
			expect(1.05 / (L + 0.05)).toBeGreaterThanOrEqual(5.5);
		}
	});
});
