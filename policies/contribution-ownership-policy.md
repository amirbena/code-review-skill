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
| Automation Good First Issue | `good first issue` on an Issue whose Type is Infrastructure (+ `help wanted`) | Normally unassigned. |
| Contributor-owned | `contributor-owned` (+ `help wanted`) | Normally unassigned unless someone already owns it. |

No dedicated `automation-good-first-issue` label exists: `good first
issue` on an Infrastructure-typed Issue (or one in an automation-flavored
`area:*`, e.g. `area:packaging-portability`) communicates the same thing
with less taxonomy. The `type:` / `area:` / `priority:` labels are
derived from the Issue Form and reconciled on every edit by
[`../scripts/governance/sync_issue_labels.py`](../scripts/governance/sync_issue_labels.py), so
the Infrastructure signal must come from the form's **Type** field — a
hand-added `type:infrastructure` label on a differently-typed Issue is
reverted. No ownership semantics are added to Type / Area / Priority.

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
semantic contract stays maintainer-owned. The same principle applies to
an individual bounded child Issue, not only to an Epic as a whole — see
the exception immediately below.

#### Touching a shared/cross-Skill contract without redefining it

**Defining or altering shared/cross-Skill semantics is always
Maintainer-led** and has no exception. But *merely touching* a
shared/cross-Skill contract — without authority to redefine its semantics
— does not by itself require Maintainer-led implementation. A narrow
exception lets such an Issue classify as **Contributor-owned** instead,
when it is explicitly bounded to *implementing, exposing, adapting,
wiring, or validating* semantics that are already canonical, and **all**
of the following hold:

1. The canonical semantic owner — the existing source of truth the Issue
   implements against — is explicitly identifiable.
2. The Issue does not grant authority to redefine that semantic contract.
3. The remaining implementation choices are ordinary engineering choices,
   not product or architecture decisions.
4. The Issue's acceptance criteria give deterministic conformance
   evidence against the canonical contract.
5. Maintainer / CODEOWNERS review remains required before merge.

If any semantic, compatibility, security, or governance decision the
Issue depends on is still unresolved, the Issue stays Maintainer-led no
matter how bounded the remaining implementation looks — implementation
that would itself have to settle an undecided contract is never eligible
for this exception. This keeps compatibility/evolution policy,
similarity/normativity or other undecided semantic thresholds, and
architectural or governance-mechanism research Maintainer-led until a
maintainer records the missing decision.

This exception never creates a new class or label, and it never moves
merge or review authority: it only changes which of the two existing
classes (`Maintainer-led` vs `Contributor-owned`) an Issue that touches a
shared/cross-Skill contract receives.

```text
maintainer-owned canonical contract
        ↓
bounded Issue that cannot redefine it
        ↓
contributor-owned implementation
        ↓
maintainer/CODEOWNERS review
```

This is not delegation of architectural ownership — the maintainer
retains semantic ownership of the contract and merge/review authority
either way. Once a maintainer records a previously-missing semantic
decision, a remaining bounded implementation Issue may become eligible
under this exception if it independently satisfies criteria 1–5.

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
enforcement-bypass behavior. They are represented by composition —
`good first issue` on an Infrastructure-typed Issue (or one in an
automation-flavored `area:*`) — not a dedicated label.

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

A bounded implementation of an already-canonical shared/cross-Skill
contract (the exception under "Touching a shared/cross-Skill contract
without redefining it" above) is also Contributor-owned even though it
leaves little open design: the contributor owns driving the
implementation, tests, and documentation through review, while the
*semantic* authority stays with the maintainer who owns the canonical
contract.

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
   small. Assign `amirbena` when ownership is active. Exception: if the
   *only* maintainer-led surface touched is a shared/cross-Skill
   contract, and the Issue satisfies all five criteria under "Touching a
   shared/cross-Skill contract without redefining it" above, classify
   **Contributor-owned** instead. Every other maintainer-led surface
   listed here has no such exception and always classifies
   Maintainer-led.
3. Otherwise, if it is bounded, deterministically verifiable, and cannot
   silently move review outcomes, classify **Good First Issue**. For
   automation / tooling work, set the Issue's **Type** to Infrastructure
   so the label automation applies `type:infrastructure`. Leave it
   unassigned and add `help wanted`.
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
- **An Issue touches a shared/cross-Skill contract and it is unclear
  whether all five shared-contract exception criteria hold** →
  Maintainer-led. The exception requires every criterion; an Issue that
  meets some but leaves one genuinely unresolved is not eligible.
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
