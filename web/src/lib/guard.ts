// The hindsight guard. Every value the interface shows comes through this module: a reading counts
// at t0 only if it was read from its source at or before t0 (`observed <= t0`). The SQL enforces it,
// and every returned row is checked again here, so a faulty query fails loudly instead of leaking.
// The same SQL files are tested against planted rows in pipeline/tests/test_guard.py.
import readingsAtSql from './sql/readings_at.sql?raw';
import readingsUntilSql from './sql/readings_until.sql?raw';
import readingDatesSql from './sql/reading_dates.sql?raw';
import valuesAtSql from './sql/values_at.sql?raw';
import { query } from './db';

export type Evidence = 'recorded' | 'reconstructed';

export interface Reading {
  project: string;
  instrument: string;
  component: string;
  value: number | null;
  note: string | null;
  observed: number;
  snapshot: number | null;
  evidence: Evidence;
  source: string;
}

export interface SeriesPoint {
  observed: number;
  value: number | null;
  note: string | null;
  evidence: Evidence;
}

export class HindsightError extends Error {
  constructor(observed: number, t0: number) {
    const when = Number.isFinite(observed) ? new Date(observed * 1000).toISOString() : 'an unknown time';
    super(`a value read at ${when} was returned for t0 ${new Date(t0 * 1000).toISOString()}`);
    this.name = 'HindsightError';
  }
}

export function assertNotAfter<T extends { observed: number }>(rows: T[], t0: number): T[] {
  for (const row of rows) {
    if (typeof row.observed !== 'number' || Number.isNaN(row.observed)) throw new HindsightError(NaN, t0);
    if (row.observed > t0) throw new HindsightError(row.observed, t0);
  }
  return rows;
}

/** The latest reading of each component read at or before t0. */
export async function readingsAt(project: string, t0: number): Promise<Reading[]> {
  return assertNotAfter(await query<Reading>(readingsAtSql, project, t0), t0);
}

/** All readings of one component read at or before t0. */
export async function seriesUntil(project: string, instrument: string, component: string, t0: number): Promise<SeriesPoint[]> {
  return assertNotAfter(await query<SeriesPoint>(readingsUntilSql, project, instrument, component, t0), t0);
}

/** The latest reading of one component for every project, read at or before t0. */
export async function valuesAt(instrument: string, component: string, t0: number): Promise<{ project: string; value: number | null; observed: number }[]> {
  return assertNotAfter(await query<{ project: string; value: number | null; observed: number }>(valuesAtSql, instrument, component, t0), t0);
}

/** Reading dates only, never values: where the scrubber can stop. */
export async function readingDates(project: string): Promise<{ instrument: string; observed: number }[]> {
  return query<{ instrument: string; observed: number }>(readingDatesSql, project);
}

export const SQL = { readingsAtSql, readingsUntilSql, readingDatesSql, valuesAtSql };
