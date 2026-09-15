# Benchmark CI Integration

Repository-development doc: not packaged, and no packaged Skill resource
depends on it. Contract for wiring the existing benchmark execution
([#250](https://github.com/amirbena/code-review-skill/issues/250):
`scripts/benchmark/run_benchmark.py` + `scripts/benchmark/benchmark_review_adapter.py`,
consuming `tests/reference/benchmark/*` and `docs/benchmark/corpus/*.yaml`)
into a dedicated PR-level CI check
([#255](https://github.com/amirbena/code-review-skill/issues/255)),
implemented by `.github/workflows/benchmark-check.yml` and
`scripts/benchmark/benchmark_ci_classifier.py`.

## 1. Scope

This check answers one question — "did this PR touch anything that can
change review-quality benchmark results?" — and, when the answer is yes,
runs the same benchmark a developer already runs manually and publishes
its result. It reimplements no benchmark logic: no second reviewer, no
second runner, no second evaluator, and no Claude Code plugin. Everything
it does is call `scripts/benchmark/run_benchmark.py` from the PR checkout and report
what came back.

## 2. Applicability classifier

`scripts/benchmark/benchmark_ci_classifier.py` is a small, deterministic function
over a list of changed repository-relative paths — no fuzzy heuristics, no
content inspection, no scoring. A PR is **applicable** when at least one
changed path falls under:

- `shared/**`
- `skills/**`
- `docs/benchmark/**`
- `tests/reference/benchmark/**`
- `scripts/benchmark/run_benchmark.py` (exact file)
- `scripts/benchmark/benchmark_review_adapter.py` (exact file)

Everything else is **not applicable**. This is a new, self-contained
classifier: it does not import, call, or route through
`scripts/release/release_lib/classification.py` or `scripts/release/release_worthiness.py`,
and neither of those imports or calls it — see "Independence from
release-worthiness" below.

## 3. Independence from release-worthiness

This check is fully independent from `.github/workflows/release-worthiness.yml`:

- a separate workflow file, own `on: pull_request` trigger, own
  `concurrency` group, own `permissions: contents: read` block;
- no `needs:` on, and no job shared with, any `release-worthiness.yml` job;
- no reuse of `release_worthiness.py`'s classify/assess logic or of
  `release_lib/classification.py`'s category tables;
- not a required status check, not added to any branch-protection ruleset,
  and never blocks or gates another job.

Neither check's classifier routes through the other's decision contract.
Read `scripts/release/release_lib/classification.py` before touching either
classifier: `.github/workflows/**` and repository-maintenance `scripts/**`
changes are not release-worthy paths there, so adding or changing this
workflow and classifier does not, on its own, require a CHANGELOG entry.

## 4. Non-blocking / informational status

The benchmark's reviewer adapter needs a real review-CLI runtime
(`scripts/benchmark/benchmark_review_adapter.py`'s `check_runtime_available` /
`RuntimeUnavailableError`), which will almost certainly be unavailable on a
bare GitHub Actions runner with no secrets configured. The job distinguishes
three outcomes, and keeps them visibly distinct in its summary:

1. **Not applicable** — the PR touched none of the paths above. The job
   completes successfully with a "benchmark check: not applicable" summary
   and does not invoke the benchmark at all.
2. **Applicable, runtime unavailable** — the PR is applicable, but the
   configured review CLI cannot be found or is not usable. The job
   completes successfully with a "benchmark not run: runtime unavailable"
   summary. This is a distinct, informational outcome — it is never
   conflated with "not applicable" and it never fails the job.
3. **Applicable, runtime available** — the job runs
   `python3 scripts/benchmark/run_benchmark.py` and publishes its JSON output (via
   `$GITHUB_STEP_SUMMARY` and an uploaded artifact). A genuine execution
   failure (the script crashing, or exiting non-zero for a reason other
   than a missing/unusable runtime) may still surface as a visibly failed
   step, for diagnostic value — but the job is never made a required merge
   gate: it holds default read-only `GITHUB_TOKEN` permissions, is not
   `needs:`-blocking for any other job, and is not added to any
   branch-protection ruleset. Keeping the model/runtime-dependent result
   informational is intentional and initial; making it a required,
   blocking gate is future work, not part of this contract.

## 5. Runs the same script a developer runs manually

The workflow invokes `python3 scripts/benchmark/run_benchmark.py` exactly as
documented in that script's own docstring, honoring `BENCHMARK_REVIEW_CLI`
/ `BENCHMARK_REVIEW_CLI_ARGS` when a workflow operator sets them. It never
duplicates the runner, matcher, metrics, or adapter logic those scripts and
`tests/reference/benchmark/` already own — this workflow only wires a
GitHub Actions trigger and a real PR checkout to that existing, unchanged
entrypoint.

## 6. Out of scope

- Making the result a required or blocking check.
- Provisioning a real review-CLI runtime/credentials in CI. The contract
  any such runtime must satisfy — trust boundary, viability criteria,
  candidate classes, required metadata — is
  [`runtime-execution-contract.md`](runtime-execution-contract.md) (#330);
  selecting a candidate is [#336](https://github.com/amirbena/code-review-skill/issues/336)
  and provisioning it is [#337](https://github.com/amirbena/code-review-skill/issues/337).
- Any second implementation of the benchmark's applicability logic —
  `scripts/benchmark/benchmark_ci_classifier.py` is the single source for this
  check's classification.
