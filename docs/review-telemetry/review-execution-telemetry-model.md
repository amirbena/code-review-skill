# Review Execution Telemetry Model

Repository-development design record for
**[#182](https://github.com/amirbena/code-review-skill/issues/182)**. Not
packaged; explanatory. It is the canonical home for the observational
review-execution telemetry record: the metric catalog and its rationale,
the explicit "not collected" list, the never-decision-affecting guarantee,
the per-metric unavailable-state rules, the JSON Schema, and the boundary
with [#131](https://github.com/amirbena/code-review-skill/issues/131).

Cross-component architecture — the dependency DAG, the nine layers, and
why telemetry (#182) is deliberately upstream of and separate from
analytics (#131) and the benchmark tree (#329) — is owned by
[`../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md),
§3 ("Review execution telemetry" layer row) and §7 (the four boundary
bullets). This document does not restate that architecture; it only
implements the one layer #182 owns.

The test-only reference model is
[`../../tests/reference/review/review_telemetry.py`](../../tests/reference/review/review_telemetry.py);
its examples and mutation checks are exercised by
[`../../tests/unit/review/observability/test_review_telemetry.py`](../../tests/unit/review/observability/test_review_telemetry.py)
and this document's own prose is pinned by
[`../../tests/policy/review/test_review_telemetry_docs.py`](../../tests/policy/review/test_review_telemetry_docs.py).
The machine-readable shape lives in its own file,
[`review-execution-telemetry.schema.json`](review-execution-telemetry.schema.json)
(JSON Schema draft-07) — this document explains it; the schema file is the
single source of truth for the exact field list, so neither restates the
other's detail.

## 1. Problem and goal

Nothing today records what a review actually looked at. A reader of a
finished review has no way to tell whether it inspected three files or
three hundred, whether repository-intelligence expansion ever fired,
whether a runtime validation ran or was skipped, or whether a large PR was
partitioned. That gap makes it impossible to answer purely descriptive
questions ("how much of the diff did this review actually touch?") without
re-deriving them by hand from a review's prose output.

The goal is a small, machine-readable, **purely observational** record of
what one review run inspected and executed — nothing about whether the
review reached the right conclusion (that is the benchmark tree's job,
§7 of the architecture doc), and nothing that feeds back into the review
that produced it.

## 2. The never-decision-affecting guarantee

**Guarantee.** The review execution telemetry record has no effect,
direct or indirect, on a review's findings, a finding's severity or
confidence, finding suppression, or the review's decision. No canonical
policy's severity, evidence, confidence, or decision derivation
(`shared/policies/severity.md`, `shared/policies/evidence.md`,
`shared/templates/finding.md`'s `confidence` field, or
`shared/policies/review-stopping-criteria.md`'s coverage/decision
override) reads a telemetry field as input, and the telemetry record is
never attached to, embedded in, or referenced from a `Finding` value.
Telemetry is assembled *from* the same observations a review already
makes while it runs; it never reaches back *into* the reasoning that
produced those observations.

This is backed by a test, not only by this sentence:
[`test_decision_identical_with_and_without_telemetry`](../../tests/unit/review/observability/test_review_telemetry.py)
constructs the same finding set twice against the existing decision
contract (`tests/reference/review/decision_semantics.py`, Issue #37's
mechanical `derive_decision`), once with a populated telemetry record
attached via the reference module's `decide_with_telemetry` helper and
once with no telemetry at all, and asserts the two decisions and rendered
finding sets are identical. `decide_with_telemetry` takes a telemetry
value only to prove, by construction, that its own signature has no path
from that parameter into `derive_decision`'s input — the same technique
`tests/reference/review/decision_semantics.py`'s
`PROHIBITED_OVERRIDE_PARAM_FRAGMENTS` guards for that module.

This is a **deliberately different model** from the *decision-affecting*
coverage concept `shared/policies/review-stopping-criteria.md` already
defines (its `coverage: complete | incomplete` can override a review's
top-level outcome to `REVIEW INCOMPLETE`). Telemetry's `stages_completed`
field is descriptive only — a review with every stage present in
`stages_completed` can still be behaviorally wrong, and a review that
omits a stage from `stages_completed` is not thereby marked incomplete;
only `review-stopping-criteria.md`'s own coverage computation does that,
through its own mechanism, unchanged by this document. See
`shared/policies/review-stopping-criteria.md`, "Relationship to review
execution telemetry (#182)" for the pointer the other direction.

## 3. Metric catalog

Each metric answers one concrete "what did the review touch" question.
None is collected merely because a runtime happens to expose it — see §4
for the rejected list.

| Metric | Field(s) | Rationale | Unavailable state |
| --- | --- | --- | --- |
| **Stages completed** | `stages_completed` | Names, from a fixed catalog, which of this repository's always-on/conditional review passes actually reached their own defined stop condition during this run — the same passes `review-stopping-criteria.md` already enumerates by depth. Without this, a reader cannot tell "repository-expansion never fired because no trigger existed" from "repository-expansion never ran." | A stage's own name is simply absent from the array; there is no separate null/boolean per stage. An empty array is valid and means no listed stage completed. |
| **Files inspected** | `files_inspected` | The concrete set of files a review actually read, independent of which were part of the original diff — this is the rawest, most direct "what did it touch" signal and the one most reviewers intuitively ask for first. | `null` when file-level inspection was not tracked for the run. `[]` means tracking ran and zero files were read (a genuinely empty/trivial diff). |
| **Symbols expanded** | `symbols_expanded_count` | How many bounded-context symbol expansions (`review-scope.md`'s caller/callee ladder) the review performed — a proxy for how far it looked beyond the literal diff lines. A count, not a list, because symbol identity is not stably serializable across languages the way a file path is. | `null` when symbol-expansion tracking was not available for the run. `0` means tracking ran and no expansion occurred. |
| **Repository-intelligence expansions** | `repository_intelligence_expansions.{call_site,interface_contract,migration_schema,config_consumer}` | Per-trigger counts mirroring `repository-expansion.md`'s fixed, closed trigger catalog (Issue #87) — lets a reader see *which kind* of expansion fired, not just that expansion happened at all. | The whole object is `null` when the `repository_expansion` stage is absent from `stages_completed`. When present, an individual trigger is `0` if it was evaluated and did not fire; a trigger is `null` only if that trigger concept does not apply to the run's language/ecosystem at all. |
| **Runtime validations executed** | `runtime_validations[].{outcome,provenance}` | How many `runtime-validation.md` (Issue #128) executions the review attempted, each one's `executed`/`failed`/`skipped`/`unavailable` outcome, and its `sandbox`/`trusted_host` execution provenance — the same values that policy already defines, restated here as a count-and-list rather than re-derived. | `null` when the `runtime_validation` stage is absent from `stages_completed` (validation was never applicable/attempted). `[]` means the stage ran and attempted zero executions. |
| **Partitions used** | `partitions.{partition_count,partition_ids}` | Whether `large-pr-partitioning.md` (Issue #88) activated for this review and, if so, how many coherent review units it split the diff into — a large-PR review's "how was this actually organized" signal. | `null` when partitioning did not activate (diff under its size threshold, or the `large_pr_partitioning` stage absent from `stages_completed`). There is no empty/zero-partition state: partitioning is either inactive (`null`) or active with at least one partition. |
| **Deterministic stage timing** | `stage_timing_ms{stage_name: ms}` | Wall-clock duration per completed stage, in milliseconds, **where the runtime can measure it deterministically** — explicitly best-effort, never a performance SLA or a benchmark latency claim (the benchmark tree owns latency-as-quality-signal questions, if any, separately). | `null` at the record level when no runtime exposed stage timing at all for the run. When present, an individual stage's timing may itself be `null` if that one stage's duration could not be measured, independent of whether the stage completed (a stage can appear in `stages_completed` with a `null` timing entry). |

## 4. Explicitly not collected

Rejected because they would be collected only because a runtime happens
to expose them, not because they answer an observational "what did the
review touch" question, or because collecting them would blur telemetry
into a different, already-owned concern:

- **Model token usage, latency-as-cost, or dollar cost.** Measurable from
  most runtimes, but this is a cost/operations concern, not a review-scope
  observation, and has no owning capability in this issue's scope.
- **Prompt or response text, or any model reasoning trace.** Would turn an
  observational record into a transcript-retention surface with its own
  privacy and storage-cost implications, well outside "what was
  inspected."
- **Finding counts, severities, or the decision itself.** This is exactly
  the boundary §2 exists to hold — restating decision output inside the
  telemetry record would immediately invite reading telemetry as if it
  explained or justified the decision, which it must never do. A reader
  who wants findings/decision reads the review's own output, not
  telemetry.
- **Reviewer/author/committer identity, or any other PII.** Telemetry
  describes *what a run did*, not *who ran it* or *whose code it was*;
  identity has no observational value for this record's purpose and would
  create a data-handling obligation this design does not take on.
- **Repository name, URL, or any other externally-identifying
  string.** Same rationale as identity — not needed to answer "what did
  this run inspect," and copying it in would make the record double as an
  inventory of which repositories use these Skills, a different (and
  unowned) concern.
- **Benchmark match/fidelity outcomes (whether a finding was "correct").**
  Owned entirely by `docs/benchmark/match-criteria.md` and the benchmark
  tree (§7's "benchmark ground truth" row) — mixing it into telemetry
  would repeat exactly the "telemetry ≠ benchmark ground truth" conflation
  §7 of the architecture doc warns against.
- **Aggregated/historical trend data across multiple reviews.** One
  telemetry record describes exactly one review run. Aggregation across
  runs is #131's (analytics) job, once it exists — see §5.

## 5. Boundary with #131 (outcome analytics — not implemented here)

[#131](https://github.com/amirbena/code-review-skill/issues/131) is open
and **not implemented by this issue**. The boundary, restated from the
architecture doc's §3/§7 so this document is self-contained:

- **#182 (this document) is the observational raw signal**: one record per
  review run, produced as a byproduct of that run, describing only what
  happened during it. It has no notion of "across reviews," "over time,"
  or "quality."
- **#131 (future) is the aggregation/analytics consumer**: it would read
  many #182 records (plus, separately, benchmark-derived ground truth from
  #329's tree once trustworthy) and report a consolidated,
  denominator-defined view of workflow-observation metrics over time. #131
  does not exist yet in this repository — no aggregation, export, storage,
  or dashboard for telemetry records is built by this change, and this
  document does not specify #131's shape.
- **The direction of dependency is fixed**: #131 depends on #182 existing
  first (the architecture doc's DAG, §2), never the other way around.
  Nothing in this document or its reference model imports, calls, or
  assumes anything from a future #131 implementation.
- **Neither may read as the other.** A single telemetry record is not an
  analytics report, and an analytics report (once #131 exists) must not
  claim to be raw per-review telemetry — the same non-substitution rule
  §7 of the architecture doc states for telemetry versus benchmark ground
  truth applies here between telemetry and its own future aggregation.

## 6. Partial runs produce valid output

A review that never reaches every possible stage (a `standard`-depth
change that never triggers `repository_expansion` or
`large_pr_partitioning`; a review with no eligible runtime-validation
target) still produces a **fully schema-valid** telemetry record: the
unavailable stage's own fields resolve to `null` per §3's per-metric
rules, and `stages_completed` simply omits that stage's name. The schema
never requires a field to be non-null, and never requires a stage's
absence from `stages_completed` to force any other field to a particular
value — each field's own unavailable-state rule is independent, so no
combination of ran/did-not-run stages can produce an invalid record.
[`review-execution-telemetry.schema.json`](review-execution-telemetry.schema.json)
marks only `schema_version`, `review_id`, `generated_at`, and
`stages_completed` as `required`; every metric field is optional or
nullable.

## 7. Worked examples

Two examples, both schema-valid, both exercised by
`tests/unit/review/observability/test_review_telemetry.py`:

**Example A — a `standard`-depth review, no expansion or partitioning
triggered, one runtime validation executed.**

```json
{
  "schema_version": "1.0.0",
  "review_id": "local-2026-09-17-0001",
  "generated_at": "2026-09-17T09:15:00Z",
  "stages_completed": [
    "scope_normalization",
    "change_risk_classification",
    "repository_expansion",
    "runtime_validation",
    "stopping_criteria"
  ],
  "files_inspected": ["src/pay/retry.py", "tests/unit/pay/test_retry.py"],
  "symbols_expanded_count": 2,
  "repository_intelligence_expansions": {
    "call_site": 0,
    "interface_contract": 0,
    "migration_schema": 0,
    "config_consumer": 0
  },
  "runtime_validations": [
    { "outcome": "executed", "provenance": "sandbox" }
  ],
  "partitions": null,
  "stage_timing_ms": {
    "scope_normalization": 120.0,
    "change_risk_classification": 40.0,
    "repository_expansion": 310.0,
    "runtime_validation": 2100.0,
    "stopping_criteria": 15.0
  }
}
```

**Example B — a partial run: a very small diff where nothing beyond
initial scope work ran (repository-expansion and runtime-validation never
became applicable), and stage timing was never captured by this
runtime.**

```json
{
  "schema_version": "1.0.0",
  "review_id": "local-2026-09-17-0002",
  "generated_at": "2026-09-17T09:20:00Z",
  "stages_completed": ["scope_normalization", "change_risk_classification", "stopping_criteria"],
  "files_inspected": ["README.md"],
  "symbols_expanded_count": 0,
  "repository_intelligence_expansions": null,
  "runtime_validations": null,
  "partitions": null,
  "stage_timing_ms": null
}
```

## 8. Smallest useful first implementation

1. **This model** — the metric catalog with rationale (§3), the
   not-collected list (§4), the never-decision-affecting guarantee backed
   by a test (§2), the availability/unavailable-state rules (§3, §6), the
   #131 boundary (§5), and worked examples (§7) — plus the JSON Schema
   ([`review-execution-telemetry.schema.json`](review-execution-telemetry.schema.json)).
2. **A test-only reference model**
   (`tests/reference/review/review_telemetry.py`) implementing the record
   shape, its per-field unavailable-state defaults, a small hand-rolled
   schema validator (`validate_against_schema`) so the worked examples and
   any future record are checked against the same schema file rather than
   a re-derived copy, and the `decide_with_telemetry` construction the
   guarantee test (§2) uses.
3. **No runtime emission wiring is added by this change.** Nothing in
   either Skill's `SKILL.md` or packaged `policies/` is changed — a
   review still runs exactly as it does today. Actually assembling a real
   telemetry record from a live review run (reading `stages_completed`
   off the review's own pass results, counting inspected files as they
   happen, etc.) is deferred to a future, separately-scoped runtime-wiring
   change, once a concrete need to consume it (e.g. #131, or the
   citation-grounding cross-check named in the architecture doc's §12.2)
   makes the wiring point concrete rather than speculative.

**Deferred** (named here so scope stays fixed): any #131 aggregation,
export, or dashboard; any runtime code path that actually populates a
telemetry record during a live review; any packaged Skill/policy change.
