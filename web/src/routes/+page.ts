import { prefetch } from '$lib/prefetch';

export const load = () => prefetch('ratings', 'predictions', 'luck', 'qbs', 'stability');
