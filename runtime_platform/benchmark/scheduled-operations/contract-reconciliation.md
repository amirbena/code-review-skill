# Contract Reconciliation and Required Amendments

Part of the [scheduled benchmark operations decision record](decision-record.md)
(GitHub Issue [#464](https://github.com/amirbena/code-review-skill/issues/464)).
Research / design only; not packaged into either Skill archive.

The issue requires that any conflict with
[#338](https://github.com/amirbena/code-review-skill/issues/338),
[#339](https://github.com/amirbena/code-review-skill/issues/339),
[#415](https://github.com/amirbena/code-review-skill/issues/415),
[#431](https://github.com/amirbena/code-review-skill/issues/431), or
[`runtime-execution-contract.md`](../runtime-execution-contract.md) be
resolved as an **explicit, maintainer-approved amendment list**. This file is
that list. **No existing contract document, script, or issue was changed to
produce it**; the four issues are closed and are not reopened — their
canonical documents are amended by the reviewed change in F1
([`follow-up-plan.md`](follow-up-plan.md)) once a maintainer approves each
row.

## 1. Where each contract stands

| Contract | Canonical text | Kept unchanged | In conflict with this design |
| --- | --- | --- | --- |
| #338 — scheduled execution, history, baseline | [`nightly-history-and-baseline.md`](../nightly-history-and-baseline.md) | pinned-per-lane baseline policy and its ratchet rationale (§4); bootstrap-once-per-lane; non-blocking; no contributor credentials | storage keyed by date+SHA (§3.1); "newest 90" retention (§3.3); the Routine pushes the history branch under the maintainer identity (§2 step 5); `corpus_id` whole-corpus gating (§3.2) |
| #339 — drift and issue lifecycle | [`drift-detection-and-regression-lifecycle.md`](../drift-detection-and-regression-lifecycle.md) | the three drift types, tolerance, fingerprint, hidden-marker identity, `keep-open`, machine-readable metadata | resolution ignores lane coverage (§4.3, §7); a single observation is issue-worthy; drift inputs are hand-prepared files; label prerequisites absent |
| #415 — Routine vehicle | [`cloud-routine-integration.md`](../../../docs/benchmark/cloud-routine-integration.md) | modes, positive completion verification, explicit metadata, non-reachability, fail-closed | evidence is an issue-comment store and repository commits are rejected (§4); `gh` publication inside the Routine (§2, §5, §7); constant marker; ordering of `--results-out` and the post (§11) |
| #431 — two lanes | across the three documents above plus [`docs/benchmark/corpus/README.md`](../../../docs/benchmark/corpus/README.md) | sentinel = 4 fixed cases, comprehensive = derived membership, `full` = deprecated `sentinel` synonym, independent per-lane baselines, no GitHub Actions cron, collision not deduplicated | "verified" no-cross-lane lifecycle (§7 of #339's document); cadence and window wording; a comprehensive baseline that any fixture PR invalidates |
| Contract §2.2 | [`runtime-execution-contract.md`](../runtime-execution-contract.md) | Class 2 boundary, never a contributor prerequisite, Desktop tasks excluded, verify-not-trust, no Actions benchmark execution path | maintainer's own GitHub identity for execution; "Cloud Routines only" wording; pipeline order persist→evaluate→issues |
| "No GitHub Actions cron" statements | #431's acceptance criterion and non-goal; #338's non-goals; [`cloud-routine-integration.md`](../../../docs/benchmark/cloud-routine-integration.md) §8; the architecture model §6; contract §2.2 | that no Actions workflow schedules, runs, re-runs, or evaluates the benchmark, and that nothing is a contributor or merge prerequisite | read literally, they also forbid a publication-only `schedule` workflow (A13) |

## 2. Amendment list

"Blocking" means implementation of the affected follow-up must not start until
the amendment is approved.

| ID | Contract and section | Today | Proposed amendment | Class |
| --- | --- | --- | --- | --- |
| **A1** | #415 [`cloud-routine-integration.md`](../../../docs/benchmark/cloud-routine-integration.md) §4 vs #338 §3.1/§3.2 | Two contradictory stores; §4 rejects repository commits because they "bypass this repository's own PR-review workflow". | Authoritative store is a compact record on the isolated `benchmark-history` branch, written by the publication App. §4's rejection is **narrowed** to commits into reviewed branches or Skill source — the branch here is neither, which is the argument #338 §3.1 already makes. Evidence-issue comments become the human index and notification. | Blocking |
| **A2** | Contract §2.2 bullet 3; #415 §2, §5, §7 and its scope items "credential/usage bounding" and the in-Routine GitHub smoke test; #338 §2 step 5 | Execution runs under the maintainer's Claude **and GitHub** identity; the Routine posts evidence and pushes history with `gh`. | Execution keeps the maintainer's Claude account only. GitHub writes move to the `benchmark-publication` App token minted inside the publication-only workflow; no GitHub write credential is provisioned into the runtime, and repository-owned execution code performs only the seal (itself a bounded provider-mediated write). `--mode auth-check` is repurposed to smoke-test the handoff and the publisher, not `gh`. Documents the residual R1 (provider-native identity) instead of denying it. | Blocking |
| **A3** | Contract §2.2, §4.3, §7 — "Claude Cloud Routines, and only Claude Cloud Routines" | A closed choice. | **Optional.** Keep Cloud Routines as the selected default; replace "only" with an admissibility test (maintainer-controlled; not repository-event-triggered; independent of a personal machine; unchanged entrypoint; no provisioned GitHub write credential). Desktop tasks stay rejected, and so does GitHub Actions as a *benchmark* scheduler or runner (see A13 for what Actions may do). Not required for the recommended architecture. | Should |
| **A4** | #338 §3.1/§3.2 and `record_run`; #415 §4 marker | Key `<date>-<sha[:12]>`, refuses overwrite; constant evidence marker. | Identity `run_id = <lane>-<UTC start>-<sha12>`; publication keyed by `run_id`; per-run markers on GitHub objects. | Blocking |
| **A5** | #338 §3.3 | "Newest 90 entries" retention; treated as bounding storage. | Records and receipts are never pruned; growth is bounded by compaction plus a measured trigger; raw bundles are time-bounded in the handoff. The 90-entry statement is withdrawn as a size bound (E7). | Should |
| **A6** | #338 §4 (`promote-baseline`, bootstrap authority) | A local CLI edits `baseline.json`; the Routine's record step bootstraps. | Policy unchanged. Mechanism: baseline becomes a pointer file; the publisher performs only the once-per-lane bootstrap; a maintainer promotes with their own credentials under a branch-scoped ruleset bypass (M7). | Should |
| **A7** | #338 §3.2, #431's "no new guard code", [`regression-report.md`](../regression-report.md) §3, `compare()` | Any `corpus_id` mismatch is a total fail-closed refusal; the comprehensive `corpus_id` changes with any of ~106 fixtures (E14). | Lane-identity mismatch stays total fail-closed. `corpus_id` remains the whole-corpus identity; a per-case `fixture_digest` makes a fixture edit affect **only that case**, listed as `incomparable`. No baseline-policy change. This is the highest-consequence row (M4): the alternative — total block plus manual re-promotion — is operationally near-continuous given corpus churn, or blind. | Blocking |
| **A8** | #339 §1–§4; contract §2.2 pipeline diagram | Evaluation is a Routine "sync step" over hand-prepared files; the diagram orders persist → evaluate → issues; "confirmed drift" undefined. | Order becomes evaluate (with in-run confirmation) → seal → publish → issue lifecycle. The sealed record's `cases[]` feeds `classify_drift`. `sync_regressions` and the `gh` client move to the publisher and consume `drift.confirmed[]`. Classification, types, tolerance, fingerprint unchanged. | Blocking |
| **A9** | #339 §4.3 row 3 and §7; #431 acceptance criterion "#339 verified non-cross-comparing" | Any open labeled issue absent from the current drift set is closed (E13); §7 states the lifecycle is non-cross-comparing. | Resolution is scoped by lane coverage ([`drift-issue-lifecycle-and-recovery.md`](drift-issue-lifecycle-and-recovery.md) §4). #339 §7's statement is corrected: it holds for `compare()`, not for the lifecycle. | Blocking |
| **A10** | #339 §4.2–§4.3 | Labels assumed to exist; recurrence after closure unspecified. | Labels are a provisioning prerequisite with fail-closed start-up check; recurrence after closure opens a new linked issue (no reopen). | Should |
| **A11** | #431 scope wording; [`nightly-history-and-baseline.md`](../nightly-history-and-baseline.md) §2 | "Every 3 days"; "every Friday night"; 01:00 start / 04:00 maximum completion; "~89" fixtures. | (a) "Every 3 days" is not an exact cron interval (the minimum interval is one hour; under standard cron semantics a day-of-month step of 3 restarts each month, giving gaps of 1–3 days) — restate as a **maximum gap** (sentinel ≤ 96 h, comprehensive ≤ 8 d). (b) "Friday night" at 01:00 is ambiguous (early Friday versus early Saturday) — name the local weekday. (c) The 04:00 completion window is **unmeasured** against ~106 sequential invocations plus confirmation re-runs — measure before promising it (F9). (d) DST behavior is not stated in the Routines documentation beyond local-zone entry with automatic conversion — verify, do not assume. (e) Membership is currently 106, derived. | Should |
| **A12** | #415 §9 and #338 §2 prompt templates | Multi-step prompt including installs, `gh` posting, and history push. | Replaced by a thin prompt spec: fresh checkout, run the entrypoint for a named lane with the model id, exit non-zero on failure. All logic is repository code at the pinned SHA. | Should |
| **A13** | #431 acceptance criterion and non-goal ("no GitHub Actions cron"); #338 non-goals; [`cloud-routine-integration.md`](../../../docs/benchmark/cloud-routine-integration.md) §8; the architecture model §6 ("not reachable from GitHub Actions cron"); contract §2.2 (no independent Actions benchmark path) | Written about benchmark scheduling and execution, but phrased as blanket Actions-cron prohibitions. | State the actual invariant: **no Actions workflow schedules, runs, re-runs, or evaluates the benchmark, and none is a contributor or merge prerequisite.** A publication-only workflow (`schedule` sweep and watchdog, manual `workflow_dispatch`), which reads sealed records and touches no model, is permitted and is a different thing. Enforced by a policy test on the workflow's triggers, credentials, and imports ([`publication-architecture.md`](publication-architecture.md) §5). Approval of A13 is what allows F8. | Blocking |

## 3. Explicitly unchanged

The matcher and metrics (#54–#57); #339's drift types, tolerance and
fingerprint; the baseline **policy** (pinned per lane, refreshed only by
explicit maintainer action, once-per-lane bootstrap); the sentinel and
comprehensive corpus definitions and `full` = deprecated `sentinel`;
PR-time Top-K selection ([#333](https://github.com/amirbena/code-review-skill/issues/333)/[#334](https://github.com/amirbena/code-review-skill/issues/334));
the non-blocking, never-a-merge-prerequisite rule; the retirement of the
Actions benchmark path ([#420](https://github.com/amirbena/code-review-skill/issues/420));
Class 1 remaining unprovisioned; collision between the two lanes remaining
un-deduplicated.

## 4. Consistent as found

- Verification never trusts a "green" Routine status
  ([`benchmark_routine_verify.py`](../scripts/benchmark_routine_verify.py)); this
  record adds no weaker path.
- `canonical_lane` already makes `full` record as `sentinel`, so the lane is
  never ambiguous in a record.
- Sentinel and comprehensive `corpus_id` values are distinct by construction,
  which keeps `compare()` from cross-comparing lanes; only the lifecycle (A9)
  and the comprehensive staleness (A7) needed attention.
- #182 telemetry is scoped per review and is not coupled to this cadence
  (#431's own recorded finding); nothing here reopens that.

## 5. How amendments land

1. A maintainer approves, rejects, or edits each row on #464, recording the
   decision (the M-questions in [`decision-record.md`](decision-record.md) §4
   feed the same review).
2. F1 lands the approved rows as a docs-only change to the canonical documents,
   with the required documentation-impact check
   ([`../../../policies/documentation-policy.md`](../../../policies/documentation-policy.md)).
3. Implementation issues cite the amended documents, not this record.
