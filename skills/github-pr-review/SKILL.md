---
name: github-pr-review
description: >-
  Reviews an existing GitHub Pull Request — passively as a report, or,
  with authenticated GitHub access, actively by publishing inline PR
  review comments and one consolidated final summary. Review analysis is
  separate from GitHub mutation authority: the default is a non-mutating
  recommendation, and an Approve/Request Changes decision is submitted
  only under independently trusted authorization with genuine reviewer
  independence. Self-review is allowed — the Skill analyzes its own PR
  and produces a verdict — but self-approval is not: no formal
  Approve/Request Changes is ever submitted on the reviewer's own work.
  Never edits implementation code and never merges. For local,
  not-yet-PR'd changes use `local-code-review`.
---

# SKILL.md — github-pr-review

A portable Code Review Skill that reviews GitHub Pull Requests and, when
authorized, publishes findings and a final Approve/Request Changes
decision. It behaves like an external senior reviewer — **not** an
implementation-fixing agent, a merge agent, or a repository-lifecycle
owner.

**Use it** on an existing GitHub Pull Request (by URL or number) —
someone else's or the reviewer's own. For local, not-yet-PR'd changes use
the sibling `local-code-review` Skill.

**Compatibility:** requires Git; active review additionally requires
authenticated GitHub access with sufficient review permissions.

## Safety boundaries (read before invoking)

The entry-contract rules, in brief. **Section 7** is the full contract
for review-action authority; the canonical policies own the rest.

- **Analysis vs. GitHub mutation authority are separate.** The Skill
  always produces a full review and a mechanically derived verdict;
  *submitting* it as `APPROVE` / `REQUEST_CHANGES` is a separate,
  authorized decision. The default is non-mutating (recommendation-only);
  a verdict is not authorization; `APPROVE` is submitted only in
  explicitly-authorized auto-action mode. See section 7 and
  [`policies/review-action-authorization.md`](policies/review-action-authorization.md).
- **Self-review is allowed; self-approval is not.** Authorship — or a
  shared controlling authority (an alternate account/token, bot, service
  account, GitHub App identity, nested agent, or spawned process) — never
  blocks analysis or changes the verdict, but no formal
  APPROVE / REQUEST_CHANGES is ever submitted on the reviewer's own work;
  the result may be published as an informational `COMMENT` only. See
  [`policies/review-authority.md`](policies/review-authority.md).
- **Reviewer independence is authority separation, not username
  separation**, and natural-language intent ("approve if clean") is
  *requested* behavior, never trusted mutation authorization. Any
  ambiguity fails closed to a non-mutating review.
- **HEAD safety.** The reviewed HEAD is recorded at start and revalidated
  before the decision; a stale HEAD is never approved; any trusted
  authorization is bound to the exact reviewed HEAD. See section 5.
- **Merge boundary.** This Skill never merges and never deletes branches;
  `APPROVE` is never merge authority. Maximum positive action is
  **Approve**.
- **Review ownership.** `One review scope → one Code Review Agent owner`;
  if another already owns this PR, return `REVIEW ALREADY OWNED` — see
  [`review-ownership.md`](../../shared/policies/review-ownership.md).
- **Severity → verdict is mechanical.** P0/P1 block; P2 never does; the
  verdict is derived once from whether any P0/P1 is present — see
  [`severity.md`](../../shared/policies/severity.md).

## Review flow (high level)

```text
resolve PR + authenticated identity, PR author, controlling authority
  → self-review? full analysis still runs; no formal event on own work
  → resolve review mode (delta re-review vs. normal review)
  → [optional] resolve a Jira reference (read-only; else JIRA CONTEXT UNRESOLVED)
  → retrieve the complete required PR scope for that mode, paginated to
    exhaustion (incl. prior reviews/comments as Existing Review Evidence)
  → repository access mode (API-only | optional | required checkout);
    determine formal-review capability; resolve review-action mode +
    mutation authorization (default recommendation-only; ambiguity fails closed)
  → discover per-file AGENTS.md/CLAUDE.md; apply runtime-validation policy;
    plan execution (sequential or
    read-only parallel workers per dimension — same findings and decision)
  → inspect diff + surrounding code as logical cohorts within the PR's
    realistic blast radius; apply repository conventions
  → aggregate → dedupe → reconcile (missing required dimension →
    REVIEW INCOMPLETE, never REVIEW CLEAN)
  → finalize findings; classify severity; resolve inline eligibility
  → revalidate HEAD → construct ONE review (body + inline comments)
  → apply the review-action authorization gate → submit the permitted
    event when active, or report formal-review unavailability
  → finally: remove any temporary checkout → stop
```

