# Candidate-Finding Validation

Repository-development design record for the pre-publication
`observation → candidate claim → validated finding → severity` reasoning
contract: what a candidate must prove before it is promoted to a
severity-bearing finding.

Like [`../review-context/README.md`](../review-context/README.md) and
[`../finding-confidence/README.md`](../finding-confidence/README.md), this
is a repository-development doc: **not** packaged into either Skill
archive, and no packaged Skill resource depends on it. It is explanatory /
a design record — the normative rule lives in the file named for it, and
the packaged
[`shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
[`shared/policies/evidence.md`](../../shared/policies/evidence.md), and
[`shared/policies/severity.md`](../../shared/policies/severity.md)
reference it by name and do not restate its hierarchy or worked examples.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`candidate-finding-validation-model.md`](candidate-finding-validation-model.md) | The `observation → candidate claim → validated finding → severity` pipeline; the observation-first gate, semantic-role validation, the evidence/contract grounding hierarchy (with non-Jira technically-grounded blocking findings explicitly preserved), the causal validation chain, regression-proof discipline, the disconfirmation pass, classification before severity, the `claim_valid`/`blocking_justification_valid` separation, and reuse (not redefinition) of the existing ring-based blast-radius model. | [#382](https://github.com/amirbena/code-review-skill/issues/382) |

## Related

- The confirmed-defect / credible-risk / optional-improvement labeling this
  model gates access to:
  [`../../shared/policies/evidence.md`](../../shared/policies/evidence.md).
- P0/P1/P2 and the mechanical decision derivation this model feeds, never
  overrides:
  [`../../shared/policies/severity.md`](../../shared/policies/severity.md).
- The bounded, ring-based blast-radius model this document reuses:
  [`../../shared/policies/repository-expansion.md`](../../shared/policies/repository-expansion.md),
  [`../../shared/policies/architectural-placement.md`](../../shared/policies/architectural-placement.md).
- The typed authoritative/informational evidence model this document's
  grounding hierarchy and disconfirmation pass consume:
  [`../review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md).
- The single `confidence` field this model's outcome composes with:
  [`../finding-confidence/finding-confidence-model.md`](../finding-confidence/finding-confidence-model.md).
- The base review-scope routing point:
  [`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
