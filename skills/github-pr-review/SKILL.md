---
name: github-pr-review
description: >-
  Reviews an existing GitHub Pull Request and returns evidence-backed
  P0/P1/P2 findings — passively as a report, or, with authenticated
  GitHub access, actively by publishing inline findings and a final
  Approve/Request Changes decision. It never edits implementation code
  and never merges. Use when the user references a GitHub PR by URL or
  number, or asks to review, approve, or request changes on a pull
  request — not for reviewing local/uncommitted changes with no PR.
---

# SKILL.md — github-pr-review

A portable Code Review Skill that reviews GitHub Pull Requests and,
when authorized, publishes findings and a final Approve/Request Changes
decision. It behaves like an external senior reviewer.

**Compatibility:** requires Git; active review additionally requires
authenticated GitHub access with sufficient review permissions.

```text
resolve PR
    ↓
resolve authenticated identity and PR author
    ↓
same identity? → yes → REVIEW SKIPPED → stop
    ↓ no
retrieve complete paginated PR scope
    ↓
determine formal-review capability
    ↓
discover applicable AGENTS.md / CLAUDE.md
    ↓
inspect diff and surrounding code
    ↓
apply repository conventions
    ↓
deduplicate same-HEAD findings when active
    ↓
finalize findings: classify severity, resolve inline eligibility
    ↓
construct one coherent review: human-facing body + inline comments
    ↓
submit that one review (body + inline comments + event) when active
or report formal-review unavailability
    ↓
stop
```

Findings accumulate silently during analysis and are never published
individually as they are discovered. Publication is a deliberate
finalization step: once analysis is complete, the entire finalized
finding set is submitted together as a single GitHub review whenever the
platform capability permits it — see
[`policies/github-review.md`](policies/github-review.md), "Batched review
construction and submission."

**This Skill is a reviewer role, not an implementation-completion step.**
It is intended for genuine reviewer/author separation — a different
Agent or identity reviewing someone else's PR, or review of an existing
external PR — never as something an implementing Agent chains onto after
opening or updating its own PR. Preventing that chaining in the first
place is the calling system's orchestration responsibility, not this
Skill's own — but this Skill does not depend on that orchestration
being honored: "Self-review capability" below and in
[`policies/github-review.md`](policies/github-review.md) defines this
Skill's own complete, self-contained defensive guard (`REVIEW SKIPPED`)
for the case where it is invoked against a PR it authored anyway.

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
[`review-ownership.md`](../../shared/policies/review-ownership.md), and
[`file-reviewability.md`](../../shared/policies/file-reviewability.md).

Also always: [`review-summary.md`](../../shared/templates/review-summary.md)
(the shared human-facing review body shape).

This Skill's own: [`policies/github-review.md`](policies/github-review.md)
(PR HEAD authority, scope completeness, event capability, publication
idempotency, HEAD revalidation, submission ordering, integration contract,
batched review construction).

This Skill defines no severity, evidence, or scope policy of its own — it
consumes the shared ones so both Skills apply one review standard.

## 4. Prerequisites

- Git
- an available authenticated GitHub integration for GitHub-connected
  operations

Authentication comes entirely from the environment; this Skill never
embeds or invents credentials. If no available integration can retrieve
the required PR state, report the capability failure clearly. Active review
requires sufficient permission for each intended publication action.
Passive review may still be possible where sufficient PR data can be
retrieved.

## 5. Active Review Access Check

Before active review, resolve the authenticated GitHub identity, verify
the PR author, compare their account identities, verify the target
repository/PR is accessible to the authenticated identity, and verify it has
sufficient capability to submit the intended review action.
**Authentication alone is not sufficient evidence of review capability**
— see [`policies/github-review.md`](policies/github-review.md), "Review/
repository access prerequisite." If active publication is unavailable, do
not fake success or claim comments/decisions were submitted — fall back
to passive review.

## 6. Output Contract

- **Passive:** a human-readable report using the same shared shape as
  active review ([`review-summary.md`](../../shared/templates/review-summary.md)),
  returned to the caller, not published.
- **Active:** the finalized findings, once analysis completes, are
  submitted together as **one** GitHub review: a human-readable body
  ([`templates/external-review-summary.md`](templates/external-review-summary.md))
  plus the inline comments for inline-eligible findings
  ([`templates/inline-finding.md`](templates/inline-finding.md)), and a
  permitted Approve or Request Changes event — or an explicit reason that
  no formal final review can be submitted. This Skill never publishes a
  standalone comment as each finding is discovered, and never splits one
  finalized finding set across multiple review submissions; see
  [`policies/github-review.md`](policies/github-review.md), "Batched
  review construction and submission." Human-readable content always
  precedes any machine-oriented metadata. A self-review never claims
  an independent approval; see
  [`policies/github-review.md`](policies/github-review.md), "Self-review
  capability."

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

No runtime-specific configuration is required. This Skill has no loop/
iteration concept — each invocation reviews the PR's current authoritative
state once, per mode.
