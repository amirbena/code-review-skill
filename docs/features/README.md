# Feature Guides

User-facing guidance for the **optional and advanced capabilities** of
the two Code Review Agent Skills — what each one does, when it helps,
which Skill supports it, whether it is on by default, and how you ask for
it in plain language.

These pages are **explanatory, not normative**. Each one links to the
canonical policy or runbook that defines the exact semantics; where a
guide and a canonical policy appear to disagree, the policy wins. Nothing
here changes review behavior, severity, decision derivation, or a
mutation boundary.

For the system-level picture — components, the review pipeline, and the
boundaries these features sit inside — see
[`../ARCHITECTURE.md`](../ARCHITECTURE.md). For the day-one overview and
which Skill to pick, start at the [root `README.md`](../../README.md) and
each Skill's own README
([`local-code-review`](../../skills/local-code-review/README.md) ·
[`github-pr-review`](../../skills/github-pr-review/README.md)).

## The guides

| Guide | What it covers | Skill(s) | Default / conditional / requested | Canonical semantics |
|---|---|---|---|---|
| [Review context & prior review evidence](review-context.md) | focusing a review with requirements, a ticket, a GitHub Issue, an HLD/ADR, a plan, or an associated PR's prior findings | both | optional; absence changes nothing | [`review-context.md`](../../shared/policies/review-context.md), [`review-evidence.md`](../../shared/policies/review-evidence.md) |
| [Runtime validation evidence](runtime-validation.md) | letting the review run a repository-declared test/lint/validation command as bounded evidence | both | conditional — needs a declared command **and** a verified isolation boundary | [`runtime-validation.md`](../../shared/policies/runtime-validation.md) |
| [Parallel review](parallel-review.md) | splitting one review across independent read-only workers to reduce latency | both (wired into `github-pr-review`) | conditional — needs a reliable runtime capability; sequential is always the fallback | [`parallel-review.md`](../../shared/policies/parallel-review.md) |
| [Human-style review output](human-review-output.md) | a concise senior-engineer-voice rendering of the final summary | both | explicitly requested in natural language; presentation only | [`invocation-options.md`](../../shared/policies/invocation-options.md) |
| [Delta & SHA-aware re-review](delta-re-review.md) | re-reviewing only what changed since the last review, and skipping a redundant re-review | `github-pr-review` (local review reconciles a PR reference instead) | conditional — same reviewer + a reliable prior reviewed SHA | [`reviewer-delta-review.md`](../../skills/github-pr-review/policies/reviewer-delta-review.md) |
| [GitHub publication & review authorization](github-review-publication.md) | passive vs. active review, `recommendation-only` / `block-only` / auto-action, self-review, and the optional machine-readable status/check | `github-pr-review` | default is non-mutating `recommendation-only`; positive actions need independent trusted authorization | [`review-action-authorization.md`](../../skills/github-pr-review/policies/review-action-authorization.md), [`review-output.md`](../../skills/github-pr-review/policies/review-output.md), [`review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md) |
| [Coding-agent fix prompt](fix-prompt.md) | appending a ready-to-run implementation prompt to qualifying findings | `local-code-review` | explicitly requested (`include_fix_prompt`, default off); output only | [`remediation-guidance.md`](../../shared/policies/remediation-guidance.md) |

## Not a feature guide

Some capabilities are **core, always-on, or internal**, so they are
documented in the architecture map and the canonical policies rather than
here. `docs/features/` is for optional/advanced user-facing capability
guidance — not every subsystem behavior.

| Capability | Why it has no feature guide | Canonical home |
|---|---|---|
| Reviewer ownership (`One review scope → one Code Review Agent owner`) | always on; not something you enable | [`review-ownership.md`](../../shared/policies/review-ownership.md) |
| Exact reviewed-HEAD tracking / revalidation before the decision | always on; a stale HEAD is never approved | [`review-output.md`](../../skills/github-pr-review/policies/review-output.md), "HEAD revalidation"; [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §9 |
| Repository-instruction discovery (root→specific `AGENTS.md` / `CLAUDE.md`) | always on; shapes evaluation, never widens the target | [`repository-instructions.md`](../../shared/policies/repository-instructions.md) |
| P0/P1/P2 severity model and mechanical decision derivation | not optional; the verdict is derived, not chosen | [`severity.md`](../../shared/policies/severity.md) |
| Isolated read-only temporary PR checkout | a review-input enrichment for `github-pr-review` with no user-facing knob (the [GitHub publication guide](github-review-publication.md) mentions it) | [`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md) |
