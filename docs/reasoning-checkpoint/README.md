# Reasoning Checkpoint — Human Reasoning Questions

Repository-development design record for the **human reasoning checkpoint**:
a short, evidence-anchored set of questions to the engineer at the end of a
review, so a deep review is not mistaken for the engineer's own root-cause or
design validation.

Like [`../finding-confidence/README.md`](../finding-confidence/README.md) and
[`../review-context/README.md`](../review-context/README.md), this is a
repository-development doc: **not** packaged into either Skill archive, and no
packaged Skill resource depends on it. It is explanatory; once implemented, the
normative rules live in the packaged shared policy and template it names.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`reasoning-checkpoint-contract.md`](reasoning-checkpoint-contract.md) | Activation, the `Reasoning check` section (shape, bounds, placement), question derivation and the anchor rule, the Problem Context Contract and its five epistemic classes, the bug-investigation evidence boundary, readiness language, interactions with every output mode, non-effects, benchmark representability, canonical homes, and scope for the children. | [#565](https://github.com/amirbena/code-review-skill/issues/565) (Epic [#564](https://github.com/amirbena/code-review-skill/issues/564)) |

The delivered behavior is proven by the test-only corpus in
[`../benchmark/corpus/reasoning-checkpoint/README.md`](../../benchmark/corpus/reasoning-checkpoint/README.md)
([#567](https://github.com/amirbena/code-review-skill/issues/567)).

Implementation, benchmark, and documentation follow in
[#566](https://github.com/amirbena/code-review-skill/issues/566),
[#567](https://github.com/amirbena/code-review-skill/issues/567), and
[#568](https://github.com/amirbena/code-review-skill/issues/568).

## Related

- Review context and its evidence hierarchy:
  [`../../shared/policies/review-context.md`](../../shared/policies/review-context.md);
  authority model: [`../review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md).
- Bounded placement investigation the checkpoint consumes:
  [`../../shared/policies/architectural-placement.md`](../../shared/policies/architectural-placement.md).
- Human-facing shape: [`../../shared/templates/review-summary.md`](../../shared/templates/review-summary.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
