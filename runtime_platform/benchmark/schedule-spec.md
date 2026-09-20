# Scheduled Benchmark Schedule Spec

The repository-owned half of the scheduled sentinel/comprehensive benchmark
operation ([#469](https://github.com/amirbena/code-review-skill/issues/469),
parent [#466](https://github.com/amirbena/code-review-skill/issues/466)): the
**expected-run manifest**, the **thin Routine prompt spec**, and the **label
set**. It implements the repository-owned column of
[`scheduled-operations/execution-publication-boundary.md`](scheduled-operations/execution-publication-boundary.md)
§3 under the landed amendments A10–A12
([`scheduled-operations/contract-reconciliation.md`](scheduled-operations/contract-reconciliation.md)).

Repository-development contract; not packaged into either Skill archive. It
defines *what is expected*; it registers nothing and runs nothing — the
Routine, App, and labels are provisioned by
[#473](https://github.com/amirbena/code-review-skill/issues/473) /
[#475](https://github.com/amirbena/code-review-skill/issues/475), execution is
[#470](https://github.com/amirbena/code-review-skill/issues/470), and
publication is [#471](https://github.com/amirbena/code-review-skill/issues/471).

## 1. Expected-run manifest

[`schedule/expected-run-manifest.json`](schedule/expected-run-manifest.json)
is versioned (`schema: benchmark-schedule/v1`) and closed (an unknown or missing
field is invalid). It is the single source of these values for the execution
entrypoint ([#470](https://github.com/amirbena/code-review-skill/issues/470)),
the publisher and watchdog
([#471](https://github.com/amirbena/code-review-skill/issues/471),
[#472](https://github.com/amirbena/code-review-skill/issues/472)), and CI
validation ([#476](https://github.com/amirbena/code-review-skill/issues/476)),
none of which read it yet. It is validated by
[`scripts/benchmark_schedule_manifest.py`](scripts/benchmark_schedule_manifest.py),
which is the executable schema.

| Field | Meaning |
| --- | --- |
| `repository`, `entrypoint` | The repository the Routine checks out and the entrypoint it invokes ([`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md) §2). |
| `lanes.<lane>.mode` | The `--mode` for the lane; must equal the lane name (`sentinel`, `comprehensive`). The deprecated `full` alias is never scheduled. |
| `lanes.<lane>.intended_cadence` | Cadence as **text** (A11). Never an exact interval and never enforced. |
| `lanes.<lane>.intended_start` | Declarative local start: `weekday` (comprehensive only; `null` for sentinel), `local_time`, `timezone`. **No repository code computes with it** — timezone and DST stay a Routine-configuration responsibility, and the watchdog is gap-based. |
| `lanes.<lane>.target_completion_local` | The 04:00 completion target. A target, not a promise: it is measured in [#475](https://github.com/amirbena/code-review-skill/issues/475) before being relied on. |
| `lanes.<lane>.max_gap_hours` | The **enforced** cadence contract: the longest tolerated gap between verified scheduled runs. Sentinel ≤ 96, comprehensive ≤ 192 (A11). The validator rejects a larger value. |
| `lanes.<lane>.tracking_issue`, `health_issue` | Per-lane evidence tracking issue and the health-status issue. `null` until provisioned (§4). |
| `confirmation` | In-run drift confirmation ([`scheduled-operations/drift-issue-lifecycle-and-recovery.md`](scheduled-operations/drift-issue-lifecycle-and-recovery.md) §2): `reruns`, `threshold` (≥ 2 and ≤ `1 + reruns`), and `max_cases`; the recommended values (decision M3) are the manifest's. The run's time budget is not fixed here; it is measured in #475. |
| `publication.staging_ref_pattern` | The handoff refs the publisher sweeps; must start with `claude/benchmark-result-`, never a wider `claude/` pattern. |
| `publication.pusher_allowlist` | GitHub logins accepted by origin attestation (`branch_creation` actor; commit author metadata is never used). |
| `publication.max_new_issues_per_run` | Spam bound on new drift issues opened per published run. |
| `watchdog.missed_run_comment_interval_hours` | A persisting missed-run issue is commented at most this often. |
| `labels` | The four labels of §3. |

The comprehensive lane's Israel-local start weekday is **Friday, 01:00
`Asia/Jerusalem`** — the early hours of Friday, not Friday night — as A11(b)
requires. Changing it is a manifest edit plus the matching Routine
reconfiguration; `max_gap_hours` is what the repository enforces either way.

Membership of the comprehensive lane is derived from the corpus, never listed
here.

### Validation

```bash
python3 runtime_platform/benchmark/scripts/benchmark_schedule_manifest.py validate
```

`validate_manifest(..., require_provisioned=True)` (CLI
`--require-provisioned`) additionally rejects a `null` tracking or health
issue. The publisher and watchdog are to use it at start-up so they fail closed
before any GitHub write; the default mode is for CI and the execution side.

## 2. Thin Routine prompt spec

The Routine prompt is exactly the literal template in
[`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md)
§9 (A12), bound per lane to the manifest:

- `--mode` is the lane's `mode`;
- `--trigger scheduled` marks the run as scheduled, so it counts toward the
  lane's cadence (a run started without it is recorded as `manual`);
- `--model-id` is the model backend the Routine session runs as (the only value
  the repository cannot know; it is recorded as declared in `runtime.model_id`);
- the checkout is a fresh copy of `repository` at its default branch.

The prompt does three things and nothing else: check out, invoke the
entrypoint for the named lane, and stop if the command fails. A Routine session
realises A12's "exit non-zero on failure" as the template's step 3: on a
non-zero exit it reports no success, does not retry silently, and posts or
pushes nothing to GitHub — a run that did not seal is not a verified run. It
carries no dependency installs, no `gh`, no history push, no evidence posting,
and no cadence, tracking-issue, confirmation, or label values — those live in
the manifest, and all logic is repository code at the pinned SHA, so provider-side
prompt drift cannot change behavior. The Routine definition itself, its
enabled state, schedule, and stagger are provider-owned and cannot be checked
from the repository.

## 3. Labels

The manifest's `labels` array is the definition; **creation is a provisioning
step** ([#473](https://github.com/amirbena/code-review-skill/issues/473)), never
runtime behavior. The publisher has no label-creation capability and fails
closed at start-up if one is missing (A10).

| Role | Name | Applied to | Applied by |
| --- | --- | --- | --- |
| `drift` | `benchmark-regression` | drift issues (one per fingerprint) | publisher |
| `keep-open` | `keep-open` | a drift issue a maintainer wants kept open | users with triage rights; only ever *prevents* a close |
| `missed-run` | `benchmark-missed-run` | the per-lane missed-run issue | watchdog |
| `tracking` | `benchmark-tracking` | per-lane evidence tracking issues and the health issue | maintainer, at provisioning |

`benchmark-regression` and `keep-open` are the names
[`scripts/benchmark_drift.py`](scripts/benchmark_drift.py) already uses
(`REGRESSION_LABEL`, `KEEP_OPEN_LABEL`); a test keeps the manifest in step with
them.

## 4. Provisioning state

`tracking_issue` and `health_issue` were `null` until the #473 runbook, executed
under #484, created those issues. The provisioning-evidence change filled the
numbers in (sentinel #486, comprehensive #487, health #488) and is the only edit
expected to change them; consumers that write to GitHub must use
`--require-provisioned` semantics.

## 5. What this spec does not own

The seal and handoff, drift evaluation, publication, and the watchdog's
behavior are owned by their own documents
([`scheduled-operations/`](scheduled-operations/README.md)); the modes and
verification are [`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md);
the baseline policy is [`nightly-history-and-baseline.md`](nightly-history-and-baseline.md).
This document owns only the values and shapes above.
