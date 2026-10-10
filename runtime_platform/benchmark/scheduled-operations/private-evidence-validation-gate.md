# Private Evidence Validation Gate

Compatibility and validation gate for GitHub Issue
[#689](https://github.com/amirbena/code-review-skill/issues/689) (epic
[#686](https://github.com/amirbena/code-review-skill/issues/686)). It validates the
destination contract that #688 implemented against the invariants of the
[private evidence repository ADR](private-evidence-repository.md), and it is a **precondition
of the cutover** owned by [#690](https://github.com/amirbena/code-review-skill/issues/690)
(ADR §10, step 0). Like the rest of [`./`](README.md), this is a repository-development record,
not packaged into either Skill archive.

**Status: the gate passes for everything #689 can validate; two items are carried to #690 as
open preconditions (G-open-1, G-open-2).** Nothing here creates, reads or writes a real private
repository, calls a model or activates a Routine: every check runs against stub bare
repositories, scripted GitHub responses and the in-memory publisher world.

Re-run the gate:

```bash
python3 -m unittest tests.unit.benchmark.test_private_evidence_gate \
  tests.unit.benchmark.test_benchmark_evidence_destination \
  tests.unit.benchmark.test_benchmark_publisher_evidence_destination \
  tests.policy.benchmark.test_evidence_destination_wiring \
  tests.policy.benchmark.test_benchmark_publish_workflow \
  tests.policy.benchmark.test_private_evidence_gate_docs
```

The affected suites (`tests.unit.benchmark` as a whole) must also pass; the gate adds no
exemption to any of them.

## 1. Scenario coverage (issue #689 scope)

Test references are `file::test_name`; the docs test checks that each one exists.

| Scenario | Evidence |
| --- | --- |
| Successful private publication | `test_benchmark_evidence_destination.py::test_auth_check_to_a_proven_private_remote_seals_only_there`; `test_private_evidence_gate.py::test_sweep_and_watchdog_run_over_the_private_phase_manifest` |
| Private reads and ref discovery | `test_private_evidence_gate.py::test_private_reads_and_ref_discovery_see_only_the_private_store`; `test_benchmark_evidence_destination.py::test_baseline_history_is_read_from_the_destination_branch` |
| Duplicate-run prevention | `test_private_evidence_gate.py::test_duplicate_run_prevention_end_to_end_skips_on_a_private_observation`; `test_private_evidence_gate.py::test_f7_the_severity_stop_condition_counts_the_private_store_only`; `test_private_evidence_gate.py::test_f7_the_experiment_stop_condition_counts_the_private_store_only` |
| Idempotent retries | `test_private_evidence_gate.py::test_i1_a_retry_of_a_sealed_ref_is_refused_and_the_first_seal_stays_intact`; `test_private_evidence_gate.py::test_f4a_an_unconfirmed_push_leaves_one_ref_in_the_private_store_and_a_retry_cannot_double_it`; `test_private_evidence_gate.py::test_i2_publishing_the_same_run_again_is_a_no_op` |
| Missing credentials | `test_private_evidence_gate.py::test_missing_credentials_fail_closed_as_unauthorized_without_echoing_the_url`; `test_benchmark_evidence_destination.py::test_v9_embedded_credentials_are_rejected_and_never_echoed` |
| Permission failure | `test_private_evidence_gate.py::test_permission_failure_is_classified_unauthorized_and_leaves_no_ref` |
| Unavailable private repository | `test_benchmark_evidence_destination.py::test_v10_unreachable_store_fails_the_preflight_and_writes_nothing`; `test_private_evidence_gate.py::test_an_unavailable_private_store_never_falls_back_to_the_populated_public_origin`; `test_private_evidence_gate.py::test_a_missing_private_repository_is_not_found_not_empty` |
| Wrong remote configuration | `test_private_evidence_gate.py::test_wrong_remote_configuration_exits_2_for_every_entrypoint_and_writes_nothing`; `test_benchmark_evidence_destination.py::test_v8_identity_mismatch_is_rejected_with_no_retry_elsewhere` |
| Accidental public publication prevention | `test_private_evidence_gate.py::test_wrong_remote_configuration_exits_2_for_every_entrypoint_and_writes_nothing`; `test_private_evidence_gate.py::test_an_unavailable_private_store_never_falls_back_to_the_populated_public_origin`; `test_benchmark_evidence_destination.py::test_pointing_a_private_run_at_the_source_exits_2`; `test_evidence_destination_wiring.py::test_no_entrypoint_defaults_a_remote_or_names_origin` |
| Partial-evidence preservation | `test_private_evidence_gate.py::test_f4_a_rejected_push_keeps_the_would_be_files_locally_and_exits_3`; `test_private_evidence_gate.py::test_a_terminated_concurrency_experiment_seals_its_partial_evidence_to_the_private_store_only` |
| Termination (#660) handling | `test_private_evidence_gate.py::test_a_terminated_run_against_a_private_destination_seals_nothing_and_writes_no_results`; `test_private_evidence_gate.py::test_a_terminated_concurrency_experiment_seals_its_partial_evidence_to_the_private_store_only` |
| Benchmark / severity-observation / concurrency-experiment compatibility | `test_private_evidence_gate.py::test_unchanged_inputs_seal_a_record_identical_to_the_pre_688_snapshot`; `test_private_evidence_gate.py::test_wrong_remote_configuration_exits_2_for_every_entrypoint_and_writes_nothing`; the unmodified `test_run_benchmark_routine.py`, `test_run_severity_observation.py` and `test_run_concurrency_experiment.py` suites |
| Publisher sweep and watchdog against the private store | `test_private_evidence_gate.py::test_sweep_and_watchdog_run_over_the_private_phase_manifest`; `test_private_evidence_gate.py::test_every_sweep_and_watchdog_request_targets_the_evidence_repository_and_none_writes_on_failure`; `test_benchmark_publisher_evidence_destination.py::test_private_phase_builds_every_port_for_the_evidence_repository_only` |

## 2. ADR invariant checklist

| Invariant | Result | Evidence |
| --- | --- | --- |
| V1–V10 (§4.4 matrix) | pass | `test_benchmark_evidence_destination.py::test_v1_pre_cutover_without_remote_uses_the_proven_checkout_remote`, `::test_v2_pre_cutover_with_another_repository_is_rejected`, `::test_v3_private_with_proven_remote_is_accepted`, `::test_v4_private_naming_the_source_is_rejected`, `::test_v5_missing_repository_is_rejected`, `::test_v6_private_without_remote_never_uses_the_checkouts_own`, `::test_v7_missing_or_unknown_phase_is_rejected`, `::test_v8_identity_mismatch_is_rejected_with_no_retry_elsewhere`, `::test_v9_embedded_credentials_are_rejected_and_never_echoed`, `::test_v10_unreachable_store_fails_the_preflight_and_writes_nothing` |
| F1 | pass | `test_benchmark_evidence_destination.py::test_private_phase_without_a_remote_exits_2_and_pushes_nothing` |
| F2 | pass | `test_private_evidence_gate.py::test_wrong_remote_configuration_exits_2_for_every_entrypoint_and_writes_nothing` |
| F3 | pass | `test_benchmark_evidence_destination.py::test_unreachable_private_store_exits_3_before_any_push` |
| F4 | pass | `test_private_evidence_gate.py::test_f4_a_rejected_push_keeps_the_would_be_files_locally_and_exits_3` |
| F4a | pass | `test_private_evidence_gate.py::test_f4a_an_unconfirmed_push_leaves_one_ref_in_the_private_store_and_a_retry_cannot_double_it` |
| F5 | pass | `test_benchmark_evidence_destination.py::test_a_failed_stop_condition_read_is_never_zero_refs` |
| F6 | pass | `test_benchmark_publisher_evidence_destination.py::test_every_request_is_addressed_to_the_evidence_repository`; `test_private_evidence_gate.py::test_every_sweep_and_watchdog_request_targets_the_evidence_repository_and_none_writes_on_failure` |
| F7 | pass | `test_private_evidence_gate.py::test_f7_the_severity_stop_condition_counts_the_private_store_only`; `::test_f7_the_experiment_stop_condition_counts_the_private_store_only` |
| F8 | pass | `test_benchmark_evidence_destination.py::test_a_ref_outside_the_registry_is_refused_before_any_push` |
| F9, F9a | pass | `test_evidence_destination_wiring.py::test_the_manifest_validator_rejects_the_matrix_rows_statically`; `test_benchmark_evidence_destination.py::test_pre_cutover_without_a_remote_still_seals_to_the_source` |
| F10 | pass | `test_evidence_destination_wiring.py::test_every_claude_ref_prefix_in_benchmark_code_is_registered` |
| F11 | pass | `test_benchmark_publish_workflow.py::test_three_app_tokens_each_one_permission_and_only_the_evidence_repository` |
| F12, F13 | **open (G-open-1)** | Not implemented by #688 (ADR §5.4, §14); nothing in #689 changes the publisher's output. |
| I1 | pass | `test_benchmark_evidence_destination.py::test_an_existing_ref_is_a_refusal_and_the_run_unsealed`; `test_private_evidence_gate.py::test_i1_a_retry_of_a_sealed_ref_is_refused_and_the_first_seal_stays_intact` |
| I2 | pass | `test_private_evidence_gate.py::test_i2_publishing_the_same_run_again_is_a_no_op` |
| I3 | pass | `test_benchmark_evidence_destination.py::test_sealed_content_hash_is_the_same_in_either_store` |
| I4 | pass | `test_private_evidence_gate.py::test_i4_copying_a_ref_between_stores_preserves_the_commit_and_its_content_hash` |
| P1, P2, P3 | pass | `test_private_evidence_gate.py::test_p1_p2_provenance_names_the_source_in_both_phases_and_never_the_evidence_store`; `::test_unchanged_inputs_seal_a_record_identical_to_the_pre_688_snapshot` |
| R1 | pass | `test_evidence_destination_wiring.py::test_the_committed_block_is_pre_cutover_and_names_the_source` |
| R2, R4 | **open (G-open-2)** | Properties of the migration procedure, not of the code; #690 owns them and records the evidence (ADR §10). |
| R3 | pass | `test_benchmark_publisher_evidence_destination.py::test_private_phase_builds_every_port_for_the_evidence_repository_only` |

## 3. Unchanged behavior (the before/after comparison)

**Method.** One deterministic Sentinel run (stubbed runner and clock, one stub case) was sealed
to a directory twice: at `6dee089`, the last commit before #688, and at the head of #688's
tests. The two records were compared field by field. The pre-#688 record is committed as
`tests/support/pre_688_sentinel_record.json`, and the gate test re-seals the same inputs and
compares against it under **both** phases, so the comparison is repeatable and not a one-time
observation.

**Result.** Every field is identical except:

| Field | Differs because |
| --- | --- |
| `provenance.spec_sha256` and the `content_sha256` that covers it | `spec_sha256` digests the Routine prompt template and the manifest, and #688 amended both (the `evidence` block and `--evidence-remote`). It is a recorded pin, not an input to comparability or drift: nothing in `runtime_platform/` reads it back (`grep -rn spec_sha256 runtime_platform --include='*.py'`). A run sealed after #688 therefore has a different `content_sha256` than one sealed before it, even for identical benchmark inputs. This is expected and intended, and no baseline comparison depends on it. |
| `finished_at`, `sealed_at` | Wall clock, which the lane-run function stamps at call time. Excluded from the comparison. |

No case result, verdict, drift observation, baseline state, provenance (`repo`, `repo_sha`, `ref`) or
severity field changed.

## 4. Verified properties

- **Fixtures and expected baselines stay public.** The corpus and its expected findings are tracked in the source repository, and the
  modules that load them do not import the evidence destination
  (`test_private_evidence_gate.py::test_the_corpus_and_expected_baselines_do_not_go_through_the_evidence_destination`).
  Only Routine-generated evidence moves.
- **Source SHAs stay traceable.** `provenance.repo` is the source repository and `provenance.repo_sha` its commit in both phases, and no sealed field names the evidence repository
  (P1, P2).
- **No correctness behavior changes.** Section 3.
- **No evidence silently disappears.** Every non-zero seal path either leaves the ref on the evidence store only (`seal-unconfirmed`), or keeps the
  would-be files locally and prints a JSON status (`evidence-store-unavailable`). In the `private` phase no failure path writes to the source repository (under `pre_cutover` the
  source is the evidence store), and none reports success.

## 5. Findings fixed while validating

| Finding | Fix |
| --- | --- |
| A failed or unconfirmed push echoed the evidence remote (the private repository's URL or path) on stderr, although the ADR says it is not printed. | `Destination._scrub` redacts credentials and replaces the whole remote with the repository identity, before truncating, on both branches. Pinned by `test_f4_a_rejected_push_keeps_the_would_be_files_locally_and_exits_3`, `test_f4a_an_unconfirmed_push_leaves_one_ref_in_the_private_store_and_a_retry_cannot_double_it` and `test_the_remote_is_replaced_whole_and_before_truncation`. |
| A missing-credentials failure (`could not read Username … terminal prompts disabled`, the real message when git runs without a credential helper) was classified `unknown`. | `classify_git_error` maps it to `unauthorized`. Pinned by `test_missing_credentials_fail_closed_as_unauthorized_without_echoing_the_url`. |

## 6. Open preconditions carried to #690

| Id | What | Why it is not closed here |
| --- | --- | --- |
| G-open-1 | The private-phase public-log allowlist (ADR §5.4; F12, F13). | #688 did not implement it and #689's scope is validation. It must be implemented and its F12/F13 tests must pass no later than the cutover commit (ADR §5.3). |
| G-open-2 | R2 (no run crosses a cutover) and R4 (no ref deleted before its verified copy and approval). | They are rules of the cutover procedure; #690 executes them and records the evidence. |

## 7. Limits of the stubs (what only #690 can show)

Stubs can diverge from real GitHub. The checks above do **not** show, and #690 and the maintainer
experiments of ADR §12 must: the activity API on a private repository (X3), the `benchmark-publication` App's installation on the
evidence repository and token minting, the public creation ruleset (Q4; the evidence repository runs without Rulesets by the accepted risk in ADR §8, #706, which weakens none of the checks above), how the provider-side
Routine authenticates to the private repository (X1), and the real wording of git's authentication
errors beyond the two classes above.

## 8. Cutover is blocked by this gate

[`#690`](https://github.com/amirbena/code-review-skill/issues/690) must not merge the cutover
commit until (a) the commands in the header pass on the commit it cuts over from, and
(b) G-open-1 is closed. ADR §10 states this as step 0.
