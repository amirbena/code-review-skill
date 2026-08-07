# code-review-skill

A private, portable **Code Review Agent Skill** for GitHub repositories.

> **Status: first full modular implementation.** This repository defines
> the complete Code Review Agent Skill as a modular package. See
> [`SKILL.md`](SKILL.md) for the operational entry point.

## What this Skill does

The Code Review Agent behaves like a traditional senior code reviewer. It
can:

- review an existing GitHub Pull Request;
- review a local implementation branch, before or during PR creation;
- inspect committed, staged, unstaged, and relevant untracked changes;
- review arbitrary file types and mixed technology stacks — no assumption
  about language, framework, or repository layout;
- classify findings as **P0** (critical/blocking), **P1**
  (significant/blocking), or **P2** (non-blocking improvement);
- publish inline GitHub review comments and a final review decision in
  active mode;
- run passive review loops against a local implementation, returning
  findings to the implementing Agent for it to fix;
- stop automatically after the configured maximum review-loop count
  (see [`review-config.yaml`](review-config.yaml), default `max_loops: 3`).

## What this Skill does not do

- It **suggests** fixes; it does not directly implement them. Fixing
  implementation code is the responsibility of the implementing Agent or
  developer.
- It never merges a Pull Request. Its maximum positive action on an
  external PR is **Approve**. Merge ownership stays with the developer or
  owning workflow.
- It never deletes branches, rewrites history, or performs repository
  lifecycle operations beyond reviewing.

## Prerequisites

```text
- Git
- GitHub CLI (`gh`)
- an authenticated GitHub CLI session, for remote PR operations
```

- **Local passive review** works from Git data alone and does not require
  `gh` or any remote GitHub mutation.
- **External active review** (publishing comments and a final decision)
  requires an authenticated `gh` session with actual review access to the
  target repository/PR — authentication alone is not sufficient (see
  [`policies/github-review.md`](policies/github-review.md)). If active
  review isn't possible, the Skill falls back to passive reporting rather
  than faking publication.
- `gh` credentials belong to the environment. The Skill never stores,
  embeds, or invents credentials.

Verify GitHub CLI authentication before requesting active review:

```bash
gh auth status
```

## How it integrates with GitHub

`gh` is the preferred integration mechanism. Final review decisions use
the equivalent of `gh pr review --approve` / `gh pr review
--request-changes`; line-specific inline comments may use `gh api`
against the GitHub Pull Request review APIs when needed. See
[`policies/github-review.md`](policies/github-review.md) for the full
contract.

## Review modes

- **passive local** — reviews a local branch/working tree, returns
  findings to the implementing Agent, never touches GitHub.
- **passive PR** — reviews an existing GitHub PR and returns a
  human-readable report without publishing anything.
- **active PR** — reviews an existing GitHub PR and publishes inline
  P0/P1/P2 findings, a final human-readable summary, and an
  Approve/Request Changes decision.

See [`SKILL.md`](SKILL.md) section 1 for the full entry-point table.

## Local review loop

Local review can run iteratively with an implementing Agent (review → fix
→ re-review) up to a configured maximum — default **3** iterations (see
[`review-config.yaml`](review-config.yaml) and
[`runbooks/review-loop.md`](runbooks/review-loop.md)). It stops
immediately once clean, and reports `REVIEW LOOP LIMIT REACHED` rather
than claiming success if blocking findings remain at the limit.

## External PR behavior

- inline findings are labeled `[P0]` / `[P1]` / `[P2]` and kept short
  (see [`templates/inline-finding.md`](templates/inline-finding.md));
- a final human-readable summary (what changed, what was done well, what
  needs improvement, decision) is always published after inline findings
  and before the final decision (see
  [`templates/external-review-summary.md`](templates/external-review-summary.md));
- the review ends in **Approve** or **Request Changes** — never a merge;
- the PR HEAD is revalidated immediately before the final decision so a
  stale review is never submitted.

## Runtime neutrality

This Skill is runtime-neutral. It is defined as a portable operational
specification (`SKILL.md` plus `policies/`, `runbooks/`, and
`templates/`), not as a Claude-specific subagent, a Codex-specific agent,
a Cursor-specific agent, or any other runtime-specific worker. Any
runtime capable of following these files and invoking `git`/`gh` can
execute it. See [`AGENTS.md`](AGENTS.md) for the full **Agent via Skill**
vocabulary and this repository's own development rules.

## Repository structure

```text
.
├── AGENTS.md              canonical repo-wide rules (this repo's own development)
├── CLAUDE.md               thin adapter → AGENTS.md / SKILL.md
├── README.md               this file
├── ARCHITECTURE.md         conceptual design and module boundaries
├── SKILL.md                concise operational entry point
├── review-config.yaml      local review-loop configuration (max_loops)
│
├── metadata/
│   └── skill.yaml          package identity/capabilities
│
├── policies/                stable review rules and invariants
├── runbooks/                 step-by-step execution procedures
├── templates/                 human-facing review output contracts
│
└── scripts/
    ├── package-skill.sh      packages the Skill (POSIX shell)
    └── package-skill.ps1     packages the Skill (PowerShell)
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for how these pieces fit
together.

## Packaging

The Skill can be packaged into a distributable archive containing only
what's needed to *consume* it (not this repository's own development
files):

```bash
./scripts/package-skill.sh
```

```powershell
./scripts/package-skill.ps1
```

Both scripts implement equivalent behavior: they validate required files
exist, stage an explicit allowlist (`SKILL.md`, `review-config.yaml`,
`metadata/`, `policies/`, `runbooks/`, `templates/`) into `dist/`, and
produce `dist/github-code-review-skill.zip`. `README.md`, `AGENTS.md`,
`ARCHITECTURE.md`, and `CLAUDE.md` are intentionally excluded — they are
this repository's own development/adapter documentation, not canonical
Skill behavior consumed at runtime. Neither script touches anything
outside `dist/`.

## Configuration

Local review-loop behavior is controlled by
[`review-config.yaml`](review-config.yaml):

```yaml
review:
  max_loops: 3
```

The Skill reads this value from configuration rather than hardcoding it;
raising or lowering `max_loops` changes how many automatic passive
review/fix iterations run before the Skill stops and reports remaining
findings.
