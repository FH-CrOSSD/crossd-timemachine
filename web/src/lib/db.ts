// DuckDB-WASM in the browser over the precomputed Parquet files. No server: the worker and wasm
// files are bundled by Vite, so the booth build runs offline.
import * as duckdb from '@duckdb/duckdb-wasm';
import mvpWasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';
import mvpWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';
import ehWasm from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url';
import ehWorker from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url';
import { assets } from '$app/paths';

const TABLES = ['projects', 'readings', 'events', 'activity', 'components', 'validity'] as const;

let ready: Promise<duckdb.AsyncDuckDBConnection> | null = null;

export function connection(): Promise<duckdb.AsyncDuckDBConnection> {
  ready ??= open();
  return ready;
}

async function open(): Promise<duckdb.AsyncDuckDBConnection> {
  const bundle = await duckdb.selectBundle({
    mvp: { mainModule: mvpWasm, mainWorker: mvpWorker },
    eh: { mainModule: ehWasm, mainWorker: ehWorker }
  });
  const worker = new Worker(bundle.mainWorker!);
  const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  const conn = await db.connect();
  await Promise.all(
    TABLES.map(async (table) => {
      const response = await fetch(`${assets}/data/${table}.parquet`);
      if (!response.ok) throw new Error(`data/${table}.parquet: ${response.status}`);
      await db.registerFileBuffer(`${table}.parquet`, new Uint8Array(await response.arrayBuffer()));
    })
  );
  for (const table of TABLES) {
    await conn.query(`CREATE TABLE ${table} AS SELECT * FROM read_parquet('${table}.parquet')`);
  }
  return conn;
}

type Row = Record<string, unknown>;

function plain(value: unknown): unknown {
  return typeof value === 'bigint' ? Number(value) : value;
}

/** Run a parameterised statement and return plain objects. */
export async function query<T = Row>(sql: string, ...params: unknown[]): Promise<T[]> {
  const conn = await connection();
  const result = params.length
    ? await conn.prepare(sql).then(async (stmt) => {
        try {
          return await stmt.query(...params);
        } finally {
          await stmt.close();
        }
      })
    : await conn.query(sql);
  return result.toArray().map((row) => {
    const out: Row = {};
    for (const [key, value] of Object.entries(row.toJSON())) out[key] = plain(value);
    return out as T;
  });
}