Findings accumulate silently and are published only as a single batched
GitHub review once analysis is complete — never finding-by-finding.
Procedures:
[`runbooks/passive-pr-review.md`](runbooks/passive-pr-review.md) /
[`runbooks/active-pr-review.md`](runbooks/active-pr-review.md). Output:
[`templates/inline-finding.md`](templates/inline-finding.md) /
[`templates/external-review-summary.md`](templates/external-review-summary.md).

## 1. Modes and Inputs

- **Passive PR review**
  ([`runbooks/passive-pr-review.md`](runbooks/passive-pr-review.md)) —
  reads the PR and returns a report. No GitHub mutation.
- **Active PR review**
  ([`runbooks/active-pr-review.md`](runbooks/active-pr-review.md)) — may
  publish inline findings, a final summary, and submit Approve or Request
  Changes, subject to section 7.

Both modes apply identical review standards; only delivery differs. Two
execution options never change *what* is reviewed (the **PR stays the
Review Target**) or the result: **repository-backed inspection** — an
isolated, read-only checkout at the PR head, always cleaned up with a
guarded delete, where a required-mode failure returns `REVIEW INCOMPLETE`
/ `REPOSITORY CONTEXT UNAVAILABLE` before workers start
([`policies/repository-checkout.md`](policies/repository-checkout.md)) —
and **parallel review**, read-only workers per dimension that must reach
the **same** findings and decision as sequential (always the fallback),
with one aggregating reviewer submitting the one review (shared
[`parallel-review.md`](../../shared/policies/parallel-review.md),
[`policies/parallel-review.md`](policies/parallel-review.md)).

### Inputs

**Required:** a PR URL, a PR number with repository context, or a
repository + PR number.

**Optional — review context** describing the intended change, per shared
[`review-context.md`](../../shared/policies/review-context.md), "Input
form" (thin application:
[`policies/review-context.md`](policies/review-context.md)): free-form
instructions/requirements, pasted ticket text or acceptance criteria, a
pasted GitHub Issue, an HLD/ADR, a plan, or the PR description read as
intent — consumed directly. A bare **Jira reference** is a pointer
resolved **before** review reasoning via the shared policy's "Jira
context resolution" → "Resolution procedure" (read-only, normalize,
continue only on success); if it cannot be resolved this Skill returns
`JIRA CONTEXT UNRESOLVED` and never infers the ticket from its key,
branch name, PR title, or surrounding text. A GitHub Issue reference
resolves through read-only GitHub access or pasted text; **no automatic
PR↔Issue discovery**. Context focuses attention and enables
scope-boundary reasoning; it never becomes an additional review target
and never widens the PR delta. When omitted, behavior is exactly as
before this input existed; Jira is never mandatory.

**Always considered when available:** the PR's own prior reviews (with
their `APPROVED` / `CHANGES_REQUESTED` / `COMMENTED` state), review and
issue comments, and review-thread resolved state — retrieved
paginated-to-exhaustion per
[`policies/pr-scope.md`](policies/pr-scope.md), "Existing review
awareness" — as Existing Review Evidence per shared
[`review-evidence.md`](../../shared/policies/review-evidence.md) and
[`policies/review-evidence.md`](policies/review-evidence.md): used to
avoid repeating settled findings, contradicting a settled decision
without new evidence, and missing an unresolved prior issue — never
blindly inherited, always reconciled against the current PR HEAD.

**Optional — presentation options:** `include_fix_guidance` (default
`true`) and `include_finding_details` (default `false`), normalized per
[`invocation-options.md`](../../shared/policies/invocation-options.md)
using only the current invocation; a finding-level decision may still show
materially useful context. `include_fix_prompt` is recognized for
direct/mediated parity but stays local-only.

## 2. Required Policy Loading

