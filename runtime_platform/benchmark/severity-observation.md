# Temporary Severity Observation Routine

**Temporary measurement infrastructure** ([#652](https://github.com/amirbena/code-review-skill/issues/652),
parent [#651](https://github.com/amirbena/code-review-skill/issues/651), feeds
[#653](https://github.com/amirbena/code-review-skill/issues/653)). It collects about 14 independent,
once-per-night severity observations of exactly one case, `correctness-off-by-one-pagination`, so
variance can be told from a real shift. It is not a lane, has no baseline, and cannot affect canonical
benchmark state. Repository-development document; not packaged into either Skill archive.

## 1. Spec

[`schedule/severity-observation-spec.json`](schedule/severity-observation-spec.json) is the repository-owned
spec: the one case, the cadence text, the stop condition, the storage prefix and the removal path. It is
deliberately **not** part of [`schedule/expected-run-manifest.json`](schedule/expected-run-manifest.json)
and is not in its `lanes`, so the watchdog, baseline promotion and the publisher never see it.

Cadence: once per day at 05:00 `Asia/Jerusalem`, after the 01:00 lane window's 04:00 completion target, so it
does not overlap the sentinel or comprehensive runs. Timezone handling is a Routine-configuration
responsibility, as for the lanes. One fresh invocation per night; no in-session repetition.

## 2. Entrypoint

```bash
python3 runtime_platform/benchmark/scripts/run_severity_observation.py \
  --trigger scheduled --model-id <the model backend this Routine session is running as>
python3 runtime_platform/benchmark/scripts/run_severity_observation.py --seal-dir /tmp/observation   # dry run
```

It calls the same `run_benchmark.py` path as the lanes (production adapter, unmodified fixture and prompt)
through `benchmark_lane_run.invoke`, so output is positively verified before anything is recorded; a failed
verification exits non-zero and records nothing.

## 3. Routine prompt (temporary)

```text
TEMPORARY (#652): collects 14 nightly severity observations of one case, then is disabled.
1. Check out a fresh copy of amirbena/code-review-skill at main.
2. Run:
   python3 runtime_platform/benchmark/scripts/run_severity_observation.py \
     --trigger scheduled \
     --model-id <the model backend this Routine session is running as>
3. If the command exits non-zero, stop — do not report success, do not retry, and do not
   post or push anything else to GitHub.
```

## 4. Evidence format

Each run pushes one orphan commit to `claude/severity-observation-<run_id>` (never `claude/benchmark-result-*`),
holding two files; `run_id` is `<UTC timestamp>-<repo sha[:12]>`, so an observation is addressable by ref.

`severity-observation.json` (`schema: severity-observation/v1`, `temporary: true`):

| Field | Meaning |
| --- | --- |
| `run_id`, `ref`, `case_id`, `trigger` | Identity; `trigger` is `scheduled` only from the Routine prompt. |
| `started_at`, `finished_at`, `duration_s` | Timestamps (UTC) and invocation wall time. |
| `resolved` | `severity` (the produced severity, or `null`), `state` (`exact` / `over` / `under` / `not-produced`), `expected`, `mismatches`. |
| `runtime` | `runtime_name`, `runtime_version`, `model_id`, `adapter_id`; same fields as a lane record's `runtime`. |
| `provenance` | `repo`, `repo_sha`, `ref`; same as a lane record's `provenance` subset. |
| `evidence` | The case's normal per-case `metrics`, `severity` and `duplicate_noise` rows. |

`resolved.severity` is the produced severity of the required finding. The benchmark result does not expose it directly (the severity row lists only mismatches), so it is read from the mismatch row, or, for an exact comparison, taken as the required entry's single severity (exact means produced is in the permitted set) and cross-checked against the raw produced findings; the run fails closed if they disagree. An optional entry matching alone is recorded as `not-produced`.

`raw-output.json` is the raw review output (`run_benchmark.py`'s `run` block).

## 5. Isolation guarantees

The entrypoint has no lane, baseline, drift or publication code path: it writes only through
`benchmark_seal.seal_to_ref` to the `claude/severity-observation-` prefix, never calls `gh` or the GitHub API,
and reads no baseline. Nothing in `records/`, `benchmark-history`, or any `benchmark-regression` /
tracking / health issue changes. `tests/unit/benchmark/test_run_severity_observation.py` pins this.

## 6. Stop condition and removal

Target: 14 observations. Once 14 `claude/severity-observation-*` refs exist the entrypoint prints
`"stopped": true`, runs nothing and exits 0; the maintainer then disables the Routine. To remove the
infrastructure, follow the spec's `removal_path`; keep the refs until #653 has read them.

## 7. Maintainer step

Register the daily Routine on the provider side with §3's prompt at 05:00 `Asia/Jerusalem`, confirm it fits
the account's daily run cap alongside the two lane Routines, and confirm the first run produced a
`claude/severity-observation-*` ref. The repository cannot check provider state.

The repository states no numeric daily run cap; it lives with the provider account. Load added: one
Routine run per day. With the sentinel (about every 3 days) and comprehensive (weekly) lanes that is at
most three runs on a night where all collide, usually one or two. The 05:00 start is after the lanes'
04:00 *target*, which is measured in #475 and not yet a guarantee; if the comprehensive lane is observed to
overrun 05:00, move this schedule later rather than letting runs overlap.
