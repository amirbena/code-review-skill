# Contribution Ownership & Issue Classification Policy

Canonical repository-development rules for **who is expected to own a
GitHub Issue** and **how an agent classifies contributor suitability**
when authoring or restructuring Issues for this repository.

This policy is **not packaged into either Skill archive**, and no packaged
Skill resource may depend on it. It governs backlog organization and
Issue authoring here; it does not change review semantics, the Issue Form
in [`../.github/ISSUE_TEMPLATE/engineering-task.yml`](../.github/ISSUE_TEMPLATE/engineering-task.yml),
or the human-facing contribution walkthrough in
[`../CONTRIBUTING.md`](../CONTRIBUTING.md). It never overrides the
authoring-shape rules in
[`github-issue-pr-authoring.md`](github-issue-pr-authoring.md) or the Git
mechanics in [`git-pr-merge-policy.md`](git-pr-merge-policy.md). See
[`../AGENTS.md`](../AGENTS.md) for global invariants and routing.

## Why this exists

The backlog serves three readers at once:

1. **Maintainer** — which capabilities require my semantic or
   architectural ownership?
2. **New contributor** — what can I safely take to learn the repository
   and build confidence?
3. **Experienced contributor** — which substantial capability can I claim
   and independently lead?

Classification makes that legible on the Issues page. It is backlog
governance, not a gate on who may open a pull request: anyone may still
claim any `help wanted` / `good first issue` per
[`../CONTRIBUTING.md`](../CONTRIBUTING.md).

## Classification is not about patch size

**Blast radius, coupling to review semantics, and validation difficulty
decide contributor suitability — never diff size alone.** A one-line
change to finding identity or severity derivation is maintainer-led. A
large but isolated fixture corpus can be a good first issue.

Weigh:

- **Blast radius** — how far a mistake propagates.
- **Coupling to review semantics** — does it touch finding
  identity/semantics, severity, evidence thresholds, deduplication,
  root-cause consolidation, the final review decision, re-review state,
  or publication/anchor semantics?
- **Architectural ownership** — is it a shared cross-Skill contract?
- **Privilege / security implications** — trusted release behavior,
  GitHub enforcement, autofix authorization, ruleset or required-check
  paths.
- **Difficulty of validating correctness** — can a contributor prove the
  result deterministically without reading the whole reviewer?
- **Independent design judgment** — how much architecture must the owner
  decide?
- **Risk of silently changing reviewer behavior** — could an imperfect
  implementation pass tests yet shift review outcomes?

## Contribution classes

The taxonomy is deliberately small and composable. It layers **on top of**
the existing Type / Area / Priority labels — it never overloads them.

| Class | Label(s) | Assignment |
| --- | --- | --- |
| Maintainer-led | `maintainer-led` | Assign `amirbena` when ownership is active; otherwise unassigned. |
| Good First Issue | `good first issue` (+ `help wanted`) | Normally unassigned. |
| Automation Good First Issue | `good first issue` + `type:infrastructure` (+ `help wanted`) | Normally unassigned. |
| Contributor-owned | `contributor-owned` (+ `help wanted`) | Normally unassigned unless someone already owns it. |

No dedicated `automation-good-first-issue` label exists: `good first
issue` composed with `type:infrastructure` (or an automation-flavored
`area:*`, e.g. `area:packaging-portability`) communicates the same thing
with less taxonomy. No ownership semantics are added to Type / Area /
Priority.

### A. Maintainer-led

Work whose **semantic or architectural ownership stays with the
repository maintainer**. Typical surfaces: finding semantics, finding
identity, severity, the final review decision, evidence thresholds,
deduplication, root-cause semantics, re-review state, publication/anchor
semantics, GitHub enforcement, autofix authorization boundaries,
privileged release behavior, and shared cross-Skill architectural
contracts.

Maintainer-led does **not** mean contributors cannot participate. A
maintainer-led Epic may expose safe child Issues (fixtures, corpora,
tooling, bounded components) that contributors implement while the parent
semantic contract stays maintainer-owned.

### B. Good First Issue

A bounded, low-blast-radius task appropriate for an early contribution.
The contributor should be able to understand the boundary without
learning the whole reviewer architecture, make progress independently,
validate the result deterministically, and produce an imperfect
implementation **without** silently changing review semantics.

