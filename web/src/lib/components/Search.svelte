<script lang="ts">
  // Project search over the panel: a combobox with keyboard navigation.
  import type { Project } from '$lib/data';

  let { projects, onpick }: { projects: Project[]; onpick: (p: string) => void } = $props();

  let text = $state('');
  let open = $state(false);
  let active = $state(0);
  let input: HTMLInputElement;

  const matches = $derived.by(() => {
    const q = text.trim().toLowerCase();
    if (!q) return [];
    const starts = projects.filter((p) => p.project.toLowerCase().split('/').some((part) => part.startsWith(q)));
    const has = projects.filter((p) => !starts.includes(p) && p.project.toLowerCase().includes(q));
    return [...starts, ...has].slice(0, 8);
  });

  function pick(p: string) {
    onpick(p);
    text = '';
    open = false;
    input.blur();
  }

  function key(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      active = Math.min(matches.length - 1, active + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      active = Math.max(0, active - 1);
    } else if (e.key === 'Enter' && matches[active]) {
      e.preventDefault();
      pick(matches[active].project);
    } else if (e.key === 'Escape') {
      open = false;
      input.blur();
    }
  }
</script>

<div class="relative w-full sm:w-80">
  <input
    bind:this={input}
    bind:value={text}
    oninput={() => ((open = true), (active = 0))}
    onfocus={() => (open = true)}
    onblur={() => setTimeout(() => (open = false), 120)}
    onkeydown={key}
    type="search"
    placeholder="Search {projects.length.toLocaleString('en-GB')} projects"
    aria-label="Search projects"
    role="combobox"
    aria-expanded={open && matches.length > 0}
    aria-controls="search-results"
    aria-activedescendant={matches[active] ? `opt-${active}` : undefined}
    autocomplete="off"
    spellcheck="false"
    class="h-9 w-full rounded-lg border border-line bg-raised px-3 text-[14px] text-ink placeholder:text-ink-3 focus:border-line-strong focus:outline-none"
  />
  {#if open && matches.length}
    <ul
      id="search-results"
      role="listbox"
      class="absolute right-0 left-0 z-20 mt-1 origin-top overflow-hidden rounded-xl border border-line bg-surface py-1 shadow-[0_8px_24px_rgba(0,0,0,0.08)]"
    >
      {#each matches as m, i (m.project)}
        <li
          id="opt-{i}"
          role="option"
          aria-selected={i === active}
          onpointerdown={(e) => (e.preventDefault(), pick(m.project))}
          onpointerenter={() => (active = i)}
          class="mx-1 flex cursor-pointer items-baseline justify-between gap-3 rounded-lg px-2.5 py-1.5 text-[14px] {i === active ? 'bg-raised text-ink' : 'text-ink-2'}"
        >
          <span class="truncate">{m.project}</span>
          <span class="mono shrink-0 text-xs text-ink-3">{m.crossd_readings} readings</span>
        </li>
      {/each}
    </ul>
  {/if}
</div>
