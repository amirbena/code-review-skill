# Benchmark Corpus

Repository-development artifact for GitHub Issue
[#51](https://github.com/amirbena/code-review-skill/issues/51). This
directory is the **initial benchmark corpus**: a small, deliberately
minimal set of `benchmark-case/v1` fixtures — one per review category —
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
fixture's `metadata` block (`source`, `tags`, `rationale`).

## Related sub-corpora

- [`consolidation/`](consolidation/README.md) — a focused
  `benchmark-case/v1` sub-corpus for root-cause / duplicate finding
  consolidation (Issue
  [#185](https://github.com/amirbena/code-review-skill/issues/185), parent
  [#177](https://github.com/amirbena/code-review-skill/issues/177)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/review/test_consolidation_corpus.py`](../../../tests/unit/review/test_consolidation_corpus.py)).
  The four category cases above are unaffected by it.
- [`repository-intelligence/`](repository-intelligence/README.md) — a
  focused `benchmark-case/v1` sub-corpus demonstrating
  `repository-expansion.md`'s (#87) triggers (Issue
  [#129](https://github.com/amirbena/code-review-skill/issues/129)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/review/test_repository_intelligence_corpus.py`](../../../tests/unit/review/test_repository_intelligence_corpus.py)).
- [`risk-depth/`](risk-depth/README.md) — a focused `benchmark-case/v1`
  sub-corpus for risk-based review depth and large-PR handling (Issue
  [#90](https://github.com/amirbena/code-review-skill/issues/90), parent
  [#48](https://github.com/amirbena/code-review-skill/issues/48)). Same
  format and reference validator; its own README, cases, and unit test
  ([`../../../tests/unit/review/test_risk_depth_corpus.py`](../../../tests/unit/review/test_risk_depth_corpus.py)).
  Deep depth/expansion/partitioning/coverage assertions are pinned against
  the reference models directly in
  [`../../../tests/unit/review/test_risk_based_review_scenarios.py`](../../../tests/unit/review/test_risk_based_review_scenarios.py).

## Validation

[`../../../tests/unit/benchmark/test_benchmark_corpus.py`](../../../tests/unit/benchmark/test_benchmark_corpus.py)
loads every `*.yaml` here through the single reference validator
[`../../../tests/reference/benchmark/benchmark_fixture.py`](../../../tests/reference/benchmark/benchmark_fixture.py)
(the same one that checks the worked example), and asserts the corpus stays
small, that filenames match case `id`s, that every case records a
rationale, and that the four categories above are all present. Peer review
of the expected findings themselves happens on the pull request.
