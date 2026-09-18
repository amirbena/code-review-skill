# Capability-loading baseline (pre-`specialist-depth`-extraction)

Repository-development record for issue
[#408](https://github.com/amirbena/code-review-skill/issues/408), child of
[#403](https://github.com/amirbena/code-review-skill/issues/403). Like the
rest of [`./`](README.md), this is a repository-development doc: **not**
packaged into either Skill archive, and no packaged Skill resource depends
on it.

Establishes the reproducible reference
[`capability-architecture-model.md`](capability-architecture-model.md)
§I.1/§I.2 requires before any capability's loading becomes conditional:
without it, no later "loading went down" or "behavior stayed stable" claim
for `specialist-depth` extraction is verifiable. This document records
**one measurement**, taken at a fixed commit, not a live dashboard —
re-running it later (§4) is how a future change is diffed against it.

## 1. Scope and non-goals

Per #408:

- Measures today's **packaged** instruction/resource surface (what
  `scripts/packaging/package-manifest.json` actually ships each adapter
  today — nothing is conditional yet, so this is the same surface every
  review of that adapter loads), attributed by capability via `#404`'s
  `capability.yaml` files.
- Records current values of the three existing quality-metric contracts
  (`missed-and-incorrect-findings.md` #55, `severity-accuracy.md` #56,
  `duplicate-noise.md` #57) as the stability baseline, reusing
  `runtime_platform/benchmark/scripts/`'s existing evaluators unchanged — no new evaluator.
- Does **not** fix the benchmark runner's non-recursive corpus glob
  (`run_benchmark.py`'s default `corpus_dir.glob("*.yaml")` reaches only
  the 4 top-level cases of ~180 total fixtures) — a separate, pre-existing
  gap this issue's Non-Goals explicitly exclude.
- Does **not** measure runtime latency, time-to-first-finding, or total
  token consumption (`model.md` §I.2's runtime-execution-dependent rows)
  — those need `#330`'s Class 2 runtime, out of scope here.
- Does **not** measure `verdict-consistency` — its corpus
  (`docs/benchmark/corpus/verdict-consistency/`) sits below the same
  non-recursive glob and is a separate, larger measurement this issue does
  not extend to.

## 2. Static instruction/resource-surface baseline

Reproducible with:

```bash
python3 scripts/capability_architecture/capability_loading_baseline.py static
```

`capability_loading_baseline.measure_static_surface()` sums `wc -w`-equivalent
word counts (Python's whitespace `str.split()`, matching
`capability-architecture-model.md`'s own stated methodology) over every
file `scripts/packaging/generate_package_manifest.build_manifest()`
currently ships each adapter (`shared_files` + that adapter's own
`skills.<adapter>.files`), attributing each file to the `capability.yaml`
that declares it and leaving everything else — the not-yet-manifested,
always-resident core (`review-kernel`, `finding-contract`,
`capability-posture`, `review-context-core`, `review-router`, and the
per-Skill files no `capability.yaml` owns yet, per `capability-manifest-schema.md`
"Field: `loads`") — as `core_unattributed_words`. This is narrower than
`capability-architecture-model.md` §0's ~81,300/~110,000-word figures,
which additionally follow one more markdown-link hop into the rest of
`shared/`; the packaged-manifest surface below is the exact set a real
Skill invocation reads today, which is what a loading-behavior claim needs
to be diffable against.

Word→token conversion uses the one ratio `capability-architecture-model.md`
§0 itself reports for this repository's prose (~108,000 tokens /
~81,300 words ≈ 1.329) — not re-derived here.

Measured at commit `55f521f628a2` (2026-09-17), `main` synchronized:

| Adapter | Total words | Total tokens (est.) | Core (unattributed) words | Attributed to a manifested capability |
| --- | ---: | ---: | ---: | ---: |
| `local-code-review` | 82,850 | 110,059 | 42,775 (51.6%) | 40,075 (48.4%) |
| `github-pr-review` | 112,038 | 148,833 | 45,593 (40.7%) | 66,445 (59.3%) |

Per-capability attribution (words):

| Capability | local | github |
| --- | ---: | ---: |
| `authorization-github` | — | 5,063 |
| `conditional-passes` | 7,213 | 7,213 |
| `context-resolution` | 3,696 | 3,696 |
| `finding-placement-derivation` | 7,394 | 8,671 |
| `parallel-execution` | 2,892 | 2,892 |
| `publication-github` | — | 10,030 |
| `remediation` | 1,499 | 1,499 |
| `repository-checkout` | — | 1,331 |
| `reviewer-assist` | — | 2,078 |
| `runtime-execution` | 4,915 | 4,915 |
| `scale` | 3,350 | 3,350 |
| `specialist-depth` | 9,116 | 9,116 |
| `stateful-review` | — | 6,591 |

The full machine-readable output (including the raw per-adapter JSON this
table summarizes) is committed alongside this document at
[`capability-loading-baseline.json`](capability-loading-baseline.json)
(`static_surface` key).

Reading this against §I.4's named improvement sources: `specialist-depth`
(9,116 words, both adapters) is the single largest attributed capability
in either adapter's surface today, and — being `on-activation` but
currently shipped unconditionally — is entirely inside
`core`-equivalent always-loaded territory until its own loading actually
becomes conditional. That is the number a first extraction should move
out of the unconditional path and into a measured activation rate.

## 3. Quality-metric stability baseline

Reproducible with (requires the `claude` CLI on `PATH` or
`BENCHMARK_REVIEW_CLI` set, per `run_benchmark.py`'s own runtime-
availability check):

```bash
python3 scripts/capability_architecture/capability_loading_baseline.py quality
```

This runs `docs/benchmark/corpus`'s reachable cases (today's 4 top-level
fixtures — §1's stated non-goal) through
`runtime_platform/benchmark/scripts/benchmark_review_adapter.ProductionReviewerAdapter`
against a real `claude` CLI reading the packaged `local-code-review`
Skill unchanged, then computes each existing metric verbatim from that one
run: `runtime_platform/benchmark/reference/benchmark_metrics.compute_run_metrics`
(#55), `benchmark_severity.compute_run_severity_accuracy` (#56), and
`benchmark_dupes.compute_run_duplicate_noise` (#57) — the same reference
implementations `run_benchmark.py` and the nightly history vehicle
(`nightly-history-and-baseline.md`) already use, called together here only
because no existing entrypoint wires all three at once.

Measured the same day, same commit, `claude` CLI `2.1.272`:

| Metric | Value | Source |
| --- | --- | --- |
| Cases executed | 4 / 4 (0 errored) | `run.ok` |
| False negatives | 0 | #55 |
| False positives | 0 | #55 |
| Near misses | 0 | #55 |
| Matched findings | 3 (the 4th case, `no-op-comment-and-rename`, correctly produced 0 findings) | #56 |
| Severity exact-match rate | 3/3 = 1 | #56 |
| Over-severity / under-severity | 0 / 0 | #56 |
| Duplicate clusters | 0 | #57 |
| Redundant findings | 0 | #57 |
| Duplicate rate | 0 | #57 |

The full per-case `run`, `missed_and_incorrect`, `severity_accuracy`, and
`duplicate_noise` payloads (each in its owning contract's own §-defined
shape) are committed verbatim in
[`capability-loading-baseline.json`](capability-loading-baseline.json)
(`quality_metrics` key) — this table is a summary, that file is the
record a future comparison should actually diff against.

This is a **clean baseline on a 4-case corpus**: it establishes that
`specialist-depth` extraction has no room to silently regress on the cases
that are reachable today, but a clean 4/4 does not itself validate routing
correctness at scale — the non-recursive-glob gap (§1) means ~176 other
corpus cases, including every domain-deepening and composition corpus
`specialist-depth`'s own extraction will touch, are not represented in
this number.

## 4. Reproducing / re-measuring

```bash
python3 scripts/capability_architecture/capability_loading_baseline.py all \
  --out docs/capability-architecture/capability-loading-baseline.json
```

`all` runs both halves and writes the combined JSON this document's tables
were generated from. A later comparison re-runs the same command at a new
commit and diffs the two JSON files — §I.3's efficiency-with-a-guard
formula reads directly off `static_surface`'s `total_words` and
`quality_metrics`'s three metric sections. This document's own prose
tables (§2, §3) are a snapshot, not re-generated automatically; a
maintainer updates them by hand when re-measuring, the same convention
`regression-report.md` §8 uses for its own baseline refresh ("an explicit
human action ... only when the deltas are understood and accepted").

## Status and canonical home

This document and
[`scripts/capability_architecture/capability_loading_baseline.py`](../../scripts/capability_architecture/capability_loading_baseline.py)
are the authoritative baseline for #408. Neither is packaged into either
Skill archive, and no runtime behavior, packaging, or loading changed to
produce it — purely additive, matching #404's own precedent.
