# Runbook — Local Review

The single runbook for `local-code-review`. Applies shared policies:
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md),
[`evidence.md`](../../../shared/policies/evidence.md),
[`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
[`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
[`git-safety.md`](../../../shared/policies/git-safety.md), and the shared
human-facing output shape in
[`review-summary.md`](../../../shared/templates/review-summary.md), plus
this Skill's own
[`../policies/invocation-approval.md`](../policies/invocation-approval.md)
(the invocation-approval precondition assumed below) and
[`../policies/repository-state.md`](../policies/repository-state.md)
(the committed/staged/unstaged/tracked/untracked category definitions,
per-category detection commands, and the staged-delta fingerprint used
below).

## Flow

```text
resolve local review scope
    ↓
discover applicable AGENTS.md / CLAUDE.md
    ↓
detect each category separately: committed, staged, unstaged, untracked
    ↓
compute staged-delta fingerprint
    ↓
inspect relevant surrounding code
    ↓
review against code + repository conventions
    ↓
return P0/P1/P2 findings, each attributed to its source category
    ↓
stop
```

## Steps

1. Verify the target is a valid Git repository; inspect working-tree
   status, current branch, and HEAD.
2. Resolve the base branch and base SHA. Verify the implementation scope
   is not accidentally being reviewed directly on a protected/default
   branch unless the target repository's own rules explicitly permit it.
   **Do not create a branch** — validate what already exists; branch
   creation belongs to the implementing workflow.
3. Determine the **complete** local delta — do not assume local `HEAD`
   contains the whole task, and do not blend categories into one
   undifferentiated set. Detect each category with its own command per
   [`../policies/repository-state.md`](../policies/repository-state.md),
   "Detection commands per category":
   - **Committed** delta relative to base: `git log <base>..HEAD --oneline`
     (commits) and `git diff <base>...HEAD` (content; files:
     `git diff --name-status <base>...HEAD`). This is relative to the
     **review base**, not to the branch's upstream — it says nothing
     about push status; see step 5 for that, and
     [`../policies/repository-state.md`](../policies/repository-state.md),
     "Committed delta is not push status."
   - **Staged** (tracked, indexed) delta: `git diff --cached` (files:
     `git diff --cached --name-status`).
   - **Unstaged** (tracked, working-tree-only) delta: `git diff`
     (files: `git diff --name-status`).
   - **Untracked** files: `git ls-files --others --exclude-standard`.

   ```text
   base         = A
   local HEAD   = B
   staged       = S (index vs. B)
   unstaged     = U (working tree vs. index)
   untracked    = T (working tree, not tracked)

   Review: A → B + S + U + T, each category attributed separately
   ```

   Record, for the report, whether each category is included in this
   review's scope or explicitly excluded — never silently omitted
   without saying so (see
   [`../templates/local-review-report.md`](../templates/local-review-report.md)).
4. Compute the **staged-delta fingerprint** per
   [`../policies/repository-state.md`](../policies/repository-state.md),
   "Staged delta fingerprint": run `git diff --cached --raw -M -z` and
   take the SHA-256 hash of its exact raw stdout bytes — never of a
   filename list, a human-readable diff, or a newline-converted form of
   that output. Record the resulting fingerprint for the report. If this
   invocation is a re-review and the caller supplied the previously
   reported staged fingerprint as context, compare the two per
   [`../policies/repository-state.md`](../policies/repository-state.md),
   "Fingerprint scope and re-review comparison," and "Re-review
   discipline" below — a match means the staged delta is unchanged since
   the prior review; a difference means it must be reviewed as new
   delta. This comparison says nothing about unstaged or untracked
   state, which are independently (re-)detected via their own commands
   above on every invocation regardless of the staged-fingerprint
   result.
5. Determine push/synchronization status against the branch's own
   configured upstream — this is the single source of truth for
   "local-only"/"not yet pushed" commits, never step 3's base-relative
   committed delta. Resolve local ahead/behind/diverged state with
   `git log @{u}..HEAD --oneline` (local-only, unpushed commits) and
   `git log HEAD..@{u} --oneline` (remote-only commits not yet merged
   locally), or the equivalent ahead/behind counts. If the branch has no
   configured upstream (resolving `@{u}` fails), report "no tracking
   branch configured" explicitly — do not guess or substitute an assumed
   `origin/<branch>` ref. This is informational for the report and the
   caller, not a decision this Skill makes on its own.
6. **Discover applicable repository-local instructions** per
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md):
   for each changed file, look for `AGENTS.md` / `CLAUDE.md` at the
   target repository root and along that file's directory ancestry. Do
   this before reviewing so discovered conventions inform the review
   itself, not just a post-hoc check.
