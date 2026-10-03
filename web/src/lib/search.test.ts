import { describe, expect, it } from 'vitest';
import { kickoffKey, kickoffLabel, kickoffLabelFromKey } from './kickoff';
import { matchScore, parseGlossary, rank, slugify, words } from './search';

describe('matchScore', () => {
	it('ranks exact > prefix > word start > extra word start > substring > extra substring', () => {
		expect(matchScore('Justin Jefferson', '', 'justin jefferson')).toBe(100);
		expect(matchScore('Justin Jefferson', '', 'just')).toBe(80);
		expect(matchScore('Justin Jefferson', '', 'jef')).toBe(60);
		expect(matchScore('Justin Jefferson', '', 'j jeff')).toBe(60);
		expect(matchScore('Justin Jefferson', '', 'ffer')).toBe(30);
		expect(matchScore('Detroit Lions', 'det detroit lions', 'det')).toBe(80);
		expect(matchScore('Power ratings', 'predictive ratings week by week', 'week')).toBe(35);
		// A word start in the description beats a mid-word hit in a name ("epa" in "Shepard").
		expect(matchScore('Quarterbacks', 'EPA per dropback', 'epa')).toBeGreaterThan(
			matchScore('Sterling Shepard', '', 'epa')
		);
		expect(matchScore('Power ratings', 'predictive ratings', 'ictive')).toBe(10);
	});
	it('splits names on hyphens and periods', () => {
		expect(words('Amon-Ra St. Brown')).toEqual(['amon', 'ra', 'st', 'brown']);
		expect(matchScore('Amon-Ra St. Brown', '', 'ra')).toBe(60);
		expect(matchScore('Amon-Ra St. Brown', '', 'brown')).toBe(60);
		expect(matchScore('Amon-Ra St. Brown', '', 'smith')).toBe(0);
	});
	it('needs every query word', () => {
		expect(matchScore('Justin Jefferson', '', 'justin herbert')).toBe(0);
	});
});

describe('rank', () => {
	const e = (label: string, kind = 0) => ({ label, key: label.toLowerCase(), kind });
	it('orders by score, then priority, then shorter names', () => {
		const out = rank(
			[e('Jeff Wilson', 2), e('Justin Jefferson', 2), e('Jefferson', 1), e('Van Jefferson', 2)],
			'jeff',
			(x) => x.kind
		);
		expect(out.map((x) => x.label)).toEqual([
			'Jefferson',
			'Jeff Wilson',
			'Van Jefferson',
			'Justin Jefferson'
		]);
	});
});

describe('parseGlossary', () => {
	it('reads id/term/def object literals and slugifies missing ids', () => {
		const src = `const groups = [{ name: 'Core', terms: [
			{ id: 'epa', term: 'EPA (expected points added)', def: 'EP after minus before.' },
			{ term: 'Target share / air yards', def: 'Share of targets.', see: ['/x/', 'See'] }
		] }];`;
		expect(parseGlossary(src)).toEqual([
			{ id: 'epa', term: 'EPA (expected points added)', def: 'EP after minus before.' },
			{ id: 'target-share-air-yards', term: 'Target share / air yards', def: 'Share of targets.' }
		]);
		expect(slugify('Fit / validate / test')).toBe('fit-validate-test');
	});
});

describe('kickoff', () => {
	it('labels day, date and Eastern time', () => {
		expect(kickoffLabel('2026-10-04', '13:00')).toBe('Sun 10/4 · 1:00 PM');
		expect(kickoffLabel('2026-10-04', '09:30')).toBe('Sun 10/4 · 9:30 AM');
		expect(kickoffLabel('2026-10-05', '20:15')).toBe('Mon 10/5 · 8:15 PM');
		expect(kickoffLabel('2026-10-05', null)).toBe('Mon 10/5');
		expect(kickoffKey('2026-10-04', '09:30') < kickoffKey('2026-10-04', '13:00')).toBe(true);
		expect(kickoffLabelFromKey(kickoffKey('2026-10-05', null))).toBe('Mon 10/5');
		expect(kickoffLabelFromKey(kickoffKey('2026-10-05', '20:15'))).toBe('Mon 10/5 · 8:15 PM');
	});
});
