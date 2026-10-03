import { load, loadPath, type Datasets } from './data';

/** Reactive wrapper around a dataset fetch: `{ value, error }`, for {#if}/{:else} states.
 *
 * Values are `$state.raw`: datasets are thousands of rows that are replaced, never mutated,
 * and deep proxies would put every row read in the render path behind a Proxy trap. */
export function resource<K extends keyof Datasets>(name: K) {
	let value = $state.raw<Datasets[K] | undefined>(undefined);
	let error = $state.raw<string | null>(null);
	load(name)
		.then((v) => {
			value = v;
		})
		.catch((e) => {
			error = e instanceof Error ? e.message : String(e);
		});
	return {
		get value() {
			return value;
		},
		get error() {
			return error;
		}
	};
}

/** Per-season rows from `<dir>/<season>.json`, reloading when `season()` changes. The previous
 * season's rows stay until the next arrive (pages filter by season, so nothing stale shows).
 * A missing file (e.g. no ratings for the first season) reads as no rows. */
export function seasonResource<T extends { season: number }>(
	dir: 'ratings' | 'team_splits' | 'team_weeks' | 'qb_games' | 'schedule',
	season: () => number | null | undefined
) {
	let value = $state.raw<T[] | undefined>(undefined);
	let error = $state.raw<string | null>(null);
	$effect(() => {
		const s = season();
		if (!s) return;
		loadPath<T[]>(`${dir}/${s}`)
			.then((v) => {
				if (season() === s) {
					value = v;
					error = null;
				}
			})
			.catch((e) => {
				if (season() !== s) return;
				value = [];
				const msg = e instanceof Error ? e.message : String(e);
				error = /HTTP 404/.test(msg) ? null : msg;
			});
	});
	return {
		get value() {
			return value;
		},
		get error() {
			return error;
		}
	};
}
