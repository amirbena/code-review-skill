# Policy — Review Context (PR application)

`github-pr-review`'s **thin application** of the shared review-context model.
Canonical index: [`github-review.md`](github-review.md). The semantics —
the review-target / review-context / repository-context / existing-review-evidence
concepts, input forms (including an explicitly supplied GitHub Issue), the
evidence hierarchy, using context to focus attention, context-mismatch
handling, **scope-boundary reasoning** and its precedence notes, explicit
non-goals, scope discipline, and tracing findings back to context — are owned
by [`review-context.md`](../../../shared/policies/review-context.md) and are
not restated here.

This file adds only what is specific to reviewing a GitHub Pull Request.

## Optional; runs after the authority and mode gates

Supplied review context is optional. When none is supplied, this Skill
behaves exactly as before this input existed, and never asks for it. Missing
or not-provided free-form/textual context is never a reason to fail, block,
or degrade the review. A **supplied Jira reference that cannot be resolved**
is the one exception — see "Jira context resolution (PR application)" below —
and it never makes Jira mandatory for reviews that do not supply one.

Context is resolved **after**
[`review-authority.md`](review-authority.md) (the self-review guard is
authoritative and terminates first) and
[`reviewer-delta-review.md`](reviewer-delta-review.md) (review-mode
resolution), and **before or alongside** PR scope retrieval
([`pr-scope.md`](pr-scope.md)). It never changes whether the PR is reviewed
or how much of it is in scope — see
[`reviewer-delta-review.md`](reviewer-delta-review.md) for that.

## Input form

Per the shared [`review-context.md`](../../../shared/policies/review-context.md),
"Input form," context is either **textual / free-form** (consumed directly)
or a **reference** (resolved first). The caller may supply:

- explicit user instructions / requirements (text);
- pasted Jira/ticket text and/or acceptance criteria, **or** a bare Jira
  ticket key/URL that is resolved per "Jira context resolution (PR
  application)" below;
- a pasted GitHub Issue, **or** a GitHub Issue reference resolved through the
  same read-only GitHub access used for PR state — supplied explicitly;
  **no automatic PR↔Issue discovery** in this phase;
- an HLD, architecture/design document, or ADR;
- an implementation plan;
- the PR description itself, read as a statement of intent;
- migration/security/performance/rollout constraints.

The PR's own description is always available as review context even when the
caller supplies nothing else. Each source is normalized and treated
uniformly per the shared policy's "Input form" and "Recommended internal
normalization."

## Jira context resolution (PR application)

The full contract — Jira MCP / connector / equivalent integration as a
transport-agnostic capability, read-only retrieval only, the retrieve/
normalize list, Jira-comment classification, and the
`JIRA CONTEXT UNRESOLVED` precondition — is owned by the shared
[`review-context.md`](../../../shared/policies/review-context.md), "Jira
context resolution," and is not restated here. For a PR review:

- resolution runs after the self-review guard and review-mode resolution and
  before PR scope retrieval; it never changes the review mode or the PR
  delta;
- **read-only**: retrieving Jira context adds no Jira write capability —
  never edit/transition an issue, add a comment, change a field, create a
  ticket, or assign a user;
- when a supplied Jira reference **cannot be resolved**, this Skill reports
  the `JIRA CONTEXT UNRESOLVED` reasoning result (see
  [`review-output.md`](review-output.md), "Final decision") and does not
  perform the Jira-scoped review — it does not infer the ticket from the
  key, the branch name, the PR title, a commit message, or surrounding text,
  and it submits no Approve/Request Changes for a Jira scope it never
  established.

## The PR remains the review target

Context never converts a Jira ticket, a GitHub Issue, an ADR, or the PR
description into an additional review target. The review target stays the
**PR delta** (the full diff for a normal review, or the bounded delta for a
delta re-review). Context focuses attention *within* that target and enables
scope-boundary reasoning about it; it never widens it, and never pulls
unrelated files or commits into review.

## Scope-boundary reasoning for a PR

Apply the shared policy's "Scope-boundary reasoning" to the PR: detect
required behavior missing from the PR, the PR contradicting acceptance
criteria, unrelated scope expansion in the PR, a valid-but-out-of-scope
finding, and repository-policy violations that hold regardless of the
ticket's stated scope. Precedence between disagreeing scope sources follows
the shared policy's "Precedence when scope sources disagree" — repository
policy/invariants can constrain the PR even when a ticket says otherwise; an
accepted ADR/HLD generally outweighs speculative ticket discussion; newer
explicit maintainer clarification supersedes stale earlier discussion. There
is no rigid global priority order; report an unresolved material conflict as
an ambiguity rather than silently picking a side.

## Boundaries

- **No new mutation.** Reading supplied context or a referenced GitHub Issue
  is read-only. It never adds any GitHub write capability; this Skill's
  mutation boundary and maximum positive action (**Approve**) are unchanged.
- **Decision derivation unchanged.** Context informs which findings exist and
  their severity exactly as any other evidence source would — see
  [`review-output.md`](review-output.md), "Final decision," and
  [`severity.md`](../../../shared/policies/severity.md), "Decision derivation
  (mechanical)." It never adds a separate decision path.
- **Self-review guard unchanged.** Supplying context never bypasses
  [`review-authority.md`](review-authority.md), "Self-review capability."
