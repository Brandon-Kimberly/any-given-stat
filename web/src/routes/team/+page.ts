import { prefetch, prefetchSeason } from '$lib/prefetch';

export const load = ({ url }: { url: URL }) => {
	prefetchSeason(url, 'team_weeks', 'ratings', 'team_splits');
	return prefetch('teams', 'luck');
};
