# Scale Progressive-Loading-Proof Corpus

Repository-development artifact for GitHub Issue
[#447](https://github.com/amirbena/code-review-skill/issues/447), parent
[#403](https://github.com/amirbena/code-review-skill/issues/403). Mirrors
[`../specialist-depth-progressive-loading-proof/`](../specialist-depth-progressive-loading-proof/README.md)'s
shape (Issue #411) for the second capability to prove the
declarative-manifest + hand-authored-predicate + conditional-load pattern
generalizes: `scale`.

Like [`../`](../README.md), this is **not** packaged into either Skill
archive and no packaged Skill resource depends on it — it is consumed
only by this repository's own test/proof tooling, through the single
reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py).

## Selection principle

`scale`'s existing corpora — [`../risk-depth/`](../risk-depth/README.md)
(#90) and [`../repository-intelligence/`](../repository-intelligence/README.md)
(#129) — already cover confident non-activation (no trigger fires),
confident activation (a positive, evidence-resolved trigger), and a
confidently *ambiguous relationship* that stays unresolved
(`repo-intel-python-dynamic-dispatch-safe-failure`, a trigger that fires
but whose concrete target cannot be resolved). None of those exercises
#447's own fail-closed clause: whether the trigger *fires at all* is
itself unclear from the diff and its immediately adjacent evidence. This
corpus adds exactly the one case that shape needs, the same "one net-new
fixture" scope #411 used.

## Cases

| File | A correct review must… | Decision |
| --- | --- | --- |
| [`scale-progressive-loading-proof-ambiguous-public-export-forces-fail-closed-expansion.yaml`](scale-progressive-loading-proof-ambiguous-public-export-forces-fail-closed-expansion.yaml) | expand the ring (load `scale`) rather than skip expansion when whether a call-site trigger fires at all is not confidently resolvable, and surface the caller-side defect that expansion reveals | `clean` (a required finding permitted at P1 or P2, never a confident P0 — see the fixture's own rationale) |

## No statistical-significance claim

This is a single, hand-crafted, illustrative case, not a measured
hit-rate or precision/recall figure — see
[`../../fixture-format.md`](../../fixture-format.md) §13 and
[#41](https://github.com/amirbena/code-review-skill/issues/41).

## Validation

Loaded through the same single reference validator used everywhere else
in this directory tree
([`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py))
by
[`scripts/capability_architecture/scale_progressive_loading_proof.py`](../../../../scripts/capability_architecture/scale_progressive_loading_proof.py),
mirroring
[`specialist_depth_progressive_loading_proof.py`](../../../../scripts/capability_architecture/specialist_depth_progressive_loading_proof.py)'s
static + behavioral proof shape.
