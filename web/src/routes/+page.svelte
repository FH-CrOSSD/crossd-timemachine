<script lang="ts">
  import { onMount } from 'svelte';
  import { replaceState } from '$app/navigation';
  import * as data from '$lib/data';
  import type { ActivityRow, Component, EventRow, Meta, Project, Validity } from '$lib/data';
  import { readingDates, readingsAt, type Reading } from '$lib/guard';
  import { counts, eventKey, leadTimes, lookAlikes, type Lead, type LookAlike, type OutcomeEvent } from '$lib/hindsight';
  import { day, fromIso, iso } from '$lib/format';
  import Timeline from '$lib/components/Timeline.svelte';
  import Readings from '$lib/components/Readings.svelte';
  import Events from '$lib/components/Events.svelte';
  import Search from '$lib/components/Search.svelte';
  import Guide from '$lib/components/Guide.svelte';

  const DOI = 'https://doi.org/10.5281/zenodo.24113633';
  const CROSSD = 'https://health.crossd.tech';
  const DEFAULT_PROJECT = 'minio/minio';
  const DEFAULT_T0 = Date.UTC(2024, 7, 1) / 1000;

  let status = $state<'loading' | 'ready' | 'error'>('loading');
  let failure = $state('');
  let meta = $state<Meta | null>(null);
  let projects = $state<Project[]>([]);
  let catalogue = $state<Component[]>([]);
  let validity = $state<Validity[]>([]);

  let current = $state(DEFAULT_PROJECT);
  let t0 = $state(DEFAULT_T0);
  let dates = $state<{ instrument: string; observed: number }[]>([]);
  let events = $state<EventRow[]>([]);
  let activity = $state<ActivityRow[]>([]);
  let readings = $state<Reading[]>([]);
  let cohort = new Set<string>();
  let outcomes: OutcomeEvent[] = [];
  let leads = $state(new Map<string, Lead[]>());
  let alikes = $state<LookAlike[]>([]);
  let alikesAt = $state(0);
  const flags = $derived(validity.filter((v) => v.flag_max !== null && v.against));
  const names: Record<string, string> = { crossd: 'CrOSSD', scorecard: 'Scorecard', criticality: 'Criticality Score', opencode: 'openCode' };

  const tMin = $derived(meta ? (fromIso(meta.t0_min) ?? DEFAULT_T0) : DEFAULT_T0);
  const freeze = $derived(meta ? (fromIso(meta.data_freeze) ?? 0) + 86399 : 0);
  const tMax = $derived(freeze);
  const info = $derived(projects.find((p) => p.project === current));

  // A second check on what reaches the screen: only rows read by the t0 now shown.
  const shown = $derived(readings.filter((r) => r.observed <= t0));
  const shownAlikes = $derived(alikesAt <= t0 ? alikes : []);

  onMount(async () => {
    try {
      const params = new URLSearchParams(location.search);
      [meta, projects, catalogue, validity, cohort, outcomes] = await Promise.all([
        data.meta(), data.projects(), data.components(), data.validity(), data.cohort(), data.outcomeEvents()
      ]);
      const wanted = params.get('p');
      if (wanted && projects.some((p) => p.project === wanted)) current = wanted;
      const t = params.get('t0') ?? '';
      const parsed = fromIso(t.slice(0, 10));
      if (parsed !== null) {
        const exact = t.length > 10 ? Date.parse(t) / 1000 : parsed;
        t0 = Math.min(tMax, Math.max(tMin, Number.isNaN(exact) ? parsed : exact));
      }
      await load(current);
      status = 'ready';
    } catch (err) {
      failure = err instanceof Error ? err.message : String(err);
      status = 'error';
    }
  });

  async function load(project: string) {
    const [d, e, a] = await Promise.all([readingDates(project), data.events(project), data.activity(project)]);
    if (project !== current) return;
    dates = d;
    events = e;
    activity = a;
    // Lead time per outcome event: readings made before the event only (guard.seriesUntil). Independent of t0.
    const found = new Map<string, Lead[]>();
    for (const ev of e) {
      if (ev.date === null || !['archived', 'gone', 'dormant', 'advisory'].includes(ev.kind)) continue;
      const l = await leadTimes(project, { kind: ev.kind, date: ev.date, detail: ev.detail }, flags);
      if (flags.some((f) => f.against && counts(ev, f.against))) found.set(eventKey(ev), l);
    }
    if (project === current) leads = found;
  }

  // Coalesced guarded query: one in flight; a result is kept only if its t0 is not later than the
  // t0 on screen, so a slow answer for a later date can never show values the line has not reached.
  let inflight = false;
  let again = false;
  async function refresh() {
    if (inflight) {
      again = true;
      return;
    }
    inflight = true;
    do {
      again = false;
      const project = current;
      const at = t0;
      const started = performance.now();
      const rows = await readingsAt(project, at);
      if (project === current && at <= t0) readings = rows;
      const counted = await lookAlikes(project, at, flags, cohort, outcomes);
      if (project === current && at <= t0) {
        alikes = counted;
        alikesAt = at;
      }
      performance.measure('refresh', { start: started }); // query time per t0, visible in the browser's performance panel
      if (project !== current || at !== t0) again = true;
    } while (again);
    inflight = false;
  }

  $effect(() => {
    void current;
    void t0;
    if (status === 'ready') refresh();
  });

  function pick(project: string) {
    current = project;
    readings = [];
    load(project).then(() => settle());
  }

  function random() {
    const pool = projects.filter((p) => p.in_cohort && p.project !== current);
    pick(pool[Math.floor(Math.random() * pool.length)].project);
  }

  function settle(t = t0) {
    const midnight = t % 86400 === 0;
    const url = new URL(location.href);
    url.searchParams.set('p', current);
    url.searchParams.set('t0', midnight ? iso(t) : new Date(t * 1000).toISOString().slice(0, 16) + 'Z');
    try {
      replaceState(url, {});
    } catch {
      /* router not ready yet */
    }
  }

  const strata: Record<string, string> = {
    most_starred: 'most-starred list',
    random_sample: 'random-sample list',
    netidee: 'netidee list'
  };
