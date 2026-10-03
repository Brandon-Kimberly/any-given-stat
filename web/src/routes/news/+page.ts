import { browser } from '$app/environment';
import { loadNews } from '$lib/news.svelte';

export const load = () => {
	if (browser) loadNews().catch(() => {});
	return {};
};
