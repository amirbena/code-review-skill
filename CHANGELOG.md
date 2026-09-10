# Changelog

Notable user-facing and project-level changes, newest first. Each version
corresponds to a published GitHub Release and a matching `vX.Y.Z` tag.
This file summarizes releases; it is not a commit-by-commit log.

Entries under `## Unreleased` are grouped by Keep a Changelog category
(`Added` / `Changed` / `Deprecated` → minor, `Fixed` / `Security` →
patch, `Removed` / `Breaking` → major). The highest category present
determines the next version, which is derived and published automatically
when the change reaches `main`. See
[`docs/RELEASE.md`](docs/RELEASE.md).

## Unreleased

### Fixed

- Internal: the `github-pr-review` entrypoint and both review-output
  templates (`external-review-summary.md`, `local-review-report.md`) no
  longer restate rules owned by their canonical policies — the template
  `## Rules` sections and `SKILL.md` sections 6–7 are trimmed to rendering
  shape plus pointers to `review-output.md`,
  `review-action-authorization.md`, `finding-placement.md`,
  `remediation-guidance.md`, and the shared finding/severity contracts.
  Wording only; no change to review semantics, the authorization boundary,
  finding rendering, or output behavior. (#199)

## v1.9.3 — 2026-09-10

### Fixed

- Internal: the shared review contracts are split along their existing
  architectural boundaries — the finding rendering exemplars into
  `shared/templates/finding-rendering.md`, Jira context resolution into
  `shared/policies/jira-context.md`, and the root-cause-consolidation and
  affected-test analysis sub-domains into their own shared policies — each
  cross-linked from a thin overview in the original file. Relocation only;
  no change to review semantics, severity, the finding contract, or output
  behavior. (#198)

## v1.9.2 — 2026-09-09

### Fixed

- Packaging now reads archive names, resource mappings, destinations, and
  required-entry guards from one declarative manifest shared by the shell and
  PowerShell implementations, preventing their package layouts from drifting.

## v1.9.1 — 2026-09-09

### Fixed

- Internal: the Skill discovery-metadata validator behind
  `scripts/validate-skill-metadata.py` is now a thin entrypoint over a
  focused `scripts/skill_metadata/` package (expectation tables, link /
  metadata / shared-resource / per-Skill checkers, orchestrator, CLI).
  No change to what is validated, the CLI, error messages, or exit codes.

## v1.9.0 — 2026-09-09

### Added

- The shared root-cause review pass now defines **finding
  consolidation**: when one shared defect-bearing element (a validator,
  helper, config value, invariant) reaches **at least two** call paths,
  both Skills emit a single authoritative finding — one identity, one
  severity, one fix direction — with a **required, exhaustive
  affected-locations list** naming every known manifestation site,
  rendered on every human-readable and structured surface (a consolidated
  finding is not publishable without it). Detection fails open: when the
  shared cause is not positively established, separate findings are
  emitted rather than over-merged.
- On a re-review, whether prior separate per-site finding identities fold
  into the consolidated finding is now governed by a new explicit
  **`CONSOLIDATED`** lifecycle disposition. It applies **only** when the
  review positively establishes one shared root cause under
  `review-scope.md` — never inferred from `N→1` matching topology or
  wording similarity, which stay `AMBIGUOUS`/`UNCERTAIN` with every prior
  identity preserved. A folded identity stays `OPEN` (consolidation
  resolves nothing and never reuses `SUPERSEDED`) and its site is kept in
  the affected-locations list. Defined across
  `docs/findings/finding-lifecycle-contract.md` (§4, scenario 16),
  `finding-identity-requirements.md`, `finding-matching-strategy.md`,
  `delta-re-review-contract.md`, and the packaged
  `skills/github-pr-review/policies/stateful-delta-rereview.md`;
  `review-scope.md` and `shared/templates/finding.md` carry the reviewer
  criteria and the finding shape.

## v1.8.1 — 2026-09-09

### Fixed

- Replaced the payments-domain illustration used for review context
  (`CC + RTP` combinations, `CC/RTP` validation, the recurring-payment
  execution path) with a domain-neutral resource/lock example across the
  packaged `shared/policies/review-context.md`, the local report
  template, the READMEs, the feature guide, and the context test corpus.
  Documentation and examples only — review detection, severity, evidence,
  and decision semantics are unchanged.

## v1.8.0 — 2026-09-09

### Added

- `github-pr-review` can now render **GitHub inline review findings** in
  the same concise senior-engineer voice `human_review_output` already
  applies to the final summary, via a companion option
  (`human_inline_findings`) whose default is derived —
  `explicit_value ?? human_review_output` — so enabling senior-review mode
  ("review it like a senior engineer") produces a coherent human-facing
  review end to end: a short heading that keeps the `P0` / `P1` / `P2`
  severity and names the finding, then compact prose carrying the
  evidence, the engineering consequence, and the correction direction
  without `Evidence:` / `Impact:` / `Fix:` labels. An explicit
  `human_inline_findings=false` keeps the structured inline block under a
  concise summary; an explicit `human_inline_findings=true` re-voices the
  inline comments on their own. The re-voicing is presentation only:
  finding detection, severity, identity, deduplication, evidence and
  remediation requirements, the mechanical decision, the GitHub review
  state, the batched single submission, the canonical fix/action anchor,
  and the `#164` / `#165` body-fallback behaviour are all unchanged —
  structured and human renderings are two projections of the same
  semantic finding. `local-code-review` has no inline-comment surface and
  is unaffected (#166).

## v1.7.0 — 2026-09-08

### Changed

- `github-pr-review` now anchors each inline review comment at the
  location an author must change to resolve the finding — its **canonical
  fix/action location** — rather than merely where the problem is
  observable or where GitHub happens to permit a comment. Findings now
  distinguish three things: the evidence/detection location, the canonical
  fix/action location, and the GitHub publication anchor. A finding whose
  fix/action location is outside the PR diff, not inline-commentable, or
  unresolved is surfaced at review-summary level with an explicit path (or
  an explicit unresolved marker) and remediation, instead of being
  attached to an unrelated nearby line. Anchor selection resolves
  semantically valid fix candidates before applying a deterministic
  tie-break, and only then GitHub commentability. Finding identity,
  severity, deduplication, the one-authoritative-representation rule, and
  the single batched submission are unaffected by publication placement.
  The shared finding contract gains an optional `evidence location` field
  and an explicit "fix/action location unresolved" annotation, which
  `local-code-review` output inherits (#164).

## v1.6.0 — 2026-09-07

### Added

- Both review Skills now perform affected-test / test-impact analysis: when a
  change alters observable production behavior, the reviewer traces that
  change into the existing tests that encode or depend on the behavior —
  including tests outside the changed-file set that ordinary repository
  search can reach — and evaluates whether their assertions, fixtures,
  mocks, and expected errors/statuses are still valid, and whether a newly
  introduced path has meaningful regression coverage. Signal-triggered,
  read-only (test code is inspected as text; target-repository tests are
  never run), bounded to the change's blast radius, and evidence-gated — it
  is not a "did the PR add tests?" check and never forces a test change for
  every production change. Extends the existing proportional-scope and
  evidence model rather than adding a second one (#160).

## v1.5.0 — 2026-09-06

### Added

- Both review Skills now detect architecturally misplaced behavior — code
  that is locally correct but sits at the wrong point in the surrounding
  execution flow (an eligibility decision made inside execution, a check
  duplicated below the layer that owns it, a mutation before its
  precondition) — via bounded, semantically triggered context expansion
  along the caller/callee/owning-boundary chain, with explicit stop
  conditions and an "insufficient evidence is terminal" rule. Extends the
  existing proportional-scope and evidence model rather than adding a
  second one (#153).

## v1.4.0 — 2026-09-05

### Changed

- Generalize review-context examples to remove product-specific references
  and add a repository guard preventing their reintroduction (#151).

## v1.3.0 — 2026-09-05

### Added

- Add packaged stateful delta re-review for GitHub PR reviews, including
  prior-finding reconciliation, regression/blast-radius handling,
  settled-assumption invalidation, and fail-closed escalation to broader
  review (#65).

## v1.2.0 — 2026-09-04

### Added

- Safe, repository-declared runtime validation evidence for both review Skills
  (#138).

## v1.1.0 — 2026-09-03

### Added

- Opt-in **`human_review_output`** presentation mode for both Skills,
  requested in ordinary natural language (for example "make the review
  shorter and more human", "review it like a senior engineer", "use
  concise review comments") with no CLI-style flag. When enabled, only
  the final human-facing review summary is rendered in a concise
  senior-engineer voice — what's good / what's concerning / what to
  change, in prose, each referenced finding keeping its `P0` / `P1` / `P2`
  label, an intentional trade-off optionally raised as a question, and no
  review-process or machine metadata. Default off; presentation only — it
  never changes finding detection, severity, deduplication, the
  mechanically derived verdict, the GitHub review state, inline comments,
  any machine-readable status, or publication ordering, and mode on/off
  produce identical findings and severities. Normalized deterministically
  from a fixed, exhaustive phrase vocabulary in
  `shared/policies/invocation-options.md` (#140).

### Changed

- `github-pr-review` now pins the publication order of a review run so
  that **`final review comment == last publication event`**: the one
  batched review submission (body + inline comments + event) carries the
  final human-facing summary and is the last review-owned publication;
  any optional machine-readable status/check is published **before** that
  submission, never after it; nothing review-owned is published or edited
  afterward. HEAD is re-confirmed immediately before that status
  publication and that single re-confirmation gates both the status and
  the review submission — a HEAD advance withholds the status **and**
  blocks the submission, routing to the existing HEAD-revalidation
  re-review path. The single atomic review submission and the
  review-action authorization gate are unchanged. Ordering is identical
  whether or not `human_review_output` is enabled
  (`skills/github-pr-review/policies/review-output.md`, "Submission
  ordering") (#140).

## v1.0.3 — 2026-08-29

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
