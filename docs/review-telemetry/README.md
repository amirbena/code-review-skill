# Review Telemetry — Execution Coverage Signal

Repository-development design records for **[#182](https://github.com/amirbena/code-review-skill/issues/182)**:
an observational, machine-readable record of what one review actually
inspected and executed — never decision-affecting.

Like [`../review-context/README.md`](../review-context/README.md) and
[`../finding-confidence/README.md`](../finding-confidence/README.md),
these are repository-development docs: **not** packaged into either
Skill archive, and no packaged Skill resource depends on them. Nothing
here is wired into a packaged Skill runbook or policy by this change —
see the model doc's §8 "Smallest useful first implementation" for why.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`review-execution-telemetry-model.md`](review-execution-telemetry-model.md) | The metric catalog and rationale, the explicit "not collected" list, the never-decision-affecting guarantee (backed by a test), per-metric unavailable-state rules, worked examples, and the boundary with #131. | [#182](https://github.com/amirbena/code-review-skill/issues/182) |
| [`review-execution-telemetry.schema.json`](review-execution-telemetry.schema.json) | The single source of truth for the record's exact machine-readable shape (JSON Schema draft-07). | [#182](https://github.com/amirbena/code-review-skill/issues/182) |

## Related

- Cross-component architecture (the dependency DAG, the nine layers, and
  the #182/#131/#329 boundary this document's §5 restates):
  [`../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md).
- The *decision-affecting* coverage concept this design is deliberately
  distinct from:
  [`../../shared/policies/review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md).
- The test-only reference model:
  [`../../tests/reference/review/review_telemetry.py`](../../tests/reference/review/review_telemetry.py).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
