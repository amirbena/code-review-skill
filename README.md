# code-review-skill

A private, portable **Code Review Agent Skill** for GitHub repositories.

> **Status: foundation + first full implementation.** This repository now
> defines the complete Code Review Agent Skill. See [`SKILL.md`](SKILL.md)
> for the operational definition.

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

## How it integrates with GitHub

`gh` (the GitHub CLI) is the preferred integration mechanism. GitHub
authentication comes entirely from the environment — this Skill never
embeds or invents credentials. If `gh` is unavailable or unauthenticated,
the Skill reports the missing capability explicitly and, where possible,
still performs a purely local passive review using Git data alone.

## Runtime neutrality

This Skill is runtime-neutral. It is defined as a portable operational
specification ([`SKILL.md`](SKILL.md)), not as a Claude-specific subagent,
a Codex-specific agent, a Cursor-specific agent, or any other
runtime-specific worker. Any runtime capable of following `SKILL.md` and
invoking `git`/`gh` can execute it. See [`AGENTS.md`](AGENTS.md) for the
full **Agent via Skill** vocabulary and this repository's own development
rules.

## Documentation map

| File | Purpose |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Canonical, runtime-neutral rules for developing *this* repository (branching, PRs, merges). |
| [`CLAUDE.md`](CLAUDE.md) | Thin bootstrap adapter pointing Claude Code at `AGENTS.md` and `SKILL.md`. |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Conceptual architecture of the Code Review Agent Skill. |
| [`SKILL.md`](SKILL.md) | The canonical, portable operational definition of the Code Review Agent. |
| [`review-config.yaml`](review-config.yaml) | Minimal configuration contract (currently: `max_loops: 3`). |

## Configuration

Local review-loop behavior is controlled by
[`review-config.yaml`](review-config.yaml):

```yaml
review:
  max_loops: 3
```

The Skill reads this value conceptually rather than hardcoding it; raising
or lowering `max_loops` changes how many automatic passive review/fix
iterations run before the Skill stops and reports remaining findings.
