import { afterEach, describe, expect, it, vi } from 'vitest';
import sleeperLeague from './fixtures/sleeper_league.json';
import sleeperRosters from './fixtures/sleeper_rosters.json';
import sleeperUsers from './fixtures/sleeper_users.json';
import {
	KEYS,
	buildOwnership,
	currentSeason,
	loadSaved,
	type FantasyLeague,
	type KeyValueStore
} from './league.svelte';
import { PRESETS } from './scoring';
import { SLEEPER_API, type FetchFn } from './sleeper';
import type { FantasyIds } from './statline';

class MemoryStore implements KeyValueStore {
	data = new Map<string, string>();
	getItem(k: string) {
		return this.data.get(k) ?? null;
	}
	setItem(k: string, v: string) {
		this.data.set(k, v);
	}
	removeItem(k: string) {
		this.data.delete(k);
	}
}

const league: FantasyLeague = {
	platform: 'sleeper',
	id: '42',
	season: 2025,
	name: 'L',
	scoring: PRESETS.ppr,
	teams: 2,
	starters: { QB: 1, BN: 5 },
	rosters: [
		{ id: '1', name: 'Alpha', owner: 'a', players: ['4046', 'LA', '777'] },
		{ id: '2', name: 'Beta', owner: 'b', players: ['4881'] }
	],
	fetchedAt: '2026-10-01T00:00:00Z'
};
const ids: FantasyIds = {
	sleeper: { '4046': '00-0033873', '4881': '00-0034796' },
	espn: { '3918298': '00-0033873' }
};

const SID = '1048276153928429568';
const SBASE = `${SLEEPER_API}/league/${SID}`;
const sleeperFetch: FetchFn = async (url) => {
	const body = {
		[SBASE]: sleeperLeague,
		[`${SBASE}/users`]: sleeperUsers,
		[`${SBASE}/rosters`]: sleeperRosters
	}[url];
	return new Response(JSON.stringify(body ?? null), { status: body ? 200 : 404 });
};

describe('buildOwnership', () => {
	it('maps rostered players to gsis ids and defenses to team codes', () => {
		const own = buildOwnership(league, ids, '2');
		expect([...own.keys()].sort()).toEqual(['00-0033873', '00-0034796', 'LA']);
		expect(own.get('LA')).toEqual({ teamId: '1', teamName: 'Alpha', mine: false });
		expect(own.get('00-0034796')).toEqual({ teamId: '2', teamName: 'Beta', mine: true });
		expect(buildOwnership(null, ids, null).size).toBe(0);
		expect(buildOwnership({ ...league, platform: 'espn' }, ids, null).size).toBe(1); // LA only
	});
});

describe('loadSaved', () => {
	it('defaults to half PPR with nothing saved or no storage', () => {
		const empty = { league: null, preset: 'half', myTeam: null, espn: null };
		expect(loadSaved(null)).toEqual(empty);
		expect(loadSaved(new MemoryStore())).toEqual(empty);
	});

	it('restores league, preset, my team and ESPN cookies', () => {
		const s = new MemoryStore();
		s.setItem(KEYS.league, JSON.stringify(league));
		s.setItem(KEYS.preset, 'ppr');
		s.setItem(KEYS.myTeam, '2');
		s.setItem(KEYS.espn, JSON.stringify({ espnS2: 'abc', swid: '{X}' }));
		expect(loadSaved(s)).toEqual({
			league,
			preset: 'ppr',
			myTeam: '2',
			espn: { espnS2: 'abc', swid: '{X}' }
		});
	});

	it('ignores malformed or stale values', () => {
		const s = new MemoryStore();
		s.setItem(KEYS.league, '{not json');
		s.setItem(KEYS.preset, 'superflex');
		s.setItem(KEYS.myTeam, '2');
		expect(loadSaved(s)).toEqual({ league: null, preset: 'half', myTeam: null, espn: null });
		s.setItem(KEYS.league, JSON.stringify({ ...league, rosters: 'x' }));
		expect(loadSaved(s).league).toBeNull();
		const throwing: KeyValueStore = {
			getItem() {
				throw new Error('SecurityError');
			},
			setItem() {},
			removeItem() {}
		};
		expect(loadSaved(throwing).preset).toBe('half');
	});
});

