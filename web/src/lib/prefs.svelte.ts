import type { Scope } from './types';

/** Page-wide filters shared by every view. The URL wins (shareable links), then the last
 * values this browser used, then defaults. */
export const prefs = $state<{ season: number | null; scope: Scope }>({
	season: null,
	scope: 'no_garbage'
});

const KEY = 'ags-prefs';

export function restorePrefs(url: URL): void {
	try {
		const saved = JSON.parse(localStorage.getItem(KEY) ?? '{}');
		if (typeof saved.season === 'number') prefs.season = saved.season;
		if (saved.scope === 'all' || saved.scope === 'no_garbage') prefs.scope = saved.scope;
	} catch {
		/* storage unavailable: defaults are fine */
	}
	const season = Number(url.searchParams.get('season'));
	if (Number.isInteger(season) && season > 1990) prefs.season = season;
	const scope = url.searchParams.get('scope');
	if (scope === 'all' || scope === 'no_garbage') prefs.scope = scope;
}

export function savePrefs(): void {
	try {
		localStorage.setItem(KEY, JSON.stringify(prefs));
	} catch {
		/* ignore */
	}
}

/** The current URL with season/scope applied, preserving other params (e.g. ?t=KC). */
export function prefsUrl(url: URL): URL {
	const next = new URL(url);
	if (prefs.season != null) next.searchParams.set('season', String(prefs.season));
	if (prefs.scope === 'all') next.searchParams.set('scope', 'all');
	else next.searchParams.delete('scope');
	return next;
}
