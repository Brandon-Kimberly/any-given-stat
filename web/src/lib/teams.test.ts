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
