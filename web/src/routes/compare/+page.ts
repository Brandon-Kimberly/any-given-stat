import { prefetch } from '$lib/prefetch';

export const load = () => prefetch('teams', 'predictions');
