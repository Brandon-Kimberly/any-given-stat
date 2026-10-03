import { describe, expect, it } from 'vitest';
import { escapeAttr, pageMeta } from './seo';

describe('link previews', () => {
	it('gives each route its own title and falls back to the home card', () => {
		expect(pageMeta('/odds/').title).toBe('Playoff odds · Any Given Stat');
		expect(pageMeta('/').title).toMatch(/^Any Given Stat/);
		expect(pageMeta('/no-such-page/')).toEqual(pageMeta('/'));
	});
	it('keeps descriptions short enough for chat previews', () => {
		for (const p of ['/', '/predictions/', '/fantasy/', '/team/', '/game/']) {
			expect(pageMeta(p).description.length).toBeLessThanOrEqual(220);
		}
	});
	it('escapes attribute text', () => {
		expect(escapeAttr(`"A" & <b>'s`)).toBe('&quot;A&quot; &amp; &lt;b&gt;&#39;s');
	});
});
