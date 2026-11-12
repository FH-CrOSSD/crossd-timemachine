import { describe, expect, it, vi } from 'vitest';

vi.mock('./db', () => ({ query: vi.fn() }));
vi.mock('$app/paths', () => ({ assets: '' }));

const { assertNotAfter, HindsightError, SQL } = await import('./guard');

const t0 = Date.UTC(2024, 7, 1) / 1000;

describe('assertNotAfter', () => {
  it('passes readings at or before t0', () => {
    const rows = [{ observed: t0 - 86400 }, { observed: t0 }];
    expect(assertNotAfter(rows, t0)).toBe(rows);
  });

  it('fails on a reading after t0, even by one second', () => {
    expect(() => assertNotAfter([{ observed: t0 + 1 }], t0)).toThrow(HindsightError);
  });

  it('fails on an undated reading', () => {
    expect(() => assertNotAfter([{ observed: Number.NaN }], t0)).toThrow(HindsightError);
  });
});

describe('guard SQL', () => {
  it('filters on the reading time, not the snapshot', () => {
    for (const sql of [SQL.readingsAtSql, SQL.readingsUntilSql, SQL.valuesAtSql]) {
      const code = sql.replace(/--.*$/gm, '');
      expect(code).toMatch(/observed\s*<=\s*\?/);
      expect(code).not.toMatch(/snapshot\s*<=/);
    }
  });

  it('returns dates only for the scrubber', () => {
    const code = SQL.readingDatesSql.replace(/--.*$/gm, '');
    expect(code).not.toMatch(/\bvalue\b/);
  });
});
