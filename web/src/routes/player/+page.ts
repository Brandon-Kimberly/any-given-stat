import { prefetch, prefetchSeason } from '$lib/prefetch';

export const load = ({ url }: { url: URL }) => {
	prefetchSeason(url, 'qb_games');
	return prefetch('players', 'qbs', 'receivers', 'rushers');
};
