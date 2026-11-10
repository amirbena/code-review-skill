# Duplication / Reuse Corpus

Repository-development artifact for GitHub Issue
[#876](https://github.com/amirbena/code-review-skill/issues/876). Fixtures
for the Core's "Reuse" rule in
[`../../../skills/review-core/rules/reasoning.md`](../../../skills/review-core/rules/reasoning.md):
report unjustified duplication or reimplementation only when it is
equivalent, a shared implementation exists, and a concrete consequence is
shown. Not packaged; consumed by the test suite and benchmark harness.

| File | Shape | Expected |
|---|---|---|
| [`duplication-reuse-backend-divergent-validator-p1.yaml`](duplication-reuse-backend-divergent-validator-p1.yaml) | new validator looser than the canonical one, live path | one **P1**, `changes-required` |
| [`duplication-reuse-frontend-formatter-one-copy-fixed-p2.yaml`](duplication-reuse-frontend-formatter-one-copy-fixed-p2.yaml) | component re-implements a hook that got a later fix | one **P2** |
| [`duplication-reuse-infra-copied-helm-block-p2.yaml`](duplication-reuse-infra-copied-helm-block-p2.yaml) | Helm block copied despite a shared helper, copy out of date | one **P2** |
| `duplication-reuse-clean-*.yaml` (5) | different responsibilities, documented isolation, test setup, two-line repeat, extraction needing flags | no finding |

`../quality-duplicated-branch-logic.yaml` keeps its P2 as `optional`: a
one-line in-function repeat is the trivial repetition the rule excludes.
