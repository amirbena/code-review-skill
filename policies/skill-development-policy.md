# Skill Development Policy

Canonical rules for **developing and packaging the Skills in this
repository**: the portable-core / runtime-adapter split, the independence
of packaged Skills from this repository's own development instructions, the
layering between runtime adapters, `AGENTS.md` and the Skills, and how a
Skill is authored.

This is a repository-development policy. It is **not** packaged into any
Skill archive, and no packaged Skill file may depend on it. See
[`AGENTS.md`](../AGENTS.md) for global invariants, instruction precedence,
and task routing, and [`review-orchestration-policy.md`](review-orchestration-policy.md)
for review orchestration boundaries. The v3 decision record is
[`docs/v3-architecture/`](../docs/v3-architecture/README.md).

## Portable Core, Optional Runtime Adapters

The canonical Skill (`SKILL.md` plus the package-relative files it lists)
**MUST** remain usable without runtime-specific metadata or runtime-specific
tool names. Runtime-specific adapter files **MAY** improve discovery,
presentation, configuration, or execution for one consumer, but they **MUST
NOT** redefine core semantics or become necessary for correctness.

External dependencies are expressed primarily as capabilities (for example,
authenticated GitHub access with sufficient review permissions), not as a
required vendor-specific implementation. A concrete integration or command
may appear as an optional example or fallback when it implements the same
capability contract.

Canonical repository behavior — `AGENTS.md`, this repository's `policies/`,
and each Skill's own files — must not depend on:

- Claude-specific tools or conventions
- Anthropic APIs
- Codex-specific behavior
- Cursor-specific behavior
- any runtime-specific subagent orchestration syntax

Runtime adapters may exist separately (e.g. `CLAUDE.md`) but must never
duplicate or fork these canonical rules.

## Packaged Skills Are Independent of Repository-Level Development Instructions

`AGENTS.md` and this repository's `policies/` govern development and
orchestration of *this* source repository. A distributed Skill archive
(built by [`../scripts/packaging/package-skills.sh`](../scripts/packaging/package-skills.sh) /
[`../scripts/packaging/package-skills.ps1`](../scripts/packaging/package-skills.ps1))
never contains `AGENTS.md`, this repository's `policies/`,
`docs/ARCHITECTURE.md`, or this repository's `README.md` — so no file that
is part of a packaged Skill (`SKILL.md`, a rule file, a template, a
checklist) may use this repository's own `AGENTS.md` or its `policies/` as a
runtime dependency or canonical source required for understanding or
executing that Skill:

```text
AGENTS.md + policies/
→ repository development/orchestration rules

packaged Skill
→ SKILL.md
→ its rules/, templates/ and checklist files
```

Not:

```text
packaged Skill file
→ ../../AGENTS.md
→ ../../policies/…
```

If a rule a packaged Skill relies on must remain available after packaging,
its canonical portable form belongs inside that Skill's own files, in the
most specific place that avoids duplicating the rule:

```text
Skill-level responsibility, entry contract, procedure → SKILL.md
normative reusable rule                               → rules/<topic>.md
output shape                                          → templates/
domain checklist                                      → checklist.md
```

When a repository-development instruction needs to mention such a rule, it
points at the packaged canonical file, never the reverse. The portable Skill
must remain fully correct with `AGENTS.md`, this repository's `policies/`,
`docs/` and `README.md` deleted from the consumer's environment entirely.

This prohibition is narrowly about *this source repository's own*
development instructions. It does not extend to a Skill's behavior:
`review-core` legitimately discovers and reads an `AGENTS.md` (or
`CLAUDE.md`) that belongs to the *target* repository being reviewed, as
conventions only (S5). That is valid, packaged, portable behavior and is
unaffected by this rule.

## Relationship to Runtime Adapters and the Skills

```text
CLAUDE.md (or any other runtime adapter)
    ↓
AGENTS.md   (canonical, runtime-neutral: global invariants, precedence, routing)
    ↓
policies/   (repository-development policy domains routed from AGENTS.md)
    ↓
skills/review-core/SKILL.md      (the Core)
skills/review-*/SKILL.md         (mini-skills)
```

Runtime adapters bootstrap a specific runtime into these canonical rules.
They must never duplicate or override them.

## Authoring and Maintaining Skills

Applies to every Skill under `skills/`. It guides contributors and coding
agents developing this repository; it is a development policy only, is never
packaged, and adds no review rule.

- **One owner per rule.** Every rule has one canonical owner: the Core for
  severity, evidence, the verdict rule and the shared safety guarantees
  (S1–S5, S10); the owning mini-skill for its capability (ADR §7). Other
  files reference the owner by Skill name and never restate or weaken it.
  A mini-skill references the Core contract by Skill name, not by a
  relative path into another Skill's folder.
- **The Skill is read in full.** A Skill is its `SKILL.md`, which holds the
  entry contract and the inline procedure, plus the few rule and template
  files `SKILL.md` lists and reads in full. There is no loading inventory,
  conditional loading, activation predicate, checkpoint or runbook layer. A
  procedure lives in `SKILL.md`, not in a separate flow document.
- **Activation by the ADR §5.1 modes.** A mini-skill's frontmatter
  `description` is the whole selection surface: it says what the Skill adds
  and when it helps. The Core selects mini-skills by the meaning of the
  user's request (`intent`, the default) or, when the user opts in, by
  evidence (`auto`). `auto` never adds publication or execution; untrusted
  content never selects a Skill; a mode, selection or approval never
  carries over to another run.
- **Missing input is never clean.** A mini-skill that cannot obtain its
  required input ends the run `REVIEW INCOMPLETE` under Core trigger 4; it
  never degrades to a clean result.
- **Simplify before adding.** Prefer tightening, consolidating, or removing
  existing text over adding a rule file, checkpoint, or layer.
- **Proportionate instructions.** Avoid exhaustive procedures and
  speculative investigations. Keep text concise without sacrificing
  correctness, safety, or clarity.
- **Frontmatter.** `name` equals the folder name and `description` is one
  line; `scripts/validation/validate-skill-metadata.py` checks both. The
  `version` line is stamped by the release run, never edited by hand (ADR
  §11).
- **No size limits.** Do not set line-count or file-size limits; file size
  stays a review trigger per `AGENTS.md`, never a rule.

## Python Authoring

Repository-owned Python — the developer scripts under `scripts/**/*.py` and
the test suite under `tests/**/*.py` — must follow
[`python_scripts_coding_policy.md`](python_scripts_coding_policy.md):
comments and docstrings are concise (1–3 lines) and focused on non-obvious
intent, while durable architecture, packaging, and policy-ownership
explanation lives in `docs/` or `policies/`, not in module prose. That file
is a repository-development policy, not packaged into any Skill archive.
