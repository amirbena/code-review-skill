# CLAUDE.md

This repository uses [`AGENTS.md`](AGENTS.md) as the canonical
repository-wide instruction entrypoint. `AGENTS.md` holds the global
invariants, instruction precedence, and a routing table into the focused
repository-development policies under [`policies/`](policies/).

Read and follow `AGENTS.md` first, then the `policies/` file it routes to
for your task, before performing any work.

When operating through one of this repository's Code Review Agent
Skills, also read that Skill's own `SKILL.md` and its applicable
rules and templates:

- [`skills/review-core/SKILL.md`](skills/review-core/SKILL.md)
- the `skills/review-*/SKILL.md` mini-skill the task selects

Do not duplicate repository-wide rules or Skill-selection logic here.

```text
CLAUDE.md
    ↓
AGENTS.md
    ↓
applicable Skill
```
