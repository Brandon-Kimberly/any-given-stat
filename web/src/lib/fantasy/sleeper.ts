// Sleeper league connector, plus the normalized league shape both connectors return.
//
// Sleeper's API is public and CORS-open, so this runs in the browser on the static site too.
// https://docs.sleeper.com: GET /league/{id}, /league/{id}/users, /league/{id}/rosters.

import type { Scoring } from './scoring';

export interface FantasyTeam {
	id: string;
	name: string;
	owner: string;
	/** Platform player ids; team defenses normalized to our team codes ('DET', 'LA'). */
	players: string[];
}

export interface FantasyLeague {
	platform: 'sleeper' | 'espn';
	id: string;
	season: number;
	name: string;
	scoring: Scoring;
	/** League size (number of teams). */
	teams: number;
	/** Lineup slot counts, normalized: QB RB WR TE FLEX SUPER_FLEX K DEF DL LB DB IDP_FLEX
	 * (and P), plus BN = bench size. The starting lineup is every slot except BN; IR and taxi
	 * slots are left out. */
	starters: Record<string, number>;
	rosters: FantasyTeam[];
	fetchedAt: string;
}

export type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;
// Wrapped so the global is never called with a foreign `this` (Illegal invocation).
export const defaultFetch: FetchFn = (input, init) => fetch(input, init);

export const SLEEPER_API = 'https://api.sleeper.app/v1';

/** Other platforms' team abbreviations -> ours (nflverse codes). */
const TEAM_CODES: Record<string, string> = {
	LAR: 'LA',
	STL: 'LA',
	WSH: 'WAS',
	JAC: 'JAX',
	OAK: 'LV',
	SD: 'LAC'
};

export function normalizeTeamCode(code: string): string {
	const c = code.toUpperCase();
	return TEAM_CODES[c] ?? c;
}

/** Team-defense ids are team codes; player ids are numeric. */
export const isTeamCode = (id: string): boolean => /^[A-Za-z]{2,3}$/.test(id);

/** Sleeper roster_positions -> our slot names (null = not a lineup slot we count). */
export function sleeperSlot(pos: string): string | null {
	switch (pos) {
		case 'FLEX':
		case 'WRRB_FLEX':
		case 'REC_FLEX':
			return 'FLEX';
		case 'SUPER_FLEX':
			return 'SUPER_FLEX';
		case 'IDP_FLEX':
			return 'IDP_FLEX';
		case 'DE':
		case 'DT':
			return 'DL';
		case 'CB':
		case 'S':
			return 'DB';
		case 'IR':
		case 'TAXI':
			return null;
		default:
			return pos;
	}
}

export function countSlots(slots: (string | null)[]): Record<string, number> {
	const out: Record<string, number> = {};
	for (const s of slots) if (s) out[s] = (out[s] ?? 0) + 1;
	return out;
}

interface SleeperLeagueJson {
	league_id: string;
	name: string;
	season: string;
	total_rosters?: number;
	roster_positions?: string[];
	scoring_settings?: Record<string, number>;
}
interface SleeperUserJson {
	user_id: string;
	display_name?: string;
	metadata?: { team_name?: string } | null;
}
interface SleeperRosterJson {
	roster_id: number;
	owner_id: string | null;
	players: string[] | null;
}

async function getJson<T>(url: string, fetchFn: FetchFn): Promise<T | null> {
	let res: Response;
	try {
		res = await fetchFn(url);
	} catch {
		throw new Error("Couldn't reach Sleeper. Check your connection and try again.");
	}
	if (res.status === 404) return null;
	if (!res.ok) throw new Error(`Sleeper answered HTTP ${res.status}. Try again in a minute.`);
	try {
		return (await res.json()) as T | null;
	} catch {
		throw new Error('Sleeper sent an unreadable response. Try again in a minute.');
	}
}

export async function fetchSleeperLeague(
	id: string,
	fetchFn: FetchFn = defaultFetch
): Promise<FantasyLeague> {
	const leagueId = id.trim();
	if (!/^\d{1,30}$/.test(leagueId)) {
		throw new Error(
			'A Sleeper league ID is a long number: the digits after /leagues/ in the league URL.'
		);
	}
	const base = `${SLEEPER_API}/league/${leagueId}`;
	const league = await getJson<SleeperLeagueJson>(base, fetchFn);
	if (!league || !league.league_id) throw new Error(`No Sleeper league with ID ${leagueId}.`);
	const [users, rosters] = await Promise.all([
		getJson<SleeperUserJson[]>(`${base}/users`, fetchFn),
		getJson<SleeperRosterJson[]>(`${base}/rosters`, fetchFn)
	]);

	const byUser = new Map((users ?? []).map((u) => [u.user_id, u]));
	const teams: FantasyTeam[] = (rosters ?? []).map((r) => {
		const u = r.owner_id ? byUser.get(r.owner_id) : undefined;
		const owner = u?.display_name ?? '';
		return {
			id: String(r.roster_id),
			name: u?.metadata?.team_name || owner || `Team ${r.roster_id}`,
			owner,
			players: (r.players ?? []).map((p) => (isTeamCode(p) ? normalizeTeamCode(p) : p))
		};
	});

	return {
		platform: 'sleeper',
		id: league.league_id,
		season: Number(league.season),
		name: league.name || `Sleeper league ${leagueId}`,
		scoring: {
			platform: 'sleeper',
			label: league.name || 'Sleeper league',
			sleeper: { ...(league.scoring_settings ?? {}) }
		},
		teams: league.total_rosters ?? teams.length,
		starters: countSlots((league.roster_positions ?? []).map(sleeperSlot)),
		rosters: teams,
		fetchedAt: new Date().toISOString()
	};
}
