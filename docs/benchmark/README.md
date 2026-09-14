# Code-Review Quality Benchmark

Repository-development contracts for the measurable code-review quality
benchmark (parent [#40](https://github.com/amirbena/code-review-skill/issues/40)):
a repeatable way to tell whether a Skill change improved or regressed
review quality against a fixed corpus.

Like [`../findings/`](../findings/README.md) and
[`../runtime-parallelism.md`](../runtime-parallelism.md), these are
repository-development docs — **not** packaged into either Skill archive,
and no packaged Skill resource depends on them. The normative rule for each
concern lives in the file named for it.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`fixture-format.md`](fixture-format.md) | The canonical machine-readable format for a single benchmark case — case identity, input (inline patch or repository reference), expected findings, expected severity, expected location detail, the four typed variance constructs (same-defect alternatives, alternative findings, optional findings, permitted severity variance), optional metadata, schema/versioning, and fail-closed validation. | [#50](https://github.com/amirbena/code-review-skill/issues/50) |
| [`corpus/README.md`](corpus/README.md) | The initial benchmark corpus — a small set of `benchmark-case/v1` fixtures, one per review category (correctness, security, quality, no-op), with the case-selection rationale recorded per case and in the directory README. | [#51](https://github.com/amirbena/code-review-skill/issues/51) |
| [`runner-contract.md`](runner-contract.md) | How a benchmark run executes the reviewer over the corpus — per-case isolation into a disposable workspace, the repository-safety invariants for every protected source checkout, cleanup on success and failure, the machine-readable per-case result shape, single-case vs. whole-corpus runs, and the exit-status rule. | [#52](https://github.com/amirbena/code-review-skill/issues/52) |
| [`regression-report.md`](regression-report.md) | How a candidate run is compared against a stored baseline — the baseline result artifact, the corpus-identity guard, the per-case and aggregate deltas, the metric-free rule that separates a regression from an improvement, deterministic output, and the deliberate baseline-refresh step. | [#53](https://github.com/amirbena/code-review-skill/issues/53) |
| [`match-criteria.md`](match-criteria.md) | When a produced review finding matches an expected benchmark finding — the two match axes (location, defect), the three-valued `MATCH` / `NEAR_MISS` / `NO_MATCH` result, the fixed tolerances, and how `alternatives` / `any_of` / `match: optional` resolve. The pairing relation the [#41](https://github.com/amirbena/code-review-skill/issues/41) quality metrics are built on. | [#54](https://github.com/amirbena/code-review-skill/issues/54) |
| [`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md) | Turning match results into **missed-finding (false-negative)** and **incorrect-finding (false-positive)** counts — the deterministic produced↔expected one-to-one pairing (`MATCH` edges only, fixture document order), the per-case and aggregate counts, how `match: optional` / `any_of` / `findings_completeness` change the accounting, and how the counts render alongside the regression report's deltas without gating it. | [#55](https://github.com/amirbena/code-review-skill/issues/55) |
| [`severity-accuracy.md`](severity-accuracy.md) | Measuring, over the #55 matched set, how often a matched finding carries a permitted expected severity — the **exact** / **over-severity** / **under-severity** classification on the P0 > P1 > P2 ordinal, the `severity`-list and `any_of` member resolution, the per-case and aggregate counts with a single exact-rational exact-match rate, and how they render alongside the regression report's deltas without gating it. | [#56](https://github.com/amirbena/code-review-skill/issues/56) |
| [`duplicate-noise.md`](duplicate-noise.md) | Measuring duplicate / same-root-cause noise over a case's **produced findings alone** — the same-root-cause edge (the #54 `MATCH` cell applied to a pair of produced findings, unchanged), connected-component clustering, the redundant-finding count and its exact-rational duplicate rate per case and in aggregate, the highest-noise-cases list, and how they render alongside the regression report's deltas without gating it. | [#57](https://github.com/amirbena/code-review-skill/issues/57) |
| [`ci-integration.md`](ci-integration.md) | Wiring the existing benchmark execution (`scripts/benchmark/run_benchmark.py` + `scripts/benchmark/benchmark_review_adapter.py`, #250) into a dedicated, informational/non-blocking PR-level CI check (`.github/workflows/benchmark-check.yml`) — the deterministic applicability classifier (`scripts/benchmark/benchmark_ci_classifier.py`), the not-applicable / runtime-unavailable / ran three-state contract, and its full independence from `release-worthiness.yml`. | [#255](https://github.com/amirbena/code-review-skill/issues/255) |

The first four documents cover the whole epic-[#40](https://github.com/amirbena/code-review-skill/issues/40)
benchmark surface; [`match-criteria.md`](match-criteria.md) ([#54](https://github.com/amirbena/code-review-skill/issues/54))
adds the expected-vs-produced match relation that the epic-[#41](https://github.com/amirbena/code-review-skill/issues/41)
quality metrics (#55–#57) consume;
[`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md)
([#55](https://github.com/amirbena/code-review-skill/issues/55)) is the
first of those metrics — the false-negative / false-positive counts — and
[`severity-accuracy.md`](severity-accuracy.md)
([#56](https://github.com/amirbena/code-review-skill/issues/56)) is the
second — the exact / over-severity / under-severity split over the matched
set — and [`duplicate-noise.md`](duplicate-noise.md)
([#57](https://github.com/amirbena/code-review-skill/issues/57)) is the
third — the same-root-cause clustering of produced findings and the
redundant-finding count. The corpus and its case-selection rationale
([#51](https://github.com/amirbena/code-review-skill/issues/51)) live in
[`corpus/`](corpus/README.md); the runner contract
([#52](https://github.com/amirbena/code-review-skill/issues/52)) is
[`runner-contract.md`](runner-contract.md); the run-to-run regression
report ([#53](https://github.com/amirbena/code-review-skill/issues/53)) is
[`regression-report.md`](regression-report.md).

## Worked example

[`examples/example-case.yaml`](examples/example-case.yaml) is one complete,
validated `benchmark-case/v1` fixture referenced by `fixture-format.md`
§12. It is an illustrative reference for the format, **not** a corpus case
(the corpus is #51). Its automated validation and the negative tests for
the format's rejection rules live in
[`../../tests/unit/benchmark/test_benchmark_fixture.py`](../../tests/unit/benchmark/test_benchmark_fixture.py).

## Corpus

[`corpus/`](corpus/README.md) holds the initial benchmark corpus (#51):
one crafted `benchmark-case/v1` fixture per review category, each a
self-contained inline patch with its pre-image and expected findings. The
corpus is validated by
[`../../tests/unit/benchmark/test_benchmark_corpus.py`](../../tests/unit/benchmark/test_benchmark_corpus.py)
through the same reference validator as the worked example.

## Runner

[`runner-contract.md`](runner-contract.md) (#52) fixes how a run executes
the reviewer over each case: one isolated, disposable workspace per case,
verbatim capture of produced findings, cleanup on both the success and
failure path, and a hard guarantee that no protected source checkout —
the user's tree, the caller checkout, or this repository's tree — is
mutated, even when a case fails. The test-only reference runner
[`../../tests/reference/benchmark/benchmark_runner.py`](../../tests/reference/benchmark/benchmark_runner.py)
mirrors it and is exercised by
[`../../tests/unit/benchmark/test_benchmark_runner.py`](../../tests/unit/benchmark/test_benchmark_runner.py),
including the deliberately-dirty-source-repo safety regression. Nothing
here is packaged and no Skill launches it. A production reviewer adapter
that drives a real runtime reading the packaged `local-code-review` Skill —
as opposed to a deterministic test stub — is
[`../../scripts/benchmark/benchmark_review_adapter.py`](../../scripts/benchmark/benchmark_review_adapter.py),
run via the CLI entrypoint
[`../../scripts/benchmark/run_benchmark.py`](../../scripts/benchmark/run_benchmark.py) (#250).

## Regression report

[`regression-report.md`](regression-report.md) (#53) fixes how a candidate
run is compared against a stored **baseline** run: joined by case `id`,
every per-case and aggregate delta is reported, and cases that got worse
(a dropped finding, an `executed` → `error` flip, a severity rise) are
called out distinctly from cases that got better; a `mixed`/ambiguous case
fails closed with the regressions. It is a pure run-to-run diff — it never
reads a fixture's `expected` block and computes no score, so it catches a
seeded regression before the quality-metric layer (#41) exists — and it
never writes the baseline: a refresh is a deliberate, committed step. The
test-only reference report
[`../../tests/reference/benchmark/benchmark_report.py`](../../tests/reference/benchmark/benchmark_report.py)
mirrors it and is exercised by
[`../../tests/unit/benchmark/test_benchmark_report.py`](../../tests/unit/benchmark/test_benchmark_report.py),
including the seeded-regression diff and the stable-output check.

## Match criteria

[`match-criteria.md`](match-criteria.md) (#54) fixes **when a produced
review finding matches an expected benchmark finding**: a `MATCH` needs
correspondence on **both** axes — same defect, same location — with a
one-axis-only correspondence surfacing as a distinct `NEAR_MISS` and
everything else `NO_MATCH`. Tolerances are fixed in the document (a
± 3-line proximity window, two claim-overlap thresholds) so two readers
classify every §8 worked example the same way. Matching is
severity-independent (that is #56) and does no counting (that is #55). The
test-only reference matcher
[`../../tests/reference/benchmark/benchmark_match.py`](../../tests/reference/benchmark/benchmark_match.py)
mirrors it and is exercised by
[`../../tests/unit/benchmark/test_benchmark_match.py`](../../tests/unit/benchmark/test_benchmark_match.py),
which encodes every worked example as a data-driven case.

## Missed & incorrect findings

[`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md)
(#55) is the first #41 quality metric: it turns `match-criteria.md`
results into **false-negative** (missed) and **false-positive**
(incorrect) counts, per case and in aggregate. It first resolves a
deterministic one-to-one pairing between produced findings and expected
entries — `MATCH` edges only, greedy in fixture document order — then
counts unpaired `required` entries as misses and union-`NO_MATCH`
unconsumed produced findings as false positives (only when the case is
`findings_completeness: exhaustive`; `at-least` tolerates them).
`match: optional` and unsatisfied `any_of` groups are handled per
`fixture-format.md` §9, near-misses are surfaced as a strict subset of the
misses without double-counting, and the counts render **alongside** the
regression report's per-case deltas without ever changing
`has_regressions`. It computes no score, rate, or severity judgement
(severity accuracy is #56; duplicate noise is #57). The test-only
reference metric
[`../../tests/reference/benchmark/benchmark_metrics.py`](../../tests/reference/benchmark/benchmark_metrics.py)
mirrors it (executed by
[`../../tests/unit/benchmark/test_benchmark_metrics.py`](../../tests/unit/benchmark/test_benchmark_metrics.py),
including every §8 worked example) and delegates every pairwise decision to
the single reference matcher.

## Severity accuracy

[`severity-accuracy.md`](severity-accuracy.md) (#56) is the second #41
quality metric. Over **exactly** the matched pairs the #55 pairing
produced, it compares each produced severity against the permitted expected
severities of the entry that pair satisfied and classifies the pair as
**exact** (a permitted value), **over-severity** (more severe than the
whole permitted band), or **under-severity** (neither). The three outcomes
partition the matched set, so `exact + over + under == matched`. A
`severity` list permits a band; an `any_of` group is scored against the
achieving member's severity. The per-case and aggregate records carry the
counts plus an exact-match **rate** as an exact `fractions.Fraction`
(`null` when nothing matched), and render **alongside** the regression
report's per-case deltas without ever changing `has_regressions`. It never
pairs or re-pairs a finding and redefines nothing about P0/P1/P2 (duplicate
noise is #57). The test-only reference metric
[`../../tests/reference/benchmark/benchmark_severity.py`](../../tests/reference/benchmark/benchmark_severity.py)
mirrors it (executed by
[`../../tests/unit/benchmark/test_benchmark_severity.py`](../../tests/unit/benchmark/test_benchmark_severity.py),
including every §7 worked example) and consumes the single reference
pairing and matcher.

## Duplicate noise

[`duplicate-noise.md`](duplicate-noise.md) (#57) is the third #41 quality
metric. Over a case's **produced findings alone** — no expected finding,
no #55 pairing — it takes every unordered pair of produced findings,
calls it a same-root-cause edge exactly when the #54 relation is `MATCH`
(location EXACT and defect CORRESPONDS, the matcher applied verbatim in
either direction), and groups the findings into **connected components**.
A cluster of `k` findings contributes `k − 1` redundant findings; the
per-case and aggregate records carry the cluster and redundant-finding
counts plus an exact-rational duplicate **rate** (`null` when the case
produced nothing), and the report section adds a `highest_noise_cases`
list ranked by redundant findings. It renders **alongside** the regression
report's per-case deltas without ever changing `has_regressions`, defines
no second match relation, adds no axis or tolerance, and specifies no
de-duplication behaviour for the reviewer itself (a #57 non-goal). The
test-only reference metric
[`../../tests/reference/benchmark/benchmark_dupes.py`](../../tests/reference/benchmark/benchmark_dupes.py)
mirrors it (executed by
[`../../tests/unit/benchmark/test_benchmark_dupes.py`](../../tests/unit/benchmark/test_benchmark_dupes.py),
including every §7 worked example) and consumes the single reference
matcher.

## Senior voice examples

[`senior-voice-examples.md`](senior-voice-examples.md) (issue
[#231](https://github.com/amirbena/code-review-skill/issues/231), design
record [#229](https://github.com/amirbena/code-review-skill/issues/229))
is a **documented reference set, not a CI gate**, unlike everything above:
eight findings paired as their structured and senior-voice renderings,
demonstrating the voice principles owned by
[`../../shared/templates/finding-rendering.md`](../../shared/templates/finding-rendering.md),
"Senior voice contract". It measures presentation quality, which the
#40/#41 corpus and metrics above do not.

## Reviewer Brief benchmark

[`corpus/reviewer-brief/README.md`](corpus/reviewer-brief/README.md)
(issue [#309](https://github.com/amirbena/code-review-skill/issues/309),
depends on [#304](https://github.com/amirbena/code-review-skill/issues/304))
pins the semantic quality and publication isolation of the private,
caller-facing `Reviewer Brief` every `github-pr-review` result includes.
Unlike every corpus above, it is not `benchmark-case/v1` fixtures — that
schema has no field for a private prose artifact or for a second,
GitHub-bound surface to compare it against — so it follows the
test-only-reference-model pattern instead:
[`../../tests/reference/benchmark/reviewer_brief_fixtures.py`](../../tests/reference/benchmark/reviewer_brief_fixtures.py),
exercised by
[`../../tests/unit/benchmark/test_reviewer_brief_structural.py`](../../tests/unit/benchmark/test_reviewer_brief_structural.py)
(deterministic structural properties) and
[`../../tests/unit/benchmark/test_reviewer_brief_publication_isolation.py`](../../tests/unit/benchmark/test_reviewer_brief_publication_isolation.py)
(zero-leakage into the GitHub-bound review body/inline comments, including
a negative canary proving the check can catch a real leak). The
semantic-quality properties whose wording is intentionally flexible are a
documented, non-CI-gated reference set,
[`reviewer-brief-examples.md`](reviewer-brief-examples.md), exactly like
the senior voice examples below.

## Agent-spawn / delegation benchmark

[`corpus/delegation-spawn/README.md`](corpus/delegation-spawn/README.md)
(issue [#307](https://github.com/amirbena/code-review-skill/issues/307),
depends on [#303](https://github.com/amirbena/code-review-skill/issues/303))
proves the agent-spawn and delegated-authority capability boundary stays
bounded: no `spawn_agent` capability, invocation agent-count/spawn-depth
budgets, the capability-subset delegation rule, non-transferable
mutation/formal-review-action authorization, sibling-collusion
resistance, and confused-deputy protection. Like the Reviewer Brief
benchmark below, it is not `benchmark-case/v1` fixtures — that schema has
no field for a capability grant, a spawn-depth/agent-count budget, or a
structural allow/deny result — so it follows the same test-only
reference-model pattern:
[`../../tests/reference/benchmark/delegation_fixtures.py`](../../tests/reference/benchmark/delegation_fixtures.py),
exercised by
[`../../tests/unit/benchmark/test_delegation_spawn_corpus.py`](../../tests/unit/benchmark/test_delegation_spawn_corpus.py)
(structural allow/deny assertions against the single reference model,
corpus-completeness checks against every `DELEG-###`/tagged `DOS-###`
threat-scenario id, and malformed-fixture rejection). Every comparison is
a deterministic structural assertion — never an LLM/rubric score — and
the corpus is disjoint from the finding-precision/recall/severity
metrics above and from ordinary code-review quality fixtures.

## Mutation-capability-boundary benchmark

[`corpus/mutation-boundary/README.md`](corpus/mutation-boundary/README.md)
(issue [#305](https://github.com/amirbena/code-review-skill/issues/305),
depends on [#301](https://github.com/amirbena/code-review-skill/issues/301))
proves code mutation never occurs without the exact required user
authorization and that authority never widens across the `APPLY_PATCH` /
`COMMIT` / `PUSH` transitions: repository-controlled instructions cannot
cause direct mutation, a proposed patch stays advisory, unauthorized
`APPLY_PATCH` and patch-digest/base-state mismatches are denied,
out-of-scope mutation is denied while an authorized apply changes only
its exact scope, apply/commit/push each require their own independent
authorization, authorization cannot be replayed across invocations or
inherited by a spawned child, and `github-pr-review` can never apply,
commit, or push even when prompted to. Like the agent-spawn / delegation
benchmark above, it is not `benchmark-case/v1` fixtures — that schema has
no field for a requested capability, an authorization scope/state, or a
structural allow/deny result with an expected post-action repository/Git
state — so it follows the same test-only reference-model pattern:
[`../../tests/reference/benchmark/mutation_fixtures.py`](../../tests/reference/benchmark/mutation_fixtures.py),
exercised by
[`../../tests/unit/benchmark/test_mutation_boundary_corpus.py`](../../tests/unit/benchmark/test_mutation_boundary_corpus.py)
(structural allow/deny assertions against the single reference model, run
in a real disposable temporary Git repository per case, corpus-
completeness checks against every `AUTH-###` threat-scenario id excluding
`AUTH-014`, and malformed-fixture rejection). Every comparison is a
deterministic structural assertion — never an LLM/rubric score — and the
corpus is disjoint from the finding-precision/recall/severity metrics
above and from ordinary code-review quality fixtures.

## CI integration

[`ci-integration.md`](ci-integration.md) (#255) wires the existing #250
benchmark execution into a **dedicated, informational** PR-level CI check,
independent from `release-worthiness.yml`: a small deterministic path
classifier decides applicability, an applicable PR runs
`python3 scripts/benchmark/run_benchmark.py` from its own checkout exactly as a
developer would, and the result is published without ever becoming a
required merge gate — an unavailable review-CLI runtime on the bare Actions
runner is a distinct, non-failing "benchmark not run" outcome, not a
failure. It reimplements no runner/matcher/metrics/adapter logic above.

## Related

The architecture map is [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
