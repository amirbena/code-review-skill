# ARCHITECTURE.md

This document describes the conceptual architecture of the Code Review
Agent Skill. It is intentionally decoupled from any specific runtime
implementation — see [`AGENTS.md`](AGENTS.md) section 2 ("Runtime
Neutrality") and the **Agent via Skill** vocabulary in section 1.

## 1. Module Map

```text
                    SKILL.md
                       │
             ┌─────────┴─────────┐
             │                   │
          Policies            Runbooks
             │                   │
             └─────────┬─────────┘
                       │
                 Core Review
                       │
                 Templates
                       │
              Delivery Adapter
                 /           \
          Passive          GitHub
```

```text
AGENTS.md
    ↓
repository rules (development of *this* repository)

SKILL.md
    ↓
portable Agent behavior — concise entry point, references the rest

policies/
    ↓
stable review invariants (severity, evidence, scope, ownership, ...)

runbooks/
    ↓
step-by-step execution procedures per entry point

templates/
    ↓
human-facing output contract

metadata/
    ↓
Skill identity / package metadata

review-config.yaml
    ↓
user-configurable behavior (e.g. review.max_loops)
```

`SKILL.md` is the operational entry point but owns no detailed rule or
procedure directly — it resolves mode, then delegates to `policies/` for
what must always hold true, to `runbooks/` for what to actually do step by
step, and to `templates/` for how output must look. `AGENTS.md` sits
above all of this and governs *this repository's own* development
(branching, commits, PRs, merges) rather than how the Skill reviews an
external repository.

## 2. Core Pipeline

```text
Input
    ↓
Review Context Resolver
    ↓
Git / GitHub State Inspector
    ↓
Review Delta Resolver
    ↓
Repository Context Loader
    ↓
Core Code Review Engine
    ↓
Finding Classification
    ↓
Delivery Mode
    ├── Passive Report
    └── Active GitHub Review
```

### Stage responsibilities

- **Input** — a PR URL, a PR number with repository context, a
  repository + PR number, or "review the local branch/working tree."
- **Review Context Resolver** — determines whether this is a GitHub PR
  review or a local branch review, and resolves the repository, base
  branch, and (for PRs) the PR itself.
- **Git / GitHub State Inspector** — read-only inspection of Git state
  (branch, HEAD, staged/unstaged/untracked) and, when applicable, GitHub
  state (PR metadata, base/head SHA, checks, existing comments). This
  stage never mutates state.
- **Review Delta Resolver** — computes exactly what must be reviewed: the
  committed delta relative to base, plus any local-only commits, staged
  changes, unstaged changes, and relevant untracked files not yet
  reflected in a PR.
- **Repository Context Loader** — loads relevant surrounding context
  beyond the raw diff: repository-local instructions (`AGENTS.md`,
  `SKILL.md`, contribution guides), architecture docs, related tests,
  contracts, schemas, and conventions needed to judge the change fairly.
- **Core Code Review Engine** — the single review reasoning model. Used
  identically regardless of delivery mode — see
  [`policies/review-scope.md`](policies/review-scope.md).
- **Finding Classification** — every actionable finding is assigned
  exactly one severity: P0, P1, or P2 — see
  [`policies/severity.md`](policies/severity.md).
- **Delivery Mode** — the same findings are either returned as a passive
  report or published as an active GitHub review. The delivery adapter
  never changes the underlying findings or severities.

## 3. Separation of Concerns

| Concern | Owned by |
|---|---|
| Review reasoning (what's wrong, why, severity) | Core Code Review Engine |
| Git state inspection | Git / GitHub State Inspector |
| GitHub delivery (comments, Approve/Request Changes) | Delivery Mode: Active GitHub Review |
| Orchestration (which Agent runs when, loop control) | The calling workflow / Team Lead, using `review-config.yaml` |
| Implementation ownership (writing/fixing code) | The implementing Agent or developer — **never** the Code Review Agent |

The Code Review Agent produces findings and, in active mode, publishes
them to GitHub. It does not edit implementation files and does not merge
Pull Requests.

## 4. Local Workflow

```text
Implementation Agent
    ↓
Local Git State
    ↓
Passive Code Review
    ↓
Findings
    ↓
Implementation Fix
    ↓
Re-review
    ↓
... up to review.max_loops (review-config.yaml; default 3) ...
    ↓
Review Clean
    ↓
Commit
    ↓
Push
    ↓
Open / Update PR
    ↓
Stop
```

No merge occurs in the local workflow. The dedicated task branch and any
opened/updated PR are left for the developer or an owning workflow to
merge. See [`runbooks/review-loop.md`](runbooks/review-loop.md) and
[`runbooks/local-pr-completion.md`](runbooks/local-pr-completion.md).

## 5. External PR Workflow

```text
External GitHub PR
    ↓
Inspect authoritative PR HEAD
    ↓
Review
    ↓
Inline findings
    ↓
P0 / P1 / P2
    ↓
Approve or Request Changes
    ↓
Stop
```

Maximum automated positive action: **Approve**. No merge occurs in the
external PR workflow — the repository owner or their merge workflow
performs the merge separately, following `AGENTS.md`'s merge-strategy rules
when this repository's own PRs are the ones being merged. See
[`runbooks/active-pr-review.md`](runbooks/active-pr-review.md).

## 6. Reasoning vs. Delivery vs. Ownership

- **Review reasoning** is delivery-mode-agnostic: the same Core Code
  Review Engine and severity model apply whether the result is reported
  passively or published actively.
- **Git state inspection** is read-only and never assumes GitHub is
  authoritative when local state diverges from it — see
  [`policies/local-review.md`](policies/local-review.md), "Local/remote
  gap detection."
- **GitHub delivery** is the only stage permitted to mutate PR state
  (comments, review decisions), and only in active mode.
- **Orchestration ownership** (deciding which Agent acts next, enforcing
  one-reviewer-per-scope, and enforcing `max_loops`) belongs to the
  calling workflow, not to the Core Code Review Engine itself.
- **Implementation ownership** always belongs to the implementing Agent or
  developer, never to the Code Review Agent.
