# Runbook — Passive Local Review

Applies policies: [`review-scope.md`](../policies/review-scope.md),
[`severity.md`](../policies/severity.md), [`evidence.md`](../policies/evidence.md),
[`local-review.md`](../policies/local-review.md),
[`repository-instructions.md`](../policies/repository-instructions.md),
[`git-safety.md`](../policies/git-safety.md).

## Flow

```text
local implementation
    ↓
inspect Git state
    ↓
determine base
    ↓
determine full local delta
    ↓
review
    ↓
P0/P1/P2
    ↓
return report to implementing Agent
```

## Steps

1. Verify the target is a valid Git repository; inspect working-tree
   status, current branch, and HEAD.
2. Resolve the base branch and base SHA (see
   [`../AGENTS.md`](../AGENTS.md) section 11, "Skill Consumer Branch
   Policy" — the reviewer validates branch state, it does not create
   branches).
3. Determine the full local delta per
   [`../policies/local-review.md`](../policies/local-review.md): committed
   branch delta, local-only commits, staged changes, unstaged changes,
   and relevant untracked files.
4. Load applicable repository-local instructions (see
   [`../policies/repository-instructions.md`](../policies/repository-instructions.md)).
5. Review the complete delta against
   [`../policies/review-scope.md`](../policies/review-scope.md).
6. Classify findings per [`../policies/severity.md`](../policies/severity.md),
   each backed by evidence per
   [`../policies/evidence.md`](../policies/evidence.md).
7. Render [`../templates/local-review-report.md`](../templates/local-review-report.md)
   and return it to the implementing Agent.

## Constraints

- Must not mutate GitHub state.
- Must not modify implementation files.
- Must not commit, push, or otherwise mutate the repository beyond
  read-only inspection (see
  [`../policies/git-safety.md`](../policies/git-safety.md)).

For the surrounding iterate-until-clean behavior, see
[`review-loop.md`](review-loop.md). For what happens once review is
clean, see [`local-pr-completion.md`](local-pr-completion.md).
