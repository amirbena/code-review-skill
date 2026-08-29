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
with the verdict, then the findings that matter, and stop. Process and
machine state are subordinate — a short trailing block, never the body.

## Clean review

```markdown
## Code Review

**Result: ✅ REVIEW CLEAN**

Reviewed against <brief intent/context>. Safe to merge at `<short-sha>` —
no blocking findings.

<optional: one concise sentence on a notable strength or a follow-up
worth knowing about — only when it genuinely helps the author; never a
manufactured praise section>

### Validation
Validation passed: <one sentence, e.g. "full test suite, metadata
validation, packaging, and diff checks">.

### Decision
**APPROVE**
```

The first fenced block above is the whole clean review — no `What was
done well`, no `Findings`, no restated "no issues" prose. `Reviewed HEAD`
and any counts live in the subordinate metadata block below.

## Review with findings

```markdown
## Code Review

**Result: ⚠️ CHANGES REQUIRED**

Reviewed against <brief intent/context>. Not safe to merge at
`<short-sha>`: <the single most important reason, in one line>.

### Findings

- **P1 — Incomplete pagination can produce a false clean review**
  `runbooks/active-pr-review.md:84`
  _(full finding published as an inline comment on this line)_

#### F2 [P2] Validation output hides a useful failure reason

- **Location:** `scripts/validate.py:117`
- **Evidence:** <concrete evidence — this finding had no valid inline
  anchor, so its full form lives here instead>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
- **Details:** <only when a finding-level decision or
  `include_finding_details=true` selects materially useful context>

### Validation
Validation passed: <one sentence>.

### Decision
**REQUEST CHANGES**

1 P1 finding must be addressed before this PR should be approved.
```

## Self-review (informational COMMENT)

When the reviewer is the PR author (or shares the author's controlling
authority), the same human-facing body is published as an informational
GitHub review `COMMENT` — no formal `APPROVE` / `REQUEST_CHANGES` event.
It is identical to the forms above except for one short closing line:

```markdown
## Code Review

**Result: ✅ REVIEW CLEAN**

Reviewed against <brief intent/context>. No blocking findings at
`<short-sha>`.

### Validation
Validation passed: <one sentence>.

### Decision
**REVIEW CLEAN** — GitHub review mutation withheld: reviewer is the PR author

_Self-review: formal approval was withheld by policy._
```

For a blocking self-review the closing line is
`_Self-review: formal REQUEST_CHANGES was withheld by policy._` and the
Decision line reads `**CHANGES REQUIRED** — GitHub review mutation
withheld: reviewer is the PR author`. The informational `COMMENT` is
never approval, request-changes, or merge authorization and is never a
route to any of them — see
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
- **No manufactured sections.** Omit `What was done well` unless a
  strength is real, specific, and useful to the author — then one
  sentence. On a clean review there is no `Findings` section and no
  restated "no issues found" prose; the opening and `Decision` already
  say it.
- **Findings** is the aggregate view: every finding appears exactly once,
  in exactly one authoritative form — the full form (per
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "Canonical full rendering": `### <id> [<severity>] <title>` then the
  compact `Location` / `Evidence` / `Impact` / `Fix` block) when this
  body is its only representation, or the summary-pointer form when the
  full form was already published as an inline comment (see
  [`../policies/finding-placement.md`](../policies/finding-placement.md),
  "No duplicate findings"). Do not repeat a full inline finding here.
  `include_finding_details` defaults to `false`; a populated `Details`
  field renders only when the invocation enables it or a higher-priority
  finding-level decision selects materially useful context, per
  [`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
  and only for a finding that satisfies
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "When a longer explanation is justified." Findings are for developer
  action — no generic "consider refactoring" filler.
- **Validation** is one sentence summarising what was actually run (or
  explicitly noting what could not be). Never a command-by-command dump.
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
