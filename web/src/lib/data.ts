import { base } from '$app/paths';
import type {
	Concepts,
	FourthDowns,
	GameIndexEntry,
	Lab,
	Player,
	QBGame,
	TeamMeta,
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

export interface Datasets {
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
	lab: Lab;
	teams_meta: TeamMeta[];
	players: Player[];
	concepts: Concepts;
	fourth_downs: FourthDowns;
	qb_games: QBGame[];
	'games/index': GameIndexEntry[];
}

const cache = new Map<string, Promise<unknown>>();

/** Fetch a pipeline dataset once per page load. */
export function load<K extends keyof Datasets>(name: K): Promise<Datasets[K]> {
	return loadPath(name) as Promise<Datasets[K]>;
}

/** Any JSON file under /data (e.g. a per-season file), cached like named datasets. */
export function loadPath<T = unknown>(name: string): Promise<T> {
	if (!cache.has(name)) {
		const p = fetch(`${base}/data/${name}.json`).then((r) => {
			if (!r.ok) throw new Error(`${name}.json: HTTP ${r.status} — run the pipeline first`);
			return r.json();
		});
		p.catch(() => cache.delete(name));
		cache.set(name, p);
	}
	return cache.get(name) as Promise<T>;
}

export function dataUrl(path: string): string {
	return new URL(`${base}/data/${path}`, location.href).href;
}
