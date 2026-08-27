# Policy — Parallel Review (PR application)

`github-pr-review`'s application of the portable parallel-review contract.
Canonical index: [`github-review.md`](github-review.md). The contract —
"parallelism is an execution optimisation, never a semantic change", the
worker input/output shape, review dimensions, the execution-policy gate,
centralized aggregation, and failure handling — is owned by the shared
[`parallel-review.md`](../../../shared/policies/parallel-review.md) and is
not restated here.

This file adds only what is PR-specific.

## Where it runs

After PR scope is established, any repository-backed checkout is verified,
changed files and their normalized repository-instruction context are
resolved, and before findings are finalized. Required repository-context
failure starts no workers. It never changes the review mode
([`reviewer-delta-review.md`](reviewer-delta-review.md)), the PR delta, the
self-review guard, or the batched single-review publication
([`review-output.md`](review-output.md)).

## Execution-policy signals for a PR

Sequential review is the default. Apply the shared two-gate decision only
after context resolution: reliable runtime capability plus at least two
materially independent dimensions with a credible latency benefit. PR shape
may reveal those dimensions—requirements, architecture, correctness,
repository policy, config/infra, independent subsystems, or prior-review
reconciliation—but changed-file count alone never selects parallelism.
Small/localized or mechanically broad PRs remain sequential when the parent
can review them efficiently.

## Shared checkout vs. worker copies

In this phase workers are **read-only**, so they all inspect the **same**
immutable, detached repository-backed checkout
([`repository-checkout.md`](repository-checkout.md)) — one clone, not one per
worker. Distinguish:

- **runtime execution isolation** — some runtimes give each sub-agent its own
  isolated worktree/sandbox for *execution*; that is a runtime concern;
- **semantic repository snapshot** — every worker must analyse the **same PR
  base/head state**. If a runtime insists on per-agent worktrees, each must
  be checked out at the identical `head_sha`, and none may modify it.

Every worker also receives the identical normalized repository-instruction
context identity. The parent resolves that context once; workers never
rediscover `AGENTS.md` independently.

The repository-backed checkout lifecycle in
[`repository-checkout.md`](repository-checkout.md) is independent of, and not
owned by, any worker-isolation mechanism.

## Aggregation and output

The aggregating reviewer is the same one that submits the single GitHub
review. Worker candidate findings are normalized, deduplicated, and
reconciled, then [`severity.md`](../../../shared/policies/severity.md)'s
mechanical derivation produces one decision — see
[`review-output.md`](review-output.md), "Final decision." Workers publish
nothing.

## Required vs. incomplete

If a required review dimension cannot be produced (worker failed and the
parent cannot recover it), the reasoning result is `REVIEW INCOMPLETE` per
[`review-output.md`](review-output.md), "Final decision" — never `REVIEW
CLEAN` / `Approve`. An optional dimension the parent recovers itself does not
degrade the result.

## Runtime realisation

Capability detection picks whichever mechanism the runtime actually exposes;
the Skill never enables an experimental one by changing the user's
configuration. Sequential review is always the fallback and never fails the
review.

| Runtime | Parallel mechanism | Prerequisite | If unavailable |
|---|---|---|---|
| **Claude Code** | Agent Teams (parent + parallel sub-agents) | Agent Teams are experimental and disabled by default; they require the environment/settings opt-in `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. The Skill detects it; it never sets it. | ordinary Task/sub-agent calls if available, else sequential |
| **Cursor** | Subagents with isolated context windows, run in parallel; project agents under `.cursor/agents/` (Cursor also reads `.claude/agents/` and `.codex/agents/` for compatibility, with its own precedence) | subagent capability enabled in Cursor | sequential |
| **Codex** | Multiple concurrent agents / tasks, with isolated worktrees available for parallel work | concurrent-agent capability in the Codex app/CLI | sequential |

These product details change over time and are cited, with a "last verified"
note, in this repository's `docs/runtime-parallelism.md` (a repository
development doc, not part of this packaged Skill). Keeping only capability
*names* here, and the source citations there, means a product change updates
one doc, not this policy.

## Boundary

- No new mutation; the PR stays the Review Target; decision derivation is
  unchanged (shared [`parallel-review.md`](../../../shared/policies/parallel-review.md),
  "Boundaries").
