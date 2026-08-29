# Changelog

Notable user-facing and project-level changes, newest first. Each version
corresponds to a published GitHub Release and a matching `vX.Y.Z` tag.
This file summarizes releases; it is not a commit-by-commit log.

## Unreleased

_Nothing yet. New entries land here and move under a version heading at
release time._

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
