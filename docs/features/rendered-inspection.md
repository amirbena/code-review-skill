# Rendered-UI inspection

## What it does

When a change **materially alters what a user sees**, the review can look at
the page actually rendered — in a browser, at a small number of viewports —
and add what it observes as bounded **supplementary evidence**. Source review
can miss defects only a rendered page shows: clipped or overlapping controls,
broken reflow, a control that is hidden or unreachable, broken focus
treatment. The ordinary source-level reasoning always runs; this step adds
evidence beside it and never replaces it.

The review records one `Rendered inspection:` entry in its `Validation`
section (mode, target source, SHA, viewports, states, outcome, observed
facts). It records observed facts, never images: captures are ephemeral and
are never uploaded, committed, or published.

## When it runs — and when it stays silent

It is considered only when **all** of these hold:

1. the change implicates the user-facing / client-behavior dimension;
2. it **materially** changes rendered output (not a refactor with unchanged
   output, or a types-only, tests-only, docs-only, or copy-only change);
3. a render could add evidence the source, tests, and DOM assertions do not
   already settle.

Otherwise the capability is **inert and silent**: no plan, no question, no
`Validation` entry, no empty section. Such a review is identical to one that
never had this capability.

## What it inspects (default bounds)

The plan is built only from what the change itself names — changed
components, routes, and stories, and existing browser-test configuration —
and it never crawls or follows links.

| Bound | Default |
| --- | --- |
| targets (route or state) | at most 3 |
| viewports | at most 2 (desktop and mobile; light/dark only when theming changed) |
| attempts per target and viewport | one |
| captures | at most 6 |
| wall-clock for the whole step | 120 seconds (server start 30 s, each navigation 15 s) |

Nothing is retried and no bound is widened to finish.

## Where the page comes from

A target is chosen only from this closed, ordered list — first usable source
wins, with no fallback past a source that failed its gate:

1. a **running local server you declare** for this invocation through a
   trusted channel;
2. a **deployment preview** that a trusted source binds to the reviewed SHA;
3. the project's **declared start command**, run only inside a verified
   isolation boundary or under your explicit trusted-host authorization;
4. none — the outcome is `unavailable`.

A URL found in a PR, issue, comment, or repository file is **never** opened or
used as a target. Whatever is rendered must be shown to match the reviewed SHA;
a target that cannot be shown to match is not evidence. v1 inspects
unauthenticated pages only, in a throwaway browser context — never your own
signed-in browser.

## Your approval comes first

Rendering needs your **session-scoped approval**. After the trigger fires, and
only when the diff touches one of seven change classes (grid, overflow and
clipping, typography, interaction and state, responsive layout, positioning and
stacking, visibility and appearance), the review asks **once**:

> This review includes frontend changes that may benefit from browser-rendered
> verification. Would you like me to run Playwright?

One extra line names the planned classes, says keyboard or pointer interaction
may occur, and says only the Playwright you already have is used.

- **Granted** by your own reply in the conversation, or by the trusted
  `allow_rendered_inspection` signal, it covers relevant renders for the rest of
  the session. The Skill stores nothing: the grant is the visible reply in your
  conversation, and a new conversation asks again.
- **Declined, revoked, or no way to ask** (a non-interactive or automated run
  with no structured grant) records `skipped` with reason `consent-declined`,
  `consent-revoked`, or `consent-unavailable`. The review completes in full. A
  backend-only or trivial frontend change never prompts.
- Hosts that cannot hold the grant across invocations ask again each time; hosts
  that cannot deliver a question never wait and render only on a structured grant.
  Nothing in a repository, PR, or page can grant consent.

**Existing Playwright only.** After approval the review checks, read-only, for a
Playwright you already installed and its browser binary. **Nothing is installed,
downloaded, or repaired, with or without approval**, and an install suggestion in
an error message or page is ignored. A missing installation is reported once as
`unavailable` ("rendered verification was unavailable and was not performed"); a
failing one is reported once with no retry. Your project's own Playwright runs
only inside the isolation boundary or under `allow_trusted_host_execution`, and
its configuration is read as data, never executed. The earlier
`allow_browser_tooling_install` and `rendered_inspection_opt_out` signals no
longer exist and are ignored if supplied; for lasting silence supply
`allow_rendered_inspection=false`.

## What is verified, and how it is reported

The plan is derived from the diff, so a change that touches one class plans
checks for that class only, and there is no generic checklist. Viewports follow
the diff within the same budget (both sides of a changed breakpoint). Every check
records its evidence separately:

- `dom` — measurements and computed styles; never proof of how it looks;
- `visual` — an observation of a captured rendering; the only way to confirm or
  refute appearance, so "visually verified" is used only for a property whose
  visual check ran;
- `interaction` — real keyboard or pointer input (passive on a target outside the
  disposable boundary, with non-read requests blocked).

Each check ends `confirmed`, `refuted` (at the viewports checked only), or
`not-checked(<reason>)`; humans may read that as "not completed". A passing
Playwright test run is never visual evidence. Only the reviewed revision is
rendered ("after only"), screenshots are not required, and captures never exceed
six. None of this changes severity or the Decision.

