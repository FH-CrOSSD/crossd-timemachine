// One date format and one number format across the interface: "1 Aug 2024", tabular figures.
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const DAY = 86400;

export function day(seconds: number): string {
  const d = new Date(seconds * 1000);
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

export function month(seconds: number): string {
  const d = new Date(seconds * 1000);
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

export function iso(seconds: number): string {
  return new Date(seconds * 1000).toISOString().slice(0, 10);
}

export function fromIso(text: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return null;
  const t = Date.parse(`${text}T00:00:00Z`);
  return Number.isNaN(t) ? null : t / 1000;
}

/** End of the given UTC day: a t0 means "everything known by the end of this day". */
export function endOfDay(seconds: number): number {
  return Math.floor(seconds / DAY) * DAY + DAY - 1;
}

export function startOfMonth(seconds: number): number {
  const d = new Date(seconds * 1000);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1) / 1000;
}

export function addMonths(seconds: number, n: number): number {
  const d = new Date(seconds * 1000);
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + n, 1) / 1000;
}

/** "8 months later", "3 weeks earlier", "the same day". */
export function distance(from: number, to: number): string {
  const days = Math.round((to - from) / DAY);
  const abs = Math.abs(days);
  const side = days >= 0 ? 'later' : 'earlier';
  if (abs === 0) return 'the same day';
  if (abs < 14) return `${abs} ${abs === 1 ? 'day' : 'days'} ${side}`;
  if (abs < 61) return `${Math.round(abs / 7)} weeks ${side}`;
  const months = Math.round(abs / 30.44);
  if (months < 24) return `${months} months ${side}`;
  return `${(abs / 365.25).toFixed(1)} years ${side}`;
}

export function value(v: number | null, unit = ''): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '';
  // units are fixed per component in the catalogue: a share is a fraction, a percentage is 0–100
  if (unit === 'share') return `${(v * 100).toFixed(0)}%`;
  if (unit === '%') return `${v.toFixed(0)}%`;
  if (unit === '0–1') return v.toFixed(2);
  if (Number.isInteger(v)) return v.toLocaleString('en-GB');
  if (Math.abs(v) >= 100) return Math.round(v).toLocaleString('en-GB');
  return v.toFixed(Math.abs(v) < 10 ? 1 : 0);
}
