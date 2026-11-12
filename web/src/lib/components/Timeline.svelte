<script lang="ts">
  // The main chart: the project's record on one time axis, split at t0. Readings appear only to the
  // left of the t0 line (dates passed in are filtered again here); events after t0 sit on the right.
  // The t0 line is a scrubber: it tracks the pointer 1:1, hands off release velocity to a critically
  // damped spring, projects momentum and snaps to the nearest reading or month start.
  import { onDestroy } from 'svelte';
  import type { ActivityRow, EventRow } from '$lib/data';
  import { addMonths, day, DAY, month } from '$lib/format';
  import { project as projectMomentum, settled, step, velocityOf, type SpringState } from '$lib/spring';

  interface Props {
    t0: number;
    tMin: number;
    tMax: number;
    freeze: number;
    dates: { instrument: string; observed: number }[];
    events: EventRow[];
    activity: ActivityRow[];
    hasGit?: boolean;
    onsettle?: (t0: number) => void;
  }

  let { t0 = $bindable(), tMin, tMax, freeze, dates, events, activity, hasGit = true, onsettle }: Props = $props();

  const D0 = Date.UTC(2023, 0, 1) / 1000;
  const D1 = Date.UTC(2026, 11, 1) / 1000;
  const ROWS = [
    { key: 'crossd', label: 'CrOSSD' },
    { key: 'scorecard', label: 'Scorecard' },
    { key: 'criticality', label: 'Criticality' },
    { key: 'opencode', label: 'openCode' }
  ];

  let width = $state(960);
  const PAD = 16;
  const AXIS = 52;
  const ACT_H = 64;
  const ROW_H = 22;
  const EVT_H = 40;
  const top = AXIS + 8;
  const rowsTop = top + ACT_H + 12;
  const evtTop = rowsTop + ROWS.length * ROW_H + 10;
  const height = evtTop + EVT_H + 8;

  const x = (t: number) => PAD + ((t - D0) / (D1 - D0)) * (width - 2 * PAD);
  const invert = (px: number) => D0 + ((px - PAD) / (width - 2 * PAD)) * (D1 - D0);
  const clamp = (t: number) => Math.min(tMax, Math.max(tMin, t));

  const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- derived marks ------------------------------------------------------------------------
  const ticks = $derived.by(() => {
    const out: { t: number; label: string; year: boolean }[] = [];
    for (let t = D0; t <= D1; t = addMonths(t, 3)) {
      const m = new Date(t * 1000).getUTCMonth();
      out.push({ t, label: m === 0 ? String(new Date(t * 1000).getUTCFullYear()) : month(t).slice(0, 3), year: m === 0 });
    }
    return out;
  });

  const maxCommits = $derived(Math.max(1, ...activity.filter((a) => a.month >= D0).map((a) => a.commits)));
  const barW = $derived(Math.max(2, ((width - 2 * PAD) / ((D1 - D0) / (30.44 * DAY))) - 2));

  // Only readings at or before t0 are drawn; the latest per instrument is the one in use.
  const known = $derived.by(() => {
    const byRow: Record<string, number[]> = {};
    for (const d of dates) if (d.observed <= t0 && d.observed >= D0) (byRow[d.instrument] ??= []).push(d.observed);
    return byRow;
  });
  const inUse = $derived.by(() => {
    const out: Record<string, number> = {};
    for (const d of dates) if (d.observed <= t0 && (out[d.instrument] ?? -Infinity) < d.observed) out[d.instrument] = d.observed;
    return out;
  });

  const marks = $derived(
    events
      .filter((e) => e.date !== null && e.date >= D0)
      .map((e) => ({ ...e, date: e.date as number, after: (e.date as number) > t0, tone: tone(e) }))
  );

  function tone(e: EventRow): 'loss' | 'warn' | 'info' {
    if (e.kind === 'archived' || e.kind === 'gone') return 'loss';
    if (e.kind === 'dormant') return 'warn';
    if (e.kind === 'advisory') return /no fixed|KEV/.test(e.detail) ? 'warn' : 'info';
    return 'info';
  }

  const label = $derived(`Known on ${day(t0)}`);
  const lineX = $derived(x(t0));
  const labelW = $derived(label.length * 7.2 + 20);
  const labelX = $derived(Math.min(width - PAD - labelW, Math.max(PAD, lineX - labelW / 2)));

  // ---- snapping -----------------------------------------------------------------------------
  const snaps = $derived.by(() => {
    const s = new Set<number>();
    for (let t = tMin; t <= tMax; t = addMonths(t, 1)) s.add(t);
    for (const d of dates) if (d.observed >= tMin && d.observed <= tMax) s.add(Math.ceil(d.observed / 60) * 60);
    s.add(tMax);
    return [...s].sort((a, b) => a - b);
  });

  function nearest(t: number): number {
    let best = snaps[0] ?? clamp(t);
    for (const s of snaps) if (Math.abs(s - t) < Math.abs(best - t)) best = s;
    return best;
  }

  // ---- motion -------------------------------------------------------------------------------
  let frame = 0;
  let spring: SpringState | null = null;

  function animateTo(target: number, velocity = 0) {
    cancelAnimationFrame(frame);
    if (reduced) {
      t0 = target;
      spring = null;
      onsettle?.(target);
      return;
    }
    spring = { x: x(t0), v: velocity };
    const goal = x(target);
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.064, (now - last) / 1000);
      last = now;
      spring = step(spring!, goal, dt);
      if (settled(spring, goal)) {
        spring = null;
        t0 = target;
        onsettle?.(target);
        return;
      }
      t0 = clamp(invert(spring.x));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
  }

  onDestroy(() => cancelAnimationFrame(frame));

  // ---- pointer ------------------------------------------------------------------------------
  let svg: SVGSVGElement;
  let dragging = $state(false);
  let grabOffset = 0;
  let history: { x: number; t: number }[] = [];

  function localX(e: PointerEvent) {
    const r = svg.getBoundingClientRect();
    return ((e.clientX - r.left) / r.width) * width;
  }

  function down(e: PointerEvent) {
    if (e.button !== 0) return;
    cancelAnimationFrame(frame); // grab it mid-flight: motion starts from where the line is now
    spring = null;
    try {
      svg.setPointerCapture(e.pointerId);
    } catch {
      /* synthetic or already released pointer */
    }
    dragging = true;
    const px = localX(e);
    // grabbing the line keeps the offset; pressing elsewhere moves the line under the pointer
    grabOffset = Math.abs(px - lineX) <= 14 ? px - lineX : 0;
    t0 = clamp(invert(px - grabOffset));
    history = [{ x: px, t: e.timeStamp }];
  }

  function move(e: PointerEvent) {
    if (!dragging) return;
    const px = localX(e);
    t0 = clamp(invert(px - grabOffset));
    history.push({ x: px, t: e.timeStamp });
    if (history.length > 8) history.shift();
  }

  function up(e: PointerEvent) {
    if (!dragging) return;
    dragging = false;
    if (svg.hasPointerCapture(e.pointerId)) svg.releasePointerCapture(e.pointerId);
    const v = velocityOf(history);
    // snappier deceleration than scrolling: this is a precise instrument, a flick should not overshoot far
    const projected = clamp(invert(x(t0) + projectMomentum(v, 0.99)));
    animateTo(nearest(projected), v);
  }

  // ---- keyboard: reading to reading, month with Shift, Home and End ---------------------------
  function key(e: KeyboardEvent) {
    const readings = snaps.filter((s) => dates.some((d) => Math.ceil(d.observed / 60) * 60 === s));
    let target: number | undefined;
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
      target = e.shiftKey ? clamp(addMonths(t0, 1)) : (readings.find((s) => s > t0 + 59) ?? snaps.find((s) => s > t0 + 59));
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
      target = e.shiftKey ? clamp(addMonths(t0 - 1, 0)) : ([...readings].reverse().find((s) => s < t0 - 59) ?? [...snaps].reverse().find((s) => s < t0 - 59));
    } else if (e.key === 'PageUp') target = clamp(addMonths(t0, 12));
    else if (e.key === 'PageDown') target = clamp(addMonths(t0, -12));
    else if (e.key === 'Home') target = tMin;
    else if (e.key === 'End') target = tMax;
    if (target === undefined) return;
    e.preventDefault();
    animateTo(target);
  }
