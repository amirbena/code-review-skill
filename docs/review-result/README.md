# Review Result — Machine-Readable Output

Repository-development design records for
**[#67](https://github.com/amirbena/code-review-skill/issues/67)**: a JSON
Schema and example for the machine-readable form of one review's output.

Like [`../review-telemetry/README.md`](../review-telemetry/README.md) and
[`../finding-confidence/README.md`](../finding-confidence/README.md), these
are repository-development docs: **not** packaged into either Skill
archive, and no packaged Skill resource depends on them. `local-code-review` emits a
result on request ([#69](https://github.com/amirbena/code-review-skill/issues/69));
`github-pr-review` does not yet.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`review-result-model.md`](review-result-model.md) | The representation decisions (naming, enums, required vs `null`, structure), the field → canonical-owner map, the decision-code mapping, and what the schema deliberately leaves out. | [#67](https://github.com/amirbena/code-review-skill/issues/67) |
| [`schema-versioning.md`](schema-versioning.md) | The `schema_version` field, compatible vs breaking change rules, consumer handling of unknown versions, and deprecation/rollout guidance. | [#68](https://github.com/amirbena/code-review-skill/issues/68) |
| [`review-result.schema.json`](review-result.schema.json) | The single source of truth for the document's exact shape (JSON Schema draft-07). | [#67](https://github.com/amirbena/code-review-skill/issues/67) |
| [`examples/review-result.example.json`](examples/review-result.example.json) | One validating example. | [#67](https://github.com/amirbena/code-review-skill/issues/67) |

## Related

- Test-only validator:
  [`../../tests/reference/review/review_result.py`](../../tests/reference/review/review_result.py).
- The semantic owners the schema points at rather than redefines:
  [`../../shared/templates/finding.md`](../../shared/templates/finding.md),
  [`../../shared/policies/severity.md`](../../shared/policies/severity.md),
  [`../findings/README.md`](../findings/README.md).
- Test-only version-rule reference:
  [`../../tests/reference/review/review_result_version.py`](../../tests/reference/review/review_result_version.py).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
