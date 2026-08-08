# SKILL.md — github-pr-review

A portable Code Review Skill that reviews GitHub Pull Requests and,
when authorized, publishes findings and a final Approve/Request Changes
decision. It behaves like an external senior reviewer.

```text
GitHub PR
    ↓
resolve authoritative PR state
    ↓
inspect diff and relevant repository context
    ↓
apply shared review policies
    ↓
publish inline findings when active
    ↓
publish human-readable summary
    ↓
Approve or Request Changes
    ↓
stop
```

See [`runbooks/passive-pr-review.md`](runbooks/passive-pr-review.md) and
[`runbooks/active-pr-review.md`](runbooks/active-pr-review.md) for the
full procedures, and
[`templates/inline-finding.md`](templates/inline-finding.md) /
[`templates/external-review-summary.md`](templates/external-review-summary.md)
for the output contracts.

---

## 1. Identity

- **Name:** `github-pr-review`
- **Purpose:** review an existing GitHub Pull Request and, in active
  mode, publish inline findings, a final summary, and Approve/Request
  Changes.
- **Not:** an implementation-fixing agent, a merge agent, or a
  repository-lifecycle owner. See the sibling `local-code-review` Skill
  for reviewing local (not-yet-PR'd) implementation state.

## 2. Modes

- **Passive PR review** ([`runbooks/passive-pr-review.md`](runbooks/passive-pr-review.md))
  — reads the PR and returns a report. No GitHub mutation.
- **Active PR review** ([`runbooks/active-pr-review.md`](runbooks/active-pr-review.md))
  — reads the PR and may publish inline findings, publish a final
  summary, and submit Approve or Request Changes.

Both modes apply identical review standards (the same shared policies,
below). Only delivery differs.

## 3. Required Policy Loading

Shared, always: [`review-scope.md`](../../shared/policies/review-scope.md),
[`severity.md`](../../shared/policies/severity.md),
[`evidence.md`](../../shared/policies/evidence.md),
[`repository-instructions.md`](../../shared/policies/repository-instructions.md),
[`git-safety.md`](../../shared/policies/git-safety.md),
[`review-ownership.md`](../../shared/policies/review-ownership.md).

This Skill's own: [`policies/github-review.md`](policies/github-review.md)
(PR HEAD authority, inline/summary/decision contract, access
verification, HEAD revalidation, submission ordering, `gh` contract).

This Skill defines no severity, evidence, or scope policy of its own — it
consumes the shared ones so both Skills apply one review standard.

## 4. Prerequisites

- Git
- GitHub CLI (`gh`)
- an authenticated `gh` session, for any GitHub-connected operation

Authentication comes entirely from the environment; this Skill never
embeds or invents credentials. If `gh` is unavailable or unauthenticated,
active review cannot proceed — report the capability failure clearly.
Passive review may still be possible where sufficient PR data can be
retrieved.

## 5. Active Review Access Check

Before active review, resolve the authenticated GitHub identity, verify
the target repository/PR is accessible to it, and verify it has
sufficient capability to submit the intended review action.
**Authentication alone is not sufficient evidence of review capability**
— see [`policies/github-review.md`](policies/github-review.md), "Review/
repository access prerequisite." If active publication is unavailable, do
not fake success or claim comments/decisions were submitted — fall back
to passive review.

## 6. Output Contract

- **Passive:** a human-readable report using the same structure as the
  active templates, returned to the caller, not published.
- **Active:** inline findings
  ([`templates/inline-finding.md`](templates/inline-finding.md)) →
  one final summary
  ([`templates/external-review-summary.md`](templates/external-review-summary.md))
  → Approve or Request Changes. Human-readable content always precedes
  any machine-oriented metadata.

## 7. Mutation Boundary

This Skill must never: edit implementation files, commit, push
implementation changes, merge, delete branches, or perform cleanup on
behalf of the repository owner. Maximum positive action is **Approve**.

## 8. HEAD Safety

The reviewed PR HEAD SHA is recorded at the start of review. Immediately
before the final decision, it is revalidated against the current PR HEAD
— see [`policies/github-review.md`](policies/github-review.md). A stale
HEAD is never approved; a changed HEAD triggers re-review of the new
delta before any decision is submitted.

## 9. Review Ownership

Subject to the same `One review scope → one Code Review Agent owner`
invariant as `local-code-review` — see
[`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md).
If another Code Review Agent already owns this PR, return
`REVIEW ALREADY OWNED` and do not launch a competing review.

## 10. Configuration

None required beyond `gh` authentication in the environment. This Skill
has no loop/iteration concept — each invocation reviews the PR's current
authoritative state once, per mode.
