# Documentation UX and Information Architecture Policy

Applies to this repository's human-facing documentation — the root
[`../README.md`](../README.md), [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md),
[`../docs/CODE_REVIEW_COMPARISON.md`](../docs/CODE_REVIEW_COMPARISON.md), the
user-facing feature guides under [`../docs/features/`](../docs/features/README.md),
and the Skill `README.md` files. It governs *structure and reading
experience*, not normative content, and never overrides the
policy-ownership model in
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

**Thin README discipline.** README files are intentionally thin
orientation and navigation surfaces — never capability encyclopedias. The
reader drills down through layers:

```text
root README            → what this repo provides, which Skills exist, the
                         distinction, high-level capability categories, links onward
Skill README           → that Skill's purpose, basic usage, a compact
                         capability/difference summary, key boundaries, links onward
docs/features/README.md → the capability catalog: which Skill(s) support each
                         optional/advanced feature and how it is activated
docs/features/<name>.md → one capability's user-facing explanation and invocation
docs/ARCHITECTURE.md    → the concise system map (components, lifecycle,
                         relationships, boundaries, invariants)
policies/ + runbooks    → canonical exact semantics and operational contracts
```

When adding or changing a capability, update the smallest appropriate
layer and link the others to it; do not copy the same detailed
explanation into several READMEs, and do not grow a README merely to make
a capability discoverable when a deeper surface exists or should exist.
READMEs and feature guides are explanatory; a canonical policy or runbook
wins any conflict.

**Per-document responsibility.**

- **README** answers: what is this, how do I install / use it, which Skill
  do I choose, where is the deeper documentation.
- **Architecture** establishes the high-level conceptual model (what is
  shared, what differs, the major layers, who owns policy / runbook /
  output, what is packaged vs. test-only) before low-level implementation
  detail. It is an overview that links to canonical detail, not a
  policy/runbook aggregation.
- **Feature guides** (`docs/features/`) explain a single optional or
  advanced capability from the user's point of view — what it does, when
  it helps, which Skill supports it, whether it is default / conditional /
  requested, how to invoke it, its user-visible limits, and a link to the
  canonical policy/runbook. They are guidance, not a second normative
  layer; the canonical policy always wins.
- **Comparison** exposes its primary comparison dimensions early, in a
  compact table when practical, with the detailed analysis kept below it.

**Avoid normative duplication.** Documentation summarizes and links; it is
not a competing source of truth. Keep the ownership model intact: shared
policies are normative shared behavior, Skill policies are target-specific
behavior, runbooks are procedures, and `docs/` plus the READMEs are
explanation, navigation, and mental models. Do not copy large normative
sections out of `shared/policies/` or a Skill's `policies/` into a README
or a `docs/` file — reference them instead.

### Documentation impact for capability changes

An **optional/advanced capability** is a user-visible feature of either
Skill — the kind catalogued in
[`../docs/features/README.md`](../docs/features/README.md). Any change to
such a capability that affects its user-visible behavior or its contract
must include a **documentation-impact check**: identify every
documentation surface the change makes stale, and update the **smallest**
one that still leaves the hierarchy correct. This is a governance rule for
documentation completeness, not a mechanical `code X changed → doc Y must
change` mapping.

Cases that trigger the check: a capability is **added or removed**;
**renamed**; its **Skill support changes** (one Skill gains or loses it);
its **default / conditional / explicitly-requested state changes**; its
**invocation or enablement changes**; its **user-visible limitations or
safety boundaries change**; or its **canonical behavioral / operational
semantics change**.

Route each stale surface to the smallest layer that owns it:

| Surface | Update it when… |
|---|---|
| [`../docs/features/README.md`](../docs/features/README.md) (the catalog) | the set of capabilities changes; a capability is renamed; Skill support changes; the default / conditional / requested state changes; the canonical link moves |
| `docs/features/<name>.md` | user-facing behavior, invocation, activation, usage, limitations, safety boundaries, or examples change |
| Skill `README.md` | day-one usage, the compact capability/difference summary, Skill-selection guidance, or an important Skill boundary changes |
| root [`../README.md`](../README.md) | repository-level orientation, Skill selection, or a high-level capability *category* materially changes |
| [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) | components, relationships, lifecycle/data flow, boundaries, invariants, or architectural ownership change |
| canonical policy / runbook | the exact behavioral or operational semantics change |

Rules that bound the check:

- **Do not update a README merely because implementation code changed.**
  An internal change with no user-visible effect needs no README or
  feature-guide edit.
- **Prefer the smallest appropriate authoritative or user-facing layer**,
  and let higher layers link down to it rather than restating it — see
  "Thin README discipline" above.
- **A capability change is incomplete while a known-affected documentation
  surface is left stale.** The check is part of finishing the change, not
  a follow-up.

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
  [`../shared/policies/`](../shared/policies/README.md),
  [`../tests/`](../tests/README.md), and
  [`../docs/features/`](../docs/features/README.md).
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
