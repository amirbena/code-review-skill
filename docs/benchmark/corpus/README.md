# Benchmark Corpus

Repository-development artifact for GitHub Issue
[#51](https://github.com/amirbena/code-review-skill/issues/51). This
directory is the **initial benchmark corpus**: a small, deliberately
minimal set of `benchmark-case/v2` fixtures — one per review category —
plus the case-selection rationale for each. Parent capability:
[#40](https://github.com/amirbena/code-review-skill/issues/40).

Every case conforms to
[`../fixture-format.md`](../fixture-format.md). Like the rest of
[`../`](../README.md) this is **not** packaged into either Skill archive
and no packaged Skill resource depends on it. The corpus is consumed only
by the repository's own test suite today, through the runner contract
([#52](https://github.com/amirbena/code-review-skill/issues/52),
[`../runner-contract.md`](../runner-contract.md)) and the run-to-run
regression report
([#53](https://github.com/amirbena/code-review-skill/issues/53),
[`../regression-report.md`](../regression-report.md)); neither is packaged
and no Skill launches either.

## Two scheduled execution lanes (#431)

The **4 cases in this directory** (below) are the permanent **sentinel**
corpus — never rotated, sampled, or Top-K'd — scheduled every 3 days. The
files in this directory **plus every `benchmark-case/v2` fixture in every
sub-corpus directory listed under "Related sub-corpora"** (excluding a
handful of test-only/reference-model suites that hold no `benchmark-
case/v2` fixtures at all — see below) together form the **comprehensive**
corpus, scheduled weekly, and discovered *programmatically* by
`scripts/benchmark/benchmark_corpus_membership.py` — never a hard-coded
count. Both lanes execute through the same `run_benchmark_routine.py`
Class 2 Cloud Routine vehicle, with independently keyed history and
baselines. Full scheduling/baseline contract:
[`../nightly-history-and-baseline.md`](../nightly-history-and-baseline.md)
§2/§4; mode contract:
[`../cloud-routine-integration.md`](../cloud-routine-integration.md) §2.1.

A sub-corpus directory that holds only a `README.md` and no `benchmark-
case/v2` fixture YAML (e.g. `mutation-boundary/`, `reviewer-brief/`,
`delegation-spawn/`, `sandbox-adversarial/`,
`trusted-host-nl-authorization/`, `security-events/`,
`publication-mode/`, `verdict-consistency/`) is a specialized test-only or
real-runner suite consumed directly by `tests/` rather than through
`ProductionReviewerAdapter` — it is excluded from the comprehensive lane
by construction (the membership scan finds no fixture to include), never
by a maintained denylist.

## Selection principle

- **One case per review category** the roadmap cares about — correctness,
  security, quality, and a no-op — so a regression in any one category
  surfaces.
- **Each case isolates its category.** The correctness case has no security
  or style angle; the quality case is safe and correct; the no-op changes
  nothing. A miss is therefore unambiguous.
- **Crafted, self-contained inline patches.** Every case ships an
  `input.patch` plus the `input.base` pre-image it applies onto, so the
  corpus is runnable without network access and is not blocked on whether
  the runner (#52) supports `repo_ref` inputs.
- **Distinct from the worked example.** The security case is command
  injection, a different sink from the example's SQL injection, so the two
  do not overlap. [`../examples/example-case.yaml`](../examples/example-case.yaml)
  is a format reference, never a corpus case.
- **Intentionally small.** Non-goals (from #51): hundreds of fixtures,
  exhaustive coverage, synthetic bulk generation. Growth is per-category
  and deliberate.
- **`exhaustive` completeness, with test-gap notes made explicit.** Every
  case uses the default `findings_completeness: exhaustive`, so a reviewer
  finding outside the expected set is an unexpected finding. Where the
  seeded change plausibly warrants a regression/security test, that
  observation is carried as an `optional` finding (severity `P1` or `P2`),
  mirroring the worked example — so a review that correctly asks for a
  test is neither required to nor penalised for raising it.

## Cases

| File | Category | Input | A correct review must… | Decision |
|---|---|---|---|---|
| [`correctness-off-by-one-pagination.yaml`](correctness-off-by-one-pagination.yaml) | correctness | refactor of a pagination helper adds `+ 1` to the slice end | report one **P1** off-by-one: every page returns one row that also appears on the next page (an `optional` missing-regression-test note is also acceptable) | `changes-required` |
| [`security-command-injection.yaml`](security-command-injection.yaml) | security | argument-vector `subprocess` call becomes a `shell=True` string built from an untrusted `name` | report one **P0** command injection (acceptably on the `subprocess.run` call **or** the f-string that feeds it; an `optional` missing-security-test note is also acceptable) | `changes-required` |
| [`quality-duplicated-branch-logic.yaml`](quality-duplicated-branch-logic.yaml) | quality | a new `sms` dispatch branch copy-pastes `format_message(user)` from the `email` branch | report one **P2** duplication and still return `clean` — the change is correct and safe | `clean` |
| [`no-op-comment-and-rename.yaml`](no-op-comment-and-rename.yaml) | no-op | a docstring is added and a local variable renamed; behaviour is identical (the pre-image already uses `math.pi`, so the touched line has nothing flag-worthy) | report **nothing** (`findings: []`, `findings_completeness: exhaustive`) | `clean` |

Per-case provenance and a one-paragraph rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`), alongside its
mandatory canonical taxonomy classification (`metadata.taxonomy`) —
see [`../taxonomy.md`](../taxonomy.md) and
[`../fixture-format.md`](../fixture-format.md) §10.1.

## Related sub-corpora

- [`consolidation/`](consolidation/README.md) — a focused
  `benchmark-case/v2` sub-corpus for root-cause / duplicate finding
  consolidation (Issue
  [#185](https://github.com/amirbena/code-review-skill/issues/185), parent
  [#177](https://github.com/amirbena/code-review-skill/issues/177)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/review/root_cause/test_consolidation_corpus.py`](../../../tests/unit/review/root_cause/test_consolidation_corpus.py)).
  The four category cases above are unaffected by it.
- [`repository-intelligence/`](repository-intelligence/README.md) — a
  focused `benchmark-case/v2` sub-corpus demonstrating
  `repository-expansion.md`'s (#87) triggers (Issue
  [#129](https://github.com/amirbena/code-review-skill/issues/129)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/review/repository_intelligence/test_repository_intelligence_corpus.py`](../../../tests/unit/review/repository_intelligence/test_repository_intelligence_corpus.py)).
- [`risk-depth/`](risk-depth/README.md) — a focused `benchmark-case/v2`
  sub-corpus for risk-based review depth and large-PR handling (Issue
  [#90](https://github.com/amirbena/code-review-skill/issues/90), parent
  [#48](https://github.com/amirbena/code-review-skill/issues/48)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/review/specialist_depth/test_risk_depth_corpus.py`](../../../tests/unit/review/specialist_depth/test_risk_depth_corpus.py)).
  Deep depth/expansion/partitioning/coverage assertions are pinned against
  the reference models directly in
  [`../../../tests/unit/review/specialist_depth/test_risk_based_review_scenarios.py`](../../../tests/unit/review/specialist_depth/test_risk_based_review_scenarios.py).
- [`semantic-implication/`](semantic-implication/README.md) — a focused
  `benchmark-case/v2` sub-corpus for the base semantic change-implication
  reasoning pass (Issue
  [#211](https://github.com/amirbena/code-review-skill/issues/211)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/review/root_cause/test_semantic_implication_corpus.py`](../../../tests/unit/review/root_cause/test_semantic_implication_corpus.py)).
- [`null-absence-risk/`](null-absence-risk/README.md) — a focused
  `benchmark-case/v2` sub-corpus for the cross-language null-like
  absence-risk review requirement (Issue
  [#121](https://github.com/amirbena/code-review-skill/issues/121)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/review/root_cause/test_null_absence_corpus.py`](../../../tests/unit/review/root_cause/test_null_absence_corpus.py)).
- [`api-compatibility/`](api-compatibility/README.md) — a focused
  `benchmark-case/v2` sub-corpus pinning the expected compatible /
  breaking / context-dependent classification for the API / contract
  compatibility review capability (Issue
  [#184](https://github.com/amirbena/code-review-skill/issues/184), parent
  [#175](https://github.com/amirbena/code-review-skill/issues/175)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/benchmark/test_api_compatibility_corpus.py`](../../../tests/unit/benchmark/test_api_compatibility_corpus.py)).
- [`security-deepening/`](security-deepening/README.md) — a focused
  `benchmark-case/v2` sub-corpus pinning representative outcomes for the
  Security deepening specialist-depth capability (Issue
  [#271](https://github.com/amirbena/code-review-skill/issues/271), parent
  [#83](https://github.com/amirbena/code-review-skill/issues/83)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/benchmark/test_security_deepening_corpus.py`](../../../tests/unit/benchmark/test_security_deepening_corpus.py)).
- [`distributed-systems-deepening/`](distributed-systems-deepening/README.md) —
  a focused `benchmark-case/v2` sub-corpus pinning representative
  outcomes for the Distributed Systems deepening specialist-depth
  capability (Issue
  [#272](https://github.com/amirbena/code-review-skill/issues/272), parent
  [#84](https://github.com/amirbena/code-review-skill/issues/84)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/benchmark/test_distributed_systems_deepening_corpus.py`](../../../tests/unit/benchmark/test_distributed_systems_deepening_corpus.py)).
- [`database-migration-deepening/`](database-migration-deepening/README.md) —
  a focused `benchmark-case/v2` sub-corpus pinning representative
  outcomes for the Database / Migration deepening specialist-depth
  capability (Issue
  [#186](https://github.com/amirbena/code-review-skill/issues/186), parent
  [#179](https://github.com/amirbena/code-review-skill/issues/179)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/benchmark/test_database_migration_deepening_corpus.py`](../../../tests/unit/benchmark/test_database_migration_deepening_corpus.py)).
- [`performance-deepening/`](performance-deepening/README.md) — a focused
  `benchmark-case/v2` sub-corpus pinning representative outcomes for the
  Performance deepening specialist-depth capability (Issue
  [#187](https://github.com/amirbena/code-review-skill/issues/187), parent
  [#180](https://github.com/amirbena/code-review-skill/issues/180)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/benchmark/test_performance_deepening_corpus.py`](../../../tests/unit/benchmark/test_performance_deepening_corpus.py)).
- [`dependency-supply-chain-deepening/`](dependency-supply-chain-deepening/README.md) —
  a focused `benchmark-case/v2` sub-corpus pinning representative
  outcomes for the Dependency / Supply-Chain deepening specialist-depth
  capability (Issue
  [#188](https://github.com/amirbena/code-review-skill/issues/188), parent
  [#181](https://github.com/amirbena/code-review-skill/issues/181)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/benchmark/test_dependency_supply_chain_deepening_corpus.py`](../../../tests/unit/benchmark/test_dependency_supply_chain_deepening_corpus.py)).

- [`analogue-placement-pattern/`](analogue-placement-pattern/README.md) —
  a focused `benchmark-case/v2` sub-corpus proving recall and
  false-positive resistance for the analogue-based responsibility/
  placement pattern inference capability (Issue
  [#328](https://github.com/amirbena/code-review-skill/issues/328), parent
  [#327](https://github.com/amirbena/code-review-skill/issues/327)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/benchmark/test_analogue_placement_pattern_corpus.py`](../../../tests/unit/benchmark/test_analogue_placement_pattern_corpus.py)).

- [`specialist-depth-composition/`](specialist-depth-composition/README.md) —
  a focused `benchmark-case/v2` sub-corpus pinning the architecture-level
  activation/composition/boundedness contract
  [`specialist-depth.md`](../../../shared/policies/specialist-depth.md)
  (#82) defines across 0..N domain-specific deepening capabilities (Issue
  [#85](https://github.com/amirbena/code-review-skill/issues/85), parent
  [#47](https://github.com/amirbena/code-review-skill/issues/47)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/benchmark/test_specialist_depth_composition_corpus.py`](../../../tests/unit/benchmark/test_specialist_depth_composition_corpus.py)).
  Reuses fixtures from the Security (#271), Database/Migration (#186),
  and Performance (#187) sub-corpora above as integration inputs rather
  than re-deriving their domain correctness.

- [`specialist-depth-progressive-loading-proof/`](specialist-depth-progressive-loading-proof/README.md) —
  a focused `benchmark-case/v2` sub-corpus (one net-new case) proving
  `specialist-depth`'s conditional, fail-closed loading (Issue
  [#411](https://github.com/amirbena/code-review-skill/issues/411),
  parent [#403](https://github.com/amirbena/code-review-skill/issues/403))
  behaviorally, not just at the text/manifest level #410 already pins.
  Same format and reference validator; its own README, one case, and unit
  test
  ([`../../../tests/unit/benchmark/test_specialist_depth_progressive_loading_proof_corpus.py`](../../../tests/unit/benchmark/test_specialist_depth_progressive_loading_proof_corpus.py)).
  Reuses `specialist-depth-composition/`'s Case A and Case B by id for
  the "not needed" / "must activate" required cases rather than
  re-declaring them.

- [`sandbox-adversarial/`](sandbox-adversarial/README.md) — not a
  `benchmark-case/v2` corpus (see its README for why): the real-runner
  adversarial security-boundary benchmark for the runtime-validation
  sandbox (Issue [#306](https://github.com/amirbena/code-review-skill/issues/306),
  parent [#302](https://github.com/amirbena/code-review-skill/issues/302)),
  kept separate from finding precision/recall metrics. Cases execute
  [`../../../tests/integration/sandbox/test_adversarial_containment.py`](../../../tests/integration/sandbox/test_adversarial_containment.py)
  against the real sandbox runner.

- [`candidate-finding-validation/`](candidate-finding-validation/README.md) —
  a focused `benchmark-case/v2` sub-corpus pinning the precision of the
  candidate-finding-validation reasoning contract
  [`candidate-finding-validation-model.md`](../../candidate-finding-validation/candidate-finding-validation-model.md)
  defines (Issue [#383](https://github.com/amirbena/code-review-skill/issues/383),
  parent [#382](https://github.com/amirbena/code-review-skill/issues/382)).
  Same format and reference validator; its own README, cases, and unit
  test
  ([`../../../tests/unit/review/root_cause/test_candidate_finding_validation_corpus.py`](../../../tests/unit/review/root_cause/test_candidate_finding_validation_corpus.py)).
  Includes a real-world-derived scenario sourced from PR
  [#390](https://github.com/amirbena/code-review-skill/pull/390).

- [`finding-placement/`](finding-placement/README.md) — a focused
  `benchmark-case/v2` sub-corpus proving correct primary fix/action
  location selection for the "Deriving the fix/action location" reasoning
  in
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md)
  (Issue [#387](https://github.com/amirbena/code-review-skill/issues/387),
  parent [#385](https://github.com/amirbena/code-review-skill/issues/385),
  implementation contract
  [#386](https://github.com/amirbena/code-review-skill/issues/386)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/benchmark/test_finding_placement_corpus.py`](../../../tests/unit/benchmark/test_finding_placement_corpus.py)).
  Consumes, never duplicates,
  [`../../../skills/github-pr-review/policies/finding-placement.md`](../../../skills/github-pr-review/policies/finding-placement.md)'s
  (#164) existing anchor-selection/transport fixtures.

## Validation

[`../../../tests/unit/benchmark/test_benchmark_corpus.py`](../../../tests/unit/benchmark/test_benchmark_corpus.py)
loads every `*.yaml` here through the single reference validator
[`../../../tests/reference/benchmark/benchmark_fixture.py`](../../../tests/reference/benchmark/benchmark_fixture.py)
(the same one that checks the worked example), and asserts the corpus stays
small, that filenames match case `id`s, that every case records a
rationale, and that the four categories above are all present. Peer review
of the expected findings themselves happens on the pull request.

[`../../../tests/unit/benchmark/test_benchmark_corpus_membership.py`](../../../tests/unit/benchmark/test_benchmark_corpus_membership.py)
covers the comprehensive-lane membership scan itself (#431): every
sub-corpus directory's `benchmark-case/v2` fixtures are included, a
`README.md`-only test-suite directory contributes nothing, and a duplicate
case `id` across two fixtures is a hard error.
