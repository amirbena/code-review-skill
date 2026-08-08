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

### Packaged Skills Are Independent of Repository-Level `AGENTS.md`

This file governs development and orchestration of *this* source
repository. A distributed Skill archive (built by
[`scripts/package-skills.sh`](scripts/package-skills.sh) /
[`scripts/package-skills.ps1`](scripts/package-skills.ps1)) never contains
this file, `ARCHITECTURE.md`, or this repository's `README.md` — so no
file that is part of a packaged Skill (`SKILL.md`, a packaged policy, a
runbook, a template, or shared/-packaged resource) may use this
repository's own `AGENTS.md` as a runtime dependency or canonical source
required for understanding or executing that Skill:

```text
AGENTS.md
→ repository development/orchestration rules

packaged Skill
→ SKILL.md
→ packaged policies
→ packaged runbooks
→ packaged templates/shared resources
```

Not:

```text
packaged Skill resource
→ ../../AGENTS.md
```

If a rule a packaged Skill relies on must remain available after
packaging, its canonical portable form belongs inside a packaged
resource, using the resource type that best fits the rule — prefer the
most specific one that avoids duplicating the same rule across multiple
files:

```text
normative reusable invariant  → policy (skills/<skill>/policies/ or shared/policies/)
operational procedure         → runbook
reusable output/content shape → template
Skill-level responsibility     → SKILL.md
```

When this file also needs to mention such a rule for repository-development
context, prefer pointing toward the packaged canonical resource rather than
the reverse:

```text
AGENTS.md → references the packaged canonical policy/runbook/template/SKILL.md   (preferred)
packaged Skill → references AGENTS.md                                            (prohibited)
```

`AGENTS.md` may summarize a rule's repository-development implications, but
the portable Skill must remain fully correct and self-explanatory with
`AGENTS.md`, `ARCHITECTURE.md`, and this repository's `README.md` deleted
from the consumer's environment entirely.

This prohibition is narrowly about *this source repository's own*
`AGENTS.md`. It does not extend to either Skill's own behavior: both
`local-code-review` and `github-pr-review` legitimately discover and read
an `AGENTS.md` (or `CLAUDE.md`) that belongs to the *target* repository
being reviewed — see
[`shared/policies/repository-instructions.md`](shared/policies/repository-instructions.md).
That target-repository instruction discovery is valid, packaged, portable
behavior and is unaffected by this rule.

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
implementation workflow. Each invocation — the first review and any
later re-review after fixes — requires fresh, explicit user approval
scoped to that specific run; approval for review N never authorizes
review N+1. Obtaining that approval is entirely the responsibility of
the caller, Team Lead, runtime, or implementing workflow — never of the
Skill itself:

```text
implementation complete (or a fix just applied)
    ↓
caller asks the user for approval to run local-code-review
    ↓
fresh approval for this run?
├── yes → one local-code-review invocation
└── no  → do not invoke; continue without review

another review desired afterward → fresh approval required again
```

`local-code-review` is optional and user-authorized, never a mandatory
terminal gate before commit, push, or PR creation.

This is a repository-level orchestration summary only. The complete
portable contract — approval scope, prohibited invocation flows, the
caller/orchestrator responsibility boundary, and what the Skill itself
must never do — is owned by
[`skills/local-code-review/policies/invocation-approval.md`](skills/local-code-review/policies/invocation-approval.md),
which this rule does not duplicate. See also
[`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md),
"Statelessness and Orchestration Boundary," and
[`ARCHITECTURE.md`](ARCHITECTURE.md), "Handoff Between Skills," for how
this approval gate fits into the overall implementation lifecycle.

---

## 15. Shell / PowerShell Script Parity

This repository intentionally ships genuine cross-platform counterpart
scripts for the same repository capability — currently
[`scripts/package-skills.sh`](scripts/package-skills.sh) and
[`scripts/package-skills.ps1`](scripts/package-skills.ps1). When the
functionality represented by both a `.sh` script and its corresponding
`.ps1` script changes, both implementations MUST be updated in the same
task so they remain behaviorally equivalent — including their packaged
resource lists, validation steps, and guard behavior:

```text
change shell implementation
    ↓
inspect PowerShell counterpart
    ↓
update PowerShell counterpart

or

change PowerShell implementation
    ↓
inspect shell counterpart
    ↓
update shell counterpart
```

This holds even when only one runtime is available for execution in the
current environment — the inability to execute one platform-specific
script is a **validation limitation to report**, never a reason to leave
that counterpart stale:

```text
update by inspection
    ↓
perform static/equivalence checks where possible
    ↓
report the execution limitation
```

This rule applies to genuine counterpart scripts that implement the same
repository capability on two platforms, not to unrelated `.sh` and `.ps1`
files that happen to share a naming pattern.

---

## 16. Human-Facing Review Publication

Preserved as a canonical repository-wide principle, applying
independently to both Skills:

```text
analyze complete review scope
    ↓
collect candidate findings
    ↓
verify evidence
    ↓
finalize severity
    ↓
deduplicate findings
    ↓
determine decision
    ↓
publish one organized review
```

Each Skill's output is a finalized review artifact, not a stream of
intermediate reviewer observations. A candidate finding may still be
revised, merged, upgraded, downgraded, or discarded during analysis —
publishing it before finalization would expose reasoning that has not
yet settled, and risks noisy, contradictory, or duplicate output. Neither
Skill publishes a finding, comment, or partial review as it is
discovered; both publish once, after the review scope is complete and
findings are finalized.

`local-code-review` always returns exactly one organized report per
invocation, never a sequence of separately surfaced findings followed by
a summary — see
[`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md),
"Statelessness and Orchestration Boundary," and
[`skills/local-code-review/runbooks/local-review.md`](skills/local-code-review/runbooks/local-review.md).

`github-pr-review`, whenever the GitHub review capability supports a
submission carrying both a review body and multiple inline comments,
submits finalized inline findings together as part of one coherent
GitHub review rather than one standalone comment per discovered finding.
When a resolved inline location is unavailable or rejected, the finding
remains represented in the review body rather than being dropped or
attached to an arbitrary line. The complete batching, inline-eligibility,
and fallback contract is owned by
[`skills/github-pr-review/policies/github-review.md`](skills/github-pr-review/policies/github-review.md)
— see "Analysis phase vs. publication phase," "Batched review
construction and submission," and "Rejected inline location fallback."
This file does not duplicate that contract.

The complete human-facing output shape (result, what changed, meaningful
strengths, findings, validation, decision) and the finding contract
(what/where/evidence/impact/recommended direction) are owned by
[`shared/templates/review-summary.md`](shared/templates/review-summary.md)
and [`shared/templates/finding.md`](shared/templates/finding.md),
consumed identically by both Skills — this file does not duplicate their
complete templates. Machine-oriented state (reviewed HEAD, finding
counts, a normalized decision value, internal identifiers) may remain
available where genuinely required by orchestration, but stays
subordinate to that human-facing output in both Skills' published and
returned review artifacts.

---

## 17. Relationship to Runtime Adapters and the Skills

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
