import { prefetch } from '$lib/prefetch';

export const load = () =>
	prefetch('predictions', 'luck', 'qbs', 'stability', 'games/index', 'playoff_odds/index');
