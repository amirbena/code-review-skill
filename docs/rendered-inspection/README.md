# Rendered-UI Inspection — Design Record

Repository-development design record for **optional rendered-UI inspection**:
a bounded, supplementary evidence step in which the reviewer inspects a
rendered page when a PR materially changes rendered UI, optionally against a
trusted design reference (for example a Figma frame).

Like [`../finding-confidence/README.md`](../finding-confidence/README.md) and
[`../review-context/README.md`](../review-context/README.md), this is a
repository-development doc: **not** packaged into either Skill archive, and
no packaged Skill resource depends on it. It is contract-first and docs-only:
it ratifies, amends, or rejects each position of
[#615](https://github.com/amirbena/code-review-skill/issues/615) so that the
implementation children (C2–C5) and the documentation child (C6) never
re-decide semantics inside code PRs.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`rendered-inspection-contract.md`](rendered-inspection-contract.md) | The position-by-position ratification table with repository evidence, the conflict resolutions against each existing contract, the shared-policy amendments C2–C5 make, the locked contracts stated verbatim, the single-owner assignment of every design-reference decision, and the no-benchmark decision. | [#615](https://github.com/amirbena/code-review-skill/issues/615) |

## Epic and delivery

Parent epic [#614](https://github.com/amirbena/code-review-skill/issues/614).
This record is C1; it blocks
[#616](https://github.com/amirbena/code-review-skill/issues/616) (C2), after
which C3 [#617](https://github.com/amirbena/code-review-skill/issues/617),
C4 [#618](https://github.com/amirbena/code-review-skill/issues/618), and C5
[#620](https://github.com/amirbena/code-review-skill/issues/620) may proceed
in parallel; C6 [#619](https://github.com/amirbena/code-review-skill/issues/619)
documents the stabilized contract.

## Related

- Runtime boundary this step sits beside:
  [`../../shared/policies/runtime-validation.md`](../../shared/policies/runtime-validation.md),
  [`../../shared/policies/trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md).
- Severity and the mechanical decision, which this capability never touches:
  [`../../shared/policies/severity.md`](../../shared/policies/severity.md).
- The epistemic-state field this record reuses without adding a value:
  [`../finding-confidence/finding-confidence-model.md`](../finding-confidence/finding-confidence-model.md).
- Context provenance and evidence hierarchy the design-reference authority
  composes with:
  [`../../shared/policies/review-context.md`](../../shared/policies/review-context.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

## Non-goals

Packaged Skill behavior, policies, manifests, or tests (C2–C5); a benchmark
corpus; Wiki/user docs (C6); authentication flows, visual-regression
baselines, pixel-diffing, cross-browser matrices, video/trace capture,
crawling, accessibility audits beyond objective checks; static
design-to-source comparison, design-token or Code Connect analysis.
