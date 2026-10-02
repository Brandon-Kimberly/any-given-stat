import { load, type Datasets } from './data';

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
