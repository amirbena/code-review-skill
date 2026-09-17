# Candidate-Finding Validation Precision Corpus

Repository-development artifact for GitHub Issue
[#383](https://github.com/amirbena/code-review-skill/issues/383). Parent
capability: [#382](https://github.com/amirbena/code-review-skill/issues/382)
(child of the [#381](https://github.com/amirbena/code-review-skill/issues/381)
epic), which defines
[`../../../candidate-finding-validation/candidate-finding-validation-model.md`](../../../candidate-finding-validation/candidate-finding-validation-model.md),
the `observation → candidate claim → validated finding → severity`
reasoning contract: what a candidate must prove before it is promoted to a
severity-bearing finding. This is a **focused sub-corpus** of
[`benchmark-case/v2`](../../fixture-format.md) fixtures that pin the
expected outcomes for that contract and keep its false-escalation
protections (unproven regression, unestablished semantic equivalence, an
invented P0/P1 with no supporting evidence) and its non-suppression
protections (a technically-grounded blocking finding with no Jira, a
proven defect that is not demoted merely because its impact is
non-blocking) from regressing.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of
[`../`](../README.md) and [`../../`](../../README.md) this is **not**
packaged into either Skill archive and no packaged Skill resource depends
on it — it is consumed only by this repository's own test suite, through
the single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py).

This corpus **consumes** the canonical contract in
`candidate-finding-validation-model.md`; it does not redefine it. Every
finding's `claim` and `defect_kind` below is written to match that
document's own vocabulary and worked examples (§3–§11), not a paraphrase
of them.

## Selection principle

- **One case per required outcome shape** named in Issue #383's scope, so
  a regression in any one gate is unambiguous: semantic-role
  no-inference (§4), unproven-regression non-assertion (§7),
  disconfirmed-candidate drop (§8 `DROPPED`), no-Jira technically-grounded
  blocking finding (§5 level 4), valid-defect severity downgrade (§8
  `DOWNGRADED`), requirement ambiguity not invented as P0/P1 (§5/§9),
  disconfirming-precedent re-evaluation (§8 `RECLASSIFIED`), structural
  inconsistency staying non-blocking (§9 maintainability concern), a
  concrete invariant violation staying a valid finding with no
  requirement behind it (§9 worked example 6), and a blast radius that
  bounded evidence narrows to one path (§10).
- **Plus one required real-world-derived scenario** — see "The real-world
  scenario" below — proving the corpus additionally catches a semantic
  reasoning defect that internally-consistent docs/implementation/tests
  can mask.
- **Each case isolates its outcome.** The diffs are small and
  single-dimension so a miss is unambiguously about the validation gate
  under test, not about noticing the underlying code shape.
- **Deliberately reuses one small fictional domain** — an inventory
  reservation/checkout service (`inventory/`, `billing/`, `payments/`,
  `admin_console.py`) — across the synthetic cases, the same way sibling
  sub-corpora reuse a narrow domain, to keep the corpus small while still
  isolating each outcome shape. The real-world-derived case uses its own
  fictional `review_engine/` domain instead, since it is specifically
  about a reasoning-model implementation, not the checkout domain.
- **Intentionally small.** A representative set for each outcome shape
  named in #383's scope, not exhaustive coverage of every gate
  interaction.

## What this corpus does *not* assert

No fixture asserts a preference for any particular code style, error-
handling convention, or module layout. Every flagged case's finding is
grounded exactly as `candidate-finding-validation-model.md` §5 requires
(a stated invariant, a test, established behavior, or a technical
invariant — never bare reviewer taste), and every clean case's absence of
a finding is likewise explained by a named gate the candidate failed to
clear (§3–§8), never by the corpus preferring quieter review output.

## The real-world scenario

[`real-world-semantic-consistency-trap-pr-390.yaml`](real-world-semantic-consistency-trap-pr-390.yaml)
is derived from a real local review of
[PR #390](https://github.com/amirbena/code-review-skill/pull/390)
("Canonicalize pre-publication candidate-finding validation", reviewed at
commit `3d08fcb`), run with the older review behavior that predates the
#382 discipline this corpus protects. That review returned `REVIEW CLEAN`:
it verified strong internal consistency (design record matched the
reference model, tests matched the design record, policy cross-links
resolved, focused tests passed) but missed that the reference model
itself conflated finding classification with blocking justification —
exactly the anti-pattern
[`candidate-finding-validation-model.md`](../../../candidate-finding-validation/candidate-finding-validation-model.md)
§9 ("Classification and blocking justification are orthogonal
dimensions") exists to prevent.

The fixture is a **self-contained fictional analogue** of that failure
mode — it does not reproduce PR #390's actual code and requires no
GitHub/network access at run time. Its `metadata.source` records the PR
and issue #382 for provenance only, never as a runtime dependency. It
proves the corpus catches what an artifact-level consistency check
(docs match tests, tests pass, implementation is internally consistent)
alone would miss: a semantic invariant violated inside code that is
otherwise clean, tested, and documented.

## Cases

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`cfv-semantic-role-no-inference.yaml`](cfv-semantic-role-no-inference.yaml) | §4 semantic-role validation | report **nothing** — `sku` validated at intake versus read unvalidated in internal reporting are different responsibilities, not evidence of a defect | `clean` |
| [`cfv-unproven-regression-not-asserted.yaml`](cfv-unproven-regression-not-asserted.yaml) | §7 regression-proof discipline | report **nothing** — a brand-new flag has no prior-behavior evidence, so a suspected flipped default is never asserted as a proven regression | `clean` |
| [`cfv-disconfirmed-severe-candidate-dropped.yaml`](cfv-disconfirmed-severe-candidate-dropped.yaml) | §8 `DROPPED` | report **nothing** — an apparently severe missing-authorization candidate is disconfirmed by its only caller already enforcing the check | `clean` |
| [`cfv-no-jira-toctou-still-blocking.yaml`](cfv-no-jira-toctou-still-blocking.yaml) | §5 level 4, no ticket required | report **one P1** — a checkout-path TOCTOU race is blocking on technical-invariant grounding alone, no Jira reference needed | `changes-required` |
| [`cfv-valid-defect-severity-downgrade.yaml`](cfv-valid-defect-severity-downgrade.yaml) | §8 `DOWNGRADED` | report **one P2** (not the P0 a naive read would assign) — a real CSV-injection sink survives disconfirmation but its severity is narrowed by bounded, admin-only exposure | `clean` |
| [`cfv-requirement-ambiguity-not-invented.yaml`](cfv-requirement-ambiguity-not-invented.yaml) | §5/§9 requirement ambiguity | report **one P2** requirement-ambiguity finding — an edge case grounded only in reviewer inference is never invented as an unsupported P0/P1 | `clean` |
| [`cfv-disconfirming-precedent-reevaluated.yaml`](cfv-disconfirming-precedent-reevaluated.yaml) | §8 `RECLASSIFIED` | report **one P2** — nearby precedent shows the swallowed exception is the established pattern for this responsibility, re-evaluated as a smaller log-context regression, not the original P1 lost-error claim | `clean` |
| [`cfv-structural-inconsistency-non-blocking.yaml`](cfv-structural-inconsistency-non-blocking.yaml) | §9 maintainability concern | report **one P2** — a real field-order/naming inconsistency with no behavioral consequence stays non-blocking | `clean` |
| [`cfv-invariant-violation-no-requirement-still-valid.yaml`](cfv-invariant-violation-no-requirement-still-valid.yaml) | §9 worked example 6 | report **one P2**, classified as a correctness defect (not demoted) — the same TOCTOU shape as the blocking sibling case, but insufficient material impact, with no requirement naming the counter at all | `clean` |
| [`cfv-narrowed-blast-radius-bounded-evidence.yaml`](cfv-narrowed-blast-radius-bounded-evidence.yaml) | §10 bounded blast-radius reuse | report **one P1** scoped to the single actually-affected caller — bounded evidence at each call site narrows an initially-broad three-caller observation | `changes-required` |
| [`real-world-semantic-consistency-trap-pr-390.yaml`](real-world-semantic-consistency-trap-pr-390.yaml) | real-world-derived: semantic-consistency trap (PR #390) | report **one P1** — `classify()` derives classification from `material_impact`, contradicting the already-documented separation, even though docs/tests/implementation are mutually consistent and tests pass | `changes-required` |

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`).

## Validation

[`../../../../tests/unit/review/root_cause/test_candidate_finding_validation_corpus.py`](../../../../tests/unit/review/root_cause/test_candidate_finding_validation_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and every other corpus — it never defines a
second one — and asserts: the sub-corpus stays small and documented; every
required outcome shape (including the real-world scenario) is present;
every case pins an explicit `decision` consistent with the mechanical
derivation; every finding carries a `defect_kind` and a rationale/tags;
and every patch-case anchor resolves inside its own case's patch or base.
Matching a reviewer's output to these expectations and scoring it are out
of scope here (Issues #41 / #52 / #54). Peer review of the expected
findings themselves happens on the pull request.
