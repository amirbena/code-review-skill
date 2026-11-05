# Migrating from v2 to v3

Explanatory guide for people who used the v2 Skills (`local-code-review`,
`github-pr-review`). It says where each v2 Skill, mode and option went and
what was removed. The rules themselves live in the Skills; the reasons are in
the [v3 ADR](v3-architecture/adr-v3-review-core.md) (§5.1 modes, §6
removals, §12 compatibility names).

## The short version

- One read-only Skill, [`review-core`](../skills/review-core/SKILL.md),
  reviews a local Git change **or** a GitHub pull request.
- Everything extra is an optional `review-*` mini-skill. You select one by
  asking for what it does, in your own words. You never need its name.
- Publishing a review to GitHub is its own mini-skill and runs only when you
  ask for it.
- The published line stays v2.x until the v3 cutover
  ([#851](https://github.com/amirbena/code-review-skill/issues/851)). The v2
  names `local-code-review` and `github-pr-review` are kept as thin wrappers
  over `review-core` (ADR §12); backward compatibility covers the names, not
  v2 behavior or machinery.

## Skills

| v2 | v3 |
|---|---|
| `local-code-review` | [`review-core`](../skills/review-core/SKILL.md) on a local change |
| `github-pr-review`, `PASSIVE` (the default) | `review-core` on a PR: "review PR 123" |
| `github-pr-review`, `ACTIVE` | `review-core` on the PR, then [`review-publish-github`](../skills/review-publish-github/SKILL.md): "review PR 123 and post the review" |
| `github-pr-review`, `SEMI` (preview of what would publish) | removed. Review without asking to publish; the report is the preview |
| `shared/` policies and `capabilities/` deepening | split between `review-core` and the mini-skills below |

## Capabilities that became mini-skills

| v2 capability | v3 mini-skill | Ask for it like this |
|---|---|---|
| Jira / Issue / acceptance-criteria context, requirement coverage | [`review-requirements`](../skills/review-requirements/SKILL.md) | "Does this meet PROJ-123?" |
| Affected-test analysis, failure/retry, null-absence, architectural placement | [`review-deep-investigation`](../skills/review-deep-investigation/SKILL.md) | "Trace this root cause all the way through." |
| Code hygiene, engineering-design content | [`review-suggestions`](../skills/review-suggestions/SKILL.md) | "Any maintainability suggestions?" |
| Security and dependency / supply-chain deepening | [`review-security`](../skills/review-security/SKILL.md) | "Is this auth change safe?" |
| API compatibility, database migrations, distributed systems, performance, deployment | [`review-backend`](../skills/review-backend/SKILL.md) | "Review the backend thoroughly." |
| Rendered inspection, design reference | [`review-frontend`](../skills/review-frontend/SKILL.md) | "Check the UI states and accessibility." |
| Runtime validation, trusted-host execution | [`review-runtime-check`](../skills/review-runtime-check/SKILL.md) | "Run the test that would confirm finding 2." |

## Modes and options

v2 activated depth with predicates and toggled output with named options.
v3 has two selection modes, `intent` (default) and `auto` (opt-in), decided by
the model from the meaning of your request. There is no flag to type.

| v2 | v3 |
|---|---|
| Specialist-depth activation predicates, change-risk depth classes | `intent`: only what the request justifies; the Core may ask once before going further |
| Reviewer-chosen depth | `auto`: "go as deep as necessary and use whatever expertise is relevant" |
| `PASSIVE` / `ACTIVE` publication mode | publish only on request, through `review-publish-github` (S7). It never approves its own PR |
| `structured_review_result` | ask for a machine-readable result; the report ends with the JSON result ([`result.schema.json`](../skills/review-core/templates/result.schema.json)) |
| Review context: pasted text, Jira key, Issue | pasted criteria or a key you supply go to `review-requirements`. A PR description is data, not a reference |
| Optional PR reference on a local review | removed: the target is a local change or a PR, not both |
| Design reference | `review-frontend`, only when you supply it, and rendering needs your consent |
| Repository-backed inspection (isolated checkout) | the Core's own PR checkout: isolated, temporary, always cleaned up (S10) |
| `include_fix_prompt`, `include_fix_guidance`, `include_finding_details` | removed. Every finding carries its own `fix` |
| `human_review_output`, `human_inline_findings` | removed. There is one senior voice |
| `include_severity_description` | removed |
| Multi-repository Review Targets, workspace-sibling and external-contract context, dependency-tree inspection | removed |
| Parallel review, agent delegation, Reviewer Brief, review ownership (`REVIEW ALREADY OWNED`) | removed |
| Stateful delta re-review, machine-readable review status, required-check setup, stacked-PR policy | removed. A re-review is a new request and a full review |
| Finding confidence, contextual-evidence provenance, capability provenance | removed |
| Large-PR partitioning, reasoning checkpoint, conditional policy loading | removed. The Core reads its few files in full |

Unchanged: P0 / P1 / P2 severity, the mechanical decision (any P0 or P1 is
`CHANGES REQUIRED`, otherwise `REVIEW CLEAN`, and `REVIEW INCOMPLETE`
overrides both), read-only operation, and "never invoked automatically".

## Staying on v2

v2.x keeps working as published. To stay on it after v3 ships, install from a
v2 tag of the distribution repository,
[`amirbena/code-review-skills`](https://github.com/amirbena/code-review-skills),
instead of its default branch. Tags there are `vX.Y.Z` and match the source
repository's releases (for example `v2.0.0`).

- Tools that accept a Git ref can point at the tag.
- Otherwise, clone the tag and copy the Skill folders into your runtime's
  Skill directory.

Updates to v3 are deliberate: moving off the tag is the upgrade. See
[`distribution.md`](distribution.md) for the install paths.
