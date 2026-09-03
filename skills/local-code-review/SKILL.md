---
name: local-code-review
description: >-
  Reviews local, not-yet-PR'd Git changes (committed delta, staged,
  unstaged, and untracked) and returns evidence-backed P0/P1/P2 findings.
  Read-only and opt-in only: never edits, commits, pushes, or touches
  GitHub, and every review or re-review requires explicit user selection.
  Optionally accepts free-form context such as requirements, Jira/HLD/ADR,
  acceptance criteria, or implementation plans to focus the review, plus
  an associated GitHub PR reference for reconciling prior findings and
  architectural decisions. The local delta always remains the review
  scope. For reviewing an existing PR itself, use github-pr-review.
---

# SKILL.md — local-code-review

A small, bounded, **stateless** Code Review Skill that reviews a local Git
repository's implementation state (committed delta, staged, unstaged, and
untracked) and returns structured P0/P1/P2 findings. It is a reviewer
only — never an orchestrator, a fix loop, a Git-mutating agent, or a
GitHub-publishing agent.

**Use it** on local/uncommitted work before a push or PR. For an existing
GitHub Pull Request, use the sibling `github-pr-review` Skill.

**Compatibility:** requires a local Git repository; an optional PR
reference additionally requires read-only GitHub access.

## Safety boundaries (read before invoking)

The entry contract. Full text lives in the linked canonical policies;
restated here because hiding them behind a link would be dangerous.

- **Opt-in only.** This Skill **MUST NOT be invoked automatically.**
  Every invocation — first review *and* every re-review after fixes —
  requires fresh, explicit user approval scoped to that one run, obtained
  by the caller. Generic "check your work" language, a standing
  preference, repository or orchestration policy, and silence/non-objection
  never qualify. Returning findings from one invocation is never, by
  itself, authorization for the caller to invoke this Skill again after
  fixes. A separate, explicit approval is required for every subsequent
  invocation. Delegating as an Agent/Sub-Agent never moves the decision
  away from the end user. Canonical owner:
  [`policies/invocation-approval.md`](policies/invocation-approval.md).
- **Review ownership.** `One review scope → one Code Review Agent owner`.
  If another Code Review Agent already owns this local branch/scope,
  return `REVIEW ALREADY OWNED` and do not launch a competing review —
  see [`review-ownership.md`](../../shared/policies/review-ownership.md).
- **Severity → verdict is mechanical.** Findings are P0/P1/P2. **P0** and
  **P1** block; **P2** never blocks, however strongly recommended or
  wherever it originated. The `REVIEW CLEAN` / `CHANGES REQUIRED` decision
  is derived once, mechanically, from whether any P0/P1 is present — never
  a separate judgment call. Canonical owner:
  [`severity.md`](../../shared/policies/severity.md), "Decision
  derivation (mechanical)."
- **Read-only.** This Skill never edits files, applies patches, commits,
  pushes, rebases, creates branches, opens PRs, or mutates GitHub (see
  section 6). Repository-state safety — including reviewing directly on a
  protected/default branch — is owned by
  [`policies/repository-state.md`](policies/repository-state.md) and
  [`git-safety.md`](../../shared/policies/git-safety.md).

## Review flow (high level)

```text
resolve scope → discover per-file AGENTS.md/CLAUDE.md → inspect the Git
delta by category (committed, staged, unstaged, untracked) → compute the
staged-delta fingerprint → [optional] resolve a Jira reference (read-only;
else JIRA CONTEXT UNRESOLVED) / map review context / reconcile a PR
reference's prior findings — all onto the delta, never widening it →
resolve the shared runtime-validation policy and record any safe validation
outcome → inspect surrounding code → review against code + conventions,
focused by context → classify by severity (source never changes it) → derive the
decision mechanically from blocking (P0/P1) severities → return, stop
```

The optional Jira and PR inputs never widen scope: the local delta stays
the Review Target. Full procedure:
[`runbooks/local-review.md`](runbooks/local-review.md). Output contract:
[`templates/local-review-report.md`](templates/local-review-report.md).

## 1. Inputs

