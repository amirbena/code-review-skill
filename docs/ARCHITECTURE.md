# ARCHITECTURE.md

The conceptual architecture of this repository's Code Review Agent Skills:
one small read-only Review Core and independently selectable `review-*`
mini-skills. It is decoupled from any specific runtime — see
[`AGENTS.md`](../AGENTS.md) ("Global invariants" — runtime neutrality; the
**Agent via Skill** vocabulary) and
[`policies/skill-development-policy.md`](../policies/skill-development-policy.md),
"Portable Core, Optional Runtime Adapters."

This document is a **map, not a contract**. Exact behavior lives in each
Skill's `SKILL.md` and rule files; the decision record, with the reasons and
the removed v2 mechanisms, is the
[v3 ADR](v3-architecture/adr-v3-review-core.md). Moving from v2:
[`migration-v2-to-v3.md`](migration-v2-to-v3.md); per-Skill pages:
[`features/`](features/README.md).

## The mental model in one picture

```text
user's natural-language review request
        │
        ▼
review-core    resolve the target, review it read-only, decide
        │      (a local Git change, or a GitHub PR as one more diff source)
        │
        ├── no depth requested ─────────► Core report (+ JSON on request)
        └── mini-skills selected ───────► each adds findings or delivery
                                          on top of the Core's result
```

A plain "review this" runs the Core alone. Depth comes from what the user
asks for, in their own words, never from routing predicates.

## 1. Module map

```text
skills/
├── review-core/               the Core: shared review rules, report, JSON result
│   ├── SKILL.md               entry contract + inline procedure
│   ├── rules/                 safety.md, reasoning.md, findings.md
│   └── templates/             report.md, result.schema.json
├── review-publish-github/     delivery: one batched, comment-only PR review
├── review-requirements/       depth: verify against Jira / Issue / pasted criteria
├── review-deep-investigation/ depth: lifts the Core investigation bound
├── review-suggestions/        depth: non-blocking P2 maintainability suggestions
├── review-security/           domain: security and supply chain
├── review-backend/            domain: APIs, data, concurrency, performance, deployment
├── review-frontend/           domain: UI, state, accessibility, rendered inspection
└── review-runtime-check/      execution: confirm a finding by running a check
```

A Skill is its `SKILL.md` plus the few rule, template and checklist files it
lists. The Core is read in full on every run; there is no loading inventory,
conditional loading or runbook layer.

## 2. Who owns which rule

Each rule has exactly one owner; other files reference it by Skill name.

| Rule | Owner |
|---|---|
| Severity (P0/P1/P2), evidence, the mechanical decision, `REVIEW INCOMPLETE` | `review-core` |
| Read-only posture, untrusted repository content, no destructive Git (S1, S5, S10) | `review-core` |
| Explicit per-run request, no automatic invocation (S2) | `review-core` |
| Mini-skill selection modes (`intent`, `auto`) | `review-core` |
| Publishing: comment-only on self-review, HEAD revalidation, one batched review (S7) | `review-publish-github` |
| Code execution: sandbox by default, host only with explicit authorization (S8) | `review-runtime-check` |
| Jira and Issue resolution is read-only (S9) | `review-requirements` |

A mini-skill never redefines severity, the verdict rule or S1–S5/S10.

## 3. Review lifecycle

1. The user asks for a review. Nothing starts a review on its own.
2. `review-core` resolves the target and reads the change.
3. It reasons about the change, validates candidate findings against
   evidence, and applies the mechanical decision: any P0/P1 is
   `CHANGES REQUIRED`, otherwise `REVIEW CLEAN`, and `REVIEW INCOMPLETE`
   overrides both.
4. Selected mini-skills add findings or delivery on the Core's result.
5. The caller decides what happens next: fix, re-review (a new request),
   or publish.

## 4. Orchestration boundary

The Skills do not decide when to run, how many iterations to make, or
whether to publish — the calling runtime, Team Lead or implementing
workflow does. An implementing Agent never publishes a review to the PR it
just opened (see
[`policies/review-orchestration-policy.md`](../policies/review-orchestration-policy.md)).

## 5. Repository tooling around the Skills

| Area | Purpose |
|---|---|
| [`scripts/packaging/`](../scripts/packaging/) | builds self-contained Skill trees and archives from `package-manifest.json` |
| [`scripts/skill_metadata/`](../scripts/skill_metadata/) | validates each Skill's frontmatter and links |
| [`scripts/release/`](../scripts/release/) | release-worthiness, CHANGELOG generation, tagging; see [`RELEASE.md`](RELEASE.md) |
| [`scripts/sandbox/`](../scripts/sandbox/) | the sandbox backend `review-runtime-check` uses |
| [`scripts/github_integration/`](../scripts/github_integration/) | the authenticated GitHub call boundary and write allow-list behind S7 |
| [`scripts/validation/`](../scripts/validation/) | CI test routing, link and PR-description validators |
| [`runtime_platform/benchmark/`](../runtime_platform/benchmark/README.md), [`benchmark/`](../benchmark/README.md) | the review-quality benchmark: contracts, harness, corpus |
| [`tests/`](../tests/README.md) | the repository's own test suite; none of it is packaged |

Packaged Skills are Markdown and JSON only. Nothing under `tests/`, `scripts/`
or `runtime_platform/` is a runtime dependency of a Skill.

## 6. Packaging

The v3 Skills are added to the package manifest, and the distribution
published from the built trees, at the cutover
([#851](https://github.com/amirbena/code-review-skill/issues/851)). Until
then `package-manifest.json` declares no Skill and the build produces
nothing. See [`distribution.md`](distribution.md) for the consumer-side
install guide.
