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
review-authority.md         identity, self-review mutation boundary, publication capability
        ↓
review-action-authorization.md  review analysis vs. GitHub mutation authority;
                            recommendation-only default; trusted authorization
                            and reviewer independence; fail closed
        ↓
reviewer-delta-review.md    delta re-review vs. normal review mode
        ↓
pr-scope.md                 complete PR scope, pagination, prior-review awareness
        ↓
repository-checkout.md      optional isolated temporary checkout for richer
                            Repository Context; read-only; guaranteed cleanup
        ↓
review-context.md           optional supplied context (Jira / Issue / HLD / ADR /
                            plan / PR description); scope-boundary reasoning
        ↓
review-evidence.md          prior reviews/comments as Existing Review Evidence;
                            settled vs. speculative; no blind inheritance
        ↓
review-reasoning.md         logical cohorts, code impact / dependency analysis
        ↓
parallel-review.md          optional parallel workers per review dimension;
                            execution optimisation only; centralized aggregation
        ↓
finding-placement.md        inline vs. body placement, one representation per finding
        ↓
review-output.md            analysis/publication boundary, batching, decision
        ↓
review-status-enforcement.md  optional exact-HEAD machine-readable status;
                            blocking vs. positive authority; enforcement
                            detection; explicit opt-in required-check setup
```

This order is the authoritative dependency order: a later file's rules
assume every earlier file's gates have already resolved for this
invocation. [`review-authority.md`](review-authority.md) resolves first
and is never bypassed by anything downstream;
[`review-action-authorization.md`](review-action-authorization.md) builds
directly on it — it separates review analysis from GitHub mutation
authority, defaults to a non-mutating (recommendation-only) result, and
requires trusted authorization plus reviewer independence before any
`APPROVE` / `REQUEST_CHANGES` is submitted; its gate is enforced at
submission time in [`review-output.md`](review-output.md), "Review-action
authorization gate."
[`reviewer-delta-review.md`](reviewer-delta-review.md) explicitly runs
after the self-review mutation-boundary check, and applies to a
self-review exactly as to an external review;
[`repository-checkout.md`](repository-checkout.md) is optional, runs after
[`pr-scope.md`](pr-scope.md) has established the PR's base/head, and never
changes the Review Target — the PR delta;
[`review-context.md`](review-context.md) and
[`review-evidence.md`](review-evidence.md) are optional and run after
review-authority and reviewer-mode resolution, informing but never widening
the scope [`pr-scope.md`](pr-scope.md) establishes;
[`review-reasoning.md`](review-reasoning.md) explicitly reasons only once
review-authority and reviewer-mode resolution have already run; and
[`parallel-review.md`](parallel-review.md) is an optional execution
optimisation whose sequential and parallel forms must reach the same
findings and decision;
[`review-status-enforcement.md`](review-status-enforcement.md) is optional
and runs last — only after the verdict, HEAD revalidation, and the
review-action authorization gate in
[`review-output.md`](review-output.md) have resolved — and adds nothing
to the verdict or to native-event authority. See each file for its own
cross-references; this list is not restated per-section elsewhere. The shared semantics behind the
optional context files live in
[`review-context.md`](../../../shared/policies/review-context.md) and
[`review-evidence.md`](../../../shared/policies/review-evidence.md), and the
portable parallel contract in
[`parallel-review.md`](../../../shared/policies/parallel-review.md);
`local-code-review` applies the same shared context model.

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
