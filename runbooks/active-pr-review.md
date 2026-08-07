# Runbook — Active PR Review

Reviews an existing GitHub Pull Request and publishes findings and a final
decision. Applies policies: [`review-scope.md`](../policies/review-scope.md),
[`severity.md`](../policies/severity.md), [`evidence.md`](../policies/evidence.md),
[`github-review.md`](../policies/github-review.md),
[`review-ownership.md`](../policies/review-ownership.md),
[`repository-instructions.md`](../policies/repository-instructions.md).

## Flow

```text
PR
    ↓
verify authenticated identity
    ↓
verify repository/review access
    ↓
resolve authoritative HEAD
    ↓
review
    ↓
publish inline findings
    ↓
publish final summary
    ↓
re-check HEAD
    ↓
Approve or Request Changes
    ↓
stop
```

## Steps

1. Check for an existing Code Review Agent owner of this scope per
   [`../policies/review-ownership.md`](../policies/review-ownership.md). If
   owned elsewhere, return `REVIEW ALREADY OWNED` and stop.
2. Resolve the repository and PR; verify `gh` authentication and resolve
   the authenticated identity.
3. **Verify repository/review access** for that identity against the
   target repository/PR (see
   [`../policies/github-review.md`](../policies/github-review.md),
   "Review/repository access prerequisite"). Successful authentication
   alone is not sufficient.
   - If access cannot be confirmed: do not fake publication, do not claim
     Approve/Request Changes was submitted; fall back to
     [`passive-pr-review.md`](passive-pr-review.md) and clearly state
     that GitHub publication was unavailable.
4. Resolve and record the authoritative PR HEAD SHA.
5. Inspect existing review activity to avoid obvious duplicate
   publication against an unchanged HEAD.
6. Review per [`../policies/review-scope.md`](../policies/review-scope.md);
   classify findings per [`../policies/severity.md`](../policies/severity.md)
   with evidence per [`../policies/evidence.md`](../policies/evidence.md).
7. Publish inline findings using
   [`../templates/inline-finding.md`](../templates/inline-finding.md).
8. Publish the final human-readable summary using
   [`../templates/external-review-summary.md`](../templates/external-review-summary.md).
9. Re-check the current PR HEAD against the recorded HEAD (see
   [`../policies/github-review.md`](../policies/github-review.md), "HEAD
   revalidation"). If it changed, do not submit a decision for the stale
   SHA — review the new delta first.
10. Submit **Approve** or **Request Changes** per
    [`../policies/github-review.md`](../policies/github-review.md).
11. Stop. Never merge, never delete branches, never modify implementation
    code, never take ownership of repository lifecycle cleanup.
