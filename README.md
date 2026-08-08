# code-review-skill

This repository contains two portable **Code Review Agent Skills**.

## What this repository contains

| Skill | What it does |
|---|---|
| [`local-code-review`](skills/local-code-review/SKILL.md) | Reviews local implementation changes and returns P0/P1/P2 findings. Does not modify code or GitHub state. |
| [`github-pr-review`](skills/github-pr-review/SKILL.md) | Reviews GitHub Pull Requests. Can operate passively, or, when active review access is available, publish inline P0/P1/P2 findings, publish a concise final review summary, Approve, or Request Changes. It never merges the Pull Request. |

## Prerequisites

- Git
- GitHub CLI (`gh`) — for GitHub PR review
- an authenticated `gh` session — for active GitHub operations

```bash
gh auth status
```

Credentials come from the environment and are never stored in either
Skill.

## Packaging

```bash
./scripts/package-skills.sh local
./scripts/package-skills.sh github
./scripts/package-skills.sh all
```

```powershell
./scripts/package-skills.ps1 local
./scripts/package-skills.ps1 github
./scripts/package-skills.ps1 all
```

Produces:

```text
dist/local-code-review-skill.zip
dist/github-pr-review-skill.zip
```

## Where to read more

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — design, module boundaries, and
  the orchestration boundary between the Skills and their caller
- [`AGENTS.md`](AGENTS.md) — this repository's own canonical development
  rules, plus the shared review-ownership invariant
- [`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md)
- [`skills/github-pr-review/SKILL.md`](skills/github-pr-review/SKILL.md)
