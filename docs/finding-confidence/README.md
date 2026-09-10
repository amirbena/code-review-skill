# Finding Confidence — Unified Evidence State

Repository-development design record for the **one machine-readable
epistemic-state field** a finding carries: how sure the reviewer is that the
defect is real, expressed as a small closed set of values rather than a
probability score.

Like [`../findings/README.md`](../findings/README.md),
[`../review-context/README.md`](../review-context/README.md), and
[`../runtime-parallelism.md`](../runtime-parallelism.md), these are
repository-development docs: **not** packaged into either Skill archive, and
no packaged Skill resource depends on them. They are explanatory / design
records — the normative rule lives in the file named for it, and the packaged
finding template
([`../../shared/templates/finding.md`](../../shared/templates/finding.md))
references this document by name.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`finding-confidence-model.md`](finding-confidence-model.md) | The unified `confidence` field — its closed value set and per-value entry criteria, how the runtime-evidence states of [#128](https://github.com/amirbena/code-review-skill/issues/128) and the authoritative/informational provenance of [#118](https://github.com/amirbena/code-review-skill/issues/118) map onto the one field, the deterministic derivation order, the default when a Skill does not compute it, and the rule that a lower value never lowers the evidence bar, severity, or the review decision. | [#178](https://github.com/amirbena/code-review-skill/issues/178) |

## Related

- The finding contract and the optional **confidence** field:
  [`../../shared/templates/finding.md`](../../shared/templates/finding.md),
  "Confidence and evidence state".
- The runtime-evidence states this field rolls up:
  [`../../shared/policies/runtime-validation.md`](../../shared/policies/runtime-validation.md),
  "Finding validation state".
- The contextual-evidence authority model this field rolls up:
  [`../review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md).
- The code-evidence bar every reported finding still meets:
  [`../../shared/policies/evidence.md`](../../shared/policies/evidence.md).
- Severity and the mechanical decision derivation, which this field never
  touches: [`../../shared/policies/severity.md`](../../shared/policies/severity.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
