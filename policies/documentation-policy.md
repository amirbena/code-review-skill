# Documentation UX and Information Architecture Policy

Applies to this repository's human-facing documentation — the root
[`../README.md`](../README.md), [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md), and the other
explanatory pages under `../docs/`. It governs *structure and reading
experience*, not normative content, and never overrides the
policy-ownership model in
[`skill-development-policy.md`](skill-development-policy.md) or
[`python_scripts_coding_policy.md`](python_scripts_coding_policy.md).

This is a repository-development policy. It is **not** packaged into any
Skill archive, and no packaged Skill file may depend on it. See
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

**Thin README discipline.** README files are intentionally thin
orientation and navigation surfaces — never capability encyclopedias. The
reader drills down through layers:

```text
root README            → what this repo provides, which Skills exist, how to
                         choose, links onward
SKILL.md               → each Skill's contract (canonical, not explanatory)
docs/ARCHITECTURE.md   → the concise system map (components, lifecycle,
                         relationships, boundaries, invariants)
policies/              → canonical exact repository-development semantics
```

When adding or changing a capability, update the smallest appropriate
layer and link the others to it; do not copy the same detailed
explanation into several READMEs, and do not grow a README merely to make
a capability discoverable when a deeper surface exists or should exist.
READMEs and `docs/` are explanatory; a canonical policy or `SKILL.md`
wins any conflict.

**Per-document responsibility.**

- **README** answers: what is this, how do I install / use it, which Skill
  do I choose, where is the deeper documentation.
- **Architecture** establishes the high-level conceptual model (the Core and
  its mini-skills, who owns which rule, what is packaged vs. test-only)
  before low-level implementation detail. It is an overview that links to
  canonical detail, not a policy aggregation.

**Avoid normative duplication.** Documentation summarizes and links; it is
not a competing source of truth. Keep the ownership model intact: each `SKILL.md` and
its rule files are normative Skill behavior, and `docs/` plus the READMEs
are explanation, navigation, and mental models. Do not copy large
normative sections out of a Skill into a README or a `docs/` file —
reference them instead.

### Documentation impact for capability changes

A **capability** is a user-visible behavior of a Skill: what it reviews,
how it is selected, what it needs, what it refuses. Any change to a
capability that affects its user-visible behavior or its contract must
include a **documentation-impact check**: identify every documentation
surface the change makes stale, and update the **smallest** one that still
leaves the hierarchy correct. This is a governance rule for documentation
completeness, not a mechanical `code X changed → doc Y must change`
mapping.

Cases that trigger the check: a capability is **added or removed**;
**renamed**; its **selection or activation changes**; its **invocation or
enablement changes**; its **user-visible limitations or safety boundaries
change**; or its **canonical behavioral semantics change**.

Route each stale surface to the smallest layer that owns it:

| Surface | Update it when… |
|---|---|
| the Skill's `SKILL.md` or rule file | the exact behavioral semantics change |
| root [`../README.md`](../README.md) | repository-level orientation, Skill selection, or a high-level capability *category* materially changes |
| [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) | components, relationships, lifecycle/data flow, boundaries, invariants, or architectural ownership change |
| canonical policy | the repository-development semantics change |

Rules that bound the check:

- **Do not update a README merely because implementation code changed.**
  An internal change with no user-visible effect needs no README edit.
- **Prefer the smallest appropriate authoritative or user-facing layer**,
  and let higher layers link down to it rather than restating it — see
  "Thin README discipline" above.
- **A capability change is incomplete while a known-affected documentation
  surface is left stale.** The check is part of finishing the change, not
  a follow-up. When a known-affected surface cannot reasonably be updated
  in the same pull request — including the GitHub Wiki, which lives in a
  separate repository — the pull request description identifies the
  affected surface and the correction it needs.

**Wiki consideration.** When a capability change above lands, also consider
whether the repository Wiki describes documented behavior, commands, or
paths the change alters. A Wiki update need not be published before the
change is merged or released. This is a *consideration*, not a merge
blocker, and never applies to internal refactors with no user-visible
effect.

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
  [`../policies/`](../policies/README.md), [`../tests/`](../tests/README.md),
  [`../benchmark/`](../benchmark/README.md) and
  [`../runtime_platform/benchmark/`](../runtime_platform/benchmark/README.md).
- **Not automatically in scope**: leaf/implementation directories reached
  only by following a link to a specific file — e.g. `tests/unit/`,
  `tests/support/`, a Skill's `templates/` or `rules/` — unless one becomes
  a direct navigation surface in its own right.

**The README stays navigational, not normative.** It states purpose,
ownership, canonicality, and routing, and links to the files that hold
the rules. It must not restate a policy's logic, decision tables, or
rule blocks. If a README and a policy conflict, the policy wins. This is
not a rule that "every directory has a `README.md`" — it applies only to
genuine navigation surfaces.

When adding a new policy/guidance directory that people will browse
directly, add its README in the same change, and route to it from the
nearest existing entrypoint (`../AGENTS.md`, a parent README, or `docs/`).
