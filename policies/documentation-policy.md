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
