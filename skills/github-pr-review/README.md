# github-pr-review

## Purpose

A portable Code Review Agent Skill that reviews an existing GitHub Pull
Request with repository-aware reasoning and returns evidence-backed
P0/P1/P2 findings — passively as a report, or, with sufficient
authenticated GitHub access, actively by publishing inline findings, a
final summary, and an Approve/Request Changes decision. For why this
Skill exists alongside native and third-party PR reviewers, see
[`../../CODE_REVIEW_COMPARISON.md`](../../CODE_REVIEW_COMPARISON.md).

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
- [`policies/review-reasoning.md`](policies/review-reasoning.md) — logical
  cohorts, impact/dependency analysis
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

## README Boundary

This README is descriptive onboarding documentation. It is not a policy
file and carries no normative authority. Normative behavior is defined
by [`SKILL.md`](SKILL.md), the policies under [`policies/`](policies/github-review.md),
and the shared policies under
[`../../shared/policies/`](../../shared/policies/severity.md).
