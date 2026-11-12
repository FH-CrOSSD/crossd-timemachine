<script lang="ts">
  // What happened after t0, and what had already happened by t0. Events are dated after the fact
  // and read up to the data freeze; they do not depend on t0.
  import type { EventRow } from '$lib/data';
  import { eventKey, type Lead, type LookAlike } from '$lib/hindsight';
  import { day, distance } from '$lib/format';

  interface Props {
    t0: number;
    events: EventRow[];
    freeze: number;
    inCohort: boolean;
    hasGit: boolean;
    hasMeta: boolean;
    leads: Map<string, Lead[]>;
    names: Record<string, string>;
    alikes: LookAlike[];
  }

  let { t0, events, freeze, inCohort, hasGit, hasMeta, leads, names, alikes }: Props = $props();
  const shownAlikes = $derived(alikes.filter((a) => a.flagged.n + a.others.n > 0));
  const OUTCOME = { failure: 'failed', advisory: 'had a severe advisory left without a fix' };
  const pct = (g: { n: number; hit: number }) => (g.n ? `${Math.round((100 * g.hit) / g.n)}%` : '–');

  const after = $derived(events.filter((e) => e.date === null || e.date > t0));
  const before = $derived(events.filter((e) => e.date !== null && e.date <= t0).reverse());

  function tone(e: EventRow) {
    if (e.kind === 'archived' || e.kind === 'gone') return 'var(--event-loss)';
    if (e.kind === 'dormant') return 'var(--event-warn)';
    if (e.kind === 'advisory' && /no fixed|KEV/.test(e.detail)) return 'var(--event-warn)';
    return 'var(--event-info)';
  }
</script>

{#snippet item(e: EventRow, muted: boolean)}
  <li class="grid grid-cols-[12px_minmax(0,1fr)] gap-x-3 border-t border-line py-3 first:border-t-0 {muted ? 'opacity-60' : ''}">
    <span class="mt-[7px] block h-2 w-2 rounded-full" style="background: {tone(e)}"></span>
    <div class="min-w-0">
      <div class="flex flex-wrap items-baseline justify-between gap-x-3">
        <span class="text-[15px] text-ink">{e.title}</span>
        <span class="mono text-xs text-ink-2">{e.date ? day(e.date) : 'date unknown'}</span>
      </div>
      {#if e.detail}<div class="mt-0.5 text-[13px] break-words text-ink-2">{e.detail}</div>{/if}
      <div class="mono mt-0.5 text-xs text-ink-3">
        {e.source}{#if e.date && !muted}{' · '}{distance(t0, e.date)}{/if}
      </div>
      {#if !muted && e.date && leads.has(eventKey(e))}
        {@const found = leads.get(eventKey(e)) ?? []}
        {#if found.length}
          <p class="mt-2 text-[12px] text-ink-3">At their operating point when this happened, read before it:</p>
          <ul class="mt-1 grid gap-1 border-l-2 border-accent pl-3">
            {#each found as l (l.instrument + l.component)}
              <li class="text-[13px] leading-5 text-ink-2">
                {names[l.instrument] ?? l.instrument}: {l.label} from {day(l.since)},
                <span class="text-ink">{distance(e.date, l.since).replace('earlier', 'before')}</span>
                {#if e.date - l.last > 92 * 86400}<span class="text-ink-3"> (last read {day(l.last)})</span>{/if}
              </li>
            {/each}
          </ul>
        {:else}
          <p class="mt-2 text-[13px] leading-5 text-ink-3">No tested score stood at its operating point when this happened.</p>
        {/if}
      {/if}
    </div>
  </li>
{/snippet}

<section class="rounded-2xl border border-line bg-surface px-5 pt-4 pb-2">
  <header class="flex flex-wrap items-baseline justify-between gap-x-4">
    <h3 class="text-base font-medium text-ink">After t0</h3>
    <span class="mono text-xs text-ink-3">{after.length} {after.length === 1 ? 'event' : 'events'}</span>
  </header>
  {#if after.length}
    <ul class="mt-2">
      {#each after as e (e.kind + e.title + e.date)}
        {@render item(e, false)}
      {/each}
    </ul>
  {:else}
    <p class="py-3 text-[13px] text-ink-2">
      {#if !hasGit && !hasMeta}
        No events were collected for this project.
      {:else}
        Nothing recorded between t0 and the data freeze on {day(freeze)}.
      {/if}
    </p>
  {/if}
</section>

{#if shownAlikes.length}
  <section class="mt-6 rounded-2xl border border-line bg-surface px-5 pt-4 pb-3">
    <header class="flex flex-wrap items-baseline justify-between gap-x-4">
      <h3 class="text-base font-medium text-ink">Projects that looked the same</h3>
      <span class="mono text-xs text-ink-3">cohort of 1 Aug 2024</span>
    </header>
    <ul class="mt-2">
      {#each shownAlikes as a (a.instrument + a.component)}
        <li class="border-t border-line py-2.5 text-[13px] leading-5 text-ink-2 first:border-t-0">
          <span class="text-ink">{names[a.instrument] ?? a.instrument} {a.label}</span>{#if a.own === true}<span class="text-ink-3"> (this project)</span>{/if}:
          {#if a.flagged.n}
            <span class="mono text-ink">{pct(a.flagged)}</span> of {a.flagged.n.toLocaleString('en-GB')} {OUTCOME[a.against]} by the data freeze,
            against <span class="mono text-ink">{pct(a.others)}</span> of the {a.others.n.toLocaleString('en-GB')} others.
          {:else}
            no project of the cohort stood there on {day(t0)}.
          {/if}
        </li>
      {/each}
    </ul>
    <p class="mt-1 text-[12px] leading-5 text-ink-3">
      Split by each project's latest reading on {day(t0)}. Failed means archived, gone or twelve months without a commit
      or tag, counted up to the data freeze. This differs in definition and horizon from the study's outcome, so these
      shares are no validity result; a later t0 leaves less time.
    </p>
  </section>
{/if}

{#if before.length}
  <section class="mt-6 rounded-2xl border border-line bg-surface px-5 pt-4 pb-2">
    <header class="flex flex-wrap items-baseline justify-between gap-x-4">
      <h3 class="text-base font-medium text-ink-2">Already before t0</h3>
      <span class="mono text-xs text-ink-3">{before.length}</span>
    </header>
    <ul class="mt-2">
      {#each before as e (e.kind + e.title + e.date)}
        {@render item(e, true)}
      {/each}
    </ul>
  </section>
{/if}

<p class="mt-4 text-[13px] leading-5 text-ink-3">
  Events known as of {day(freeze)}. Severe advisories are those published from 1 Aug 2024 and attached to the
  project in the replication package; fix status is as listed at the data freeze.
  {#if !inCohort}This project is outside the cohort of 1 Aug 2024, so advisories were not collected.{/if}
  {#if !hasGit}Its commit history was not collected, so dormancy and the last commit are not shown.{/if}
  {#if !hasMeta}Its GitHub metadata was not collected, so an archive date would not be shown.{/if}
</p>
