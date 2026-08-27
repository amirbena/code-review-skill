# Shared Policy — Parallel Review Capability

Applies to any Code Review Skill in this repository. Defines the **portable
contract** for splitting one review across independent workers when the
runtime exposes a reliable multi-agent / sub-agent capability. Runtime-specific
realisation (Claude Code, Cursor, Codex) lives in each Skill's own
`policies/parallel-review.md`; this file is transport-neutral.

## Parallelism is an execution optimisation, never a semantic change

Given the same Review Target, Review Context, Repository Context, Existing
Review Evidence, and policies, **sequential and parallel execution must
produce equivalent final findings and decisions.** Parallelism changes only
*how fast* the analysis runs, never *what* it concludes. Sequential execution
is always a valid, complete implementation of this contract; a review is
never failed or downgraded because parallelism is unavailable.

## Capability detection, not assumption

There is no universal "spawn agent" syntax. Before planning parallel work,
detect what the current runtime actually supports:

- **none** → sequential review;
- **ordinary isolated sub-agents** → parallel workers via that mechanism;
- **an experimental / opt-in agent-team mechanism** → usable only when its
  prerequisite is already satisfied in the environment; the Skill never
  enables it by mutating the user's configuration;
- **native concurrent agents / tasks** → parallel workers via that mechanism.

If detection is uncertain, treat the capability as **none**.

## Parallelism threshold

Do not spawn workers for every small change. Use parallel workers only when
the runtime supports it **and** the change is complex enough to benefit.
Signals of complexity (illustrative, not a precise formula):

- many changed files;
- several distinct components touched;
- an architecture or configuration change;
- a substantial amount of supplied review context;
- a cross-cutting change.

Absent such signals, run sequentially. Keep the rule simple; when in doubt,
sequential.

## Worker contract

Every worker receives one **bounded, normalized** input and returns
**structured candidate findings only** — it never publishes, never derives
the final decision, and never sees another worker's output.

```text
Worker input
- Review Target                    (identical for all workers in a run)
- Review Context                   (identical for all workers in a run)
- Repository Context location      (identical for all workers in a run)
- Repository snapshot identity     (identical for all workers in a run)
- Resolved repository instruction context and identity (identical for all workers)
- Existing Review Evidence         (identical for all workers in a run)
- Assigned review dimension        (differs per worker)
- Applicable policies              (the shared policies for that dimension)
```

The identical fields are the run's semantic snapshot:
every worker analyses the same PR base/head state and the same context. A
worker that received a different snapshot is a bug, not a smaller review.
The parent resolves hierarchical repository instructions exactly once before
planning or spawning workers; workers never rediscover them.

### Review dimensions

A reasonable default split (adjust to the change, do not force all five):

- **Scope / requirements** — does the change do what was asked, nothing
  unrelated; scope-boundary reasoning against supplied context.
- **Architecture / repository invariants** — repository policies,
  interfaces/contracts, architectural constraints.
- **Correctness / regression** — logic, edge cases, failure/retry safety,
  contract/exception propagation.
- **Tests / configuration inspection** — test adequacy, missing regression
  tests, config/infra/CI changes (read as text only).
- **Existing-review reconciliation** — prior findings / settled decisions
  per [`review-evidence.md`](review-evidence.md).

## Worker output format

A compact, portable structure — no provider conversation metadata. Each
candidate finding can represent:

- affected file / location;
- concise finding;
- evidence;
- impact;
- **candidate** severity (P0 / P1 / P2);
- review dimension / source worker;
- optional related prior finding or context.

Prefer the existing finding shape
([`../templates/finding.md`](../templates/finding.md)) rendered as structured
Markdown; do not invent JSON infrastructure. "Candidate" severity is a
worker's proposal only — the aggregator owns the final severity.

## Centralized aggregation

Workers never decide independently. All results flow through one
reconciliation stage:

```text
worker findings → normalize → deduplicate → reconcile overlapping/conflicting
               → apply canonical severity semantics (severity.md)
               → derive one decision (severity.md, "Decision derivation")
```

Only this aggregator produces the final P0/P1/P2 set, `REVIEW CLEAN` /
`CHANGES REQUIRED` (local) or `Approve` / `Request Changes` (GitHub), and any
published review. **Worker completion order never affects the result.** On a
duplicate (same location, same normalized claim), the higher candidate
severity is carried and the finding is reported once.

## Failure handling — parallelism never manufactures `REVIEW CLEAN`

| Situation | Behaviour |
|---|---|
| Parallel capability unavailable | Fall back to sequential analysis of every dimension. |
| An **optional** worker failed / timed out / returned malformed output / was cancelled | The parent reviewer performs that dimension itself where feasible; the review is still graded. |
| A **required** analysis dimension could not be produced (by a worker or the parent) | Return an incomplete / ungraded state per the consuming Skill's own runbook — **never** a clean/approved result. |

Missing coverage is reported as missing, not as absence of findings.

## Boundaries

- **No new mutation.** Parallel workers are read-only; publication and any
  Approve/Request Changes stay the aggregating reviewer's, once.
- **Review target unchanged.** Splitting the review by dimension never widens
  the target or the scope — each worker is bounded to the same PR delta and
  its real blast radius.
- **Decision derivation unchanged.** The aggregator applies
  [`severity.md`](severity.md) exactly as a sequential review would.
