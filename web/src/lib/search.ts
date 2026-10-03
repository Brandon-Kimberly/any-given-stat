// Search ranking for the ⌘K palette, plus the glossary index it searches.

/** Lowercased words of a name: "Amon-Ra St. Brown" -> ["amon", "ra", "st", "brown"]. */
export function words(text: string): string[] {
	return text
		.toLowerCase()
		.split(/[^\p{L}\p{N}]+/u)
		.filter(Boolean);
}

/**
 * How well `query` matches an entry named `label` (with extra searchable text `key`), higher is
 * better, 0 = no match:
 * exact name 100 > name prefix 80 > every query word starts a word of the name 60 >
 * every query word starts a word of the extra text 35 > substring of the name 30 >
 * substring of the extra text 10.
 * "jef" finds "Justin Jefferson" (word start); "j jeff" too; "smith" doesn't find "St. Brown".
 */
export function matchScore(label: string, key: string, query: string): number {
	const q = query.trim().toLowerCase();
	if (!q) return 0;
	const name = label.toLowerCase();
	if (name === q) return 100;
	if (name.startsWith(q)) return 80;
	const qw = words(q);
	if (!qw.length) return name.includes(q) ? 30 : 0;
	const nw = words(name);
	if (qw.every((w) => nw.some((n) => n.startsWith(w)))) return 60;
	const extra = key.toLowerCase();
	const kw = words(extra);
	if (qw.every((w) => kw.some((n) => n.startsWith(w)) || nw.some((n) => n.startsWith(w))))
		return 35;
	if (name.includes(q)) return 30;
	if (extra.includes(q)) return 10;
	return 0;
}

/** Rank entries for a query: score, then kind priority (lower first), then shorter names. */
export function rank<E extends { label: string; key: string }>(
	entries: E[],
	query: string,
	priority: (e: E) => number = () => 0,
	limit = 12
): E[] {
	return entries
		.map((e) => ({ e, s: matchScore(e.label, e.key, query) }))
		.filter((r) => r.s > 0)
		.sort(
			(a, b) =>
				b.s - a.s ||
				priority(a.e) - priority(b.e) ||
				a.e.label.length - b.e.label.length ||
				a.e.label.localeCompare(b.e.label)
		)
		.slice(0, limit)
		.map((r) => r.e);
}

/** "Target share / air yards share" -> "target-share-air-yards-share". */
export function slugify(text: string): string {
	return words(text).join('-');
}

export interface GlossaryTerm {
	id: string;
	term: string;
	def: string;
}

/**
 * Glossary terms from the glossary page's source (each `{ id, term, def }` object literal), so
 * the palette stays in sync with the page without a second copy. A term without an id gets
 * one slugified from its name.
 */
export function parseGlossary(source: string): GlossaryTerm[] {
	const str = (block: string, field: string) => {
		const m = block.match(new RegExp(`\\b${field}:\\s*(['"\`])((?:\\\\.|(?!\\1).)*)\\1`, 's'));
		return m ? m[2].replace(/\\(.)/g, '$1') : null;
	};
	const out: GlossaryTerm[] = [];
	for (const m of source.matchAll(/\{[^{}]*?\bterm:[^{}]*\}/g)) {
		const term = str(m[0], 'term');
		if (!term) continue;
		out.push({ id: str(m[0], 'id') ?? slugify(term), term, def: str(m[0], 'def') ?? '' });
	}
	return out;
}