describe('currentSeason', () => {
	it('keeps January and February in the previous season', () => {
		expect(currentSeason(new Date(2027, 0, 20))).toBe(2026);
		expect(currentSeason(new Date(2026, 8, 10))).toBe(2026);
	});
});

describe('fantasy store', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		vi.resetModules();
	});

	it('connects, persists, restores on load and disconnects', async () => {
		const store = new MemoryStore();
		vi.stubGlobal('localStorage', store);
		vi.resetModules();
		const { fantasy } = await import('./league.svelte');
		// resetModules gave the store its own copy of scoring.ts
		const { PRESETS: P } = await import('./scoring');
		expect(fantasy.scoring).toBe(P.half);
		fantasy.preset = 'standard';
		expect(fantasy.scoring).toBe(P.standard);
		expect(store.getItem(KEYS.preset)).toBe('standard');

		const l = await fantasy.connect('sleeper', SID, { fetchFn: sleeperFetch });
		expect(fantasy.league).toBe(l);
		expect(fantasy.scoring).toBe(l.scoring);
		fantasy.myTeam = '1';
		const own = fantasy.ownership(ids);
		expect(own.get('00-0033873')?.mine).toBe(true);
		expect(fantasy.ownership(ids)).toBe(own); // memoized

		// A fresh page load restores everything synchronously.
		vi.resetModules();
		const reloaded = (await import('./league.svelte')).fantasy;
		expect(reloaded.league?.id).toBe(SID);
		expect(reloaded.myTeam).toBe('1');
		expect(reloaded.scoring.sleeper?.bonus_rec_te).toBe(0.5);

		// Refresh keeps my team while it still exists.
		await reloaded.refresh(sleeperFetch);
		expect(reloaded.myTeam).toBe('1');

		reloaded.disconnect();
		expect(reloaded.league).toBeNull();
		expect(reloaded.myTeam).toBeNull();
		expect(reloaded.scoring).toEqual(PRESETS.standard);
		expect(store.getItem(KEYS.league)).toBeNull();
		expect(store.getItem(KEYS.myTeam)).toBeNull();
	});

	it('reports the error when a connect fails', async () => {
		const { fantasy } = await import('./league.svelte');
		const bad: FetchFn = async () => new Response('null');
		await expect(fantasy.connect('sleeper', '123', { fetchFn: bad })).rejects.toThrow();
		expect(fantasy.error).toMatch('No Sleeper league');
		expect(fantasy.loading).toBe(false);
		expect(fantasy.league).toBeNull();
	});

	it('saves ESPN cookies under their own key and sends them on refresh', async () => {
		const store = new MemoryStore();
		vi.stubGlobal('localStorage', store);
		vi.resetModules();
		const { fantasy } = await import('./league.svelte');
		const espnJson = (await import('./fixtures/espn_league.json')).default;
		const seen: Record<string, string>[] = [];
		const fetchFn: FetchFn = async (_url, init) => {
			seen.push(init?.headers as Record<string, string>);
			return new Response(JSON.stringify(espnJson));
		};
		await fantasy.connect('espn', '336358', { season: 2025, espnS2: 's2', swid: '{W}', fetchFn });
		expect(JSON.parse(store.getItem(KEYS.espn) ?? '{}')).toEqual({ espnS2: 's2', swid: '{W}' });
		expect(store.getItem(KEYS.league)).not.toContain('s2'); // cookies never in the league
		await fantasy.refresh(fetchFn);
		expect(seen[1]).toEqual({ 'X-ESPN-S2': 's2', 'X-ESPN-SWID': '{W}' });
		fantasy.disconnect();
		expect(store.getItem(KEYS.espn)).toBeNull();
	});
});
