---
name: github-pr-review
description: >-
  Reviews an existing GitHub Pull Request authored by someone other than
  the local user or calling Agent — passively as a report, or, with
  authenticated GitHub access, actively by publishing inline PR review
  comments, one consolidated final summary, and an Approve/Request
  Changes decision. Never edits implementation code and never merges.
  Not applicable, and must not be selected, for a PR or code the local
  user or calling Agent authored — use `local-code-review` for
  local/uncommitted changes with no PR.
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
resolve review mode: same reviewer as immediately preceding
completed review? → yes → delta re-review of the bounded SHA range
                           (escalates to full review if the delta
                           materially changes scope)
                        → no  → normal review of current PR state
    ↓
Jira reference supplied? → yes → resolve via Jira MCP/connector (read-only)
                                  → resolved → normalized Jira context
                                  → unresolvable → JIRA CONTEXT UNRESOLVED,
                                    stop (no key/branch/PR-title inference)
                               → no  → unchanged
    ↓
retrieve required PR scope for that mode
    ↓
repository access mode? → API-only: no checkout
                        → optional: verified checkout or visible API-only degradation
                        → required: verified checkout or REVIEW INCOMPLETE
    ↓
determine formal-review capability
    ↓
resolve changed files, then one normalized per-file AGENTS.md/CLAUDE.md
    hierarchy from the target repository (verified checkout, or API-visible
    paths in API-only mode)
    ↓
plan review execution: reliable capability AND 2+ independent dimensions
       AND expected latency benefit?
       → yes → workers per dimension (read-only, same PR base/head snapshot)
       → no  → sequential
    ↓
inspect diff and surrounding code, reasoning about related changes as
logical cohorts and inspecting relevant dependency paths beyond the
diff, bounded to the PR's realistic blast radius
    ↓
apply repository conventions
    ↓
aggregate worker findings (normalize → dedupe → reconcile); a required
dimension missing → REVIEW INCOMPLETE, never REVIEW CLEAN
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
finally: remove the temporary checkout (success, any failure, interruption)
    ↓