**Required:** a local Git repository. The Skill inspects the four
repository-state categories owned by
[`policies/repository-state.md`](policies/repository-state.md) —
committed delta relative to a base, staged, unstaged, untracked — never
one undifferentiated "relevant files" blend, plus surrounding code,
tests, and repository instructions as needed. Push/synchronization status
is resolved against the branch's configured upstream, never the review
base. The full implementation state is reviewed; no category is silently
skipped without saying so in the report.

**Optional — review context** describing the intended change, per
[`review-context.md`](../../shared/policies/review-context.md), "Input
form" (thin local application:
[`policies/review-context.md`](policies/review-context.md)):

- **Textual / free-form** — requirements, explicit instructions, pasted
  ticket text or acceptance criteria, a pasted GitHub Issue, an HLD/ADR,
  an implementation plan, or migration/security/performance/rollout
  requirements. Consumed directly.
- **Reference-based** — a bare Jira key/URL or GitHub Issue reference is a
  pointer, not the context. A **Jira reference** is resolved **before**
  review reasoning via the shared policy's "Jira context resolution" →
  "Resolution procedure" (available Jira MCP/connector, read-only,
  normalize, continue only on success). If it cannot be resolved, this
  Skill does **not** infer ticket contents from the key, branch name, or
  surrounding text and returns `JIRA CONTEXT UNRESOLVED`. A GitHub Issue
  reference is resolved through read-only GitHub access or pasted text; no
  automatic PR↔Issue discovery.

Supplied context focuses attention and enables scope-boundary reasoning;
it is never authority over implementation evidence and never widens the
review target. When omitted, behavior is exactly as if it did not exist;
this Skill never asks for it and Jira is never mandatory.

**Optional:** a reference to an associated GitHub PR (a PR URL, or a PR
number when the repository is unambiguous). When supplied, this Skill
reconciles the local delta against relevant existing reviewer findings,
prior review comments, and settled architectural/design decisions from
that PR as Existing Review Evidence, per
[`review-evidence.md`](../../shared/policies/review-evidence.md) and
[`policies/pr-context.md`](policies/pr-context.md). The local delta always
remains the review target. When omitted, this Skill's behavior is exactly
as if this input did not exist. The two optional inputs are independent —
either, both, or neither.

**Optional — presentation/remediation options**, normalized for the
current invocation only per
[`invocation-options.md`](../../shared/policies/invocation-options.md):

- `include_fix_prompt` (boolean, default `false`).
  An explicit output-only opt-in: when `true`, a qualifying actionable
  finding may append a coding-agent-ready implementation prompt. The flag
  never changes the Review Target, inspection, evidence, finding
  identity, severity, deduplication, PR-context reconciliation, or the
  mechanical Decision, and it never authorizes mutation or an autonomous
  fix workflow. Only remediation rendering differs. Not inferred from
  urgency, severity, branch name, or intent.
- `include_fix_guidance` (default `true`) — remediation elaboration;
  never removes the mandatory concise `Fix`.
- `include_finding_details` (default `true`) — the optional supporting
  `Details` field.
- `human_review_output` (boolean, default `false`) — requested in natural
  language ("make the review shorter and more human", "like a senior
  engineer"; no flag). Renders only the human-facing body (Result →
  Decision) in a concise senior-engineer voice; the trailing "Review
  Metadata" / "Review scope contract" sections still follow it unchanged.
  Output-only: it never changes the Review Target, inspection, evidence,
  finding identity, severity, deduplication, PR-context reconciliation, or
  the mechanical Decision.

## 2. Required Policy Loading

Always, as one batched operation:
[`review-scope.md`](../../shared/policies/review-scope.md),
[`severity.md`](../../shared/policies/severity.md),
[`evidence.md`](../../shared/policies/evidence.md),
[`repository-instructions.md`](../../shared/policies/repository-instructions.md),
[`runtime-validation.md`](../../shared/policies/runtime-validation.md),
[`review-context.md`](../../shared/policies/review-context.md) (its
requirement-context and scope-boundary sections bind only when context is
supplied),
[`git-safety.md`](../../shared/policies/git-safety.md),
[`file-reviewability.md`](../../shared/policies/file-reviewability.md)
(every changed-file category, including generated/opaque content),
[`invocation-options.md`](../../shared/policies/invocation-options.md),
[`remediation-guidance.md`](../../shared/policies/remediation-guidance.md),
and [`review-summary.md`](../../shared/templates/review-summary.md). In
orchestrated/ multi-Agent contexts, also
[`review-ownership.md`](../../shared/policies/review-ownership.md).

