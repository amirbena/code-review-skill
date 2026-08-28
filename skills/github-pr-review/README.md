# github-pr-review

## Purpose

A portable Code Review Agent Skill that reviews an existing GitHub Pull
Request with repository-aware reasoning and returns evidence-backed
P0/P1/P2 findings — passively as a report, or, with sufficient
authenticated GitHub access, actively by publishing inline findings, a
final summary, and an Approve/Request Changes decision. For why this
Skill exists alongside native and third-party PR reviewers, see
[`../../docs/CODE_REVIEW_COMPARISON.md`](../../docs/CODE_REVIEW_COMPARISON.md);
its "At a glance" section helps you choose between this Skill and
`local-code-review`.

## When to Use

Use this Skill to review an existing GitHub Pull Request, authored by
someone other than the local user or calling Agent, referenced by URL or
number. It is not for reviewing local/uncommitted changes with no PR —
see the sibling [`local-code-review`](../local-code-review/SKILL.md)
Skill for that.

This Skill preserves a strict reviewer/author separation, enforced at
two layers:

- **Selection/invocation boundary (primary):** this Skill's own
  `description` states it is not applicable — and must not be selected
  or invoked — when the local user authored the code or PR under
  review, or when an implementing Agent has just opened its own PR for
  the change it made.
- **Runtime defensive guard (fallback, unchanged):** if invoked anyway,
  self-review by the authenticated PR author is skipped
  (`REVIEW SKIPPED`) before any diff analysis or publication.

Independent review authority is required for a review to proceed. The
complete rule is owned by
[`policies/review-authority.md`](policies/review-authority.md) — this is
a summary, not a restatement.

## Review Model

```text
PR state
→ review authority
→ review mode
→ complete scope
→ logical cohorts
→ impact analysis
→ findings
→ decision
```

In brief: resolve the PR and reviewer identity, apply the self-review
guard, resolve whether this is a full or bounded delta re-review,
retrieve the complete required PR scope, reason about related changes as
logical cohorts with their impact/dependency footprint, produce
evidence-backed findings, and either publish one finalized GitHub review
(active) or return a report (passive). See
[`SKILL.md`](SKILL.md) for the full flow and
[`policies/github-review.md`](policies/github-review.md) for each
stage's canonical rule.

## Repository-access modes

API-only mode never prepares a checkout. Optional or explicitly required
repository-backed inspection materialises an **isolated,
read-only, detached temporary checkout at the PR head** so it can read
surrounding implementation, interfaces, tests, config, and architecture as
Repository Context. The **PR stays the Review Target** — findings stay
causally connected to the PR delta
(`merge-base(base, head)..head`); the checkout never turns surrounding files
into independent targets. It is read-only: the target repository's tests,
builds, linters, hooks, and scripts are never run. The temporary directory is
created under a safe scratch parent, unique per invocation, and is **always**
cleaned up (success, any failure, interruption), guarded so no unconstrained
recursive delete is possible. Optional failure is reported and continues
API-only. Required failure returns ungraded `REVIEW INCOMPLETE` with
`REPOSITORY CONTEXT UNAVAILABLE`, before workers start. See
[`policies/repository-checkout.md`](policies/repository-checkout.md).

## Parallel review (opt-in execution optimisation)

Sequential review is the default. When the runtime exposes a reliable
multi-agent / sub-agent capability **and** at least two materially independent
dimensions can run concurrently with an expected latency benefit, review may split across
independent **read-only** workers by dimension (scope, architecture,
correctness, tests/config, existing-review reconciliation). Parallelism is an
optimisation, never a semantic change: sequential and parallel execution must
reach the **same** findings and decision, and sequential is always a valid
fallback — a review is never failed because parallelism is unavailable. One
aggregating reviewer normalizes, deduplicates, reconciles, applies canonical
severity, derives the one decision, and submits the one GitHub review;
workers publish nothing and a missing required dimension yields `REVIEW
INCOMPLETE`, never `REVIEW CLEAN`. Portable contract:
[`../../shared/policies/parallel-review.md`](../../shared/policies/parallel-review.md);
PR application + per-runtime realisation (Claude Code Agent Teams / Cursor
subagents / Codex concurrent agents, with capability detection and fallback):
[`policies/parallel-review.md`](policies/parallel-review.md).

## Review context and prior review evidence

The PR is always the review target. Two optional/contextual inputs shape *how*
it is reviewed, never *what* is reviewed:

- **Review context** — caller-supplied requirements, explicit user
  instructions, pasted Jira/ticket text, a GitHub Issue (no automatic
  PR↔Issue discovery), HLD/ADR content, an implementation plan, or the PR
  description read as intent. Reused from the shared
  [`../../shared/policies/review-context.md`](../../shared/policies/review-context.md)
  (the same model `local-code-review` applies), with a thin PR application in
  [`policies/review-context.md`](policies/review-context.md). Enables
  scope-boundary reasoning — required behavior missing from the PR, the PR
  contradicting acceptance criteria, unrelated scope expansion,
  valid-but-out-of-scope findings, and repository-policy violations that hold
  regardless of ticket scope. Absent context changes nothing.
