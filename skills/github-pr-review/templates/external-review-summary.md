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
## Code Review

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
subordinate metadata block below.

## Review with findings (detailed findings published inline)

The normal case: each blocking finding already has a detailed inline
comment, so the body lists it in **one concise line** — severity, title,
location — and nothing more.

```markdown
## Code Review

**Result: ⚠️ CHANGES REQUIRED**

Not safe to merge at `<short-sha>` yet. Two blocking issues need to be
addressed; see the inline comments for detail.

### Findings

- **P1 — Authorization provenance can bypass the trusted boundary**
  `src/review/authz.py:142`
- **P1 — Stale HEAD can still receive a formal review action**
  `src/review/output.py:88`
- **P2 — Validation output hides the failing check name**
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

- **P1 — Authorization provenance can bypass the trusted boundary**
  `src/review/authz.py:142`

#### F2 [P2] Config schema drift spans three unlinked files

- **Location:** `config/*.yaml` (schema vs. loader vs. docs)
- **Evidence:** <concrete evidence — no single line to anchor to>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
- **Details:** <only when a finding-level decision or
  `include_finding_details=true` selects materially useful context>

#### F3 [P1] `sanitize_path` bypass reaches two call paths

- **Location:** `app/pathsafe.py:5`
- **Affected locations:**
  - `app/reports.py:read_report` — routes user input through `sanitize_path`
  - `app/exports.py:read_export` — same shared helper, same bypass
- **Evidence:** <the shared cause, concise>
- **Impact:** <combined engineering consequence across the affected sites>
- **Fix:** <one correction direction at the shared cause / canonical owner>
```

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
## Code Review

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

Append machine/process state only if a downstream consumer
(orchestration, automated re-review, audit) actually needs it, after the
human-facing review and clearly subordinate, per
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md),
"Machine metadata is subordinate":

```markdown
<details>
<summary>Review metadata</summary>

- reviewed_head: `<sha>`
- review_mode: `full` | `delta (previous reviewed SHA <sha>, current HEAD <sha>)`
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
"Concise human-style summary (opt-in)" instead of the structured shape
above:

```markdown
## Code Review

Not safe to merge at `<short-sha>` yet — the P1 on the auth path is the
blocker.

**What's good:** the retry handling is clean and the new tests actually
exercise the failure path.

**What's concerning:** `P1` — authorization provenance can be forged
through the trusted boundary (`src/review/authz.py:142`); `P1` — a stale
HEAD can still receive a formal review action (`src/review/output.py:88`).
`P2` — the validation output hides which check failed.

Was routing the settled-tradeoff case straight to the caller here
deliberate?

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
  "Human-rendered inline findings (opt-in)" below).
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
  finding (opt-in)". Only presentation wording changes — this body, and
  (when `human_inline_findings` is on) the inline comments.
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
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Canonical human inline rendering". It changes no finding's severity,
identity, deduplication, evidence, remediation, decision, or
**publication anchor** — every anchor-selection and body-fallback rule in
[`../policies/finding-placement.md`](../policies/finding-placement.md)
applies unchanged. The body still carries exactly one summary-pointer
line per inline finding.

## Rules

These are the body's **rendering** rules. The review semantics they serve
are owned by the linked policies and are not restated here.

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
