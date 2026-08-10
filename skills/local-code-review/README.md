# local-code-review

## Purpose

A small, stateless Code Review Agent Skill that reviews a local Git
repository's implementation state — committed delta, staged, unstaged,
and untracked changes, each an explicit, separately detected category —
and returns evidence-backed P0/P1/P2 findings. It is read-only: it never
edits files, commits, pushes, or touches GitHub. For why this Skill
exists alongside native and third-party reviewers, see
[`../../CODE_REVIEW_COMPARISON.md`](../../CODE_REVIEW_COMPARISON.md).

## When to Use

Use this Skill to review local/uncommitted implementation state before
a push or PR. It is not for reviewing an existing GitHub Pull Request —
see the sibling [`github-pr-review`](../github-pr-review/SKILL.md) Skill
for that.

**This Skill is opt-in, end-user-controlled, per invocation** — even
when an implementing Agent invokes it as a delegated Agent/Sub-Agent:

- the end user, not the implementing Agent, decides whether a given
  review or re-review runs at all, via an explicit request — made in
  the current interaction — whose meaning unambiguously asks for a
  local code review; naming `local-code-review` is one sufficient form
  of that, never a required magic phrase;
- generic validation/completion language ("check your work," "make sure
  this is correct"), a remembered or standing user preference,
  repository/orchestration policy, and silence/non-objection are all
  explicitly insufficient by themselves — unless the utterance as a
  whole otherwise unambiguously requests a local code review;
- an approval that authorized one invocation never authorizes another —
  every re-review requires its own fresh, explicit user opt-in;
- this Skill does not track prior approvals or decide whether a
  re-review should happen — that is the caller's/orchestrator's
  responsibility;
- the orchestration mechanism used to invoke this Skill (direct call vs.
  delegated Agent/Sub-Agent) never changes who owns that decision, and
  never broadens or extends the scope/duration of what was authorized.

The complete rule is owned by
[`policies/invocation-approval.md`](policies/invocation-approval.md) —
this is a summary, not a restatement.

## Review Context

This Skill reasons from local Git state, not GitHub PR state. It
distinguishes explicit repository-state categories — committed delta
relative to a base, staged (tracked, indexed), unstaged (tracked,
working-tree-only), and untracked — each detected with its own Git
command, never blended into one undifferentiated set; see
[`policies/repository-state.md`](policies/repository-state.md). It may
also inspect current branch, base branch, base SHA, local `HEAD`,
relevant surrounding repository code, tests, and repository instructions
(`AGENTS.md`/`CLAUDE.md`).

## Review Model

```text
resolve local review scope
→ discover applicable AGENTS.md / CLAUDE.md
→ detect committed / staged / unstaged / untracked separately
→ compute staged-delta fingerprint (SHA-256 of `git diff --cached --raw -M -z`)
→ inspect relevant surrounding code
→ review against code + repository conventions
→ return P0/P1/P2 findings, attributed to source category
→ stop
```

Each invocation is a single, stateless pass — no loop/iteration concept,
no memory of prior invocations. On re-review, a matching staged
fingerprint means the staged delta is unchanged; it never implies
unstaged or untracked state is unchanged — those are re-detected
independently every time. See [`SKILL.md`](SKILL.md) for the full
statelessness and orchestration boundary.

## Findings / Severity

Findings use the shared P0/P1/P2 model
([`../../shared/policies/severity.md`](../../shared/policies/severity.md)):

- **P0** — critical, blocking
- **P1** — significant, blocking
- **P2** — non-blocking engineering improvement

The report resolves to `REVIEW CLEAN` or `CHANGES REQUIRED`.

The final report is rendered as native Markdown, including its Review
Metadata section — no GitHub-specific HTML presentation wrappers (e.g.
`<details>`/`<summary>`), since it is read directly in a terminal or
chat surface rather than rendered by GitHub. See
[`templates/local-review-report.md`](templates/local-review-report.md).

## Key Files

- [`SKILL.md`](SKILL.md) — canonical entry point and identity
- [`policies/invocation-approval.md`](policies/invocation-approval.md) —
  per-invocation approval contract
- [`policies/repository-state.md`](policies/repository-state.md) —
  committed/staged/unstaged/tracked/untracked category definitions,
  detection commands, and the staged-delta fingerprint
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
