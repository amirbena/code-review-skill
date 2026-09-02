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

Validation: `executed` — `<exact command>` (declared at `<source>`, exit 0,
<bounded evidence>).

### Decision
**APPROVE**
```

That is the whole clean review — no `What was done well`, no `Findings`,
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

Validation: `failed` — `<exact command>` (declared at `<source>`, exit
<status>, <bounded evidence/reason>).

### Decision
**REQUEST CHANGES**
```

Do **not** repeat `Evidence` / `Impact` / `Fix` / `Details` /
multi-paragraph reasoning in the body for a finding that was published
inline — that content lives in the inline comment.

## Fallback: a finding with no valid inline anchor

Only a finding that could **not** be attached to a line (cross-cutting,
spans files, or GitHub rejected the anchor) gets its full block in the
body, per
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Canonical full rendering":

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
```

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

## Rules

- **Verdict first.** The `Result` line states the outcome in plain
  language (`REVIEW CLEAN` / `CHANGES REQUIRED`); the `Decision` line
  restates it as the GitHub action. A reader never infers the outcome
  from raw counts, and the two never disagree.
- **The opening** says whether the reviewed HEAD is safe to merge and
  names the single most important concern, in one or two sentences. Fold
  a short "what changed / against what intent" note into it (or a brief
  `### What changed` section) only when the diff's purpose is not
  self-evident; skip "reviewed N files" boilerplate.
- **The Decision line** is unambiguous and matches the GitHub review
  action actually submitted (or the withheld/`COMMENT` outcome when no
  formal event was submitted).
- **No manufactured sections.** Omit `What was done well`, `Areas
  inspected`, `Comments`, `Mutation`, `Authorization`, and `Review mode`
  from the body. Mention a strength only if it is real, specific, and
  useful — one sentence. A clean review has no `Findings` section and no
  restated "no issues found" prose.
- **Findings own their detail inline; the body owns the list.** When a
  finding is published as a detailed inline comment, the body carries
  **one line** for it — the summary-pointer form (severity — title, then
  its `` `path:line` ``) per
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "Canonical summary-pointer rendering" and
  [`../policies/finding-placement.md`](../policies/finding-placement.md),
  "No duplicate findings" — and nothing else. Do **not** repeat
  `Evidence` / `Impact` / `Fix` / `Details` / reasoning in the body for
  an inline finding. Only a finding with **no valid inline anchor** gets
  its full `### <id> [<severity>] <title>` + `Location` / `Evidence` /
  `Impact` / `Fix` block in the body (see "Fallback" above). Every
  finding still appears exactly once. `include_finding_details` defaults
  to `false`; a populated `Details` field renders only when the
  invocation enables it or a higher-priority finding-level decision
  selects materially useful context, per
  [`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
  and only for a finding that satisfies
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "When a longer explanation is justified." No generic "consider
  refactoring" filler; no praise padding. Never drop a real finding to
  keep the list short.
- **Validation** follows the shared
  [`runtime-validation.md`](../../../shared/policies/runtime-validation.md)
  contract. Render one compact record per selected command (or an explicit
  no-command record) with exactly `executed`, `skipped`, `failed`, or
  `unavailable`, the exact command/source, scope or justification, and the
  observed evidence/reason. Never summarize non-execution as passing.
- **Review mode** is not part of the human body. A `full` review says
  nothing about mode; a `delta` re-review may add one plain sentence
  ("Reviewed the delta since `abc1234`.") when it helps the reader.
  Reviewer-identity-matching mechanics stay in the subordinate metadata,
  per
  [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md),
  "Reporting the mode."
- **Remediation** follows
  [`../../../shared/policies/remediation-guidance.md`](../../../shared/policies/remediation-guidance.md):
  the `Fix` field carries a concise recommended direction, never a
  local-style full **Implementation prompt**. It never affects severity
  or Decision.
- **Review-action authority.** The reasoned decision and the GitHub
  mutation are reported separately, per
  [`../policies/review-action-authorization.md`](../policies/review-action-authorization.md)
  and [`../policies/review-output.md`](../policies/review-output.md),
  "Review-action authorization gate." The default mode is
  recommendation-only (no mutation); `APPROVE` is submitted only in
  explicitly-authorized auto-action mode with trusted authorization and
  reviewer independence. A self-review submits no formal event and
  publishes the body as an informational `COMMENT` with the disclosure
  line above. When a mutation was withheld, say so plainly with the
  reason — a clean reasoning result with a withheld approval is never
  rendered as "approved."
- **Unresolved supplied Jira reference.** If the caller supplied a Jira
  reference that could not be resolved (see
  [`../policies/review-context.md`](../policies/review-context.md), "Jira
  context resolution (PR application)" and
  [`../policies/review-output.md`](../policies/review-output.md), "Final
  decision"), this body is not produced as a graded review: return the
  `JIRA CONTEXT UNRESOLVED` reasoning result, naming the reference and the
  integration(s) attempted, with `Comments`/`Decision` = `NOT REQUESTED`.
  The Jira-scoped review is not performed and the ticket is not inferred
  from its key/branch/PR title. Re-invoke without a Jira reference for a
  normal unscoped review.
- Keep the visible review concise — it is read by a person.
