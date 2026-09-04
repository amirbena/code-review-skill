# Parallel review

## What it does

Splits one review into independent **read-only workers** — each assigned
a single analysis dimension (scope/requirements, architecture/invariants,
correctness/regression, tests/configuration, existing-review
reconciliation) — that run concurrently from the same normalized inputs.
One aggregating reviewer then normalizes, deduplicates, reconciles, and
applies the canonical severity model to produce **one** finding set and
**one** decision.

Parallelism changes only *how fast* the analysis runs, never *what* it
concludes: a sequential run and a parallel run of the same review must
reach equivalent findings and the same decision.

## When it is useful

- A larger PR with genuinely independent work — say a schema change, a
  cross-component refactor, and new retry logic — where several
  dimensions can be analysed at once.
- It is not triggered by file count: thirty renamed or generated files
  may be trivial; three files may carry independent architecture and
  correctness work.

## Which Skill(s)

The portable contract is shared
([`shared/policies/parallel-review.md`](../../shared/policies/parallel-review.md))
and is currently **wired into `github-pr-review`**
([`policies/parallel-review.md`](../../skills/github-pr-review/policies/parallel-review.md)).
`local-code-review` would apply the same contract. Per-runtime facts
(Claude Code Agent Teams, Cursor subagents, Codex concurrent agents) are
isolated in [`../runtime-parallelism.md`](../runtime-parallelism.md).

## Default, conditional, or requested

**Conditional; sequential is the default and always-valid path.** Two
gates must both pass: the runtime exposes a reliable multi-agent /
sub-agent capability, **and** at least two materially independent
dimensions can begin from the same inputs with an expected latency
benefit. If capability detection is uncertain, the review runs
sequentially. A review is never failed or downgraded because parallelism
is unavailable.

## How to invoke it

There is no flag, and you do not need to ask for it. When the capability
is present and the change warrants it, the reviewer plans parallel
workers on its own; otherwise it runs sequentially. The Skill **never
mutates your shell, settings, or runtime configuration** to obtain a
capability — an experimental mechanism is used only when its prerequisite
is already enabled in your environment.

## Limitations & safety boundaries

- **Read-only workers.** Publication and any Approve/Request Changes stay
  the single aggregating reviewer's, once.
- **The review target is unchanged** — splitting by dimension never
  widens scope; every worker is bounded to the same delta.
- **Parallelism never manufactures `REVIEW CLEAN`.** A required dimension
  that no worker (or the parent) produced yields `REVIEW INCOMPLETE`.
- Worker completion order never affects the result.

## Canonical semantics

[`shared/policies/parallel-review.md`](../../shared/policies/parallel-review.md)
· [`skills/github-pr-review/policies/parallel-review.md`](../../skills/github-pr-review/policies/parallel-review.md)
· runtime facts in [`../runtime-parallelism.md`](../runtime-parallelism.md)
· pipeline placement in [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §2.
