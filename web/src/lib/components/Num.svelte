<script lang="ts">
  // A changed number tweens briefly from the value on screen; reduced motion shows it at once.
  import { Tween } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { value as fmt } from '$lib/format';

  let { value, unit = '' }: { value: number; unit?: string } = $props();

  const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const tween = new Tween(0, { duration: reduced ? 0 : 180, easing: cubicOut });
  let first = true;

  $effect(() => {
    tween.set(value, { duration: first || reduced ? 0 : 180 });
    first = false;
  });

  // integers stay integers while they move
  const shown = $derived(Number.isInteger(value) ? Math.round(tween.current) : tween.current);
</script>

{fmt(shown, unit)}