- **Jira reference** — a bare Jira key/URL is a *pointer*, not context. When
  supplied, it is resolved to normalized context **before** review reasoning
  through an available Jira MCP / connector / equivalent integration
  (**read-only** — retrieval only, no Jira mutation), per the shared policy's
  "Jira context resolution." If it cannot be resolved (no integration,
  auth/authz failure, ticket not found, malformed), this Skill reports the
  `JIRA CONTEXT UNRESOLVED` reasoning result and does not perform the
  Jira-scoped review — it never infers the ticket from its key, branch name,
  or PR title. Jira is never mandatory; re-invoke without a Jira reference
  for a normal unscoped review.
- **Existing Review Evidence** — the PR's own prior reviews (with their
  `APPROVED` / `CHANGES_REQUESTED` / `COMMENTED` state), review comments,
  issue comments, and review-thread `isResolved` state where GitHub exposes
  it — retrieved paginated-to-exhaustion via an authenticated GitHub
  integration (`gh api` + GraphQL `reviewThreads` being one example, per
  [`policies/pr-scope.md`](policies/pr-scope.md), "Retrieving prior review
  activity"), per the shared
  [`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md)
  and [`policies/review-evidence.md`](policies/review-evidence.md). Classified
  as still-relevant / resolved / stale / duplicate / settled decision /
  speculative discussion, then used to avoid repeating settled findings,
  contradicting settled decisions without new evidence, and missing an
  unresolved previously identified issue — never blindly inherited, always
  reconciled against the current PR HEAD. A resolved thread is evidence of a
  past conclusion, not proof the current HEAD is correct (a reintroduced
  defect is a fresh finding); a changed HEAD re-classifies every prior human
  finding; automation/bot comments contribute observations only and never
  settle a decision on their own.

## Behavioral review signals

The "reason about related changes" and "impact analysis" stages above
apply [`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md)
in full — the same file `local-code-review` applies, never a forked copy.
Beyond the baseline concern list, that shared policy includes a small,
signal-triggered set of heuristics for recurring, high-value review gaps
(existing behavior ownership/reuse, failure-state/retry/recovery safety
with applicability-gated observability, and contract/exception semantics
followed to actual callers). This Skill consumes them exactly as
`local-code-review` does; see that Skill's own README, "Behavioral review
signals," for the conceptual summary (not linked here: a packaged Skill
archive is self-contained and does not depend on a sibling Skill's own
README) — it is not repeated here.

## Review Outcomes / Severity

Findings use the shared P0/P1/P2 model
([`../../shared/policies/severity.md`](../../shared/policies/severity.md)):

- **P0** — critical, blocking
- **P1** — significant, blocking
- **P2** — non-blocking engineering improvement

Maximum positive action is **Approve**; this Skill never merges.

## Key Files

- [`SKILL.md`](SKILL.md) — canonical entry point and identity
- [`policies/github-review.md`](policies/github-review.md) — canonical
  policy index for this Skill
- [`policies/review-authority.md`](policies/review-authority.md) — identity,
  self-review guard, publication capability
- [`policies/reviewer-delta-review.md`](policies/reviewer-delta-review.md) —
  full vs. delta re-review mode
- [`policies/pr-scope.md`](policies/pr-scope.md) — complete PR scope
- [`policies/repository-checkout.md`](policies/repository-checkout.md) —
  opt-in isolated temporary checkout; base/head fidelity; read-only; cleanup
- [`policies/review-context.md`](policies/review-context.md) — thin PR
  application of the shared review-context model; scope-boundary reasoning
- [`policies/review-evidence.md`](policies/review-evidence.md) — thin PR
  application of the shared Existing Review Evidence model
- [`policies/review-reasoning.md`](policies/review-reasoning.md) — logical
  cohorts, impact/dependency analysis
- [`policies/parallel-review.md`](policies/parallel-review.md) — thin PR
  application of the shared parallel contract; runtime realisation
- [`policies/finding-placement.md`](policies/finding-placement.md) — inline
  vs. body placement
- [`policies/review-output.md`](policies/review-output.md) — publication
  and decision
- [`runbooks/passive-pr-review.md`](runbooks/passive-pr-review.md) /
  [`runbooks/active-pr-review.md`](runbooks/active-pr-review.md) — full
  procedures
- [`templates/external-review-summary.md`](templates/external-review-summary.md)
  / [`templates/inline-finding.md`](templates/inline-finding.md) — output
  contracts

## Validation / Packaging

Run from the repository root:

```bash
python3 scripts/validate-skill-metadata.py skills/github-pr-review --containment-root .
./scripts/package-skills.sh github
```

PowerShell counterpart: `./scripts/package-skills.ps1 github`. Output:
`dist/github-pr-review-skill.zip`.

The repository's Python test suite lives under `tests/`; run it from the
repository root with `python3 -m unittest discover -s tests -t .`.

## README Boundary

This README is descriptive onboarding documentation. It is not a policy
file and carries no normative authority. Normative behavior is defined
by [`SKILL.md`](SKILL.md), the policies under [`policies/`](policies/github-review.md),
and the shared policies under
[`../../shared/policies/`](../../shared/policies/severity.md).
