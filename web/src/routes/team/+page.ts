import { prefetch } from '$lib/prefetch';

export const load = () => prefetch('teams', 'team_weeks', 'luck', 'ratings', 'team_splits');
