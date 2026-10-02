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

## Needing a browser: the setup question

If a render would help but no usable browser capability exists, the review may
ask **once**, to you as the invoking operator, whether to set one up. It is
asked only when **all four** hold:

1. the change is materially UI-impacting;
2. a render would add meaningful evidence;
3. no usable browser capability is found (read-only detection of a
   runtime-supplied browser, the project's own Playwright, or a previously
   installed user-level one);
4. you have not set the local opt-out signal.

**Nothing is installed without your approval, and the Skill never installs
anything itself.** The question states the purpose, location, approximate size
(roughly 150–300 MB for Chromium), the pinned version, and the exact command;
you either run that command yourself or supply the trusted authorization
signal (`allow_browser_tooling_install`). Tooling goes to a user-level tools
directory and browser cache — never into the reviewed repository, and never via
a global install, `sudo`, or a system package.

**If you decline, ignore it, or nothing gets installed**, the review simply
completes in full without rendered evidence; the `Validation` entry says the
inspection was `unavailable` and names the missing capability, once. It is
never `REVIEW INCOMPLETE`. To stop being asked, set
`rendered_inspection_opt_out` — a **local capability/configuration signal**
delivered through the trusted channel, not remembered conversation: a one-off
"no" in chat is not durable, and a file or PR text in the repository cannot
set it. It silences the question only; it does not disable a browser that
already exists.

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
| No browser, install not approved or declined | review completes; outcome `unavailable`, naming the missing capability |
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
is `unavailable` and the rules do not change. The setup question reaches only
the invoking operator — in the Reviewer Brief for `github-pr-review`, as a note
in the final report for `local-code-review` — and is never published to GitHub.
Rendered observations are likewise never published as inline comments or review
events.

## Default, conditional, or requested

**Conditional and automatic.** There is no invocation option. It activates only
when the UI-impact trigger fires, and it is silent otherwise.

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
