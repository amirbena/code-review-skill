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
resolve PR author
    ↓
verify repository/review access
    ↓
determine self-review submission capability
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
submit permitted Approve/Request Changes
or report why formal submission is unavailable
    ↓
stop
```

## Steps

1. Check for an existing Code Review Agent owner of this scope per
   [`../../../shared/policies/review-ownership.md`](../../../shared/policies/review-ownership.md).
   If owned elsewhere, return `REVIEW ALREADY OWNED` and stop.
2. Resolve the repository and PR; verify `gh` authentication and resolve
   the authenticated identity and the PR author's account identity.
3. **Verify repository/review access** for that identity against the
   target repository/PR (see
   [`../policies/github-review.md`](../policies/github-review.md),
   "Review/repository access prerequisite"). Successful authentication
   alone is not sufficient.
   - If access cannot be confirmed: do not fake publication, do not claim
     Approve/Request Changes was submitted; fall back to
     [`passive-pr-review.md`](passive-pr-review.md) and clearly state
     that GitHub publication was unavailable.
4. Compare the authenticated identity with the PR author and determine
   self-review submission capability per
   [`../policies/github-review.md`](../policies/github-review.md),
   "Self-review capability." Do not treat authentication or repository
   access as proof that a formal review event is permitted.
5. Resolve and record the authoritative PR HEAD SHA and the changed
   files.
6. Inspect existing review activity to avoid obvious duplicate
   publication against an unchanged HEAD.
7. **Discover applicable repository-local instructions** per
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md):
   for each changed file, look for `AGENTS.md` / `CLAUDE.md` at the
   target repository root and along that file's directory ancestry. Do
   this before reviewing so discovered conventions inform the review
   itself.
8. Review per
   [`review-scope.md`](../../../shared/policies/review-scope.md) and the
   instructions discovered in step 7 — they refine evaluation but never
   override this Skill's own safety boundaries (see
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
   "Instruction precedence"); classify findings per
   [`severity.md`](../../../shared/policies/severity.md) with evidence per
   [`evidence.md`](../../../shared/policies/evidence.md).
9. Publish inline findings using
   [`../templates/inline-finding.md`](../templates/inline-finding.md).
10. Publish the final human-readable summary using
   [`../templates/external-review-summary.md`](../templates/external-review-summary.md).
11. Re-check the current PR HEAD against the recorded HEAD (see
    [`../policies/github-review.md`](../policies/github-review.md), "HEAD
    revalidation"). If it changed, do not submit a decision for the stale
    SHA — review the new delta first.
12. Submit the permitted **Approve** or **Request Changes** event per
    [`../policies/github-review.md`](../policies/github-review.md). If the
    authenticated reviewer is the PR author or GitHub otherwise disallows
    the formal event, preserve the clean/blocking reasoning result and
    report why no final formal review was submitted. Never claim a GitHub
    mutation that did not succeed.
13. Stop. Never merge, never delete branches, never modify implementation
    code, never take ownership of repository lifecycle cleanup.
