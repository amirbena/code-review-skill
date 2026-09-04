# Runtime Parallelism Notes

Repository development doc. It isolates the *product-specific* facts behind
the portable parallel-review contract so a product change updates this file
only, not the packaged policies.

- Portable contract: [`../shared/policies/parallel-review.md`](../shared/policies/parallel-review.md)
- PR application + capability table:
  [`../skills/github-pr-review/policies/parallel-review.md`](../skills/github-pr-review/policies/parallel-review.md)
- User-facing usage guide: [`features/parallel-review.md`](features/parallel-review.md)

This file is **not** packaged into either Skill archive.

## Capability model

The Skill detects one of: `none`, ordinary isolated sub-agents, an
experimental agent-team mechanism (usable only when its prerequisite is
already set), or native concurrent agents. Uncertain → `none` → sequential.
The Skill never mutates the user's shell, global settings, or runtime
configuration to obtain a capability.

## Per-runtime facts (last verified 2026-08)

### Claude Code

Agent Teams (a parent coordinating parallel sub-agents) are **experimental
and disabled by default**. They are enabled via the environment / settings
value `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`. The Skill detects whether
Agent Teams are already available; it does not set the variable. When Agent
Teams are unavailable it uses ordinary Task/sub-agent calls if the runtime
offers them, otherwise sequential review. A review is never failed because
Agent Teams are off.

Source: Claude Code docs — https://docs.anthropic.com/en/docs/claude-code/costs

### Cursor

Cursor supports **subagents with isolated context windows that run in
parallel**. Project subagents can be defined under `.cursor/agents/`; Cursor
also recognises `.claude/agents/` and `.codex/agents/` for compatibility and
applies its own precedence between them. The parent reviewer delegates
independent analysis dimensions concurrently when the capability is enabled;
otherwise sequential.

Source: Cursor docs — https://prod.cursor.com/docs/subagents

### Codex

Codex supports **multiple agents working concurrently**, with **isolated
worktrees available for parallel work**. Codex realises the same logical
review plan via its native agent/task capability. Codex worktrees are an
execution-isolation concern and are **not** responsible for the GitHub PR
checkout lifecycle (see `repository-checkout.md`) — the two are separate.

Source: OpenAI — https://openai.com/index/introducing-the-codex-app/

## Agent definition files — decision

No `.cursor/agents/`, `.claude/agents/`, or `.codex/agents/` directory is
added in this phase. The worker contract is fully specified by the packaged
`shared/policies/parallel-review.md`; adding near-duplicate prompt files for
three runtimes is the duplication the contract is meant to avoid, and such
files would not travel with the packaged Skill to a consumer anyway. If a
future need is demonstrated, prefer a single set under `.claude/agents/`
(which Cursor also reads) of thin adapters that point at the shared policy,
not three copies of the review instructions.
