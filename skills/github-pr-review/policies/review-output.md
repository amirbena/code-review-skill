# Policy — Review Output

Governs the analysis/publication boundary, batched review submission,
final summary, final decision, and HEAD revalidation for
`github-pr-review`. Canonical index:
[`github-review.md`](github-review.md).

## Analysis phase vs. publication phase

These are strictly separate, and publication never begins until analysis
is complete:

```text
analysis phase                          publication phase
───────────────                         ─────────────────
inspect file                            all reviewable files processed
    ↓                                       ↓
discover candidate finding              evidence verified
    ↓                                       ↓
record internally, keep reviewing       findings deduplicated
    ↓                                       ↓
    ...                                 severity finalized
    ↓                                       ↓
scope complete                         inline locations resolved
                                            ↓
                                        decision finalized
                                            ↓
                                        submit one review
```

A candidate finding may be confirmed, downgraded, upgraded, merged with
another finding, discarded after further evidence, or have its location
changed at any point during the analysis phase. Nothing is published
during this phase — no comment, no partial review, no decision. Only the
finalized set of findings, produced once analysis is complete, is
eligible for publication. This prevents noisy comment streams,
contradictory or duplicate comments, publishing findings that are later
discovered to be false, and unnecessary notification spam.

## Batched review construction and submission

`github-pr-review` MUST NOT publish a comment, or any part of a review,
as each finding is discovered. Findings accumulate internally during
analysis (see "Analysis phase vs. publication phase") and are published
together, once, as a single coherent GitHub review submission:

```text
finalized findings
    ↓
resolve inline eligibility (see finding-placement.md)
    ↓
one review body                one inline comment per
(review-summary.md shape,      inline-eligible finding
full findings only for              (inline-finding.md)
non-inline findings, summary-
pointers for inline ones)
    ↓                                ↓
        one GitHub review submission
        (body + inline comments + event)
```

**Default path — atomic submission.** When the available GitHub
integration supports creating a review with a body, an array of inline
comments, and an event in a single request (for example, the GitHub REST
"create a review for a pull request" operation, which accepts `body`,
`comments[]`, and `event` together), use it. This is the default and
preferred mechanism: it produces exactly one review object and one
notification, containing every finalized inline finding at once.

**Fallback path — still one review.** If the available integration
cannot submit body, comments, and event atomically, use the minimum
number of calls that still yield exactly one review object from the PR
author's perspective: open one pending/draft review, attach every
finalized inline comment to that same pending review, then submit it
once with the body and event. Do not create standalone comments outside
a review object, and do not submit more than one review event for one
finalized set of findings.

**Prohibited shapes**, regardless of which path is used:

```text
inspect file A → publish comment
inspect file B → publish another comment
inspect file C → publish another comment
...                                                    ✗ prohibited

finding discovered → notification
finding discovered → notification
finding discovered → notification                     ✗ prohibited
```

The author receives one coherent review event, not a stream of
interruptions.

## Stable review-body heading

The review body always starts with `## Review Summary` — the
`github-pr-review`-specific override of the shared default heading, per
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md),
"Heading is a per-Skill override point". This applies to every rendered
case in
[`../templates/external-review-summary.md`](../templates/external-review-summary.md)
(clean, findings, fallback, and the self-review informational `COMMENT`)
and to both the structured and the `human_review_output` senior-voice
rendering — the heading never changes with mode, verdict, or reviewed
HEAD. It replaces the previously used `## Code Review` heading; this is a
rendering-only change and affects nothing else in this file's semantics.

## Reader-visible severity legend

