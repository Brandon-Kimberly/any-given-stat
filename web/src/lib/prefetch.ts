import { browser } from '$app/environment';
import { load, loadPath, type Datasets } from './data';
import { prefs } from './prefs.svelte';

/** Start dataset downloads during navigation (and on link hover, via SvelteKit preloading)
 * so pages don't wait to mount before fetching. Components read the same cached promises. */
export function prefetch(...names: (keyof Datasets)[]): Record<string, never> {
	if (browser) for (const n of names) load(n).catch(() => {});
	return {};
}

/** Prefetch per-season files for the season the URL asks for (else the current one). */
export function prefetchSeason(url: URL, ...dirs: string[]): Record<string, never> {
	const season = Number(url.searchParams.get('season')) || prefs.season;
	if (browser && season) for (const d of dirs) loadPath(`${d}/${season}`).catch(() => {});
	return {};
}