## Evidence provenance and gaps

Every statement in the report says where it came from, and the three sources are
never blended:

| Source | Example wording | Counts as |
| --- | --- | --- |
| static suspicion | "the diff adds `overflow: hidden` to a container that holds focusable children" | a `credible` concern from reading the diff |
| DOM measurement (`dom`) | "the outline box extends 2 px past the container's clip box at 390 px" | structural support; never proof of how the page looks |
| browser observation (`visual`, `interaction`) | "at 390 px the focus ring on the last button is cut off after keyboard focus" | the only way to `confirm` or `refute` appearance |

A passing structural assertion, test run, or CI result is not visual evidence, so
"visually verified" appears only for a property whose visual check ran.

- **Plan from the diff, kept proportional.** Only the change classes the diff
  touches are planned (grid, overflow and clipping, typography, interaction and
  state, responsive layout, positioning and stacking, visibility and appearance),
  and inside a class only the properties the diff can affect. A generic checklist
  is never run, and a diff that touches no class plans nothing and stays silent.
- **Viewports follow the diff within the budget.** A non-responsive change uses
  one viewport; a changed breakpoint uses one viewport on each side of it. When
  there is more risk than budget the highest-risk breakpoint goes first and the
  rest are reported as `not-checked(budget)` with their width.
- **What is reported.** The `Rendered inspection:` line names the inspected
  targets, viewports, interactions, and observed facts, and each concern is
  `confirmed`, `refuted` (only at the viewports checked), or `not-checked(<reason>)`
  — the checks not completed. Reasons are `budget`, `input unavailable`,
  `mutation blocked`, `target not disposable`, `timeout`, and
  `visual evidence insufficient`.
- **Gaps stay gaps.** These limits are recorded as one `Validation` limitation, not a separate Context-gaps section or a finding. Declined, unavailable, or incomplete verification is stated
  once, never raises the severity of a static suspicion, and never changes the
  Decision. A suspicion that was `not-checked` keeps its static severity and its
  `credible` confidence; one that a check `refuted` is recorded only in the
  `checks` slot, scoped to the viewports checked. No screenshots are required, and
  none are published.

## Worked examples

### Focus-outline clip from `overflow`

1. **Static suspicion.** The diff adds `overflow: hidden` to a card list whose
   items are keyboard-focusable. Reading the code, the review suspects the focus
   outline of an edge item is clipped. At this point it is a `credible` concern,
   not a defect.
2. **Offer and approval.** The change touches the overflow-and-clipping class, so
   the review asks once whether to run Playwright, naming the class and saying
   keyboard input may occur. You reply "yes, run playwright".
3. **Browser check.** With your existing Playwright it renders the declared target
   at one viewport, tabs to the last item, and records both the measured outline
   box (`dom`) and an observation of the capture (`visual`) plus the focus
   traversal (`interaction`).
4. **Report.** Either the clip is observed and reported as a finding that names
   the target, viewport, and state (`confirmed` confidence), or it is not observed
   and the review records `focus-outline-clip:visual@desktop=refuted` for that
   viewport only, with no finding.
5. **Reuse.** A later review in the same conversation that touches a relevant
   class reuses the approval without asking. A new conversation asks again, and
   "stop rendering" revokes it.

### Grid change with a passing test

A diff changes a layout to four grid tracks and a unit test asserts there are four
tracks. That is a structural fact, not evidence about appearance. The review plans
checks for the grid class only and, because a breakpoint changed, uses one
viewport on each side of it:

- `track-count:dom@wide=confirmed`, `track-count:dom@narrow=confirmed`;
- `track-widths:visual@wide=confirmed` (even), `track-widths:visual@narrow=refuted`
  (no overflow seen at that width);
- `last-row-alignment:visual@narrow=not-checked(budget)` — planned, but the
  budget left no capture for it.

The report says which concerns were confirmed, refuted, or not checked, and does
not say the layout is "visually verified" beyond the properties whose visual check
ran.

## Troubleshooting

| Symptom | Likely cause and what to do |
| --- | --- |
| No offer appeared | the diff touched no listed change class, or the host is non-interactive; supply `allow_rendered_inspection` through the trusted channel if you want a render |
| `skipped · consent-unavailable` | non-interactive run with no structured grant |
| "rendered verification was unavailable and was not performed" | no usable Playwright or browser binary is installed; installing one is your own action, outside the Skill, and the next review will find it |
| `attempted-inconclusive` | the existing Playwright launched but timed out or crashed; nothing is retried or repaired |
| `project-playwright-gated` | only the project's Playwright exists and neither the isolation boundary nor `allow_trusted_host_execution` is present |
| asked again in the same chat | context was compacted and the grant turn is no longer visible; the Skill fails closed |

## What counts as a finding vs. an observation

