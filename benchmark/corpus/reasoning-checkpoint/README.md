# Reasoning Checkpoint Benchmark Corpus

Repository-development artifact for GitHub Issue
[#567](https://github.com/amirbena/code-review-skill/issues/567) (Epic
[#564](https://github.com/amirbena/code-review-skill/issues/564)), which proves
the behavior of the human reasoning checkpoint delivered by
[#566](https://github.com/amirbena/code-review-skill/issues/566)
([`shared/policies/reasoning-checkpoint.md`](../../../shared/policies/reasoning-checkpoint.md),
the `Reasoning check` section of
[`shared/templates/review-summary.md`](../../../shared/templates/review-summary.md),
and both delivery templates). The contract itself is unchanged here; this
corpus only pins that the delivered behavior activates when warranted, stays
inert otherwise, invents no evidence, and never reaches a finding, a severity,
or the Decision.

## Why this corpus is not `benchmark-case/v2` fixtures

The #565 design record
([`../../../reasoning-checkpoint/reasoning-checkpoint-contract.md`](../../../docs/reasoning-checkpoint/reasoning-checkpoint-contract.md),
section 11) decided this before implementation: `benchmark-case/v2`'s
`expected` block is a patch plus expected review findings
([`fixture-format.md`](../../../runtime_platform/benchmark/fixture-format.md)), a closed
findings/Decision-shaped schema, and the checkpoint is by contract *not* a
finding. There is no field for "a question section is present/absent" or for
"questions never change the Decision". Extending that schema would weaken its
closedness for every other corpus, and building a second fixture framework is
a stated non-goal of #567. So this corpus uses the existing **test-only
reference-fixture pattern**
([`verdict-consistency`](../verdict-consistency/README.md),
[`reviewer-brief`](../reviewer-brief/README.md)): one module of declarative,
metadata-bearing cases —
[`runtime_platform/benchmark/reference/reasoning_checkpoint_fixtures.py`](../../../runtime_platform/benchmark/reference/reasoning_checkpoint_fixtures.py)
— exercised by
[`tests/unit/benchmark/test_reasoning_checkpoint_corpus.py`](../../../tests/unit/benchmark/test_reasoning_checkpoint_corpus.py).
Nothing is packaged, and like the other README-only sub-corpus directories it
is excluded from the comprehensive lane by construction (no `benchmark-case/v2`
YAML to discover).

Decision derivation reuses
[`tests/reference/review/decision_semantics.py`](../../../tests/reference/review/decision_semantics.py),
the single mechanical source, so invariance is measured against the real
derivation, never a second one. Every check is a deterministic structural
assertion; none is an LLM or rubric score.

## What the reference module models

| Piece | Mirrors |
| --- | --- |
| `evaluate_activation` | policy "Activation": investigation facet, design facet, "Always inert", incomplete coverage and unresolved Jira inert, fail-closed when no anchorable question exists |
| `select_questions` | policy "Shape and bounds" and the anchor rule: 1–4 questions, investigation first, restated findings and unanchored candidates dropped |
| `render_review` | template placement: after Decision (and a self-review disclosure line), before metadata, body only, six surfaces × default/`human_review_output`, with `checkpoint=False` as the suppressed baseline |
| `render_structured_result` | `structured_review_result`: closed projection of findings, coverage, Decision — no checkpoint key |
| `question_violations` | per-question contract: one sentence ending `?`, no `P0/P1/P2`, no finding ID, no Decision token, not generic, no placeholder, no runtime access/contents claim, provenance tag present |

## Coverage (one tag per #567 scope bullet)

`REQUIRED_COVERAGE_TAGS` is asserted covered by at least one case, so the
"fixtures exist for every scope bullet" criterion is machine-checked.

| Scope bullet | Representative cases |
| --- | --- |
| Bug fix activates investigation questions | `bug-fix-bug-description-runtime-dependent`, `bug-fix-context-contradicts-repository-evidence`, `bug-fix-strong-content-signal-with-runtime-link` |
| Architecture/lifecycle activates, reusing placement evidence | `lifecycle-change-owning-ring-reached`, `analogue-deviation-concrete-consequence` |
| Trivial change: absent | `trivial-<kind>-inert` for every always-inert kind, `weak-signals-only-small-guard-inert`, `placement-direct-caller-confirmed-inert` |
| Insufficient evidence: nothing invented, no specific question | `no-anchorable-question-fails-closed`, `insufficient-evidence-boundary-move-no-invented-architecture`, `unverifiable-hypothesis-single-question` |
| Runtime-evidence boundary | `bug-fix-incident-followup-logs-unavailable`, `bug-fix-three-provenance-classes-distinct` |
| Findings present: questions stay non-findings; clean; P2-only | `findings-p0-with-checkpoint-stays-changes-required`, `candidate-restating-a-finding-is-dropped`, `lifecycle-change-owning-ring-reached` (P1), `analogue-deviation-concrete-consequence` (P2-only), `bug-fix-bug-description-runtime-dependent` (clean) |
| Decision/severity invariance | every case tagged `decision-severity-invariance`, checked on every surface, both output modes, on vs. off |
| Rendering coverage | six surfaces (local, GitHub passive/active/withheld/self-review/fallback) × default and `human_review_output`, plus `structured_review_result` unchanged |
| Bound/noise | `question-ceiling-six-candidates-capped-at-four`, four `ordinary-review-*-no-checkpoint` cases, and an activation-rate guard |
| Inert under `REVIEW INCOMPLETE` / unresolved Jira | `review-incomplete-coverage-inert`, `jira-context-unresolved-inert` |

## Scope boundary of the evidence

This corpus is a **reference model** of the delivered contract, like every
sibling test-only corpus: it proves the contract's observable rules hold in a
deterministic model and that the delivered packaged text states them (the
model's constants — heading, lead-in, scoped opening sentence, readiness
phrases, 1–4 bound — are pinned to the packaged policy and templates by
`PackagedContractPinTests`, and the packaged wording itself separately by
[`test_reasoning_checkpoint_docs.py`](../../../tests/policy/review/presentation/test_reasoning_checkpoint_docs.py)).
It does not drive a live model: the existing adapter
([`benchmark_review_adapter.py`](../../../runtime_platform/benchmark/scripts/benchmark_review_adapter.py))
parses only the single-surface finding format, so a live activation measurement
of the section would be new adapter infrastructure, out of #567's scope.
The fixtures are shaped to drive such an adapter if one is added later.

## Validation

```bash
python3 -m pytest tests/unit/benchmark/test_reasoning_checkpoint_corpus.py -v
```
