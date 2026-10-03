import { browser } from '$app/environment';
import { loadPath } from '$lib/data';
import { prefetch } from '$lib/prefetch';
import { prefs } from '$lib/prefs.svelte';

export const load = ({ url }: { url: URL }) => {
	const season = Number(url.searchParams.get('season')) || prefs.season;
	if (browser && season) loadPath(`fantasy/${season}`).catch(() => {});
	return prefetch('meta');
};
