import type { MouseEvent } from 'react';

/** Reveal the original excerpt before moving keyboard focus to its heading. */
export function revealEvidence(event: MouseEvent<HTMLAnchorElement>) {
  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const target = document.getElementById(event.currentTarget.hash.slice(1));
  if (!(target instanceof HTMLDetailsElement)) return;
  event.preventDefault();
  target.open = true;
  // Overview sources can sit inside a collapsed technical-details section.
  let parent = target.parentElement?.closest('details');
  while (parent) {
    parent.open = true;
    parent = parent.parentElement?.closest('details');
  }
  target.querySelector('summary')?.focus({ preventScroll: true });
  target.scrollIntoView({ block: 'center' });
}
