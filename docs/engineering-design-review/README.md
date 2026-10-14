# Engineering Design Review — Design Record

Repository-development design record for **engineering design review**:
reviewing an engineering design document (an HLD, an ADR, an RFC, a
design section of a change) as part of the **review target**, including
design-only pull requests and mixed code/design changes.

This is not the visual design-reference capability. That one compares a
rendered UI against a Figma-style reference and is owned by
[`../../shared/policies/design-reference.md`](../../shared/policies/design-reference.md).
In this record, "design" always means an engineering design.

Like [`../deployment-infrastructure/README.md`](../deployment-infrastructure/README.md)
and [`../dependency-supply-chain/README.md`](../dependency-supply-chain/README.md),
this is a repository-development doc. It is **not** packaged into either
Skill archive, and no packaged Skill resource depends on it. It is
contract-first and docs-only. It fixes the semantics that the
implementation, benchmark, and documentation children follow, so none of
them has to re-decide them.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`engineering-design-review-contract.md`](engineering-design-review-contract.md) | Classification of each element as an existing capability, implicit without a contract, or genuinely missing. Also: the proposed canonical homes, semantic activation rules, the testable proposal-versus-accepted-decision rule, evidence requirements per coverage area, verification of claims about existing code, comparison in both directions for mixed changes, the missing-information rule, reuse of the severity and validation contracts, local and GitHub API-only behavior, the Context-gap and Reasoning-check decisions (no change to either), non-goals, open maintainer questions, and the minimal implementation proposal with adjustments to the downstream children. | [#748](https://github.com/amirbena/code-review-skill/issues/748) |

## Epic and delivery

Parent epic [#747](https://github.com/amirbena/code-review-skill/issues/747).
This record is the research child. It blocks
[#749](https://github.com/amirbena/code-review-skill/issues/749)
(implementation), which blocks
[#750](https://github.com/amirbena/code-review-skill/issues/750)
(benchmark), which blocks
[#751](https://github.com/amirbena/code-review-skill/issues/751)
(documentation).

## Related

- Where a design document is supported today, as review context only:
  [`../../shared/policies/review-context.md`](../../shared/policies/review-context.md).
- How an accepted decision is distinguished from speculative discussion:
  [`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md),
  "Settled decisions", and
  [`../review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md)
  (`accepted_decision`).
- The activation and composition contract the capability composes under:
  [`../../shared/policies/specialist-depth.md`](../../shared/policies/specialist-depth.md).
- The validation contract every design finding passes through, unchanged:
  [`../candidate-finding-validation/candidate-finding-validation-model.md`](../candidate-finding-validation/candidate-finding-validation-model.md).
