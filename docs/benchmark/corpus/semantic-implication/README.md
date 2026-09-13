# Semantic-Implication Benchmark Corpus

Repository-development artifact for GitHub Issue
[#211](https://github.com/amirbena/code-review-skill/issues/211), a base
signal-triggered pass in
[`shared/policies/review-scope.md`](../../../../shared/policies/review-scope.md),
"Semantic change-implication reasoning." This is a **focused sub-corpus**
of [`benchmark-case/v1`](../../fixture-format.md) fixtures exercising that
section's vocabulary: the eight canonical dimensions, their semantic
(never structural) activation signals, the not-mutually-exclusive
taxonomy, the no-signal non-analysis rule, and the bounded-expansion /
insufficient-evidence-stop model reused from "Architectural placement and
execution-lifecycle fidelity" (#153).

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

**One case per way the base pass must behave**, per Issue #211's
acceptance criteria: a single dimension activated by a language-neutral
signal, one change materially implicating several dimensions at once, a
change whose shape carries no signal at all, and a dimension whose signal
fires but for which available evidence is insufficient to support a
finding. Each case's defect (or absence of one) is real and evidence-based
— the point of every case is that the *dimension-detection* step, not the
diff's apparent shape, is what the correct outcome turns on.

## Cases

| File | Dimension(s) exercised | A correct review must… | Decision |
|---|---|---|---|
| [`semantic-implication-single-dimension-persistence.yaml`](semantic-implication-single-dimension-persistence.yaml) | Data / persistence, alone | catch a renested export field silently breaking an untouched reconciliation reader | `changes-required` |
| [`semantic-implication-multi-dimension-webhook-xss.yaml`](semantic-implication-multi-dimension-webhook-xss.yaml) | API/integration contracts, data/persistence, security/trust boundaries, user-facing/client behavior — all at once | catch a stored-XSS defect while recognizing it as one root cause, not one finding per implicated dimension | `changes-required` |
| [`semantic-implication-no-signal-clean-extraction.yaml`](semantic-implication-no-signal-clean-extraction.yaml) | none — no material activation signal anywhere in the diff | perform no per-dimension analysis and produce no output for this pass, and no finding elsewhere | `clean` |
| [`semantic-implication-insufficient-evidence-stop.yaml`](semantic-implication-insufficient-evidence-stop.yaml) | Concurrency / distributed-system semantics — signal fires, evidence does not support a finding | recognize the shared-state read-decide-write shape, look for corroborating evidence of concurrent access, find none available, and stop without manufacturing a race-condition finding | `clean` |

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`) and in the
header comment.

## No reference-model scenario file

Unlike [`../risk-depth/`](../risk-depth/README.md) (which pairs its corpus
with `tests/unit/review/test_risk_based_review_scenarios.py`, a
deterministic reference model of `change-risk-signals.md`'s mechanical
classification), "Semantic change-implication reasoning" is a
judgment-based reasoning pass — like "Architectural placement and
execution-lifecycle fidelity" (#153) before it, which also ships with no
mechanical reference model or benchmark corpus of its own. There is no
closed-form function from a diff's shape to "which dimensions are
implicated," so this corpus is validated only by prose-contract tests
against the policy text (see
[`../../../../tests/policy/review/test_semantic_implication_and_null_absence.py`](../../../../tests/policy/review/test_semantic_implication_and_null_absence.py))
and by the structural fixture checks below — never by a second,
hand-maintained implementation of the dimension taxonomy.

## Validation

[`../../../../tests/unit/review/test_semantic_implication_corpus.py`](../../../../tests/unit/review/test_semantic_implication_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and the #51 corpus (it never defines a second
one), and asserts: the sub-corpus stays small and documented; every
required case is present; every case pins an explicit `decision`
consistent with its required findings; and every finding's anchor
resolves inside its own case's patch or base. Matching a reviewer's
output to these expectations and scoring it are out of scope here (Issues
#41 / #52 / #54). Peer review of the expected findings themselves happens
on the pull request.