stop
```

Findings accumulate silently during analysis and are never published
individually as they are discovered. Publication is a deliberate
finalization step: once analysis is complete, the entire finalized
finding set is submitted together as a single GitHub review whenever the
platform capability permits it — see
[`policies/review-output.md`](policies/review-output.md), "Batched review
construction and submission."

**This Skill is a reviewer role, not an implementation-completion step,
and not a self-review mechanism.** It is intended for genuine
reviewer/author separation — a different Agent or identity reviewing
someone else's PR, or review of an existing external PR — never as
something an implementing Agent chains onto after opening or updating
its own PR. This exclusion applies at two layers:

1. **Selection/invocation boundary (primary).** The `description` in
   this file's frontmatter already states that this Skill is not
   applicable, and must not be selected or invoked, when the local
   user authored the code or PR under review, or when an implementing
   Agent has just opened its own PR for the change it made. A calling
   system choosing which Skill to invoke should never select this one
   for that case in the first place.
2. **Runtime defensive guard (fallback, unchanged).** If this Skill is
   invoked anyway against a PR it (or the authenticated identity)
   authored, "Self-review capability" below and in
   [`policies/review-authority.md`](policies/review-authority.md)
   defines this Skill's own complete, self-contained guard
   (`REVIEW SKIPPED`) that stops before any diff analysis, finding, or
   publication occurs. This guard is defense in depth — it remains in
   place regardless of layer 1 and is never weakened by it.

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

**Repository-backed inspection** is available to either mode as optional
enrichment or as an explicit requirement: an
isolated, read-only, detached temporary checkout at the PR head that gives
the review richer **Repository Context** (surrounding implementation,
interfaces, tests, config, architecture, and the target repository's own
`AGENTS.md`/`CLAUDE.md` hierarchy) than the GitHub diff/API alone —
repository instructions are always resolved from this target-repository
snapshot, never from the Skill's own source checkout. The
**PR stays the Review Target**; the checkout never widens it. It is
read-only — the target repository's tests, builds, linters, hooks, and
scripts are never run. The temporary directory is created under a safe
scratch parent, unique per invocation, and is **always** cleaned up (success,
any failure, or interruption), guarded so no unconstrained recursive delete
can occur. Optional checkout failure is a visible API-only degradation;
required checkout failure returns an ungraded `REVIEW INCOMPLETE` /
`REPOSITORY CONTEXT UNAVAILABLE` outcome before workers start. See
[`policies/repository-checkout.md`](policies/repository-checkout.md).

**Parallel review** is an opt-in execution optimisation: when the runtime
exposes a reliable multi-agent / sub-agent capability and the PR is complex
enough to benefit, the review is split across independent read-only workers
by dimension (scope, architecture, correctness, tests/config, existing-review
reconciliation). Sequential and parallel execution must reach the **same**
findings and decision; sequential is always the fallback and a review is
never failed because parallelism is unavailable. One aggregating reviewer
normalizes, deduplicates, reconciles, applies canonical severity, derives the
one decision, and submits the one GitHub review. See the shared
[`parallel-review.md`](../../shared/policies/parallel-review.md) and
[`policies/parallel-review.md`](policies/parallel-review.md).

### Inputs

**Required:** a PR URL, a PR number with repository context, or a
repository + PR number.

**Optional:** review context describing the intended change. Two forms,
per the shared
[`review-context.md`](../../shared/policies/review-context.md), "Input form":

- **Textual / free-form** — explicit user instructions/requirements, pasted
  Jira/ticket text and/or acceptance criteria, a pasted GitHub Issue, an
  HLD/architecture document/ADR, an implementation plan, the PR description
  read as intent, or migration/security/performance/rollout constraints.
  Consumed directly.
- **Reference-based** — a bare Jira ticket key or URL, or a GitHub Issue
  reference. A reference is a pointer to context, not the context itself.
  When a **Jira reference** is supplied, this Skill executes the shared
  [`review-context.md`](../../shared/policies/review-context.md), "Jira
  context resolution" → **"Resolution procedure"** **before** review
  reasoning: identify an available Jira MCP / connector / runtime-exposed
  Jira read tool, invoke it **read-only** to fetch the issue's contents,
  fetch relevant comments and linked context when supported, normalize, and
  continue only on success. If the Jira reference cannot be resolved (no
  integration, authentication or authorization failure, issue not found,
  malformed reference, or connector/MCP error or timeout), this Skill
  returns the explicit `JIRA CONTEXT UNRESOLVED` reasoning result and does
  **not** perform the Jira-scoped review; it never infers the ticket from
  the key, the branch name, the PR title, a commit message, surrounding
  text, or copied metadata. A GitHub Issue
  reference is resolved through the same read-only GitHub access used for PR
  state, or supplied as pasted text; **no automatic PR↔Issue discovery**.

Context is consumed uniformly per the shared policy and its thin PR
application [`policies/review-context.md`](policies/review-context.md). It
focuses review attention and enables scope-boundary reasoning about the PR;
it never converts a ticket, Issue, ADR, or the PR description into an
additional review target, and never widens the PR delta. When omitted, this
Skill behaves exactly as before this input existed and never asks for it;
Jira is never mandatory.

**Always considered when available:** the PR's own prior reviews (with their
`APPROVED` / `CHANGES_REQUESTED` / `COMMENTED` state), review comments, issue
comments, and review-thread resolved/unresolved state where GitHub exposes it
— retrieved paginated-to-exhaustion through an authenticated GitHub
integration per [`policies/pr-scope.md`](policies/pr-scope.md), "Existing
review awareness" (which carries a concrete `gh api` / GraphQL example but
binds the Skill to no specific integration) — as Existing Review Evidence,
per the shared
[`review-evidence.md`](../../shared/policies/review-evidence.md) and its thin
PR application [`policies/review-evidence.md`](policies/review-evidence.md).
Used to avoid repeating settled findings, contradicting settled decisions
without new evidence, and missing an unresolved previously identified issue —
never blindly inherited, always reconciled against the current PR HEAD (a
resolved thread is evidence of a past conclusion, not proof the current HEAD
is correct; automation-authored comments contribute observations only).
Absent prior activity changes nothing.

## 3. Required Policy Loading

Shared, always: [`review-scope.md`](../../shared/policies/review-scope.md),
[`severity.md`](../../shared/policies/severity.md),
[`evidence.md`](../../shared/policies/evidence.md),
[`repository-instructions.md`](../../shared/policies/repository-instructions.md),
[`review-context.md`](../../shared/policies/review-context.md) (the shared
review-target / review-context / repository-context / existing-review-evidence
model and scope-boundary reasoning — its requirement-context sections bind
only when context is supplied),
[`review-evidence.md`](../../shared/policies/review-evidence.md) (the shared
Existing Review Evidence model),
[`git-safety.md`](../../shared/policies/git-safety.md),
[`review-ownership.md`](../../shared/policies/review-ownership.md),
[`file-reviewability.md`](../../shared/policies/file-reviewability.md), and —
whenever parallel workers are used —
[`parallel-review.md`](../../shared/policies/parallel-review.md) (the
portable parallel-review contract: sequential/parallel equivalence, worker
input/output, centralized aggregation, failure handling).

Also always: [`review-summary.md`](../../shared/templates/review-summary.md)
(the shared human-facing review body shape).

This Skill's own: [`policies/github-review.md`](policies/github-review.md),
the canonical policy index, and its sub-policies —
[`review-authority.md`](policies/review-authority.md) (identity,
self-review guard, publication capability),
[`reviewer-delta-review.md`](policies/reviewer-delta-review.md) (delta
vs. full review mode), [`pr-scope.md`](policies/pr-scope.md) (complete PR
scope, pagination, prior-review awareness),
[`repository-checkout.md`](policies/repository-checkout.md) (the opt-in
isolated temporary checkout lifecycle, base/head fidelity, read-only
inspection, security, guaranteed cleanup — loaded only when
repository-backed inspection is requested),
[`review-context.md`](policies/review-context.md) (thin PR application of
the shared review-context model; scope-boundary reasoning for a PR),
[`review-evidence.md`](policies/review-evidence.md) (thin PR application of
the shared Existing Review Evidence model; prior reviews/comments on this
PR), [`review-reasoning.md`](policies/review-reasoning.md) (logical cohorts,
code-impact/dependency analysis),
[`parallel-review.md`](policies/parallel-review.md) (thin PR application of
the shared parallel contract: threshold signals, shared checkout vs. worker
copies, runtime realisation — loaded only when parallel workers are used),
[`finding-placement.md`](policies/finding-placement.md)
(inline vs. body placement), and [`review-output.md`](policies/review-output.md)
(analysis/publication boundary, batching, HEAD revalidation, decision).

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
— see [`policies/review-authority.md`](policies/review-authority.md), "Review/
repository access prerequisite." If active publication is unavailable, do
not fake success or claim comments/decisions were submitted — fall back
to passive review.

## 6. Output Contract

When active review succeeds, GitHub itself — not this Skill's returned
response — is the authoritative, durable review record: targeted inline
PR review comments for inline-eligible findings, plus the one
consolidated final review summary below, both actually published to the
Pull Request. The structured result returned to the caller complements
that record; it is never the review's only representation.

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
  [`policies/review-output.md`](policies/review-output.md), "Batched
  review construction and submission." Human-readable content always
  precedes any machine-oriented metadata. A self-review never claims
  an independent approval; see
  [`policies/review-authority.md`](policies/review-authority.md), "Self-review
  capability."

## 7. Mutation Boundary

This Skill must never: edit implementation files, commit, push
implementation changes, merge, delete branches, or perform cleanup on
behalf of the repository owner. Maximum positive action is **Approve**.

## 8. HEAD Safety

The reviewed PR HEAD SHA is recorded at the start of review. Immediately
before the final decision, it is revalidated against the current PR HEAD
— see [`policies/review-output.md`](policies/review-output.md), "HEAD
revalidation." A stale HEAD is never approved; a changed HEAD triggers
re-review of the new delta before any decision is submitted.

## 9. Review Ownership

Subject to the same `One review scope → one Code Review Agent owner`
invariant as `local-code-review` — see
[`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md).
If another Code Review Agent already owns this PR, return
`REVIEW ALREADY OWNED` and do not launch a competing review.

