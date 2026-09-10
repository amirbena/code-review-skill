# Review Context — Evidence, Authority & Provenance

Repository-development design records for how a review **uses caller-supplied
context as evidence**: what kind of authority each piece of context carries,
how conflicting / stale / ambiguous context is resolved, and how a finding
records the contextual evidence that justified it.

Like [`../findings/README.md`](../findings/README.md) and
[`../runtime-parallelism.md`](../runtime-parallelism.md), these are
repository-development docs: **not** packaged into either Skill archive, and
no packaged Skill resource depends on them. They are explanatory / design
records — the normative rule for each concern lives in the file named for it,
and the packaged shared policies
([`../../shared/policies/review-context.md`](../../shared/policies/review-context.md),
[`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md))
and the finding template
([`../../shared/templates/finding.md`](../../shared/templates/finding.md))
reference them by name.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`contextual-evidence-model.md`](contextual-evidence-model.md) | The typed contextual-evidence model — every evidence type marked authoritative or informational, the authority/trust rules, the deterministic resolution table for conflicting / stale / ambiguous / non-authoritative evidence, provenance-aware findings, scope/intent and introduced-vs-pre-existing use, the precision-preservation analysis, and the smallest useful first implementation. | [#118](https://github.com/amirbena/code-review-skill/issues/118) |

Two follow-on issues build on this model without redefining it:
[#176](https://github.com/amirbena/code-review-skill/issues/176)
(requirement / acceptance-criteria coverage) and
[#178](https://github.com/amirbena/code-review-skill/issues/178) (unified
finding confidence / evidence-state field).

## Related

- Packaged review-context concepts and the code-first evidence hierarchy:
  [`../../shared/policies/review-context.md`](../../shared/policies/review-context.md).
- Prior-review-evidence classification and settled decisions:
  [`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md).
- The finding contract and the optional **contextual evidence** field:
  [`../../shared/templates/finding.md`](../../shared/templates/finding.md).
- User-facing usage guide:
  [`../features/review-context.md`](../features/review-context.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
