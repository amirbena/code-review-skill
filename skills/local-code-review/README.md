# local-code-review

## Purpose

A small, stateless Code Review Agent Skill that reviews a local Git
repository's implementation state — committed, staged, unstaged, and
untracked changes, each detected separately — and returns evidence-backed
P0/P1/P2 findings. Read-only: it never edits files, commits, pushes, or
touches GitHub. For local/uncommitted state before a push or PR; for an
existing GitHub Pull Request, use the sibling
[`github-pr-review`](../github-pr-review/SKILL.md) Skill instead. See
[`../../docs/CODE_REVIEW_COMPARISON.md`](../../docs/CODE_REVIEW_COMPARISON.md) for
why this Skill exists alongside native and third-party reviewers, and its
"At a glance" section for choosing between this Skill and `github-pr-review`.

## Opt-in only

This Skill never runs automatically. Every invocation — first review or
any re-review — requires fresh, explicit user approval scoped to that one
run; a prior approval never carries forward. See
[`policies/invocation-approval.md`](policies/invocation-approval.md) for
the complete contract.

## Decision semantics

Findings use the shared P0/P1/P2 model: **P0** (critical) and **P1**
(significant) block; **P2** (non-blocking improvement) never does. The
final `REVIEW CLEAN` / `CHANGES REQUIRED` decision is derived
mechanically from whether any P0/P1 is present — never a separate
judgment call, and never affected by a P2's severity or origin. A clean
review may still list P2 findings; they stay visible, never hidden or
downgraded to obtain a clean result. Full definitions and the exact
derivation rule live in
[`../../shared/policies/severity.md`](../../shared/policies/severity.md)
— this is a summary, not a restatement.

## Optional inputs

