# Temporary Concurrency Measurement Routine

**Temporary measurement infrastructure** ([#681](https://github.com/amirbena/code-review-skill/issues/681),
parent [#680](https://github.com/amirbena/code-review-skill/issues/680), feeds
[#682](https://github.com/amirbena/code-review-skill/issues/682), closed out by
[#683](https://github.com/amirbena/code-review-skill/issues/683)). It measures whether running fixtures a
bounded number at a time (1, 2, 4 workers) is safe and effective inside a Claude Code Remote Routine. It is
not a lane, has no baseline, and cannot produce a lane record, seal, baseline change or drift verdict. The
official Comprehensive lane stays sequential. Repository-development document; not packaged into either Skill
archive.

## 1. Spec

[`schedule/concurrency-experiment-spec.json`](schedule/concurrency-experiment-spec.json) is the repository-owned
spec: allowed worker counts, the subset selection, the cadence, the stop condition, the storage prefixes and the
removal path. It is deliberately **not** in [`schedule/expected-run-manifest.json`](schedule/expected-run-manifest.json)
`lanes`, so the watchdog, baseline promotion and the publisher never see it.

The subset is deterministic: an explicit `subset.case_ids` list, or (the placeholder until #682 commits the
sized, stratified list) the first `size` fixtures of the comprehensive corpus ranked by `sha256(seed:case_id)`.
Every run records `corpus_id`, a `subset_id` digest and each fixture's digest, so two runs are comparable only
when those match.

## 2. Entrypoint

```bash
python3 runtime_platform/benchmark/scripts/run_concurrency_experiment.py --arms 1,2 --seal-dir /tmp/experiment   # dry run
python3 runtime_platform/benchmark/scripts/run_concurrency_experiment.py --trigger scheduled --model-id <model>
```

[`run_concurrency_experiment.py`](scripts/run_concurrency_experiment.py) owns the spec, stop condition, audit and
sealing; [`benchmark_concurrency_workers.py`](scripts/benchmark_concurrency_workers.py) owns the pool. Each fixture is
one `run_benchmark.py --case-id` child, exactly as the lanes run them, verified with `verify_benchmark_output`.
A thread pool of N only *waits* on those children, so the review path, `ProgressLog` and signal handling stay
per-process and unchanged. Arms run one after another in the order given.

## 3. Isolation audit and its limits

| Surface | Guarantee | Limit |
| --- | --- | --- |
| Workspaces | Every worker slot owns one scratch directory, set as the child's `TMPDIR`; the runner's `mkdtemp` workspaces are created inside it and a slot is never held by two fixtures. | A child that ignores `TMPDIR` is caught only by the stray `benchmark-*` check in the shared temp directory, which also sees unrelated processes. |
| Git | Children use the runner's hermetic git environment (no system or global config). The global and repository config digests are checked unchanged. | Only those two config files are checked. |
| Protected checkout | `capture_repo_state` before and after must match. | Any edit of the checkout during a run, by anyone, is reported as a violation; run from an untouched checkout. |
| Review CLI state (config, session, cache) | **Not isolated**: redirecting it would drop the Routine's authentication. A before/after fingerprint (entry count, newest mtime) is recorded. | Shared state and rate limits can still couple workers; that is what the experiment measures, and the fingerprint is a diagnostic, not a pass/fail check. |
| Progress and signals | Per child process. The parent stops every child tree on termination and seals partial evidence as `terminated`. | `terminate_on_signal` is main-thread only, which is why no review code runs in a thread. |
| stderr | Captured per fixture (bounded tail kept in `raw-output.json`) and forwarded as worker-tagged `START`/`DONE`/`FAIL` lines. | Heartbeat lines of a running child are not streamed live. |
| Coverage | Each arm must attempt every fixture exactly once and each child must report exactly its assigned case. | |

Any violation fails the experiment: `isolation.passed` is false, the status is `incomplete` and the exit code is
non-zero.

## 4. Evidence

A scheduled run pushes one orphan commit to `claude/concurrency-experiment-<run_id>` (a trial, the default
trigger, to `claude/concurrency-trial-<run_id>`, which is never counted); never `claude/benchmark-result-*`.
`confined_ref` refuses any other prefix. Files: `concurrency-experiment.json` (`schema: concurrency-experiment/v1`)
and `raw-output.json` (each fixture's `run` block and stderr tail).

Per arm: workers, planned/attempted/completed, errors, timeouts, rate-limit hits, wall-clock, summed and median
and max fixture time, host contention (peak 1-minute load, child CPU seconds, CPU count) and per fixture: worker
slot, start offset, duration, probe and review split, exit code, failure class and the child's own failure category.
Run level: model id, CLI version, repository SHA, spec issue, corpus and subset identity, the audit.

Unavailable measurements are `null` or marked `available: false`, never estimated. Token usage is unavailable
(`run_benchmark.py` does not surface it). Rate-limit evidence counts only what the child surfaces, so zero is not
proof that nothing was throttled.

`status` is `complete` only when every arm completed every fixture and the audit passed; otherwise `incomplete` or
`terminated`. `failure_classes` separates `infrastructure` (child crash, no usable output, hard timeout, runtime
unavailable), `benchmark` (the child ran but a case did not execute) and `isolation` (an audit violation).

## 5. Stop condition and failure policy

Enforced in the entrypoint from the spec and the remote refs alone, independent of whether the Routine is enabled.
A scheduled run exits 0 without executing, printing `skipped`, when: today is after `window_end` (`window-ended`);
`max_experiments` (4) experiment refs exist (`stop-condition-reached`); the spec has no dates yet
(`not-activated`); today, in `Asia/Jerusalem`, is not a listed experiment date (`not-an-experiment-day`); or an
experiment ref already exists for today (`already-experimented-today`).

A missed or failed experiment is recorded as such and still counts. Nothing shifts the schedule, nothing makes up
a run, and a scheduled run takes its arms from the spec (`--arms` is refused), so no code path extends the
campaign. Extension needs explicit maintainer authorization in an issue and a new spec.

The entrypoint never retries a child or an arm. A listing failure refuses to run (exit 1) rather than guessing.

## 6. Routine design (inactive)

Not registered or activated by this change. Tuesday and Thursday at **12:00 `Asia/Jerusalem`**, two weeks.

- Sentinel 01:00 (about every 3 days) and Comprehensive Friday 01:00 target completion by 04:00; severity
  observation 05:00 daily (short). Noon is clear of all of them and leaves the whole afternoon and night for a long
  experiment before the next 01:00 window (13 hours).
- Tuesday and Thursday never coincide with the Comprehensive lane's Friday. The publication sweep (`23 */2 * * *`)
  only publishes and runs in its own environment, so it does not contend for the Routine session.
- Maintainer step: write the four dates (each with its arms; Tuesday `[1, 2]`, Thursday `[2, 4]`, order
  counterbalanced across weeks per #682) and `window_end` into the spec, after #682 commits the subset and
  thresholds, and confirm the daily run cap on the provider side.

```text
TEMPORARY (#681): four two-week concurrency measurement experiments, then is disabled.
1. Check out a fresh copy of amirbena/code-review-skill at main.
2. Run:
   python3 runtime_platform/benchmark/scripts/run_concurrency_experiment.py \
     --trigger scheduled \
     --model-id <the model backend this Routine session is running as>
3. If the command exits non-zero, stop — do not report success, do not retry, and do not
   post or push anything else to GitHub. Keep the command's stdout and stderr in the transcript.
```

## 7. Removal path

Per the spec's `removal_path`: disable the Routine on the provider side, delete the spec, both scripts, this
document and `tests/unit/benchmark/test_run_concurrency_experiment.py`, and keep the
`claude/concurrency-experiment-*` refs until #682 has read them. Closure is #683.
