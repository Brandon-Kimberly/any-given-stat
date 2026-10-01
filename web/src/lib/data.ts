import { base } from '$app/paths';
import type {
	Luck,
	Meta,
	Predictions,
	QB,
	Rating,
	Receiver,
	Rusher,
	Stability,
	TeamSeason,
	TeamSplit,
	TeamWeek
} from './types';

interface Datasets {
	meta: Meta;
	teams: TeamSeason[];
	team_weeks: TeamWeek[];
	luck: Luck[];
	qbs: QB[];
	receivers: Receiver[];
	rushers: Rusher[];
	stability: Stability;
	predictions: Predictions;
	ratings: Rating[];
	team_splits: TeamSplit[];
}

const cache = new Map<string, Promise<unknown>>();

/** Fetch a pipeline dataset once per page load. */
export function load<K extends keyof Datasets>(name: K): Promise<Datasets[K]> {
	if (!cache.has(name)) {
		const p = fetch(`${base}/data/${name}.json`).then((r) => {
			if (!r.ok) throw new Error(`${name}.json: HTTP ${r.status} — run the pipeline first`);
			return r.json();
		});
		p.catch(() => cache.delete(name));
		cache.set(name, p);
	}
	return cache.get(name) as Promise<Datasets[K]>;
}

export function dataUrl(path: string): string {
	return new URL(`${base}/data/${path}`, location.href).href;
}
