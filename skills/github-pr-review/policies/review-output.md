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

It reads like a review a strong human reviewer would leave: verdict
first, then the findings that need action, then stop. Process and machine
state (review mode, SHAs, counts, action mode, mutation outcome) are
subordinate — a short trailing block, never the body. A self-review
publishes the **same** human-facing body as an informational `COMMENT`,
differing only by the closing disclosure line in
[`../templates/external-review-summary.md`](../templates/external-review-summary.md),
"Self-review (informational COMMENT)" — not by a separate, heavier
format.

## Remediation guidance

Apply the shared
[`remediation-guidance.md`](../../../shared/policies/remediation-guidance.md)
after findings and severity are finalized. A GitHub finding may include one
concise, evidence-grounded **Fix** direction (the finding contract's `Fix`
field — see
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md))
aimed at the root cause or canonical owner.
Do not emit `local-code-review`'s full **Implementation prompt** or a
coding task with workflow/commit instructions. Guidance is
advisory and cannot change finding identity, severity, Approve/Request Changes,
or active/passive mutation boundaries.

## Final decision

- **Review reasoning result** is computed independently: either clean, or
  blocking findings (unresolved P0/P1). This mechanical derivation is
  owned by
  [`../../../shared/policies/severity.md`](../../../shared/policies/severity.md)
  and is unchanged by anything in this section — the reasoning result
  always exists and is always reported.
- **Approve** (reasoned) — the reasoning result is clean: no unresolved
  P0, no unresolved blocking P1, and the current PR HEAD equals the
  reviewed HEAD. P2 findings may remain.
- **Request Changes** (reasoned) — an unresolved P0 or unresolved
  blocking P1 exists.

Submitting that reasoned result to GitHub as an `APPROVE` or
`REQUEST_CHANGES` **event** is a separate, authorized action — never an
automatic consequence of the reasoning result. A reasoned "Approve" is
not a GitHub `APPROVE`, and a GitHub `APPROVE` is not merge authority.
An event is submitted only when **both**:

- the authenticated reviewer is eligible to submit that formal event
  (see [`review-authority.md`](review-authority.md), "Review/repository
  access prerequisite"); **and**
- the **Review-action authorization gate** below permits it.

The reasoning result is still reported when GitHub submission is
unavailable, unauthorized, or withheld.

### Review-action authorization gate

The reasoning result (verdict) is produced first, by the mechanical
derivation above, and is always reported. This gate is applied only to
whether that verdict is *submitted* to GitHub as an event.

Immediately before submitting any `APPROVE` / `REQUEST_CHANGES` event
(and after "HEAD revalidation" below), apply
[`review-action-authorization.md`](review-action-authorization.md):

- **Self-review is absolute.** If the reviewer is the PR author — or a
  reviewer under the same controlling authority as the author (see
  [`review-authority.md`](review-authority.md), "Self-review capability"
  and "Authority separation, not just identity separation") — no formal
  `APPROVE` / `REQUEST_CHANGES` event is submitted, regardless of mode,
  natural-language request, or any authorization. The full analysis still
  ran; the result **may** be published as an informational review
  `COMMENT` (verdict, reviewed HEAD, findings, and that the formal
  decision was withheld by policy). A `COMMENT` is not approval,
  request-changes, or merge authorization and must not be used as a route
  to any of them. Report the verdict with the withheld reason, for
  example: `REVIEW CLEAN — GitHub review mutation withheld: reviewer is
  the PR author` or `CHANGES REQUIRED — GitHub review mutation withheld:
  reviewer is the PR author` (with `Comments: COMMENTS PUBLISHED`). The
  verdict is not rewritten because the event was withheld.
- Resolve the review-action mode. The default is **recommendation-only**
  — a full review and reasoning result, with **no** GitHub mutation.
  Passive review is always recommendation-only.
- **`APPROVE` is submitted only in explicitly-authorized auto-action
  mode**, i.e. only when trusted mutation authorization for this exact
  action is established, reviewer independence (authority separation, not
  just a different username) is established, and every guarantee in that
  policy's principle 7 holds at submission time. A clean reasoning result
  without that authorization stays non-mutating.
- **`REQUEST_CHANGES`** may be submitted in block-only or auto-action
  mode when reviewer independence and GitHub event permission hold; it
  does not additionally require auto-action authorization (it cannot
  approve or unblock — see that policy, "block-only").
- Ambiguity in mode, authorization provenance, authorization scope, or
  reviewer provenance **fails closed** to recommendation-only (or
  block-only for a blocking result where independence and permission
  hold). A caller never needs to say "do not approve" to get this.
- A relied-upon authorization is scoped to this invocation / repository /
  PR / reviewed HEAD / single action and cannot be replayed elsewhere.

Report reasoning and mutation separately:

```text
Reasoning:   REVIEW CLEAN | CHANGES REQUIRED | REVIEW INCOMPLETE | NO NEW DELTA | JIRA CONTEXT UNRESOLVED
Action mode: recommendation-only | block-only | explicitly-authorized auto-action
Comments:    COMMENTS PUBLISHED | COMMENTS NOT PUBLISHED | NOT REQUESTED
Decision:    REVIEW SUBMITTED | REVIEW NOT SUBMITTED | NOT REQUESTED
Mutation:    SUBMITTED (<event>) | WITHHELD (<reason>) | NOT REQUESTED
```

A `WITHHELD` reason is explicit and names the gate that stopped the
mutation (for example `WITHHELD (no trusted mutation authorization;
default recommendation-only)` or `WITHHELD (reviewer independence not
established)`). A clean reasoning result with a withheld approval is
reported as a clean result **and** a non-mutating outcome — never as
"approved."

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
