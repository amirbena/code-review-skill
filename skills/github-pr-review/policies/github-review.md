# Policy — GitHub Review

Governs how `github-pr-review` interacts with GitHub Pull Requests,
independent of the specific runbook in use (see
[`../runbooks/passive-pr-review.md`](../runbooks/passive-pr-review.md) and
[`../runbooks/active-pr-review.md`](../runbooks/active-pr-review.md)).
Builds on the shared
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md), and
[`evidence.md`](../../../shared/policies/evidence.md) policies — this file
adds only what is specific to GitHub delivery.

## Authoritative PR HEAD

The exact PR HEAD SHA under review must be recorded at the start of
review. Any final decision must apply to that same SHA — see "HEAD
revalidation" below.

## Inline comments

Findings are attached to the narrowest relevant changed line whenever
possible, using [`../templates/inline-finding.md`](../templates/inline-finding.md).
Cross-cutting findings that cannot attach meaningfully to one line go into
the final summary instead.

## Final summary

A single human-readable review summary, using
[`../templates/external-review-summary.md`](../templates/external-review-summary.md),
is always published after inline findings and before the final decision.

## Final decision

- **Approve** — allowed when no unresolved P0 exists, no unresolved
  blocking P1 exists, and the current PR HEAD equals the reviewed HEAD.
  P2 findings may remain.
- **Request Changes** — used when an unresolved P0 or unresolved blocking
  P1 exists.

Maximum automated positive action is **Approve**. This Skill never merges
automatically, never deletes branches, never modifies implementation
code, and never takes ownership of repository lifecycle cleanup for an
externally supplied PR.

## HEAD revalidation

Immediately before submitting the final decision, refresh PR metadata and
compare the current HEAD against the reviewed HEAD:

```text
reviewed HEAD
    ↓
refresh PR
    ↓
current HEAD
```

If they differ, the review is stale: do not submit the old decision.
Review the new delta, recompute findings, and submit a decision only for
the current HEAD.

## Review/repository access prerequisite

Successful GitHub authentication alone does not imply the authenticated
identity has legitimate review access to the target repository/PR. Before
posting comments or submitting a review decision, verify:

- the authenticated GitHub identity;
- that the target repository/PR is accessible to that identity;
- that the identity has sufficient capability to submit the intended
  review action (comment, Approve, Request Changes).

This may be established through GitHub metadata/capabilities available to
the authenticated identity (see
[`../runbooks/active-pr-review.md`](../runbooks/active-pr-review.md)).

If active review permissions are unavailable:

- do not fake successful publication;
- do not claim comments were submitted;
- do not claim Approve or Request Changes was submitted;
- fall back to passive review when possible;
- return the review report and clearly state that GitHub publication was
  unavailable.

This is a separate concern from Agent review *ownership* — see
[`../../../shared/policies/review-ownership.md`](../../../shared/policies/review-ownership.md),
"Access vs. Ownership."

## Existing review awareness

Before publishing an active review, inspect existing review activity
sufficiently to avoid obvious duplicate publication. Do not blindly
repost an identical finding already made by the same review flow against
the same, unchanged HEAD. A new HEAD may require re-review; an old
approval is never authoritative for a changed HEAD.

## Submission ordering

```text
review PR
    ↓
collect findings
    ↓
publish inline P0/P1/P2 comments
    ↓
publish final human-readable review summary
    ↓
verify current PR HEAD
    ↓
submit Approve / Request Changes
```

If the GitHub API permits submitting comments and the final review
atomically in a single review operation, that is also acceptable provided
the visible ordering and resulting review semantics remain equivalent
(developer sees issues, then a coherent summary, then the review state).

## GitHub CLI contract

`gh` is the preferred integration mechanism:

- final review decisions use the equivalent of
  `gh pr review --approve` / `gh pr review --request-changes`;
- line-specific inline comments, where higher-level `gh pr` commands are
  insufficient, may use `gh api` against the GitHub Pull Request review
  APIs.

The canonical contract is described conceptually; it does not hardcode
one specific API version when the runtime can use the currently supported
API.
