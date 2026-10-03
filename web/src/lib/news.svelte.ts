// Loading the news feed. Under `ags up` the local server's /api/news serves ESPN headlines
// fetched live (10-minute cache) with the last build's injury items; the static site reads
// /data/news.json from the last build. The local API is only asked for once the sync status
// request (sync.svelte.ts) has shown the local server exists, so the static deploy never
// requests a missing /api/news.

import { base } from '$app/paths';
import { loadPath } from './data';
import { sync } from './sync.svelte';
import type { NewsFeed } from './types';

const SYNC_WAIT_MS = 2500;
let pending: Promise<NewsFeed> | null = null;

/** Resolves once the sync status request has answered (or after a short wait). */
async function localServer(): Promise<boolean> {
	sync.start();
	const t0 = Date.now();
	while (sync.available === null && Date.now() - t0 < SYNC_WAIT_MS) {
		await new Promise((r) => setTimeout(r, 30));
	}
	return sync.available === true;
}

async function fetchFeed(): Promise<NewsFeed> {
	if (await localServer()) {
		try {
			const r = await fetch(`${base}/api/news`, { cache: 'no-store' });
			if (r.ok) {
				const feed = (await r.json()) as NewsFeed;
				if (Array.isArray(feed?.items)) return feed;
			}
		} catch {
			/* fall back to the build's file */
		}
	}
	return loadPath<NewsFeed>('news');
}

/** The feed, fetched once per page load and shared by every news component. */
export function loadNews(): Promise<NewsFeed> {
	if (!pending) {
		pending = fetchFeed();
		pending.catch(() => (pending = null));
	}
	return pending;
}

/** `{ value, error }` for the feed, like `resource()`. */
export function newsResource() {
	let value = $state.raw<NewsFeed | undefined>(undefined);
	let error = $state.raw<string | null>(null);
	loadNews()
		.then((v) => (value = v))
		.catch((e) => (error = e instanceof Error ? e.message : String(e)));
	return {
		get value() {
			return value;
		},
		get error() {
			return error;
		}
	};
}
