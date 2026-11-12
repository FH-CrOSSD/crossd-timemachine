<script lang="ts">
  // What each instrument said at t0. Values come only from guard.readingsAt; every value carries its
  // reading date and evidence type. Values stay neutral: no score in the audit was validated for colour.
  import type { Component, Validity } from '$lib/data';
  import type { Reading } from '$lib/guard';
  import type { LookAlike } from '$lib/hindsight';
  import { day, distance, DAY, value as fmt } from '$lib/format';
  import Num from './Num.svelte';

  interface Props {
    t0: number;
    readings: Reading[];
    catalogue: Component[];
    validity: Validity[];
    doi: string;
    alikes: LookAlike[];
  }

  let { t0, readings, catalogue, validity, doi, alikes }: Props = $props();
  const alike = $derived(new Map(alikes.map((a) => [`${a.instrument}/${a.component}`, a])));
  let more = $state(new Set<string>());
  function flip(key: string) {
    const next = new Set(more);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    more = next;
  }
  const BACKDATING: Record<string, string> = {
    recorded: 'Recorded at the time',
    rebuilt: 'Reconstructed from dated data',
    partial: 'Reconstructed in part',
    not_backdatable: 'Not backdatable',
    'published only': 'Only as published'
  };

  const INSTRUMENTS = [
    { key: 'crossd', name: 'CrOSSD', about: 'Health metrics computed from GitHub data, crawled weekly by the CrOSSD platform since April 2024.', lead: ['maturity_level', 'bus_factor', 'elephant_factor', 'support_rate', 'criticality_score'] },
    { key: 'scorecard', name: 'OpenSSF Scorecard', about: 'Security checks of the Open Source Security Foundation, each 0 to 10, published weekly; some checks rebuilt from git history.', lead: ['aggregate', 'aggregate_t0', 'Maintained', 'Code-Review', 'Security-Policy'] },
    { key: 'criticality', name: 'OpenSSF Criticality Score', about: 'How influential and important a project is, from activity signals, 0 to 1; published as lists every few months.', lead: ['score'] },
    { key: 'opencode', name: 'openCode badges', about: 'Maintenance and security badges of the German public-sector code platform, rebuilt from their published rules.', lead: ['maintenance', 'security', 'response_ok'] }
  ];

  const byKey = $derived(new Map(readings.map((r) => [`${r.instrument}/${r.component}`, r])));
  const cat = $derived(new Map(catalogue.map((c) => [`${c.instrument}/${c.component}`, c])));
  const valid = $derived(new Map(validity.map((v) => [`${v.instrument}/${v.component}`, v])));

  function rows(instrument: string) {
    return catalogue.filter((c) => c.instrument === instrument).map((c) => c.component);
  }

  function evidenceText(r: Reading) {
    return r.evidence === 'recorded' ? 'recorded at the time' : 'reconstructed from dated data';
  }

  function stale(r: Reading) {
    return t0 - r.observed > 92 * DAY ? `, ${distance(t0, r.observed).replace('earlier', 'before t0')}` : '';
  }

  function latest(instrument: string) {
    const own = readings.filter((r) => r.instrument === instrument);
    return own.length ? Math.max(...own.map((r) => r.observed)) : null;
  }
</script>

