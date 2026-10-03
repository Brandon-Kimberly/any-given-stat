import { describe, expect, it } from 'vitest';
import { espnPlayerId, fetchEspnLeague } from './espn';
import espnJson from './fixtures/espn_league.json';
import sleeperLeague from './fixtures/sleeper_league.json';
import sleeperRosters from './fixtures/sleeper_rosters.json';
import sleeperUsers from './fixtures/sleeper_users.json';
import { scoreLine, unsupported } from './scoring';
import { SLEEPER_API, fetchSleeperLeague, type FetchFn } from './sleeper';

type Reply = { status?: number; body: unknown } | Error;

/** A fetch that answers from a url -> reply table and records each call. */
function fakeFetch(routes: Record<string, Reply>) {
	const calls: { url: string; init?: RequestInit }[] = [];
	const fn: FetchFn = async (url, init) => {
		calls.push({ url, init });
		const r = routes[url];
		if (!r) return new Response('<!doctype html><p>Not found</p>', { status: 404 });
		if (r instanceof Error) throw r;
		const body = typeof r.body === 'string' ? r.body : JSON.stringify(r.body);
		return new Response(body, { status: r.status ?? 200 });
	};
	return { fn, calls };
}

const SID = '1048276153928429568';
const SBASE = `${SLEEPER_API}/league/${SID}`;
const sleeperRoutes = (): Record<string, Reply> => ({
	[SBASE]: { body: sleeperLeague },
	[`${SBASE}/users`]: { body: sleeperUsers },
	[`${SBASE}/rosters`]: { body: sleeperRosters }
});

describe('fetchSleeperLeague', () => {
	it('normalizes a league', async () => {
		const { fn, calls } = fakeFetch(sleeperRoutes());
		const league = await fetchSleeperLeague(` ${SID} `, fn);
		expect(calls.map((c) => c.url).sort()).toEqual(
			[SBASE, `${SBASE}/rosters`, `${SBASE}/users`].sort()
		);
		expect(league).toMatchObject({
			platform: 'sleeper',
			id: SID,
			season: 2025,
			name: 'Dynasty Degenerates',
			teams: 4,
			starters: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, SUPER_FLEX: 1, K: 1, DEF: 1, BN: 3 }
		});
		expect(league.rosters).toEqual([
			{ id: '1', name: "Greg's Gang", owner: 'gridirongreg', players: ['4046', '6794', 'LA'] },
			{ id: '2', name: 'fantasyfran', owner: 'fantasyfran', players: ['4881', 'DET'] },
			{ id: '3', name: 'noname', owner: 'noname', players: [] },
			{ id: '4', name: 'Team 4', owner: '', players: ['9999'] }
		]);
		expect(new Date(league.fetchedAt).getTime()).not.toBeNaN();
		// The league's own scoring: TE premium + 100-yard bonus.
		const te = { rec: 8, rec_yd: 104, rec_td: 1 };
		expect(scoreLine(te, 'TE', league.scoring)).toBe(31.4); // 8 + 4 + 10.4 + 6 + 3
		expect(unsupported(league.scoring)).toEqual(['def_st_ff', 'rush_rz_att']);
	});

	it('explains a bad or unknown league id', async () => {
		const { fn, calls } = fakeFetch({ [`${SLEEPER_API}/league/123`]: { body: null } });
		await expect(fetchSleeperLeague('123', fn)).rejects.toThrow('No Sleeper league with ID 123');
		await expect(fetchSleeperLeague('404', fn)).rejects.toThrow('No Sleeper league with ID 404');
		await expect(fetchSleeperLeague('abc/../x', fn)).rejects.toThrow('long number');
		expect(calls.map((c) => c.url)).toEqual([
			`${SLEEPER_API}/league/123`,
			`${SLEEPER_API}/league/404`
		]);
	});

	it('reports network and server errors', async () => {
		const down = fakeFetch({ [SBASE]: new TypeError('Failed to fetch') });
		await expect(fetchSleeperLeague(SID, down.fn)).rejects.toThrow("Couldn't reach Sleeper");
		const busy = fakeFetch({ ...sleeperRoutes(), [SBASE]: { status: 503, body: 'busy' } });
		await expect(fetchSleeperLeague(SID, busy.fn)).rejects.toThrow('HTTP 503');
	});
});

