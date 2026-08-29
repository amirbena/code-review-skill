# ARCHITECTURE.md

This document describes the conceptual architecture of this repository's
two Code Review Agent Skills. It is intentionally decoupled from any
specific runtime implementation — see [`AGENTS.md`](../AGENTS.md)
("Global invariants" — runtime neutrality; and the **Agent via Skill**
vocabulary it defines) and
[`policies/skill-development-policy.md`](../policies/skill-development-policy.md),
"Portable Core, Optional Runtime Adapters." For why this architecture
exists — how it differs from Claude Code's
own native review, GitHub-native review, and third-party reviewers — see
[`CODE_REVIEW_COMPARISON.md`](CODE_REVIEW_COMPARISON.md).

## The mental model in one picture

```text
                     Shared Review Standard
             (shared/policies/ — scope, severity, evidence,
              review-context, review-evidence, ownership)
                              │
              ┌───────────────┴───────────────┐
              │                               │
      local-code-review                github-pr-review
              │                               │
   Review target: local Git delta   Review target: GitHub PR delta
   (committed / staged / unstaged /  (full diff, or a bounded
    untracked, detected separately)   reviewer-owned delta re-review)
              │                               │
   Delivery: one structured report   Delivery: a report (passive), or
   returned to the caller             inline comments + summary +
                                      Approve / Request Changes (active)
```

Everything in the top box is **one copy**, consumed identically by both
Skills, so P0/P1/P2 semantics never diverge. Everything below the split is
**target-specific**.

### What is shared vs. what differs

| Concern | Shared (one copy under `shared/`) | Differs per Skill |
|---|---|---|
| Review reasoning | scope, correctness, regression, architecture, behavioral heuristics | — |
| Severity | the P0/P1/P2 model and the mechanical blocking rule | only the decision *labels*: `REVIEW CLEAN` / `CHANGES REQUIRED` vs. `Approve` / `Request Changes` |
| Context model | review target / review context / repository context / existing review evidence | a thin per-Skill application (the local delta vs. the PR) |
| State inspection | — | local Git state vs. GitHub PR state |
| Delivery | the canonical report and finding shapes | a local report vs. GitHub publication |
| Extra machinery | — | `github-pr-review` only: temporary checkout, parallel workers, self-review guard, review-action authorization (verdict ≠ mutation authority), SHA-bound delta re-review |

### Where to read next

You do not need to read the numbered sections in order — each is
self-contained. Jump to what you need:

| To understand… | Read |
|---|---|
| which file owns what, and how it maps into an archive | §1 Module Map, §7 Packaging |
| the review-target / review-context / evidence vocabulary | §1 (shared model) and §2, "Normalize Inputs" |
| the end-to-end review pipeline | §2 Core Pipeline |
| who owns policy vs. runbook vs. output | §1 "Thin runbooks", §3 Separation of Concerns, §9 |
| what the caller owns, and the Skill does not | §4 Orchestration Boundary, §5 Handoff Between Skills |
| what is packaged vs. repository-only or test-only | §7 Packaging, §8 discovery metadata |
| what is deliberately not built | §2, "Future work" |

## 1. Module Map

```text
                 shared/
            review policies
                  │
         ┌────────┴────────┐
         │                 │
local-code-review    github-pr-review
         │                 │
 local report        GitHub delivery
```

```text
AGENTS.md
    ↓
repository rules (development of *this* repository)

shared/policies/
    ↓
review-scope, severity, evidence, repository-instructions, git-safety,
review-ownership — one copy each, consumed by both Skills (and packaged
with either, so each archive is self-contained)

shared/policies/review-context.md
    ↓
the review-target / review-context / repository-context /
existing-review-evidence model, plus requirement-context semantics
(evidence hierarchy, focus mapping, scope-boundary reasoning, explicit
non-goals) — consumed by both Skills

shared/policies/review-evidence.md
    ↓
Existing Review Evidence: classifying prior findings/comments as
still-relevant, resolved, stale, duplicate, settled decision, or
speculative discussion, and reconciling without blind inheritance —
consumed by both Skills

shared/policies/parallel-review.md
    ↓
portable parallel-review contract: sequential/parallel equivalence,
capability detection, worker input/output, execution-policy gate,
centralized aggregation, failure handling — packaged with both Skills,
wired into github-pr-review

shared/policies/file-reviewability.md
    ↓
evidence-based handling for generated, vendored, lock, minified, binary,
snapshot, and other opaque or machine-produced changes

shared/policies/invocation-options.md
    ↓
deterministic current-invocation normalization for presentation options,
including per-Skill finding-detail defaults and finding-level precedence

shared/templates/finding.md
    ↓
one canonical finding contract — a compact, field-oriented
`id`/`severity`/`title`/`Location`/`Evidence`/`Impact`/`Fix` shape,
concise by default, with a controlled `Details` field for genuinely
complex findings; the fields are the stable contract, the rendering is
one projection of them, and it is rendered per delivery surface

shared/templates/review-summary.md
    ↓
one canonical human-facing review body shape (result, what changed,
strengths, findings, validation, decision), rendered differently per
delivery surface — machine metadata stays subordinate to it

skills/local-code-review/
    ↓
SKILL.md (stateless, bounded) + its own runbook/template/metadata

skills/github-pr-review/
    ↓
SKILL.md + its own GitHub-specific policy/runbooks/templates/metadata
```

