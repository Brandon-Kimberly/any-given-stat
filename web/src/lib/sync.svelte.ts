// Local data sync (`uv run ags up` serves /api/*). On the static public site the API
// doesn't exist: the first status request fails, `available` turns false and polling stops.

import { base } from '$app/paths';
import { hosted } from './hosted';
import { toast } from '$lib/toast.svelte';

export type SyncState = 'idle' | 'checking' | 'downloading' | 'building' | 'error';
export type AutoMode = 'off' | 'interval' | 'gameday';
export type SyncResult = 'updated' | 'up_to_date' | 'error';

export interface SyncSettings {
	auto: AutoMode;
	interval_minutes: number;
}

export interface SyncStatus {
	available: true;
	state: SyncState;
	stage: string;
	trigger: 'manual' | 'auto' | null;
	started_at: string | null;
	finished_at: string | null;
	last_success_at: string | null;
	last_result: SyncResult | null;
	message: string;
	log_tail: string[];
	settings: SyncSettings;
	next_auto_at: string | null;
	seasons: string;
}

export const INTERVALS = [5, 10, 15, 30, 60, 180] as const;
const FAST_MS = 2000;
const SLOW_MS = 60_000;

export function isRunning(s: SyncStatus | null): boolean {
	return (
		s != null && (s.state === 'checking' || s.state === 'downloading' || s.state === 'building')
	);
}

/** Delay before the next status poll: fast while a sync runs or an auto-sync is about to. */
export function pollDelay(s: SyncStatus | null, now = Date.now()): number {
	if (isRunning(s)) return FAST_MS;
	const next = s?.next_auto_at ? new Date(s.next_auto_at).getTime() - now : Infinity;
	return Math.max(FAST_MS, Math.min(SLOW_MS, next + 1000));
}

/** "5 min ago", "3 h ago", "2 days ago". */
export function agoShort(iso: string | null | undefined, now = Date.now()): string {
	if (!iso) return 'never';
	const mins = Math.round((now - new Date(iso).getTime()) / 60000);
	if (mins < 1) return 'just now';
	if (mins < 60) return `${mins} min ago`;
	const hrs = Math.round(mins / 60);
	if (hrs < 48) return `${hrs} h ago`;
	return `${Math.round(hrs / 24)} days ago`;
}

/** "in 4 min", "in 2 h" (or "now"). */
export function inShort(iso: string | null | undefined, now = Date.now()): string {
	if (!iso) return '';
	const mins = Math.round((new Date(iso).getTime() - now) / 60000);
	if (mins < 1) return 'now';
	if (mins < 60) return `in ${mins} min`;
	return `in ${Math.round(mins / 60)} h`;
}

class SyncStore {
	/** null until the first status request answers. */
	available = $state<boolean | null>(null);
	status = $state.raw<SyncStatus | null>(null);
	/** A request (sync start / settings) is in flight. */
	pending = $state(false);
	running = $derived(isRunning(this.status));

	#timer: ReturnType<typeof setTimeout> | undefined;
	#started = false;
	#seenFinished: string | null | undefined = undefined;

	start(): void {
		if (this.#started || typeof window === 'undefined') return;
		this.#started = true;
		if (hosted) {
			this.available = false; // no local server on the public site
			return;
		}
		void this.poll();
	}

	async poll(): Promise<void> {
		clearTimeout(this.#timer);
		try {
			const r = await fetch(`${base}/api/status`, { cache: 'no-store' });
			if (!r.ok) throw new Error(`HTTP ${r.status}`);
			const s = (await r.json()) as SyncStatus;
			if (s?.available !== true) throw new Error('no sync server');
			this.#accept(s);
		} catch {
			// Static hosting (or the local server stopped): hide the control, stop polling.
			if (this.available !== true) {
				this.available = false;
				return;
			}
		}
		this.#timer = setTimeout(() => this.poll(), pollDelay(this.status));
	}

	#accept(s: SyncStatus): void {
		const first = this.#seenFinished === undefined;
		const finishedNow = !first && s.finished_at != null && s.finished_at !== this.#seenFinished;
		this.#seenFinished = s.finished_at;
		this.available = true;
		this.status = s;
		if (finishedNow && !isRunning(s)) this.#announce(s);
	}

	#announce(s: SyncStatus): void {
		const manual = s.trigger !== 'auto';
		if (s.last_result === 'updated') {
			toast.show('Data updated — reloading', 4000, 'ok');
			setTimeout(() => location.reload(), 1200);
		} else if (s.last_result === 'up_to_date' && manual) {
			toast.show('Already up to date', 2200, 'ok');
		} else if (s.last_result === 'error' && manual) {
			toast.show(s.message || 'Sync failed', 5000, 'error');
		}
	}

	async #post(path: string, body: unknown): Promise<Response | null> {
		this.pending = true;
		try {
			return await fetch(`${base}/api/${path}`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
		} catch {
			toast.show('Sync server not reachable: is `ags up` still running?', 5000, 'error');
			return null;
		} finally {
			this.pending = false;
		}
	}

	async syncNow(force = false): Promise<void> {
		const r = await this.#post('sync', { force });
		if (!r) return;
		if (r.ok || r.status === 409) {
			const s = (await r.json()) as SyncStatus;
			if (r.status === 409) toast.show('A sync is already running');
			this.status = s;
		} else {
			toast.show(`Sync could not start (HTTP ${r.status})`, 3000, 'error');
		}
		void this.poll();
	}

	async saveSettings(update: Partial<SyncSettings>): Promise<void> {
		const r = await this.#post('settings', update);
		if (!r) return;
		if (r.ok) {
			this.status = (await r.json()) as SyncStatus;
			void this.poll();
		} else {
			const err = await r.json().catch(() => ({}));
			toast.show(`Settings not saved: ${err.error ?? `HTTP ${r.status}`}`, 3000, 'error');
		}
	}
}

export const sync = new SyncStore();
