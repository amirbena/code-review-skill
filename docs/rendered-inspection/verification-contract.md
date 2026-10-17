# Change-Aware Verification Contract

Repository-development design record for the verification half of
**[#770](https://github.com/amirbena/code-review-skill/issues/770)** (C1 of epic
[#769](https://github.com/amirbena/code-review-skill/issues/769)). Not packaged;
explanatory. It specifies what a granted render inspects and how that is
recorded: diff-derived planning, viewport selection, input, the baseline
decision, and evidence and outcome semantics. The consent gate that precedes it
is owned by [`session-consent-contract.md`](session-consent-contract.md)
("consent contract" below). It extends
[`rendered-inspection-contract.md`](rendered-inspection-contract.md) (Epic
[#614](https://github.com/amirbena/code-review-skill/issues/614)) inside its
unchanged budget and changes no packaged resource. Implementation:
[#771](https://github.com/amirbena/code-review-skill/issues/771).

## 1. Verification planning

Once consent is `granted`, the existing "Inspection plan and default budget" of
[`rendered-inspection.md`](../../shared/policies/rendered-inspection.md) is
built from the diff. Planning is **static**: no render, no tool call beyond what
the review already performs. Each plan item names a *change class*, the
*property* to verify, the *evidence kind* (§4) that can settle it, and the
target and viewport.

| Change class (what the diff touches) | Properties planned | Kinds |
| --- | --- | --- |
| CSS Grid | track count and sizes, container and item dimensions, available width, alignment and gap, behavior at the changed breakpoint | `dom`, `visual` |
| Overflow and clipping | clipped or hidden content, scrollability, focus-outline visibility at the container edge, reachability of children | `dom`, `visual`, `interaction` |
| Typography and text | wrapping, truncation, overlap, layout shift on content or font change | `dom`, `visual` |
| Interaction and state | keyboard navigation, focus order and visibility, click-target accessibility, state transitions | `interaction`, `dom` |
| Responsive layout | reflow and element order on each side of the changed breakpoint, overflow at narrow widths, hidden or reordered content | `dom`, `visual` |
| Positioning and stacking | overlap, occlusion, and off-screen or clipped placement from position, offset, `z-index`, or stacking-context changes | `dom`, `visual` |
| Visibility and appearance | `display`, `visibility`, `opacity`, size, or colour changes that hide, reveal, or alter content a user needs | `dom`, `visual` |

These seven classes are the closed set of offer triggers: the consent gate
never offers for a property outside them, and a diff touching none has no plan.

**Proportionality.** Only classes the diff actually touches are planned. There
is no generic browser checklist and no check without a stated question it
answers (the existing "never a capture without a question" rule). A diff that
touches none of the classes has no plan, so the gate stays silent (consent contract §3). Inside
a touched class, only the properties the diff can affect are planned: a
`gap` change does not plan focus order.

**Specific offer.** The plan exists before the offer, so the offer can name what
would be checked. The two sentences of consent contract §4.1 stay verbatim; one line is appended
(for example "It would check grid column sizing and focus-outline visibility
under the new overflow"). The line names classes only; it makes no claim about
outcomes. If the plan is empty, there is no offer.

## 2. Viewport selection

The budget is unchanged: at most 2 viewports, 6 captures, 3 targets, one attempt
per target and viewport, 120 seconds in total. This record does **not** widen it.

- **Non-responsive change** (for example focus-outline or overflow with no media
  or container query): one viewport, the default desktop width. The unused
  second viewport is not spent.
- **Responsive change** (the diff adds or edits a breakpoint, media query,
  container query, or responsive utility): the two viewports sit on both sides
  of the relevant breakpoint, taken from the diff: the nearest representative
  width below it and at-or-above it. Examples, not requirements: 320, 375, 390,
  430 (mobile) and 768, 1440 (desktop).
- **More risk than budget** (several breakpoints, or more targets × viewports
  than 6 captures): keep the highest-risk breakpoint first, and record each
  uncovered one as `not-checked(budget)` with its width.
- **Theming** adds light/dark only when theming changed, as today, and counts
  against the same cap.

Anything the budget cannot cover is reported as unchecked (§4), never silently
dropped and never presented as covered.

## 3. Interaction capability and baseline

### 3.1 Input

The current capability definition (`rendered-inspection.md`, "Runtime
neutrality": navigate, viewport, capture, structure, accessibility, console)
cannot produce real keyboard or pointer input, so focus order, keyboard reach,
and state transitions cannot be settled today. **Decision: extend it by one
runtime-neutral clause**: dispatch keyboard (focus traversal and key presses)
and pointer (hover, click) input to the page under test. Still no named
automation product.

Bounds, all inside the existing isolation and budget rules:

- input goes only to the chosen target's origin, in the throwaway context;
- only actions the plan names; no form submission, no credential entry, no
  controls whose purpose is destructive or irreversible (delete, purchase,
  send), and no input that needs a signed-in state (v1 stays unauthenticated);
- the input steps of a target and viewport belong to its one attempt and count
  against the 120 s bound; the input-event cap is open (consent contract §12, question 4);
- **request guard, on every target:** while input is dispatched, any request the
  page makes to the target other than `GET` or `HEAD` is aborted, and a plan item
  that depends on a write is `not-checked(mutation blocked)`. Origin confinement
  alone does not do this: same-origin writes are otherwise allowed;
- **passive input only on a target outside the disposable boundary:** a declared
  running server and a trusted preview (sources 1 and 2 of the target order) may
  hold the user's real data, and a `GET` with side effects cannot be detected. On
  them input is limited to focus traversal, key navigation, and hover. Activation
  (click, Enter, Space) runs only on a started target (source 3) inside the
  verified isolation boundary; otherwise the check is `not-checked(target not
  disposable)`;
- the offer discloses that interaction may occur, and the consent it receives
  covers it (consent contract §4.1).

**When input is unavailable** the interaction checks are `not-checked(input
unavailable)`. The inspection still runs its other checks. A `dom` read that
reports a style or focusability **never** counts as an interaction result.

### 3.2 Before/after

**Decision: after only.** A baseline render needs the base revision served,
which is a second target and a second attempt against a budget that has neither,
and it must be bound to the base SHA while the existing contract forbids
carrying evidence between SHAs. v1 therefore renders the reviewed revision only.
The reviewer may say what the diff intended to change (static, from the diff) and
what the rendered revision shows. It never states that something "changed from"
or "regressed" on render evidence alone. Revisiting this needs a separate
amendment that spends target budget explicitly.

## 4. Evidence and outcome semantics

Every plan item records the three evidence kinds separately:

| Kind | What it is | Never proves |
| --- | --- | --- |
| `dom` | measurement or computed state read from the page (tracks, sizes, overflow, computed focus style, console) | visual correctness |
| `visual` | an observation of a captured rendering | keyboard or state behavior |
| `interaction` | the result of real input (focus moved, element reachable, state changed) | layout appearance |

A passing structural assertion (for example "four grid tracks") is a `dom`
result. It is never reported as visual correctness; a visual claim needs a
`visual` check. Screenshots are taken only where they materially help (a `visual`
item that DOM cannot settle), are never required per PR, and stay ephemeral and
outside the working tree, per the existing evidence record.

**Per-check status**, inside the existing `inspected` outcome (no new outcome):
`confirmed` (the concern was observed), `refuted` (checked at the stated
viewport and not observed), or `not-checked(<reason>)` with reasons such as
`budget`, `input unavailable`, `target`, `timeout`. A `refuted` result is scoped
to the viewports and states checked; it never generalizes.

The `Validation` entry of
[`rendered-inspection.md`](../../shared/policies/rendered-inspection.md),
"Evidence record", gains a compact `checks` slot beside the `consent` slot of consent contract §5:

`checks <property>:<kind>@<viewport>=<confirmed|refuted|not-checked(reason)>; …`

The entry therefore states what was inspected, viewports, interactions
exercised, observations, concerns confirmed or refuted, and checks not
completed. Mapping to the existing outcomes: at least one planned target
rendered and observed is `inspected` even when some checks are `not-checked`;
nothing rendered is `skipped`, `unavailable`, or `attempted-inconclusive` exactly
as before. The wording "visually verified" is allowed only for a property with a
`visual` check that ran.

**Findings.** A `confirmed` concern that a bounded observation on a SHA-matched
target directly demonstrates takes `confirmed` confidence (§7 of the [Epic #614 record](rendered-inspection-contract.md)). A static suspicion that a `refuted` check addresses at the checked
viewports is not reported as a defect, because the evidence contradicts it; it
may remain a note that names the scope of the refutation. A suspicion with
`not-checked` status keeps its static severity and its `credible` confidence, and
the unchecked status is stated once. Severity is never raised because
verification was declined, unavailable, or incomplete.
