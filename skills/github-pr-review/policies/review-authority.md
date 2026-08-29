# Policy — Review Authority

Governs the self-review mutation boundary and review/publication
capability for `github-pr-review`. Canonical index:
[`github-review.md`](github-review.md). Builds on the shared
[`review-ownership.md`](../../../shared/policies/review-ownership.md)
policy ("Access vs. Ownership") for the distinct Agent-level ownership
concern.

## Self-review capability

**Self-review analysis is allowed; self-approval is not.** A reviewer may
analyze its own work, follow the full review process, and produce
findings and a review verdict — but it must never submit a formal
`APPROVE` or `REQUEST_CHANGES` review on its own work.

Authorship is a **mutation boundary, not an analysis boundary**. When the
authenticated reviewer *is* the PR author — or shares the same
controlling authority as the PR author, see "Authority separation, not
just identity separation" below — this invocation is a **self-review**:

```text
resolve authenticated GitHub identity
resolve PR author + its controlling authority
    ↓
reviewer is the PR author, or same controlling authority?
    ↓ yes
self-review:
    analysis_allowed                = true   → run the full review
    formal_review_mutation_allowed  = false  → submit no APPROVE and no
                                               formal REQUEST_CHANGES on
                                               the reviewer's own work
```

A self-review runs the same review process as an external review — same
Issue/task intent, repository context, diff, previous review state,
reviewed HEAD, delta re-review resolution, severity policy, blocking-
finding handling, and stale-HEAD checks (see
[`reviewer-delta-review.md`](reviewer-delta-review.md),
[`pr-scope.md`](pr-scope.md), [`review-output.md`](review-output.md)).
Review quality is never weakened because the reviewer is also the author.

A self-review still produces and reports:

- findings, with P0/P1/P2 classifications;
- the mechanically derived verdict — `REVIEW CLEAN` or `CHANGES REQUIRED`
  (see [`../../../shared/policies/severity.md`](../../../shared/policies/severity.md));
- an explicit statement that the formal GitHub review event was withheld
  because the reviewer is the PR author.

It **may** publish its result to GitHub as an informational review
`COMMENT`, but it does **not** submit a formal review decision. `APPROVE`
on one's own work is always forbidden; `REQUEST_CHANGES` is not submitted
as a formal self-review action against the reviewer's own PR either (the
blocking verdict is still reported in the comment — the change is withheld
*submission* as a decision, not a softened verdict). A `COMMENT` is an
informational publication, not a governance decision, and never counts as
approval, request-changes, or merge authorization. The verdict is never
rewritten merely because formal mutation is unavailable — see
[`review-output.md`](review-output.md), "Final decision," and
[`review-action-authorization.md`](review-action-authorization.md),
"Self-review is allowed; self-approval is not."

Example outcomes:

```text
own PR, no blocking findings
    → REVIEW CLEAN
    → published as an informational COMMENT
    → GitHub review mutation withheld: reviewer is the PR author

own PR, an unresolved P1
    → CHANGES REQUIRED
    → published as an informational COMMENT (with the blocking findings)
    → GitHub review mutation withheld: reviewer is the PR author
```

There is no `REVIEW SKIPPED` for a self-review: analysis is not skipped,
only the formal GitHub event is. `MERGE` remains outside this Skill
entirely and is never introduced here.

If the authenticated identity or the PR author's controlling authority
cannot be resolved with confidence, do not assume separation merely for
convenience; treat the invocation as a self-review for the purpose of the
mutation boundary (fail closed — analysis still runs, the formal event is
still withheld).

### Authority separation, not just identity separation

The `authenticated_identity == pr_author` comparison above is
**necessary** but **not** the complete test for whether a review is
genuinely independent. `authenticated_identity != pr_author` does not, on
its own, prove the reviewer is independent of the change's author — so it
does not, on its own, lift the self-review mutation boundary.

A different GitHub identity is **not** an independent reviewer when its
selection, credentials, or instructions are controlled by the agent that
implemented or is orchestrating the change under review. Switching GitHub
accounts, selecting another token, using a bot / service account / CI
identity / GitHub App identity the agent can act as, invoking a nested
agent or sub-agent the agent spawns, spawning another process under the
same controlling authority, or forwarding the review task with
instructions to another agent still under that authority — none of these
manufacture an independent reviewer. A review conducted through any of
them is treated as a **self-review**: analysis runs in full, and the
formal GitHub review event is withheld, exactly as in the same-account
case above.

None of these checks stop the analysis itself. They gate only whether a
formal GitHub review **mutation** (`APPROVE` / `REQUEST_CHANGES`) may be
submitted. Whether an external (non-self) review may submit one is
governed by
[`review-action-authorization.md`](review-action-authorization.md), which
requires *authority separation* (this section) **and** trusted mutation
authorization, and fails closed to a non-mutating review otherwise. That
policy never lets a self-review submit a formal event, whatever
authorization is presented.

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

## Capability matrix

Resolve capability for the specific PR, identity, repository policy, token,
and intended event. Do not infer it from authentication or a broad role alone.

| State | Reasoning | Comments | Formal decision |
|---|---|---|---|
| Eligible external reviewer | Complete when scope is complete | Publish when authorized | Submit `APPROVE` or `REQUEST_CHANGES` as reasoned |
| PR author (self-review), or reviewer under the same controlling authority as the author | **Complete** — same process and evidence as an external review | May publish the result as an informational `COMMENT` (not a formal review) | **None** — no `APPROVE`, and no formal `REQUEST_CHANGES` on own work; report the verdict plus "GitHub review mutation withheld: reviewer is the PR author" |
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
