// The visitor's fantasy league (or chosen preset scoring), kept in localStorage so every page
// scores with it from the first paint. Restored synchronously at import.
//
// Keys: ags-fantasy-league (the normalized league), ags-fantasy-preset, ags-fantasy-my-team,
// ags-fantasy-espn (espn_s2 / SWID; only ever sent to the local app's ESPN proxy).

import { base } from '$app/paths';
import { fetchEspnLeague, type EspnAuth } from './espn';
import { PRESETS, isPresetName, type PresetName, type Scoring } from './scoring';
import { fetchSleeperLeague, isTeamCode, type FantasyLeague, type FetchFn } from './sleeper';
import type { FantasyIds } from './statline';

export type { FantasyLeague, FantasyTeam } from './sleeper';
export type { EspnAuth } from './espn';

export const KEYS = {
	league: 'ags-fantasy-league',
	preset: 'ags-fantasy-preset',
	myTeam: 'ags-fantasy-my-team',
	espn: 'ags-fantasy-espn'
} as const;

/** Minimal Storage surface, so tests can pass a fake. */
export type KeyValueStore = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export interface SavedFantasy {
	league: FantasyLeague | null;
	preset: PresetName;
	myTeam: string | null;
	espn: EspnAuth | null;
}

function readJson(store: KeyValueStore, key: string): unknown {
	try {
		const raw = store.getItem(key);
		return raw ? JSON.parse(raw) : null;
	} catch {
		return null;
	}
}

function isLeague(v: unknown): v is FantasyLeague {
	const l = v as FantasyLeague | null;
	return (
		l != null &&
		typeof l === 'object' &&
		(l.platform === 'sleeper' || l.platform === 'espn') &&
		typeof l.id === 'string' &&
		typeof l.season === 'number' &&
		l.scoring != null &&
		typeof l.scoring === 'object' &&
		Array.isArray(l.rosters)
	);
}

/** Read saved state; anything missing or malformed falls back to defaults. */
export function loadSaved(store: KeyValueStore | null): SavedFantasy {
	const out: SavedFantasy = { league: null, preset: 'half', myTeam: null, espn: null };
	if (!store) return out;
	const league = readJson(store, KEYS.league);
	if (isLeague(league)) out.league = league;
	try {
		const p = store.getItem(KEYS.preset);
		if (isPresetName(p)) out.preset = p;
		const t = store.getItem(KEYS.myTeam);
		if (t && out.league?.rosters.some((r) => r.id === t)) out.myTeam = t;
	} catch {
		/* defaults */
	}
	const espn = readJson(store, KEYS.espn) as EspnAuth | null;
	if (espn && typeof espn === 'object') {
		out.espn = {
			espnS2: typeof espn.espnS2 === 'string' ? espn.espnS2 : undefined,
			swid: typeof espn.swid === 'string' ? espn.swid : undefined
		};
	}
	return out;
}

function storage(): KeyValueStore | null {
	try {
		return typeof localStorage === 'undefined' ? null : localStorage;
	} catch {
		return null; // access can throw when storage is blocked
	}
}

function save(key: string, value: string | null): void {
	try {
		const s = storage();
		if (!s) return;
		if (value == null) s.removeItem(key);
		else s.setItem(key, value);
	} catch {
		/* private mode / quota: keep it for this visit only */
	}
}

// ---------- ownership ----------

export interface Owner {
	teamId: string;
	teamName: string;
	mine: boolean;
}

/** gsis id (or team code for defenses) -> the fantasy team rostering that player. Platform
 * ids without a gsis match in `ids` (e.g. players with no stat lines) are skipped. */
export function buildOwnership(
	league: FantasyLeague | null,
	ids: FantasyIds | null,
	myTeam: string | null
): Map<string, Owner> {
	const out = new Map<string, Owner>();
	if (!league) return out;
	const map = ids?.[league.platform] ?? {};
	for (const team of league.rosters) {
		const owner = { teamId: team.id, teamName: team.name, mine: team.id === myTeam };
		for (const pid of team.players) {
			const key = isTeamCode(pid) ? pid : map[pid];
			if (key) out.set(key, owner);
		}
	}
	return out;
}

