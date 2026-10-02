import { prefetch } from '$lib/prefetch';

export const load = () => prefetch('predictions', 'ratings', 'teams');
