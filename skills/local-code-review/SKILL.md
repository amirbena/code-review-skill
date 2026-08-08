# SKILL.md — local-code-review

A small, bounded, **stateless** Code Review Skill that reviews a local
Git repository's implementation state and returns structured P0/P1/P2
findings. It is a reviewer only.

```text
local repository state
    ↓
identify implementation delta
    ↓
inspect changed implementation
    ↓
apply shared review policies
    ↓
return P0/P1/P2 findings
    ↓
stop
```

See [`runbooks/local-review.md`](runbooks/local-review.md) for the full
procedure and [`templates/local-review-report.md`](templates/local-review-report.md)
for the output contract.

---

## 1. Identity

- **Name:** `local-code-review`
- **Purpose:** review the complete local implementation state of a Git
  repository (committed delta, local-only commits, staged, unstaged, and
  relevant untracked changes) and return findings.
- **Not:** an orchestrator, a fix loop, a Git-mutating agent, or a
  GitHub-publishing agent. See the sibling `github-pr-review` Skill for
  GitHub Pull Request review.

## 2. Inputs

A local Git repository. The Skill may inspect: current branch, base
branch, base SHA, local HEAD, committed branch changes, local-only
commits, staged changes, unstaged changes, relevant untracked files,
relevant surrounding repository code, tests, and repository instructions.
The full implementation state is reviewed — local `HEAD` alone is never
assumed to contain everything.

## 3. Required Policy Loading

Always: [`review-scope.md`](../../shared/policies/review-scope.md),
[`severity.md`](../../shared/policies/severity.md),
[`evidence.md`](../../shared/policies/evidence.md),
[`repository-instructions.md`](../../shared/policies/repository-instructions.md),
[`git-safety.md`](../../shared/policies/git-safety.md). In orchestrated/
multi-Agent contexts, also
[`review-ownership.md`](../../shared/policies/review-ownership.md).

This Skill defines no severity, evidence, or scope policy of its own — it
consumes the shared ones so both Skills apply one review standard.

## 4. Output Contract

Exactly one [`templates/local-review-report.md`](templates/local-review-report.md)
per invocation, containing Review State, Blocking Findings, Non-Blocking
Findings, and a Result of `REVIEW CLEAN` or `CHANGES REQUIRED`. Returned
to the caller — never published anywhere.

## 5. Statelessness and Orchestration Boundary

**This Skill does not own a multi-step fix loop.** Each invocation is:

```text
current implementation state
    ↓
review
    ↓
findings
    ↓
stop
```

It has no memory of prior invocations and does not need to know whether
this is review pass 1, 2, 3, or later. Specifically, this Skill does
**not**:

- decide whether another review iteration should run;
- count review-loop attempts or track a maximum;
- control or instruct the implementing Agent;
- commit fixes, push changes, or open PRs.

**Loop limits, re-invocation timing, and workflow progression are
entirely an orchestration concern**, owned by the calling
runtime/Team Lead/implementing workflow — not by this Skill. A caller
that wants an iterative review/fix loop invokes this Skill repeatedly and
enforces its own maximum; see this repository's own `ARCHITECTURE.md` for
the recommended handoff shape. For recommended (not enforced)
re-review discipline across repeated invocations, see
[`runbooks/local-review.md`](runbooks/local-review.md).

## 6. Mutation Boundary

This Skill must never: edit files, apply patches, commit, push, rebase,
create branches, open PRs, approve anything, or request changes on
GitHub. The implementing Agent owns remediation; the orchestrator owns
workflow progression; this Skill only reviews and reports.

## 7. Review Ownership

Subject to the same `One review scope → one Code Review Agent owner`
invariant as `github-pr-review` — see
[`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md).
If another Code Review Agent already owns this local branch/scope, return
`REVIEW ALREADY OWNED` and do not launch a competing review.

## 8. Configuration

None. This Skill package intentionally has no `review-config.yaml` and no
concept of a maximum loop count — see section 5. A separate,
orchestration-level configuration (owned by whatever runtime coordinates
repeated invocations) may define a default iteration cap; that is outside
this Skill's package.
