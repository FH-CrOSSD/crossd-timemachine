// Critically damped spring (damping ratio 1.0): no overshoot, interruptible, starts from the current
// value and velocity. Response 0.35 s, no bounce.
export interface SpringState {
  x: number;
  v: number; // units per second
}

export function step(state: SpringState, target: number, dt: number, response = 0.35): SpringState {
  const omega = (2 * Math.PI) / response;
  let { x, v } = state;
  // a few substeps keep the integration stable on slow frames
  const n = Math.max(1, Math.ceil(dt / (1 / 240)));
  const h = dt / n;
  for (let i = 0; i < n; i++) {
    const a = -omega * omega * (x - target) - 2 * omega * v;
    v += a * h;
    x += v * h;
  }
  return { x, v };
}

export function settled(state: SpringState, target: number, eps = 0.25): boolean {
  return Math.abs(state.x - target) < eps && Math.abs(state.v) < eps * 4;
}

/** Where a flick would come to rest (Apple's projection, deceleration rate per ms). */
export function project(velocity: number, decelerationRate = 0.998): number {
  return ((velocity / 1000) * decelerationRate) / (1 - decelerationRate);
}

/** Release velocity from the last pointer samples, in units per second. */
export function velocityOf(history: { x: number; t: number }[]): number {
  const now = history.at(-1);
  if (!now) return 0;
  const recent = history.filter((p) => now.t - p.t <= 80);
  const first = recent[0];
  if (!first || now.t === first.t) return 0;
  return ((now.x - first.x) / (now.t - first.t)) * 1000;
}
