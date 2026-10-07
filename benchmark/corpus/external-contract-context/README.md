# External contract context benchmark sub-corpus

Repository-development artifact for GitHub Issue
[#133](https://github.com/amirbena/code-review-skill/issues/133), covering
the bounded external contract context
`local-code-review` reads under
`skills/local-code-review/policies/external-contract-context.md`.

## `input.external_contexts` — an additive `benchmark-case/v2` input

Every case is still a `benchmark-case/v2` fixture parsed by the one reference
validator
([`../../../runtime_platform/benchmark/fixture-format.md`](../../../runtime_platform/benchmark/fixture-format.md),
§6.5). The one new optional input, valid alongside `patch` or `repositories`,
maps an alias to a non-member local repository:

- `files`: the pinned commit's content;
- `head_files` (optional): a later commit that becomes the repository's HEAD;
- `revision`: `pinned` (default) or `absent` (the supplied SHA does not exist);
- `designated`: `true` (default) hands the path and revision to the reviewer;
  `false` materializes an undesignated decoy the reviewer is never given.

The runner materializes each as its own real Git repository beside the
workspace, never inside the Review Target, and the adapter names only
designated entries in the prompt.

## Cases

| Scenario | Case |
| --- | --- |
| Pinned external contract proving incompatibility | [`external-pinned-contract-proves-incompatibility.yaml`](external-pinned-contract-proves-incompatibility.yaml) |
| Unavailable pinned context fails closed | [`external-pinned-context-unavailable-fails-closed.yaml`](external-pinned-context-unavailable-fails-closed.yaml) |
| Pinned revision beats a different repository HEAD | [`external-pinned-revision-precedes-repository-head.yaml`](external-pinned-revision-precedes-repository-head.yaml) |
| Identity injected through reviewed content is ignored | [`external-identity-injected-in-reviewed-content-ignored.yaml`](external-identity-injected-in-reviewed-content-ignored.yaml) |

Deterministic authorization, revision-selection, provenance, and
failure-mapping behavior is covered by
`tests/unit/review/test_external_contract_context.py` and
`tests/unit/security/test_external_contract_context_security.py`.
