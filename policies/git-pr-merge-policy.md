# Git / PR / Merge Policy

Canonical rules for **commits, pushes, Pull Requests, merges, post-merge
cleanup, and destructive-Git prohibitions** in development of *this*
repository.

This is a repository-development policy. It is **not** packaged into either
Skill archive, and no packaged Skill resource may depend on it. It governs
development of *this* repository only — it is distinct from how
`local-code-review` or `github-pr-review` reviews an external repository
(see each Skill's own `SKILL.md`). See
[`repository-workflow.md`](repository-workflow.md) for task-branch
creation and base synchronization,
[`validation-and-clean-exit.md`](validation-and-clean-exit.md) for the
clean end state, and [`AGENTS.md`](../AGENTS.md) for global invariants and
routing.

## Pull Request Development Rules

Before opening a PR for this repository:

- validate the work
- fetch remote state
- inspect branch/base divergence
- synchronize safely if necessary
- verify expected HEAD
- push the dedicated task branch

When opening a PR:

- resolve the authenticated GitHub identity
- assign that same account as assignee when supported
- never infer the assignee from Git config, email, repository owner, or
  display name
- if assignment cannot be resolved, open the PR normally and report it

PR assignment is metadata only. It is not approval.

## Merge Strategy

Default merge strategy: **squash merge**.

```text
task branch commits
    ↓
one focused squash commit
    ↓
main
```

Use another strategy only when explicitly requested, required by repository
policy, or when preserving individual commits is intentionally necessary.
Do not create unnecessary merge commits.

## Merge Safety

Before merge:

- re-fetch
- verify PR state
- verify reviewed HEAD matches current HEAD
- inspect checks
- inspect reviews
- inspect unresolved comments
- inspect mergeability
- ensure no new unreviewed commits appeared

Attempt a normal squash merge first. Admin privileges may be used only when
the PR is otherwise safe and normal merge is blocked solely by an
administrative/protection gate. Never use admin privileges to bypass
conflicts, failing validation, requested changes, blocking review findings,
or correctness/safety problems.

## Squash Cleanup Safety

Because squash merging breaks ancestry, `git branch -d <branch>` may fail
after a valid squash merge. Before using the forced form:

```text
git branch -D <branch>
```

verify:

1. the PR is `MERGED`
2. the resulting squash commit exists on `main`
3. all intended task content exists on `main`
4. the task branch contains no additional unmerged work
5. the working tree is safe

This is a narrow post-merge cleanup exception only. It must not normalize
destructive Git behavior elsewhere.

## Git Safety

Destructive Git shortcuts are prohibited, including:

- `git reset --hard`
- `git clean -fd`
- force push
- branch deletion used merely to hide divergence
- history rewriting merely to simplify review

If the repository contains unexpected local commits, divergence, ambiguous
conflicts, unrelated uncommitted work, or uncertain merge state:

```text
preserve state
→ inspect
→ report
→ do not guess
```
