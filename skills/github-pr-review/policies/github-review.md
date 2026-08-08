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

## Inline comment eligibility

Not every finding is forced inline. During finalization, resolve each
finding's placement:

- **Inline** — prefer this when the finding maps to a specific changed
  file, a specific changed line or narrow changed range represents the
  issue, that location is valid in the PR diff, and inline placement
  materially improves understanding. Rendered with
  [`../templates/inline-finding.md`](../templates/inline-finding.md).
- **Review body** — used when the issue spans multiple files, is
  architectural/systemic, concerns missing behavior with no natural
  changed-line anchor, the relevant location falls outside the changed
  diff, GitHub cannot attach a comment there, the finding concerns review
  completeness itself, or forcing an inline location would mislead.
  Rendered with the full-finding form in
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md)
  inside [`../templates/external-review-summary.md`](../templates/external-review-summary.md).

No valid inline anchor is never a reason to drop a finding — it changes
where the finding's one authoritative full representation lives, never
whether it is represented at all.

## Batched review construction and submission

`github-pr-review` MUST NOT publish a comment, or any part of a review,
as each finding is discovered. Findings accumulate internally during
analysis (see "Analysis phase vs. publication phase") and are published
together, once, as a single coherent GitHub review submission:

```text
finalized findings
    ↓
resolve inline eligibility (above)
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

## Rejected inline location fallback

If GitHub rejects a resolved inline location while constructing or
submitting the review (for example, the line is outside the diff's
commentable range, or a side/position mismatch), the finding MUST NOT be
dropped and MUST NOT be silently reattached to an unrelated line.
Instead, move that finding's full representation into the review body
(the same full-finding form used for non-inline findings) and continue
constructing/submitting the rest of the review normally. Prefer
completing one coherent review submission over abandoning the whole
submission; if the integration cannot recover mid-submission, retry the
review construction once with the affected finding moved to the body,
rather than repeatedly retrying the same rejected inline location.

## No duplicate findings

Each finding has exactly one authoritative full representation, per
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Rules." When a finding is published in full as an inline comment, the
review body's Findings section uses only the summary-pointer form
(severity, title, file:line) for it — never the full evidence/impact/
recommended-direction text a second time. When a finding has no inline
comment (no valid anchor, or a rejected location moved to the body per
above), its full representation appears once, in the body.

## Final summary

A single human-readable review body, using
[`../templates/external-review-summary.md`](../templates/external-review-summary.md)
(the shared shape in
[`../../../shared/templates/review-summary.md`](../../../shared/templates/review-summary.md)),
is constructed from the finalized findings and submitted as part of the
one review submission above. When publication is unavailable, it is
instead returned to the caller with publication status.

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
Reasoning: REVIEW CLEAN | CHANGES REQUIRED | REVIEW INCOMPLETE
Comments: COMMENTS PUBLISHED | COMMENTS NOT PUBLISHED | NOT REQUESTED
Decision: REVIEW SUBMITTED | REVIEW NOT SUBMITTED | NOT REQUESTED
```

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

## Self-review capability

`github-pr-review` is a reviewer role that requires genuine
reviewer/author separation to mean anything. Preventing an implementing
Agent from ever invoking this Skill against its own PR is primarily the
calling system's orchestration responsibility, not this Skill's own. This
guard is this Skill's complete, self-contained fallback for the case
where that orchestration boundary is not honored and this Skill is
invoked anyway — understanding and enforcing it requires nothing beyond
this policy.

This check runs **first, before any other step** — before retrieving the
paginated diff, before discovering repository instructions, before any
review reasoning — for both passive and active review, regardless of
which runbook was entered:

```text
resolve authenticated GitHub identity
resolve PR author
    ↓
same identity?
    ↓ yes
SKIP immediately — no diff analysis, no findings, no comments,
no summary, no decision
```

When the authenticated identity and the PR author are the same account,
this Skill terminates immediately with `REVIEW SKIPPED`. It must not
proceed to: read or analyze the diff, generate findings, generate a
review summary, emit `REVIEW CLEAN`, create inline comments, submit
general comments, approve the PR, or request changes. Output is short and
explicit:

```text
REVIEW SKIPPED

The authenticated GitHub user is the PR author.
Self-review is intentionally not performed.
```

This is a hard stop, not a degraded review: it is distinct from the
"Can inspect, cannot mutate" or "Comment-capable, decision-ineligible"
capability states below, which still complete reasoning and report a
recommendation. Self-review completes no reasoning at all.

If the authenticated identity cannot be resolved with confidence, do not
assume it differs from the PR author merely for convenience; treat
resolution failure as its own explicit incapability rather than silently
defaulting to a full review.

## Capability matrix

Resolve capability for the specific PR, identity, repository policy, token,
and intended event. Do not infer it from authentication or a broad role alone.