Every finding heading (the finding-list / summary-pointer line, the
fallback full-rendering block, the inline structured `[<severity>]` form,
and the human inline voice's heading) can show the severity code together
with one short, canonical parenthetical, defined once here and applied
consistently — this is the per-Skill severity-legend override point
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Fields" and
[`../../../shared/templates/finding-rendering.md`](../../../shared/templates/finding-rendering.md)
describe:

```text
P0 (Critical)
P1 (Blocking)
P2 (Non-Blocking)
```

**Default: compact.** Every surface named above renders the bare `P0` /
`P1` / `P2` code, with no parenthetical, unless the invocation opts in.
**Opt-in expansion** is controlled by the `include_severity_description`
invocation option (default `false`), normalized per
[`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
"`include_severity_description` phrasings" — when it resolves `true`,
every one of those surfaces substitutes the parenthetical mapping above
for the plain code, consistently, with no other change to any surface's
shape.

This wording is aligned with, and never contradicts,
[`../../../shared/policies/severity.md`](../../../shared/policies/severity.md):
both `P0` and `P1` remain blocking per that policy's "Blocking rule" —
`P0`'s parenthetical names its critical/rare tier, `P1`'s names its
blocking status, and `P2`'s names that it never blocks alone. The
parenthetical, when enabled, is rendered **once**, in the finding's
heading, never as a repeated explanatory paragraph elsewhere in the same
finding or review; it is presentation only and never changes severity,
identity, deduplication, evidence requirements, or the decision
derivation owned by `severity.md` — the option that toggles it
(`include_severity_description`) is likewise presentation-only and
controls nothing else: not whether severity is shown, not whether the
headline is emphasized. `local-code-review` defines no such legend and
continues to render the bare `[P0]` / `[P1]` / `[P2]` form regardless of
this option's value — it is normalized for cross-Skill parity only and
has no effect there.

### Emphasized-headline contract, by surface

Every finding-headline surface this Skill owns renders the **complete
headline** — severity, the optional description when enabled, and
title — as **one emphasized unit**; the title is never emphasized
separately from the severity:

- **Summary-pointer / consolidated external-review-summary findings
  list**
  ([`../templates/external-review-summary.md`](../templates/external-review-summary.md)) —
  explicit Markdown strong emphasis (`**...**`) wraps severity + optional
  description + title together: `**P1 — Title**` (default) /
  `**P1 (Blocking) — Title**` (expanded). Never `P1 — **Title**` (title
  bolded separately from severity).
- **Full finding heading** (`### <id> [<severity>] <title>`, the
  fallback/no-anchor body rendering) — emphasis comes from the Markdown
  heading level, not `**...**`; the entire visible headline sits inside
  that one heading line, with no part of it demoted outside it:
  `### <id> [P1] <title>` (default) / `### <id> [P1 (Blocking)] <title>`
  (expanded).
- **Structured inline finding**
  ([`../templates/inline-finding.md`](../templates/inline-finding.md)) —
  plain text, no heading, no bold, unchanged by this option beyond
  whether the parenthetical renders, per its existing "GitHub already
  supplies file/line context" rationale: `[P1] <title>` (default) /
  `[P1 (Blocking)] <title>` (expanded).
- **Human-review rendering** (human inline `<severity>: <title>` and
  human full `### <id> <severity>: <title>`, per
  [`../../../shared/templates/finding-rendering.md`](../../../shared/templates/finding-rendering.md))
  — the option controls only whether the parenthetical is present; each
  surface's existing emphasis mechanism (a heading for human full, none
  for human inline) is unchanged: `P1: <title>` (default) /
  `P1 (Blocking): <title>` (expanded).

Where a surface has a legitimately different container (a Markdown
heading vs. inline plain text vs. explicit `**...**`), that container is
preserved unchanged; this option never forces one single emphasis
mechanism onto every surface, and never moves a finding between surfaces.

## Stacked-PR context

When [`stacked-pr-review.md`](stacked-pr-review.md) has resolved this PR's
stack topology, the review states, for the layer under review: the
detected stack root-to-current (`main -> PR A -> PR B`), or "no stack
detected"/the fallback tier and reason when one applied; which layer is
under review; and the effective review base actually used, when it
differs from the repository's default/target branch. This is a required,
always-present field — like `change_risk_depth` — rendered as "no stack
detected" for the ordinary, non-stacked case so its presence never
changes the visible output of the overwhelming majority of reviews.
Concrete rendering is owned by
[`../templates/external-review-summary.md`](../templates/external-review-summary.md),
"Stacked-PR context." This field never changes finding severity, identity,
placement, or the mechanical decision derivation — it is presentation of
the scope already resolved, not a new decision input.

## Final summary

A single human-readable review body, using
[`../templates/external-review-summary.md`](../templates/external-review-summary.md)
(the shared shape in
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md)),
is constructed from the finalized findings and submitted as part of the
one review submission above. When publication is unavailable, it is
instead returned to the caller with publication status.