This Skill's own, always:
[`policies/invocation-approval.md`](policies/invocation-approval.md) (the
per-invocation explicit-user-approval contract — see section 5) and
[`policies/repository-state.md`](policies/repository-state.md) (category
definitions, per-category detection commands, staged-delta fingerprint).

Conditionally, only when its own input is supplied per section 1: the
shared `review-context.md` requirement-context / scope-boundary sections
plus [`policies/review-context.md`](policies/review-context.md) (review
context); the shared
[`review-evidence.md`](../../shared/policies/review-evidence.md) plus
[`policies/pr-context.md`](policies/pr-context.md) (PR reference). Each
loads independently. **This policy is never loaded or applied when no PR
reference is supplied**, and likewise for review context.

This Skill defines no severity, evidence, or scope policy of its own — it
consumes the shared ones so both Skills apply one standard. None of the
files above depend on another's content to be read — load them together
in a single batched/parallel operation rather than one at a time in
sequence.

## 3. Output Contract

Exactly one
[`templates/local-review-report.md`](templates/local-review-report.md)
per invocation, rendering the shared shape in
[`review-summary.md`](../../shared/templates/review-summary.md): a
Result, What changed, optional What was done well, an optional Context
section (only when review context materially shaped the review), an
optional PR Context section (only when a PR reference materially shaped
it), Findings (omitted when the finalized set is empty), Validation, and
a Decision of `REVIEW CLEAN` or `CHANGES REQUIRED` derived mechanically
from blocking (P0/P1) severities.

Machine detail (base/HEAD SHAs, synchronization status, raw counts,
per-category inclusion/exclusion, staged-delta fingerprint) is
subordinate — a trailing plain-Markdown metadata block, never ahead of
the human-facing review. The fingerprint and the previously-reviewed-state
comparison are always computed; their *display* is relevance-gated per
the report template. The report is returned to the caller as one complete
document — never published, never streamed finding-by-finding. With
`include_fix_prompt=false` (default) findings carry no full implementation
prompt, and a clean review never manufactures implementation work.

## 4. Statelessness and Orchestration Boundary

Each invocation is `current state → review → findings → stop`, with no
memory of prior invocations. This Skill does **not**: decide whether
another iteration should run; count or cap review-loop attempts; control
the implementing Agent; commit, push, or open PRs; ask the user for
approval to run; or assume a prior approval extends to this or any future
invocation. On its own side of the
boundary owned by
[`policies/invocation-approval.md`](policies/invocation-approval.md), it
does not ask for approval, does not track prior approvals, and does not
decide whether a re-review should happen — every invocation still
requires fresh, explicit user approval scoped to that one run, and this
Skill can neither verify nor needs to verify that it occurred. Running it
as a delegated Agent/Sub-Agent is purely mechanical and never changes who
owns the decision to invoke it. Loop limits and re-review timing are an
orchestration concern; for recommended (not enforced) re-review
discipline see [`runbooks/local-review.md`](runbooks/local-review.md).

## 5. Mutation Boundary

This Skill must never: edit files, apply patches, commit, push, rebase,
create branches, open PRs, approve anything, or request changes on
GitHub. The implementing Agent owns remediation; the orchestrator owns
workflow progression; this Skill only reviews and reports. This holds
identically when an optional PR reference is supplied per section 1:
reading PR review context is read-only and never becomes GitHub
publication, an Approve/Request Changes decision, or any other GitHub
mutation — see [`policies/pr-context.md`](policies/pr-context.md),
"Boundary with `github-pr-review`."

## 6. Configuration

None. This Skill package intentionally has no `review-config.yaml` and no
concept of a maximum loop count. Any default iteration cap is owned by
whatever runtime coordinates repeated invocations, outside this Skill's
package.
