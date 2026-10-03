// Shallow URL updates. SvelteKit's `replaceState` changes the address bar but not `page.url`
// (that only follows real navigations), so the next URL must be built from `location.href`:
// building from `page.url` silently drops params written since the last navigation, and
// reading the current value from it never sees the update.
import { replaceState } from '$app/navigation';
import { page } from '$app/state';

/** The address bar as it is right now. */
export function currentUrl(): URL {
	return new URL(location.href);
}

/** Replace the address bar without navigating (no-op when nothing changes). */
export function replaceUrl(next: URL): void {
	if (next.href !== location.href) replaceState(next, page.state);
}

/** Set (or, with null/empty, remove) one search param in place. */
export function setParam(key: string, value: string | null): void {
	const url = currentUrl();
	if (value) url.searchParams.set(key, value);
	else url.searchParams.delete(key);
	replaceUrl(url);
}
