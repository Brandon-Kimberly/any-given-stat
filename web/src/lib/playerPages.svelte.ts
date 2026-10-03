// Which players have a page. /player/ is built from the efficiency datasets (QBs,
// receivers, rushers), so box scores and fantasy tables, which list everyone, must check
// before linking a name. Loads players.json once, on first use.

import { load } from './data';

let ids = $state.raw<Set<string> | null>(null);
let started = false;

function start(): void {
	if (started) return;
	started = true;
	load('players')
		.then((rows) => (ids = new Set(rows.map((r) => r.player_id))))
		.catch(() => (ids = new Set()));
}

/** True once the directory has loaded and lists the player (reactive). */
export function hasPlayerPage(id: string): boolean {
	start();
	return ids?.has(id) ?? false;
}
