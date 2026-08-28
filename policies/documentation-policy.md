# Documentation UX and Information Architecture Policy

Applies to this repository's human-facing documentation — the root
[`../README.md`](../README.md), [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md),
[`../docs/CODE_REVIEW_COMPARISON.md`](../docs/CODE_REVIEW_COMPARISON.md), and the
Skill `README.md` files. It governs *structure and reading experience*, not
normative content, and never overrides the policy-ownership model in
[`skill-development-policy.md`](skill-development-policy.md) or
[`python_scripts_coding_policy.md`](python_scripts_coding_policy.md).

This is a repository-development policy. It is **not** packaged into either
Skill archive, and no packaged Skill resource may depend on it. See
[`AGENTS.md`](../AGENTS.md) for global invariants, instruction precedence,
and task routing.

**User journey first.** Entry-point documentation (the root README above
all) orders itself around what a first-time reader needs, in this order:
what the project is → how to install / package it → how to start using it →
which Skill to choose → what to know → deeper architecture and contributor
internals last. A new user must be able to install and choose a Skill
before encountering packaging internals, test architecture, or governance
detail.

**Progressive disclosure.** Prefer the shape
`summary → action / decision → conceptual model → detailed reference`. A
reader should be able to stop as soon as they have enough for their task.
Lead sections with a short orienting summary; put the compact decision aid
(for example, a "which Skill / which mode" table) before the exhaustive
one.

**Human scanability over arbitrary length.** Do **not** optimize
documentation for line-count targets, artificially short files, or wrapping
limits as a proxy for quality — long files are fine when their structure is
clear. Optimize for mental-model clarity, scanability, navigation, section
boundaries, and low cognitive load: short introductory summaries, tables
for ownership / comparison, diagrams for flows, bullets for invariants, and
one idea per paragraph. Preserve valuable technical detail — move it later
or link to it; do not delete it for brevity.

**Per-document responsibility.**

- **README** answers: what is this, how do I install / use it, which Skill
  do I choose, where is the deeper documentation.
- **Architecture** establishes the high-level conceptual model (what is
  shared, what differs, the major layers, who owns policy / runbook /
  output, what is packaged vs. test-only) before low-level implementation
  detail.
- **Comparison** exposes its primary comparison dimensions early, in a
  compact table when practical, with the detailed analysis kept below it.

**Avoid normative duplication.** Documentation summarizes and links; it is
not a competing source of truth. Keep the ownership model intact: shared
policies are normative shared behavior, Skill policies are target-specific
behavior, runbooks are procedures, and `docs/` plus the READMEs are
explanation, navigation, and mental models. Do not copy large normative
sections out of `shared/policies/` or a Skill's `policies/` into a README
or a `docs/` file — reference them instead.

## Navigational README for user-facing policy/guidance directories

A repository directory that exposes **policies, contracts, instructions,
or other guidance meant for direct human, maintainer, or coding-agent
navigation** must provide a concise README (or equivalent single
entrypoint) — *unless* the directory is already self-explanatory from one
obvious canonical file inside it.

**"User-facing" here** means a person or agent is expected to open or
list the directory itself to learn what policies/contracts/workflows/
guidance it holds and which file owns which concern — not merely that a
tool reads the files. Judge by how the directory is actually navigated,
not by whether it contains `.md` files.

- **In scope** (each must have a README entrypoint): the repository-root
  [`../policies/`](../policies/README.md),
  [`../shared/policies/`](../shared/policies/README.md), and
  [`../tests/`](../tests/README.md).
- **Not automatically in scope**: leaf/implementation directories reached
  only by following a link to a specific file — e.g. `tests/unit/`,
  `tests/reference/`, `tests/support/`, a Skill's `templates/` or
  `runbooks/` — unless one becomes a direct navigation surface in its own
  right.

**The README stays navigational, not normative.** It states purpose,
ownership, canonicality, and routing, and links to the files that hold
the rules. It must not restate a policy's logic, decision tables, or
rule blocks. If a README and a policy conflict, the policy wins. This is
not a rule that "every directory has a `README.md`" — it applies only to
genuine navigation surfaces.

When adding a new policy/guidance directory that people will browse
directly, add its README in the same change, and route to it from the
nearest existing entrypoint (`../AGENTS.md`, a parent README, or `docs/`).
