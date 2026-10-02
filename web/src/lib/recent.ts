// Recently opened pages, teams and players (hrefs, newest first), kept in localStorage for
// the search palette's empty state.

const KEY = 'ags-recent';
const MAX = 6;

export function readRecent(): string[] {
	try {
		const v = JSON.parse(localStorage.getItem(KEY) ?? '[]');
		return Array.isArray(v) ? v.filter((x) => typeof x === 'string').slice(0, MAX) : [];
	} catch {
		return [];
	}
}

/** Record a visit: moves `href` to the front, dropping duplicates and the oldest. */
export function pushRecent(href: string, list: string[] = readRecent()): string[] {
	const next = [href, ...list.filter((h) => h !== href)].slice(0, MAX);
	try {
		localStorage.setItem(KEY, JSON.stringify(next));
	} catch {
		/* private mode: recents just won't persist */
	}
	return next;
}
