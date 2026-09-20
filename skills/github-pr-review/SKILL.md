---
name: github-pr-review
version: 1.54.1
description: Review an existing GitHub pull request and return or publish evidence-backed P0/P1/P2 findings.
---

# SKILL.md — github-pr-review

A portable Code Review Skill that reviews GitHub Pull Requests and, when
authorized, publishes findings and a final Approve/Request Changes
decision. It behaves like an external senior reviewer — **not** an
implementation-fixing agent, a merge agent, or a repository-lifecycle owner.

**Use it** on an existing GitHub Pull Request (by URL or number) — someone
else's or the reviewer's own. For local changes, use `local-code-review`.

**Compatibility:** requires Git; active review additionally requires
authenticated GitHub access with sufficient review permissions.

## Safety boundaries (read before invoking)

The entry-contract rules, in brief — **section 7** is the full contract
for review-action authority; the canonical policies own the rest.

- **Analysis vs. GitHub mutation authority are separate**, governed by one
  canonical publication mode: `PASSIVE` (default, non-mutating), `SEMI`
  (same decision path, non-mutating preview), or `ACTIVE` (submits). An
  explicit `ACTIVE` request is itself sufficient authorization to publish
  — no second activation phrase required — subject to the unchanged
  self-review, reviewer-independence, GitHub-permission, and HEAD
  guarantees. See section 7 and
  [`policies/review-action-authorization.md`](policies/review-action-authorization.md).
- **Self-review is allowed; self-approval is not.** Authorship — or a
  shared controlling authority (alternate account/token, bot, service
  account, GitHub App, nested agent, spawned process) — never blocks
  analysis or changes the verdict, but no formal APPROVE / REQUEST_CHANGES
  is ever submitted on the reviewer's own work; the result may be
  published as an informational `COMMENT` only. See
  [`policies/review-authority.md`](policies/review-authority.md).
- **Reviewer independence is authority separation, not username
  separation**; ambiguity fails closed to `PASSIVE` (or to a withheld
  mutation when independence/permission are unfavorable).
- **HEAD safety.** The reviewed HEAD is recorded at start and revalidated
  before the decision; a stale HEAD is never approved. See section 5.
- **Merge boundary.** Never merges, never deletes branches; `APPROVE` is
  never merge authority. Maximum positive action is **Approve**.
- **Review ownership.** `One review scope → one Code Review Agent owner`;
  if another already owns this PR, return `REVIEW ALREADY OWNED` — see
  [`review-ownership.md`](../../shared/policies/review-ownership.md).
- **Severity → verdict is mechanical.** P0/P1 block; P2 never does; the
  verdict is derived once from whether any P0/P1 is present — see
  [`severity.md`](../../shared/policies/severity.md).
- **Reviewer Brief is private and never published**, structurally
  excluded from GitHub publication — see
  [`policies/reviewer-brief.md`](policies/reviewer-brief.md).
- **Agent-spawn capability is absent by default.** `spawn_agent` is only
  held when parallel review is selected; workers are read-only with hard,
  tree-wide budgets on agent count/spawn depth — see
  [`agent-delegation.md`](../../shared/policies/agent-delegation.md).

## Review flow (high level)

