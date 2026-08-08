# code-review-skill

Two private, portable **Code Review Agent Skills**, sharing one review
standard.

| Skill | Purpose |
|---|---|
| [`local-code-review`](skills/local-code-review/SKILL.md) | Review local implementation state (committed, staged, unstaged, relevant untracked changes) and return structured findings. |
| [`github-pr-review`](skills/github-pr-review/SKILL.md) | Review a GitHub Pull Request and, when authorized, publish inline findings and Approve/Request Changes. |

Both behave like a traditional senior code reviewer: they identify
problems, explain them, suggest corrections, and — where invoked again —
re-review. **Neither implements fixes, and neither merges anything.**

## Why two Skills

Each Skill is small, bounded, and independently invokable:

- `local-code-review` is a **stateless** reviewer of local Git state. It
  has no concept of review iterations, no loop limit, and never touches
  GitHub.
- `github-pr-review` reviews an existing GitHub PR — passively (report
  only) or actively (publishes comments and a decision) — and never owns
  implementation fixes or repository lifecycle cleanup.

They share one review standard via [`shared/`](shared/) — the same
P0/P1/P2 severity model, evidence requirements, review scope, repository
instruction awareness, and Git safety apply to both. Neither Skill
defines its own copy of these rules.

## How they connect

```text
Local
implementation
    → local-code-review
    → findings
    → caller decides next action (fix, re-run, or proceed)
```

```text
GitHub
PR
    → github-pr-review
    → findings/comments
    → Approve / Request Changes
```

`local-code-review` does **not** automatically invoke `github-pr-review`,
and `github-pr-review` does **not** assume `local-code-review` was
previously run — they are independently invokable. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the full handoff diagram and the
orchestration boundary.

## What neither Skill does

- **Suggests** fixes; neither directly implements them. Fixing
  implementation code is the responsibility of the implementing Agent or
  developer.
- Owns review-loop iteration count, retries, or workflow progression —
  that belongs to the orchestrating runtime/Team Lead, not to either
  Skill (see [`ARCHITECTURE.md`](ARCHITECTURE.md), "Orchestration
  Boundary").
- Merges a Pull Request, deletes branches, or performs repository
  lifecycle cleanup. `github-pr-review`'s maximum positive action is
  **Approve**.

## Prerequisites

```text
- Git
- GitHub CLI (`gh`)                    -- required only for github-pr-review
- an authenticated GitHub CLI session  -- required only for active PR review
```

- `local-code-review` only needs Git — it works entirely from local
  repository data and never requires `gh`.
- `github-pr-review`'s passive mode needs `gh` to retrieve PR data; its
  active mode additionally needs an authenticated `gh` session with
  actual review access to the target repository/PR — authentication
  alone is not sufficient (see
  [`skills/github-pr-review/policies/github-review.md`](skills/github-pr-review/policies/github-review.md)).
  If active review isn't possible, it falls back to passive reporting
  rather than faking publication.
- `gh` credentials belong to the environment. Neither Skill stores,
  embeds, or invents credentials.

Verify GitHub CLI authentication before requesting active review:

```bash
gh auth status
```

## Local review loop is an orchestration concern

`local-code-review` is stateless: each invocation reviews the current
implementation state once and returns findings. It does not decide
whether to run again, does not count iterations, and ships with no
`review-config.yaml` or `max_loops` setting of its own. A caller that
wants an iterative review/fix/re-review loop invokes the Skill repeatedly
and owns its own maximum iteration count and stopping logic. See
[`ARCHITECTURE.md`](ARCHITECTURE.md), "Orchestration Boundary."

## External PR behavior (`github-pr-review`)

- inline findings are labeled `[P0]` / `[P1]` / `[P2]` and kept short
  (see [`skills/github-pr-review/templates/inline-finding.md`](skills/github-pr-review/templates/inline-finding.md));
- a final human-readable summary (what changed, what was done well, what
  needs improvement, decision) is always published after inline findings
  and before the final decision (see
  [`skills/github-pr-review/templates/external-review-summary.md`](skills/github-pr-review/templates/external-review-summary.md));
- the review ends in **Approve** or **Request Changes** — never a merge;
- the PR HEAD is revalidated immediately before the final decision so a
  stale review is never submitted.

## Runtime neutrality

Both Skills are runtime-neutral. Each is defined as a portable
operational specification (its own `SKILL.md` plus shared/per-Skill
policies, runbooks, and templates), not as a Claude-specific subagent, a
Codex-specific agent, a Cursor-specific agent, or any other
runtime-specific worker. Any runtime capable of following these files and
invoking `git`/`gh` can execute them. See [`AGENTS.md`](AGENTS.md) for the
full **Agent via Skill** vocabulary and this repository's own development
rules.

## Repository structure

```text
.
├── AGENTS.md              canonical repo-wide rules (this repo's own development)
├── CLAUDE.md               thin adapter → AGENTS.md / applicable Skill
├── README.md               this file
├── ARCHITECTURE.md         conceptual design and module boundaries
│
├── shared/
│   ├── policies/            review-scope, severity, evidence,
│   │                         repository-instructions, git-safety
│   └── templates/
│       └── finding.md       canonical finding shape
│
├── skills/
│   ├── local-code-review/
│   │   ├── SKILL.md          entry point (stateless, bounded)
│   │   ├── metadata/skill.yaml
│   │   ├── runbooks/local-review.md
│   │   └── templates/local-review-report.md
│   │
│   └── github-pr-review/
│       ├── SKILL.md          entry point
│       ├── metadata/skill.yaml
│       ├── policies/github-review.md
│       ├── runbooks/{passive-pr-review,active-pr-review}.md
│       └── templates/{inline-finding,external-review-summary}.md
│
└── scripts/
    ├── package-skills.sh      packages either or both Skills (POSIX shell)
    └── package-skills.ps1     packages either or both Skills (PowerShell)
```

There is no root `SKILL.md` — each Skill's canonical entry point lives
under `skills/<name>/SKILL.md`. See [`ARCHITECTURE.md`](ARCHITECTURE.md)
for how these pieces fit together.

## Packaging

Each Skill can be packaged independently into a self-contained
distributable archive — consumers of one Skill are never required to
install the whole repository:

```bash
./scripts/package-skills.sh local     # dist/local-code-review-skill.zip
./scripts/package-skills.sh github    # dist/github-pr-review-skill.zip
./scripts/package-skills.sh all       # both
```

```powershell
./scripts/package-skills.ps1 -Skill local
./scripts/package-skills.ps1 -Skill github
./scripts/package-skills.ps1 -Skill all
```

Both scripts implement equivalent behavior: they validate required files
exist, stage an explicit allowlist for the requested Skill(s) — its
`SKILL.md`, metadata, policies/runbooks/templates, plus the
`shared/policies/` and `shared/templates/` files it actually depends on,
copied into the package rather than left as external references — into
`dist/`, and produce a self-contained `.zip` per Skill. `README.md`,
`AGENTS.md`, `ARCHITECTURE.md`, and `CLAUDE.md` are intentionally
excluded — they are this repository's own development/adapter
documentation, not canonical Skill behavior consumed at runtime. Neither
script touches anything outside `dist/`.
