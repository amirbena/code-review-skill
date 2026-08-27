# Policy — Review Reasoning

Governs how `github-pr-review` reasons about a PR's changes once scope is
established. Canonical index: [`github-review.md`](github-review.md). This
reasoning applies only after review authority
([`review-authority.md`](review-authority.md)) and reviewer-mode resolution
([`reviewer-delta-review.md`](reviewer-delta-review.md)) have already run — it
never determines whether or how much of the PR is in scope, only how that
already-established scope is analyzed.

The reasoning-quality invariants below are owned once, in this Skill's shared
[`review-scope.md`](../../../shared/policies/review-scope.md) and
[`evidence.md`](../../../shared/policies/evidence.md) policies, and shared
identically with `local-code-review` so both Skills apply one review-quality
standard — this file does not restate their full text. What follows is this
Skill's own PR-specific application: where each invariant fits in the PR
review flow, and light fallback guidance for a reviewing engine with no
native full-codebase context.

## Logical Cohort Review

The durable invariant — review related changes together rather than treating
files or hunks as isolated units — is owned by
[`review-scope.md`](../../../shared/policies/review-scope.md), "Related
changes as one unit." Apply it to this invocation's complete established
scope: the full diff for a normal review, or the bounded delta plus
surrounding context for a delta re-review (see
[`reviewer-delta-review.md`](reviewer-delta-review.md), "Same reviewer: delta
boundary and scope"). No PR-specific grouping mechanics beyond that shared
invariant are prescribed here.

## Root-Cause and Model-Completeness Review

When related candidate findings indicate one shared mechanism, apply
[`review-scope.md`](../../../shared/policies/review-scope.md), "Root-cause and
model-completeness pass," before finalizing findings. That shared section owns
the trigger, structural-vs-separate finding rule, model-completeness questions,
canonical-owner and external-package guidance, evidence requirements, and
re-review behavior; this PR-specific policy does not restate them.

## Code Impact / Dependency Analysis

The durable invariant — a finding located outside the changed lines is valid
only when the PR introduces, activates, exposes, breaks, or materially
affects it, never as an unrelated pre-existing-defect audit, scaled to the
change's realistic blast radius — is owned by
[`evidence.md`](../../../shared/policies/evidence.md), "Findings beyond the
changed lines."

When the reviewing engine has no native full-codebase or cross-reference
capability, bound dependency exploration to callers, callees, interface
implementations, event producers/consumers, and tests directly relevant to a
changed symbol, contract, or schema, using ordinary repository search — stop
once that is enough to judge the PR's correctness. No dedicated code-graph
tool or vendor capability is required for this analysis.

Findings produced from this reasoning still require concrete evidence per
[`evidence.md`](../../../shared/policies/evidence.md) and
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md)
— a dependency relationship is relevant to a finding only when it demonstrates
a concrete defect, regression, contract violation, or other actionable issue,
never merely because a dependent file or symbol exists.
