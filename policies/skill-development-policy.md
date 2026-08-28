# Skill Development Policy

Canonical rules for **developing and packaging the Skills in this
repository**: the portable-core / runtime-adapter split, the independence
of packaged Skills from this repository's own development instructions,
the layering between runtime adapters, `AGENTS.md`, `shared/`, and each
Skill, runbook design, and the shared review-context model.

This is a repository-development policy. It is **not** packaged into either
Skill archive, and no packaged Skill resource may depend on it. See
[`AGENTS.md`](../AGENTS.md) for global invariants, instruction precedence,
and task routing, and [`review-orchestration-policy.md`](review-orchestration-policy.md)
for review orchestration boundaries.

## Portable Core, Optional Runtime Adapters

The canonical Skill (`SKILL.md` plus its canonical package-relative
resources) **MUST** remain usable without runtime-specific metadata or
runtime-specific tool names. Runtime-specific adapter files **MAY** improve
discovery, presentation, configuration, or execution for one consumer, but
they **MUST NOT** redefine core semantics or become necessary for correctness.

External dependencies are expressed primarily as capabilities (for example,
authenticated GitHub access with sufficient review permissions), not as a
required vendor-specific implementation. A concrete integration or command
may appear as an optional example or fallback when it implements the same
capability contract.

Canonical repository behavior — `AGENTS.md`, this repository's `policies/`,
`shared/`, and each Skill's own `SKILL.md` — must not depend on:

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
(built by [`../scripts/package-skills.sh`](../scripts/package-skills.sh) /
[`../scripts/package-skills.ps1`](../scripts/package-skills.ps1)) never
contains `AGENTS.md`, this repository's `policies/`, `docs/ARCHITECTURE.md`,
or this repository's `README.md` — so no file that is part of a packaged
Skill (`SKILL.md`, a packaged policy, a runbook, a template, or
shared/-packaged resource) may use this repository's own `AGENTS.md` or its
`policies/` as a runtime dependency or canonical source required for
understanding or executing that Skill:

```text
AGENTS.md + policies/
→ repository development/orchestration rules

packaged Skill
→ SKILL.md
→ packaged policies
→ packaged runbooks
→ packaged templates/shared resources
```

Not:

```text
packaged Skill resource
→ ../../AGENTS.md
→ ../../policies/…
```

If a rule a packaged Skill relies on must remain available after
packaging, its canonical portable form belongs inside a packaged
resource, using the resource type that best fits the rule — prefer the
most specific one that avoids duplicating the same rule across multiple
files:

```text
normative reusable invariant  → policy (skills/<skill>/policies/ or shared/policies/)
operational procedure         → runbook
reusable output/content shape → template
Skill-level responsibility     → SKILL.md
```

When a repository-development instruction also needs to mention such a rule
for repository-development context, prefer pointing toward the packaged
canonical resource rather than the reverse:

```text
AGENTS.md / policies/ → references the packaged canonical policy/runbook/template/SKILL.md   (preferred)
packaged Skill → references AGENTS.md or policies/                                            (prohibited)
```

`AGENTS.md` and this repository's `policies/` may summarize a rule's
repository-development implications, but the portable Skill must remain
fully correct and self-explanatory with `AGENTS.md`, this repository's
`policies/`, `docs/ARCHITECTURE.md`, and this repository's `README.md`
deleted from the consumer's environment entirely.

This prohibition is narrowly about *this source repository's own*
development instructions. It does not extend to either Skill's own
behavior: both `local-code-review` and `github-pr-review` legitimately
discover and read an `AGENTS.md` (or `CLAUDE.md`) that belongs to the
*target* repository being reviewed — see
[`../shared/policies/repository-instructions.md`](../shared/policies/repository-instructions.md).
That target-repository instruction discovery is valid, packaged, portable
behavior and is unaffected by this rule.

## Relationship to Runtime Adapters and the Skills

```text
CLAUDE.md (or any other runtime adapter)
    ↓
AGENTS.md   (canonical, runtime-neutral: global invariants, precedence, routing)
    ↓
policies/   (repository-development policy domains routed from AGENTS.md)
    ↓
shared/     (review policies/templates common to both Skills)
    ↓
skills/local-code-review/SKILL.md
skills/github-pr-review/SKILL.md
```

Runtime adapters bootstrap a specific runtime into these canonical rules.
They must never duplicate or override them.

## Runbook Design

Applies to every runbook in either Skill (and any future one added under
`skills/`):

```text
Runbook       = flow, ordering, orchestration, and policy handoff points
Shared policy = reusable review semantics
Skill policy  = semantics unique to that Skill
Repository-state / Git policy = Git mechanics and state interpretation
```

A runbook tells the Skill runner **when** to invoke a rule and **which
policy governs it** — it does not re-document the rule itself. It must not
duplicate substantial policy semantics, decision tables, validation rules,
or state interpretation when a canonical policy already owns them; where a
runbook step names a policy, that policy's own text is authoritative, and
the runbook states only the ordering/handoff, not a second copy of the
rule. A small amount of local explanation is acceptable where needed to
make ordering or orchestration itself unambiguous — the target is a thin
runbook, not a vague one; it must remain fully executable end to end.

When new Skill behavior is introduced:

1. place reusable review semantics in the appropriate `shared/policies/`
   file;
2. place Skill-specific semantics in that Skill's own `policies/`;
3. update the runbook only enough to wire the new/changed policy into the
   normal execution path — when it runs, in what order, on what input;
4. avoid creating a second textual or executable source of truth for the
   same rule (in another runbook, another policy, or a hand-maintained
   script mirroring the policy's own decision logic).

See [`../skills/local-code-review/runbooks/local-review.md`](../skills/local-code-review/runbooks/local-review.md)
and [`../skills/local-code-review/policies/repository-state.md`](../skills/local-code-review/policies/repository-state.md)
for a worked example of this separation: Git category detection, push/sync
status, and the staged-fingerprint re-review contract live entirely in the
policy; the runbook states only when each is resolved and applied.

### Shared review-context model

The review-target / review-context / repository-context / existing-review-evidence
model and the requirement-context and Existing-Review-Evidence semantics are
reusable review semantics: they live in
[`../shared/policies/review-context.md`](../shared/policies/review-context.md) and
[`../shared/policies/review-evidence.md`](../shared/policies/review-evidence.md),
consumed by both Skills. Each Skill keeps only a thin policy naming its own
review target and prior-evidence source
(`skills/local-code-review/policies/review-context.md` and `pr-context.md`;
`skills/github-pr-review/policies/review-context.md` and `review-evidence.md`).
Do not re-document the shared semantics in a Skill's own policy.

## Python Authoring

Repository-owned Python — the developer scripts under `scripts/**/*.py` and
the test suite plus its test-only reference modules under `tests/**/*.py` —
must follow
[`python_scripts_coding_policy.md`](python_scripts_coding_policy.md):
comments and docstrings are concise (1–3 lines) and focused on non-obvious
intent — invariants, safety constraints, compatibility requirements,
external-system quirks, ordering, and surprising branches — while durable
architecture, packaging, and policy-ownership explanation lives in `docs/`,
`policies/`, or `shared/policies/`, not in module prose. That file is a
repository-development policy, not packaged into either Skill archive.
