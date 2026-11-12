import { describe, expect, it } from 'vitest';
import { counts, leadFrom, split } from './hindsight';

const p = (observed: number, value: number | null) => ({ observed, value, note: null, evidence: 'recorded' as const });

describe('lead time', () => {
  it('takes the unbroken flagged run that reaches the event', () => {
    expect(leadFrom([p(1, 3), p(2, 0), p(3, 5), p(4, 0), p(5, 0)], 0)).toEqual({ since: 4, last: 5, readings: 2 });
  });
  it('is none when the last reading before the event is not flagged', () => {
    expect(leadFrom([p(1, 0), p(2, 0), p(3, 4)], 0)).toBeNull();
  });
  it('skips missing values', () => {
    expect(leadFrom([p(1, 0), p(2, null), p(3, 0)], 0)).toEqual({ since: 1, last: 3, readings: 2 });
  });
});

describe('look-alikes', () => {
  it('counts only cohort projects with a value, on each side of the operating point', () => {
    const values = [
      { project: 'a', value: 0 },
      { project: 'b', value: 1 },
      { project: 'c', value: 0 },
      { project: 'd', value: null },
      { project: 'x', value: 0 }
    ];
    const r = split(values, 0, new Set(['a', 'b', 'c', 'd']), new Set(['a', 'b', 'x']));
    expect(r.flagged).toEqual({ n: 2, hit: 1 });
    expect(r.others).toEqual({ n: 1, hit: 1 });
  });
  it('treats only unfixed advisories as the advisory outcome', () => {
    expect(counts({ kind: 'advisory', detail: 'No fixed version listed at the data freeze' }, 'advisory')).toBe(true);
    expect(counts({ kind: 'advisory', detail: 'Fixed version listed' }, 'advisory')).toBe(false);
    expect(counts({ kind: 'dormant', detail: '' }, 'failure')).toBe(true);
    expect(counts({ kind: 'last_commit', detail: '' }, 'failure')).toBe(false);
  });
});