| State | Reasoning | Comments | Formal decision |
|---|---|---|---|
| Eligible external reviewer | Complete when scope is complete | Publish when authorized | Submit `APPROVE` or `REQUEST_CHANGES` as reasoned |
| PR author (self-review) | **None performed** — `REVIEW SKIPPED` at entry, before scope retrieval | None published | None submitted |
| Can inspect, cannot mutate | Complete when scope is complete | Do not publish | Return recommendation and `REVIEW NOT SUBMITTED` |
| Comment-capable, decision-ineligible | Complete when scope is complete | May publish permitted comments | Return recommendation and `REVIEW NOT SUBMITTED` |
| Draft PR | Review work-in-progress; complete only if scope is complete | May publish permitted feedback | Intentionally do not submit Approve/Request Changes until ready for review |
| Fork PR | Complete when upstream PR scope is accessible | Publish only with confirmed upstream capability | Never assume head-fork access grants upstream mutation capability |

GitHub defines draft PRs as work in progress that are not ready for formal
review and cannot merge. This Skill may still analyze and provide permitted
comments, but intentionally leaves the formal decision unsubmitted until the
PR is marked ready. It never changes draft/ready state.

For fork PRs, inspect the upstream PR and distinguish upstream repository
review permission from access to the contributor's head repository. Never run
or approve fork-provided workflows, expose credentials, push to the fork, or
assume same-repository permissions. A permission failure degrades to the
corresponding inspect/comment/passive state above.

Event support is probed independently. GitHub review events are `COMMENT`,
`APPROVE`, and `REQUEST_CHANGES`; review creation requires suitable Pull
requests write permission, while repository/organization policy can further
limit Approve or Request Changes. A failed or forbidden event is reported,
not retried as a stronger event and not represented as success.

## Complete PR scope and pagination

Never assume one API/CLI response contains the complete PR. Follow pagination
to exhaustion for changed files and for every collection used to establish
review state or deduplication, including reviews, review comments, issue
comments, commits, and relevant checks/statuses. Prefer page sizes up to the
documented maximum, but use response pagination metadata rather than a short
page guess where available.

Compare the retrieved changed-file total with authoritative PR metadata when
available. GitHub's REST changed-files endpoint is paginated and returns at
most 3,000 files. If the authoritative count exceeds an API cap, pages cannot
be exhausted, or totals disagree, obtain the complete name/status set from
repository Git data (base...reviewed HEAD) when available. Otherwise return
`REVIEW INCOMPLETE`; never approve or claim the full PR was reviewed.

Treat per-file API patches and aggregate diff media as potentially absent or
truncated. Fall back to fetching the exact base and reviewed HEAD and computing
the diff locally, or retrieve exact file blobs/diffs individually. Validate
that every changed path has an inspectable representation or an explicit
binary/opaque limitation under
[`../../../shared/policies/file-reviewability.md`](../../../shared/policies/file-reviewability.md).
If material scope remains unavailable, report what is missing, publish no
formal Approve/Request Changes decision, and do not lower review standards or
sample arbitrary files.

## Existing review awareness

Before publishing an active review, retrieve all relevant paginated reviews,
review comments, and issue comments from the authenticated reviewer/workflow.
Do not suppress another human reviewer's independent feedback merely because
it is similar.

For each candidate finding, compute a deterministic internal identity from
the PR HEAD SHA, normalized file path, relevant side and line/range (or a
stable cross-cutting location), severity, and normalized finding title or
category. Human-facing `F1`, `F2`, ... display IDs remain separate; a hash or
serialized identity need not be exposed. When the same workflow already
published the same identity for the same PR and HEAD, do not publish the
finding again, though it may still appear in returned reasoning. If complete
prior activity cannot be retrieved, report deduplication uncertainty rather
than asserting idempotency.

A changed HEAD starts a new authoritative review state. Prior findings may
inform investigation, but they are neither automatically resolved nor
automatically applicable. Retrieve and review the complete new state; an old
approval or duplicate identity never authorizes the new HEAD.

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
review, not after — see "HEAD revalidation" below. The review body and
inline comments are always submitted together as one review submission
per "Batched review construction and submission" above; there is no
separate "publish inline comments" step followed later by a separate
"publish summary" step.

## GitHub integration contract

Use an available authenticated GitHub integration when it can retrieve the
complete required state and perform the permitted publication action. If it
cannot, use another supported GitHub API or CLI mechanism. When no available
mechanism can establish complete state, degrade honestly to the supported
passive or `REVIEW INCOMPLETE` behavior.

Concrete tools are implementations of this capability contract, not canonical
requirements. For example, when GitHub CLI is the available integration,
final decisions may use `gh pr review --approve` /
`gh pr review --request-changes`, and line-specific comments may use `gh api`.
Equivalent authenticated integrations are valid. Do not hardcode one API
version when the available integration supports a current equivalent.
