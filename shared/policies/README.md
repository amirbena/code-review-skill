# Shared Review Policies

Portable, runtime-facing review policies used **identically by both Code
Review Agent Skills** — [`local-code-review`](../../skills/local-code-review/SKILL.md)
and [`github-pr-review`](../../skills/github-pr-review/SKILL.md). They keep
P0/P1/P2 severity, scope, evidence, and decision semantics from diverging
between the two Skills.

This README is navigation and explanation only. Each policy file is the
normative source for its own concern; where this README and a policy
disagree, the policy wins. Do not copy rule blocks or decision tables
here.

## When to read these policies

Read a file here when a Skill's `SKILL.md`, runbook, or own `policies/`
file routes you to it — these define the cross-Skill contract that
target-specific policies apply. They are consumed at runtime, wherever the
packaged Skill is installed; they do not depend on this repository.

## Policy map

| Policy | Responsibility (one line) |
| --- | --- |
| [`review-scope.md`](review-scope.md) | What any review examines — the review target and its boundary — independent of which Skill runs. |
| [`severity.md`](severity.md) | The single P0/P1/P2 severity each finding receives and the mechanical severity → decision derivation. |
| [`evidence.md`](evidence.md) | Every finding must rest on concrete repository evidence; what counts as evidence. |
| [`review-context.md`](review-context.md) | The concepts a review reasons over and how optional caller-supplied requirement/scope material is used without widening the target. |
| [`review-evidence.md`](review-evidence.md) | How a review uses previously produced review information (prior comments/decisions) — reconciled against the current target, not inherited. |
| [`repository-instructions.md`](repository-instructions.md) | Discovering and applying the target repository's own `AGENTS.md`/`CLAUDE.md` hierarchy before evaluating changed files. |
| [`runtime-validation.md`](runtime-validation.md) | Safe, repository-declared validation evidence: narrow command selection, read-only safety gates, four explicit outcomes, and unchanged finding/decision semantics. |
| [`file-reviewability.md`](file-reviewability.md) | Evidence-based classification of changed files whose direct line-by-line review is low-value or impossible (vendored, generated, minified, binary, snapshots). |
| [`git-safety.md`](git-safety.md) | How both Skills inspect a target repository without mutating it. |
| [`review-ownership.md`](review-ownership.md) | One review scope has one Code Review Agent owner; the access-vs-ownership distinction and parallel-review guards. |
| [`parallel-review.md`](parallel-review.md) | The portable contract for splitting one review across independent workers when the runtime exposes a reliable capability; sequential fallback always valid. |
| [`invocation-options.md`](invocation-options.md) | Deterministic, invocation-scoped normalization of shared presentation options and finding-detail precedence. |
| [`remediation-guidance.md`](remediation-guidance.md) | Advisory fix direction on findings; never changes finding identity, severity, dedup, or the derived verdict. |

Templates shared by both Skills live in
[`../templates/`](../templates/) (`finding.md`, `review-summary.md`).

## Shared vs. Skill-specific vs. repository policy

```text
shared/policies/                       cross-Skill runtime contract (this directory)
skills/local-code-review/policies/     local-only runtime behavior (thin, applies the shared model)
skills/github-pr-review/policies/      GitHub-only runtime behavior (thin, applies the shared model)
policies/                              repository-development governance — NOT packaged runtime policy
```

A Skill's own `policies/` file names its review target and prior-evidence
source and applies the shared semantics; it does not re-document them.
Repository-development rules (branching, PRs, packaging, documentation,
orchestration of the Skills) live in the repository-root
[`policies/`](../../policies/README.md) directory and are never shipped in
a Skill archive.

## Canonical ownership

One normative home per rule. These files are the canonical home for the
shared review contract. `SKILL.md`, runbooks, Skill-specific policies,
`docs/`, and every README summarize and link to them — they do not
restate the rules.

## Packaging

Every file in this directory **except this README** is a packaged runtime
resource: `scripts/package-skills.sh` / `scripts/package-skills.ps1` copy
them into both `dist/*.zip` archives under `shared/policies/`. This README
is a source-tree maintainer/contributor navigation aid: a packaged Skill
is entered through its `SKILL.md`, which links to each shared policy by
name, so the archive needs the policies, not this map. Keeping it
source-only also matches the existing convention that no `README.md` is
packaged.
