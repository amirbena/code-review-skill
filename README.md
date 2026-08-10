# code-review-skill

This repository contains two portable **Code Review Agent Skills** for
Agent Skills-compatible runtimes. Each is packaged around a canonical
[Agent Skills](https://agentskills.io/specification) `SKILL.md` and may
include optional runtime adapters that do not change review behavior.

## What this repository contains

| Skill | What it does |
|---|---|
| [`local-code-review`](skills/local-code-review/SKILL.md) | Reviews local implementation changes and returns P0/P1/P2 findings. Does not modify code or GitHub state. |
| [`github-pr-review`](skills/github-pr-review/SKILL.md) | Reviews GitHub Pull Requests. Can operate passively, or, when active review access is available, publish inline P0/P1/P2 findings, publish a concise final review summary, Approve, or Request Changes. It never merges the Pull Request. |

## Prerequisites

- Git — required for both Skills
- Python 3 (`python3`) — required to run this repository's validation and
  packaging tooling (`scripts/validate-skill-metadata.py`,
  `scripts/package-skills.sh` / `scripts/package-skills.ps1`,
  `scripts/test_reviewer_ownership.py`). No minimum version is currently
  enforced; check availability with:

  ```bash
  python3 --version
  ```

- authenticated GitHub access — required for GitHub-connected PR state
- sufficient review permissions — required only for *active* publication

The authenticated account must be eligible to submit the intended formal
review action. A complete review can still report findings when GitHub does
not permit that account to submit Approve or Request Changes.

Credentials come from the environment and are never stored in either
Skill.

## Packaging

Choose the package based on how the reviewer will be used. Each archive
is standalone and contains its Skill's `SKILL.md` at the archive root
(not nested under a `skills/` path) — a consumer never needs to know
this repository's source layout.

### Local code review

For reviewing local branch/worktree changes without publishing to
GitHub. Typical use: implementation review before push, or review from
an implementing Agent — covers committed, staged, unstaged, and relevant
untracked changes, returning P0/P1/P2 findings without mutating GitHub.

Shell:

```bash
./scripts/package-skills.sh local
```

PowerShell:

```powershell
./scripts/package-skills.ps1 local
```

Output: `dist/local-code-review-skill.zip`

### GitHub PR review

For reviewing an existing GitHub Pull Request — passively, or actively
(inline P0/P1/P2 comments, a human-readable summary, Approve/Request
Changes) when GitHub-connected behavior is needed. Active review
requires authenticated GitHub access with sufficient permissions.

Shell:

```bash
./scripts/package-skills.sh github
```

PowerShell:

```powershell
./scripts/package-skills.ps1 github
```

Output: `dist/github-pr-review-skill.zip`

### Package both

Only when the consuming environment needs both review entry points — not
the typical case.

Shell:

```bash
./scripts/package-skills.sh all
```

PowerShell:

```powershell
./scripts/package-skills.ps1 all
```

Output: `dist/local-code-review-skill.zip` and
`dist/github-pr-review-skill.zip`

## Where to read more

- [`CODE_REVIEW_COMPARISON.md`](CODE_REVIEW_COMPARISON.md) — why these Skills
  exist alongside Claude Code, GitHub-native, and third-party reviewers, and
  what they add
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — design, module boundaries, and
  the orchestration boundary between the Skills and their caller
- [`AGENTS.md`](AGENTS.md) — this repository's own canonical development
  rules, plus the shared review-ownership invariant
- [`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md)
- [`skills/github-pr-review/SKILL.md`](skills/github-pr-review/SKILL.md)