Shared, always (as one batched operation):
[`review-scope.md`](../../shared/policies/review-scope.md),
[`severity.md`](../../shared/policies/severity.md),
[`evidence.md`](../../shared/policies/evidence.md),
[`repository-instructions.md`](../../shared/policies/repository-instructions.md),
[`review-context.md`](../../shared/policies/review-context.md)
(requirement-context sections bind only when context is supplied),
[`review-evidence.md`](../../shared/policies/review-evidence.md),
[`runtime-validation.md`](../../shared/policies/runtime-validation.md),
[`git-safety.md`](../../shared/policies/git-safety.md),
[`review-ownership.md`](../../shared/policies/review-ownership.md),
[`file-reviewability.md`](../../shared/policies/file-reviewability.md),
[`invocation-options.md`](../../shared/policies/invocation-options.md),
[`remediation-guidance.md`](../../shared/policies/remediation-guidance.md)
(a concise recommended direction, never the local Skill's full
implementation prompt; never affects severity, decision, or mutation
authority),
[`review-summary.md`](../../shared/templates/review-summary.md), and —
with parallel workers —
[`parallel-review.md`](../../shared/policies/parallel-review.md).

This Skill's own: the canonical index
[`policies/github-review.md`](policies/github-review.md) and its
sub-policies in authoritative order —
[`review-authority.md`](policies/review-authority.md),
[`review-action-authorization.md`](policies/review-action-authorization.md),
[`reviewer-delta-review.md`](policies/reviewer-delta-review.md),
[`pr-scope.md`](policies/pr-scope.md),
[`repository-checkout.md`](policies/repository-checkout.md) (repository-backed
inspection only),
[`review-context.md`](policies/review-context.md),
[`review-evidence.md`](policies/review-evidence.md),
[`review-reasoning.md`](policies/review-reasoning.md),
[`parallel-review.md`](policies/parallel-review.md) (parallel workers
only), [`finding-placement.md`](policies/finding-placement.md),
[`review-output.md`](policies/review-output.md), and
[`review-status-enforcement.md`](policies/review-status-enforcement.md)
(optional machine-readable status; loaded only when that signal or its
setup is in play).

This Skill defines no severity, evidence, or scope policy of its own — it
consumes the shared ones so both Skills apply one review standard.

## 3. Prerequisites and Access

Git, and an available authenticated GitHub integration for
GitHub-connected operations. Authentication comes from the environment;
this Skill never embeds or invents credentials. If no integration can
retrieve the required PR state, report the capability failure clearly.

Before **active** review, resolve the authenticated identity, the PR
author, and whether they share a controlling authority (which makes this
a self-review — analysis still runs, no formal event submitted; see
[`policies/review-authority.md`](policies/review-authority.md),
"Self-review capability"), then verify the PR is accessible and the
identity has sufficient capability for the intended action.
**Authentication alone is not sufficient evidence of review capability.**
If active publication is unavailable, do not fake success — fall back to
passive review.

## 4. Output Contract

- **Passive:** a human-readable report using the shared shape
  ([`review-summary.md`](../../shared/templates/review-summary.md)),
  returned to the caller, not published.
- **Active:** on success GitHub itself is the authoritative record — the
  finalized findings submitted together as **one** GitHub review: a
  human-readable body
  ([`templates/external-review-summary.md`](templates/external-review-summary.md))
  plus inline comments for inline-eligible findings
  ([`templates/inline-finding.md`](templates/inline-finding.md)) and a
  permitted Approve or Request Changes event, or an explicit reason no
  formal review can be submitted. Never a standalone comment per finding;
  never split across submissions; human-readable content precedes machine
  metadata. A self-review completes the full analysis and reports its
  verdict but submits no formal event.

The reasoning result and the GitHub mutation are reported **separately**:
an active invocation states its `Action mode` (`recommendation-only` /
`block-only` / `explicitly-authorized auto-action`) and `Mutation`
outcome (`SUBMITTED (<event>)` / `WITHHELD (<reason>)` / `NOT REQUESTED`)
alongside the reasoning and decision lines, per
[`policies/review-output.md`](policies/review-output.md), "Review-action
authorization gate." A clean reasoning result whose approval was withheld
is reported as exactly that — a clean result and a non-mutating outcome,
never "approved."

## 5. HEAD Safety

The reviewed PR HEAD SHA is recorded at the start of review and
revalidated against the current PR HEAD immediately before the final
decision — see
[`policies/review-output.md`](policies/review-output.md), "HEAD
revalidation." A stale HEAD is never approved; a changed HEAD triggers
re-review of the new delta before any decision is submitted. Any trusted
mutation authorization is bound to the exact reviewed HEAD (per
[`policies/review-action-authorization.md`](policies/review-action-authorization.md),
"Authorization scope"): a HEAD change invalidates it, so a stale HEAD can
never carry an approval even when authorization otherwise existed.

