// Lead time and look-alikes. Both read scores only through guard.ts. Events are dated facts read up to the data
// freeze; they belong to the right of t0 and are only ever compared with readings made before them.
import type { Validity } from './data';
import { seriesUntil, valuesAt, type SeriesPoint } from './guard';

export interface OutcomeEvent {
  project: string;
  kind: string;
  date: number;
  detail: string;
}

export type Against = 'failure' | 'advisory';

export const eventKey = (e: { kind: string; title: string; date: number | null }) => `${e.kind}|${e.title}|${e.date}`;

/** Does an event count as the outcome a flag is tested against? */
export function counts(e: { kind: string; detail: string }, against: Against): boolean {
  if (against === 'failure') return e.kind === 'archived' || e.kind === 'gone' || e.kind === 'dormant';
  return e.kind === 'advisory' && /no fixed version|KEV/i.test(e.detail);
}

export const flagged = (value: number | null, max: number) => value !== null && value <= max;

export interface Lead {
  instrument: string;
  component: string;
  label: string;
  since: number; // first reading of the unbroken flagged run that reaches the event
  last: number; // last reading before the event
  readings: number;
}

/**
 * The flagged run that is still standing at the event: walk back from the last reading before the event while the
 * value stays at or below the operating point. None if the last reading before the event is not flagged.
 */
export function leadFrom(series: SeriesPoint[], max: number): { since: number; last: number; readings: number } | null {
  const values = series.filter((p) => p.value !== null);
  if (!values.length || !flagged(values[values.length - 1].value, max)) return null;
  let i = values.length - 1;
  while (i > 0 && flagged(values[i - 1].value, max)) i--;
  return { since: values[i].observed, last: values[values.length - 1].observed, readings: values.length - i };
}

/** For one event: every tested score whose operating point stood when the event happened, read before it. */
export async function leadTimes(project: string, event: { kind: string; date: number; detail: string }, flags: Validity[]): Promise<Lead[]> {
  const out: Lead[] = [];
  for (const f of flags) {
    if (f.flag_max === null || !f.against || !counts(event, f.against)) continue;
    const series = await seriesUntil(project, f.instrument, f.component, event.date - 1);
    const run = leadFrom(series, f.flag_max);
    if (run) out.push({ instrument: f.instrument, component: f.component, label: f.flag_label ?? f.component, ...run });
  }
  return out;
}

export interface Group {
  n: number;
  hit: number;
}

export interface LookAlike {
  instrument: string;
  component: string;
  label: string;
  against: Against;
  own: boolean | null; // this project's side of the operating point, null without a reading
  flagged: Group;
  others: Group;
}

/** Split the cohort at t0 by the operating point and count the outcome events after t0 in each group. */
export function split(values: { project: string; value: number | null }[], max: number, cohort: Set<string>, hit: Set<string>) {
  const flaggedGroup: Group = { n: 0, hit: 0 };
  const others: Group = { n: 0, hit: 0 };
  for (const v of values) {
    if (v.value === null || !cohort.has(v.project)) continue;
    const g = flagged(v.value, max) ? flaggedGroup : others;
    g.n++;
    if (hit.has(v.project)) g.hit++;
  }
  return { flagged: flaggedGroup, others };
}

export async function lookAlikes(project: string, t0: number, flags: Validity[], cohort: Set<string>, events: OutcomeEvent[]): Promise<LookAlike[]> {
  const out: LookAlike[] = [];
  for (const f of flags) {
    if (f.flag_max === null || !f.against) continue;
    const against = f.against;
    const hit = new Set(events.filter((e) => e.date > t0 && counts(e, against)).map((e) => e.project));
    const values = await valuesAt(f.instrument, f.component, t0);
    const mine = values.find((v) => v.project === project);
    out.push({
      instrument: f.instrument,
      component: f.component,
      label: f.flag_label ?? f.component,
      against,
      own: mine && mine.value !== null ? flagged(mine.value, f.flag_max) : null,
      ...split(values, f.flag_max, cohort, hit)
    });
  }
  return out;
}
