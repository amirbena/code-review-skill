# Runbook — Active PR Review

Reviews an existing GitHub Pull Request and publishes findings and a final
decision. Applies shared policies:
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md),
[`evidence.md`](../../../shared/policies/evidence.md),
[`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
[`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
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
resolve authoritative HEAD
    ↓
retrieve complete paginated PR scope
    ↓
determine event-specific review capability
    ↓
review
    ↓
deduplicate same-HEAD findings
    ↓
publish permitted inline findings
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
4. Resolve and record the authoritative PR HEAD SHA. Retrieve the complete
   paginated changed-file set and complete diff per "Complete PR scope and
   pagination." Reconcile the retrieved count with PR metadata where
   available. If any material scope remains missing or truncated, return
   `REVIEW INCOMPLETE`, report the missing scope, and do not submit a formal
   decision.
5. Compare the authenticated identity with the PR author and determine
   event-specific capability, including self-review, draft, fork,
   comment-only, and permission-limited states, per
   [`../policies/github-review.md`](../policies/github-review.md),
   "Capability matrix." Do not treat authentication or repository
   access as proof that a formal review event is permitted.
6. Retrieve all pages of relevant prior reviews, review comments, and issue
   comments needed for review state and same-HEAD duplicate detection. If
   that history is incomplete, report the limitation rather than claiming
   idempotent publication.
7. **Discover applicable repository-local instructions** per
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md):
   for each changed file, look for `AGENTS.md` / `CLAUDE.md` at the
   target repository root and along that file's directory ancestry. Do
   this before reviewing so discovered conventions inform the review
   itself.
8. Review per
   [`review-scope.md`](../../../shared/policies/review-scope.md) and the
   file-treatment rules in
   [`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
   applying the instructions discovered in step 7. Those instructions refine
   evaluation but never override this Skill's own safety boundaries (see
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
   "Instruction precedence"); classify findings per
   [`severity.md`](../../../shared/policies/severity.md) with evidence per
   [`evidence.md`](../../../shared/policies/evidence.md).
9. Compute the stable internal identity defined by "Existing review
   awareness" for every finding. Keep `F1`, `F2`, ... as display IDs. Suppress
   publication only when the same authenticated reviewer/workflow already
   published the same finding identity for this same PR HEAD.
10. Publish permitted, non-duplicate inline findings using
   [`../templates/inline-finding.md`](../templates/inline-finding.md).
11. Publish the final human-readable summary when permitted using
   [`../templates/external-review-summary.md`](../templates/external-review-summary.md).
12. Re-check the current PR HEAD against the recorded HEAD (see
    [`../policies/github-review.md`](../policies/github-review.md), "HEAD
    revalidation"). If it changed, do not submit a decision for the stale
    SHA — review the new delta first.
13. Submit the permitted **Approve** or **Request Changes** event per
    [`../policies/github-review.md`](../policies/github-review.md). If the
    authenticated reviewer is the PR author or GitHub otherwise disallows
    the formal event, preserve the clean/blocking reasoning result and
    report why no final formal review was submitted. Never claim a GitHub
    mutation that did not succeed.
14. Return separate reasoning, comments-publication, and decision-publication
    statuses per "Final decision," whether or not GitHub mutation succeeded.
15. Stop. Never merge, never delete branches, never modify implementation
    code, never take ownership of repository lifecycle cleanup.
