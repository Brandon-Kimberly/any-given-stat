import { prefetch } from '$lib/prefetch';
import { loadPath } from '$lib/data';
import { browser } from '$app/environment';

export const load = ({ url }: { url: URL }) => {
	const season = Number(url.searchParams.get('id')?.slice(0, 4));
	if (browser && season) loadPath(`ratings/${season}`).catch(() => {});
	return prefetch('predictions', 'teams');
};