7. Review the complete delta against
   [`review-scope.md`](../../../shared/policies/review-scope.md) and the
   file-treatment rules in
   [`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
   applying the instructions discovered in step 6 and inspecting relevant
   surrounding repository code and tests. In particular, apply
   [`review-scope.md`](../../../shared/policies/review-scope.md), "Related
   changes as one unit" — review related files/hunks in the delta together
   rather than in isolation — and
   [`evidence.md`](../../../shared/policies/evidence.md), "Findings beyond
   the changed lines," when a finding depends on code outside the delta.
   These are the same shared review-quality invariants `github-pr-review`
   applies to a PR; this runbook does not restate their full text.
   Target-repository instructions refine how the code is evaluated; they
   never override this Skill's own safety boundaries (see
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
   "Instruction precedence").
8. Classify findings per
   [`severity.md`](../../../shared/policies/severity.md), each backed by
   evidence and impact per
   [`evidence.md`](../../../shared/policies/evidence.md), using the shared
   finding shape in
   [`finding.md`](../../../shared/templates/finding.md). Attribute each
   finding to the source category it came from — committed, staged,
   unstaged, or untracked — per
   [`../policies/repository-state.md`](../policies/repository-state.md),
   "Attribution in findings." Finalize the complete set of findings —
   including any that were revised, merged, or discarded during review —
   before composing the report. Do not report findings piecemeal as they
   are discovered; the report in step 10 is composed once, from the
   finalized set.
9. Compose the human-facing body per
   [`review-summary.md`](../../../shared/templates/review-summary.md):
   a concrete "What changed" summary, an evidence-backed "What was done
   well" (omit or keep to one line if nothing concrete stands out), the
   finalized findings, and a "Validation" section listing only what was
   actually inspected or executed by this review — do not claim a
   validation step ran if it did not.
10. Render
    [`../templates/local-review-report.md`](../templates/local-review-report.md)
    as one complete report — including the review scope contract fields
    (review base, per-category inclusion/exclusion, staged fingerprint,
    initial-review-vs-re-review, and whether previously reviewed state
    changed) — and return it. **Stop.**

## Constraints

- Must not mutate GitHub state.
- Must not modify implementation files, apply patches, commit, push,
  rebase, create branches, or open PRs.
- Must not decide whether to run again, count iterations, or control the
  implementing Agent — see
  [`../SKILL.md`](../SKILL.md), "Statelessness and Orchestration
  Boundary."
- Must not otherwise mutate the repository beyond read-only inspection
  (see [`git-safety.md`](../../../shared/policies/git-safety.md)).
- Must not ask the user for approval, and must not be invoked as a
  self-triggered re-run. This runbook assumes the caller has already
  obtained fresh, explicit user approval scoped to this specific
  invocation before entering this flow — see
  [`../policies/invocation-approval.md`](../policies/invocation-approval.md)
  for the complete, self-contained contract. This runbook does not
  verify that approval was obtained; that responsibility belongs
  entirely to the caller.

## Re-review discipline (recommended, not enforced by this Skill)

Each invocation of this runbook is independent and stateless. Every
invocation, including a re-review immediately after fixes, requires its
own separate, fresh, explicit user approval — the approval that
authorized a previous invocation never authorizes this one. When an
orchestrator has obtained that new approval and chooses to invoke this
runbook again against updated implementation state, it should primarily
verify:

- whether previously reported blocking findings were resolved;
- whether the fix introduced a regression;
- whether newly changed code creates a new blocking issue.

Do not use a re-review as license for unbounded scope expansion. That
said, a newly discovered P0/P1 with concrete evidence must still be
reported even if it wasn't visible in an earlier pass — do not suppress a
real finding merely because it is new.

When the caller supplies the previously reported staged-delta
fingerprint as re-review context, compare it against the fingerprint
freshly computed in step 4 above, per
[`../policies/repository-state.md`](../policies/repository-state.md),
"Fingerprint scope and re-review comparison":

- **Match** — treat the staged delta as unchanged; focus staged-scope
  effort on verifying previously reported findings in that delta rather
  than re-reviewing it as new content.
- **Differ** — the staged delta changed and must be reviewed as new
  delta, same as any other newly detected content.

This comparison is scoped to the staged category only. Unstaged and
untracked state carry no fingerprint and must be independently
(re-)detected via their own commands (step 3) on every invocation,
regardless of whether the staged fingerprint matched — an unchanged
staged fingerprint must never be read as "nothing changed" when unstaged
or untracked content differs.
