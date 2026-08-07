# Runbook — Local Workflow Completion

Runs once [`review-loop.md`](review-loop.md) reaches `REVIEW CLEAN`.

## Flow

```text
REVIEW CLEAN
    ↓
verify intended implementation
    ↓
verify commit state
    ↓
commit if the implementing Agent still owns an intended uncommitted change
    ↓
push branch
    ↓
open PR if no PR exists, or update the existing PR
    ↓
stop
```

## Role boundary

The Code Review Agent remains a reviewer throughout. The implementing
Agent/workflow owns code changes and implementation commits (see
[`../AGENTS.md`](../AGENTS.md) section 11). The surrounding local workflow
— not the Code Review Agent itself — performs the push and PR
creation/update once review is clean.

## Rules

- No merge. This runbook never merges the resulting PR.
- Do not automatically switch to `main`.
- Finish with:
  - the dedicated task branch still checked out;
  - the intended implementation committed;
  - the branch pushed;
  - a PR created or updated;
  - a clean working tree;
  - no unrelated changes.

Merge ownership belongs to the developer or an explicitly owning workflow
— see [`../AGENTS.md`](../AGENTS.md) for this repository's own merge
rules, which are distinct from how this Skill treats a *reviewed*
repository's PRs.
