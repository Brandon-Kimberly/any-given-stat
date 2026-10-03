import { prefetch, prefetchSeason } from '$lib/prefetch';

// Home always shows the latest season; prefs.season is the latest unless a visitor picked another.
export const load = ({ url }: { url: URL }) => {
	prefetch('meta', 'upcoming');
	return prefetchSeason(url, 'schedule', 'ratings', 'qb_games', 'playoff_odds');
};
