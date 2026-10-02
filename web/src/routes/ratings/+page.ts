import { prefetchSeason } from '$lib/prefetch';

export const load = ({ url }: { url: URL }) => prefetchSeason(url, 'ratings');
