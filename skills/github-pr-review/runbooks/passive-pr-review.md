# Runbook — Passive PR Review

Reviews an existing GitHub Pull Request **without publishing anything**.
Applies shared policies:
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md),
[`evidence.md`](../../../shared/policies/evidence.md),
[`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
plus this Skill's own
[`github-review.md`](../policies/github-review.md).

## Flow

```text
PR
    ↓
retrieve metadata
    ↓
retrieve HEAD
    ↓
retrieve diff
    ↓
inspect context
    ↓
review
    ↓
return human-readable report
```

## Steps

1. Resolve the repository and PR from the given input (PR URL, PR number
   + repository context, or repository + PR number).
2. Using `gh` where available, retrieve PR metadata, base/head SHA,
   changed files, and the full diff.
3. Load applicable repository-local instructions and relevant surrounding
   context (tests, contracts, schemas, architecture docs).
4. Review per
   [`review-scope.md`](../../../shared/policies/review-scope.md).
5. Classify findings per
   [`severity.md`](../../../shared/policies/severity.md) with evidence per
   [`evidence.md`](../../../shared/policies/evidence.md), using the shared
   finding shape in
   [`finding.md`](../../../shared/templates/finding.md).
6. Render a human-readable report using the same structure as
   [`../templates/external-review-summary.md`](../templates/external-review-summary.md)
   and [`../templates/inline-finding.md`](../templates/inline-finding.md)
   (as a plain-text/return-value report, not published to GitHub).

## Constraints

- No inline comments, Approve, Request Changes, or PR metadata mutation
  of any kind.
- If `gh` is unavailable or unauthenticated, report the missing
  capability explicitly rather than inventing PR state (see
  [`../policies/github-review.md`](../policies/github-review.md)).

This runbook is the safe default for inspecting a PR when active
publication is unnecessary, unavailable, or not yet authorized — see
[`active-pr-review.md`](active-pr-review.md) for when publication is
required.
