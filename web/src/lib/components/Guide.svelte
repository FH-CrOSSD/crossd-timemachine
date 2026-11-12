<script lang="ts">
  // How to read the page, for visitors who have not read the paper. Open on the first visit; the
  // choice to close it is remembered in this browser only.
  import { onMount } from 'svelte';
  import { day } from '$lib/format';

  interface Props {
    freeze: number;
    cohortSize: number;
  }

  let { freeze, cohortSize }: Props = $props();
  let open = $state(true);
  const KEY = 'guide-open';

  onMount(() => {
    try {
      // ?guide=closed opens the page without the panel, for screenshots and embedding
      if (new URLSearchParams(location.search).get('guide') === 'closed') {
        open = false;
        return;
      }
      const saved = localStorage.getItem(KEY);
      if (saved !== null) open = saved === '1';
    } catch {
      /* storage blocked: stay open */
    }
  });

  function toggle(e: Event) {
    open = (e.currentTarget as HTMLDetailsElement).open;
    try {
      localStorage.setItem(KEY, open ? '1' : '0');
    } catch {
      /* not remembered */
    }
  }
</script>

<details id="guide" class="group mt-6 rounded-2xl border border-line bg-surface px-5 py-3" {open} ontoggle={toggle}>
  <summary class="press flex cursor-pointer list-none items-center justify-between gap-4 text-[15px] text-ink">
    <span class="font-medium">How to read this page</span>
    <span class="text-[13px] text-ink-3 group-open:hidden">Show</span>
    <span class="hidden text-[13px] text-ink-3 group-open:inline">Hide</span>
  </summary>

  <div class="mt-3 grid gap-x-10 gap-y-4 pb-2 text-[14px] leading-[1.55] text-ink-2 md:grid-cols-2">
    <div>
      <h4 class="font-medium text-ink">The question</h4>
      <p>
        Open-source health and security scores are read as early warnings. This page shows what four of them said
        about a project at a date you choose, and what happened to the project afterwards. It uses only public data
        at project level.
      </p>
    </div>
    <div>
      <h4 class="font-medium text-ink">t0, the orange line</h4>
      <p>
        The date you look from. Left of the line and in “What the scores said”: only values that had been read from
        their source by then. Right of it and in “What happened next”: events after that date, known up to the data
        freeze on {day(freeze)}. Drag the line, or focus it and use the arrow keys to step from reading to reading.
      </p>
    </div>
    <div>
      <h4 class="font-medium text-ink">Reading date</h4>
      <p>
        Every value shows the date it was read from GitHub or published. That date decides whether a value counts at
        t0. The date of the snapshot a value belongs to does not: CrOSSD sometimes read a snapshot's data weeks later,
        and a weekly Scorecard scan runs for several days, so it is dated a week after its scan date.
      </p>
    </div>
    <div>
      <h4 class="font-medium text-ink">Recorded, reconstructed, not backdatable</h4>
      <p>
        <span class="text-ink">Recorded</span>: stored at the time by the instrument itself.
        <span class="text-ink">Reconstructed</span>: computed later by the authors from data dated before t0, such as
        git history and dated issues, with today's rules.
        <span class="text-ink">Not backdatable</span>: the check needs a state that GitHub only reports for today, so
        no value is shown.
      </p>
    </div>
    <div>
      <h4 class="font-medium text-ink">The four instruments</h4>
      <p>
        <span class="text-ink">CrOSSD</span> health metrics, crawled weekly from GitHub since April 2024.
        <span class="text-ink">OpenSSF Scorecard</span> security checks, each 0 to 10, and a weighted aggregate.
        <span class="text-ink">OpenSSF Criticality Score</span>, how important a project is, 0 to 1.
        <span class="text-ink">openCode badges</span> for maintenance and security, from the rules of the German
        public-sector code platform. Open “more” under a value to see what it measures and what its makers say about it.
      </p>
    </div>
    <div>
      <h4 class="font-medium text-ink">Operating point</h4>
      <p>
        The value at which a score reads as a warning, as its documentation states it or as the paper reads it: for
        example Scorecard Maintained = 0, or a bus factor of at most 1. Under an event, the page lists every tested
        score that stood at its operating point when the event happened, and since when (the lead time).
      </p>
    </div>
    <div>
      <h4 class="font-medium text-ink">Events</h4>
      <p>
        Archived on GitHub; repository gone, dated by Software Heritage; twelve months without a commit or tag; a
        severe security advisory (OSV, CISA KEV) and whether a fixed version was listed; the last commit. “Failed”
        on this page means archived, gone or twelve months without a commit or tag.
      </p>
    </div>
    <div>
      <h4 class="font-medium text-ink">Look-alikes and measured validity</h4>
      <p>
        Look-alikes split the {cohortSize.toLocaleString('en-GB')} projects of the cohort (active on 1 Aug 2024, from
        two CrOSSD lists) at the operating point and count what happened to each group by the data freeze; later t0
        leave less time for events. The validity sentence quotes the paper. <span class="text-ink">AUROC</span> is the
        chance that a project with the outcome had a worse value than one without: 0.5 is a coin toss, 1 is perfect.
        A score “warned” if the lower end of its 95% interval lies above 0.60.
      </p>
    </div>
    <p class="text-[13px] text-ink-3 md:col-span-2">
      A score is not a verdict on the people who maintain a project, and projects end for good reasons too.
    </p>
  </div>
</details>
