// Loaders for everything that is not a reading. Events are dated facts after the fact and do not
// depend on t0; readings go through guard.ts only.
import { query } from './db';
import { assets } from '$app/paths';

export interface Project {
  project: string;
  stratum: string | null;
  in_cohort: boolean;
  gone_now: boolean;
  snapshots: number;
  first_reading: number | null;
  last_reading: number | null;
  crossd_readings: number;
  has_git: boolean;
  has_meta: boolean;
}

export interface EventRow {
  project: string;
  kind: 'archived' | 'gone' | 'last_commit' | 'dormant' | 'advisory';
  date: number | null;
  title: string;
  detail: string;
  source: string;
}

export interface ActivityRow {
  month: number;
  commits: number;
  tags: number;
}

export interface Component {
  instrument: string;
  instrument_name: string;
  component: string;
  label: string;
  unit: string;
  how: string;
  claim: string | null;
  backdating: string;
  why: string | null;
  claim_source: string | null;
}

export interface Validity {
  instrument: string;
  component: string;
  outcome: string;
  sentence: string;
  citation: string;
  warns: boolean;
  flag_max: number | null;
  flag_label: string | null;
  against: 'failure' | 'advisory' | null;
  sensitivity: number | null;
  specificity: number | null;
}

export interface Meta {
  built: string;
  data_freeze: string;
  t0_min: string;
  t0_max: string;
  citation: string;
}

export const projects = () => query<Project>('SELECT * FROM projects ORDER BY lower(project)');
export const events = (p: string) => query<EventRow>('SELECT * FROM events WHERE project = ? ORDER BY date NULLS LAST', p);
export const activity = (p: string) => query<ActivityRow>('SELECT month, commits, tags FROM activity WHERE project = ? ORDER BY month', p);
export const components = () => query<Component>('SELECT * FROM components');
/** Projects of the cohort of 1 Aug 2024. Look-alikes count only these: their events were all collected. */
export const cohort = () => query<{ project: string }>('SELECT project FROM projects WHERE in_cohort').then((r) => new Set(r.map((x) => x.project)));
/** Dated outcome events of all projects; facts read up to the data freeze, independent of t0. */
export const outcomeEvents = () =>
  query<{ project: string; kind: string; date: number; detail: string }>(
    "SELECT project, kind, date, detail FROM events WHERE date IS NOT NULL AND kind IN ('archived', 'gone', 'dormant', 'advisory')"
  );
export const validity = () => query<Validity>('SELECT * FROM validity');
export const meta = (): Promise<Meta> => fetch(`${assets}/data/meta.json`).then((r) => r.json());
