import type { Scope } from './types';

/** Page-wide filters shared by every view; remembered per browser. */
export const prefs = $state<{ season: number | null; scope: Scope }>({
	season: null,
	scope: 'no_garbage'
});

const KEY = 'ags-prefs';

export function restorePrefs(): void {
	try {
		const saved = JSON.parse(localStorage.getItem(KEY) ?? '{}');
		if (typeof saved.season === 'number') prefs.season = saved.season;
		if (saved.scope === 'all' || saved.scope === 'no_garbage') prefs.scope = saved.scope;
	} catch {
		/* storage unavailable: defaults are fine */
	}
}

export function savePrefs(): void {
	try {
		localStorage.setItem(KEY, JSON.stringify(prefs));
	} catch {
		/* ignore */
	}
}
