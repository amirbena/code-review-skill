# Policy — Review Authority

Governs the self-review guard and review/publication capability for
`github-pr-review`. Canonical index:
[`github-review.md`](github-review.md). Builds on the shared
[`review-ownership.md`](../../../shared/policies/review-ownership.md)
policy ("Access vs. Ownership") for the distinct Agent-level ownership
concern.

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

### Authority separation, not just identity separation

The `authenticated_identity == pr_author` comparison above is a
**necessary** guard and a hard stop, but it is **not** the complete trust
model for whether a review is genuinely independent. `authenticated_identity
!= pr_author` does not, on its own, prove the reviewer is independent of
the change's author.

A different GitHub identity is **not** an independent reviewer when its
selection, credentials, or instructions are controlled by the agent that
implemented or is orchestrating the change under review. Switching GitHub
accounts, selecting another token, using a bot / service account / CI
identity / GitHub App identity the agent can act as, invoking a nested
agent or sub-agent the agent spawns, spawning another process under the
same controlling authority, or forwarding the review task with
instructions to another agent still under that authority — none of these
manufacture an independent reviewer, and none bypass this guard.

Whether a privileged GitHub review **mutation** (`APPROVE` /
`REQUEST_CHANGES`) may actually be submitted is governed by
[`review-action-authorization.md`](review-action-authorization.md), which
requires *authority separation* (this section) **and** trusted mutation
authorization, and fails closed to a non-mutating review otherwise. This
`REVIEW SKIPPED` guard runs first and is authoritative; that policy never
weakens it.

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
