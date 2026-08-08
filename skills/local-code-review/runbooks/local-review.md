# Runbook — Local Review

The single runbook for `local-code-review`. Applies shared policies:
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md),
[`evidence.md`](../../../shared/policies/evidence.md),
[`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
[`git-safety.md`](../../../shared/policies/git-safety.md).

## Flow

```text
local repository state
    ↓
identify implementation delta
    ↓
inspect changed implementation
    ↓
apply shared review policies
    ↓
return P0/P1/P2 findings
    ↓
stop
```

## Steps

1. Verify the target is a valid Git repository; inspect working-tree
   status, current branch, and HEAD.
2. Resolve the base branch and base SHA. Verify the implementation scope
   is not accidentally being reviewed directly on a protected/default
   branch unless the target repository's own rules explicitly permit it
   (this repository's own development documentation calls this the
   "Skill Consumer Branch Policy"). **Do not create a branch** — validate
   what already exists; branch creation belongs to the implementing
   workflow.
3. Determine the **complete** local delta — do not assume local `HEAD`
   contains the whole task:
   - the committed branch delta relative to base;
   - local-only commits (not yet pushed);
   - staged modifications;
   - unstaged modifications;
   - relevant untracked files.

   ```text
   base         = A
   local HEAD   = B
   working tree = C

   Review: A → B + C
   ```
4. Note synchronization state for the report (local ahead/behind/diverged
   relative to any tracking branch) — this is informational for the
   caller, not a decision this Skill makes on its own.
5. Load applicable repository-local instructions (see
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md)).
6. Review the complete delta against
   [`review-scope.md`](../../../shared/policies/review-scope.md), including
   relevant surrounding repository code and tests.
7. Classify findings per
   [`severity.md`](../../../shared/policies/severity.md), each backed by
   evidence per [`evidence.md`](../../../shared/policies/evidence.md), using
   the shared finding shape in
   [`finding.md`](../../../shared/templates/finding.md).
8. Render
   [`../templates/local-review-report.md`](../templates/local-review-report.md)
   and return it. **Stop.**

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

## Re-review discipline (recommended, not enforced by this Skill)

Each invocation of this runbook is independent and stateless. When an
orchestrator chooses to invoke it again against updated implementation
state, it should primarily verify:

- whether previously reported blocking findings were resolved;
- whether the fix introduced a regression;
- whether newly changed code creates a new blocking issue.

Do not use a re-review as license for unbounded scope expansion. That
said, a newly discovered P0/P1 with concrete evidence must still be
reported even if it wasn't visible in an earlier pass — do not suppress a
real finding merely because it is new.
