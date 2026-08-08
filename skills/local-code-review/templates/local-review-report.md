# Template — Local Review Report

Returned by every invocation of `local-code-review`. This is **not** a
GitHub review event and is never published anywhere by the Skill itself
— it is handed back to the caller, once, as a single organized review
(never streamed finding-by-finding as they are discovered — see
[`../SKILL.md`](../SKILL.md), "Statelessness and Orchestration
Boundary"). It follows the shared human-facing shape in
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md);
findings use the shared shape in
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md).
This Skill has no GitHub inline-comment surface, so every finding always
uses the **full rendering** — there is no other delivery location a
finding could already be published to.

```markdown
## Code Review

**Result: ⚠️ Changes Requested**

Reviewed the current implementation state (committed delta, local-only
commits, and relevant uncommitted changes) against `<base>`.

### What changed
<concise, concrete implementation summary>

### What was done well
- **<theme>:** <concrete, evidence-backed strength>

### Findings

#### F1 [P1] Retry can duplicate processing

**File:** `src/...:<line>`

**Evidence**
<concrete evidence>

**Impact**
<concrete engineering consequence>

**Recommended direction**
<concrete correction direction>

### Validation
- <validation actually observed, or explicitly noted as not executed>

### Decision
**CHANGES REQUIRED**

1 P1 finding must be addressed before this implementation should
proceed.

<details>
<summary>Review metadata</summary>

- base branch: <name>
- base SHA: <sha>
- local HEAD: <sha>
- remote HEAD: <sha | none>
- committed delta: <base..HEAD summary>
- uncommitted state: staged=<yes/no>, unstaged=<yes/no>, untracked=<relevant files or none>
- synchronization status: <in sync | local ahead | local behind | diverged | no tracking branch>
- P0: <n>, P1: <n>, P2: <n>

</details>
```

or, when clean:

```markdown
**Result: ✅ Review Clean**

...

### Findings
No P0, P1, or P2 findings.

### Decision
**REVIEW CLEAN**

No P0, P1, or P2 findings were identified in the reviewed implementation
state.
```

## Rules

- The human-facing body (Result → What changed → What was done well →
  Findings → Validation → Decision) is primary and always appears first
  — see
  [`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md).
- Decision is exactly `REVIEW CLEAN` or `CHANGES REQUIRED`, stated
  plainly with a one-sentence rationale — `REVIEW CLEAN` only when no
  blocking findings (P0/P1) remain; P2s alone never block it (see
  [`../../../shared/policies/severity.md`](../../../shared/policies/severity.md)).
- Every finding uses the full rendering in
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md):
  a stable ID (`F1`, `F2`, ...), severity, a concrete title, file/line
  where available, evidence, impact, and a recommended direction.
- **Validation** reports only what was actually inspected or executed.
  If this Skill did not run tests/commands, say so rather than implying
  they passed.
- **Review State** (base/HEAD SHAs, synchronization status, raw
  counts) is machine/orchestration-oriented detail — it is subordinate,
  appearing only inside the trailing `<details>` block, never ahead of
  the human-facing review.
- **No loop/orchestration metadata.** This report does not track review
  iteration count, a configured maximum, or whether another iteration is
  allowed — that information belongs to the orchestrator, never to this
  Skill (see [`../SKILL.md`](../SKILL.md)).
- Return only what the implementing Agent needs to act.
