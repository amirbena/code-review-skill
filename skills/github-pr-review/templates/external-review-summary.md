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

```markdown
## Code Review

**Result: ✅ Review Clean**

Reviewed <n> changed files at commit `<sha>`.

Review mode: Full review
Reason: no previous completed review by this reviewer

### What changed
<concise summary of what the Pull Request implements and its intent>

### What was done well
- **<theme>:** <concrete, evidence-backed strength>

<omit this section, or keep it to one line, if nothing specific stands out>

### Findings
No P0, P1, or P2 findings.

### Validation
- <validation actually observed, or explicitly noted as not executed>

### Decision
**APPROVE**

No P0, P1, or P2 findings were identified in the reviewed HEAD.
```

or, when there are findings:

```markdown
Review mode: Delta re-review
Previous reviewed SHA: `abc1234`
Current HEAD: `def5678`

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

### Decision
**REQUEST CHANGES**

1 P1 finding must be addressed before this PR should be approved.
```

## Optional subordinate metadata

If structured metadata is genuinely useful for orchestration/automation,
append it after the human-facing review, clearly subordinate, per
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md),
"Machine metadata is subordinate":

```markdown
<details>
<summary>Review metadata</summary>

- reviewed_head: `<sha>`
- P0: <n>
- P1: <n>
- P2: <n>
- decision: `approve` | `request_changes`

</details>
```

## Rules

- **Review mode** states plainly whether this invocation used a normal
  full review or a delta re-review, and why, per
  [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md).
  For a delta re-review,
  include the previously reviewed SHA and current HEAD. Keep this line
  concise; do not expose additional internal reviewer-identity-matching
  mechanics as primary output.
- **Result** and **Decision** state the outcome in plain language; a
  reader never infers the outcome from raw counts.
- "What was done well" only mentions strengths actually supported by the
  PR — never invented; omit rather than pad.
- **Findings** is the aggregate view: every finding appears exactly once,
  in exactly one authoritative form — the full form (per
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md))
  when this body is its only representation, or the summary-pointer form
  when its full form was already published as an inline comment (see
  [`../policies/finding-placement.md`](../policies/finding-placement.md), "No
  duplicate findings"). Do not repeat a full inline finding here. Full
  findings use the compact, field-oriented `Location` / `Evidence` /
  `Impact` / `Fix` contract in
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md)
  — concise by default, with a `Details` field only for a finding in one
  of that file's "When a longer explanation is justified" categories.
- **Validation** reports only what was actually observed; state
  explicitly when something could not be executed.
- **Remediation** follows
  [`../../../shared/policies/remediation-guidance.md`](../../../shared/policies/remediation-guidance.md):
  the `Fix` field carries a concise recommended direction when useful, never a
  local-style full **Implementation prompt**. It does not affect severity or
  Decision.
- The Decision line is unambiguous and matches the actual GitHub review
  action submitted.
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
- Keep the visible section concise — this is read by a person, not
  parsed by a machine.
