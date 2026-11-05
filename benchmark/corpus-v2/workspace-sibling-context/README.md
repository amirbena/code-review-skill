# Workspace sibling context benchmark sub-corpus

Repository-development artifact for GitHub Issue
[#664](https://github.com/amirbena/code-review-skill/issues/664) (parent
[#661](https://github.com/amirbena/code-review-skill/issues/661)). It measures
whether bounded, caller-granted workspace sibling evidence lets a review
resolve an unresolved question before escalation, without adding unjustified
certainty when the evidence is thin. The design, arms, and pre-registered gate
are in
[`../../../runtime_platform/benchmark/workspace-sibling-context-measurement.md`](../../../runtime_platform/benchmark/workspace-sibling-context-measurement.md).

## `input.workspace_siblings` — an additive `benchmark-case/v2` input

Every case is a `benchmark-case/v2` fixture parsed by the one reference
validator ([`fixture-format.md`](../../../runtime_platform/benchmark/fixture-format.md)
§6.6) and indexed in [`corpus-index.json`](../../corpus-index.json). The input
maps an alias to a sibling repository (`files` committed as HEAD, optional
`mirrors_review_target`). The runner materializes the siblings under one
workspace root for every run; the caller decides whether the reviewer is handed
that root.

## Cases and adapter coverage

Shared cases run once per adapter, since the behavior is adapter-independent.
`wsib-gh-` cases run through the GitHub adapter only.

| Class | Case | local | github |
|---|---|---|---|
| Resolution from relevant sibling evidence | [`wsib-resolves-from-relevant-sibling`](wsib-resolves-from-relevant-sibling.yaml) | yes | yes |
| No relevant sibling (unchanged fallback) | [`wsib-no-relevant-sibling-fallback`](wsib-no-relevant-sibling-fallback.yaml) | yes | yes |
| Ambiguous or decoy sibling (no overreach) | [`wsib-ambiguous-siblings-no-overreach`](wsib-ambiguous-siblings-no-overreach.yaml) | yes | yes |
| Relevant but insufficient evidence | [`wsib-insufficient-evidence-question-preserved`](wsib-insufficient-evidence-question-preserved.yaml) | yes | yes |
| Absence in an inspected sibling | [`wsib-absence-in-inspected-sibling-no-claim`](wsib-absence-in-inspected-sibling-no-claim.yaml) | yes | yes |
| Unrelated sibling (no finding pollution) | [`wsib-unrelated-sibling-no-pollution`](wsib-unrelated-sibling-no-pollution.yaml) | yes | yes |
| PR repository excluded by identity | [`wsib-gh-pr-repository-excluded-by-identity`](wsib-gh-pr-repository-excluded-by-identity.yaml) | no | yes |
| API-only mode: grant unavailable, behavior unchanged | [`wsib-gh-api-only-grant-unavailable`](wsib-gh-api-only-grant-unavailable.yaml) | no | yes |
| No sibling content in published output | [`wsib-gh-published-output-reference-only`](wsib-gh-published-output-reference-only.yaml) | no | yes |

The ordinary benchmark runner hands the grant, so these cases run in the
capability-on configuration there. The capability-off arm exists only in the
on-demand measurement.

Deterministic fixture, materialization, and adapter behavior is covered by
[`tests/unit/benchmark/test_workspace_sibling_corpus.py`](../../../tests/unit/benchmark/test_workspace_sibling_corpus.py).