Neither Skill owns a copy of the severity model, evidence requirements,
review-scope rules, or the review-context / existing-review-evidence model
— all reference [`shared/policies/`](../shared/policies/) directly.
`github-pr-review` additionally has its own policy family, indexed from
[`policies/github-review.md`](../skills/github-pr-review/policies/github-review.md),
for GitHub-specific delivery rules with no local-review analogue: review
authority and self-review, **review-action authorization**
(`policies/review-action-authorization.md`: review analysis is separate
from GitHub mutation authority — a non-mutating `recommendation-only`
default, `block-only`, and `explicitly-authorized auto-action`; trusted
mutation authorization scoped to the invocation/repo/PR/HEAD/action;
reviewer independence as *authority* separation, not just a different
username; fail closed on ambiguity), reviewer delta re-review, PR scope
and pagination, review reasoning (logical cohorts, code-impact/dependency
analysis), finding placement, batched publication/decision, the opt-in
**repository-backed checkout** lifecycle (`policies/repository-checkout.md`:
isolated temporary clone, base/head fidelity, read-only inspection,
security, guaranteed cleanup) — plus three **thin PR applications** of a
shared model (`policies/review-context.md`: the PR is the review target,
scope-boundary reasoning for a PR; `policies/review-evidence.md`: the PR's
own prior reviews/comments as Existing Review Evidence;
`policies/parallel-review.md`: threshold signals, shared checkout vs. worker
copies, and per-runtime realisation for the shared parallel contract).
`local-code-review` has its own analogous policy family under
`skills/local-code-review/policies/`, for local-Git-specific rules with no
PR analogue: invocation approval, the repository-state category
definitions (including push/synchronization status and the staged-delta
fingerprint re-review contract), and two thin local applications of the
shared model (`policies/review-context.md`: the local delta is the review
target; `policies/pr-context.md`: an optional associated PR's prior
findings/decisions as Existing Review Evidence). The optional review
context accepts, uniformly, free-form requirements, explicit user
instructions, a Jira/tracker ticket, an explicitly supplied GitHub Issue
(no automatic PR↔Issue discovery), an HLD/ADR, or an implementation plan.

### Thin runbooks, canonical policy owners

A runbook is an execution document, not a second policy store — see
[`policies/skill-development-policy.md`](../policies/skill-development-policy.md),
"Runbook Design," for the canonical rule. It defines flow, phase ordering, and which policy governs each
phase; it does not restate that policy's decision tables, edge-case
semantics, or state-interpretation rules. Concretely:

```text
Shared policy (shared/policies/)
    → reusable review semantics (scope, evidence, severity, and the
      behavioral heuristics below), identical across both Skills

Skill-specific policy (skills/<name>/policies/)
    → semantics unique to that Skill (local Git-state mechanics and
      optional-input handling for local-code-review; GitHub delivery
      mechanics for github-pr-review)

Runbook (skills/<name>/runbooks/)
    → execution flow and phase ordering only; each step names the
      policy that governs it rather than repeating that policy's text
```

`skills/local-code-review/runbooks/local-review.md` and
`skills/local-code-review/policies/repository-state.md` are the clearest
example: Git category detection, push/sync status, and the complete
staged-fingerprint precondition/comparison contract live entirely in the
policy; the runbook states only when each is resolved and applied in the
execution flow.

## 2. Core Pipeline (per Skill)

At a glance, every review — either Skill, either delivery mode — runs three
phases:

1. **Resolve inputs** — turn the invocation into normalized presentation
   options, a Review Target, optional Review Context, Repository Context, and
   optional Existing Review Evidence (nothing below the target ever widens it).
2. **Reason** — inspect state read-only, compute the exact delta, optionally
   prepare a repository-backed checkout, plan sequential or parallel
   execution, produce candidate findings, then reconcile them centrally.
3. **Decide and deliver** — one aggregator applies the shared severity
   model to produce one P0/P1/P2 set and one decision, rendered as a local
   report or a GitHub review.

The detailed stage list below expands those three phases.