## 6. Reviewer Ownership and Delta Re-Review

Distinct from the Agent-level scope ownership above, this governs
*review-mode* selection for one already-owned PR review, and is owned by
[`policies/reviewer-delta-review.md`](policies/reviewer-delta-review.md).
In summary: delta-only re-review is allowed only when the current
authenticated reviewer is the same identity as the immediately preceding
completed review of this PR *and* that review's reviewed SHA is reliably
known; a different reviewer, no prior review, or any ambiguity defaults
to a normal full review. The self-review mutation boundary is resolved
first but never changes mode selection. Applies identically to passive
and active review.

## 7. Review Action Authority and Mutation Boundary

**Review analysis is separate from GitHub mutation authority.** This
Skill always produces a full review and a mechanically derived reasoning
result; whether that result is *submitted* to GitHub as an `APPROVE` /
`REQUEST_CHANGES` event is a separate, authorized decision governed by
[`policies/review-action-authorization.md`](policies/review-action-authorization.md).

- **A review verdict is not authorization.** `REVIEW CLEAN` never
  automatically means GitHub `APPROVE`.
- **Approval is not merge authority.** `APPROVE` never automatically
  means `MERGE`, and this Skill never merges.
- **Self-review is allowed; self-approval is not.** When the reviewer is
  the PR author (or under the same controlling authority), the full
  analysis runs and reports a verdict; the result may be published as an
  informational `COMMENT`, but **no formal APPROVE / REQUEST_CHANGES
  event is ever submitted on the reviewer's own work** — regardless of
  mode, natural-language request, or authorization. The verdict is
  reported with "GitHub review mutation withheld: reviewer is the PR
  author" and is not rewritten.
- **The default is non-mutating (recommendation-only).** A review runs
  and returns findings and a verdict with no GitHub mutation unless a
  stronger mode is established. Passive review is always
  recommendation-only. A caller never needs to say "do not approve".
- **`APPROVE` is submitted only in explicitly-authorized auto-action
  mode** — only when both trusted mutation authorization for that exact
  action (from a principal independent of the agent performing or
  orchestrating the review, via a channel that agent cannot author,
  forge, or replay, scoped to this invocation / repo / PR / reviewed
  HEAD / single action) **and** reviewer independence (authority
  separation, not merely a different GitHub username) are established. A
  flag, prompt, env var, nested instruction, alternate token/username,
  bot, service account, or GitHub App identity the invoking agent
  controls never establishes either.
- **Ambiguity fails closed** to recommendation-only (or block-only for a
  blocking result where independence and GitHub permission hold).
- **Natural language, not syntax.** Users say what they want and the
  Skill normalizes it to an internal mode. There is no required mode flag
  or keyword. Asking for a GitHub action expresses *requested* behavior —
  it is not itself trusted authorization.
- Being a portable Skill with no runtime of its own, this Skill cannot
  cryptographically verify provenance; it guarantees the safe default and
  the capability boundary and relies on the runtime/orchestrator for an
  independent authorization channel — see that policy, "Structural
  limitation."

- **Optional machine-readable status.** `github-pr-review` may also
  publish one stable, aggregated, exact-HEAD GitHub status/check for the
  reviewed SHA — separate from the native `APPROVE` / `REQUEST_CHANGES`
  event. A **blocking** status is blocking-only enforcement and may be
  published even by a self-review (it can only make the gate stricter); a
  **success** status is a positive/unblocking action requiring the same
  trusted authorization and reviewer independence as `APPROVE`, and is
  **never** published by a self-review. A new HEAD inherits no green.
  Making the status a required merge check is an explicit, opt-in setup
  action, never part of an ordinary review. Canonical:
  [`review-status-enforcement.md`](policies/review-status-enforcement.md).

This Skill must never: edit implementation files, commit, push
implementation changes, merge, delete branches, or perform cleanup on
behalf of the repository owner. Maximum positive action is **Approve**,
and only under the authorization above.

## 8. Configuration

No runtime-specific configuration is required. This Skill has no
loop/iteration concept — each invocation reviews the PR's current
authoritative state once, per mode.
