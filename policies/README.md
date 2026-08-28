# Repository Policies

These policies govern **development and maintenance of `code-review-skill`
itself** — branching, commits, PRs, merges, validation, packaging,
documentation, and how the two review Skills are orchestrated. They are
explanatory/navigational targets of the routing table in
[`../AGENTS.md`](../AGENTS.md); the normative rules live in the individual
policy files, not in this README.

## Start here

[`../AGENTS.md`](../AGENTS.md) is the repository-wide entrypoint. Read it
first for the global invariants and instruction precedence, then follow
its **Task routing** table to the one policy below that owns your task.

## Policy map

| Policy | Purpose (short) |
| --- | --- |
| [`repository-workflow.md`](repository-workflow.md) | Task branches: creation off synchronized `main`, base synchronization, dirty-tree / stash discipline, branch naming, resuming a task branch, the canonical Git lifecycle. |
| [`git-pr-merge-policy.md`](git-pr-merge-policy.md) | Commit, push, PR creation and assignment, squash-merge strategy, merge safety, post-squash branch cleanup, and the destructive-Git prohibitions for developing this repository. |
| [`validation-and-clean-exit.md`](validation-and-clean-exit.md) | Required clean end state for a task, Python cache/bytecode cleanup around commits, running repository validation and packaging, and the shell/PowerShell script-parity obligation. |
| [`documentation-policy.md`](documentation-policy.md) | Structure and reading experience of this repository's human-facing docs (`README.md`, `docs/`, Skill `README.md`) — user-journey ordering, progressive disclosure, no normative duplication, and the navigational-README requirement for directories people browse directly. |
| [`skill-development-policy.md`](skill-development-policy.md) | Developing and packaging the Skills: the portable-core / runtime-adapter split, independence of packaged Skills from repository-level instructions, adapter/`AGENTS.md`/`shared/`/Skill layering, runbook design, the shared review-context model, and Python-authoring routing. |
| [`review-orchestration-policy.md`](review-orchestration-policy.md) | Orchestrating the review Skills around this repository: the orchestration boundary, Skill-consumer branch discipline, review ownership, implementer/reviewer separation, the `local-code-review` approval gate, and human-facing review publication. Each runtime-relevant rule routes to a packaged canonical under `shared/` or `skills/`. |
| [`python_scripts_coding_policy.md`](python_scripts_coding_policy.md) | Authoring policy for this repository's own Python (`scripts/**/*.py`, `tests/**/*.py`): concise, intent-focused comments and docstrings. |

## Repository policy vs. Skill runtime policy

This distinction is deliberate and must stay explicit.

- **Repository-development instructions** — `../AGENTS.md`, `../CLAUDE.md`,
  and everything in this directory. They govern how *this source
  repository* is built, reviewed, packaged, and documented. They are
  **never shipped**: no packaged Skill archive contains them, and no
  packaged Skill resource may depend on them.
- **Runtime-portable Skill policy** — [`../shared/policies/`](../shared/policies/),
  [`../shared/templates/`](../shared/templates/),
  [`../skills/local-code-review/`](../skills/local-code-review/), and
  [`../skills/github-pr-review/`](../skills/github-pr-review/). Any rule a
  packaged Skill needs while it runs **outside** this repository lives
  here, in its portable canonical form, and is included in the Skill's
  package allowlist.

If a Skill needs a rule at runtime, that rule's canonical home is under
`shared/` or `skills/` — not a file in this directory. Adding a
`policies/*.md` file to a package allowlist is the wrong fix and is not
permitted.

## Ownership rule

One canonical home per normative rule. `../AGENTS.md` keeps only a short
invariant plus a routing link; the routed policy owns the detailed rule.
Do not create a second normative copy of a rule in `../AGENTS.md`, in
another policy, in `docs/`, or in a README.

## Adding or changing a policy

1. If the rule applies to **every** repository task and is short, state it
   as an invariant in `../AGENTS.md` and stop.
2. If it is a substantial, independently ownable domain, add or extend a
   focused file here and add a row to the `../AGENTS.md` **Task routing**
   table. Prefer a small number of meaningful domains over many tiny
   files.
3. If the rule is needed by a packaged Skill at runtime, put its portable
   canonical form under `../shared/` or the relevant `../skills/<skill>/`
   directory and reference it from that Skill's `SKILL.md`/runbook —
   never here.
4. Keep cross-references as relative Markdown links and run link
   validation (`python3 -m unittest discover -s tests -t .`).
