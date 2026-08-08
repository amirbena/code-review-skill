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
resolve authenticated identity and PR author
    ↓
same identity? → yes → REVIEW SKIPPED → stop
    ↓ no
check review ownership
    ↓
verify repository/review access
    ↓
resolve review mode (delta re-review vs. normal review)
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
finalize findings and resolve inline eligibility
    ↓
re-check HEAD
    ↓
construct one review: body + inline comments
    ↓
submit permitted Approve/Request Changes
or report why formal submission is unavailable
    ↓
stop
```

## Steps

1. **Before any other step**, resolve the repository and PR, then resolve
   the authenticated GitHub identity and the PR author and compare them,
   per [`../policies/github-review.md`](../policies/github-review.md),
   "Self-review capability." If they are the same account, terminate
   immediately with `REVIEW SKIPPED` — do not check review ownership,
   verify access, retrieve PR scope, review the diff, or produce any
   finding. This check precedes and is independent of the ownership check
   in step 2.
2. Check for an existing Code Review Agent owner of this scope per
   [`../../../shared/policies/review-ownership.md`](../../../shared/policies/review-ownership.md).
   If owned elsewhere, return `REVIEW ALREADY OWNED` and stop.
3. **Verify repository/review access** for the authenticated identity
   against the target repository/PR (see
   [`../policies/github-review.md`](../policies/github-review.md),
   "Review/repository access prerequisite"). Successful authentication
   alone is not sufficient.
   - If access cannot be confirmed: do not fake publication, do not claim
     Approve/Request Changes was submitted; fall back to
     [`passive-pr-review.md`](passive-pr-review.md) and clearly state
     that GitHub publication was unavailable.
4. **Resolve review mode** per
   [`../policies/github-review.md`](../policies/github-review.md),
   "Reviewer ownership and delta re-review." Retrieve the immediately
   preceding completed review of this PR, if any, and its reviewer
   identity and reviewed SHA. If the current authenticated reviewer is
   the same identity as that reviewer, and the previously reviewed SHA
   can be established reliably, this invocation is a **delta re-review**
   bounded by that SHA and the current PR HEAD; otherwise (no previous
   completed review, a different reviewer, or any ambiguity in reviewer
   identity or the reviewed SHA) it is a **normal review**. If the
   previously reviewed SHA already equals the current PR HEAD, stop here
   with the `NO NEW DELTA` reasoning result — do not manufacture a new
   review.
5. Resolve and record the authoritative PR HEAD SHA. For a normal
   review, retrieve the complete paginated changed-file set and complete
   diff per "Complete PR scope and pagination." For a delta re-review,
   retrieve the bounded delta between the previously reviewed SHA and the
   current PR HEAD, plus enough surrounding context to confirm the
   requested fix, absence of regression, and continued validity of the
   previous review's assumptions — full-PR retrieval is not required
   unless the delta later escalates to a normal review (see "Escalating
   from delta to full review"). Reconcile the retrieved count with PR
   metadata where available for a normal review. If any material scope
   remains missing or truncated, return `REVIEW INCOMPLETE`, report the
   missing scope, and do not submit a formal decision.
6. Determine event-specific capability, including draft, fork,
   comment-only, and permission-limited states, per
   [`../policies/github-review.md`](../policies/github-review.md),
   "Capability matrix." (Self-review was already resolved and excluded in
   step 1.) Do not treat authentication or repository access as proof
   that a formal review event is permitted.
7. Retrieve all pages of relevant prior reviews, review comments, and issue
   comments needed for review state and same-HEAD duplicate detection. If
   that history is incomplete, report the limitation rather than claiming
   idempotent publication.
8. **Discover applicable repository-local instructions** per
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md):
   for each file in this invocation's scope (the full changed-file set for
   a normal review, or the delta's changed files plus inspected
   surrounding context for a delta re-review), look for `AGENTS.md` /
   `CLAUDE.md` at the target repository root and along that file's
   directory ancestry. Do this before reviewing so discovered conventions
   inform the review itself.
9. Review per
   [`review-scope.md`](../../../shared/policies/review-scope.md) and the
   file-treatment rules in
   [`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
   applying the instructions discovered in step 8. Those instructions refine
   evaluation but never override this Skill's own safety boundaries (see
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
   "Instruction precedence"); classify findings per
   [`severity.md`](../../../shared/policies/severity.md) with evidence per
   [`evidence.md`](../../../shared/policies/evidence.md). For a delta
   re-review, if what is found here meets any "Escalating from delta to
   full review" condition in
   [`../policies/github-review.md`](../policies/github-review.md),
   switch this invocation to a normal review, retrieve the remaining full
   scope per "Complete PR scope and pagination," and continue reviewing
   from there rather than completing the review as delta-only.
10. Compute the stable internal identity defined by "Existing review
    awareness" for every finding. Keep `F1`, `F2`, ... as display IDs. Mark
    a finding as suppressed (not for publication, though it may still
    appear in returned reasoning) only when the same authenticated
    reviewer/workflow already published the same finding identity for this
    same PR HEAD.
11. **Finalize findings** — this is the boundary between analysis and
    publication (see
    [`../policies/github-review.md`](../policies/github-review.md),
    "Analysis phase vs. publication phase"): the finding set is now fixed.
    For each non-suppressed finding, resolve inline eligibility per
    [`../policies/github-review.md`](../policies/github-review.md),
    "Inline comment eligibility" — inline-eligible findings render with
    [`../templates/inline-finding.md`](../templates/inline-finding.md);
    the rest render in full within the review body. No publication has
    occurred yet.
12. Re-check the current PR HEAD against the recorded HEAD (see
    [`../policies/github-review.md`](../policies/github-review.md), "HEAD
    revalidation"), immediately before constructing the review. If it
    changed, do not construct or submit a review for the stale SHA —
    review the new delta first (re-evaluating escalation per step 9 if
    this was a delta re-review) and re-finalize findings against it.
13. Construct **one** review from the finalized findings: the body using
    [`../templates/external-review-summary.md`](../templates/external-review-summary.md)
    (full findings for non-inline ones, summary-pointers for inline ones —
    never both, per
    [`../policies/github-review.md`](../policies/github-review.md), "No
    duplicate findings") plus the array of inline comments for
    inline-eligible findings. State the review mode used (full review or
    delta re-review, with the previously reviewed SHA and current HEAD
    when delta) per
    [`../policies/github-review.md`](../policies/github-review.md),
    "Reporting the mode."
14. Submit that one review — body, inline comments, and the permitted
    **Approve** or **Request Changes** event together — per
    [`../policies/github-review.md`](../policies/github-review.md),
    "Batched review construction and submission." (Self-review was
    already excluded in step 1 and never reaches this step.) If GitHub
    rejects a specific resolved inline location during this step, apply
    the "Rejected inline location fallback" (move that finding's full
    form into the body) and complete the submission — do not drop the
    finding and do not abandon the rest of the review. If GitHub
    otherwise disallows the formal event, preserve the clean/blocking
    reasoning result and report why no final formal review was submitted.
    Never claim a GitHub mutation that did not succeed, and never submit
    more than one review for this finalized finding set.
15. Return separate reasoning, comments-publication, and decision-publication
    statuses per "Final decision," whether or not GitHub mutation succeeded.
16. Stop. Never merge, never delete branches, never modify implementation
    code, never take ownership of repository lifecycle cleanup.
