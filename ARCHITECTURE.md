# ARCHITECTURE.md

This document describes the conceptual architecture of this repository's
two Code Review Agent Skills. It is intentionally decoupled from any
specific runtime implementation — see [`AGENTS.md`](AGENTS.md) section 2
("Runtime Neutrality") and the **Agent via Skill** vocabulary in section
1.

## 1. Module Map

```text
                 shared/
            review policies
                  │
         ┌────────┴────────┐
         │                 │
local-code-review    github-pr-review
         │                 │
 local report        GitHub delivery
```

```text
AGENTS.md
    ↓
repository rules (development of *this* repository)

shared/policies/
    ↓
review-scope, severity, evidence, repository-instructions, git-safety,
review-ownership — one copy each, consumed by both Skills (and packaged
with either, so each archive is self-contained)

shared/templates/finding.md
    ↓
one canonical finding shape, rendered differently per delivery surface

skills/local-code-review/
    ↓
SKILL.md (stateless, bounded) + its own runbook/template/metadata

skills/github-pr-review/
    ↓
SKILL.md + its own GitHub-specific policy/runbooks/templates/metadata
```

Neither Skill owns a copy of the severity model, evidence requirements,
or review-scope rules — both reference [`shared/policies/`](shared/policies/)
directly. `github-pr-review` additionally has its own
[`policies/github-review.md`](skills/github-pr-review/policies/github-review.md)
for GitHub-specific delivery rules (PR HEAD authority, access
verification, submission ordering) that have no local-review analogue.
`local-code-review` has no analogous per-Skill policy file — its only
Skill-specific rules are the local-delta procedure in its own runbook.

## 2. Core Pipeline (per Skill)

```text
Input
    ↓
Review Context Resolver
    ↓
Git / GitHub State Inspector
    ↓
Review Delta Resolver
    ↓
Repository Context Loader
    ↓
Core Code Review Engine  (shared/policies/)
    ↓
Finding Classification   (shared/policies/severity.md)
    ↓
Delivery Mode
    ├── local-code-review  → structured report (always)
    └── github-pr-review   → Passive Report | Active GitHub Review
```

### Stage responsibilities

- **Input** — for `local-code-review`: "review this local repository." For
  `github-pr-review`: a PR URL, a PR number with repository context, or a
  repository + PR number.
- **Review Context Resolver** — resolves the repository, base branch, and
  (for `github-pr-review`) the PR itself.
- **Git / GitHub State Inspector** — read-only inspection of Git state
  (branch, HEAD, staged/unstaged/untracked) and, for `github-pr-review`,
  GitHub state (PR metadata, base/head SHA, checks, existing comments).
  Never mutates state.
- **Review Delta Resolver** — computes exactly what must be reviewed: the
  committed delta relative to base, plus any local-only commits, staged
  changes, unstaged changes, and relevant untracked files.
- **Repository Context Loader** — loads relevant surrounding context
  beyond the raw diff: repository-local instructions, architecture docs,
  related tests, contracts, schemas, and conventions.
- **Core Code Review Engine** — the single review reasoning model defined
  by `shared/policies/review-scope.md`. Identical regardless of which
  Skill or delivery mode invokes it.
- **Finding Classification** — every actionable finding is assigned
  exactly one severity: P0, P1, or P2, per
  [`shared/policies/severity.md`](shared/policies/severity.md).
- **Delivery Mode** — `local-code-review` always returns a structured
  report. `github-pr-review` either returns a report (passive) or
  publishes to GitHub (active). The delivery adapter never changes the
  underlying findings or severities.

## 3. Separation of Concerns

