import { browser } from '$app/environment';
import { loadPlayerIndex, loadPlayerProfile } from '$lib/playerPages.svelte';
import { prefetch, prefetchSeason } from '$lib/prefetch';

// The directory says which page this player has; start that page's downloads (the index is
// usually cached already: every page that links a player loads it).
export const load = ({ url }: { url: URL }) => {
	if (!browser) return {};
	const id = url.searchParams.get('id') ?? '';
	const efficiency = () => {
		prefetchSeason(url, 'qb_games');
		prefetch('players', 'qbs', 'receivers', 'rushers');
	};
	loadPlayerIndex()
		.then((index) => {
			const kind = index.get(id)?.[6] ?? 1;
			if (kind !== 1) loadPlayerProfile(id).catch(() => {});
			if (kind !== 0) efficiency();
			else prefetchSeason(url, 'fantasy');
		})
		.catch(efficiency);
	return {};
};
