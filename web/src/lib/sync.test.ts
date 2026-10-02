import { describe, expect, it } from 'vitest';
import { agoShort, inShort, isRunning, pollDelay, type SyncStatus } from './sync.svelte';

const now = Date.parse('2026-10-04T17:00:00Z');
const status = (over: Partial<SyncStatus>): SyncStatus => ({
	available: true,
	state: 'idle',
	stage: '',
	trigger: null,
	started_at: null,
	finished_at: null,
	last_success_at: null,
	last_result: null,
	message: '',
	log_tail: [],
	settings: { auto: 'off', interval_minutes: 15 },
	next_auto_at: null,
	seasons: '2016-2026',
	...over
});

describe('sync helpers', () => {
	it('polls fast while running or just before an auto-sync', () => {
		expect(isRunning(status({ state: 'building' }))).toBe(true);
		expect(pollDelay(status({ state: 'downloading' }), now)).toBe(2000);
		expect(pollDelay(status({}), now)).toBe(60_000);
		const soon = new Date(now + 10_000).toISOString();
		expect(pollDelay(status({ next_auto_at: soon }), now)).toBe(11_000);
		const past = new Date(now - 10_000).toISOString();
		expect(pollDelay(status({ next_auto_at: past }), now)).toBe(2000);
		expect(pollDelay(null, now)).toBe(60_000);
	});
	it('formats relative times', () => {
		expect(agoShort(null, now)).toBe('never');
		expect(agoShort(new Date(now - 20_000).toISOString(), now)).toBe('just now');
		expect(agoShort(new Date(now - 5 * 60_000).toISOString(), now)).toBe('5 min ago');
		expect(agoShort(new Date(now - 3 * 3600_000).toISOString(), now)).toBe('3 h ago');
		expect(agoShort(new Date(now - 72 * 3600_000).toISOString(), now)).toBe('3 days ago');
		expect(inShort(new Date(now + 4 * 60_000).toISOString(), now)).toBe('in 4 min');
		expect(inShort(new Date(now - 60_000).toISOString(), now)).toBe('now');
	});
});