| Concern | Owned by |
|---|---|
| Review reasoning (what's wrong, why, severity) | shared/policies/, consumed identically by both Skills |
| Local Git state inspection | `local-code-review` |
| GitHub state inspection + delivery (comments, Approve/Request Changes) | `github-pr-review` |
| Orchestration (which Skill runs when, loop control, fix application) | The calling workflow / Team Lead — **never** either Skill |
| Implementation ownership (writing/fixing code) | The implementing Agent or developer — **never** either Skill |

## 4. Orchestration Boundary

Neither Skill owns orchestration. The runtime, Team Lead, or implementing
Agent is responsible for:

- deciding when to invoke `local-code-review`;
- deciding whether to invoke it again, and how many times;
- applying fixes based on returned findings;
- committing and pushing;
- deciding when to open/update a PR;
- deciding when to invoke `github-pr-review`, and in which mode.

```text
Orchestrator
    ↓
chooses Skill
    ↓
Skill reviews once
    ↓
returns result
```

The orchestrator owns repetition; the Skill does not remember previous
invocations. This is why `local-code-review` ships with no
`review-config.yaml` or `max_loops` setting — loop limits are an
orchestration-level configuration concern, outside either Skill's
package. A separate orchestration layer may default to something like 3
iterations, but that default lives outside these Skills.

## 5. Handoff Between Skills

```text
Implementation Agent
    ↓
Local Code Review Skill
    ↓
findings
    ↓
Implementation Agent fixes
    ↓
optional Local Code Review Skill re-run
    ↓
local implementation accepted by orchestrator
    ↓
push / open PR
    ↓
GitHub PR Review Skill
```

`local-code-review` does not automatically invoke `github-pr-review`.
`github-pr-review` does not assume `local-code-review` was previously
run — it reviews the PR's actual current state regardless of history.
They are independently invokable, and each may be used without the
other.

## 6. External PR Workflow (`github-pr-review`)

```text
External GitHub PR
    ↓
Inspect authoritative PR HEAD
    ↓
Review
    ↓
Inline findings
    ↓
P0 / P1 / P2
    ↓
Approve or Request Changes
    ↓
Stop
```

Maximum automated positive action: **Approve**. No merge occurs — the
repository owner or their merge workflow performs the merge separately,
following `AGENTS.md`'s merge-strategy rules when this repository's own
PRs are the ones being merged. See
[`skills/github-pr-review/runbooks/active-pr-review.md`](skills/github-pr-review/runbooks/active-pr-review.md).

## 7. Packaging: Source Layout vs. Distribution Layout

Source layout and distribution layout are intentionally different:

```text
source repository layout            standalone Skill archive
(skills/<name>/, shared/)                (dist/*.zip)
    ↓                                        ↓
skills/<name>/SKILL.md              →   SKILL.md            (archive root)
skills/<name>/runbooks/…            →   runbooks/…
skills/<name>/templates/…           →   templates/…
skills/<name>/policies/…            →   policies/…
skills/<name>/metadata/…            →   metadata/…
shared/policies/…, shared/templates/…  →  shared/policies/…, shared/templates/…
```

`scripts/package-skills.sh` / `scripts/package-skills.ps1` assemble this
distribution layout by staging each Skill's files under `dist/.staging/`,
dropping the `skills/<name>/` source prefix so `SKILL.md` lands at the
archive root, then zipping the staged tree's *contents* (not the staging
folder itself) into `dist/*.zip`. Staging is removed after a successful
build, so normal output is just the two zips under `dist/`.

Because `SKILL.md` moves from `skills/<name>/SKILL.md` (source depth 2)
to the archive root (depth 0), its relative links into `shared/` change
from `../../shared/...` to `shared/...`; nested files one level under the
Skill (`runbooks/`, `templates/`, `policies/`, source depth 3) change
from `../../../shared/...` to `../shared/...`. The packaging scripts
apply this as a narrow, deterministic text substitution across the
staged Markdown files — scoped to exactly those two link prefixes — after
copying and before archiving. Skill-internal links (`../SKILL.md`,
`runbooks/...`, etc.) are untouched, since a Skill's own internal
relative depth is unchanged by removing the shared `skills/<name>/`
wrapper. The canonical source files in `skills/<name>/` remain the single
source of truth; only the staged copies are rewritten.

## 8. Reasoning vs. Delivery vs. Ownership

- **Review reasoning** is Skill-agnostic and delivery-mode-agnostic: the
  same shared policies and severity model apply in `local-code-review`
  and in both modes of `github-pr-review`.
- **Git/GitHub state inspection** is read-only and never assumes GitHub
  is authoritative when local state diverges from it — see
  [`skills/local-code-review/runbooks/local-review.md`](skills/local-code-review/runbooks/local-review.md).
- **GitHub delivery** is the only stage permitted to mutate PR state
  (comments, review decisions), owned exclusively by `github-pr-review`
  in active mode.
- **Orchestration ownership** (deciding which Skill runs when, enforcing
  one-reviewer-per-scope, enforcing any loop limit) belongs to the
  calling workflow — see section 4.
- **Implementation ownership** always belongs to the implementing Agent
  or developer, never to either Skill.
