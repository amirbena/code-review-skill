# Policy — Existing Review Evidence (PR application)

`github-pr-review`'s **thin application** of the shared Existing Review
Evidence model. Canonical index: [`github-review.md`](github-review.md). The
semantics — what counts as existing review evidence, "evidence and context,
not authority," the still-relevant / resolved / stale / duplicate /
settled-decision / speculative-discussion classification, the settled-decision
bar, and the read-only / decision-ownership / target boundaries — are owned by
[`review-evidence.md`](../../../shared/policies/review-evidence.md) and are not
restated here.

This file adds only what is specific to a GitHub Pull Request, and defers the
same-HEAD duplicate-suppression mechanics to
[`pr-scope.md`](pr-scope.md), "Existing review awareness."

## Source

The PR's own prior review activity, retrieved (paginated) alongside the rest
of PR scope:

- prior submitted reviews — each review's state (`APPROVED` /
  `CHANGES_REQUESTED` / `COMMENTED`) and body;
- inline review comments and their threads;
- issue comments on the PR conversation;
- resolved/unresolved state of review threads, where available.

Retrieval of all four surfaces, paginated to exhaustion — with a concrete
integration example (`gh api` for reviews/comments, GraphQL `reviewThreads`
for `isResolved`) — is owned by [`pr-scope.md`](pr-scope.md), "Existing
review awareness" → "Retrieving prior review activity". Incomplete history
never blocks the review; it only bars claiming complete deduplication.

Another human reviewer's independent feedback is never suppressed merely
because it is similar to a finding of this review.

## Authorship and resolved-thread state

Classify each prior item per the shared policy's "Comment authorship: human
review vs. automation output" and "Interpret prior evidence against the
current target":

- automation / bot comments (CI status, coverage, deployment previews,
  code-scanning summaries, "please rebase") contribute observations only and
  never by themselves establish a settled decision, a maintainer
  clarification, reviewer acceptance, or an authoritative correctness
  resolution;
- a GitHub thread's `resolved` flag is evidence of a past conclusion, not
  proof the current PR HEAD is correct — a resolved thread whose defect the
  current HEAD reintroduces is a still-relevant finding of this review,
  reported with fresh evidence.

## Use it to avoid three failures

Classify each relevant prior item per the shared policy, then use the result
to avoid:

- **repeating settled findings unnecessarily** — a prior finding already
  resolved on the current PR HEAD is not re-reported; a prior finding this
  review independently rediscovers is reconciled into one finding, not two
  (see [`finding-placement.md`](finding-placement.md), "No duplicate
  findings," and [`pr-scope.md`](pr-scope.md), "Existing review awareness");
- **contradicting a settled decision without new evidence** — a
  design/architecture question explicitly concluded in the PR discussion (or
  a direct maintainer clarification) is not reopened unless the current PR
  HEAD carries concrete new evidence per the shared policy's "Settled
  decisions";
- **missing an unresolved previously identified issue** — a prior finding
  whose condition still holds against the current PR HEAD is a finding of
  this review, even though a prior reviewer raised it first.

## Do not blindly inherit

Prior findings, severities, and decisions are not already-verified facts
merely because a prior review exists. This Skill independently applies
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`evidence.md`](../../../shared/policies/evidence.md), and
[`severity.md`](../../../shared/policies/severity.md) and reaches its own
conclusions — see [`reviewer-delta-review.md`](reviewer-delta-review.md),
"Different reviewer: normal review, no inherited judgment."

## HEAD changes reset applicability

A changed PR HEAD starts a new authoritative review state. Prior findings may
inform investigation but are neither automatically resolved nor automatically
applicable against the new HEAD — retrieve and review the new state, and
re-classify prior evidence against it. An old approval or a matching prior
finding identity never authorizes the new HEAD (see
[`pr-scope.md`](pr-scope.md), "Existing review awareness," and
[`review-output.md`](review-output.md), "HEAD revalidation").

## Boundaries

- **Read-only retrieval.** Inspecting prior reviews/comments never becomes a
  publication action; the batched single-review submission and maximum
  positive action (**Approve**) are unchanged.
- **Decision ownership.** Reconciled prior findings and decisions inform this
  review; they never substitute for its own severity classification or its
  mechanical decision derivation per [`review-output.md`](review-output.md),
  "Final decision."
- **Not the target.** Prior review evidence never becomes an additional
  review target; the PR delta remains the review target.
