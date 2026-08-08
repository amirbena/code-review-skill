# Runbook — Active PR Review

Reviews an existing GitHub Pull Request and publishes findings and a final
decision. Applies shared policies:
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md),
[`evidence.md`](../../../shared/policies/evidence.md),
[`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
plus this Skill's own
[`github-review.md`](../policies/github-review.md), and the shared
[`review-ownership.md`](../../../shared/policies/review-ownership.md).

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
   [`../../../shared/policies/review-ownership.md`](../../../shared/policies/review-ownership.md).
   If owned elsewhere, return `REVIEW ALREADY OWNED` and stop.
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
4. Resolve and record the authoritative PR HEAD SHA and the changed
   files.
5. Inspect existing review activity to avoid obvious duplicate
   publication against an unchanged HEAD.
6. **Discover applicable repository-local instructions** per
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md):
   for each changed file, look for `AGENTS.md` / `CLAUDE.md` at the
   target repository root and along that file's directory ancestry. Do
   this before reviewing so discovered conventions inform the review
   itself.
7. Review per
   [`review-scope.md`](../../../shared/policies/review-scope.md) and the
   instructions discovered in step 6 — they refine evaluation but never
   override this Skill's own safety boundaries (see
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
   "Instruction precedence"); classify findings per
   [`severity.md`](../../../shared/policies/severity.md) with evidence per
   [`evidence.md`](../../../shared/policies/evidence.md).
8. Publish inline findings using
   [`../templates/inline-finding.md`](../templates/inline-finding.md).
9. Publish the final human-readable summary using
   [`../templates/external-review-summary.md`](../templates/external-review-summary.md).
10. Re-check the current PR HEAD against the recorded HEAD (see
    [`../policies/github-review.md`](../policies/github-review.md), "HEAD
    revalidation"). If it changed, do not submit a decision for the stale
    SHA — review the new delta first.
11. Submit **Approve** or **Request Changes** per
    [`../policies/github-review.md`](../policies/github-review.md).
12. Stop. Never merge, never delete branches, never modify implementation
    code, never take ownership of repository lifecycle cleanup.
