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

Reviewed the current implementation state (committed delta, staged,
unstaged, and untracked changes — see the Review Scope below for what
was included) against `<base>`.

### What changed
<concise, concrete implementation summary>

### What was done well
- **<theme>:** <concrete, evidence-backed strength>

### Context
<only present when review context was supplied AND it materially shaped
this review — see
[`../policies/review-context.md`](../policies/review-context.md),
"Output"; omitted entirely otherwise, including whenever no review
context was supplied>
- Reviewed against supplied context`<: source-name, if given>`.
- Focus areas it identified: `<concrete list, e.g. "validation ordering
  in the recurring-payment path">`.
- Non-goals it stated: `<n>` (kept out of scope) — omit this line if none
  apply.
- Mismatches noted: `<n>` (context appears stale/conflicting; flagged
  rather than assumed — see the policy's "Context mismatch vs.
  implementation defect") — omit this line if none apply.

### PR Context
<only present when a PR reference was supplied AND it materially shaped
this review — see
[`../policies/pr-context.md`](../policies/pr-context.md), "Output";
omitted entirely otherwise, including whenever no PR reference was
supplied>
- Reconciled against PR `<url-or-#number>`.
- Existing reviewer findings: `<n>` still valid (reflected in Findings
  below), `<n>` resolved, `<n>` required re-evaluation (reflected below).
- Architectural decisions: `<n>` violated/regressed (reported as a
  finding below) | `<n>` intentionally superseded with new evidence
  (briefly noted here) — omit this line if none apply.

### Findings

#### F1 [P1] Retry can duplicate processing

**File:** `src/...:<line>` _(staged)_

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

### Review Metadata

- Base branch: `<name>`
- Base SHA: `<sha>`
- Local HEAD: `<sha>`
- Remote HEAD: `<sha | none>`
- Synchronization status: <in sync | local ahead | local behind | diverged | no tracking branch>
- P0: <n>, P1: <n>, P2: <n>

**Review scope contract** (per
[`../policies/repository-state.md`](../policies/repository-state.md)) —
states plainly what was inspected; a category marked "excluded" is a
deliberate, stated exclusion, never a silent omission:

- Committed delta relative to base: <included, `<base>..HEAD` summary | excluded, reason>
- Staged: <included, files/delta summary | excluded, reason>
- Unstaged: <included, files/delta summary | excluded, reason>
- Untracked: <included, files | excluded, reason>
- Staged-delta fingerprint (SHA-256 of `git diff --cached --raw -M -z`): `<hex digest>`
- Review kind: <initial review | re-review>
- Previously reviewed state changed: <staged: unchanged/changed — fingerprint compared; unstaged: unchanged/changed — re-detected; untracked: unchanged/changed — re-detected | not applicable, initial review>
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

or, clean while still preserving a non-blocking P2 (a P2 finding never
by itself changes the decision — see
[`../../../shared/policies/severity.md`](../../../shared/policies/severity.md),
"Decision derivation (mechanical)"):

```markdown
**Result: ✅ Review Clean**

...

### Findings

#### F1 [P2] Repository style convention violation

**File:** `src/...:<line>` _(staged)_

**Evidence**
<concrete evidence, e.g. the target repository's `AGENTS.md` states the
convention and the staged delta violates it>

**Impact**
<concrete engineering consequence — maintainability/consistency, not a
correctness or safety defect>

**Recommended direction**
<concrete correction direction>

### Decision
**REVIEW CLEAN**

No P0 or P1 (blocking) findings were identified; the P2 finding above is
a non-blocking recommendation and does not change this decision, however
strongly it is recommended before commit.
```

## Rules

- The human-facing body (Result → What changed → What was done well →
  [Context, when applicable] → [PR Context, when applicable] → Findings
  → Validation → Decision) is primary and always appears first — see
  [`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md).
- **Context** is entirely optional and appears only when the caller
  supplied review context (per
  [`../policies/review-context.md`](../policies/review-context.md)) and
  it materially shaped the review — see that policy, "Output." It is
  omitted completely, with no placeholder or empty section, whenever no
  review context was supplied — this is the no-context
  backward-compatible case and the default. A context-derived finding's
  provenance belongs in that finding's own **Evidence** field, per that
  policy's "Tracing findings back to context," not as a duplicate entry
  here — this section is a concise pointer, never a second listing of
  the findings themselves. Supplied context guides investigation; it
  never substitutes for implementation evidence and never adds a second
  decision path — see
  [`../policies/review-context.md`](../policies/review-context.md),
  "Evidence hierarchy," and
  [`../../../shared/policies/severity.md`](../../../shared/policies/severity.md),
  "Decision derivation (mechanical)."
- **PR Context** is entirely optional and appears only when the caller
  supplied a PR reference and it materially shaped the review (a
  reconciled finding, a violated or superseded decision) — see
  [`../policies/pr-context.md`](../policies/pr-context.md), "Output." It
  is omitted completely, with no placeholder or empty section, whenever
  no PR reference was supplied — this is the no-PR backward-compatible
  case and the default. A reconciled finding's provenance (e.g. "still
  valid per PR review, evidence reused") belongs in that finding's own
  **Evidence** field, not as a duplicate entry here — this section is a
  concise pointer, never a second listing of the findings themselves.
- Decision is exactly `REVIEW CLEAN` or `CHANGES REQUIRED`, derived
  mechanically per
  [`../../../shared/policies/severity.md`](../../../shared/policies/severity.md),
  "Decision derivation (mechanical)": `REVIEW CLEAN` iff no P0/P1
  finding is present among the finalized findings; `CHANGES REQUIRED`
  iff at least one is. Any number of P2 findings, however strongly they
  are recommended, never by themselves produce `CHANGES REQUIRED` —
  including a P2 that originates from a violated repository convention
  (see
  [`../../../shared/policies/severity.md`](../../../shared/policies/severity.md),
  "Repository conventions and severity," and
  [`../../../shared/policies/repository-instructions.md`](../../../shared/policies/repository-instructions.md),
  "Conventions determine findings, not severity"). The one-sentence
  rationale explains this mechanical result; it is never an independent
  subjective call that could contradict it.
- Every finding uses the full rendering in
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md):
  a stable ID (`F1`, `F2`, ...), severity, a concrete title, file/line
  where available, evidence, impact, and a recommended direction. The
  file line also carries this Skill's optional trailing annotation
  naming the finding's source category — `(committed)`, `(staged)`,
  `(unstaged)`, or `(untracked)` — per
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "Optional Skill-specific trailing annotation," and
  [`../policies/repository-state.md`](../policies/repository-state.md),
  "Attribution in findings," so the report says precisely where each
  finding came from. This annotation is specific to this Skill's local
  Git working-tree model; it is not part of the shared template's
  required fields.
- **Validation** reports only what was actually inspected or executed.
  If this Skill did not run tests/commands, say so rather than implying
  they passed.
- **Review State** (base/HEAD SHAs, synchronization status, raw
  counts) is machine/orchestration-oriented detail — it is subordinate,
  appearing only inside the trailing "Review Metadata" section as plain
  Markdown, never ahead of the human-facing review and never wrapped in
  GitHub-oriented HTML (e.g. `<details>`/`<summary>`), which offers no
  benefit for a report read directly in a terminal or chat surface.
- **Review scope contract** is required in every report, initial or
  re-review: state plainly whether committed/staged/unstaged/untracked
  state was included, the staged-delta fingerprint, whether this is an
  initial review or a re-review, and — for a re-review — whether the
  staged delta changed (by fingerprint comparison) and whether unstaged
  or untracked state changed (by independent re-detection, never
  inferred from the staged fingerprint). A category intentionally
  excluded from scope is stated as excluded with a reason, never
  silently dropped.
- **No loop/orchestration metadata.** This report does not track review
  iteration count, a configured maximum, or whether another iteration is
  allowed — that information belongs to the orchestrator, never to this
  Skill (see [`../SKILL.md`](../SKILL.md)).
- Return only what the implementing Agent needs to act.
