# CLAUDE.md

This repository uses [`AGENTS.md`](AGENTS.md) as the canonical
repository-wide instruction entrypoint. `AGENTS.md` holds the global
invariants, instruction precedence, and a routing table into the focused
repository-development policies under [`policies/`](policies/).

Read and follow `AGENTS.md` first, then the `policies/` file it routes to
for your task, before performing any work.

When operating through one of this repository's Code Review Agent
Skills, also read that Skill's own `SKILL.md` and its applicable
policies, runbooks, templates, and metadata:

- [`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md)
- [`skills/github-pr-review/SKILL.md`](skills/github-pr-review/SKILL.md)

Both Skills also depend on [`shared/`](shared/) for common review rules.

Do not duplicate repository-wide rules or Skill-selection logic here.

```text
CLAUDE.md
    ↓
AGENTS.md
    ↓
applicable Skill
```
