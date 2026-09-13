# API / Contract Compatibility — Design Record

Repository-development design record for the reviewer's **API / contract
compatibility review** capability: reasoning about whether a changed
repository contract (OpenAPI, JSON Schema, protobuf, a public API model,
an event/message schema, or a configuration contract) breaks existing
consumers.

Like [`../finding-confidence/README.md`](../finding-confidence/README.md)
and [`../review-context/README.md`](../review-context/README.md), this is
a repository-development doc: **not** packaged into either Skill archive,
and no packaged Skill resource depends on it. It is an explanatory / design
record — the normative, packaged rule lives in
[`../../shared/policies/api-contract-compatibility.md`](../../shared/policies/api-contract-compatibility.md),
which [`review-scope.md`](../../shared/policies/review-scope.md) routes to,
and which references this document by name (not by link, since this is not
a packaged resource).

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`api-compatibility-model.md`](api-compatibility-model.md) | The recognized contract types and their diff-recognition signals, the compatible / breaking / context-dependent classification for each change shape with a worked example, the fail-closed rule for an unresolvable consumer surface, and the smallest useful first implementation. | [#175](https://github.com/amirbena/code-review-skill/issues/175) |

## Related

- The packaged, operative rule a reviewer actually applies:
  [`../../shared/policies/api-contract-compatibility.md`](../../shared/policies/api-contract-compatibility.md).
- The dimension this capability is a depth owner of:
  [`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
  "Semantic change-implication reasoning" — "API / integration contracts."
- The fixture corpus pinning the expected classification for each change
  shape before and after this design record:
  [`../benchmark/corpus/api-compatibility/README.md`](../benchmark/corpus/api-compatibility/README.md)
  ([#184](https://github.com/amirbena/code-review-skill/issues/184)).
- The code-evidence bar every reported finding still meets:
  [`../../shared/policies/evidence.md`](../../shared/policies/evidence.md).
- Severity and the mechanical decision derivation, which this capability
  never touches: [`../../shared/policies/severity.md`](../../shared/policies/severity.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

## Non-goals

- Cross-repository contract retrieval — fetching or inspecting another
  repository's consumer code to resolve an ambiguous consumer surface
  (tracked separately by [#133](https://github.com/amirbena/code-review-skill/issues/133)).
- Duplicating a dedicated schema-linter or SAST tool.
- A generic "a schema file changed" notifier with no compatibility
  reasoning behind it.
- Any new severity, finding category, or numeric/probabilistic score.