Three optional inputs may accompany a review request. Review context and PR
context are independent applications of the
shared context model in
[`../../shared/policies/review-context.md`](../../shared/policies/review-context.md)
and
[`../../shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md).

- **Review context** — free-form requirements, explicit user instructions,
  Jira/ticket content, acceptance criteria, an explicitly supplied GitHub
  Issue (no automatic PR↔Issue discovery), HLD/ADR content, an
  implementation plan, or constraints/non-goals describing the intended
  change. Used to focus attention (what to inspect carefully) and to reason
  about the requested change's scope boundary — missing required behavior,
  contradiction of acceptance criteria, unrelated scope expansion,
  valid-but-out-of-scope findings, and repository-policy violations that
  hold regardless of ticket scope. Never authority over the actual code:
  evidence precedence is code/diff/tests > repository instructions >
  supplied context > inference, and context never expands the review target
  beyond the current delta. See
  [`policies/review-context.md`](policies/review-context.md).
- **PR reference** — an associated GitHub PR whose prior findings, prior
  review comments, and settled decisions are reconciled as Existing Review
  Evidence: still-relevant, resolved, stale, duplicate, settled decision, or
  speculative discussion — never blindly inherited, always reconciled against
  the current local delta. Retrieval is read-only, targeted to the delta
  (`gh api` reviews/comments + GraphQL `reviewThreads` is one example), and
  never expands the review target to the PR's full history; unavailable
  history never blocks the local review. A resolved thread is evidence of a
  past conclusion, not proof the delta is correct; automation/bot comments
  contribute observations only. See
  [`policies/pr-context.md`](policies/pr-context.md).

Example invocation with review context (exact syntax depends on the
runtime):

```text
/local-code-review

Context source: Jira BILLPAY-1234
Acceptance criteria:
- reject unsupported CC + RTP combinations
- validation must occur before execution
```

A plain `/local-code-review` with no context supplied remains fully
supported and behaves exactly as before this input existed.

- **`include_fix_prompt`** — boolean, default `false`, explicit opt-in only.
  When enabled, qualifying actionable findings may add a coding-agent-ready
  implementation prompt for the fast local review → fix → separately approved
  re-review workflow. It changes only remediation rendering: scope, inspection,
  findings, severity, reconciliation, deduplication, and verdict remain
  identical. The Skill remains read-only and does not execute the prompt.
- **`include_finding_details`** — boolean, default `true`; controls only the
  optional supporting `Details` field.
- **`include_fix_guidance`** — boolean, default `true`; controls optional
  remediation elaboration but never removes the mandatory concise `Fix`.

Canonical assignments and explicit requests such as “give me a fix prompt”
normalize identically for the current invocation only; see
[`../../shared/policies/invocation-options.md`](../../shared/policies/invocation-options.md).

## Review flow (overview)

1. determine review scope (base, branch, committed/staged/unstaged/untracked delta)
2. discover and load applicable repository instructions (`AGENTS.md`/`CLAUDE.md`)
3. understand optional review context and/or PR context, if supplied
4. review the delta, focused by any applicable context from step 3
5. classify findings and verify evidence
6. derive the decision mechanically from blocking severities

The authoritative, numbered procedure is
[`runbooks/local-review.md`](runbooks/local-review.md); this is a
compact overview, not a substitute for it.

## Behavioral review signals (step 4)

Step 4's review reasoning is defined once in
[`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md)
(shared identically with `github-pr-review`, so it never diverges between
the two Skills). Beyond the baseline concern list, it includes a small,
signal-triggered set of heuristics for recurring, high-value review gaps:
whether new business/validation/state-transition logic duplicates an
existing canonical owner rather than reusing it ("Existing behavior
ownership"); whether a multi-step, retryable, or externally re-triggerable
flow leaves safe or stranded state on partial failure, and whether any
claimed recovery is actually evidenced ("Failure state, retry safety, and
recovery"); and whether a changed contract, return value, or exception —
including one now swallowed, translated, or masked by a fallback — is
followed to its actual callers (a tightening of "Related changes as one
unit"). Each activates only when the diff's own shape gives concrete
reason to and stays scaled to blast radius per
[`../../shared/policies/evidence.md`](../../shared/policies/evidence.md) —
none of them turns a review into a repository-wide audit or a mandatory
checklist.

Observability is itself applicability-gated within that same section: it
only applies once a change actually has a production-operational failure
mode worth detecting or diagnosing (commonly backend/service runtime
behavior, payments, queues/events/webhooks, external integrations,
retries, or background jobs; conditionally frontend changes with an
established client telemetry convention; usually not agent-instruction,
prompt, policy, or static-doc changes unless they carry runtime behavior
of their own). Only then does it prefer the repository's own established
metrics/alerts or logging convention over inventing new observability —
never a blanket "add a metric" or "add more logs" recommendation.

## Key files

- [`SKILL.md`](SKILL.md) — the Skill contract (identity, inputs, output contract)
- [`runbooks/local-review.md`](runbooks/local-review.md) — the full, authoritative procedure
- `policies/` — behavioral rules this Skill owns (invocation approval, repository-state categories, optional review context, optional PR context)
- [`templates/local-review-report.md`](templates/local-review-report.md) — the output contract
- [`../../shared/policies/severity.md`](../../shared/policies/severity.md) — the canonical P0/P1/P2 and decision-derivation model, shared with `github-pr-review`

### Thin runbook, canonical policy owners

`runbooks/local-review.md` is intentionally a thin execution document: it
defines flow, phase ordering, and which policy governs each phase, and it
does not restate that policy's own semantics — this source repository's
own repository-development policies (the "Runbook Design" rule in its
Skill-development policy) state the general rule this follows (not linked
here: a packaged Skill archive never depends on this source repository's
own root-level development docs or `policies/`). In particular, all
Git-mechanics detail
— the four repository-state categories, push/synchronization status, and
the complete staged-fingerprint re-review precondition/comparison contract
— is owned entirely by
[`policies/repository-state.md`](policies/repository-state.md); the
runbook only says when each is resolved and applied. Optional
review-context and PR-context handling are owned the same way by
[`policies/review-context.md`](policies/review-context.md) and
[`policies/pr-context.md`](policies/pr-context.md) respectively.

The Python modules under this repository's `tests/reference/` directory (e.g.
`review_context.py`, `decision_semantics.py`) are this repository's own
validation/reference helpers — they mirror a policy's decision tables for
this repo's test suite and are not packaged Skill runtime logic. The
behavioral heuristics in `review-scope.md` have no such module: an earlier
iteration added one purely for testability and it was removed as a
duplicate source of truth (see this repository's "Runbook Design" rule) — that policy's
Markdown text is tested directly instead (see
[`../../tests/policy/test_review_scope_behavioral_heuristics.py`](../../tests/policy/test_review_scope_behavioral_heuristics.py)).

## Development / validation

From the repository root:

```bash
python3 scripts/validate-skill-metadata.py skills/local-code-review --containment-root .
./scripts/package-skills.sh local
```

PowerShell counterpart: `./scripts/package-skills.ps1 local`. Output:
`dist/local-code-review-skill.zip`.

The repository's Python test suite lives under `../../tests/`; run it from
the repository root with `python3 -m unittest discover -s tests -t .`.

## README boundary

This README is descriptive onboarding documentation only — it carries no
normative authority. Normative behavior is defined by
[`SKILL.md`](SKILL.md), this Skill's own `policies/`,
[`runbooks/local-review.md`](runbooks/local-review.md), and the shared
policies under
[`../../shared/policies/`](../../shared/policies/severity.md).