```text
resolve PR + authenticated identity, PR author, controlling authority
  → self-review? full analysis still runs; no formal event on own work
  → resolve review mode (delta re-review vs. normal review)
  → resolve stack topology: base is the default branch (no-op), or another
    open PR — a stack layer whose effective base is that PR's head
  → [optional] resolve a Jira reference (read-only; else JIRA CONTEXT UNRESOLVED)
  → retrieve the complete required PR scope for that mode (against the
    effective review base), paginated to exhaustion (incl. prior
    reviews/comments as Existing Review Evidence)
  → repository access mode (API-only | optional | required checkout);
    determine formal-review capability; resolve publication mode
    (PASSIVE | SEMI | ACTIVE; default PASSIVE; ambiguity fails closed)
  → discover per-file AGENTS.md/CLAUDE.md; apply runtime-validation policy;
    plan execution (sequential or
    read-only parallel workers per dimension — same findings and decision)
  → inspect diff + surrounding code as logical cohorts within the PR's
    realistic blast radius; apply repository conventions
  → aggregate → dedupe → reconcile (missing required dimension →
    REVIEW INCOMPLETE, never REVIEW CLEAN)
  → finalize findings; classify severity; resolve inline eligibility
  → revalidate HEAD → construct ONE review (body + inline comments)
  → apply the review-action authorization gate → submit in ACTIVE, report
    WOULD PUBLISH in SEMI, or report formal-review unavailability
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

There are three publication modes — **`PASSIVE`**, **`SEMI`**, **`ACTIVE`**
— the single canonical switch governing whether, and how, the result
reaches GitHub (see
[`policies/review-action-authorization.md`](policies/review-action-authorization.md),
"Publication modes (canonical)"). Two runbooks implement them: **Passive
PR review** ([`runbooks/passive-pr-review.md`](runbooks/passive-pr-review.md))
is `PASSIVE` — reads the PR and returns a report, no GitHub mutation;
**Active PR review** ([`runbooks/active-pr-review.md`](runbooks/active-pr-review.md))
runs the same decision path for both `SEMI` (reports what would publish,
submits nothing) and `ACTIVE` (may publish inline findings, a final
summary, and submit Approve or Request Changes), subject to section 7.

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
`true`), `include_finding_details` (default `false`),
`human_review_output` (default `false`), and its derived companion
`human_inline_findings` (default `explicit_value ?? human_review_output`),
normalized per
[`invocation-options.md`](../../shared/policies/invocation-options.md)
using only the current invocation. `include_fix_prompt` stays local-only.
`human_review_output` is a natural-language opt-in (no CLI flag — e.g.
"review it like a senior engineer," "senior review") rendering the
**final summary**, and any body/fallback finding rendered in full, in a
concise senior-engineer voice; `human_inline_findings` extends that voice
to the **inline comments** only
([`templates/inline-finding.md`](templates/inline-finding.md)). Both are
presentation-only: findings, severity, identity, dedup, verdict, review
state, placement, the canonical fix/action anchor and `#164` / `#165`
fallback, and machine-readable status are unchanged. Publishing a
previously produced passive review with no stated presentation asks once
which to use — see `policies/review-output.md`, "Publishing a previously
produced passive review."

## 2. Required Policy Loading

