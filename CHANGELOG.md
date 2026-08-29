# Changelog

Notable user-facing and project-level changes, newest first. Each version
corresponds to a published GitHub Release and a matching `vX.Y.Z` tag.
This file summarizes releases; it is not a commit-by-commit log.

## Unreleased

### Added

- `github-pr-review` can publish one optional, stable, aggregated,
  **exact-HEAD machine-readable GitHub status/check** for the reviewed
  SHA, separate from the native `APPROVE` / `REQUEST_CHANGES` event and
  derived from the same canonical verdict. A blocking (non-`success`)
  status is blocking-only enforcement and may be published even by a
  self-review; a `success` status is a positive/unblocking action that
  requires the same trusted authorization and reviewer independence as
  `APPROVE` and is **never** published by a self-review; incomplete or
  unresolved review states never publish `success`; a new HEAD inherits
  no green. The Skill can also report, read-only, whether that context is
  `ENFORCED` / `NOT ENFORCED` / `UNKNOWN` across repository rulesets and
  classic branch protection, and — only through a separate, explicitly
  requested, minimal, preserving setup action — add the one context to a
  base branch's required checks without touching approval-count rules,
  `dismiss_stale_reviews_on_push`, `require_last_push_approval`, bypass
  actors, or any unrelated rule. It never merges. New canonical policy
  `skills/github-pr-review/policies/review-status-enforcement.md` (#34).
- Release-worthiness automation: a deterministic classifier
  (`scripts/release_worthiness.py`) and a `Release worthiness` GitHub
  Action. On PRs/pushes it is read-only — it classifies all changes since
  the previous `v*` tag and fails closed when release-worthy work is
  missing from `## Unreleased`. On a maintainer-triggered
  `workflow_dispatch` it is the authoritative release flow: preflight,
  roll the changelog, build and verify both Skill archives, commit and
  push directly to `main`, create and push an annotated `vX.Y.Z` tag at
  that commit, publish the GitHub Release with the archives, and verify
  the live tag/commit/assets. Direct-to-`main` push is limited to a
  dedicated release GitHub App as the sole branch-ruleset bypass actor.
  Convention and required repository configuration: `docs/RELEASE.md`
  (#104).

## v1.0.2 — 2026-08-29

Documentation and review-presentation refinements for both Skills. No
change to review semantics, severity, verdict derivation, or the
security and mutation boundaries.

### Changed

- Slimmed the `local-code-review` and `github-pr-review` Skill
  entrypoints by removing duplicated policy and runbook prose, while
  keeping the critical review and security contracts visible at the point
  of invocation and pointing to their canonical policies for detail.
- Refreshed both Skill READMEs for clearer onboarding, natural-language
  invocation examples, and easier navigation to the canonical
  documentation.
- Made `github-pr-review` review summaries more concise and
  human-readable: detailed evidence, impact, and fix guidance stay in the
  inline review comments instead of being repeated in the final review
  body, which now carries the verdict and a scannable one-line list of
  findings.
- Unified self-review and external-review presentation around the same
  human-facing review format, while preserving their different GitHub
  mutation boundaries — self-review publishes an informational comment,
  and an authorized independent review may approve or request changes.

## v1.0.1 — 2026-08-29

Hardens `github-pr-review`'s authorization model: reviewing a pull
request is now separate from being allowed to act on it.

### Added

- **Review-action modes**, chosen from ordinary natural language (no
  flags or mode keywords): a non-mutating recommendation by default, a
  block-only mode, and an explicitly-authorized auto-action mode.
- A **self-review** may publish its result to GitHub as an informational
  `COMMENT` (verdict, reviewed HEAD, findings).

### Changed

- **Review analysis is separate from GitHub mutation authority.** A clean
  verdict no longer implies `APPROVE`; a formal `APPROVE` /
  `REQUEST_CHANGES` is submitted only under trusted authorization from a
  source independent of the invoking agent, scoped to that
  invocation / repository / PR / reviewed HEAD / action.
- **Self-review now runs the full review** — findings and a verdict —
  instead of stopping early. Authorship gates GitHub *mutations*, not
  *analysis*; formal self-`APPROVE` and self-`REQUEST_CHANGES` remain
  forbidden.
- **Reviewer independence means authority separation, not just a
  different username.** An alternate account, token, bot, service
  account, GitHub App, nested agent, or process under the same
  controlling authority is treated as a self-review.
- Packaging and metadata validation, plus `docs/ARCHITECTURE.md` and
  `docs/CODE_REVIEW_COMPARISON.md`, updated to match.

### Security

- Agent-controlled input — flags, prompts, generated instructions, nested
  Skill/agent invocations, alternate tokens or identities — cannot
  establish GitHub mutation authority. Ambiguous authorization or reviewer
  provenance fails closed to a non-mutating review, and `APPROVE` never
  implies merge authority.

## v1.0.0 — 2026-08-28

First public release. Two portable Code Review Agent Skills sharing one
review standard: `local-code-review` for local changes before they become
a PR, and `github-pr-review` for existing GitHub pull requests.
Deterministic P0/P1/P2 severity model, reviewer ownership and explicit
review authorization, SHA-aware and delta re-review, security and
mutation boundaries, cross-platform packaging, repository validation and
test coverage, and an external-contributor `/claim` workflow. Both Skills
are distributed as ready-to-use ZIP archives under Apache-2.0.
