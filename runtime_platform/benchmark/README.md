# Code-Review Quality Benchmark

Repository-development contracts for the measurable code-review quality
benchmark (parent [#40](https://github.com/amirbena/code-review-skill/issues/40)):
a repeatable way to tell whether a Skill change improved or regressed
review quality against a fixed corpus.

Like [`../../docs/findings/`](../../docs/findings/README.md) and
[`../../docs/runtime-parallelism.md`](../../docs/runtime-parallelism.md), these are
repository-development docs — **not** packaged into either Skill archive,
and no packaged Skill resource depends on them. The normative rule for each
concern lives in the file named for it.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`fixture-format.md`](fixture-format.md) | The canonical machine-readable format for a single benchmark case — case identity, input (inline patch or repository reference), expected findings, expected severity, expected location detail, the four typed variance constructs (same-defect alternatives, alternative findings, optional findings, permitted severity variance), required metadata including its mandatory canonical taxonomy classification, schema/versioning, and fail-closed validation. | [#50](https://github.com/amirbena/code-review-skill/issues/50) |
| [`taxonomy.md`](taxonomy.md) | The canonical, closed, alias-free benchmark candidate taxonomy — four dimensions (`capability`, `policy_contract`, `risk_mode`, `affected_surface`) each with an explicit `unclassified` member, corpus case classification metadata and its fail-closed validation, the one bounded schema-constrained PR-diff classification model call, and the deterministic non-LLM inverted index (`corpus-index.json`) that lets PR-time candidate selection narrow the corpus by lookup instead of a full scan. | [#333](https://github.com/amirbena/code-review-skill/issues/333) |
| [`selection.md`](selection.md) | The deterministic Top-K benchmark selector over #333's candidate pool — the weighted Case Relevance Score and its `primary`/`secondary`/`not-eligible` bands, the distinct Selection Coverage Score and its 60% golden threshold, the greedy coverage-maximizing bounded Top-K algorithm (`K_DEFAULT`/`K_MAX`), the explicit non-silent `insufficient-coverage` outcome, and the machine-readable explainability object published per run. Ships informational-only. | [#334](https://github.com/amirbena/code-review-skill/issues/334) |
| [`corpus/README.md`](../../docs/benchmark/corpus/README.md) | The initial benchmark corpus — a small set of `benchmark-case/v2` fixtures, one per review category (correctness, security, quality, no-op), with the case-selection rationale recorded per case and in the directory README. | [#51](https://github.com/amirbena/code-review-skill/issues/51) |
| [`runner-contract.md`](runner-contract.md) | How a benchmark run executes the reviewer over the corpus — per-case isolation into a disposable workspace, the repository-safety invariants for every protected source checkout, cleanup on success and failure, the machine-readable per-case result shape, single-case vs. whole-corpus runs, and the exit-status rule. | [#52](https://github.com/amirbena/code-review-skill/issues/52) |
| [`regression-report.md`](regression-report.md) | How a candidate run is compared against a stored baseline — the baseline result artifact, the corpus-identity guard, the per-case and aggregate deltas, the metric-free rule that separates a regression from an improvement, deterministic output, and the deliberate baseline-refresh step. | [#53](https://github.com/amirbena/code-review-skill/issues/53) |
| [`match-criteria.md`](match-criteria.md) | When a produced review finding matches an expected benchmark finding — the two match axes (location, defect), the three-valued `MATCH` / `NEAR_MISS` / `NO_MATCH` result, the fixed tolerances, and how `alternatives` / `any_of` / `match: optional` resolve. The pairing relation the [#41](https://github.com/amirbena/code-review-skill/issues/41) quality metrics are built on. | [#54](https://github.com/amirbena/code-review-skill/issues/54) |
| [`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md) | Turning match results into **missed-finding (false-negative)** and **incorrect-finding (false-positive)** counts — the deterministic produced↔expected one-to-one pairing (`MATCH` edges only, fixture document order), the per-case and aggregate counts, how `match: optional` / `any_of` / `findings_completeness` change the accounting, and how the counts render alongside the regression report's deltas without gating it. | [#55](https://github.com/amirbena/code-review-skill/issues/55) |
| [`severity-accuracy.md`](severity-accuracy.md) | Measuring, over the #55 matched set, how often a matched finding carries a permitted expected severity — the **exact** / **over-severity** / **under-severity** classification on the P0 > P1 > P2 ordinal, the `severity`-list and `any_of` member resolution, the per-case and aggregate counts with a single exact-rational exact-match rate, and how they render alongside the regression report's deltas without gating it. | [#56](https://github.com/amirbena/code-review-skill/issues/56) |
| [`duplicate-noise.md`](duplicate-noise.md) | Measuring duplicate / same-root-cause noise over a case's **produced findings alone** — the same-root-cause edge (the #54 `MATCH` cell applied to a pair of produced findings, unchanged), connected-component clustering, the redundant-finding count and its exact-rational duplicate rate per case and in aggregate, the highest-noise-cases list, and how they render alongside the regression report's deltas without gating it. | [#57](https://github.com/amirbena/code-review-skill/issues/57) |
| [`claim-correspondence-adequacy.md`](claim-correspondence-adequacy.md) | Research recommendation (not a contract change): whether `match-criteria.md`'s lexical claim-correspondence check can recognize an independently-phrased-but-correct finding, measured with real harness-fidelity-corrected benchmark reruns. Finds the free-text Jaccard/subset path is, in practice, the *only* path that ever decides the defect axis in production because a produced `defect_kind` is never populated, and recommends evaluating `defect_kind` population first per the deterministic-options-first guardrail. | [#343](https://github.com/amirbena/code-review-skill/issues/343) |
| [`runtime-execution-contract.md`](runtime-execution-contract.md) | The vendor-neutral runtime execution contract any benchmark runtime must satisfy — split into Class 1 (automatic/repository-triggered, untrusted-input, the original non-personal-machine trust boundary; currently unprovisioned, not further pursued) and Class 2 (maintainer-controlled, optional quality observability, never a contributor/merge prerequisite, Claude Cloud Routines as the sole selected scheduled-integration target); the shared `run_benchmark.py` → `ReviewerAdapter` → agent CLI/runtime → unmodified Skill → model backend execution chain; the runtime viability criteria per class; the required runtime/model/Skill-SHA metadata; the historical Class 1 candidate classes A–D; and the rejected approaches for both classes. | [#330](https://github.com/amirbena/code-review-skill/issues/330), revised by [#391](https://github.com/amirbena/code-review-skill/issues/391) |
| [`runtime-candidate-decision.md`](runtime-candidate-decision.md) | The empirical spike's decision record — the real candidates actually run against a small corpus subset, their results scored against `runtime-execution-contract.md`'s viability criteria and an added economic-sustainability constraint. Historical record: its conditional execution path for #337 is superseded by #391. | [#336](https://github.com/amirbena/code-review-skill/issues/336) |
| [`cloud-routine-integration.md`](../../docs/benchmark/cloud-routine-integration.md) | The concrete Class 2 (maintainer-controlled) Claude Cloud Routine vehicle `runtime-execution-contract.md` §2.2/§8 scopes but does not implement: the `run_benchmark_routine.py` entrypoint and its smoke/selected/**sentinel**/**comprehensive**/full(deprecated)/auth-check modes, positive completion verification that never trusts a Routine's own "green" status, explicit runtime/model/SHA metadata, evidence persisted as tracking-Issue comments instead of the Routine's own transcript, the GitHub auth/issue-permission smoke test, and why nothing in this vehicle is reachable from contributor PR automation. | [#415](https://github.com/amirbena/code-review-skill/issues/415), [#431](https://github.com/amirbena/code-review-skill/issues/431) |
| [`nightly-history-and-baseline.md`](nightly-history-and-baseline.md) | Scheduling the #415 vehicle's **sentinel** (maximum gap ≤ 96 h) and **comprehensive** (maximum gap ≤ 8 d) modes as two maintainer-configured Cloud Routines; run identity, the `benchmark-history`-branch record shape (per lane, never pruned), and first-run bootstrap (amended by #467); and the chosen baseline policy (a pinned, deliberately-refreshed reference, keyed independently per lane) with the rationale for why a naive last-known-good or rolling baseline was set aside. | [#338](https://github.com/amirbena/code-review-skill/issues/338), [#431](https://github.com/amirbena/code-review-skill/issues/431) |
| [`drift-detection-and-regression-lifecycle.md`](drift-detection-and-regression-lifecycle.md) | Turning a #338 baseline-vs-candidate comparison into meaningful drift versus noise (three closed drift types over the unmodified #55/#56 metrics), a stable `{case_id, drift_type, expected_finding_key}` fingerprint, and the GitHub issue lifecycle (open once per fingerprint via a hidden marker, comment on recurrence, auto-close on resolution, a `keep-open` maintainer override) plus the machine-readable metadata every issue carries. | [#339](https://github.com/amirbena/code-review-skill/issues/339) |
| [`scheduled-operations/`](scheduled-operations/README.md) | Research/design decision record for the production operating layer of the scheduled sentinel/comprehensive lanes: the execution-outside-GitHub / publication-only-App boundary, the canonical result record and its persistence, the drift-to-issue lifecycle and failure recovery, and the amendments it proposes to the #338/#339/#415/#431 contracts. Design only — nothing implemented, no existing contract changed. | [#464](https://github.com/amirbena/code-review-skill/issues/464) |
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
[`corpus/`](../../docs/benchmark/corpus/README.md); the runner contract
([#52](https://github.com/amirbena/code-review-skill/issues/52)) is
[`runner-contract.md`](runner-contract.md); the run-to-run regression
report ([#53](https://github.com/amirbena/code-review-skill/issues/53)) is
[`regression-report.md`](regression-report.md).

## Worked example

[`examples/example-case.yaml`](../../docs/benchmark/examples/example-case.yaml) is one complete,
validated `benchmark-case/v2` fixture referenced by `fixture-format.md`
§12. It is an illustrative reference for the format, **not** a corpus case
(the corpus is #51). Its automated validation and the negative tests for
the format's rejection rules live in
[`../../tests/unit/benchmark/test_benchmark_fixture.py`](../../tests/unit/benchmark/test_benchmark_fixture.py).

## Corpus

[`corpus/`](../../docs/benchmark/corpus/README.md) holds the initial benchmark corpus (#51):
one crafted `benchmark-case/v2` fixture per review category, each a
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

## Senior voice examples

[`senior-voice-examples.md`](../../docs/benchmark/senior-voice-examples.md) (issue
[#231](https://github.com/amirbena/code-review-skill/issues/231), design
record [#229](https://github.com/amirbena/code-review-skill/issues/229))
is a **documented reference set, not a CI gate**, unlike everything above:
eight findings paired as their structured and senior-voice renderings,
demonstrating the voice principles owned by
[`../../shared/templates/finding-rendering.md`](../../shared/templates/finding-rendering.md),
"Senior voice contract". It measures presentation quality, which the
#40/#41 corpus and metrics above do not.

## Reviewer Brief benchmark

[`corpus/reviewer-brief/README.md`](../../docs/benchmark/corpus/reviewer-brief/README.md)
(issue [#309](https://github.com/amirbena/code-review-skill/issues/309),
depends on [#304](https://github.com/amirbena/code-review-skill/issues/304))
pins the semantic quality and publication isolation of the private,
caller-facing `Reviewer Brief` every `github-pr-review` result includes.
Unlike every corpus above, it is not `benchmark-case/v2` fixtures — that
schema has no field for a private prose artifact or for a second,
GitHub-bound surface to compare it against — so it follows the
test-only-reference-model pattern instead:
[`reference/reviewer_brief_fixtures.py`](reference/reviewer_brief_fixtures.py),
exercised by
[`../../tests/unit/benchmark/test_reviewer_brief_structural.py`](../../tests/unit/benchmark/test_reviewer_brief_structural.py)
(deterministic structural properties) and
[`../../tests/unit/benchmark/test_reviewer_brief_publication_isolation.py`](../../tests/unit/benchmark/test_reviewer_brief_publication_isolation.py)
(zero-leakage into the GitHub-bound review body/inline comments, including
a negative canary proving the check can catch a real leak). The
semantic-quality properties whose wording is intentionally flexible are a
documented, non-CI-gated reference set,
[`reviewer-brief-examples.md`](../../docs/benchmark/reviewer-brief-examples.md), exactly like
the senior voice examples below.

## Agent-spawn / delegation benchmark

[`corpus/delegation-spawn/README.md`](../../docs/benchmark/corpus/delegation-spawn/README.md)
(issue [#307](https://github.com/amirbena/code-review-skill/issues/307),
depends on [#303](https://github.com/amirbena/code-review-skill/issues/303))
proves the agent-spawn and delegated-authority capability boundary stays
bounded: no `spawn_agent` capability, invocation agent-count/spawn-depth
budgets, the capability-subset delegation rule, non-transferable
mutation/formal-review-action authorization, sibling-collusion
resistance, and confused-deputy protection. Like the Reviewer Brief
benchmark below, it is not `benchmark-case/v2` fixtures — that schema has
no field for a capability grant, a spawn-depth/agent-count budget, or a
structural allow/deny result — so it follows the same test-only
reference-model pattern:
[`reference/delegation_fixtures.py`](reference/delegation_fixtures.py),
exercised by
[`../../tests/unit/benchmark/test_delegation_spawn_corpus.py`](../../tests/unit/benchmark/test_delegation_spawn_corpus.py)
(structural allow/deny assertions against the single reference model,
corpus-completeness checks against every `DELEG-###`/tagged `DOS-###`
threat-scenario id, and malformed-fixture rejection). Every comparison is
a deterministic structural assertion — never an LLM/rubric score — and
the corpus is disjoint from the finding-precision/recall/severity
metrics above and from ordinary code-review quality fixtures.

## Trusted-host natural-language authorization benchmark

[`corpus/trusted-host-nl-authorization/README.md`](../../docs/benchmark/corpus/trusted-host-nl-authorization/README.md)
(issue [#370](https://github.com/amirbena/code-review-skill/issues/370),
depends on [#369](https://github.com/amirbena/code-review-skill/issues/369))
proves natural-language `allow_trusted_host_execution` authorization
resolves by **semantic intent, not literal phrase-matching**: canonical
structured authorization, direct and several differently-worded
affirmative requests, the full explicit-denial vocabulary, ambiguous
phrasing and descriptive/policy-quoting mentions that must never be
mistaken for a grant, repository-controlled and malicious-instruction-file
attempts, PR-content escalation and delegated-agent report-back attempts,
authorization non-persistence across invocations, conflicting positive/
negative instructions resolving toward denial, and sandbox-preferred
selection holding regardless of authorization presence. Like the
Agent-spawn / delegation benchmark above, it is not `benchmark-case/v2`
fixtures — that schema has no field for a resolved authorization boolean
or an execution-backend provenance value — so it follows the same
test-only reference-model pattern:
[`reference/trusted_host_nl_fixtures.py`](reference/trusted_host_nl_fixtures.py),
exercised by
[`../../tests/unit/benchmark/test_trusted_host_nl_authorization_corpus.py`](../../tests/unit/benchmark/test_trusted_host_nl_authorization_corpus.py)
(structural resolved/provenance assertions against the single reference
model in `tests/reference/review/runtime_validation.py`, required-category
and required-coverage-tag completeness, a canary proving the
repository/malicious-file rejection has genuine detection power, and
malformed-fixture rejection). Every comparison is a deterministic
structural assertion — never an LLM/rubric score — and the corpus is
disjoint from the finding-precision/recall/severity metrics above and
from ordinary code-review quality fixtures. It does not re-test #367's
structured-flag-only behavior or #302's sandbox isolation guarantees,
which already have their own coverage.

## Publication-mode benchmark

[`corpus/publication-mode/README.md`](../../docs/benchmark/corpus/publication-mode/README.md)
(issue [#316](https://github.com/amirbena/code-review-skill/issues/316),
depends on [#314](https://github.com/amirbena/code-review-skill/issues/314))
proves the passive/semi/active review-publication boundary #314
established stays bounded: mode resolution, publication intent,
formal-action selection, actual GitHub-bound side-effect presence or
absence, semi/active semantic equivalence before publication, the
self-review boundary across every mode, the review-publication-only
authority boundary, and a small bounded set of equivalent invocation
phrasings — including a stable, named fixture reproducing the PR #297
regression shape (an explicit `ACTIVE` request with a clean, otherwise-
publishable review must never resolve to a withheld mutation for a
missing second activation signal). Like the two benchmarks above, it is
not `benchmark-case/v2` fixtures — that schema has no field for a
publication mode, a "would publish" preview, or a GitHub-bound
publication artifact — so it follows the same test-only reference-model
pattern:
[`reference/publication_mode_fixtures.py`](reference/publication_mode_fixtures.py),
exercised by
[`../../tests/unit/benchmark/test_publication_mode_corpus.py`](../../tests/unit/benchmark/test_publication_mode_corpus.py).
Uniquely among the corpora above, it constructs and inspects the actual
GitHub-bound publication artifact (`body` + inline comments + `event`, or
the narrower self-review informational `COMMENT`) rather than only the
resolver's `MutationOutcome` — a caller-facing sentence that nothing was
posted is not, by itself, evidence. Every comparison is a deterministic
structural assertion, and the corpus is disjoint from the
finding-precision/recall/severity metrics above and from ordinary
code-review quality fixtures.

## Mutation-capability-boundary benchmark

[`corpus/mutation-boundary/README.md`](../../docs/benchmark/corpus/mutation-boundary/README.md)
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
benchmark above, it is not `benchmark-case/v2` fixtures — that schema has
no field for a requested capability, an authorization scope/state, or a
structural allow/deny result with an expected post-action repository/Git
state — so it follows the same test-only reference-model pattern:
[`reference/mutation_fixtures.py`](reference/mutation_fixtures.py),
exercised by
[`../../tests/unit/benchmark/test_mutation_boundary_corpus.py`](../../tests/unit/benchmark/test_mutation_boundary_corpus.py)
(structural allow/deny assertions against the single reference model, run
in a real disposable temporary Git repository per case, corpus-
completeness checks against every `AUTH-###` threat-scenario id excluding
`AUTH-014`, and malformed-fixture rejection). Every comparison is a
deterministic structural assertion — never an LLM/rubric score — and the
corpus is disjoint from the finding-precision/recall/severity metrics
above and from ordinary code-review quality fixtures.

## Denied-capability security-event benchmark

[`corpus/security-events/README.md`](../../docs/benchmark/corpus/security-events/README.md)
(issue [#308](https://github.com/amirbena/code-review-skill/issues/308),
depends on [#299](https://github.com/amirbena/code-review-skill/issues/299)
and the relevant enforced denial from
[#301](https://github.com/amirbena/code-review-skill/issues/301) /
[#302](https://github.com/amirbena/code-review-skill/issues/302) /
[#303](https://github.com/amirbena/code-review-skill/issues/303)) proves
the **emitted #299 security event**, not the allow/deny decision the
mutation-boundary, sandbox-adversarial, and agent-spawn/delegation
benchmarks above already prove: given a real enforced denial, its
`SecurityEvent` carries a deterministic `event_type` from the closed
taxonomy, the correct `expected_denial` /
`boundary_violation_attempt` classification, invocation and
parent/child correlation where relevant, the target/scope identifiers
the domain calls for, and none of the content #299 forbids (a secret,
token, credential value, raw prompt, or full patch body). Like the two
benchmarks above, it is not `benchmark-case/v2` fixtures — that schema
has no field for an event schema, a classification, or a redaction
assertion — so it follows the same test-only reference-model pattern:
[`reference/security_event_fixtures.py`](reference/security_event_fixtures.py),
exercised by
[`../../tests/unit/benchmark/test_security_event_corpus.py`](../../tests/unit/benchmark/test_security_event_corpus.py)
(per-family coverage, closed-vocabulary drift checks against
`scripts/security/validate_threat_model.py`, determinism, redaction, the
observational-only invariant proving recording never perturbs
findings/severity/verdict, threat-scenario/enforcement-owner
traceability, and malformed-fixture rejection). Every comparison is a
deterministic structural assertion — never an LLM/rubric score — and the
corpus is disjoint from the finding-precision/recall/severity metrics
above and from ordinary code-review quality fixtures.

## Verdict-consistency benchmark

[`corpus/verdict-consistency/README.md`](../../docs/benchmark/corpus/verdict-consistency/README.md)
(issue [#378](https://github.com/amirbena/code-review-skill/issues/378),
depends on [#377](https://github.com/amirbena/code-review-skill/issues/377))
proves the shared verdict-consistency comparator #377 built from #351's
design record actually withholds a mismatched rendered or submitted
decision signal before it can be returned or published — a deliberately
adversarial corpus, distinct from
[#350](https://github.com/amirbena/code-review-skill/issues/350)'s
normal-path proof that a real blocking finding correctly *derives* a
blocking verdict. Coverage spans all four reconciliation points
`shared/policies/verdict-consistency.md` names: `local-code-review`
pre-render, `github-pr-review` PASSIVE/SEMI pre-render, `github-pr-review`
ACTIVE pre-render, and `github-pr-review` ACTIVE pre-publish against the
literal GitHub review API `event` — including the required highest-risk
blocking-findings → clean/`Approve` mismatch at each point, a case
proving the pre-publish point independently catches a silent drift
introduced after the pre-render point already passed, the `REVIEW
INCOMPLETE` carve-out under adversarial drift (a mismatch that happens to
involve the carve-out is still caught, never misclassified as it), and
control cases proving a genuinely consistent signal is never withheld.
Like the benchmarks above, it is not `benchmark-case/v2` fixtures — that
schema has no field for an already-finalized decision, a drifted
rendered/submitted signal, or a withheld-artifact outcome — so it follows
the same test-only reference-model pattern:
[`reference/verdict_consistency_fixtures.py`](reference/verdict_consistency_fixtures.py),
exercised by
[`../../tests/unit/benchmark/test_verdict_consistency_corpus.py`](../../tests/unit/benchmark/test_verdict_consistency_corpus.py)
(structural withhold/emit assertions against the single real comparator
in `tests/reference/review/verdict_consistency.py`, an `Observed`-shape
invariant rejecting both a self-corrected two-artifact outcome and a
silently-skipped zero-artifact outcome, reconciliation-point completeness
checks, and malformed-fixture rejection). Every comparison is a
deterministic structural assertion — never an LLM/rubric score — and the
corpus is disjoint from the finding-precision/recall/severity metrics
above and from ordinary code-review quality fixtures. It does not
re-test #377's own comparator unit suite, which already proves the raw
functions mechanically in isolation, and it does not redesign or
re-derive `severity.md`'s decision semantics.

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