/** Current NFL season for a date: January-February still belong to the previous season. */
export function currentSeason(now = new Date()): number {
	return now.getMonth() < 2 ? now.getFullYear() - 1 : now.getFullYear();
}

// ---------- store ----------

export interface ConnectOptions extends EspnAuth {
	/** ESPN only: the season to load (default: the current season). */
	season?: number;
	/** Injected in tests. */
	fetchFn?: FetchFn;
}

class FantasyStore {
	league = $state.raw<FantasyLeague | null>(null);
	#preset = $state<PresetName>('half');
	#myTeam = $state<string | null>(null);
	#espn = $state.raw<EspnAuth | null>(null);
	/** A connect/refresh is in flight. */
	loading = $state(false);
	/** The last connect/refresh error message, cleared on success. */
	error = $state<string | null>(null);

	/** The league's scoring when connected, else the chosen preset. */
	scoring: Scoring = $derived(this.league?.scoring ?? PRESETS[this.#preset]);

	#ownCache: {
		league: FantasyLeague | null;
		ids: FantasyIds;
		myTeam: string | null;
		map: Map<string, Owner>;
	} | null = null;

	constructor(saved: SavedFantasy) {
		this.league = saved.league;
		this.#preset = saved.preset;
		this.#myTeam = saved.myTeam;
		this.#espn = saved.espn;
	}

	get preset(): PresetName {
		return this.#preset;
	}
	set preset(p: PresetName) {
		this.#preset = p;
		save(KEYS.preset, p);
	}

	/** The visitor's own team (a FantasyTeam id in the connected league). */
	get myTeam(): string | null {
		return this.#myTeam;
	}
	set myTeam(id: string | null) {
		this.#myTeam = id;
		save(KEYS.myTeam, id);
	}

	/** Saved ESPN cookies (for prefilling the form; never shown in full). */
	get espnAuth(): EspnAuth | null {
		return this.#espn;
	}

	async connect(platform: 'sleeper' | 'espn', id: string, opts: ConnectOptions = {}) {
		this.loading = true;
		this.error = null;
		try {
			let league: FantasyLeague;
			if (platform === 'sleeper') {
				league = await fetchSleeperLeague(id, opts.fetchFn);
			} else {
				const auth: EspnAuth = {
					espnS2: opts.espnS2 ?? this.#espn?.espnS2,
					swid: opts.swid ?? this.#espn?.swid
				};
				league = await fetchEspnLeague(
					id,
					opts.season ?? currentSeason(),
					{ ...auth, base },
					opts.fetchFn
				);
				const has = auth.espnS2 || auth.swid;
				this.#espn = has ? auth : null;
				save(KEYS.espn, has ? JSON.stringify(auth) : null);
			}
			const same = this.league?.platform === league.platform && this.league.id === league.id;
			this.league = league;
			save(KEYS.league, JSON.stringify(league));
			if (!same || !league.rosters.some((r) => r.id === this.#myTeam)) this.myTeam = null;
			return league;
		} catch (e) {
			this.error = e instanceof Error ? e.message : String(e);
			throw e;
		} finally {
			this.loading = false;
		}
	}

	/** Re-fetch the connected league (rosters change weekly). */
	async refresh(fetchFn?: FetchFn) {
		const l = this.league;
		if (!l) return null;
		return this.connect(l.platform, l.id, { season: l.season, fetchFn });
	}

	/** Forget the league, my team and any ESPN cookies; scoring falls back to the preset. */
	disconnect(): void {
		this.league = null;
		this.myTeam = null;
		this.#espn = null;
		this.error = null;
		save(KEYS.league, null);
		save(KEYS.espn, null);
	}

	/** buildOwnership for the connected league, memoized on its inputs. */
	ownership(ids: FantasyIds): Map<string, Owner> {
		const c = this.#ownCache;
		const league = this.league;
		const myTeam = this.#myTeam;
		if (c && c.league === league && c.ids === ids && c.myTeam === myTeam) return c.map;
		const map = buildOwnership(league, ids, myTeam);
		this.#ownCache = { league, ids, myTeam, map };
		return map;
	}
}

export const fantasy = new FantasyStore(loadSaved(storage()));