```text
Review Invocation
    ↓
Resolve External Context
    ├── Jira MCP / connector        (only when a Jira reference is supplied;
    │                                read-only; unresolved → JIRA CONTEXT
    │                                UNRESOLVED, stop — no key/branch inference)
    ├── explicit GitHub Issue context (reference → read-only GitHub, or
    │                                  pasted text; no auto PR↔Issue discovery)
    └── supplied free-form context    (consumed directly, no resolution)
    ↓
Normalize Inputs
    ├── Review Target        (local delta | GitHub PR delta)
    ├── Review Context        (optional: user instructions / resolved Jira /
    │                          GitHub Issue / HLD / ADR / plan / PR description)
    ├── Repository Context   (repository snapshot / API-accessible files;
    │                          applicable AGENTS.md hierarchy; repository
    │                          policies; architecture/docs; surrounding code;
    │                          tests/config)
    └── Existing Review Evidence (optional: prior findings, resolved
                                  findings, settled decisions, prior comments)
    ↓
Git / GitHub State Inspector
    ↓
Review Delta Resolver
    ↓
Prepare Repository Context
    ├── GitHub/API-only mode         (no checkout)
    ├── Temporary repository-backed mode (mode family)
    ├── Optional repository-backed enrichment (failure → visible API-only degradation)
    └── Required repository-backed review (failure → REVIEW INCOMPLETE):
          mkdtemp → blobless clone → fetch base/head → detached checkout at
          head_sha; read-only; PR delta stays merge-base(base,head)..head
    ↓
Resolve changed files and one normalized per-file AGENTS.md hierarchy
    ↓
Plan Review Execution
    ├── Sequential                   (default and always valid)
    └── Parallel only with capability + at least two materially independent
          dimensions + expected latency benefit (read-only workers,
          same PR base/head snapshot; execution optimisation only)
    ↓
Review workers  (each: Review Target, Review Context, Repository Context
                 location + snapshot identity, resolved instruction-context
                 identity, Existing Review Evidence, assigned dimension,
                 applicable policies → candidate findings only)
    ↓
Reconcile findings  (normalize → deduplicate → reconcile overlapping/
                     conflicting → canonical severity)
    ↓
Shared Review Semantics  (shared/policies/)
    ├── scope validation (incl. scope-boundary reasoning against context)
    ├── correctness
    ├── regression analysis
    ├── architecture / repository invariants
    └── severity classification  (shared/policies/severity.md)
    ↓
Canonical final decision  (one aggregator; worker order never matters;
                           required dimension missing → REVIEW INCOMPLETE)
    ↓
Skill-Specific Output
    ├── local-code-review  → structured report (always)
    └── github-pr-review   → Passive Report | Active GitHub Review
    ↓
Cleanup  (github-pr-review: remove the temporary checkout on every exit
          path — success, failure, interruption — guarded delete only)
```

This flow is conceptual guidance, not a required implementation shape — the
Skills are natural-language instruction packages, and the ordering above is
the reading order their `SKILL.md` and runbooks already imply. Repository-backed
modes and parallel workers apply to `github-pr-review` only;
`local-code-review` and API-only `github-pr-review` skip those stages entirely
with no loss of correctness.

### Stage responsibilities

- **Review Invocation** — for `local-code-review`: "review this local
  implementation state," optionally with review context (free-form text or a
  Jira / GitHub Issue reference) and/or an associated PR reference. For
  `github-pr-review`: a PR URL, a PR number with repository context, or a
  repository + PR number, optionally with review context (free-form text or a
  Jira / GitHub Issue reference; the PR description is always available).
- **Resolve External Context** — before review reasoning, turn *references*
  into normalized context, per
  [`shared/policies/review-context.md`](../shared/policies/review-context.md),
  "Input form" and "Jira context resolution." Free-form text is consumed
  directly. A **Jira reference** triggers the shared policy's explicit,
  numbered **"Resolution procedure"** — (1) identify an available Jira
  integration (a Jira MCP server, a Jira connector, or an equivalent
  runtime-exposed Jira read tool — a capability, not a hard-coded
  transport); (2) invoke it read-only to fetch the issue's contents;
  (3) fetch relevant comments and linked requirement context when supported;
  (4) normalize into Review Context (the downstream shared policies consume
  the normalized context, never a raw connector payload); (5) continue only
  on success. Jira access is **retrieval only** — no issue edits,
  transitions, comments, field changes, ticket creation, or assignment. If
  any step fails (no integration, authentication or authorization failure,
  issue not found, malformed reference, connector/MCP error or timeout), the
  Skill returns the explicit
  `JIRA CONTEXT UNRESOLVED` outcome and does not perform the Jira-scoped
  review — it never infers the ticket from its key, the branch name, the PR
  title, a commit message, or surrounding text. A **GitHub Issue reference**
  is resolved through read-only GitHub access when available, or supplied as
  pasted text; there is **no automatic PR↔Issue discovery**. Supplying no
  Jira reference is always valid — Jira is never mandatory.
