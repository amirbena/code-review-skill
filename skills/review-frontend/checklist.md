# Frontend checklist

Use as prompts for tracing, not as a list to tick through. Each item needs
a concrete consequence in this change to become a finding.

## Behavior and state

- State derived or copied from props and left stale; updates that race
  (out-of-order responses, double submit); unmounted components updating.
- Effects, memos and callbacks with missing or wrong dependencies; cleanup
  of listeners, timers and subscriptions.
- Loading, error and empty states for every new async path; optimistic
  updates that never roll back.
- Forms: validation, disabled and submitting states, preserved input on
  error. Routing, navigation guards and URL state kept in sync.
- Escaping of rendered content: raw HTML insertion, unsafe URLs in links
  and sources, secrets or tokens placed in client bundles or storage.

## Accessibility

- Interactive elements that are real controls, reachable and operable by
  keyboard, with a visible focus state and sensible focus order.
- Names, roles and states for assistive technology: labels on inputs,
  alt text, ARIA used correctly and not to paper over wrong elements.
- Focus moved into and restored from dialogs and menus; announcements for
  async changes; no keyboard trap.
- Contrast, reduced-motion, text scaling and touch-target size where the
  change touches styling.

## Responsive and visual

- Layout that depends on fixed sizes, overflow, z-index or positioning
  that changed; behavior at narrow and wide viewports and in right-to-left
  text.
- Components that differ from the supplied design reference in structure
  or behavior within the frame, viewport and state the design covers.

## Rendered checks (only after render consent)

- Clipped, overlapping or unreachable controls; broken reflow; missing
  focus treatment; console errors on load; the new state visibly present.
