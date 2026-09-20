# Sealed Benchmark Result Schema (`benchmark-result/v1`)

Repository-development contract for GitHub Issue
[#468](https://github.com/amirbena/code-review-skill/issues/468) (F2 of Epic
[#466](https://github.com/amirbena/code-review-skill/issues/466); design record
[#464](https://github.com/amirbena/code-review-skill/issues/464)). Like the rest of
[`./`](README.md) it is **not packaged into either Skill archive**.

It fixes the exact machine-readable shape of one sealed scheduled-run record and
its publisher receipt. The field table and rationale live in
[`scheduled-operations/canonical-result-and-persistence.md`](scheduled-operations/canonical-result-and-persistence.md)
§1; the amended storage contract is
[`nightly-history-and-baseline.md`](nightly-history-and-baseline.md) §3. This
document owns only the shape, identity, and conformance rules.

| Artifact | Owns |
| --- | --- |
| [`schemas/benchmark-result-v1.schema.json`](schemas/benchmark-result-v1.schema.json) | The sealed record's fields (JSON Schema draft-07). The single source for shape. |
| [`schemas/benchmark-receipt-v1.schema.json`](schemas/benchmark-receipt-v1.schema.json) | The publisher receipt (`benchmark-receipt/v1`). |
| [`scripts/benchmark_result.py`](scripts/benchmark_result.py) | Canonical hashing, `run_id`, sealing, per-case comparability, and the validator (`validate` CLI). |
| [`schemas/examples/`](schemas/examples/) | Reference fixtures: a bootstrap record, a compared record with confirmed and unconfirmed drift and one incomparable case, and its receipt. |

## 1. Identity and sealing (A4)

- `run_id = <lane>-<YYYYMMDDTHHMMSSZ>-<repo_sha[:12]>` from the run's UTC start
  time, so two runs of one lane on one SHA and day are distinct. It is the
  publication idempotency key.
- `content_sha256` is the SHA-256 of the canonical-JSON sealed body — the record
  **without** `content_sha256` itself. Canonical JSON is sorted keys and minimal
  separators, identical to the fingerprint canonicalization in
  [`drift-detection-and-regression-lifecycle.md`](drift-detection-and-regression-lifecycle.md)
  §3; a test pins the two together.
- A sealed record is never edited. Any change without resealing fails validation.

## 2. Field decisions

The field table names groups; these are the exact shapes it left open.

- `lane` is `canonical_lane(mode)`; `mode` is as invoked, so the deprecated `full`
  is recorded as `mode: full`, `lane: sentinel`.
- `corpus.membership_digest` is the SHA-256 of the canonical JSON of the lane's
  sorted case ids; `corpus.case_count` equals `len(cases)`.
- `cases[].fixture_digest` is the SHA-256 of the fixture file's bytes — the digest
  `corpus_id` is already built from. `cases[]` carries the `as_dict()` fields of
  the #55/#56/#57 per-case objects with `id` and `status` lifted to the case.
- `drift.confirmation` uses the parameter names of
  [`scheduled-operations/drift-issue-lifecycle-and-recovery.md`](scheduled-operations/drift-issue-lifecycle-and-recovery.md)
  §2: `reruns`, `threshold`, `max_cases`; `drift.systemic` records the cap being hit.
- `drift.observations[]`, `confirmed[]`, `unconfirmed[]` use the `DriftRecord`
  shape including `fingerprint`, closed to unknown fields; `confirmed` and `unconfirmed` partition
  `observations`. Each `unconfirmed` entry adds a `reason`:
  `not-reproduced`, `unconfirmed-timeout`, or `systemic-cap`.
- `drift.outcome` is `{status: none | drift | not-evaluated, reason}`; `reason` is
  required exactly for `not-evaluated`. `drift.attribution` is `none` or
  `runtime-changed`.
- `drift.evidence` maps a **confirmed** case id to a raw excerpt of at most
  32 KiB (UTF-8 bytes).
- `baseline.incomparable_cases[]` entries carry `id`, `reason:
  fixture-digest-mismatch`, and both digests.
- `provenance.spec_sha256` is the SHA-256 of the canonical JSON of the expected-run
  manifest and the SHA-256 of the literal Routine prompt template block
  ([`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md)
  §9), so edits elsewhere in that document do not change it.
- Only verified runs are sealed: `verification.overall_verified` must be `true`.

## 3. Conformance

`validate_record` runs the schema, then the cross-field rules a schema cannot
express, and reports every error:

- `content_sha256`, `run_id`, and the lane/mode relation recompute correctly;
  timestamps satisfy `started_at <= finished_at <= sealed_at`.
- Case ids are unique; `corpus.case_count` and `membership_digest` match them.
- `baseline.state` `bootstrap` and `incomparable` carry no baseline reference or
  case partition and force `drift.outcome.status` `not-evaluated`; `compared`
  requires `baseline.run_id` and `record_sha256`.
- `drift.evaluated_scope` lies within `baseline.comparable_case_ids`; every drift
  fingerprint recomputes from its `{case_id, drift_type, expected_finding_key}`
  triple and lies in scope; `drift.outcome.status` agrees with `confirmed`.

Aggregates and per-case projections are stored verbatim; the validator checks their
shape, never recomputes them.

## 4. Per-case comparability (A7)

`partition_case_comparability(candidate_cases, baseline_cases)` splits one lane's
cases by `fixture_digest`. A digest mismatch makes **only that case**
`incomparable`; cases present on one side only are reported as added or removed
and never block the rest. Lane-identity mismatch remains a total fail-closed
refusal ([`regression-report.md`](regression-report.md) §3). The execution
entrypoint applies the partition when evaluating drift
([#470](https://github.com/amirbena/code-review-skill/issues/470),
[`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md)
§2.2).

## 5. First record-size measurement

Measured with the test-only
[`reference/benchmark_result_reference.py`](reference/benchmark_result_reference.py)
`measure` command on the corpus at `main` 8c4746f: every case executed by a
reviewer that reports nothing, scored by the real #55/#56/#57 reference code, with
each fixture's real digest.

| Lane | Cases | Canonical | Pretty (as stored) | Mean / largest case |
| --- | --- | --- | --- | --- |
| sentinel | 4 | 5,165 B | 7,079 B | 623 B / 638 B |
| comprehensive | 108 | 84,856 B | 120,087 B | 657 B / 742 B |

Against the §4 assumptions of
[`canonical-result-and-persistence.md`](scheduled-operations/canonical-result-and-persistence.md):

- Per-case size (0.5–1 KB) holds. Comprehensive (est. 50–110 KB) is 85 KB
  canonical, 120 KB pretty; sentinel (est. 2–4 KB) is 5–7 KB because a fixed
  ≈ 2.5 KB of per-record blocks dominates four cases. Both are slightly above
  the estimate as stored, and immaterial to the trigger.
- A year at 130 sentinel and 52 comprehensive runs is ≈ 7.2 MB uncompressed
  (estimate ≈ 6 MB), far below the 100 MB packed-size trigger; no single file is
  near 10 MB.
- The 32 KiB evidence cap, not the metrics, is the worst case: up to 10 cases per
  comprehensive record (4 per sentinel) adds ≈ 320 KiB (128 KiB), giving ≈ 41 MB a
  year if every run confirmed maximal drift. Still under the trigger, so the
  trigger is unchanged.

**Limits.** This is a real corpus and real metric code, not a model run: real
findings add severity `mismatches` and duplicate `cluster_members`, so real cases
are larger than the silent-run floor above. The first verified scheduled runs
([#475](https://github.com/amirbena/code-review-skill/issues/475), F9 in
[`scheduled-operations/follow-up-plan.md`](scheduled-operations/follow-up-plan.md))
must re-measure before the trigger is relied on.

## 6. Non-goals

Executing the benchmark and evaluating drift are
[#470](https://github.com/amirbena/code-review-skill/issues/470); persisting
records to `benchmark-history` and the publisher CLI are
[#471](https://github.com/amirbena/code-review-skill/issues/471)
([`publication-cli.md`](publication-cli.md)). This change adds
no workflow, and no packaged Skill resource depends on it.
