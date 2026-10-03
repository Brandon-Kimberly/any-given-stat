import { prefetch, prefetchSeason } from '$lib/prefetch';

export const load = ({ url }: { url: URL }) => {
	prefetchSeason(
		url,
		'team_weeks',
		'ratings',
		'team_splits',
		'schedule',
		'playoff_odds',
		'qb_games'
	);
	return prefetch('teams', 'luck', 'upcoming', 'receivers', 'rushers', 'players');
};
