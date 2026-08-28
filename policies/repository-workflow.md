# Repository Workflow Policy

Canonical rules for **task branches** in development of *this* repository:
which branch a task runs on, how the base is synchronized, how unrelated
local work is preserved, and how a task branch is named.

This is a repository-development policy. It is **not** packaged into either
Skill archive, and no packaged Skill resource may depend on it. It is
distinct from how `local-code-review` or `github-pr-review` reviews an
external repository — that behavior is defined in each Skill's own
`SKILL.md`. See [`AGENTS.md`](../AGENTS.md) for global invariants,
instruction precedence, and task routing, and
[`git-pr-merge-policy.md`](git-pr-merge-policy.md) for commit, push, PR,
and merge rules.

## Repository Branch Policy

Every materially separate implementation task uses a dedicated,
freshly created task branch. Implementation is never done directly on
`main`, and never continued on a branch created for a different,
previous task.

**Required order — no implementation/documentation file may be modified
before step 6 completes:**

1. inspect repository state (current branch, working-tree status, local
   HEAD)
2. verify/synchronize the intended base branch (identify the default/
   base branch, fetch/prune if remote access exists, compare against
   `origin/main`)
3. ensure the working tree is clean, or safely preserve any legitimate
   existing work (never discard it silently)
4. create a new task-specific branch from the synchronized base
5. switch to that branch
6. only then modify implementation or documentation files

An implementing Agent must not:

- modify files directly on `main`;
- continue a new, unrelated task on a branch created for a previous
  task — including a branch that already carries a previous task's
  commits or an already-open PR;
- reuse an already-open PR branch for unrelated work;
- begin implementation and only create or switch branches afterward.

If the current branch is `main`, a previous task's feature/fix branch,
or any branch not created specifically for the task at hand, step 4
(fresh branch creation) is mandatory before any edit — do not treat
continuing on that branch as an acceptable shortcut, even if the branch
is already synchronized with the base.

### Continuing on an already-correct task branch

The converse also holds: if the current branch is already clearly
associated with the task/context at hand (for example, an Agent resuming
its own in-progress task branch), step 4 is **not** re-triggered —
continue on that branch rather than creating an unnecessary nested or
replacement branch. "Dedicated task branch" means one branch per task,
not one branch per work session on that task.

### Preserving local changes when switching (stash discipline)

Step 3 ("ensure the working tree is clean, or safely preserve any
legitimate existing work") is a `git stash` obligation whenever the
current branch is unrelated to the task at hand and the working tree is
not already clean:

1. inspect the local changes before doing anything else — never assume
   what they are;
2. never discard them (no `git reset --hard`, `git checkout .`, `git
   clean -fd`, or equivalent) merely to reach a clean state for the
   branch switch;
3. `git stash` them (including untracked content, via `-u`, when
   relevant) before creating/switching to the task branch;
4. create/switch to the branch that actually belongs to the current
   task;
5. `git stash pop` only when the stashed changes are determined to
   belong to the current task — never automatically, and never merely
   because a stash exists.

If the stashed changes belong to a different task, leave them stashed,
report that a stash exists and what it contains, and do not mix it into
the current task branch. Branch hygiene is never a reason to discard or
blend unrelated working-tree changes.

Branch names follow the shared contributor convention in
[`../CONTRIBUTING.md`](../CONTRIBUTING.md), "Branch names": `feat/`, `fix/`,
`docs/`, `test/`, `refactor/`, `chore/`, or `research/`, followed by a
lowercase kebab-case description of one logical task. The convention applies
equally to maintainers, external contributors, and coding agents; the work,
not the person or runtime, determines the name. An associated Issue number is
optional.

Do not reuse an already-merged task branch for unrelated work.

## Canonical Git Lifecycle

```text
receive implementation task
    ↓
verify safe/clean base
    ↓
create dedicated task branch
    ↓
implement
    ↓
validate
    ↓
synchronize with target HEAD
    ↓
push
    ↓
open PR
    ↓
assign authenticated PR creator when supported
    ↓
code review
    ↓
squash merge by default
    ↓
switch to main
    ↓
sync main
    ↓
delete merged task branch locally + remotely
    ↓
prune
    ↓
clean final state
```

These rules govern development of *this* repository. They are distinct from
how `local-code-review` or `github-pr-review` reviews external repositories
(see each Skill's own `SKILL.md`). The commit/push/PR/merge steps are
governed by [`git-pr-merge-policy.md`](git-pr-merge-policy.md); the
clean-exit end state is governed by
[`validation-and-clean-exit.md`](validation-and-clean-exit.md).
