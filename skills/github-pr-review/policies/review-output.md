# Policy — Review Output

Governs the analysis/publication boundary, batched review submission,
final summary, final decision, and HEAD revalidation for
`github-pr-review`. Canonical index:
[`github-review.md`](github-review.md).

## Analysis phase vs. publication phase

These are strictly separate, and publication never begins until analysis
is complete:

```text
analysis phase                          publication phase
───────────────                         ─────────────────
inspect file                            all reviewable files processed
    ↓                                       ↓
discover candidate finding              evidence verified
    ↓                                       ↓
record internally, keep reviewing       findings deduplicated
    ↓                                       ↓
    ...                                 severity finalized
    ↓                                       ↓
scope complete                         inline locations resolved
                                            ↓
                                        decision finalized
                                            ↓
                                        submit one review
```

A candidate finding may be confirmed, downgraded, upgraded, merged with
another finding, discarded after further evidence, or have its location
changed at any point during the analysis phase. Nothing is published
during this phase — no comment, no partial review, no decision. Only the
finalized set of findings, produced once analysis is complete, is
eligible for publication. This prevents noisy comment streams,
contradictory or duplicate comments, publishing findings that are later
discovered to be false, and unnecessary notification spam.

## Batched review construction and submission

`github-pr-review` MUST NOT publish a comment, or any part of a review,
as each finding is discovered. Findings accumulate internally during
analysis (see "Analysis phase vs. publication phase") and are published
together, once, as a single coherent GitHub review submission:

```text
finalized findings
    ↓
resolve inline eligibility (see finding-placement.md)
    ↓
one review body                one inline comment per
(review-summary.md shape,      inline-eligible finding
full findings only for              (inline-finding.md)
non-inline findings, summary-
pointers for inline ones)
    ↓                                ↓
        one GitHub review submission
        (body + inline comments + event)
```

**Default path — atomic submission.** When the available GitHub
integration supports creating a review with a body, an array of inline
comments, and an event in a single request (for example, the GitHub REST
"create a review for a pull request" operation, which accepts `body`,
`comments[]`, and `event` together), use it. This is the default and
preferred mechanism: it produces exactly one review object and one
notification, containing every finalized inline finding at once.

**Fallback path — still one review.** If the available integration
cannot submit body, comments, and event atomically, use the minimum
number of calls that still yield exactly one review object from the PR
author's perspective: open one pending/draft review, attach every
finalized inline comment to that same pending review, then submit it
once with the body and event. Do not create standalone comments outside
a review object, and do not submit more than one review event for one
finalized set of findings.

**Prohibited shapes**, regardless of which path is used:

```text
inspect file A → publish comment
inspect file B → publish another comment
inspect file C → publish another comment
...                                                    ✗ prohibited

finding discovered → notification
finding discovered → notification
finding discovered → notification                     ✗ prohibited
```

The author receives one coherent review event, not a stream of
interruptions.

## Final summary

A single human-readable review body, using
[`../templates/external-review-summary.md`](../templates/external-review-summary.md)
(the shared shape in
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md)),
is constructed from the finalized findings and submitted as part of the
one review submission above. When publication is unavailable, it is
instead returned to the caller with publication status.

## Remediation guidance

Apply the shared
[`remediation-guidance.md`](../../../shared/policies/remediation-guidance.md)
after findings and severity are finalized. A GitHub finding may include one
concise, evidence-grounded **Recommended direction** aimed at the root cause or
canonical owner. Do not emit `local-code-review`'s full **Implementation
prompt** or a coding task with workflow/commit instructions. Guidance is
advisory and cannot change finding identity, severity, Approve/Request Changes,
or active/passive mutation boundaries.

## Final decision

- **Review reasoning result** is computed independently: either clean, or
  blocking findings (unresolved P0/P1).
- **Approve** — allowed when no unresolved P0 exists, no unresolved
  blocking P1 exists, and the current PR HEAD equals the reviewed HEAD.
  P2 findings may remain.
- **Request Changes** — used when an unresolved P0 or unresolved blocking
  P1 exists.

Approve or Request Changes is submitted only when the authenticated
reviewer is eligible to submit that formal event. The reasoning result is
still reported when GitHub submission is unavailable.

Report reasoning and mutation separately:

```text
Reasoning: REVIEW CLEAN | CHANGES REQUIRED | REVIEW INCOMPLETE | NO NEW DELTA | JIRA CONTEXT UNRESOLVED
Comments: COMMENTS PUBLISHED | COMMENTS NOT PUBLISHED | NOT REQUESTED
Decision: REVIEW SUBMITTED | REVIEW NOT SUBMITTED | NOT REQUESTED
```

`NO NEW DELTA` applies only when the current reviewer is the same
identity as the immediately preceding completed review and the
previously reviewed SHA equals the current PR HEAD — see
[`reviewer-delta-review.md`](reviewer-delta-review.md), "Same reviewer:
delta boundary and scope." No new review is submitted in this case.

`JIRA CONTEXT UNRESOLVED` applies only when the caller supplied a Jira
reference that could not be resolved to normalized context — see
[`review-context.md`](review-context.md), "Jira context resolution (PR
application)," and the shared
[`review-context.md`](../../../shared/policies/review-context.md), "Jira
context resolution." The Jira-scoped review is not performed: no diff
grading, no inference of the ticket from its key/branch/PR title, and no
Approve/Request Changes for a scope never established. Comments/Decision are
`NOT REQUESTED`. Re-invoking without a Jira reference yields a normal
unscoped review.

`REVIEW SUBMITTED` identifies the accepted event (`APPROVE`,
`REQUEST_CHANGES`, or `COMMENT`). It never follows merely from a successful
analysis; only a confirmed GitHub response establishes publication.

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

## Submission ordering

```text
review complete PR scope
    ↓
finalize findings (dedupe, severity, inline eligibility)
    ↓
verify current PR HEAD
    ↓
construct one review: body + inline comments + event
    ↓
submit that one review submission
or report why no formal review can be submitted
```

Verifying HEAD happens immediately before constructing/submitting the
review, not after — see "HEAD revalidation" above. The review body and
inline comments are always submitted together as one review submission
per "Batched review construction and submission" above; there is no
separate "publish inline comments" step followed later by a separate
"publish summary" step.
