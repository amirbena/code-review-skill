# Scheduled Benchmark Operations

Navigation for the decision record of GitHub Issue
[#464](https://github.com/amirbena/code-review-skill/issues/464) (parent
[#332](https://github.com/amirbena/code-review-skill/issues/332)): the
production operating architecture that connects the scheduled benchmark's
existing parts — the Cloud Routine vehicle, per-lane history and baselines,
and the drift/issue lifecycle.

Like the rest of [`../`](../README.md), this is a **repository-development
record, not packaged into either Skill archive**. **Status: research / design
only — nothing here is implemented**, and no existing contract was edited;
required changes are proposed as amendments.

The architecture in one line: the benchmark is scheduled and executed
**outside GitHub** (never GitHub Actions); once a sealed canonical result
exists, a publication-only GitHub App persists it and manages issues.

## Document map

| Document | Owns |
| --- | --- |
| [`decision-record.md`](decision-record.md) | The constraint, the re-checkable current-state evidence, decisions D1–D9 with rejected alternatives, and the maintainer questions M1–M8. **Start here.** |
| [`execution-publication-boundary.md`](execution-publication-boundary.md) | Where execution ends and publication begins: scheduler adapter, provisioning split, the seal/handoff, the publisher, the `benchmark-publication` App, permission matrix, credential path, closed capability set, contributor reachability, and the GitHub Actions role. |
| [`canonical-result-and-persistence.md`](canonical-result-and-persistence.md) | The canonical run record (every field), the persistence options compared, the `benchmark-history` layout, retention, growth bound, and baseline access. |
| [`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md) | What is issue-worthy, in-run confirmation, dedup/idempotency, scope-aware resolution, spam bounds, the missed-run watchdog, the failure table, and the maintainer health checklist. |
| [`contract-reconciliation.md`](contract-reconciliation.md) | How #338, #339, #415, #431, and `runtime-execution-contract.md` §2.2 are reconciled, and the amendment list A1–A12 awaiting maintainer approval. |
| [`follow-up-plan.md`](follow-up-plan.md) | The listed (not created) follow-up issues F1–F12 (plus three conditional ones), their order and ownership class, and the documentation work for both surfaces: the canonical repository specification and the GitHub Wiki page. |

The existing contracts this record builds on and proposes to amend are
[`../runtime-execution-contract.md`](../runtime-execution-contract.md),
[`../nightly-history-and-baseline.md`](../nightly-history-and-baseline.md),
[`../drift-detection-and-regression-lifecycle.md`](../drift-detection-and-regression-lifecycle.md),
[`../../../docs/benchmark/cloud-routine-integration.md`](../../../docs/benchmark/cloud-routine-integration.md),
and the cross-component architecture in
[`../../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../../../docs/benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§6.
