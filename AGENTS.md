# AGENTS.md

This is the **canonical, runtime-neutral, repository-wide instruction
source** for this repository. Every implementation task — regardless of
which runtime executes it — follows the definitions and lifecycle below.

This repository hosts **two portable Code Review Agent Skills** that
share one review standard:

- [`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md)
  — reviews local Git implementation state and returns findings;
- [`skills/github-pr-review/SKILL.md`](skills/github-pr-review/SKILL.md)
  — reviews GitHub Pull Requests and, when active, publishes findings and
  a final decision.

Both consume the same shared review rules in
[`shared/policies/`](shared/policies/) and
[`shared/templates/`](shared/templates/), so P0/P1/P2 review semantics
never diverge between them — see [`ARCHITECTURE.md`](ARCHITECTURE.md) for
the module map.

This file governs *development of this repository itself* (branching,
commits, PRs, merges). It is distinct from how either Skill reviews an
*external* repository — that behavior is defined in each Skill's own
`SKILL.md`.

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

Each Code Review Agent is defined by its own `SKILL.md`
([`local-code-review`](skills/local-code-review/SKILL.md),
[`github-pr-review`](skills/github-pr-review/SKILL.md)). Neither is
defined as a Claude-specific subagent, a Codex-specific agent, a
Cursor-specific agent, an Anthropic API workflow, or any runtime-specific
worker syntax. Runtime adapters (e.g. `CLAUDE.md`) may exist separately,
but never redefine an Agent — they only bootstrap a runtime into reading
the canonical Skills.

**Review orchestration is external to the individual review Skills.**
Deciding when to invoke a Skill, whether to invoke it again, how many
review/fix iterations to run, and when to progress from local review to
opening a PR to GitHub review is the responsibility of the calling
runtime, Team Lead, or implementing workflow — never of
`local-code-review` or `github-pr-review` themselves. See
[`ARCHITECTURE.md`](ARCHITECTURE.md), "Orchestration Boundary." This
discretion is bounded, not open-ended: it never extends to an
implementing Agent invoking `github-pr-review` on the PR it just opened
or updated for its own implementation work — see section 13,
"Implementation Workflow Termination and Reviewer/Author Separation." Nor
does it extend to invoking `local-code-review` automatically — every
invocation requires fresh, explicit user approval scoped to that one run
— see section 14, "Explicit User Approval Required for
`local-code-review` Invocation."

---

## 2. Runtime Neutrality

Canonical repository behavior — this file, `shared/`, and each Skill's
own `SKILL.md` — must not depend on:

- Claude-specific tools or conventions
- Anthropic APIs
- Codex-specific behavior
- Cursor-specific behavior
- any runtime-specific subagent orchestration syntax

Runtime adapters may exist separately (e.g. `CLAUDE.md`) but must never
duplicate or fork these canonical rules.

### Portable Core, Optional Runtime Adapters

The canonical Skill (`SKILL.md` plus its canonical package-relative
resources) **MUST** remain usable without runtime-specific metadata or
runtime-specific tool names. Runtime-specific adapter files **MAY** improve
discovery, presentation, configuration, or execution for one consumer, but
they **MUST NOT** redefine core semantics or become necessary for correctness.

External dependencies are expressed primarily as capabilities (for example,
authenticated GitHub access with sufficient review permissions), not as a
required vendor-specific implementation. A concrete integration or command
may appear as an optional example or fallback when it implements the same
capability contract.

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
how `local-code-review` or `github-pr-review` reviews external repositories
(see each Skill's own `SKILL.md`).

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

## 11. Skill Consumer Branch Policy

This section governs branch discipline for Agents *consuming* either
Code Review Agent Skill against a target repository (the repository being
reviewed) — as distinct from section 3, which governs development of
*this* repository.

The Code Review Agent must understand the distinction between:

- **external PR review** — reviewing a Pull Request that already exists
  on a remote GitHub repository, opened by some other Agent or developer;
- **local implementation review** — reviewing an implementation branch in
  a local working copy, before or during PR creation.

For local implementation workflows, formal review occurs on a dedicated
implementation branch, not directly on the repository's protected/default
branch, unless that repository's own rules explicitly permit it. Before
beginning a local implementation review, the reviewer verifies that:

- the target is a valid Git repository;
- the current branch is identifiable;
- the implementation scope is not accidentally being performed directly
  on a protected/default branch unless repository rules explicitly permit
  it;
- the branch actually contains the implementation intended for review
  (see [`skills/local-code-review/runbooks/local-review.md`](skills/local-code-review/runbooks/local-review.md));
- base and branch state are understood (base branch, base SHA, local
  HEAD, and any divergence from a remote tracking branch).

**The reviewer must not create arbitrary branches just to make review
possible.** Branch creation is owned by the implementing workflow, not by
the Code Review Agent. The reviewer's role is limited to validating branch
state and reviewing what already exists.

---

## 12. Review Ownership

Preserved as a canonical repository-wide principle, applying
independently to both Skills:

```text
One review scope → one Code Review Agent owner
```

The full invariant — including the "Access vs. Ownership" distinction and
the multi-Agent/parallel-review guards — is defined once, in
[`shared/policies/review-ownership.md`](shared/policies/review-ownership.md),
so it is packaged with either Skill rather than living only in this
repository-development document. Both `local-code-review` and
`github-pr-review` reference that file directly.

---

## 13. Implementation Workflow Termination and Reviewer/Author Separation

An implementing Agent's normal workflow ends when it opens or updates the
Pull Request containing its own implementation work. Opening/updating
that PR is the **terminal step** of the implementation workflow, not a
step that automatically chains into review:

```text
implement
    ↓
validate
    ↓
commit
    ↓
push
    ↓
open or update PR
    ↓
STOP
```

The following flow is prohibited: an implementing Agent must never invoke
`github-pr-review` against the PR it just created or updated as part of
its own implementation workflow.

```text
implement → validate → commit → push → open PR → invoke github-pr-review on that PR   ✗ prohibited
```

This holds regardless of whether the implementing Agent technically has
access to the `github-pr-review` Skill. `github-pr-review` is a reviewer
role, not a post-implementation validation step, and it requires a
genuine reviewer/author separation to mean anything — see
[`skills/github-pr-review/SKILL.md`](skills/github-pr-review/SKILL.md)
and [`skills/github-pr-review/policies/github-review.md`](skills/github-pr-review/policies/github-review.md),
"Self-review capability."

Valid shapes keep implementer and reviewer distinct:

```text
Agent A implements → opens PR → STOP
Agent B / a dedicated reviewer → invokes github-pr-review

existing external PR → github-pr-review
```

If local review is wanted for implementation work in progress, that
belongs to `local-code-review`, invoked before or during implementation
completion, subject to its own invocation conditions — see section 14,
"Explicit User Approval Required for `local-code-review` Invocation" —
and never invoked automatically, and never to `github-pr-review` used as
a substitute completion check:

```text
implementation
├─ optional local-code-review, if its invocation conditions are satisfied
└─ commit / push / PR
   └─ STOP

review assignment (separate task, separate identity)
    ↓
github-pr-review
```

Orchestration is the primary safeguard here. `github-pr-review` also
carries its own defensive self-review guard for the case where it is
nevertheless invoked against a PR authored by the authenticated identity
— see [`skills/github-pr-review/policies/github-review.md`](skills/github-pr-review/policies/github-review.md),
"Self-review capability." That guard is a fallback, not a substitute for
orchestration honoring the rule above.

---

## 14. Explicit User Approval Required for `local-code-review` Invocation

`local-code-review` MUST NOT be invoked automatically at any point in an
implementation workflow — not after implementation finishes, not after
validation, not after a fix, and not immediately after a previous
review. Every individual invocation requires fresh, explicit user
approval scoped to that specific run:

```text
implementation finished (or fixes applied)
    ↓
ask user whether to run local-code-review
    ↓
explicit approval for this run?
├── yes → invoke local-code-review once
└── no  → do not invoke, continue without review
```

**Approval is not persistent.** Approval obtained for one invocation
authorizes exactly that one invocation. It must never be treated as:

- approval for the rest of the task;
- approval for all future reviews;
- approval for a review/fix loop;
- approval to automatically re-run after findings are fixed;
- approval to invoke whenever the implementation changes.

```text
user approves review #1
    ↓
local-code-review runs once
    ↓
findings returned
    ↓
Agent fixes findings
    ↓
review #2 desired
    ↓
ask user again — the approval for review #1 does not authorize review #2
```

The following flows are prohibited:

```text
implement → validate → automatically invoke local-code-review            ✗ prohibited

user approved local review once → review → fix findings
    → automatically review again                                        ✗ prohibited

local-code-review finds issues → reviewer triggers itself again
    after fixes                                                          ✗ prohibited

implementation workflow decides review is "best practice"
    → invokes local-code-review without asking                          ✗ prohibited
```

Even when this repository or a target repository generally prefers
review, that preference never substitutes for asking the user before
each specific invocation.

**Caller/reviewer responsibility boundary.** Approval orchestration
belongs to the caller, Team Lead, runtime, or implementing workflow:

```text
caller/orchestrator
    ↓
determines whether review is desired
    ↓
asks user
    ↓
receives explicit approval for this run
    ↓
invokes local-code-review once
```

`local-code-review` itself is not responsible for, and must not attempt,
any of the following:

- asking the user for permission;
- deciding whether another review iteration should happen;
- automatically scheduling a re-review;
- continuing a review/fix/review loop on its own.

The Skill only reviews the scope it was explicitly invoked to review —
see [`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md),
"Statelessness and Orchestration Boundary."

