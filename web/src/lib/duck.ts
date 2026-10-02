// Lazy DuckDB-WASM singleton for the SQL explorer. Engine files are bundled
// (self-hosted) so the explorer has no third-party CDN dependency.
import * as duckdb from '@duckdb/duckdb-wasm';
import ehWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url';
import mvpWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';
import ehWasm from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url';
import mvpWasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';
import { dataUrl } from './data';

const BUNDLES: duckdb.DuckDBBundles = {
	mvp: { mainModule: mvpWasm, mainWorker: mvpWorker },
	eh: { mainModule: ehWasm, mainWorker: ehWorker }
};

let dbPromise: Promise<duckdb.AsyncDuckDB> | null = null;
const registered = new Set<string>();

async function init(): Promise<duckdb.AsyncDuckDB> {
	const bundle = await duckdb.selectBundle(BUNDLES);
	const worker = new Worker(bundle.mainWorker!);
	const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), worker);
	await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
	return db;
}

export function getDb(): Promise<duckdb.AsyncDuckDB> {
	dbPromise ??= init().catch((e) => {
		dbPromise = null;
		throw e;
	});
	return dbPromise;
}

/** Point the `pbp` view at the given explorer parquet files (paths relative to /data). */
export async function usePbp(files: string[]): Promise<void> {
	const db = await getDb();
	for (const f of files) {
		if (registered.has(f)) continue;
		await db.registerFileURL(f, dataUrl(f), duckdb.DuckDBDataProtocol.HTTP, false);
		registered.add(f);
	}
	const conn = await db.connect();
	try {
		const list = files.map((f) => `'${f}'`).join(', ');
		await conn.query(
			`create or replace view pbp as select * from read_parquet([${list}], union_by_name = true)`
		);
	} catch (e) {
		// DuckDB-WASM downloads its parquet reader from extensions.duckdb.org on first use.
		const msg = e instanceof Error ? e.message : String(e);
		if (/extensions\.duckdb\.org|signature mismatch|parquet\.duckdb_extension/.test(msg)) {
			throw new Error(
				"Couldn't load DuckDB's parquet reader from extensions.duckdb.org. A network filter or ad blocker may be blocking it."
			);
		}
		throw e;
	} finally {
		await conn.close();
	}
}

export interface QueryResult {
	columns: { name: string; numeric: boolean }[];
	rows: Record<string, unknown>[];
	ms: number;
}

export async function run(sql: string): Promise<QueryResult> {
	const db = await getDb();
	const conn = await db.connect();
	const t0 = performance.now();
	try {
		const table = await conn.query(sql);
		const columns = table.schema.fields.map((f) => ({
			name: f.name,
			numeric: /Int|Float|Decimal/.test(String(f.type))
		}));
		const rows = table.toArray().map((r) => {
			const o = r.toJSON() as Record<string, unknown>;
			for (const k in o) {
				const v = o[k];
				if (typeof v === 'bigint') o[k] = Number(v);
			}
			return o;
		});
		return { columns, rows, ms: performance.now() - t0 };
	} finally {
		await conn.close();
	}
}
