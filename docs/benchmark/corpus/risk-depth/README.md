# Risk-Depth Benchmark Corpus

Repository-development artifact for GitHub Issue
[#90](https://github.com/amirbena/code-review-skill/issues/90), the last
child of epic [#48](https://github.com/amirbena/code-review-skill/issues/48)
"risk-based review depth + large-PR strategy". This is a **focused
sub-corpus** of [`benchmark-case/v1`](../../fixture-format.md) fixtures
exercising the vocabulary
[`#86`](https://github.com/amirbena/code-review-skill/issues/86)-[`#89`](https://github.com/amirbena/code-review-skill/issues/89)
already established:
[`shared/policies/change-risk-signals.md`](../../../../shared/policies/change-risk-signals.md)
(catalog signals and depth), and, illustratively,
[`repository-expansion.md`](../../../../shared/policies/repository-expansion.md)
and
[`large-pr-partitioning.md`](../../../../shared/policies/large-pr-partitioning.md).

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of
[`../`](../README.md) and [`../../`](../../README.md) this is **not**
packaged into either Skill archive and no packaged Skill resource depends
on it — it is consumed only by this repository's own test suite, through
the single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
(never a second one).

## Selection principle

- **One case per way a real review arrives at `deep`/`elevated` depth.**
  A deep catalog signal alone (`auth`), a second deep catalog signal alone
  (`concurrency`), two independent `elevated` occurrences escalating to
  `deep` (`sensitive_path` + `infra_config`), `elevated` from
  `diff_size` alone with **no** catalog signal firing, and a large
  multi-area change — the shape `large-pr-partitioning.md` targets.
- **Each case's defect is real and would be missed by a shallower pass.**
  The auth case is two lines; the diff-size case is 11 near-identical
  call-site hunks with one silently un-updated; the concurrency case reads
  as a harmless narrowing of a critical section. The point of each case is
  that the signal, not the diff's apparent size or drama, is what forces
  the scrutiny that catches the defect.
- **`exhaustive` completeness.** Every case uses the default
  `findings_completeness: exhaustive`, so an unexpected finding is itself
  a corpus failure.
- **Intentionally small.** Representative, not exhaustive, coverage of
  the catalog — not every signal/depth combination gets its own case.

## Fixture-level scope: what a `benchmark-case/v1` fixture cannot pin

`benchmark-case/v1`'s schema is closed (see
[`../../fixture-format.md`](../../fixture-format.md) §2, "an unknown key
anywhere is a rejection") and has no field for an expected `depth`,
expansion `ring`, partition assignment, or `coverage` label — only
`expected.findings` and `expected.decision`. So, exactly as
[`../repository-intelligence/README.md`](../repository-intelligence/README.md)
already establishes for its own mechanism: **the corpus fixture pins the
expected finding outcome; the reference-model case pins the mechanism.**
Every case below has a matching scenario in
[`../../../../tests/unit/review/test_risk_based_review_scenarios.py`](../../../../tests/unit/review/test_risk_based_review_scenarios.py)
that constructs the same signal/trigger/partition shape the fixture's
rationale describes and asserts the `depth`/`ring`/`capped`/`coverage`
value directly against
[`change_risk_signals.py`](../../../../tests/reference/review/change_risk_signals.py),
[`repository_expansion.py`](../../../../tests/reference/review/repository_expansion.py),
[`large_pr_partitioning.py`](../../../../tests/reference/review/large_pr_partitioning.py),
and
[`review_stopping_criteria.py`](../../../../tests/reference/review/review_stopping_criteria.py)
directly. The large-multiarea case's patch is deliberately **not** scaled
up to literally cross `large-pr-partitioning.md`'s `>=1200`-line /
`>=60`-file activation threshold — hand-authoring a genuinely large diff
would add bulk without adding coverage; that literal threshold arithmetic
is already exhaustively pinned in
[`../../../../tests/unit/review/test_large_pr_partitioning.py`](../../../../tests/unit/review/test_large_pr_partitioning.py)
and re-exercised at realistic scale in
`test_risk_based_review_scenarios.py`. This fixture instead pins the
**multi-area finding-retention** property: three unrelated areas, each
with its own defect, none of which partitioning-by-directory may drop.

## Cases

| File | What forces depth | A correct review must… | Decision |
|---|---|---|---|
| [`risk-depth-auth-signal-deep.yaml`](risk-depth-auth-signal-deep.yaml) | `auth` catalog signal alone → `deep` | catch a 2-line broken-access-control regression (role check replaced by a spoofable client header) | `changes-required` |
| [`risk-depth-concurrency-signal-deep.yaml`](risk-depth-concurrency-signal-deep.yaml) | `concurrency` catalog signal alone → `deep` | catch a TOCTOU race reintroduced by moving a check outside its lock | `changes-required` |
| [`risk-depth-elevated-escalation-deep.yaml`](risk-depth-elevated-escalation-deep.yaml) | two independent `elevated` occurrences (`sensitive_path` + `infra_config`) escalate → `deep` | catch a CI workflow echoing a secret into the job log | `changes-required` |
| [`risk-depth-diffsize-elevated-refactor.yaml`](risk-depth-diffsize-elevated-refactor.yaml) | `diff_size` alone (11 files >= 10) → `elevated`, no catalog signal fires | catch the one call site a mechanical 11-file argument-order refactor left un-updated | `changes-required` |
| [`risk-depth-large-multiarea-partitioning.yaml`](risk-depth-large-multiarea-partitioning.yaml) | multi-area change spanning `api/`, `worker/`, `infra/` — the shape `large-pr-partitioning.md` targets | catch one independent defect per area, with none dropped or misattributed across partitions | `changes-required` |

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`) and in the
header comment.

## Related sub-corpora

This corpus does not repeat
[`../repository-intelligence/`](../repository-intelligence/README.md)'s
coverage of `repository-expansion.md`'s four triggers — that corpus
already exercises the call-site, interface/contract, and config-consumer
triggers end to end, including a safe-failure and a control case. This
corpus is scoped to `change-risk-signals.md`'s depth vocabulary and
`large-pr-partitioning.md`'s multi-area shape instead.

## Validation

[`../../../../tests/unit/review/test_risk_depth_corpus.py`](../../../../tests/unit/review/test_risk_depth_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and the #51 corpus (it never defines a second
one), and asserts: the sub-corpus stays small and documented; every
required case is present; every case pins an explicit `decision`
consistent with its required findings; and every case's rationale is
reflected by an equivalent depth/expansion/partitioning assertion against
the reference models in
[`../../../../tests/unit/review/test_risk_based_review_scenarios.py`](../../../../tests/unit/review/test_risk_based_review_scenarios.py).
Matching a reviewer's output to these expectations and scoring it are out
of scope here (Issues #41 / #52 / #54). Peer review of the expected
findings themselves happens on the pull request.