</script>

<div class="min-h-dvh bg-bg text-ink">
  <header class="border-b border-line bg-bg">
    <div class="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-8">
      <a href="./" class="flex items-center gap-2.5 text-[16px] font-medium tracking-[-0.005em] text-ink">
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <path d="M1 13h16" stroke="var(--ink)" stroke-opacity=".3" stroke-width="1.5" />
          <path d="M9 1v16" stroke="var(--accent)" stroke-width="1.75" />
          <circle cx="9" cy="4" r="2.25" fill="var(--accent)" />
        </svg>
        CrOSSD Time Machine
      </a>
      {#if status === 'ready'}
        <div class="flex w-full items-center gap-2 sm:w-auto">
          <Search {projects} onpick={pick} />
          <button
            type="button"
            onclick={random}
            class="press h-9 shrink-0 rounded-lg border border-line bg-surface px-3 text-[14px] text-ink-2 hover:bg-raised hover:text-ink"
          >
            Random project
          </button>
        </div>
      {/if}
    </div>
  </header>

  <main class="mx-auto max-w-[1440px] px-4 pt-8 pb-16 sm:px-8">
    {#if status === 'loading'}
      <p class="py-24 text-center text-[15px] text-ink-2">Loading the record</p>
    {:else if status === 'error'}
      <p class="py-24 text-center text-[15px] text-ink-2">The data could not be loaded: {failure}</p>
    {:else}
      <section class="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
        <div class="min-w-0">
          <h1 class="text-[28px] leading-[1.15] font-medium tracking-[-0.01em] break-words text-ink sm:text-[32px]">{current}</h1>
          <p class="mt-1.5 text-[14px] text-ink-2">
            {#if info?.stratum}{strata[info.stratum] ?? info.stratum} of the CrOSSD panel{:else}CrOSSD panel{/if}{#if info?.in_cohort}, in the cohort of 1 Aug 2024{/if}
            <span class="mono text-ink-3"> · {info?.crossd_readings ?? 0} CrOSSD readings</span>
            {#if (info?.crossd_readings ?? 0) > 0}
              <span class="text-ink-3">{' · '}</span><a
                class="text-ink-2 underline decoration-line-strong underline-offset-2 hover:text-ink"
                href={`${CROSSD}/project/${encodeURIComponent(current)}`}
                target="_blank"
                rel="noreferrer">today on CrOSSD ↗</a>
            {/if}
          </p>
        </div>
        <p class="max-w-[46ch] text-[14px] leading-5 text-ink-2">
          Drag the line to a date. Left of it, only what each score had read by then. Right of it, what happened next.
        </p>
      </section>

      <Guide {freeze} cohortSize={projects.filter((p) => p.in_cohort).length} />

      <section class="mt-6 rounded-2xl border border-line bg-surface px-3 pt-6 pb-4 sm:px-5" aria-label="Timeline">
        <Timeline bind:t0 {tMin} {tMax} {freeze} {dates} {events} {activity} hasGit={info?.has_git ?? false} onsettle={settle} />
      </section>

      <div class="mt-10 grid gap-8 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <section aria-labelledby="said">
          <h2 id="said" class="mb-4 text-[20px] font-medium tracking-[-0.005em]">
            What the scores said by <span class="mono text-[17px] text-accent-ink">{day(t0)}</span>
          </h2>
          <Readings {t0} readings={shown} {catalogue} {validity} doi={DOI} alikes={shownAlikes} />
        </section>
        <section aria-labelledby="next">
          <h2 id="next" class="mb-4 text-[20px] font-medium tracking-[-0.005em]">What happened next</h2>
          <Events {t0} {events} {freeze} inCohort={info?.in_cohort ?? false} hasGit={info?.has_git ?? false} hasMeta={info?.has_meta ?? false} {leads} {names} alikes={shownAlikes} />
        </section>
      </div>
    {/if}
  </main>

  <footer class="border-t border-line">
    <div class="mx-auto grid max-w-[1440px] gap-2 px-4 py-6 text-[13px] leading-5 text-ink-3 sm:px-8">
      <p>
        Readings from <a class="underline decoration-line-strong underline-offset-2 hover:text-ink" href={CROSSD} target="_blank" rel="noreferrer">CrOSSD</a> (health.crossd.tech), published OpenSSF Scorecard scans and Criticality Score lists, and
        Scorecard checks and openCode rules rebuilt from dated data. Each value is dated by when it was read, never by
        its snapshot. Events from GitHub, git history, OSV and Software Heritage.
      </p>
      <p class="mono text-xs">
        {#if meta}data freeze {day(fromIso(meta.data_freeze) ?? 0)} · built {day(Date.parse(meta.built) / 1000)} ·{/if}
        <a class="underline decoration-line-strong underline-offset-2 hover:text-ink" href={DOI} target="_blank" rel="noreferrer">replication package</a>
      </p>
    </div>
  </footer>
</div>
