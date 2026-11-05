# Code-Review Quality Benchmark

Repository-development contracts for the measurable code-review quality
benchmark (parent [#40](https://github.com/amirbena/code-review-skill/issues/40)):
a repeatable way to tell whether a Skill change improved or regressed
review quality against a fixed corpus.

Like `../../docs/findings/` and
`../../docs/runtime-parallelism.md`, these are
repository-development docs — **not** packaged into either Skill archive,
and no packaged Skill resource depends on them. The normative rule for each
concern lives in the file named for it.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`fixture-format.md`](fixture-format.md) | The canonical machine-readable format for a single benchmark case — case identity, input (inline patch or repository reference), expected findings, expected severity, expected location detail, the four typed variance constructs (same-defect alternatives, alternative findings, optional findings, permitted severity variance), required metadata including its mandatory canonical taxonomy classification, schema/versioning, and fail-closed validation. | [#50](https://github.com/amirbena/code-review-skill/issues/50) |
| [`taxonomy.md`](taxonomy.md) | The canonical, closed, alias-free benchmark candidate taxonomy — four dimensions (`capability`, `policy_contract`, `risk_mode`, `affected_surface`) each with an explicit `unclassified` member, corpus case classification metadata and its fail-closed validation, the one bounded schema-constrained PR-diff classification model call, and the deterministic non-LLM inverted index (`corpus-index.json`) that lets PR-time candidate selection narrow the corpus by lookup instead of a full scan. | [#333](https://github.com/amirbena/code-review-skill/issues/333) |
| [`selection.md`](selection.md) | The deterministic Top-K benchmark selector over #333's candidate pool — the weighted Case Relevance Score and its `primary`/`secondary`/`not-eligible` bands, the distinct Selection Coverage Score and its 60% golden threshold, the greedy coverage-maximizing bounded Top-K algorithm (`K_DEFAULT`/`K_MAX`), the explicit non-silent `insufficient-coverage` outcome, and the machine-readable explainability object published per run. Ships informational-only. | [#334](https://github.com/amirbena/code-review-skill/issues/334) |
| [`../../benchmark/corpus/README.md`](../../benchmark/corpus/README.md) | The initial benchmark corpus — a small set of `benchmark-case/v3` fixtures, one per review category (correctness, security, quality, no-op), with the case-selection rationale recorded per case and in the directory README. | [#51](https://github.com/amirbena/code-review-skill/issues/51) |
| [`runner-contract.md`](runner-contract.md) | How a benchmark run executes the reviewer over the corpus — per-case isolation into a disposable workspace, the repository-safety invariants for every protected source checkout, cleanup on success and failure, the machine-readable per-case result shape, single-case vs. whole-corpus runs, and the exit-status rule. | [#52](https://github.com/amirbena/code-review-skill/issues/52) |
| [`regression-report.md`](regression-report.md) | How a candidate run is compared against a stored baseline — the baseline result artifact, the corpus-identity guard, the per-case and aggregate deltas, the metric-free rule that separates a regression from an improvement, deterministic output, and the deliberate baseline-refresh step. | [#53](https://github.com/amirbena/code-review-skill/issues/53) |
| [`match-criteria.md`](match-criteria.md) | When a produced review finding matches an expected benchmark finding — the two match axes (location, defect), the three-valued `MATCH` / `NEAR_MISS` / `NO_MATCH` result, the fixed tolerances, and how `alternatives` / `any_of` / `match: optional` resolve. The pairing relation the [#41](https://github.com/amirbena/code-review-skill/issues/41) quality metrics are built on. | [#54](https://github.com/amirbena/code-review-skill/issues/54) |
| [`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md) | Turning match results into **missed-finding (false-negative)** and **incorrect-finding (false-positive)** counts — the deterministic produced↔expected one-to-one pairing (`MATCH` edges only, fixture document order), the per-case and aggregate counts, how `match: optional` / `any_of` / `findings_completeness` change the accounting, and how the counts render alongside the regression report's deltas without gating it. | [#55](https://github.com/amirbena/code-review-skill/issues/55) |
| [`severity-accuracy.md`](severity-accuracy.md) | Measuring, over the #55 matched set, how often a matched finding carries a permitted expected severity — the **exact** / **over-severity** / **under-severity** classification on the P0 > P1 > P2 ordinal, the `severity`-list and `any_of` member resolution, the per-case and aggregate counts with a single exact-rational exact-match rate, and how they render alongside the regression report's deltas without gating it. | [#56](https://github.com/amirbena/code-review-skill/issues/56) |
| [`duplicate-noise.md`](duplicate-noise.md) | Measuring duplicate / same-root-cause noise over a case's **produced findings alone** — the same-root-cause edge (the #54 `MATCH` cell applied to a pair of produced findings, unchanged), connected-component clustering, the redundant-finding count and its exact-rational duplicate rate per case and in aggregate, the highest-noise-cases list, and how they render alongside the regression report's deltas without gating it. | [#57](https://github.com/amirbena/code-review-skill/issues/57) |
| [`citation-fidelity.md`](citation-fidelity.md) | The mechanical **citation-existence check** — whether the file, line span, symbol, and quoted evidence a produced finding cites actually exist in the reviewed tree the runner captured; the closed `verified` / `fabricated` / `unverifiable` statuses and fixed reason order, the conservative undecidable-is-never-a-failure defaults, per-case and aggregate output as its own category beside (never inside) the match/quality metrics, and the no-gate boundary. | [#349](https://github.com/amirbena/code-review-skill/issues/349) |
| [`claim-correspondence-adequacy.md`](claim-correspondence-adequacy.md) | Research recommendation (not a contract change): whether `match-criteria.md`'s lexical claim-correspondence check can recognize an independently-phrased-but-correct finding, measured with real harness-fidelity-corrected benchmark reruns. Finds the free-text Jaccard/subset path is, in practice, the *only* path that ever decides the defect axis in production because a produced `defect_kind` is never populated, and recommends evaluating `defect_kind` population first per the deterministic-options-first guardrail. | [#343](https://github.com/amirbena/code-review-skill/issues/343) |
| [`runtime-execution-contract.md`](runtime-execution-contract.md) | The vendor-neutral runtime execution contract any benchmark runtime must satisfy — split into Class 1 (automatic/repository-triggered, untrusted-input, the original non-personal-machine trust boundary; currently unprovisioned, not further pursued) and Class 2 (maintainer-controlled, optional quality observability, never a contributor/merge prerequisite, Claude Cloud Routines as the sole selected scheduled-integration target); the shared `run_benchmark.py` → `ReviewerAdapter` → agent CLI/runtime → unmodified Skill → model backend execution chain; the runtime viability criteria per class; the required runtime/model/Skill-SHA metadata; the historical Class 1 candidate classes A–D; and the rejected approaches for both classes. | [#330](https://github.com/amirbena/code-review-skill/issues/330), revised by [#391](https://github.com/amirbena/code-review-skill/issues/391) |
| [`runtime-candidate-decision.md`](runtime-candidate-decision.md) | The empirical spike's decision record — the real candidates actually run against a small corpus subset, their results scored against `runtime-execution-contract.md`'s viability criteria and an added economic-sustainability constraint. Historical record: its conditional execution path for #337 is superseded by #391. | [#336](https://github.com/amirbena/code-review-skill/issues/336) |
| [`cloud-routine-integration.md`](../../benchmark/cloud-routine-integration.md) | The concrete Class 2 (maintainer-controlled) Claude Cloud Routine vehicle `runtime-execution-contract.md` §2.2/§8 scopes but does not implement: the `run_benchmark_routine.py` entrypoint and its smoke/selected/**sentinel**/**comprehensive**/full(deprecated)/auth-check modes, positive completion verification that never trusts a Routine's own "green" status, explicit runtime/model/SHA metadata, in-run drift confirmation and the seal to the handoff ref (no GitHub write from execution), the handoff smoke test, and why nothing in this vehicle is reachable from contributor PR automation. | [#415](https://github.com/amirbena/code-review-skill/issues/415), [#431](https://github.com/amirbena/code-review-skill/issues/431), [#470](https://github.com/amirbena/code-review-skill/issues/470) |
| [`nightly-history-and-baseline.md`](nightly-history-and-baseline.md) | Scheduling the #415 vehicle's **sentinel** (maximum gap ≤ 96 h) and **comprehensive** (maximum gap ≤ 8 d) modes as two maintainer-configured Cloud Routines; run identity, the `benchmark-history`-branch record shape (per lane, never pruned), and first-run bootstrap (amended by #467); and the chosen baseline policy (a pinned, deliberately-refreshed reference, keyed independently per lane) with the rationale for why a naive last-known-good or rolling baseline was set aside. | [#338](https://github.com/amirbena/code-review-skill/issues/338), [#431](https://github.com/amirbena/code-review-skill/issues/431) |
| [`drift-detection-and-regression-lifecycle.md`](drift-detection-and-regression-lifecycle.md) | Turning a #338 baseline-vs-candidate comparison into meaningful drift versus noise (three closed drift types over the unmodified #55/#56 metrics), a stable `{case_id, drift_type, expected_finding_key}` fingerprint, and the GitHub issue lifecycle (open once per fingerprint via a hidden marker, comment on recurrence, auto-close on resolution, a `keep-open` maintainer override) plus the machine-readable metadata every issue carries. | [#339](https://github.com/amirbena/code-review-skill/issues/339) |
| [`schedule-spec.md`](schedule-spec.md) | The repository-owned schedule spec for the scheduled sentinel/comprehensive lanes: the versioned expected-run manifest (per-lane `max_gap_hours`, the named comprehensive weekday, confirmation parameters, the origin-attestation pusher allowlist, tracking-issue slots, the `expected_from` activation instant), the thin Routine prompt spec, and the four-label set. Definitions only — provisioning, execution, and publication are separate issues. | [#469](https://github.com/amirbena/code-review-skill/issues/469) |
| [`scheduled-operations/`](scheduled-operations/README.md) | Research/design decision record for the production operating layer of the scheduled sentinel/comprehensive lanes: the execution-outside-GitHub / publication-only-App boundary, the canonical result record and its persistence, the drift-to-issue lifecycle and failure recovery, and the amendments it proposes to the #338/#339/#415/#431 contracts. Design only — nothing implemented, no existing contract changed. | [#464](https://github.com/amirbena/code-review-skill/issues/464) |
| [`benchmark-result-schema.md`](benchmark-result-schema.md) | The exact `benchmark-result/v1` sealed-record and `benchmark-receipt/v1` schemas for a scheduled run: `run_id` identity, canonical-JSON `content_sha256` sealing, per-case `fixture_digest` comparability, the conformance validator and reference fixtures, and the first record-size measurement against the growth trigger. | [#468](https://github.com/amirbena/code-review-skill/issues/468) |
| [`publication-cli.md`](publication-cli.md) | The deterministic publisher's `sweep` and `watchdog` commands: App-token-only credentials and acting identity, `--once` and `--dry-run`, the handoff file it reads, the ordered validate → persist → reconcile → announce → receipt pass with its refusal gates, publisher-authored marker recognition (A14), lane-aware drift-issue resolution (A9), recurrence links, spam bounds, and failure-table recovery; and the `watchdog`'s gap-based missed-run issues and edited-in-place health-status comment. Retires the in-Routine `GhCliIssueClient` path. | [#471](https://github.com/amirbena/code-review-skill/issues/471), [#472](https://github.com/amirbena/code-review-skill/issues/472) |
| [`shadow-validation.md`](shadow-validation.md) | Measuring whether #334's Top-K selector is trustworthy: the burn-in-sample join of a PR's selection to #339's classified nightly regressions, the case-level miss rate, the empirically-defined redundancy rate (never the selector's own always-positive marginal-coverage-gain signal), and the evidence-bar decision methodology — a process, not a hard-coded threshold, since no bar is asserted in advance of real observed data. Ships informational-only; required-gate promotion stays explicitly conditional on a future, not-currently-pursued Class 1 runtime. | [#335](https://github.com/amirbena/code-review-skill/issues/335) |

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
[`corpus/`](../../benchmark/corpus/README.md); the runner contract
([#52](https://github.com/amirbena/code-review-skill/issues/52)) is
[`runner-contract.md`](runner-contract.md); the run-to-run regression
report ([#53](https://github.com/amirbena/code-review-skill/issues/53)) is
[`regression-report.md`](regression-report.md).

## Worked example

[`../../benchmark/examples/example-case.yaml`](../../benchmark/examples/example-case.yaml) is one complete,
validated `benchmark-case/v3` fixture referenced by `fixture-format.md`
§12. It is an illustrative reference for the format, **not** a corpus case
(the corpus is #51). Its automated validation and the negative tests for
the format's rejection rules live in
[`../../tests/unit/benchmark/test_benchmark_fixture.py`](../../tests/unit/benchmark/test_benchmark_fixture.py).

## Corpus

[`corpus/`](../../benchmark/corpus/README.md) holds the initial benchmark corpus (#51):
one crafted `benchmark-case/v3` fixture per review category, each a
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
[`reference/benchmark_runner.py`](reference/benchmark_runner.py)
mirrors it and is exercised by
[`../../tests/unit/benchmark/test_benchmark_runner.py`](../../tests/unit/benchmark/test_benchmark_runner.py),
including the deliberately-dirty-source-repo safety regression. Nothing
here is packaged and no Skill launches it. A production reviewer adapter
that drives a real runtime reading the packaged `local-code-review` Skill —
as opposed to a deterministic test stub — is
[`scripts/benchmark_review_adapter.py`](scripts/benchmark_review_adapter.py),
run via the CLI entrypoint
[`scripts/run_benchmark.py`](scripts/run_benchmark.py) (#250).

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
[`reference/benchmark_report.py`](reference/benchmark_report.py)
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
[`reference/benchmark_match.py`](reference/benchmark_match.py)
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
[`reference/benchmark_metrics.py`](reference/benchmark_metrics.py)
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
[`reference/benchmark_severity.py`](reference/benchmark_severity.py)
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
[`reference/benchmark_dupes.py`](reference/benchmark_dupes.py)
mirrors it (executed by
[`../../tests/unit/benchmark/test_benchmark_dupes.py`](../../tests/unit/benchmark/test_benchmark_dupes.py),
including every §7 worked example) and consumes the single reference
matcher.

## Citation existence

[`citation-fidelity.md`](citation-fidelity.md) (#349) is a separate
mechanical check, not a #41 quality metric: for each produced finding it
asks whether the cited file, line span, symbol, and quoted evidence
*exist* in the reviewed tree — never whether the citation was inspected, and
never whether it matches a fixture. The runner captures each cited file's
text before workspace cleanup (`CaseResult.cited_sources`); a finding is
`fabricated` only when a check that could run positively fails, and
`unverifiable` (never a failure) when existence could not be decided.
`scripts/run_benchmark.py` reports it as a top-level `citation_fidelity`
key beside `metrics`; it never gates anything. The test-only reference
[`reference/benchmark_citation.py`](reference/benchmark_citation.py) mirrors
it (executed by
[`../../tests/unit/benchmark/test_benchmark_citation.py`](../../tests/unit/benchmark/test_benchmark_citation.py),
including every §7 worked example).

## Claim-correspondence matcher adequacy

[`claim-correspondence-adequacy.md`](claim-correspondence-adequacy.md)
(#343) is a **research record, not a contract change**, answering the
open question #342 left behind: once the matcher actually receives full
finding evidence and location signal, can its lexical Jaccard/subset claim
check recognize an independently-phrased-but-correct finding? Real,
harness-fidelity-corrected reruns of the three non-trivial corpus cases
found location correspondence working correctly in every run, but the
defect axis scoring `NO_MATCH` in all four executed runs — three of them
manually verified `SEMANTICALLY_EQUIVALENT` findings with rich, correct
evidence, at Jaccard scores of 0.08–0.13, well under the 0.25 `RELATED`
floor. It traces the cause to `defect_kind` (`match-criteria.md` §4.1)
never being populated on the produced side in production — the packaged
`local-code-review` rendering has no field for it — so the free-text path
`match-criteria.md` designed as a fallback is, in practice, the only path
that has ever run. It recommends, without implementing, evaluating
`defect_kind` population as the next deterministic lever per #343's
guardrail, ahead of any semantic/LLM judge.

## Retired: PR-level benchmark CI check

The dedicated, informational PR-level CI check that once wired the #250
benchmark execution into `.github/workflows/benchmark-check.yml` via a
standalone applicability classifier (`runtime_platform/benchmark/scripts/benchmark_ci_classifier.py`,
#255) has been retired
([#420](https://github.com/amirbena/code-review-skill/issues/420)): its
PR-time responsibility — deciding what a PR's changes mean for benchmark
coverage — is now owned by the canonical taxonomy/index (`taxonomy.md`,
#333) and the deterministic Top-K selector (`selection.md`, #334), which
did not exist when #255 shipped. Neither of those is a GitHub Actions
workflow, and there is no remaining independent GitHub Actions benchmark
execution path from #255. Scheduled execution and its history — split
into the sentinel (maximum gap ≤ 96 h) and comprehensive (maximum gap ≤ 8 d) lanes, #431 —
are owned by the Class 2 Cloud Routine vehicle below.

## Runtime execution contract

[`runtime-execution-contract.md`](runtime-execution-contract.md) (#330,
revised by [#391](https://github.com/amirbena/code-review-skill/issues/391))
is the foundational, vendor-neutral contract any benchmark-execution
runtime must satisfy — now split into two execution classes: **Class 1**
(automatic/repository-triggered, untrusted input — the original
non-negotiable rule that this class never runs on the maintainer's
personal machine/credentials/session under any trigger; currently
unprovisioned and not being further pursued, see
[`runtime-candidate-decision.md`](runtime-candidate-decision.md)) and
**Class 2** (maintainer-controlled, optional quality observability —
never a contributor/merge prerequisite, with Claude Cloud Routines as the
selected, and only, scheduled-integration target). Both classes share the
`run_benchmark.py` → `ReviewerAdapter` → agent CLI/runtime → unmodified
Skill → model backend execution chain, the runtime/model/Skill-SHA
metadata every result must carry, and most of the runtime viability
criteria. It picks no Class 1 runtime and implements no Class 2
integration — Class 1 candidate evaluation is #336/#366's closed
historical spike (superseding #337's provisioning), and the Class 2 Cloud
Routine integration is scoped to a future, separately-opened
implementation issue.

## Runtime candidate decision

[`runtime-candidate-decision.md`](runtime-candidate-decision.md) (#336) is
the bounded empirical spike `runtime-execution-contract.md` (#330)
required before a Class 1 runtime could be selected: it actually ran
class A (the
`claude` CLI against the Anthropic backend) and one currently-real class-B
candidate (`opencode` against a local Ollama coding model) through the
same two corpus cases via thin, throwaway adapters, and scored both
against §4's viability criteria plus an added economic-sustainability
constraint (this project's uncertain long-term maintenance means $0
recurring cost is strongly preferred, ~$40–50/month is the maintainer's
absolute ceiling, and no plausible triple-digit-monthly-spend path is
viable). Class B did not invoke the Skill's actual semantics or fit a
bounded PR-check latency budget, and is not viable in this spike's
configuration; class A is the fidelity baseline the spike recorded, but
this document's original §7 conditional recommendation to provision it
via #337 is superseded — see
[#391](https://github.com/amirbena/code-review-skill/issues/391). No
class-C candidate was available to test empirically in this environment.
A bounded follow-up screen of five more candidates (Gemini CLI, Groq,
OpenRouter free models, Cloudflare Workers AI, GitHub Copilot CLI, Amazon
Q Developer CLI) found only Gemini CLI clears the screen; its empirical
corpus run was scoped into
[#366](https://github.com/amirbena/code-review-skill/issues/366) (Parent
#336) and actually run — both cases hit provider daily-quota exhaustion
before producing a review (§8.4 of the decision record's PR, closed
without merging as
[PR #389](https://github.com/amirbena/code-review-skill/pull/389); #366
itself is closed). This evidence, and the rest of this spike, is kept as
historical record and was not reopened by #391 — see #391 for the
resulting architecture change.

## Related

The architecture map is [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md). The
cross-component architecture for turning this benchmark into a real
pre-merge quality gate and nightly drift-detection loop, and how that
relates to review execution telemetry, analytics, and repository-scoped
learning, is
[`../../docs/benchmark-measurement-architecture/README.md`](../../docs/benchmark-measurement-architecture/README.md).