**Scope of explicit approval.** Approval must be unambiguous and
specific to the current review run — for example, an instruction
equivalent to "run local-code-review now," "yes, review the current
implementation," or "perform one local review before pushing." A
previous approval earlier in the task must never be reused. General
statements such as "review things carefully," or a repository policy
that merely recommends review, do not create standing authorization for
repeated invocations.

**Re-review after findings.** If `local-code-review` returns findings
and the implementing Agent fixes them, no automatic re-review is
permitted:

```text
review #1 → findings → fixes → validation → ask user whether to run review #2
```

Only a new, explicit approval permits review #2. This applies to every
subsequent iteration — approval for review N never authorizes review
N+1.

Implementation workflows remain valid whether or not review is approved:

```text
implement → validate → ask whether to run local-code-review

user says no  → continue implementation delivery workflow
user says yes → local-code-review once → return findings → (fixes, if any)
    → ask again before another local-code-review
```

`local-code-review` remains optional and user-authorized; it is not a
mandatory terminal gate before commit, push, or PR creation unless the
user explicitly chooses to run it for that specific invocation. See
[`ARCHITECTURE.md`](ARCHITECTURE.md), "Handoff Between Skills," for how
this approval gate fits into the overall implementation lifecycle.

---

## 15. Relationship to Runtime Adapters and the Skills

```text
CLAUDE.md (or any other runtime adapter)
    ↓
AGENTS.md   (this file — canonical, runtime-neutral)
    ↓
shared/     (review policies/templates common to both Skills)
    ↓
skills/local-code-review/SKILL.md
skills/github-pr-review/SKILL.md
```

Runtime adapters bootstrap a specific runtime into these canonical rules.
They must never duplicate or override them.
