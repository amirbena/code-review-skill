# Policy — GitHub Review

Canonical policy entrypoint for `github-pr-review`, independent of the
specific runbook in use (see
[`../runbooks/passive-pr-review.md`](../runbooks/passive-pr-review.md) and
[`../runbooks/active-pr-review.md`](../runbooks/active-pr-review.md)).
Builds on the shared
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md), and
[`evidence.md`](../../../shared/policies/evidence.md) policies. This file
owns the top-level review lifecycle, the ordering of major policy gates,
and cross-cutting invariants; each concern's normative rule lives in
exactly one canonical sub-policy, referenced below — this file does not
duplicate that prose.

## Canonical sub-policies, in authoritative order

```text
review-authority.md         identity, self-review guard, publication capability
        ↓
reviewer-delta-review.md    delta re-review vs. normal review mode
        ↓
pr-scope.md                 complete PR scope, pagination, prior-review awareness
        ↓
review-reasoning.md         logical cohorts, code impact / dependency analysis
        ↓
finding-policy.md           inline vs. body placement, one representation per finding
        ↓
review-output.md            analysis/publication boundary, batching, decision
```

This order is the authoritative dependency order: a later file's rules
assume every earlier file's gates have already resolved for this
invocation. [`review-authority.md`](review-authority.md) resolves first
and is never bypassed by anything downstream —
[`reviewer-delta-review.md`](reviewer-delta-review.md) explicitly runs
after its self-review guard, and
[`review-reasoning.md`](review-reasoning.md) explicitly reasons only
once review-authority and reviewer-mode resolution have already run. See
each file for its own cross-references; this list is not restated
per-section elsewhere.

## Authoritative PR HEAD

The exact PR HEAD SHA under review must be recorded at the start of
review. Any final decision must apply to that same SHA — see
[`review-output.md`](review-output.md), "HEAD revalidation."

## Review reasoning flow

Once [`review-authority.md`](review-authority.md) and
[`reviewer-delta-review.md`](reviewer-delta-review.md) resolve for this
invocation, review reasoning proceeds:

```text
PR intent → diff → logical cohorts → impacted dependency surface → findings
```

The diff remains the starting point of review, but not necessarily the
complete reasoning boundary — see
[`review-reasoning.md`](review-reasoning.md). For a delta re-review, this
reasoning flow applies to the reviewed delta and any surrounding context
required to validate it, per
[`reviewer-delta-review.md`](reviewer-delta-review.md), "Same reviewer:
delta boundary and scope"; it does not change the delta boundary itself.

## GitHub integration contract

Use an available authenticated GitHub integration when it can retrieve the
complete required state and perform the permitted publication action. If it
cannot, use another supported GitHub API or CLI mechanism. When no available
mechanism can establish complete state, degrade honestly to the supported
passive or `REVIEW INCOMPLETE` behavior.

Concrete tools are implementations of this capability contract, not canonical
requirements. For example, when GitHub CLI is the available integration,
final decisions may use `gh pr review --approve` /
`gh pr review --request-changes`, and line-specific comments may use `gh api`.
Equivalent authenticated integrations are valid. Do not hardcode one API
version when the available integration supports a current equivalent.
