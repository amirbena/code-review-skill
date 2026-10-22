# Refactoring Baselines (Phase 0)

Repository-development record of the baselines that later work under Epic
[#786](https://github.com/amirbena/code-review-skill/issues/786) compares
against ([#787](https://github.com/amirbena/code-review-skill/issues/787)).
Like the other `docs/` design records it is **not** packaged into either Skill
archive, and no packaged resource depends on it.

Measured at `3db2af8` (v1.79.1), 2026-10-21/22. The numbers below are a
snapshot; the commands in "Reproduce" regenerate them, and a later PR should
re-run the relevant command and cite both outputs rather than edit this page.

## Reproduce

```bash
python3 scripts/validation/context_size_report.py
```

```bash
python3 scripts/validation/suite_timing_report.py --runs 2 --out /tmp/timing.json
```

```bash
python3 runtime_platform/benchmark/scripts/benchmark_baseline_summary.py
```

The first reads only repository files and is deterministic. The second runs
the whole suite (several minutes; keep `--out` outside the repository) and `--from-json /tmp/timing.json` re-renders a
stored result. The third reads `origin/benchmark-history` (`git fetch origin
benchmark-history` first) or a checkout via `--history-dir`, and never writes.

## 1. Mandatory context size

The default set is `SKILL.md` plus every file its "Required Policy Loading"
section lists as unconditional; the report derives it from that section, so it
cannot drift from the Skill. Tokens are estimated as bytes / 4.

| | Files | Lines | Bytes | Est. tokens |
| --- | ---: | ---: | ---: | ---: |
| Local default set | 17 | 5,532 | 303,109 | ~75,800 |
| Local default + runbook + report template | 19 | 6,681 | 369,837 | ~92,500 |
| GitHub default set | 20 | 6,123 | 338,329 | ~84,600 |
| GitHub default + both runbooks + both summary templates | 24 | 8,364 | 467,986 | ~117,000 |

The Epic's "about 90K tokens" is the Local figure *with* the runbook and report
template. Not in the default sets: Local conditional files 138,606 bytes and one
context-specific member (`review-ownership.md`, 2,402 bytes); GitHub conditional
files 65,546 bytes and two context-specific members (22,246 bytes).

Largest default-set files, shared by both Skills: `finding.md` 56,448 bytes,
`review-scope.md` 40,229, `finding-rendering.md` 33,539, `review-summary.md`
30,227, `runtime-validation.md` 26,628. Regenerate for the full per-file list.

## 2. Test and CI timing

Local run: Python 3.14.6, macOS arm64, 12 CPUs, two sequential runs of
`unittest discover -s tests -t .`. CI uses Python 3.13 on a different runner, so
compare shares and ranking, not absolute seconds.

| Measure | Value |
| --- | ---: |
| Tests discovered | 6,671 |
| Wall time per run | 422 s, 389 s |
| Sum of per-test durations (median of runs) | 366 s |
| Wall time not attributed to a test (fixtures, imports) | ~40 s |
| Per-test time the FAST tier still runs | 82 s |

| Tier directory | Tests | Seconds | Share |
| --- | ---: | ---: | ---: |
| `tests.unit` | 4,211 | 236 | 64.6% |
| `tests.integration` | 140 | 126 | 34.4% |
| `tests.policy` | 2,312 | 3.6 | 1.0% |
| `tests.repository` | 8 | 0.1 | 0.0% |

Within `unit`, `benchmark` is 157.6 s (43.1% of the suite). The largest
integration areas are `sandbox` 55.0 s, `packaging` 34.7 s and `release` 24.2 s.
The five slowest modules are `unit.benchmark.test_run_concurrency_experiment`
(64.7 s), `integration.sandbox.test_adversarial_containment` (55.0 s),
`integration.packaging.test_ordinary_packaging_version` (33.7 s),
`integration.release.test_skill_archive_release_version` (20.7 s) and
`unit.benchmark.test_benchmark_corpus_patch_applies` (15.6 s).

What this supports. The FAST tier's 82 s share of per-test time agrees with the
roughly 60 s FAST test step seen in CI, and policy-tier tests (2,312 of them)
cost about 1% of the time, so the cost of FULL sits in `unit.benchmark` and
`integration`. What it does not support: any claim about PARTIAL or DOCS tiers
(their set depends on the change), or absolute CI seconds.

**One flaky test.** `unit.benchmark.test_run_concurrency_experiment.FailureTest.
test_termination_stops_children_and_seals_partial_evidence_as_terminated`
errored in run 1 (60.7 s) and passed in run 2 (30.8 s); alone it passes in
about 31 s through the timing runner, and its class passes under plain `unittest`. Its
`communicate(timeout=60)` leaves about 2x margin over the roughly 30 s the
termination path takes, and 60.7 s matches that timeout, so the failure is
consistent with a timeout under load. The error text was not captured in that
run (the runner now records the last traceback line), so the cause is inferred.
The test is counted at its median (45.8 s) in the tables above.

## 3. Benchmark quality baseline

Source: 12 sealed `benchmark-result/v1` records, all valid and verified, on
`benchmark-history` (read through `benchmark_baseline_summary.py`). Only the
**sentinel** lane has records; **comprehensive** has none, so there is no
comprehensive quality baseline. Today's comprehensive discovery finds 183
`benchmark-case/v2` fixtures.

| Sentinel, 2026-09-24 to 2026-10-20 | |
| --- | --- |
| Corpus cases per record | 4 |
| Missed findings (FN) / incorrect findings (FP) | 0 / 0 in 11 records; 1 / 1 in `…-20260929…` |
| Errored cases | 0 in every record |
| Exact severity rate | `1` in 6 records, `2/3` in 5, `1/2` in 1 |
| Drift status | `drift` in 5 records, `none` in 6, `not-evaluated` in 1 (the bootstrap) |
| Pinned baseline | `sentinel-20260924T220515Z-bf01aff11010` (bootstrap) |
| Run duration | 62 to 384 s |

The `2/3` severity movement is the subject of Epic #651; this record only
reports it.

Provenance recorded per record: `model_id`, `runtime_name`, `runtime_version`,
`adapter_id`, `repo_sha`, `entrypoint_version`, `spec_sha256`, `corpus_id`. The
model ID was `claude-sonnet-5` in all 12 records while the Claude Code version
changed between 10 of the 11 consecutive pairs. **No field records the Skill version**;
it is recoverable only through `repo_sha`.

## 4. Production execution vs. reference-model validation

| Path | Calls the real runtime and packaged Skill? | Evidence |
| --- | --- | --- |
| `run_benchmark.py` | Yes, through `ProductionReviewerAdapter` | `scripts/benchmark_review_adapter.py` |
| Sentinel and comprehensive lanes (`run_benchmark_routine.py`) | Yes | adapter import; sealed records above |
| On-demand measurements (`measure_dependency_tree.py`, `measure_structured_result.py`, `measure_workspace_sibling.py`) | Yes | adapter imports |
| Temporary routines (`run_concurrency_experiment.py`, `run_severity_observation.py`) | Yes | adapter imports |
| Live-runtime tests (`LiveRuntimeTestCase`, `BENCHMARK_REQUIRE_RUNTIME`) | Only when a runtime is available | `tests/support/benchmark_runtime.py`; skipped otherwise |
| Scoring and reporting (`reference/benchmark_metrics.py`, `benchmark_match.py`, `benchmark_report.py`, …) | No, deterministic functions over recorded output | `runtime_platform/benchmark/reference/` |
| Nine Python-literal fixture domains (`*_fixtures.py`: mutation, delegation, trusted-host NL, reasoning checkpoint, security events, GitHub enforcement, publication mode, verdict consistency, reviewer brief) | No; `validate_corpus` checks data against the `tests.reference.review` models | none imports the adapter |
| `benchmark-case/v2` YAML structure tests | No | `tests/unit/benchmark/test_benchmark_corpus*.py` |

Consequence: the sealed records above measure production behavior for the
YAML cases only. The nine Python-literal domains are validated against
reference models and are not scored on real Skill output.

## 5. Not measured

- Token counts: only a bytes / 4 estimate exists. Sealed records contain no
  token or cost fields.
- Whether a reviewer actually opens the default set (loading compliance is
  prose plus the #784 checkpoint, not observed).
- The GitHub default set's transitive loads from `policies/github-review.md`.
- Comprehensive-lane quality (no sealed record) and production scoring of the
  nine Python-literal domains.
- Skill version per benchmark record; token or cost per run.
- Per-test CI durations (only local; CI step totals come from `gh run view`).
- Run-to-run variance beyond two local runs and twelve sentinel records.
- PARTIAL and DOCS tier cost.

## 6. Reductions landed

Each row cites `context_size_report.py` before and after. **Genuine** means the
content is not loaded on the common path; **deferred** means it is still
loaded before its first governed decision (reported as moved, not saved).

| Issue / change | Activation predicate | Genuine saving (default set) | Deferred |
| --- | --- | --- | --- |
| #788: human renderings split from `finding-rendering.md` into conditional `finding-rendering-human.md` | `human_review_output` / `human_inline_findings` resolves `true` or is ambiguous after reading the invocation; fail-closed | Local 303,109 → 289,028 bytes (−14,081, ~3.5k tokens); GitHub 338,329 → 324,303 (−14,026) | none; the 14.4 KB file loads only when the predicate fires |

Still open under #788: the `finding.md` split and the `runtime-validation.md`
unconditional-vs-`on-activation` reconciliation, each in its own PR.
