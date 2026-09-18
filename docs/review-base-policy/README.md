# Review-Base Policy Compliance — Design Record

Repository-development design record for the reviewer's **review-base
policy compliance** capability: recognizing when a change under review
targets an integration base that reliably violates the target
repository's own review-base policy, and reporting that as one blocking
P0 before implementation findings.

Like [`../dependency-supply-chain/README.md`](../dependency-supply-chain/README.md),
[`../api-compatibility/README.md`](../api-compatibility/README.md), and
[`../review-context/README.md`](../review-context/README.md), this is a
repository-development doc: **not** packaged into either Skill archive,
and no packaged Skill resource depends on it. It is an explanatory /
design record — the normative, packaged rule lives in
[`../../shared/policies/review-base-policy.md`](../../shared/policies/review-base-policy.md),
which references this document by name (not by link, since this is not a
packaged resource).

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`review-base-policy-model.md`](review-base-policy-model.md) | The resolution model for the repository-resolved review base, the ranked signals, the fail-closed rule, the per-Skill application, and the smallest useful first implementation. | [#134](https://github.com/amirbena/code-review-skill/issues/134) |

## Related

- The packaged, operative rule a reviewer actually applies:
  [`../../shared/policies/review-base-policy.md`](../../shared/policies/review-base-policy.md).
- Repository-instruction discovery this capability reuses without
  duplicating:
  [`../../shared/policies/repository-instructions.md`](../../shared/policies/repository-instructions.md).
- Stack-topology detection and the effective review base for a stack
  layer, whose resolved root this capability checks:
  [`../../skills/github-pr-review/policies/stacked-pr-review.md`](../../skills/github-pr-review/policies/stacked-pr-review.md).
- The local Skill's own review-base resolution for Git mechanics, which
  this capability evaluates but does not redefine:
  [`../../skills/local-code-review/policies/repository-state.md`](../../skills/local-code-review/policies/repository-state.md).
- Severity and the mechanical decision derivation, which this capability
  never touches beyond classifying its own finding as P0:
  [`../../shared/policies/severity.md`](../../shared/policies/severity.md).
- The Review Target / Review Context / Repository Context vocabulary this
  capability consumes where already resolved, and does not redefine:
  [#45](https://github.com/amirbena/code-review-skill/issues/45),
  [#72](https://github.com/amirbena/code-review-skill/issues/72).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

## Non-goals

- Retargeting or editing a PR's base branch.
- Changing GitHub branch protection, rulesets, or required checks.
- General branch-naming validation unrelated to the review base.
- Publishing a GitHub status/check for this outcome (separate
  GitHub-native enforcement work, see
  [#49](https://github.com/amirbena/code-review-skill/issues/49)).
- A second Review Target / Review Context / Repository Context model.
- Guessing a repository-resolved review base when it cannot be reliably
  established — the fail-closed rule is load-bearing, not a fallback of
  last resort.
