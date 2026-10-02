import { browser } from '$app/environment';
import { load, type Datasets } from './data';

/** Start dataset downloads during navigation (and on link hover, via SvelteKit preloading)
 * so pages don't wait to mount before fetching. Components read the same cached promises. */
export function prefetch(...names: (keyof Datasets)[]): Record<string, never> {
	if (browser) for (const n of names) load(n).catch(() => {});
	return {};
}
