# Root-Cause / Duplicate Consolidation Corpus

Repository-development artifact for GitHub Issue
[#185](https://github.com/amirbena/code-review-skill/issues/185). Parent
capability: [#177](https://github.com/amirbena/code-review-skill/issues/177)
(root-cause finding consolidation). This is a **focused sub-corpus** of
[`benchmark-case/v1`](../../fixture-format.md) fixtures that pin the
expected consolidation classifications *before* the reviewer logic in #177
exists, and keep it from regressing afterwards.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of
[`../`](../README.md) and [`../../`](../../README.md) this is **not**
packaged into either Skill archive and no packaged Skill resource depends
on it — it is consumed only by this repository's own test suite, through
the single reference validator
[`../../../../tests/reference/benchmark_fixture.py`](../../../../tests/reference/benchmark_fixture.py).

## Selection principle

- **One case per consolidation outcome #177 names.** Shared-cause →
  consolidate; look-alike but independent → stay separate; shared cause
  but low confidence → fall back to separate; re-review → reconcile prior
  separate findings to the consolidated one. A regression in any one
  outcome surfaces as a single failing fixture.
- **Each case isolates its outcome.** The defects are plain and
  single-dimension (a loosened validator, two off-by-ones, two naive
  datetimes, one weak sanitizer) so a miss is unambiguously about
  consolidation, not about catching the bug.
- **`exhaustive` completeness.** Every case uses the default
  `findings_completeness: exhaustive`, so an over-merged *or* an
  over-split finding set is an unexpected finding. Where the change
  plausibly warrants a regression test, that is carried as an `optional`
  finding so a review that asks for one is neither required to nor
  penalised for raising it.
- **Intentionally small.** A representative set, not exhaustive coverage of
  every clustering shape — growth is per-outcome and deliberate.

## Cases

| File | Outcome | Input | A correct review must… | Decision |
|---|---|---|---|---|
| [`consolidation-shared-validator-many-call-paths.yaml`](consolidation-shared-validator-many-call-paths.yaml) | shared cause → **one** authoritative finding | `is_valid_email` is loosened from `re.fullmatch` to `re.match`; four callers inherit the weakened check | report **one P0/P1** finding on `is_valid_email` naming the affected call paths — not one finding per caller (an `optional` missing-regression-test note is also acceptable) | `changes-required` |
| [`consolidation-similar-but-independent-defects.yaml`](consolidation-similar-but-independent-defects.yaml) | look-alike but independent → **separate** findings | two off-by-one bugs in unrelated modules that share no code | report **two** independent **P1** findings; do not merge them under one "off-by-one root cause" | `changes-required` |
| [`consolidation-shared-cause-low-confidence-fallback.yaml`](consolidation-shared-cause-low-confidence-fallback.yaml) | shared cause, low confidence → **separate** findings (fallback) | two naive-vs-aware datetime defects in different layers; a common "no timezone discipline" cause is plausible but not established | report **two** separate **P1** findings rather than an over-merged "timezone handling" finding | `changes-required` |
| [`consolidation-rereview-reconciles-to-authoritative.yaml`](consolidation-rereview-reconciles-to-authoritative.yaml) | re-review → **reconcile** prior separate findings | a shared weak `sanitize_path` used by two call paths; `input.context` carries a prior review's two per-call-site findings | report **one P1** authoritative finding on `sanitize_path` that reconciles the two prior findings — not two, not a third new one | `changes-required` |

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`) and in the
header comment.

### On the re-review case

`benchmark-case/v1` has no first-class prior-review input, so
[`consolidation-rereview-reconciles-to-authoritative.yaml`](consolidation-rereview-reconciles-to-authoritative.yaml)
supplies the earlier review's two findings through `input.context`
([`../../fixture-format.md`](../../fixture-format.md) §6.3), treated as
prior review evidence per
[`../../../../shared/policies/review-evidence.md`](../../../../shared/policies/review-evidence.md).
A dedicated re-review fixture shape is left to a later `format` revision
under #177, not this corpus.

## Validation

[`../../../../tests/unit/test_consolidation_corpus.py`](../../../../tests/unit/test_consolidation_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark_fixture.py`](../../../../tests/reference/benchmark_fixture.py)
used for the worked example and the #51 corpus (it never defines a second
one), and asserts the sub-corpus stays small, that filenames match case
`id`s, that every case records a rationale and a consistent explicit
`decision`, that patch-case anchors occur in the diff under review, and
that all four #185 outcomes above are represented — including the
re-review reconciliation case. Matching a reviewer's output to these
expectations and scoring it are out of scope here (Issues #41 / #52 / #54).
