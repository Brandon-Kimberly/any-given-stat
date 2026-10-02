import { prefetch } from '$lib/prefetch';

export const load = () => prefetch('players', 'qbs', 'receivers', 'rushers');
