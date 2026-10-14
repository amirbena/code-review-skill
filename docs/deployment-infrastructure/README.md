# Deployment & Infrastructure Review Depth — Design Record

Repository-development design record for **deployment and infrastructure
review depth**: evidence-driven, domain-specific deepening of the
"Infrastructure / deployment" dimension for Kubernetes, Helm, Argo CD,
Docker, Terraform, Jenkins, and GitHub Actions changes.

Like [`../rendered-inspection/README.md`](../rendered-inspection/README.md)
and [`../dependency-supply-chain/README.md`](../dependency-supply-chain/README.md),
this is a repository-development doc: **not** packaged into either Skill
archive, and no packaged Skill resource depends on it. It is contract-first
and docs-only: it fixes the semantics that the implementation, benchmark,
and documentation children follow, so none of them re-decides semantics.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`deployment-infrastructure-review-contract.md`](deployment-infrastructure-review-contract.md) | Gap analysis against existing coverage, the proposed canonical home, activation signals, the per-technology concern × evidence-tier matrix with unsupported checks, validation of user-provided output, execution boundaries under existing policy, local vs GitHub API-only behavior, non-goals, and the minimal implementation proposal with adjustments to the downstream children. | [#741](https://github.com/amirbena/code-review-skill/issues/741) |

## Epic and delivery

Parent epic [#740](https://github.com/amirbena/code-review-skill/issues/740).
This record is the research child; it blocks
[#742](https://github.com/amirbena/code-review-skill/issues/742)
(implementation), which blocks
[#743](https://github.com/amirbena/code-review-skill/issues/743)
(benchmark) and
[#744](https://github.com/amirbena/code-review-skill/issues/744)
(documentation).

## Related

- The base dimension this capability deepens:
  [`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
  "Semantic change-implication reasoning" — "Infrastructure / deployment."
- The activation/composition contract it composes under:
  [`../../shared/policies/specialist-depth.md`](../../shared/policies/specialist-depth.md).
- The existing depth owner it must not duplicate:
  [`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
  "Dependency / supply-chain deepening review" (#181), and
  [`../../shared/policies/dependency-tree-inspection.md`](../../shared/policies/dependency-tree-inspection.md) (#730).
- The execution boundary it reuses unchanged:
  [`../../shared/policies/runtime-validation.md`](../../shared/policies/runtime-validation.md),
  [`../../shared/policies/trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md).