- **Normalize Inputs** — resolves the repository, base branch, and (for
  `github-pr-review`) the PR itself, and separates the four concepts owned
  by [`shared/policies/review-context.md`](../shared/policies/review-context.md)
  and [`shared/policies/review-evidence.md`](../shared/policies/review-evidence.md):
  the **review target** (never widened by anything below it), optional
  **review context** (intended scope/requirements — focuses attention and
  enables scope-boundary reasoning), **repository context**, and optional
  **existing review evidence** (prior findings/decisions, reconciled not
  inherited — always against the *current* target, so a resolved thread is
  evidence of a past conclusion, not proof of present correctness, and a
  changed PR HEAD re-classifies every prior human finding; automation/bot
  comments contribute observations only and never settle a decision alone —
  [`shared/policies/review-evidence.md`](../shared/policies/review-evidence.md),
  "Interpret prior evidence against the current target" and "Comment
  authorship"). Missing optional inputs change nothing.
- **Git / GitHub State Inspector** — read-only inspection of Git state
  (branch, HEAD, staged/unstaged/untracked) and, for `github-pr-review`,
  GitHub state (PR metadata, base/head SHA, checks, existing comments,
  prior reviews with their `APPROVED` / `CHANGES_REQUESTED` / `COMMENTED`
  state, review comments, issue comments, and review-thread `isResolved`
  state where GitHub exposes it — retrieved paginated-to-exhaustion via an
  authenticated GitHub integration, `gh api` + GraphQL `reviewThreads` being
  one example, per
  [`skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md),
  "Retrieving prior review activity"). Never mutates state.
- **Review Delta Resolver** — computes exactly what must be reviewed: the
  committed delta relative to base, plus any local-only commits, staged
  changes, unstaged changes, and relevant untracked files (local), or the
  PR's full or bounded-delta diff (GitHub).
- **Prepare Repository Context** — in **API-only mode** (default, and the
  only mode for `local-code-review`), surrounding context comes from
  API/working-tree reads. In optional or required **temporary repository-backed mode**
  (`github-pr-review` — [`skills/github-pr-review/policies/repository-checkout.md`](../skills/github-pr-review/policies/repository-checkout.md)),
  the Skill also materialises an isolated, read-only, detached checkout at
  the PR head: `mkdtemp` under a safe scratch parent → blobless clone
  (`--no-checkout --no-tags --filter=blob:none`) → fetch base/head refs
  (SHA fallback) → detached checkout of the immutable `head_sha`, verified.
  Both real GitHub metadata and the repository's local PR simulation resolve
  to one `NormalizedPrSource` the checkout consumes. It stays **read-only** —
  no target-repository tests/builds/linters/hooks/scripts run; the PR delta
  remains `merge-base(base_sha, head_sha)..head_sha` and surrounding files
  never become independent review targets. Every Git call runs with
  `core.hooksPath=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, `--no-tags`, no
  submodule update. Optional failure visibly degrades to API-only. Required
  failure is pre-grading `REVIEW INCOMPLETE` with repository context
  unavailable, and no workers start. The temporary directory is owned
  by one lifecycle with guarded cleanup on every exit path (see "Cleanup").
- **Repository Instruction Resolver** — after target/changed-file resolution,
  resolve root-to-specific applicable `AGENTS.md` chains once from the same
  repository snapshot. Missing files are valid; applicable unreadable or
  unsafe paths make context incomplete. The normalized per-file mapping and
  identity go unchanged to sequential execution or every worker and never
  widen the Review Target.
- **Plan Review Execution** — sequential is the default. Detect the runtime's parallel capability
  (`none` / isolated sub-agents / experimental agent teams, usable only when
  already enabled / native concurrent agents; uncertain → `none`). Use
  parallel **read-only** workers only when a capability exists **and** at
  least two materially independent analysis dimensions can run from the same
  normalized inputs with an expected latency benefit. File count alone is
  never a gate; dependent dimensions remain sequential. Parallelism is an execution
  optimisation only — [`shared/policies/parallel-review.md`](../shared/policies/parallel-review.md)
  requires that sequential and parallel runs reach the same findings and
  decision, and the Skill never mutates the user's configuration to obtain a
  capability.
- **Review workers** — each worker gets one bounded, normalized input
  (identical Review Target, Review Context, Repository Context location and
  snapshot identity, resolved instruction context and identity, and Existing
  Review Evidence across a run; its own assigned dimension and
  policies) and returns **structured candidate findings only**. It never
  publishes and never derives the final decision.
- **Reconcile findings** — one centralized aggregation stage: normalize →
  deduplicate (same location + normalized claim; carry the higher candidate
  severity, report once) → reconcile overlapping/conflicting findings. Worker
  completion order never affects the result.
- **Repository Context Loader** — loads relevant surrounding context
  beyond the raw diff: repository-local instructions, architecture docs,
  related tests, contracts, schemas, and conventions — from the temporary
  checkout when repository-backed mode prepared one, otherwise from
  API/working-tree reads.
- **Canonical final decision** — only the aggregating reviewer applies
  [`shared/policies/severity.md`](../shared/policies/severity.md)'s
  mechanical derivation to produce the one P0/P1/P2 set and one
  `REVIEW CLEAN` / `CHANGES REQUIRED` (local) or `Approve` / `Request
  Changes` (GitHub). A **required** review dimension that no worker produced
  and the parent could not recover yields `REVIEW INCOMPLETE` — never a
  clean/approved result. Parallelism cannot manufacture `REVIEW CLEAN`.
- **Cleanup** — for `github-pr-review` repository-backed mode, the temporary
  checkout is removed on **every** exit path (success, review/worker
  failure, context-resolution failure after allocation, publication failure,
  interruption the runtime surfaces), in a `finally`/equivalent. Deletion is
  refused unless the target resolves inside the scratch parent, is not the
  scratch parent itself, and carries this Skill's ownership marker — no
  unconstrained recursive delete.
- **Shared Review Semantics** — the single review reasoning
  model defined by `shared/policies/review-scope.md`, plus scope validation
  against any supplied review context per
  [`shared/policies/review-context.md`](../shared/policies/review-context.md),
  "Scope-boundary reasoning." Identical regardless of which
  Skill or delivery mode invokes it. Beyond the baseline concern list, this
  model reasons in the same local-first, signal-triggered style about four
  higher-value behavioral concerns when the diff's own shape makes them
  relevant: whether new business/validation/state-transition logic
  duplicates an existing canonical owner rather than reusing it; whether a
  multi-step, retryable, or externally re-triggerable flow leaves safe or
  stranded state on partial failure, and whether any claimed recovery path
  is actually evidenced; whether a changed contract, return value, or
  exception is followed to its real callers, including exceptions that are
  now swallowed, translated, or masked by a fallback; and, only once a
  change actually has a production-operational failure mode worth
  detecting or diagnosing (an explicit applicability gate — commonly
  backend/service/queue/integration/retry/background-job changes,
  conditionally frontend changes with an established client telemetry
  convention, usually not agent-instruction/prompt/policy/static-doc
  changes unless they carry runtime behavior of their own), whether that
  failure path stays diagnosable through the repository's own established
  metrics/alerts or logging convention. None of these expand the model
  into a repository-wide audit — each is gated on a concrete signal in the
  diff and scaled to blast radius exactly like the model's other
  reasoning, per `shared/policies/review-scope.md` and
  `shared/policies/evidence.md`.
- **Severity classification** — every actionable finding is assigned
  exactly one severity: P0, P1, or P2, per
  [`shared/policies/severity.md`](../shared/policies/severity.md). The final
  decision is derived mechanically from blocking severities; supplied
  context and reconciled prior evidence inform which findings exist and at
  what severity, never a separate decision path.
- **Skill-Specific Output** — `local-code-review` always returns a
  structured report. `github-pr-review` either returns a report (passive) or
  publishes to GitHub (active). The delivery adapter never changes the
  underlying findings or severities.

### Implemented since the initial design

- **Temporary repository-backed GitHub PR review** — `github-pr-review` has
  an opt-in mode that materialises an isolated, read-only, detached checkout
  at the PR head (`skills/github-pr-review/policies/repository-checkout.md`).
  It is context only: the PR stays the Review Target and no target-repository
  code runs.
- **Portable parallel review** — an opt-in execution optimisation with
  capability detection and a sequential fallback
  (`shared/policies/parallel-review.md`), realised via Claude Code Agent
  Teams, Cursor subagents, or Codex concurrent agents where available.
  Semantics are unchanged: one aggregator, one decision.
- **Review-action authorization** — `github-pr-review` separates review
  analysis from GitHub mutation authority
  (`skills/github-pr-review/policies/review-action-authorization.md`). The
  review always runs and produces a verdict; whether that verdict is
  *submitted* as an `APPROVE` / `REQUEST_CHANGES` event is a separate
  authorized decision. The default is non-mutating
  (`recommendation-only`); `APPROVE` is submitted only in
  `explicitly-authorized auto-action` mode, only under trusted mutation
  authorization (independent of the review-performing/orchestrating
  agent, scoped to the invocation/repo/PR/reviewed HEAD/action) and
  genuine reviewer independence (authority separation, not merely a
  different GitHub username). Agent-controlled flags, prompts, generated
  instructions, nested Skill/agent invocations, alternate tokens, and
  alternate identities cannot establish it; ambiguity fails closed. A
  verdict is not authorization (`REVIEW CLEAN` ≠ `APPROVE`) and approval
  is not merge authority (`APPROVE` ≠ `MERGE`). As a portable Skill with
  no runtime of its own, it cannot cryptographically verify provenance —
  it guarantees the safe default and the capability boundary and relies
  on the runtime for an independent authorization channel.

### Future work (not implemented)

The following are deliberately **not** part of the current architecture and
are documented here only to mark them as future phases — no code, policy, or
runbook implements them today:

- **GitHub merge-blocking / required status checks** — neither Skill
  creates a GitHub status check, a required check, a ruleset, or any
  branch-protection state. `github-pr-review`'s maximum positive action
  remains **Approve**; it never blocks merges through GitHub machinery.
- **Automatic execution of PR code** — neither Skill runs the target
  repository's tests, linters, build, hooks, or arbitrary commands, even in
  repository-backed mode. Cloning untrusted PR code is not permission to
  execute it.

## 3. Separation of Concerns

| Concern | Owned by |
|---|---|
| Review reasoning (what's wrong, why, severity) | shared/policies/, consumed identically by both Skills |
| Local Git state inspection | `local-code-review` |
| GitHub state inspection + delivery (comments, Approve/Request Changes) | `github-pr-review` |
| Orchestration (which Skill runs when, loop control, fix application) | The calling workflow / Team Lead — **never** either Skill |
| Implementation ownership (writing/fixing code) | The implementing Agent or developer — **never** either Skill |

## 4. Orchestration Boundary

Neither Skill owns orchestration. The runtime, Team Lead, or implementing
Agent is responsible for:

- deciding when to invoke `local-code-review`;
- deciding whether to invoke it again, and how many times;
- applying fixes based on returned findings;
- committing and pushing;
- deciding when to open/update a PR;
- deciding when to invoke `github-pr-review`, and in which mode.

This discretion is bounded, not open-ended in two independent ways.

First, invoking `local-code-review` at all is never automatic. Every
single invocation — the first review of an implementation and any later
re-review after fixes — requires the orchestrator to have already
obtained fresh, explicit user approval scoped to that one run. An
approval that authorized one invocation never authorizes another; the
orchestrator must ask again before each subsequent invocation, including
immediately after fixing findings from the previous one. See
[`policies/review-orchestration-policy.md`](../policies/review-orchestration-policy.md),
"Explicit User Approval Required for `local-code-review` Invocation."

Second, it never extends to an implementing Agent invoking
`github-pr-review` against the PR it just opened or updated for its own
implementation work. Opening/updating that PR is the terminal step of the
implementation workflow — see
[`policies/review-orchestration-policy.md`](../policies/review-orchestration-policy.md),
"Implementation Workflow Termination and Reviewer/Author Separation."
`github-pr-review` is a reviewer-role Skill invoked by a genuinely
separate reviewer or review task, not a post-implementation validation
step chained onto the same workflow.

```text
Orchestrator
    ↓
chooses Skill
    ↓
Skill reviews once
    ↓
returns result
```

The orchestrator owns repetition; the Skill does not remember previous
invocations. This is why `local-code-review` ships with no
`review-config.yaml` or `max_loops` setting — loop limits are an
orchestration-level configuration concern, outside either Skill's
package. A separate orchestration layer may default to something like 3
iterations, but that default lives outside these Skills.

## 5. Handoff Between Skills

```text
Implementation Agent (implementation finished, or a fix just applied)
    ↓
ask user: run local-code-review for this run?
    ↓
explicit approval for this run?
├── no  → continue without review
└── yes
     ↓
   Local Code Review Skill (single invocation — this run only)
     ↓
   findings
     ↓
   Implementation Agent fixes (if any)
     ↓
   [no automatic re-run — ask the user again before another invocation]
    ↓
local implementation accepted by orchestrator
    ↓
push / open or update PR
    ↓
STOP (implementation workflow ends here)

— separate reviewer / review task —
    ↓
GitHub PR Review Skill
```

Each `Local Code Review Skill` box above represents exactly one
invocation, gated by its own fresh, explicit user approval obtained
immediately beforehand. Approval for one invocation never carries over
to a later one — see
[`policies/review-orchestration-policy.md`](../policies/review-orchestration-policy.md),
"Explicit User Approval Required for `local-code-review` Invocation." A
"no" at any
approval gate is a fully valid outcome: the implementation workflow
continues straight to local acceptance, push, and PR without review.

`local-code-review` does not automatically invoke `github-pr-review`,
and neither does the implementing Agent that just opened or updated the
PR — see
[`policies/review-orchestration-policy.md`](../policies/review-orchestration-policy.md),
"Implementation Workflow Termination and Reviewer/Author Separation."
`github-pr-review` is
invoked by a genuinely separate reviewer (a different Agent/identity, or
a dedicated review task against an existing PR), never as an automatic
continuation of the same implementation workflow. `github-pr-review`
does not assume `local-code-review` was previously run — it reviews the
PR's actual current state regardless of history. They are independently
invokable, and each may be used without the other.

## 6. External PR Workflow (`github-pr-review`)

```text
External GitHub PR
    ↓
Resolve reviewer identity + PR author
    ↓
Inspect authoritative PR HEAD
    ↓
Review
    ↓
Inline findings
    ↓
P0 / P1 / P2
    ↓
Permitted Approve/Request Changes event
or explicit formal-review unavailability
    ↓
Stop
```

Maximum automated positive action: **Approve**. No merge occurs — the
repository owner or their merge workflow performs the merge separately,
following
[`policies/git-pr-merge-policy.md`](../policies/git-pr-merge-policy.md)'s
merge-strategy rules when this repository's own PRs are the ones being
merged. See
[`skills/github-pr-review/runbooks/active-pr-review.md`](../skills/github-pr-review/runbooks/active-pr-review.md).

## 7. Packaging: Source Layout vs. Distribution Layout

Source layout and distribution layout are intentionally different:

```text
source repository layout            standalone Skill archive
(skills/<name>/, shared/)                (dist/*.zip)
    ↓                                        ↓
skills/<name>/SKILL.md              →   SKILL.md            (archive root)
skills/<name>/runbooks/…            →   runbooks/…
skills/<name>/templates/…           →   templates/…
skills/<name>/policies/…            →   policies/…
skills/<name>/metadata/…            →   metadata/…
shared/policies/…, shared/templates/…  →  shared/policies/…, shared/templates/…
```

`scripts/package-skills.sh` / `scripts/package-skills.ps1` assemble this
distribution layout by staging each Skill's files under `dist/.staging/`,
dropping the `skills/<name>/` source prefix so `SKILL.md` lands at the
archive root, then zipping the staged tree's *contents* (not the staging
folder itself) into `dist/*.zip`. Staging is removed after a successful
build, so normal output is just the two zips under `dist/`.

Because `SKILL.md` moves from `skills/<name>/SKILL.md` (source depth 2)
to the archive root (depth 0), its relative links into `shared/` change
from `../../shared/...` to `shared/...`; nested files one level under the
Skill (`runbooks/`, `templates/`, `policies/`, source depth 3) change
from `../../../shared/...` to `../shared/...`. The packaging scripts
apply this as a narrow, deterministic text substitution across the
staged Markdown files — scoped to exactly those two link prefixes — after
copying and before archiving. Skill-internal links (`../SKILL.md`,
`runbooks/...`, etc.) are untouched, since a Skill's own internal
relative depth is unchanged by removing the shared `skills/<name>/`
wrapper. The canonical source files in `skills/<name>/` remain the single
source of truth; only the staged copies are rewritten.

## 8. Agent Skills Discovery vs. Operational Behavior

Each `SKILL.md`'s YAML frontmatter (`name` and `description`) is Agent Skills
discovery metadata only — it exists so a runtime can find and activate the
right Skill without loading anything else. It carries no review policy of
its own.

```text
SKILL.md frontmatter
    ↓
Skill discovery (name, description)

SKILL.md body
    ↓
core operating instructions (identity, inputs, workflow, mutation boundary)

shared/policies/, runbooks/, templates/
    ↓
detailed review rules, procedures, and output contracts, loaded as needed
```

`skills/<name>/metadata/skill.yaml` remains separate package metadata
(version, capabilities, packaged-file manifest) for consumers outside the
Agent Skills discovery path; its `name`/`description` are a mirror of the
canonical values in `SKILL.md`'s frontmatter, not a second source of truth.
Packaging fails unless both values are exactly equal. Resource paths remain
repository-relative in canonical source metadata and are narrowly adapted
in staged package metadata, then checked for containment and existence.

## 9. Reasoning vs. Delivery vs. Ownership

- **Review reasoning** is Skill-agnostic and delivery-mode-agnostic: the
  same shared policies and severity model apply in `local-code-review`
  and in both modes of `github-pr-review`.
- **The canonical finding contract is shared, its rendering is a
  projection.** Both Skills render the one compact, field-oriented finding
  shape in
  [`shared/templates/finding.md`](../shared/templates/finding.md)
  (`id`/`severity`/`title`/`Location`/`Evidence`/`Impact`/`Fix`, concise
  by default, with a controlled `Details` field for complex findings). The
  human projection reads problem → impact → fix → optional supporting detail.
  The fields are the stable, agent-parseable contract; each surface (local
  report, GitHub review body, GitHub inline comment) projects the same
  fields. A future machine-readable renderer would be another projection —
  it would not redesign the review reasoning model or the severity/
  decision semantics.
- **Detail is presentation-only.** `include_finding_details` defaults to
  `true` locally and `false` on GitHub; a per-finding decision overrides the
  invocation, which overrides the Skill default. The option never changes the
  canonical finding data, severity, or decision.
- **Human-facing report formatting is not implied by shared reasoning.**
  Each Skill's own template owns the presentation appropriate to its own
  delivery surface, per
  [`shared/templates/review-summary.md`](../shared/templates/review-summary.md),
  "Machine metadata is subordinate": `local-code-review`'s
  [`templates/local-review-report.md`](../skills/local-code-review/templates/local-review-report.md)
  renders its trailing metadata as plain Markdown and relevance-gates
  which fields appear (a report read directly in a terminal/chat has no
  use for a collapsible widget, and an initial review with nothing
  staged has no use for a fixed, empty-input fingerprint every time),
  while `github-pr-review`'s
  [`templates/external-review-summary.md`](../skills/github-pr-review/templates/external-review-summary.md)
  legitimately wraps its own optional subordinate metadata in a
  collapsible `<details>` block, since GitHub natively renders and
  collapses it. Neither choice is more "correct" than the other — they
  are Skill-specific answers to different delivery surfaces, and a
  change to one Skill's presentation must not be read as implying the
  other should match it.
- **GitHub submission capability** is separate from reasoning. A clean or
  blocking result remains valid even when the authenticated account (for
  example, the PR author) cannot submit the corresponding formal review.
- **GitHub mutation authority** is separate again from both reasoning and
  submission *capability*. Even when reasoning is clean and the account
  *could* submit an `APPROVE`, the event is submitted only in
  `explicitly-authorized auto-action` mode under trusted, scoped
  authorization and genuine reviewer independence
  (`skills/github-pr-review/policies/review-action-authorization.md`). The
  default is `recommendation-only`; a verdict is not authorization and
  approval is not merge authority. This gate composes with — never
  replaces — HEAD revalidation, stale-review protection, reviewer
  ownership, delta re-review, and the mechanical severity → decision
  derivation.
- **Git/GitHub state inspection** is read-only and never assumes GitHub
  is authoritative when local state diverges from it — see
  [`skills/local-code-review/runbooks/local-review.md`](../skills/local-code-review/runbooks/local-review.md).
- **GitHub delivery** is the only stage permitted to mutate PR state
  (comments, review decisions), owned exclusively by `github-pr-review`
  in active mode.
- **Orchestration ownership** (deciding which Skill runs when, enforcing
  one-reviewer-per-scope, enforcing any loop limit) belongs to the
  calling workflow — see section 4.
- **Implementation ownership** always belongs to the implementing Agent
  or developer, never to either Skill.

## 10. Portable Core, Optional Runtime Adapters

The portable core is `SKILL.md` plus the canonical package-relative policies,
runbooks, templates, shared resources, and portable package metadata. It owns
all normative review semantics and expresses external dependencies as
capabilities rather than vendor-specific tools.

Runtime adapters are subordinate optional resources. They may improve
discovery, UI presentation, or runtime configuration, but they cannot redefine
review scope, severity, mutation boundaries, output contracts, or dependency
requirements. Ignoring or removing an adapter leaves a coherent Skill. The
current `agents/openai.yaml` files contain only optional Codex UI metadata and
are not referenced by the portable core.

Installation location is a consumer concern, not a package format. The same
standalone package can be placed under a runtime-supported destination such as
`.agents/skills/<name>/`, `.claude/skills/<name>/`,
`.cursor/skills/<name>/`, or `.opencode/skills/<name>/`; each archive still
keeps `SKILL.md` at its own root.

### Documentation-backed compatibility matrix

This matrix records format conclusions from current product documentation. It
is not a claim that every runtime loaded these packages during validation.

| Concern | Claude | Codex | Cursor | OpenCode |
|---|---|---|---|---|
| Canonical directory-based `SKILL.md` | documented | documented/static validation | documented | documented |
| Canonical `name` / `description` | documented | documented/static validation | documented | documented |
| Package-relative supporting files | documented | documented/static validation | documented | documented |
| Runtime-specific adapter required | no | no | no | no |
| Optional adapter used here | none | `agents/openai.yaml` | none | none |

The common canonical frontmatter deliberately contains only `name` and
`description`. Although the open Agent Skills specification defines additional
optional keys, the current Codex validation guidance accepts a narrower set;
keeping capability requirements in the Skill body avoids coupling canonical
validity to optional-field handling. Claude- or Cursor-specific frontmatter is
not required, and OpenCode documents both directory-based supporting resources
and `.agents/skills` discovery. Actual runtime loading is reported separately
from documentation and static package validation.