It reads like a review a strong human reviewer would leave: verdict
first, then a scannable list of the findings that need action, then stop.
**Detail ownership is split**: a finding published as a detailed inline
comment appears in the body as a single summary-pointer line (severity,
title, location) and its evidence/impact/reasoning/fix are **not**
repeated there; only a finding with no valid inline anchor carries its
full field block in the body — the structured full rendering by default,
or, when `human_review_output` is on, the human full rendering per the
shared [`../../../shared/templates/finding-rendering.md`](../../../shared/templates/finding-rendering.md),
"Canonical human full rendering" (see "Concise human-style summary
(opt-in)" below). Process and machine state (review mode,
SHAs, counts, publication mode, mutation outcome) are subordinate — a short
trailing block, never the body. A self-review publishes the **same**
human-facing body as an informational `COMMENT`, differing only by the
closing disclosure line in
[`../templates/external-review-summary.md`](../templates/external-review-summary.md),
"Self-review (informational COMMENT)" — not by a separate, heavier
format.

This review body **is** the final human-facing summary comment for the
run: `final review comment == last publication event` (see "Submission
ordering"). Nothing this review owns — an inline comment, the review
event, an optional machine-readable status/check, or an edit to any of
them — is published after it.

### Density and de-duplication

Both rendering modes (structured and `human_review_output`) follow the
explicit, testable density/de-duplication guidance owned once, for both
Skills, by
[`../../../shared/templates/finding-rendering.md`](../../../shared/templates/finding-rendering.md),
"Senior voice contract", "Density, de-duplication, and voice tightening":
omit empty/low-value sections, never restate the diff, never narrate
file-by-file inspection or reproduction mechanics beyond the
`Validation` / `runtime-validation.md` record, never repeat the same
evidence across the summary line, a fallback full finding, and its
inline comment, and let output length scale with the number and
complexity of findings rather than with the number of available template
sections. There is no numeric word or line cap.

### No agent/model/tool disclosure

The human-facing review body and every inline comment never disclose or
advertise the underlying agent, model, or tool that produced the review
— no "Generated by", "Powered by", model name, vendor name, or similar
signature anywhere in the published review content. This is distinct
from, and does not touch, this repository's own separate repository-
development convention for AI-assistance disclosure in a *contributed*
PR's own body (owned outside this packaged Skill, by this source
repository's own contribution policy) — that is a PR-body convention for
contributions to *this* repository, not part of the review output this
Skill publishes about a *reviewed* PR. No packaged `github-pr-review`
template, runbook, or policy resource may introduce such a signature into
published review content.

### Concise human-style summary (opt-in)

When the invocation selects `human_review_output` — normalized from
natural language per
[`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
"`human_review_output` phrasings" (there is no required flag such as
`--human-review-output`) — this review body is rendered in the concise
senior-engineer voice defined in
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md),
"Concise human-style summary (opt-in)": a short opening on merge safety
and the top concern, then what's good / what's concerning / what to
change in prose, each referenced finding keeping its `P0` / `P1` / `P2`
label, an intentional trade-off optionally raised as a question, and no
review-process or machine metadata. Inline comments still own each
finding's full detail; the concise body still carries one summary-pointer
line per inline finding so every finding appears exactly once.

`human_review_output` re-words this final summary and, for every finding
that has no inline comment and is instead rendered in full in the body
(a passive review's findings, or an active-review finding with no valid
inline anchor per [`finding-placement.md`](finding-placement.md)), it
re-words that finding too — via the shared
[`../../../shared/templates/finding-rendering.md`](../../../shared/templates/finding-rendering.md),
"Canonical human full rendering" — so a senior-mode review never leaves a
body finding in the structured block while everything around it reads in
senior voice. This holds identically in passive review (where every
finding is a body finding) and in active review's inline-anchor
fallback. Its derived companion option `human_inline_findings` — default
`explicit_value ?? human_review_output`, so on by default under senior
mode — separately re-words the **inline comments** to match, per
[`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
"`human_inline_findings` derived default and phrasings" and
[`../templates/inline-finding.md`](../templates/inline-finding.md),
"Human-rendered inline finding (opt-in)". An explicit
`human_inline_findings=false` keeps the structured
`[<severity>] / Evidence / Impact / Fix` inline block under a concise
body; an explicit `human_inline_findings=true` re-voices the inline
comments even when this body is structured. `human_inline_findings` is
never what governs a body finding's voice — that is always
`human_review_output` directly, so an explicit `human_inline_findings`
value has no effect on body/fallback findings.

Both options are **presentation only**. Mode on and mode off produce the
identical finalized findings, severities, finding identity,
deduplication, canonical fix/action locations, publication anchors, the
`#164` / `#165` body-fallback behaviour, GitHub review state
(`APPROVE` / `REQUEST_CHANGES` / `COMMENT`), mechanical decision,
publication ordering, and optional machine-readable status — only the
wording changes: this final summary and every body-rendered finding
whenever `human_review_output` is on, and the inline comments when
`human_inline_findings` is on. When both options are off (the default),
the body, its full/fallback findings, and the inline comments use the
existing structured shapes unchanged. The self-review informational
`COMMENT` uses the same concise body plus its unchanged closing
disclosure line.

### Publishing a previously produced passive review

A passive review (`runbooks/passive-pr-review.md`) may already have been
shown to the user — in either presentation — before a later, separate
request asks to publish or post it (e.g. "publish it", "post the
review"). That publish request is a fresh active-review invocation and,
per [`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
"Invocation isolation and mediation parity," normalizes presentation
options from its own current-invocation text only — it does not inherit
`human_review_output` from the earlier passive invocation. Left
unaddressed, this silently republishes a different presentation than the
one the user already saw.

When the current publish request does not itself resolve a presentation
(no explicit `human_review_output` / `human_inline_findings` value or
recognized phrasing, per that shared policy), and it is asking to publish
a review already produced passively earlier in this same interaction,
`active-pr-review.md` asks the user once, before proceeding further,
which presentation to publish — **Senior/human** or **Structured**. The
presentation the passive review was actually shown in may be offered as
the recommended choice (see that shared policy, "Offering, never
applying, a prior value"), but is never silently applied without an
answer. The answer is normalized as ordinary current-invocation text,
exactly like any other option value. If no answer can be resolved (a
non-interactive or mediated caller with no way to surface the question),
withhold publication — report `Mutation: WITHHELD (publication format
unresolved)` per "Reporting" in
[`review-action-authorization.md`](review-action-authorization.md) —
rather than defaulting to structured presentation.

This question is asked **only** for that specific case. It is never asked
for an ordinary active-review invocation that already establishes its
presentation — directly (an explicit option or recognized phrasing) or
through senior intent stated in the same request (e.g. "senior review
this PR and publish it", "review #123 and post it in structured
format") — and never for a fresh active review that was not preceded by a
passive result the user already saw. See
[`../runbooks/active-pr-review.md`](../runbooks/active-pr-review.md),
step 3a, for the procedural placement of this check.

## Private Reviewer Brief (never published)

Every result — passive report or active publication — also includes a
private, caller-facing `Reviewer Brief`, composed once the findings,
severity, coverage, and verdict above are finalized. Full semantics,
required fields, and mode composition:
[`reviewer-brief.md`](reviewer-brief.md); rendering and worked examples:
[`../templates/reviewer-brief.md`](../templates/reviewer-brief.md).

It is never submitted as a GitHub review body, inline comment, or
Approve / Request Changes / COMMENT event. The publication payload this
"Batched review construction and submission" section builds is
constructed exclusively from
[`../templates/external-review-summary.md`](../templates/external-review-summary.md)
and [`../templates/inline-finding.md`](../templates/inline-finding.md),
plus the permitted event; `templates/reviewer-brief.md` is never one of
those inputs. The brief is appended to the caller-facing returned result
in its own section, distinct from and never merged into the GitHub-shaped
review body — a structural separation, not a textual filter applied
after the fact.

## Remediation guidance

Apply the shared
[`remediation-guidance.md`](../../../shared/policies/remediation-guidance.md)
after findings and severity are finalized. A GitHub finding may include one
concise, evidence-grounded **Fix** direction (the finding contract's `Fix`
field — see
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md))
aimed at the root cause or canonical owner.
Do not emit `local-code-review`'s full **Implementation prompt** or a
coding task with workflow/commit instructions. Guidance is
advisory and cannot change finding identity, severity, Approve/Request Changes,
or active/passive mutation boundaries.

## Final decision

- **Review reasoning result** is computed independently: either clean, or
  blocking findings (unresolved P0/P1). This mechanical derivation is
  owned by
  [`../../../shared/policies/severity.md`](../../../shared/policies/severity.md)
  and is unchanged by anything in this section — the reasoning result
  always exists and is always reported.
- **Approve** (reasoned) — the reasoning result is clean: no unresolved
  P0, no unresolved blocking P1, and the current PR HEAD equals the
  reviewed HEAD. P2 findings may remain.
- **Request Changes** (reasoned) — an unresolved P0 or unresolved
  blocking P1 exists.

Submitting that reasoned result to GitHub as an `APPROVE` or
`REQUEST_CHANGES` **event** is a separate, authorized action — never an
automatic consequence of the reasoning result. A reasoned "Approve" is
not a GitHub `APPROVE`, and a GitHub `APPROVE` is not merge authority.
An event is submitted only when **both**:

- the authenticated reviewer is eligible to submit that formal event
  (see [`review-authority.md`](review-authority.md), "Review/repository
  access prerequisite"); **and**
- the **Review-action authorization gate** below permits it.

The reasoning result is still reported when GitHub submission is
unavailable, unauthorized, or withheld.

### Review-action authorization gate

The reasoning result (verdict) is produced first, by the mechanical
derivation above, and is always reported. This gate is applied only to
whether that verdict is *submitted* to GitHub as an event.

Immediately before submitting any `APPROVE` / `REQUEST_CHANGES` event
(and after "HEAD revalidation" below), apply
[`review-action-authorization.md`](review-action-authorization.md):

- **Self-review is absolute.** If the reviewer is the PR author — or a
  reviewer under the same controlling authority as the author (see
  [`review-authority.md`](review-authority.md), "Self-review capability"
  and "Authority separation, not just identity separation") — no formal
  `APPROVE` / `REQUEST_CHANGES` event is submitted, regardless of
  publication mode or natural-language request. The full analysis still
  ran; the result **may** be published as an informational review
  `COMMENT` (verdict, reviewed HEAD, findings, and that the formal
  decision was withheld by policy). A `COMMENT` is not approval,
  request-changes, or merge authorization and must not be used as a route
  to any of them. Report the verdict with the withheld reason, for
  example: `REVIEW CLEAN — GitHub review mutation withheld: reviewer is
  the PR author` or `CHANGES REQUIRED — GitHub review mutation withheld:
  reviewer is the PR author` (with `Comments: COMMENTS PUBLISHED`). The
  verdict is not rewritten because the event was withheld.
- Resolve the publication mode: **PASSIVE**, **SEMI**, or **ACTIVE** — see
  [`review-action-authorization.md`](review-action-authorization.md),
  "Publication modes (canonical)." The default is **PASSIVE** — a full
  review and reasoning result, with **no** GitHub mutation. Passive review
  is always `PASSIVE`.
- **An explicit `ACTIVE` request is its own authorization.** `APPROVE` is
  submitted whenever the mode is `ACTIVE`, the invocation is not a
  self-review, reviewer independence (authority separation, not just a
  different username) is established, the desired event is permitted for
  this identity, and the reviewed HEAD is still current — see that
  policy's "Core invariant: an explicit ACTIVE request is its own
  authorization." No further, second authorization signal is required or
  consulted once those hold.
- **`REQUEST_CHANGES`** is submitted under the identical `ACTIVE` +
  independence + permission + HEAD conditions — there is exactly one
  publication-authorization question for both events (see that policy,
  "Migration from the pre-#314 model").
- **`SEMI`** runs the same decision path and computes the same desired
  event, but never submits it — it reports `Mutation: WOULD PUBLISH
  (<event>)` instead.
- Ambiguity in mode or reviewer provenance **fails closed** to `PASSIVE`
  (for an unresolved mode) or to a `WITHHELD` mutation (for an `ACTIVE`
  request whose independence/permission/HEAD facts are unfavorable or
  ambiguous). A caller never needs to say "do not approve" to get this.

Report reasoning and mutation separately:

```text
Reasoning:         REVIEW CLEAN | CHANGES REQUIRED | REVIEW INCOMPLETE | NO NEW DELTA | JIRA CONTEXT UNRESOLVED
Publication mode:  PASSIVE | SEMI | ACTIVE
Comments:          COMMENTS PUBLISHED | COMMENTS NOT PUBLISHED | NOT REQUESTED
Decision:          REVIEW SUBMITTED | REVIEW NOT SUBMITTED | NOT REQUESTED
Mutation:          SUBMITTED (<event>) | WOULD PUBLISH (<event>) | WITHHELD (<reason>) | NOT REQUESTED
```

A `WITHHELD` reason is explicit and names the gate that stopped the
mutation (for example `WITHHELD (publication mode is PASSIVE)` or
`WITHHELD (reviewer independence not established)`). A clean reasoning
result with a withheld approval is reported as a clean result **and** a
non-mutating outcome — never as "approved."

`NO NEW DELTA` applies only when the current reviewer is the same
identity as the immediately preceding completed review and the
previously reviewed SHA equals the current PR HEAD — see
[`reviewer-delta-review.md`](reviewer-delta-review.md), "Same reviewer:
delta boundary and scope." No new review is submitted in this case.

`JIRA CONTEXT UNRESOLVED` applies only when the caller supplied a Jira
reference that could not be resolved to normalized context — see
[`review-context.md`](review-context.md), "Jira context resolution (PR
application)," and the shared
[`review-context.md`](../../../shared/policies/review-context.md), "Jira
context resolution." The Jira-scoped review is not performed: no diff
grading, no inference of the ticket from its key/branch/PR title, and no
Approve/Request Changes for a scope never established. Comments/Decision are
`NOT REQUESTED`. Re-invoking without a Jira reference yields a normal
unscoped review.

`REVIEW SUBMITTED` identifies the accepted event (`APPROVE`,
`REQUEST_CHANGES`, or `COMMENT`). It never follows merely from a successful
analysis; only a confirmed GitHub response establishes publication.

Maximum automated positive action is **Approve**. This Skill never merges
automatically, never deletes branches, never modifies implementation
code, and never takes ownership of repository lifecycle cleanup for an
externally supplied PR.

## HEAD revalidation

Immediately before submitting the final decision, refresh PR metadata and
compare the current HEAD against the reviewed HEAD:

```text
reviewed HEAD
    ↓
refresh PR
    ↓
current HEAD
```

If they differ, the review is stale: do not submit the old decision.
Review the new delta, recompute findings, and submit a decision only for
the current HEAD.

## Submission ordering

```text
review complete PR scope
    ↓
finalize findings (dedupe, severity, inline eligibility)
    ↓
verify current PR HEAD
    ↓
apply the review-action authorization gate
    ↓
construct one review: body + inline comments + event
    ↓
re-confirm current PR HEAD == reviewed HEAD
(if it advanced: withhold the status, do NOT submit the review — the
review is stale; re-review the new delta per "HEAD revalidation")
    ↓
publish any optional machine-readable status/check for the reviewed SHA
    ↓
submit that one review submission  ← final review-owned publication
or report why no formal review can be submitted
```

Verifying HEAD happens immediately before constructing/submitting the
review, not after — see "HEAD revalidation" above. Because the optional
machine-readable status is now published between HEAD revalidation and the
submission, HEAD is re-confirmed once more immediately before that status
publication, and that single re-confirmation gates **both** the status
and the review submission: if HEAD has advanced, the status is withheld
(`STATUS WITHHELD (HEAD advanced)`) **and** the review is not submitted
for the stale reviewed SHA — the review is stale and the "HEAD
revalidation" re-review path applies. The status is never withheld for a
HEAD advance while the review is still submitted for that same stale SHA.
The review body and inline comments are always submitted together as one
review submission per "Batched review construction and submission" above;
there is no separate "publish inline comments" step followed later by a
separate "publish summary" step.

**The final human-facing summary comment is the last publication event of
the run** — `final review comment == last publication event`. The one
review submission carries that summary as its body (see "Final summary"),
so the optional machine-readable status/check is published **before** that
submission, never after it. After the review submission, this run
publishes nothing further and edits nothing it already published — no
comment, no inline comment, no status, no check. This ordering is
identical whether or not `human_review_output` is enabled; the option
changes only the wording of that final summary, not its position.

## Optional machine-readable review status

After this file's gates resolve — verdict, HEAD revalidation, and the
review-action authorization gate — an optional, exact-HEAD,
machine-readable GitHub status/check may be published for the reviewed
SHA. It is published **before the final summary comment** (the one review
submission), so nothing this review owns is published after that summary
— see "Submission ordering". It is a separate, optional signal from the
native `APPROVE` / `REQUEST_CHANGES` event, it never merges, and its
blocking-vs-positive authorization split, enforcement-state detection,
and explicit opt-in required-check setup are owned by
[`review-status-enforcement.md`](review-status-enforcement.md). This file
does not restate that behavior.
