# local-code-review

## Purpose

A small, stateless Code Review Agent Skill that reviews a local Git
repository's implementation state — committed delta, local-only commits,
staged, unstaged, and relevant untracked changes — and returns
evidence-backed P0/P1/P2 findings. It is read-only: it never edits
files, commits, pushes, or touches GitHub.

## When to Use

Use this Skill to review local/uncommitted implementation state before
a push or PR — for example, an implementing Agent seeking an independent
review of its own work in progress. It is not for reviewing an existing
GitHub Pull Request — see the sibling
[`github-pr-review`](../github-pr-review/SKILL.md) Skill for that.

**Every invocation requires fresh, explicit user approval scoped to that
one run**, obtained by the caller before invoking this Skill:

- approval is per invocation, including any later re-review after fixes;
- an approval that authorized one invocation never authorizes another;
- this Skill does not track prior approvals or decide whether a
  re-review should happen — that is the caller's/orchestrator's
  responsibility.

The complete rule is owned by
[`policies/invocation-approval.md`](policies/invocation-approval.md) —
this is a summary, not a restatement.

## Review Context

This Skill reasons from local Git state, not GitHub PR state. It may
inspect: current branch, base branch, base SHA, local `HEAD`,
committed branch changes, local-only commits, staged changes, unstaged
changes, relevant untracked files, relevant surrounding repository code,
tests, and repository instructions (`AGENTS.md`/`CLAUDE.md`).

## Review Model

```text
resolve local review scope
→ discover applicable AGENTS.md / CLAUDE.md
→ inspect Git delta
→ inspect relevant surrounding code
→ review against code + repository conventions
→ return P0/P1/P2 findings
→ stop
```

Each invocation is a single, stateless pass — no loop/iteration concept,
no memory of prior invocations. See [`SKILL.md`](SKILL.md) for the full
statelessness and orchestration boundary.

## Findings / Severity

Findings use the shared P0/P1/P2 model
([`../../shared/policies/severity.md`](../../shared/policies/severity.md)):

- **P0** — critical, blocking
- **P1** — significant, blocking
- **P2** — non-blocking engineering improvement

The report resolves to `REVIEW CLEAN` or `CHANGES REQUIRED`.

## Key Files

- [`SKILL.md`](SKILL.md) — canonical entry point and identity
- [`policies/invocation-approval.md`](policies/invocation-approval.md) —
  per-invocation approval contract
- [`runbooks/local-review.md`](runbooks/local-review.md) — full procedure
- [`templates/local-review-report.md`](templates/local-review-report.md) —
  output contract

## Validation / Packaging

Run from the repository root:

```bash
python3 scripts/validate-skill-metadata.py skills/local-code-review --containment-root .
./scripts/package-skills.sh local
```

PowerShell counterpart: `./scripts/package-skills.ps1 local`. Output:
`dist/local-code-review-skill.zip`.

## README Boundary

This README is descriptive onboarding documentation. It is not a policy
file and carries no normative authority. Normative behavior is defined
by [`SKILL.md`](SKILL.md),
[`policies/invocation-approval.md`](policies/invocation-approval.md),
[`runbooks/local-review.md`](runbooks/local-review.md), and the shared
policies under
[`../../shared/policies/`](../../shared/policies/severity.md).
