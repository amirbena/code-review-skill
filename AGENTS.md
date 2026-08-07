# AGENTS.md

This is the **canonical, runtime-neutral, repository-wide instruction
source** for this repository. Every implementation task — regardless of
which runtime executes it — follows the definitions and lifecycle below.

This repository hosts a portable **Code Review Agent Skill**. This file
governs *development of this repository itself* (branching, commits, PRs,
merges). It is distinct from how the Code Review Skill reviews *external*
repositories — that behavior is defined in [`SKILL.md`](SKILL.md).

---

## 1. Core Vocabulary: Agent via Skill

```text
Agent
= stable software-engineering role
  (e.g. "Code Review Agent")
  defined by responsibility and scope, not by implementation

Skill
= portable operational definition of the Agent
  (instructions, policies, templates, runbooks)
  authored once, consumed by any runtime

Subagent / Worker
= optional internal execution mechanism used by an Agent
  (a runtime-specific way of parallelizing or delegating work)
  an implementation detail, never the definition of the Agent itself

Runtime
= environment consuming/executing the Skill
  (Claude Code, Codex, Cursor, or any other agent runtime)
```

**Canonical principle:**

```text
Agent via Skill
```

The Code Review Agent is defined by [`SKILL.md`](SKILL.md). It is **not**
defined as a Claude-specific subagent, a Codex-specific agent, a
Cursor-specific agent, an Anthropic API workflow, or any runtime-specific
worker syntax. Runtime adapters (e.g. `CLAUDE.md`) may exist separately, but
never redefine the Agent — they only bootstrap a runtime into reading the
canonical Skill.

---

## 2. Runtime Neutrality

Canonical repository behavior — this file and `SKILL.md` — must not depend
on:

- Claude-specific tools or conventions
- Anthropic APIs
- Codex-specific behavior
- Cursor-specific behavior
- any runtime-specific subagent orchestration syntax

Runtime adapters may exist separately (e.g. `CLAUDE.md`) but must never
duplicate or fork these canonical rules.

---

## 3. Repository Branch Policy

Every materially separate implementation task uses a dedicated task branch.
Implementation is never done directly on `main`.

Preferred naming:

```text
feature/<clear-description>
```

Supported alternatives:

```text
fix/<clear-fix-name>
refactor/<clear-refactor-name>
docs/<clear-docs-name>
test/<clear-test-name>
chore/<clear-chore-name>
```

Do not reuse an already-merged task branch for unrelated work.

Before creating a task branch:

- inspect current branch
- inspect working-tree state
- identify the default/base branch
- inspect local and remote HEAD
- fetch/prune if remote access exists
- verify base synchronization
- preserve unrelated work (never discard it silently)

---

## 4. Clean Branch Exit Policy

Every implementation task must finish in a known, clean state.

**Tasks that end before merge** (e.g. a Skill implementation task not yet
opened as a PR) must finish with:

- current branch = the dedicated task branch
- intended implementation committed
- working tree clean
- no unrelated modifications
- no accidental generated artifacts
- no destructive cleanup used to manufacture this state

**Tasks that include merge and cleanup** must finish with:

- current branch = `main`
- local `main` synchronized with `origin/main`
- merged task branch absent locally
- merged task branch absent remotely
- remote tracking ref pruned
- working tree clean

Never sacrifice unmerged work merely to reach a visually clean status.

---

## 5. Canonical Git Lifecycle

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
how the Code Review Skill reviews external repositories (see `SKILL.md`).

---

## 6. Pull Request Development Rules

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

---

## 7. Merge Strategy

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

---

## 8. Merge Safety

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

---

## 9. Squash Cleanup Safety

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

---

## 10. Git Safety

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

---

## 11. Relationship to Runtime Adapters and the Skill

```text
CLAUDE.md (or any other runtime adapter)
    ↓
AGENTS.md   (this file — canonical, runtime-neutral)
    ↓
SKILL.md    (portable Code Review Agent definition)
```

Runtime adapters bootstrap a specific runtime into these canonical rules.
They must never duplicate or override them.