Typical work: fixture corpora, regression examples, documentation,
bounded tests, isolated reference-model coverage, deterministic
contributor tooling. A small diff alone does **not** qualify an Issue —
sensitive review behavior is never beginner work.

### C. Automation Good First Issue

A first contribution for someone interested in repository automation,
DevOps, or tooling: validators, metadata checks, packaging/archive
integrity, reference/docs integrity, generated-file consistency,
deterministic maintenance scripts, CI diagnostics, benchmark/report
generation, repository-consistency checks, contributor preflight
commands.

These Issues must stay isolated from severity/decision semantics, finding
identity, publication semantics, privileged release mutation, and
enforcement-bypass behavior. They are represented by composition
(`good first issue` + `type:infrastructure`), not a dedicated label.

### D. Contributor-owned

Meaningful work an **experienced external contributor can independently
own and lead**. This is **not** another name for `good first issue`: a
Contributor-owned Issue may be large or technically difficult. What
matters is that it has a clear boundary, explicit invariants / acceptance
criteria, manageable integration points, and room for independent
architecture and design decisions. The Issue defines *what* and the
*invariants*; it deliberately does not prescribe every implementation
step. Examples: a specialist review profile, dependency/supply-chain
analysis, bounded observational telemetry, other isolated review
extensions.

## Epic decomposition

Parent and child Issues need not share a class. The preferred pattern:

```text
Maintainer-led Epic
    ├── Good First Issue: fixtures / regression corpus
    ├── Automation Good First Issue: validator / tooling
    ├── Contributor-owned: bounded implementation component
    └── Maintainer-led: semantic / integration contract
```

Every extracted child must deliver useful repository value
independently, have a clear completion boundary, be testable and
reviewable on its own, and not depend on unfinished speculative
architecture. Do **not** manufacture tiny child Issues solely to produce
`good first issue` labels.

## How an agent classifies a new or restructured Issue

1. Identify the surface the Issue touches and its blast radius using the
   criteria above — not the expected diff size.
2. If it touches any maintainer-led surface (review semantics, finding
   identity/lifecycle, severity, evidence bar, dedup/root-cause, final
   decision, re-review state, publication/anchors, GitHub enforcement,
   autofix authorization, privileged release, shared cross-Skill
   contracts), classify **Maintainer-led** — even when the change looks
   small. Assign `amirbena` when ownership is active.
3. Otherwise, if it is bounded, deterministically verifiable, and cannot
   silently move review outcomes, classify **Good First Issue**
   (compose with `type:infrastructure` when the work is automation /
   tooling). Leave it unassigned and add `help wanted`.
4. If it is a substantial capability with a clean boundary and explicit
   invariants but intentionally open design, classify **Contributor-owned**.
   Leave it unassigned and add `help wanted`.
5. When a large Epic is maintainer-led, look for safe child Issues to
   extract (fixtures, corpora, tooling, a bounded component) and keep the
   parent semantic/integration contract maintainer-owned.
6. Preserve existing Type / Area / Priority labels and legitimate
   existing assignments. Not every Issue needs an ownership class —
   ordinary work may stay unclassified.

## Ambiguous cases

- **Unsure between Maintainer-led and Good First Issue** → Maintainer-led.
  A wrong beginner label on sensitive behavior is more costly than a
  conservative one.
- **Unsure between Good First Issue and Contributor-owned** → if the
  expected behavior is already well defined and the contributor mainly
  implements an established contract, it is a Good First Issue; if the
  contributor must investigate the repository and propose the approach,
  it is Contributor-owned.
- **A `good first issue` that has since grown, gained architectural
  decisions, or now touches review semantics** → remove the label and
  reclassify. A label is not preserved merely because it has
  historically been present.
- **Genuinely ordinary Issue** → leave it unclassified. Do not force a
  class.

## Relationship to `CONTRIBUTING.md`

This policy is canonical. [`../CONTRIBUTING.md`](../CONTRIBUTING.md) is the
human-facing explanation of the same model for someone discovering the
repository on GitHub — it explains how to choose between a Good First
Issue and Contributor-owned work and how claiming works, and it must not
restate these rules in a way that can drift. On any conflict, this policy
wins.
