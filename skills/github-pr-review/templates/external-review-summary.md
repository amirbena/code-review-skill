# Template — External Review Summary

The review body submitted as part of one batched GitHub review (see
[`../policies/review-output.md`](../policies/review-output.md), "Batched
review construction and submission"). It is constructed once, from the
finalized set of findings, after analysis completes — never assembled
incrementally as findings are discovered. It follows the shared
human-facing shape in
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md);
findings use the shared shape in
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md).

Write it the way a strong human reviewer leaves a review on a PR: lead
with the verdict, then a scannable list of the findings that matter, and
stop. The **inline comments own the technical detail** (evidence, impact,
reasoning, precise location, fix); the body owns the verdict, a
high-level list, compact validation records, and the decision. The developer
should not have to read the same finding twice. Process and machine state are
subordinate — a short trailing block, never the body.

## Clean review

```markdown
## Review Summary

**Result: ✅ REVIEW CLEAN**

No blocking findings at `<short-sha>`.

### Requirement coverage
**Overall: `complete`**

- **R1 — `implemented`** — `<source citation>`; `<code/test evidence>`

Validation: `executed` — `<exact command>` (declared at `<source>`, exit 0,
<bounded evidence>).

### Decision
**APPROVE**
```

When coverage analysis was active, the conditional section shown above is
part of the clean review. When it was inert, omit that section; the remainder
is the whole clean review — no `What was done well`, no `Findings`,
no `Areas inspected`, no restated "no issues" prose, no review-mode or
mutation lines. Add one sentence only if a strength or follow-up
genuinely helps the author. `Reviewed HEAD` and counts live in the
subordinate metadata block below, which is present even on a clean review
because it always carries the change-risk classification (see "Optional
subordinate metadata").

## Review with findings (detailed findings published inline)

The normal case: each blocking finding already has a detailed inline
comment, so the body lists it in **one concise line** — severity, title,
location — and nothing more.

```markdown
## Review Summary

**Result: ⚠️ CHANGES REQUIRED**

Not safe to merge at `<short-sha>` yet. Two blocking issues need to be
addressed; see the inline comments for detail.

### Findings

- **P1 (Blocking) — Authorization provenance can bypass the trusted boundary**
  `src/review/authz.py:142`
- **P1 (Blocking) — Stale HEAD can still receive a formal review action**
  `src/review/output.py:88`
- **P2 (Non-Blocking) — Validation output hides the failing check name**
  `scripts/validate.py:117`

### Requirement coverage
**Overall: `incomplete`**

- **R1 — `implemented`** — `<source citation>`; `<code/test evidence>`
- **R2 — `not_evidenced`** — `<source citation>`; `<inspected missing path and explanation>`

Validation: `failed` — `<exact command>` (declared at `<source>`, exit
<status>, <bounded evidence/reason>).

### Decision
**REQUEST CHANGES**
```

Omit `Requirement coverage` unless authoritative requirements or acceptance
criteria activate
[`requirement-coverage.md`](../../../shared/policies/requirement-coverage.md).
When active, include every requirement before Validation. Its completeness
signal never changes finding severity or the mechanically derived Decision.

Do **not** repeat `Evidence` / `Impact` / `Fix` / `Details` /
multi-paragraph reasoning in the body for a finding that was published
inline — that content lives in the inline comment.

## Fallback: a finding with no valid inline anchor

Only a finding that could **not** be attached to its canonical fix/action
location inline — cross-cutting, spans files, the fix/action location is
outside the PR diff / not inline-commentable, the fix/action location is
unresolved, or GitHub rejected the anchor — gets its full block in the
body, per
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Canonical full rendering". The body finding carries the explicit
fix/action `path:line` (or the `_(evidence location; fix/action location
unresolved)_` marker) and its remediation, and may cite the evidence
location; any inline pointer left at an in-diff evidence location is a
short, non-authoritative navigation aid, never a second copy of the
finding (see
[`../policies/finding-placement.md`](../policies/finding-placement.md),
"Anchor at the fix/action location"):

```markdown
### Findings

- **P1 (Blocking) — Authorization provenance can bypass the trusted boundary**
  `src/review/authz.py:142`

#### F2 [P2 (Non-Blocking)] Config schema drift spans three unlinked files

- **Location:** `config/*.yaml` (schema vs. loader vs. docs)
- **Evidence:** <concrete evidence — no single line to anchor to>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
- **Details:** <only when a finding-level decision or
  `include_finding_details=true` selects materially useful context>

#### F3 [P1 (Blocking)] `sanitize_path` bypass reaches two call paths

- **Location:** `app/pathsafe.py:5`
- **Affected locations:**
  - `app/reports.py:read_report` — routes user input through `sanitize_path`
  - `app/exports.py:read_export` — same shared helper, same bypass
- **Evidence:** <the shared cause, concise>
- **Impact:** <combined engineering consequence across the affected sites>
- **Fix:** <one correction direction at the shared cause / canonical owner>
```

When `human_review_output` is on, each of these body findings uses the
**human full rendering** instead, per
[`../../../shared/templates/finding-rendering.md`](../../../shared/templates/finding-rendering.md),
"Canonical human full rendering" — the same `id` and `Location` line, the
`Evidence` / `Impact` / `Fix` block re-voiced as senior-engineer prose:

```markdown
### Findings

- **P1 (Blocking) — Authorization provenance can bypass the trusted boundary**
  `src/review/authz.py:142`

#### F2 P2 (Non-Blocking): Config schema drift spans three unlinked files

`config/*.yaml` (schema vs. loader vs. docs)

<concrete evidence, impact, and fix direction carried by prose instead of
labelled fields>
```

This is the same finding, at the same location, with the same severity
and identity — only its wording changes. See
[`../policies/review-output.md`](../policies/review-output.md), "Concise
human-style summary (opt-in)."

A **consolidated root-cause finding** (one shared cause reaching at least
two sites) always renders in the body, with its required, exhaustive
`Affected locations` list of two or more sites directly after `Location`,
per
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Affected locations on a consolidated finding" and
[`../policies/finding-placement.md`](../policies/finding-placement.md),
"Inline comment eligibility" — it is one body finding, never one inline
comment per affected call path.

## Self-review (informational COMMENT)

When the reviewer is the PR author (or shares the author's controlling
authority), the **same** human-facing body — clean or with findings — is
published as an informational GitHub review `COMMENT`. No formal
`APPROVE` / `REQUEST_CHANGES` event is submitted. The only additions are
a note on the `Decision` line and one closing disclosure line:

```markdown
## Review Summary

**Result: ✅ REVIEW CLEAN**

No blocking findings at `<short-sha>`.

Validation: `skipped` — no declared command (no validation executed).

### Decision
**REVIEW CLEAN** — GitHub review mutation withheld: reviewer is the PR author

_Self-review: formal approval was withheld by policy._
```

For a blocking self-review the closing line is
`_Self-review: formal REQUEST_CHANGES was withheld by policy._` and the
`Decision` line reads `**CHANGES REQUIRED** — GitHub review mutation
withheld: reviewer is the PR author`. Keep it to that — no
authorization-state explanation, no mutation diagnostics in the body. The
informational `COMMENT` is never approval, request-changes, or merge
authorization and is never a route to any of them — see
[`../policies/review-authority.md`](../policies/review-authority.md),
"Self-review capability."

## Optional subordinate metadata

The deterministic `standard` / `elevated` / `deep` change-risk depth and
its activating signals per
[`../../../shared/policies/change-risk-signals.md`](../../../shared/policies/change-risk-signals.md),
"Rationale emission," and the fired repository-expansion triggers, rings
reached, and inspected locations per
[`../../../shared/policies/repository-expansion.md`](../../../shared/policies/repository-expansion.md),
"Expansion decisions are reported," are always part of this subordinate
block — so the block is present on every review, including a clean one —
rendered as `standard` with no signals and `none` with no fired trigger
when nothing is flagged, never in the human body, never a finding, and
with no effect on the verdict, the review-action gate, or any
machine-readable status.

Unlike that always-on pair, `large_pr_partitioning` per
[`../../../shared/policies/large-pr-partitioning.md`](../../../shared/policies/large-pr-partitioning.md)
is **conditional on activation**: the field is included in this block
only when that policy's diff-size threshold activated partitioning for
this PR, naming the partition count and any `capped` or cross-partition
de-duplication note. A PR that stayed under the threshold omits the field
entirely — it is never rendered as an empty/`none` placeholder the way
the always-on pair is.

The `coverage` field per
[`../../../shared/policies/review-stopping-criteria.md`](../../../shared/policies/review-stopping-criteria.md)
is always present, like `change_risk_depth` and
`repository_expansion_triggers` — but it is **not** effect-free the way
those two are: when it is `incomplete`, the reasoning result above is
`REVIEW INCOMPLETE` instead of whatever the mechanical derivation from
findings alone would otherwise produce, so that an incomplete review is
never mistaken for `REVIEW CLEAN` / Approve. This block's own `decision`
field still records whichever GitHub action was actually taken —
typically `comment`, since the review-action authorization gate still
applies — never `approve`; `REVIEW INCOMPLETE` is not itself a value of
that field. Findings already gathered are still reported in full; only
the top-level outcome is overridden.

Append the remaining machine/process state only if a downstream consumer
(orchestration, automated re-review, audit) actually needs it, after the
human-facing review and clearly subordinate, per
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md),
"Machine metadata is subordinate":

```markdown
<details>
<summary>Review metadata</summary>

- reviewed_head: `<sha>`
- review_mode: `full` | `delta (previous reviewed SHA <sha>, current HEAD <sha>)`
- change_risk_depth: `standard` | `elevated` | `deep`
- change_risk_signals: `none` | `<signal (tier) — evidence>` per resolved occurrence
- repository_expansion_triggers: `none` | `<trigger (ring N) — locations>` per fired trigger
- large_pr_partitioning: `<n> partitions, <capped/dedup note>` — omitted entirely when inactive
- coverage: `complete` | `incomplete — <reason(s)>`
- P0: <n>
- P1: <n>
- P2: <n>
- decision: `approve` | `request_changes` | `comment`
- action_mode: `recommendation-only` | `block-only` | `explicitly-authorized-auto-action`
- mutation: `submitted (<event>)` | `withheld (<reason>)` | `not_requested`

</details>
```

## Concise human-style body (opt-in)

When the invocation selects `human_review_output` (natural language only —
"make the review shorter and more human", "review it like a senior
engineer", "use concise review comments"; per
[`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
"`human_review_output` phrasings"), this review body is written in the
concise senior-engineer voice from
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md),
"Concise human-style summary (opt-in)" — whose voice is owned by
[`../../../shared/templates/finding-rendering.md`](../../../shared/templates/finding-rendering.md),
"Senior voice contract" — instead of the structured shape above:

```markdown
## Review Summary

Not safe to merge at `<short-sha>` yet. Two blockers: authorization
provenance can be forged through the trusted boundary
(`P1 (Blocking)`, `src/review/authz.py:142`), and a stale HEAD can still
receive a formal review action (`P1 (Blocking)`, `src/review/output.py:88`).
The validation output hiding which check failed
(`P2 (Non-Blocking)`, `scripts/validate.py:117`) is worth fixing but
doesn't block.

Was routing the settled-tradeoff case straight to the caller here
deliberate?

The retry handling is clean, and the new tests exercise the failure path
that was previously untested.

**Requirement coverage:** `incomplete` — R1 `implemented` (`<source>`;
`<evidence>`); R2 `not_evidenced` (`<source>`; `<evidence/explanation>`).

### Decision
**REQUEST CHANGES**
```

- Every blocking finding still appears — once — as a summary-pointer line
  keeping its `P0` / `P1` / `P2` label and `` `path:line` ``; the inline
  comment still owns each finding's full detail — its `Evidence` /
  `Impact` / `Fix` in the structured rendering, or the equivalent
  senior-engineer prose when `human_inline_findings` is on (see
  "Human-rendered inline findings (opt-in)" below). A finding with **no**
  inline comment (no valid anchor) instead carries its full block directly
  in this concise body — the human full rendering described above under
  "Fallback: a finding with no valid inline anchor," since
  `human_review_output` is what selects this concise body in the first
  place.
- No review mode, SHAs beyond the short opening reference, counts, action
  mode, worker/aggregation wording, or the `Review metadata` block.
- The `Result` / `Decision` value is the same single mechanically derived
  decision. Findings, severities, finding identity, deduplication,
  publication anchors, the GitHub review event, and any machine-readable
  status are **identical** to the mode-off review. Inline comments carry
  the **same findings** either way: byte-identical to the mode-off review
  when `human_inline_findings` is off, and — when it is on (its derived
  default under `human_review_output`) — the same severity, identity,
  anchor, evidence content, remediation, and decision re-voiced per
  [`inline-finding.md`](inline-finding.md), "Human-rendered inline
  finding (opt-in)". Only presentation wording changes — this body
  (including any body-rendered fallback finding, per "Fallback: a finding
  with no valid inline anchor"), and (when `human_inline_findings` is on)
  the inline comments.
- Active requirement coverage remains visible in this concise body with its
  overall signal and every requirement/status; only its wording is condensed.
  Omit it entirely when coverage analysis was inert.
- A self-review uses this same concise body as its informational
  `COMMENT`, keeping the closing disclosure line from "Self-review
  (informational COMMENT)".
- This body is still submitted as part of the **one** batched review
  submission, which stays the final publication event for the run (see
  [`../policies/review-output.md`](../policies/review-output.md),
  "Submission ordering").

## Human-rendered inline findings (opt-in)

`human_inline_findings` (see
[`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
"`human_inline_findings` derived default and phrasings") extends the
senior-engineer voice to the **inline comments**, so a
`human_review_output` review reads coherently end to end. Its default is
`human_review_output`'s resolved value; an explicit
`human_inline_findings=false` keeps the structured
`[<severity>] / Evidence / Impact / Fix` inline block while this body
stays concise, and an explicit `human_inline_findings=true` re-voices the
inline comments even when this body is structured.

The inline re-voicing is presentation only and is governed by
[`inline-finding.md`](inline-finding.md), "Human-rendered inline finding
(opt-in)" and
[`../../../shared/templates/finding-rendering.md`](../../../shared/templates/finding-rendering.md),
"Canonical human inline rendering" and "Senior voice contract". It
changes no finding's severity,
identity, deduplication, evidence, remediation, decision, or
**publication anchor** — every anchor-selection and body-fallback rule in
[`../policies/finding-placement.md`](../policies/finding-placement.md)
applies unchanged. The body still carries exactly one summary-pointer
line per inline finding.

`human_inline_findings` is scoped to this inline surface only. It has no
effect on a finding rendered in full in the body — that finding's voice
is governed directly by `human_review_output` via "Fallback: a finding
with no valid inline anchor" above, independent of whatever
`human_inline_findings` resolves to.

## Rules

These are the body's **rendering** rules. The review semantics they serve
are owned by the linked policies and are not restated here.

- **Stable heading.** The body always starts `## Review Summary` — for
  the clean, findings, fallback, and self-review-`COMMENT` cases, and
  identically under `human_review_output`. Canonical:
  [`../policies/review-output.md`](../policies/review-output.md), "Stable
  review-body heading".
- **Severity legend.** Every finding heading shows the severity code with
  its compact canonical parenthetical (`P0 (Critical)` / `P1 (Blocking)` /
  `P2 (Non-Blocking)`), rendered once, never as a repeated explanatory
  paragraph. Canonical:
  [`../policies/review-output.md`](../policies/review-output.md), "Reader-
  visible severity legend".
- **Density and no disclosure.** Both rendering modes follow the
  density/de-duplication guidance and never disclose the underlying
  agent/model/tool. Canonical:
  [`../policies/review-output.md`](../policies/review-output.md),
  "Density and de-duplication" and "No agent/model/tool disclosure".
- **Verdict first, no manufactured sections.** `Result` states the
  outcome in plain language (`REVIEW CLEAN` / `CHANGES REQUIRED`) and the
  `Decision` line restates it as the GitHub action actually submitted (or
  the withheld / `COMMENT` outcome); the two never disagree and the
  reader never infers the outcome from raw counts. Omit `What was done
  well`, `Areas inspected`, `Comments`, `Mutation`, `Authorization`, and
  `Review mode` from the body; a clean review has no `Findings` section
  and no "no issues found" prose. Fold a short "what changed / against
  what intent" note into the opening only when the diff's purpose is not
  self-evident. Canonical:
  [`../policies/review-output.md`](../policies/review-output.md), "Final
  summary".
- **Incomplete coverage overrides the verdict.** When `coverage` per
  [`../../../shared/policies/review-stopping-criteria.md`](../../../shared/policies/review-stopping-criteria.md)
  is `incomplete`, `Result` and `Decision` render `REVIEW INCOMPLETE`
  instead of `REVIEW CLEAN` / `CHANGES REQUIRED`, with a one-sentence
  reason tied to the metadata block's `coverage` value — never `Approve`,
  never a clean-reading `Result`. Findings actually gathered before
  coverage was interrupted still render in full.
- **Findings own their detail inline; the body owns the list.** An
  inline-published finding gets exactly one summary-pointer line
  (severity — title, then `` `path:line` ``) and nothing else — no
  `Evidence` / `Impact` / `Fix` / `Details` / reasoning repeated in the
  body. Only a finding with **no valid inline anchor** carries its full
  `### <id> [<severity>] <title>` + `Location` / `Evidence` / `Impact` /
  `Fix` block in the body (see "Fallback" above). Every finding appears
  exactly once; never drop a real finding to keep the list short.
  `include_finding_details` defaults to `false`; a `Details` field
  renders only for a finding that satisfies
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "When a longer explanation is justified". Canonical:
  [`../policies/finding-placement.md`](../policies/finding-placement.md),
  "No duplicate findings";
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "Canonical summary-pointer rendering";
  [`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md).
- **Validation** renders one compact record per selected command (or an
  explicit no-command record) — `executed` / `skipped` / `failed` /
  `unavailable` with command, source, scope, and evidence — per the
  shared
  [`runtime-validation.md`](../../../shared/policies/runtime-validation.md)
  contract; non-execution is never summarized as passing.
- **Review mode** is not part of the human body — a `delta` re-review may
  add one plain sentence; identity-matching mechanics stay in the
  subordinate metadata per
  [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md),
  "Reporting the mode".
- **Remediation** — the `Fix` field carries a concise recommended
  direction, never a local-style full **Implementation prompt**, and
  never affects severity or Decision, per
  [`../../../shared/policies/remediation-guidance.md`](../../../shared/policies/remediation-guidance.md).
- **Review-action authority.** The reasoned decision and the GitHub
  mutation are reported separately per
  [`../policies/review-action-authorization.md`](../policies/review-action-authorization.md)
  and [`../policies/review-output.md`](../policies/review-output.md),
  "Review-action authorization gate"; a clean reasoning result whose
  approval was withheld is never rendered as "approved".
- **Unresolved supplied Jira reference** — the body is not produced as a
  graded review: return `JIRA CONTEXT UNRESOLVED`, naming the reference
  and the integration(s) attempted, with `Comments` / `Decision` =
  `NOT REQUESTED`, per
  [`../policies/review-context.md`](../policies/review-context.md), "Jira
  context resolution (PR application)".
- Keep the visible review concise — it is read by a person.