{#snippet row(instrument: string, component: string, lead: boolean)}
  {@const c = cat.get(`${instrument}/${component}`)}
  {@const r = byKey.get(`${instrument}/${component}`)}
  {@const v = valid.get(`${instrument}/${component}`)}
  {@const a = lead ? alike.get(`${instrument}/${component}`) : undefined}
  {#if c}
    <li class="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 border-t border-line py-3 first:border-t-0">
      <div class="min-w-0">
        <div class="flex flex-wrap items-baseline gap-x-2">
          <span class="text-[15px] {lead ? 'text-ink' : 'text-ink-2'}">{c.label}</span>
          <button
            type="button"
            class="press text-[12px] text-ink-3 underline decoration-line-strong underline-offset-2 hover:text-ink"
            aria-expanded={more.has(`${instrument}/${component}`)}
            onclick={() => flip(`${instrument}/${component}`)}
          >{more.has(`${instrument}/${component}`) ? 'less' : 'more'}</button>
        </div>
        {#if r}
          <div class="mono mt-0.5 text-xs text-ink-3">
            read {day(r.observed)}{' · '}{evidenceText(r)}{stale(r)}
          </div>
        {:else if c.backdating === 'not_backdatable'}
          <div class="mt-0.5 text-[13px] text-ink-3">Not backdatable: {c.why}</div>
        {:else}
          <div class="mt-0.5 text-[13px] text-ink-3">No reading before t0</div>
        {/if}
      </div>
      <div class="text-right">
        {#if r && r.value !== null}
          <div class="mono text-[17px] text-ink"><Num value={r.value} unit={c.unit} /></div>
          <div class="mono text-xs text-ink-3">{c.unit}</div>
        {:else if r && r.note}
          <div class="text-[13px] text-ink-2">{r.note}</div>
        {/if}
      </div>
      {#if more.has(`${instrument}/${component}`)}
        <div class="col-span-2 mt-1 grid max-w-[64ch] gap-1 rounded-lg bg-raised px-3 py-2 text-[13px] leading-5 text-ink-2">
          <p><span class="text-ink">Measures:</span> {c.how}{c.unit ? ` (${c.unit})` : ''}.</p>
          {#if c.claim}
            <p>
              <span class="text-ink">Its makers say:</span> “{c.claim}”
              {#if c.claim_source}<a class="text-ink-3 underline decoration-line-strong underline-offset-2 hover:text-ink" href={c.claim_source} target="_blank" rel="noreferrer">source</a>{/if}
            </p>
          {/if}
          <p><span class="text-ink">{BACKDATING[c.backdating] ?? c.backdating}:</span> {c.why}.</p>
          {#if v?.flag_label}<p><span class="text-ink">Operating point:</span> {v.flag_label}.</p>{/if}
        </div>
      {/if}
      {#if a && a.flagged.n + a.others.n > 0}
        <p class="col-span-2 max-w-[60ch] text-[13px] leading-5 text-ink-2">
          On {day(t0)}, <span class="mono text-ink">{a.flagged.n.toLocaleString('en-GB')}</span> of the
          {(a.flagged.n + a.others.n).toLocaleString('en-GB')} projects of the cohort with a reading stood at {a.label}{#if a.own === true}, this
          project among them{/if}. What happened to them is under “What happened next”.
        </p>
      {/if}
      {#if v && lead}
        <p class="col-span-2 max-w-[60ch] text-[13px] leading-5 text-ink-2">
          {v.sentence}
          <a class="text-ink-3 underline decoration-line-strong underline-offset-2 hover:text-ink" href="#guide" onclick={() => document.getElementById('guide')?.setAttribute('open', '')}>What this means</a> ·
          <a class="text-ink-3 underline decoration-line-strong underline-offset-2 hover:text-ink" href={doi} target="_blank" rel="noreferrer">Neumaier and Dam, under review</a>
        </p>
      {/if}
    </li>
  {/if}
{/snippet}

<div class="grid gap-6">
  {#each INSTRUMENTS as inst (inst.key)}
    {@const last = latest(inst.key)}
    {@const rest = rows(inst.key).filter((c) => !inst.lead.includes(c))}
    <section class="rounded-2xl border border-line bg-surface px-5 pt-4 pb-2">
      <header class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 class="text-base font-medium text-ink">{inst.name}</h3>
        <span class="mono text-xs text-ink-3">
          {last ? `latest reading ${day(last)}` : 'no reading before t0'}
        </span>
      </header>
      <p class="mt-1 max-w-[64ch] text-[13px] leading-5 text-ink-3">{inst.about}</p>
      <ul class="mt-2">
        {#each inst.lead as component (component)}
          {@render row(inst.key, component, true)}
        {/each}
      </ul>
      {#if rest.length}
        <details class="group border-t border-line py-3">
          <summary class="press cursor-pointer list-none text-[13px] text-ink-2 hover:text-ink">
            <span class="inline-block transition-transform duration-150 group-open:rotate-90">›</span>
            {rest.length} more {inst.key === 'scorecard' ? 'checks' : inst.key === 'criticality' ? 'signals' : 'components'}
          </summary>
          <ul class="mt-1">
            {#each rest as component (component)}
              {@render row(inst.key, component, false)}
            {/each}
          </ul>
        </details>
      {/if}
    </section>
  {/each}
</div>
