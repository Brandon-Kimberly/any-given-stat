import { load, type Datasets } from './data';

/** Reactive wrapper around a dataset fetch: `{ value, error }`, for {#if}/{:else} states. */
export function resource<K extends keyof Datasets>(name: K) {
	const r = $state<{ value: Datasets[K] | undefined; error: string | null }>({
		value: undefined,
		error: null
	});
	load(name)
		.then((v) => {
			r.value = v;
		})
		.catch((e) => {
			r.error = e instanceof Error ? e.message : String(e);
		});
	return r;
}