## 10. Reviewer Ownership and Delta Re-Review

Distinct from section 9's Agent-level scope ownership, this section
governs *review-mode* selection for a single already-owned PR review:
whether this invocation may perform a bounded delta re-review or must
perform a normal full review of the current PR state. The complete rule
— reviewer identity resolution, the delta boundary, escalation
conditions, and edge cases — is owned by
[`policies/reviewer-delta-review.md`](policies/reviewer-delta-review.md);
this section does not duplicate it.

In summary: delta-only re-review is allowed only when the current
authenticated reviewer is the same identity as the reviewer of the
immediately preceding completed review of this PR, and that review's
reviewed SHA can be established reliably. A different reviewer, no prior
completed review, or any ambiguity in reviewer identity or the reviewed
SHA all default to a normal full review. The self-review guard described
at the top of this file and in
[`policies/review-authority.md`](policies/review-authority.md), "Self-review
capability," runs first and is authoritative; review-mode resolution
never bypasses it. This applies identically to passive and active
review — see
[`runbooks/passive-pr-review.md`](runbooks/passive-pr-review.md) and
[`runbooks/active-pr-review.md`](runbooks/active-pr-review.md).

## 11. Configuration

No runtime-specific configuration is required. This Skill has no loop/
iteration concept — each invocation reviews the PR's current authoritative
state once, per mode.