const EURL = '/api/espn/league?id=336358&season=2025';

describe('fetchEspnLeague', () => {
	it('normalizes a league through the local proxy', async () => {
		const { fn, calls } = fakeFetch({ [`/base${EURL}`]: { body: espnJson } });
		const league = await fetchEspnLeague(
			'336358',
			2025,
			{ base: '/base', espnS2: ' AEB%2Fx%3D ', swid: '{ABC-123}' },
			fn
		);
		expect(calls[0].init?.headers).toEqual({
			'X-ESPN-S2': 'AEB%2Fx%3D',
			'X-ESPN-SWID': '{ABC-123}'
		});
		expect(league).toMatchObject({
			platform: 'espn',
			id: '336358',
			season: 2025,
			name: 'Office League',
			teams: 3,
			starters: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, DEF: 1, K: 1, BN: 7 }
		});
		expect(league.starters).not.toHaveProperty('SUPER_FLEX'); // OP slot count 0
		expect(league.rosters).toEqual([
			{ id: '1', name: 'Taco Corp', owner: 'taco_tuesday', players: ['3918298', 'DET'] },
			{ id: '2', name: 'Bear Necessities', owner: 'Ben Ruiz', players: ['4241389', 'LA', 'WAS'] },
			{ id: '3', name: 'EMPT', owner: '', players: [] }
		]);
		expect(league.scoring.platform).toBe('espn');
		expect(league.scoring.espn?.find((i) => i.statId === 53)).toEqual({
			statId: 53,
			points: 1,
			pointsOverrides: { '6': 1.5 }
		});
	});

	it('sends no cookie headers when none are given', async () => {
		const { fn, calls } = fakeFetch({ [EURL]: { body: espnJson } });
		await fetchEspnLeague('336358', 2025, {}, fn);
		expect(calls[0].init?.headers).toEqual({});
	});

	it('maps D/ST ids to our team codes', () => {
		expect(espnPlayerId(-16008)).toBe('DET');
		expect(espnPlayerId(-16014)).toBe('LA');
		expect(espnPlayerId(-16028)).toBe('WAS');
		expect(espnPlayerId(-16033)).toBe('BAL');
		expect(espnPlayerId(3918298)).toBe('3918298');
	});

	it('explains private, missing and unreachable leagues', async () => {
		const espnErr = (status: number) => ({
			status,
			body: { error: `ESPN answered HTTP ${status}`, source: 'espn', status }
		});
		const priv = fakeFetch({ [EURL]: espnErr(401) });
		await expect(fetchEspnLeague('336358', 2025, {}, priv.fn)).rejects.toThrow(/private.*espn_s2/);
		const forbidden = fakeFetch({ [EURL]: espnErr(403) });
		await expect(fetchEspnLeague('336358', 2025, {}, forbidden.fn)).rejects.toThrow('private');
		const missing = fakeFetch({ [EURL]: espnErr(404) });
		await expect(fetchEspnLeague('336358', 2025, {}, missing.fn)).rejects.toThrow(
			'No ESPN league with ID 336358 in 2025'
		);
		const down = fakeFetch({ [EURL]: espnErr(502) });
		await expect(fetchEspnLeague('336358', 2025, {}, down.fn)).rejects.toThrow("Couldn't load");
	});

	it('says ESPN needs the local app when there is no proxy', async () => {
		// Static hosting: an HTML 404. Dev server: an HTML SPA page with 200. Older local server:
		// a JSON 404 without source 'espn'. Offline: a network error.
		const cases: Record<string, Reply>[] = [
			{},
			{ [EURL]: { status: 200, body: '<!doctype html><html></html>' } },
			{ [EURL]: { status: 404, body: { error: 'not found' } } },
			{ [EURL]: new TypeError('Failed to fetch') }
		];
		for (const routes of cases) {
			const { fn } = fakeFetch(routes);
			await expect(fetchEspnLeague('336358', 2025, {}, fn)).rejects.toThrow(/start\.cmd/);
		}
	});

	it('validates the id and season before calling anything', async () => {
		const { fn, calls } = fakeFetch({});
		await expect(fetchEspnLeague('12&x=1', 2025, {}, fn)).rejects.toThrow('ESPN league ID');
		await expect(fetchEspnLeague('123', 25, {}, fn)).rejects.toThrow('season');
		expect(calls).toEqual([]);
	});
});
