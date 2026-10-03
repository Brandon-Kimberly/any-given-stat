// ESPN league connector.
//
// ESPN's fantasy API sends no CORS headers, so the browser can't call it directly: requests go
// through the local app's proxy (`GET /api/espn/league`, pipeline/src/ags/serve.py), which
// forwards the espn_s2 / SWID cookies a private league needs. On the static site (or
// `npm run dev`) there is no proxy, and the error says to use the local app.

import { ESPN_PRO_TEAMS } from './espnStats';
import type { EspnScoringItem } from './scoring';
import {
	countSlots,
	defaultFetch,
	type FantasyLeague,
	type FantasyTeam,
	type FetchFn
} from './sleeper';

export interface EspnAuth {
	espnS2?: string;
	swid?: string;
}

export interface EspnOptions extends EspnAuth {
	/** URL prefix of the local app (SvelteKit `base`); '' by default. */
	base?: string;
}

const LOCAL_APP =
	'ESPN leagues need the local app, which can reach ESPN for you: run .\\start.cmd (Windows) or ./start.sh, then connect from the page it opens.';
const PRIVATE =
	'This ESPN league is private. Add your espn_s2 and SWID cookies: on espn.com, open your browser dev tools, Application (Storage in Firefox) > Cookies > https://www.espn.com, and copy the values of espn_s2 and SWID.';

/** ESPN lineup slot id -> our slot names (null = not counted). */
export const ESPN_LINEUP_SLOTS: Record<number, string | null> = {
	0: 'QB',
	2: 'RB',
	3: 'FLEX', // RB/WR
	4: 'WR',
	5: 'FLEX', // WR/TE
	6: 'TE',
	7: 'SUPER_FLEX', // OP
	8: 'DL', // DT
	9: 'DL', // DE
	10: 'LB',
	11: 'DL',
	12: 'DB', // CB
	13: 'DB', // S
	14: 'DB',
	15: 'IDP_FLEX', // DP
	16: 'DEF',
	17: 'K',
	18: 'P',
	20: 'BN',
	21: null, // IR
	23: 'FLEX' // RB/WR/TE
};

/** ESPN D/ST player ids are -16000 - proTeamId; normalize them to our team codes. */
export function espnPlayerId(id: number): string {
	if (id < 0) {
		const team = ESPN_PRO_TEAMS[-16000 - id];
		if (team) return team;
	}
	return String(id);
}

interface EspnLeagueJson {
	id: number;
	seasonId: number;
	settings?: {
		name?: string;
		size?: number;
		scoringSettings?: { scoringItems?: EspnScoringItem[] };
		rosterSettings?: { lineupSlotCounts?: Record<string, number> };
	};
	teams?: {
		id: number;
		abbrev?: string;
		name?: string;
		location?: string;
		nickname?: string;
		owners?: string[];
		primaryOwner?: string;
		roster?: { entries?: { playerId: number }[] };
	}[];
	members?: { id: string; displayName?: string; firstName?: string; lastName?: string }[];
}

export function normalizeEspnLeague(json: EspnLeagueJson, fallbackSeason: number): FantasyLeague {
	const s = json.settings ?? {};
	const members = new Map((json.members ?? []).map((m) => [m.id, m]));
	const rosters: FantasyTeam[] = (json.teams ?? []).map((t) => {
		const m = members.get(t.owners?.[0] ?? t.primaryOwner ?? '');
		const owner = m?.displayName || [m?.firstName, m?.lastName].filter(Boolean).join(' ') || '';
		const name =
			t.name || [t.location, t.nickname].filter(Boolean).join(' ').trim() || t.abbrev || '';
		return {
			id: String(t.id),
			name: name || `Team ${t.id}`,
			owner,
			players: (t.roster?.entries ?? []).map((e) => espnPlayerId(e.playerId))
		};
	});
	const slots: (string | null)[] = [];
	for (const [slot, count] of Object.entries(s.rosterSettings?.lineupSlotCounts ?? {})) {
		const name = ESPN_LINEUP_SLOTS[Number(slot)] ?? null;
		for (let i = 0; i < count; i++) slots.push(name);
	}
	const items = (s.scoringSettings?.scoringItems ?? []).map((i) => ({
		statId: i.statId,
		points: i.points ?? 0,
		...(i.pointsOverrides && Object.keys(i.pointsOverrides).length
			? { pointsOverrides: { ...i.pointsOverrides } }
			: {})
	}));
	const name = s.name || `ESPN league ${json.id}`;
	return {
		platform: 'espn',
		id: String(json.id),
		season: json.seasonId ?? fallbackSeason,
		name,
		scoring: { platform: 'espn', label: name, espn: items },
		teams: s.size ?? rosters.length,
		starters: countSlots(slots),
		rosters,
		fetchedAt: new Date().toISOString()
	};
}

export async function fetchEspnLeague(
	id: string,
	season: number,
	opts: EspnOptions = {},
	fetchFn: FetchFn = defaultFetch
): Promise<FantasyLeague> {
	const leagueId = id.trim();
	if (!/^\d{1,15}$/.test(leagueId)) {
		throw new Error('An ESPN league ID is a number: the leagueId=… part of the league URL.');
	}
	if (!Number.isInteger(season) || season < 1000 || season > 9999) {
		throw new Error(`Bad season: ${season}.`);
	}
	const headers: Record<string, string> = {};
	if (opts.espnS2?.trim()) headers['X-ESPN-S2'] = opts.espnS2.trim();
	if (opts.swid?.trim()) headers['X-ESPN-SWID'] = opts.swid.trim();
	const url = `${opts.base ?? ''}/api/espn/league?id=${leagueId}&season=${season}`;

	let res: Response;
	try {
		res = await fetchFn(url, { headers, cache: 'no-store' });
	} catch {
		throw new Error(LOCAL_APP);
	}
	let body: unknown;
	try {
		body = await res.json();
	} catch {
		throw new Error(LOCAL_APP); // an HTML page: no proxy here
	}
	const err = body as { error?: string; source?: string } | null;
	if (!res.ok || err?.error) {
		// Only the proxy's own ESPN errors carry source 'espn'; anything else means no proxy.
		if (err?.source !== 'espn') throw new Error(LOCAL_APP);
		if (res.status === 401 || res.status === 403) throw new Error(PRIVATE);
		if (res.status === 404) throw new Error(`No ESPN league with ID ${leagueId} in ${season}.`);
		throw new Error(`Couldn't load the league from ESPN (${err.error ?? `HTTP ${res.status}`}).`);
	}
	const json = body as EspnLeagueJson;
	if (!json || typeof json !== 'object' || json.id == null) {
		throw new Error(`No ESPN league with ID ${leagueId} in ${season}.`);
	}
	return normalizeEspnLeague(json, season);
}
