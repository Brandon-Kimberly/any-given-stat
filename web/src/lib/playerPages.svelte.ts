// Which players have a page, and the directory behind them. Every player with a stat line
// has one (player_index.json): QBs, receivers and rushers get the efficiency page, everyone
// else (kickers, punters, defenders, depth players) a profile built from players/<id>.json.
// Box scores, fantasy tables and rosters check hasPlayerPage before linking a name.

import { load, loadPath } from './data';
import type { PlayerIndexRow, PlayerProfile } from './types';

const HEADSHOT_PREFIXES: Record<string, string> = {
	p: 'https://static.www.nfl.com/image/private/f_auto,q_auto/league/',
	u: 'https://static.www.nfl.com/image/upload/f_auto,q_auto/league/'
};

/** Expand an index headshot ('p:<token>', 'u:<token>' or a full URL). */
export function headshotUrl(h: string | null | undefined): string | null {
	if (!h) return null;
	const m = /^([a-z]):(.+)$/.exec(h);
	return m && HEADSHOT_PREFIXES[m[1]] ? HEADSHOT_PREFIXES[m[1]] + m[2] : h;
}

let indexPromise: Promise<Map<string, PlayerIndexRow>> | null = null;

/** player_index.json by id, loaded once. Before a rebuild writes it, players.json stands in
 * (efficiency players only, as before). */
export function loadPlayerIndex(): Promise<Map<string, PlayerIndexRow>> {
	indexPromise ??= loadPath<PlayerIndexRow[]>('player_index')
		.then((rows) => new Map(rows.map((r) => [r[0], r])))
		.catch(() =>
			load('players').then(
				(rows) =>
					new Map(
						rows.map((p): [string, PlayerIndexRow] => [
							p.player_id,
							[p.player_id, p.name, p.position, '', 0, p.headshot, 1]
						])
					)
			)
		);
	indexPromise.catch(() => (indexPromise = null));
	return indexPromise;
}

/** A profile player's bio and game lines (players/<id>.json). */
export function loadPlayerProfile(id: string): Promise<PlayerProfile> {
	return loadPath<PlayerProfile>(`players/${id}`);
}

let index = $state.raw<Map<string, PlayerIndexRow> | null>(null);
let failed = $state(false);
let started = false;

function start(): void {
	if (started) return;
	started = true;
	loadPlayerIndex()
		.then((m) => (index = m))
		.catch(() => {
			index = new Map();
			failed = true;
		});
}

/** True once the directory has loaded and lists the player (reactive). */
export function hasPlayerPage(id: string): boolean {
	start();
	return index?.has(id) ?? false;
}

/** The directory (reactive): undefined while loading, an empty map if it failed. */
export const playerIndex = {
	get value(): Map<string, PlayerIndexRow> | undefined {
		start();
		return index ?? undefined;
	},
	get failed(): boolean {
		return failed;
	}
};