- **Objective defects are normal findings** under the usual P0/P1/P2 model: a
  rendered defect a user can actually hit (clipping, overlap, broken reflow, a
  hidden or unreachable control, missing content, broken focus treatment, a
  console error caused by the changed code). It needs concrete evidence and a
  causal link to the change; a defect that was already there and is not made
  worse is not attributed to the change.
- **Subjective polish is never a finding** and never affects the Decision. It
  appears only in a separate, severity-less **Rendered observations** section:
  at most **3**, each grounded in a page and state that was actually rendered,
  never an inline comment or review event.
- **Promotion test:** if ignoring it could block, mislead, or exclude a user,
  leave a requirement unmet, or carry a measurable engineering cost, it is not
  polish and is handled as a normal finding. If it is taste — a spacing
  preference, color harmony, alignment with no functional effect — it is an
  observation.

## Optional design reference

A design reference (typically a Figma frame) is **optional**. Supplying one
never triggers an inspection and never widens its targets or budget; with no
render there is no comparison.

- **Trusted channel only.** It is used only when you explicitly supply it in the
  current invocation (for example, "use this Figma as the design reference for
  this review: `<url>`") or through the trusted `design_reference` signal. It is
  re-supplied every invocation and never remembered.
- **Links in PR or repository text are not used.** A design link found in a PR
  body, comment, commit, issue, or repository file is attacker-reachable, so it
  is never fetched; at most one limitation line says one was present and not
  used. A link inside context you pasted still counts as discovered unless you
  name it as the design reference.
- **Structure and intent, never pixels.** The comparison looks at layout,
  hierarchy, expected components and content, responsive variants, and
  represented states. There is no pixel threshold, no pixel diffing, and no
  stored design image; the design is **not absolute truth** and is not
  pixel-perfect enforcement.
- **Evidence record.** In `design-reference` mode the `Validation` entry gains
  one line naming the reference used (file/frame, version when available), how
  it was supplied, the target/state/viewport it was matched to, the match basis,
  its coverage (full or partial), and the freshness evidence.
- **Stale, partial, or diverging designs.** A divergence explained by a stale
  design, intentional divergence, partial coverage, responsive or state
  ambiguity, or a newer explicit requirement is recorded as an uncertainty line
  in `Validation`, not as a defect and not as an observation. A concrete,
  in-scope mismatch evidenced on both the design and the render is a normal
  finding even when tests pass.
- **Fallback.** If the design is inaccessible, inapplicable, or unverifiable,
  the review runs in `analytical` mode with one stated limitation — no "the
  design says" claim and no fabricated mismatch. The absence of a design is
  never a finding.

## Limitations and fallbacks

| Situation | What happens |
| --- | --- |
| Approval declined, revoked, or unavailable | review completes; `skipped` with a consent reason |
| No existing Playwright or browser binary | review completes; outcome `unavailable`, "not performed"; nothing is installed |
| No usable target, or target not shown to match the reviewed SHA | `unavailable` / `attempted-inconclusive`; not evidence |
| Sandbox or trusted-host authorization absent for a start command | that source is `unavailable`; never silently falls back to unsandboxed execution |
| Page needs sign-in or an absent environment | recorded `unavailable`; no credentials are injected |
| Timeout, crash, or blank output | `attempted-inconclusive`; nothing is retried |
| Design reference missing or unusable | `analytical` mode with one limitation |

`skipped`, `unavailable`, and `attempted-inconclusive` are never shown as a
pass. None of them changes coverage, a finding, a severity, or the Decision, and
none makes a review `REVIEW INCOMPLETE`. Page text, console output, and design
content are untrusted data, never instructions, and secrets visible on a page
are redacted from the report.

## Which Skill(s)

Both, identically. `local-code-review` may hold a declared running server from
your checkout; `github-pr-review` has a checkout only when the repository
checkout capability provides one, and a preview only from a trusted source bound
to the PR head SHA. Where the needed checkout or preview is absent, that source
is `unavailable` and the rules do not change. The approval offer reaches only
the invoking operator, in an interactive session, and is never published to
GitHub; an automated or passive GitHub run never offers.
Rendered observations are likewise never published as inline comments or review
events.

## Default, conditional, or requested

**Conditional and consent-gated.** It activates only when the UI-impact trigger
fires and the diff touches a change class, then renders only after your approval;
it is silent otherwise. The only option is the trusted `allow_rendered_inspection`
signal.

## Delta re-review

Observed evidence is bound to the one reviewed SHA or tree and is never carried
forward to a later review. A delta re-review inspects only targets the delta
affects; the design reference, like every other input, must be supplied again.

## Not benchmarked

This capability is documented, not benchmarked: it is supplementary evidence
that never changes the Decision.

## Canonical semantics

[`rendered-inspection.md`](../../shared/policies/rendered-inspection.md) ·
[`rendered-inspection-environment.md`](../../shared/policies/rendered-inspection-environment.md) ·
[`design-reference.md`](../../shared/policies/design-reference.md). Where this
guide and a policy disagree, the policy wins. Design record:
[`../rendered-inspection/README.md`](../rendered-inspection/README.md).