Shared, always (as one batched operation):
[`review-scope.md`](../../shared/policies/review-scope.md),
[`change-risk-signals.md`](../../shared/policies/change-risk-signals.md) (deterministic `standard`/`elevated`/`deep` review-depth classification, emitted with every review),
[`repository-expansion.md`](../../shared/policies/repository-expansion.md) (fixed expansion-trigger catalog, bounded ring-based expansion scaled by change-risk depth, emitted with every review),
[`large-pr-partitioning.md`](../../shared/policies/large-pr-partitioning.md) (deterministic partitioning of an unusually large diff into coherent review units, each fully reviewed, with cross-partition aggregation/de-duplication; conditional on a diff-size threshold),
[`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md) (coverage and exit conditions scaled by change-risk depth and partitions, the closed set of incomplete triggers, and the rule that an incomplete review never renders as clean; emitted with every review),
[`severity.md`](../../shared/policies/severity.md),
[`evidence.md`](../../shared/policies/evidence.md),
[`repository-instructions.md`](../../shared/policies/repository-instructions.md),
[`review-base-policy.md`](../../shared/policies/review-base-policy.md)
(repository-relative review-base compliance; fail-closed when the
required base cannot be reliably resolved),
[`review-context.md`](../../shared/policies/review-context.md)
(requirement-context sections bind only when context is supplied),
[`requirement-coverage.md`](../../shared/policies/requirement-coverage.md)
(binds only when authoritative requirements or acceptance criteria are
supplied),
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
[`finding.md`](../../shared/templates/finding.md) (the finding schema and
quality/conciseness contract every finding must satisfy),
[`finding-rendering.md`](../../shared/templates/finding-rendering.md)
(the canonical full and inline renderings — see
[`policies/finding-placement.md`](policies/finding-placement.md) for
this Skill's own inline-vs-body placement rule),
[`review-summary.md`](../../shared/templates/review-summary.md), and —
with parallel workers —
[`parallel-review.md`](../../shared/policies/parallel-review.md) and
[`agent-delegation.md`](../../shared/policies/agent-delegation.md).

This Skill's own: the canonical index
[`policies/github-review.md`](policies/github-review.md), which owns the
complete Skill-specific sub-policy set and its authoritative loading
order.

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
If unavailable, do not fake success — fall back to passive review.

## 4. Output Contract

- **Every result** additionally includes a private `Reviewer Brief`,
  composed once findings/severity/coverage/verdict are finalized and
  structurally excluded from anything published to GitHub — see
  [`policies/reviewer-brief.md`](policies/reviewer-brief.md).
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
  verdict but submits no formal event. That one review submission carries
  the **final human-facing summary** and is the last review-owned
  publication of the run (`final review comment == last publication
  event`; any machine-readable status precedes it — see
  [`policies/review-output.md`](policies/review-output.md), "Submission
  ordering"); `human_review_output` only renders that summary, and any
  body/fallback finding, concisely.

The reasoning result and the GitHub mutation are reported **separately**:
an active or semi invocation states its `Publication mode` (`PASSIVE` /
`SEMI` / `ACTIVE`) and `Mutation` outcome (`SUBMITTED (<event>)` /
`WOULD PUBLISH (<event>)` / `WITHHELD (<reason>)` / `NOT REQUESTED`), per
[`policies/review-output.md`](policies/review-output.md), "Review-action
authorization gate." A clean result with a withheld approval is never
reported as "approved."

## 5. HEAD Safety

The reviewed PR HEAD SHA is recorded at the start of review and
revalidated against the current PR HEAD immediately before the final
decision — see
[`policies/review-output.md`](policies/review-output.md), "HEAD
revalidation." A stale HEAD is never approved and triggers re-review of
the new delta first — it withholds `ACTIVE` publication even though an
explicit `ACTIVE` request is otherwise its own authorization (see
[`policies/review-action-authorization.md`](policies/review-action-authorization.md),
"Core invariant").

## 6. Reviewer Ownership and Delta Re-Review

Distinct from the Agent-level scope ownership above, this governs
*review-mode* selection for one already-owned PR review, owned by
[`policies/reviewer-delta-review.md`](policies/reviewer-delta-review.md):
delta-only re-review is allowed only when the current authenticated
reviewer is the same identity as the immediately preceding completed
review of this PR *and* that review's reviewed SHA is reliably known; any
other case defaults to a full review, and the self-review mutation
boundary is resolved first but never changes mode selection. Reconciling
prior finding/lifecycle state within that boundary — failing closed when
unreliable, escalating to full review when invalidated — is owned by
[`policies/stateful-delta-rereview.md`](policies/stateful-delta-rereview.md).
Applies identically to passive and active review.

**Stacked/dependent PRs.** When a PR's declared base is itself another
open PR rather than the repository's default/target branch,
[`policies/stacked-pr-review.md`](policies/stacked-pr-review.md) derives
the effective review base (the immediate parent's current head) and
scopes review to this layer's owned delta; the lower stack is read-only
Repository Context, never an additional review target. It extends
`stateful-delta-rereview.md`'s escalation triggers with the stack-specific
case of a lower layer changing after this layer was reviewed, and the
final review states the detected stack and the active layer. A PR based
directly on the repository's default/target branch is unaffected — every
rule above applies exactly as before this capability existed.

## 7. Review Action Authority and Mutation Boundary

**Review analysis is separate from GitHub mutation authority.** This
Skill always produces a full review and a mechanically derived reasoning
result; whether that result is *submitted* to GitHub as an `APPROVE` /
`REQUEST_CHANGES` event is a separate, authorized decision governed by
[`policies/review-action-authorization.md`](policies/review-action-authorization.md)
and the gate in
[`policies/review-output.md`](policies/review-output.md),
"Review-action authorization gate."

- **A review verdict is not, by itself, a GitHub event.** `REVIEW CLEAN`
  becomes a submitted `APPROVE` only once the publication mode, self-
  review boundary, reviewer independence, GitHub permission, and HEAD
  freshness checks all pass; `APPROVE` is never merge authority.
- **Self-review is allowed; self-approval is not.** When the reviewer is
  the PR author (or shares a controlling authority), the full analysis
  runs and reports a verdict, and the result may be published as an
  informational `COMMENT`, but **no formal APPROVE / REQUEST_CHANGES
  event is ever submitted on the reviewer's own work** — regardless of
  publication mode or natural-language request. Reported with "GitHub
  review mutation withheld: reviewer is the PR author"; not rewritten.
- **The default is non-mutating (`PASSIVE`).** No GitHub mutation unless
  `SEMI` or `ACTIVE` is established; a caller never needs to say "do not
  approve". **An explicit `ACTIVE` request is its own authorization** —
  `APPROVE` (clean) or `REQUEST_CHANGES` (blocking) is submitted whenever
  the mode is `ACTIVE`, the invocation is not a self-review, reviewer
  independence (authority separation, not merely a different GitHub
  username) is established, the event is permitted, and the reviewed HEAD
  is current — with **no second activation phrase, approval prompt, or
  out-of-band authorization channel** required or consulted. `SEMI` runs
  the identical decision path and reports what would publish, without
  publishing. Ambiguity fails closed to `PASSIVE` (or to a withheld
  mutation when independence/permission/HEAD are unfavorable).
- **Natural language, not syntax.** Users say what they want and the
  Skill normalizes it to one of the three publication modes. There is no
  required mode flag or keyword. See
  [`review-action-authorization.md`](policies/review-action-authorization.md),
  "Natural-language publication intent."
- **Authority boundary.** This section authorizes review-publication
  outputs only — inline comments, the review body,
  `APPROVE`/`REQUEST_CHANGES`/`COMMENT`. It never authorizes file
  modification, patch application, commit, push, merge, or repository
  settings changes; those capabilities are governed by this source
  repository's own canonical threat model (issues #298/#301, outside this
  packaged Skill), referenced rather than re-derived — see
  [`review-action-authorization.md`](policies/review-action-authorization.md),
  "Authority boundary."
- **Optional machine-readable status.** One stable, aggregated, exact-HEAD
  GitHub status/check for the reviewed SHA, separate from the native
  event: a **blocking** status may be published even by a self-review; a
  **success** status needs the same `ACTIVE` mode + independence as
  `APPROVE`, and is **never** published by a self-review. A new HEAD
  inherits no green. Required-check setup is a separate, explicit opt-in
  action. Canonical:
  [`review-status-enforcement.md`](policies/review-status-enforcement.md).

- **Agent-spawn capability is absent by default and never transfers
  formal authority.** A spawned worker holds no publication, mutation, or
  formal review-action authorization of its own — never inherited,
  copied, forwarded, or replayed across an agent-spawn boundary, exactly
  as it is never inherited across an alternate-identity boundary above.
  Canonical: [`agent-delegation.md`](../../shared/policies/agent-delegation.md).

This Skill must never: edit implementation files, commit, push
implementation changes, merge, delete branches, or perform cleanup on
behalf of the repository owner. Maximum positive action is **Approve**,
and only under the authorization above — in every mode, structurally incapable of `APPLY_PATCH`/`COMMIT`/`PUSH` (canonical: [`mutation-authority.md`](../../shared/policies/mutation-authority.md)).

## 8. Configuration

No runtime-specific configuration is required. This Skill has no
loop/iteration concept — each invocation reviews the PR's current
authoritative state once, per mode.