</script>

<div class="relative" bind:clientWidth={width}>
  <svg
    bind:this={svg}
    {width}
    {height}
    viewBox="0 0 {width} {height}"
    class="block touch-none select-none outline-none {dragging ? 'cursor-grabbing' : 'cursor-ew-resize'}"
    role="slider"
    tabindex="0"
    aria-label="Date t0: what was known at this date"
    aria-valuemin={tMin}
    aria-valuemax={tMax}
    aria-valuenow={Math.round(t0)}
    aria-valuetext={label}
    onpointerdown={down}
    onpointermove={move}
    onpointerup={up}
    onpointercancel={up}
    onkeydown={key}
  >
    <!-- after t0: the side of the record the scores could not see -->
    <rect x={lineX} y={AXIS} width={Math.max(0, width - PAD - lineX)} height={height - AXIS} fill="var(--after)" />

    <!-- axis -->
    {#each ticks as tick (tick.t)}
      <line x1={x(tick.t)} x2={x(tick.t)} y1={AXIS} y2={height} stroke="var(--line)" stroke-dasharray={tick.year ? '' : '2 3'} />
      {#if tick.year || width >= 720}
        <text x={x(tick.t) + 4} y={AXIS - 8} class="mono" font-size="11" fill={tick.year ? 'var(--ink-2)' : 'var(--ink-3)'}>{tick.label}</text>
      {/if}
    {/each}

    <!-- commit activity, dated by git history: before and after t0 -->
    <text x={PAD} y={top + 12} font-size="12" fill="var(--ink-3)">Commits per month</text>
    {#each activity as a (a.month)}
      {#if a.month >= D0 && a.commits > 0}
        {@const h = Math.max(1.5, Math.sqrt(a.commits / maxCommits) * (ACT_H - 20))}
        <rect
          x={x(a.month) + 1}
          y={top + ACT_H - h}
          width={barW}
          height={h}
          rx="1"
          fill="var(--ink)"
          opacity={a.month + 15 * DAY <= t0 ? 0.42 : 0.16}
        />
      {/if}
    {/each}
    {#if !hasGit}
      <text x={width / 2} y={top + ACT_H / 2 + 6} text-anchor="middle" font-size="13" fill="var(--ink-3)">Commit history not collected for this project</text>
    {/if}
    <line x1={PAD} x2={width - PAD} y1={top + ACT_H + 0.5} y2={top + ACT_H + 0.5} stroke="var(--line-strong)" />

    <!-- readings, left of t0 only -->
    {#each ROWS as row, i (row.key)}
      {@const y = rowsTop + i * ROW_H + ROW_H / 2}
      {#each known[row.key] ?? [] as t (t)}
        <circle cx={x(t)} cy={y} r="2.5" fill="var(--ink)" opacity={t === inUse[row.key] ? 1 : 0.3} />
      {/each}
      {#if inUse[row.key] !== undefined && inUse[row.key] >= D0}
        <line x1={x(inUse[row.key])} x2={lineX} y1={y} y2={y} stroke="var(--ink-3)" stroke-dasharray="1 3" />
      {/if}
      <!-- drawn last, on a halo of the card colour, so early readings never run through the label -->
      <text x={PAD} y={y + 4} font-size="12" fill="var(--ink-3)" stroke="var(--surface)" stroke-width="6" stroke-linejoin="round" paint-order="stroke">{row.label}</text>
    {/each}

    <!-- events, dated after the fact -->
    <text x={PAD} y={evtTop + 14} font-size="12" fill="var(--ink-3)">Events</text>
    {#each marks as m (m.kind + m.title + m.date)}
      {@const cx = x(m.date)}
      {@const cy = evtTop + 22}
      <g opacity={m.after ? 1 : 0.4} style="color: var(--event-{m.tone})">
        <title>{day(m.date)}: {m.title}</title>
        {#if m.kind === 'archived'}
          <rect x={cx - 5} y={cy - 5} width="10" height="10" rx="1.5" fill="currentColor" />
        {:else if m.kind === 'gone'}
          <path d="M{cx - 5} {cy - 5}L{cx + 5} {cy + 5}M{cx + 5} {cy - 5}L{cx - 5} {cy + 5}" stroke="currentColor" stroke-width="2" />
        {:else if m.kind === 'dormant'}
          <path d="M{cx} {cy - 6}L{cx + 6} {cy}L{cx} {cy + 6}L{cx - 6} {cy}Z" fill="currentColor" />
        {:else if m.kind === 'advisory'}
          <path d="M{cx} {cy - 6}L{cx + 5.5} {cy + 4}L{cx - 5.5} {cy + 4}Z" fill="currentColor" />
        {:else}
          <line x1={cx} x2={cx} y1={cy - 7} y2={cy + 7} stroke="currentColor" stroke-width="2" />
        {/if}
      </g>
    {/each}

    <!-- data freeze -->
    {#if freeze <= D1}
      <line x1={x(freeze)} x2={x(freeze)} y1={AXIS} y2={height} stroke="var(--ink-3)" stroke-dasharray="4 3" />
    {/if}

    <!-- t0: the signature line -->
    <line x1={lineX} x2={lineX} y1={24} y2={height} stroke="var(--accent)" stroke-width="1.5" />
    <circle cx={lineX} cy={height - 4} r="4" fill="var(--accent)" />
  </svg>

  <!-- label sits in HTML so it stays crisp and readable at any width -->
  <div
    class="mono pointer-events-none absolute top-0 rounded-md border border-line bg-surface px-2 py-0.5 text-accent-ink"
    style="left: {labelX}px; width: {labelW}px; font-size: 12px; text-align: center;"
    aria-hidden="true"
  >
    {label}
  </div>
</div>

<div class="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-3">
  <span class="inline-flex items-center gap-2"><svg width="10" height="10"><circle cx="5" cy="5" r="2.5" fill="var(--ink)" /></svg>reading in use at t0</span>
  <span class="inline-flex items-center gap-2" style="color: var(--event-loss)"><svg width="10" height="10"><rect width="10" height="10" rx="1.5" fill="currentColor" /></svg><span class="text-ink-3">archived or gone</span></span>
  <span class="inline-flex items-center gap-2" style="color: var(--event-warn)"><svg width="12" height="12"><path d="M6 0L12 6L6 12L0 6Z" fill="currentColor" /></svg><span class="text-ink-3">twelve months without a commit</span></span>
  <span class="inline-flex items-center gap-2" style="color: var(--event-warn)"><svg width="12" height="10"><path d="M6 0L11.5 10L0.5 10Z" fill="currentColor" /></svg><span class="text-ink-3">severe advisory without a fix</span></span>
  <span class="inline-flex items-center gap-2"><svg width="2" height="12"><rect width="2" height="12" fill="var(--event-info)" /></svg>last commit</span>
  <span class="inline-flex items-center gap-2"><svg width="16" height="2"><line x2="16" y1="1" y2="1" stroke="var(--ink-3)" stroke-dasharray="4 3" /></svg>data freeze, {day(freeze)}</span>
</div>
