# code-review-skill

> Two portable **Code Review Agent Skills** that share one review standard —
> one for local changes before they become a PR, one for existing GitHub
> Pull Requests.

Each Skill is packaged around a canonical
[Agent Skills](https://agentskills.io/specification) `SKILL.md` and runs on
any Agent Skills-compatible runtime (Claude Code, Codex, Cursor, OpenCode,
…). Optional runtime adapters may improve discovery but never change review
behavior.

Licensed under the [Apache License 2.0](LICENSE).

Explanatory, navigational documentation — onboarding, a Skill-selection
guide, and a dated AI code-review landscape comparison — lives in the
[GitHub Wiki](https://github.com/amirbena/code-review-skill/wiki). It
never overrides the canonical files in this repository.

## What this repository provides

| Skill | Reviews | Delivers |
|---|---|---|
| [`local-code-review`](skills/local-code-review/SKILL.md) | your local implementation delta — committed, staged, unstaged, and untracked changes, each detected separately | one structured P0/P1/P2 report to the caller |
| [`github-pr-review`](skills/github-pr-review/SKILL.md) | an existing GitHub Pull Request delta | a report (passive), or — with active GitHub access — inline P0/P1/P2 comments, a summary, and an Approve / Request Changes decision |

Both are **read-only for your code**: neither edits files, commits, pushes,
or merges. `github-pr-review`'s strongest positive action is **Approve**.

## Which Skill should I use?

| Your need | Use |
|---|---|
| Review local changes before you push | `local-code-review` |
| Get a coding-agent-ready fix prompt for the findings, locally | `local-code-review` with `include_fix_prompt=true` |
| Review an existing GitHub PR (that you did not author) | `github-pr-review` |
| Publish inline comments / Approve / Request Changes on that PR | `github-pr-review` with active GitHub access |

Rule of thumb: **no PR yet → `local-code-review`; a PR exists and you are
not its author → `github-pr-review`.** An implementing Agent never reviews
its own PR — see
[`policies/review-orchestration-policy.md`](policies/review-orchestration-policy.md),
"Implementation Workflow Termination and Reviewer/Author Separation." Full
side-by-side detail is
in [`docs/CODE_REVIEW_COMPARISON.md`](docs/CODE_REVIEW_COMPARISON.md) §9.

## Install / package

Building a Skill produces one standalone archive with `SKILL.md` and
`LICENSE` at its root (never nested under a `skills/` path), so a consumer
never needs to know this repository's layout. Pick the archive that matches
how the reviewer will be used — packaging both is rarely needed.

| Package | Command (shell · PowerShell) | Output |
|---|---|---|
| Local review only | `./scripts/packaging/package-skills.sh local` · `./scripts/packaging/package-skills.ps1 local` | `dist/local-code-review-skill.zip` |
| GitHub PR review only | `./scripts/packaging/package-skills.sh github` · `./scripts/packaging/package-skills.ps1 github` | `dist/github-pr-review-skill.zip` |
| Both entry points | `./scripts/packaging/package-skills.sh all` · `./scripts/packaging/package-skills.ps1 all` | both archives above |

## Quick start

1. **Package** the Skill you need (above).
2. **Install** the archive into your runtime's Skill directory — for
   example `.claude/skills/<name>/`, `.agents/skills/<name>/`,
   `.cursor/skills/<name>/`, or `.opencode/skills/<name>/`. Each archive
   already keeps `SKILL.md` at its own root, so unzip it directly into that
   directory.
3. **Invoke** it from the runtime.
   - `local-code-review` is opt-in — it runs only when you explicitly ask,
     every time. Optionally pass review context to focus attention:

     ```text
     /local-code-review

     Context source: Jira PROJECT-1234
     Acceptance criteria:
     - reject writes to a record while it is locked
     - validation must occur before the write is persisted
     ```

     A bare `/local-code-review` with no context is fully supported.
   - `github-pr-review` takes a PR URL or number.

Missing optional context never fails or degrades a review.

## Capabilities and guarantees

Both Skills apply one **portable review governance protocol** on top of
ordinary bug-finding — the durable value is *how* a review is controlled,
not only what it finds:

- **Read-only** — no edits, commits, pushes, merges, or branch management.
- **Opt-in local review** — `local-code-review` needs fresh, explicit user
  approval for every invocation, including each re-review after a fix.
- **Self-review is allowed; self-approval is not** — `github-pr-review`
  analyzes its own PR and produces a real verdict, but never submits a
  formal `APPROVE` / `REQUEST_CHANGES` on the reviewer's own work.
- **Analysis is separate from GitHub mutation authority** — one canonical
  publication mode (`PASSIVE` / `SEMI` / `ACTIVE`), defaulting to
  non-mutating `PASSIVE`; an explicit `ACTIVE` request is itself
  sufficient authorization to publish, subject to genuine reviewer
  independence and GitHub permission.
- **One reviewer owner per scope**, **exact reviewed-HEAD tracking**, and
  **HEAD revalidation before the decision**, so a changed HEAD is never
  approved as the SHA that was actually reviewed.
- **Shared P0/P1/P2 severity model** with a mechanical blocking rule,
  identical in both Skills.

**Optional and advanced capabilities** — review context, runtime
validation evidence, parallel review, human-style output, delta / SHA-aware
re-review, GitHub publication & review authorization, and the coding-agent
fix prompt — each has a short usage guide, with which Skill supports it
and how it is activated, in the capability catalog
[`docs/features/`](docs/features/README.md).

**Not** implemented: any GitHub-side merge or auto-merge,
branch-protection changes beyond one opt-in required-check setup, and any
execution of the target repository's code. See
[`docs/CODE_REVIEW_COMPARISON.md`](docs/CODE_REVIEW_COMPARISON.md) §3 and §10.

## Requirements

- **Git** — required for both Skills.
- **Authenticated GitHub access** — required for `github-pr-review` to read
  PR state; **sufficient review permissions** are required only to
  *publish* an active review. A complete review can still report findings
  when GitHub does not permit that account to submit Approve or Request
  Changes. Credentials come from the environment and are never stored in
  either Skill.
- **Python 3** — only to run *this repository's* validation, packaging, and
  test tooling (see below). It is **not** a runtime dependency of either
  packaged Skill.

## Contributing to this repository

Contributions are welcome. Issues labeled `help wanted` or `good first issue`
are available for anyone to claim without prior approval. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the fork, `/claim`, pull request,
review, and merge workflow.

Development of this repository follows its own canonical rules in
[`AGENTS.md`](AGENTS.md) and the focused [`policies/`](policies/) it
routes to — a dedicated branch per task, squash-merge by default,
read-only Git safety, and the documentation-UX standards in
[`policies/documentation-policy.md`](policies/documentation-policy.md).
Opening a PR here applies
[`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)
automatically — its compact What / Validation / Review shape keeps Issue,
contract, governance, packaging, changelog, and review traceability scannable.

All validation and packaging commands run from the repository root, after
one-time setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

(On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` and use
`python` in place of `python3` throughout this section.)

### Local validation before opening a PR

Local validation is **targeted**, not a fixed sequence: run only the checks
relevant to what you changed, for fast feedback before pushing. The full
suite below is **not** required locally before every push or PR — it runs
automatically in [`.github/workflows/validate.yml`](.github/workflows/validate.yml)
on every PR, which remains the authoritative regression gate before merge
(see [`policies/git-pr-merge-policy.md`](policies/git-pr-merge-policy.md)).

| Change | Run |
| --- | --- |
| Docs-only (`docs/`, root `*.md`, `policies/*.md`) | `python3 scripts/validation/validate-markdown-links.py` |
| Benchmark-related (`docs/benchmark/`, benchmark tooling/tests) | the benchmark test package, e.g. `python3 -m unittest discover -s tests/policy/benchmark` and/or `tests/unit/benchmark` |
| Skill metadata (`skills/<name>/SKILL.md`, `metadata/skill.yaml`, `package-manifest.json`) | `python3 scripts/validation/validate-skill-metadata.py skills/<name> --containment-root .` for the affected Skill |
| Packaging (`scripts/packaging/**`) | `./scripts/packaging/package-skills.sh <local\|github\|all>` for the affected target, plus `python3 -m unittest discover -s tests/integration/packaging` |
| Focused code/test change (`shared/**`, `scripts/**`, `tests/**`) | the directly affected module(s), e.g. `python3 -m unittest tests.unit.test_reviewer_ownership` |

If a change doesn't map cleanly to one of these, run a broader targeted
subset instead — for example every test module under the top-level
directory you touched — rather than defaulting to the full suite below.

### Full local validation (optional)

Running the complete sequence locally is always safe and is worth doing
when a change genuinely spans multiple areas, touches a shared
cross-cutting contract, or you want CI-equivalent confidence before
pushing. It is never a precondition for opening a PR.
[Issue #183](https://github.com/amirbena/code-review-skill/issues/183)
tracks a `scripts/preflight.sh` / `scripts/preflight.ps1` to automate this;
until it exists, run the steps by hand:

```bash
python3 scripts/validation/validate-skill-metadata.py skills/local-code-review --containment-root .
python3 scripts/validation/validate-skill-metadata.py skills/github-pr-review --containment-root .
python3 scripts/validation/validate-markdown-links.py
python3 -m unittest discover -s tests -t .
./scripts/packaging/package-skills.sh all
```

On Windows PowerShell, package with
`./scripts/packaging/package-skills.ps1 all`. Packaging also needs the `zip` and
`unzip` command-line tools on macOS/Linux, or PowerShell on Windows. Generated
archives stay under the ignored `dist/` directory.

Packaging internals — how the source layout under `skills/<name>/` and
`shared/` becomes the flat archive layout, and how package-relative links
are rewritten during staging — are described in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §7.

## Deeper documentation

| Read this | For |
|---|---|
| [`skills/local-code-review/README.md`](skills/local-code-review/README.md) · [`skills/github-pr-review/README.md`](skills/github-pr-review/README.md) | per-Skill onboarding — purpose, invocation, capabilities, boundaries |
| [`docs/features/`](docs/features/README.md) | usage guides for the optional/advanced capabilities — what each does and how to ask for it |
| [`docs/CODE_REVIEW_COMPARISON.md`](docs/CODE_REVIEW_COMPARISON.md) | why these Skills exist alongside Claude Code, GitHub-native, and third-party reviewers, and the full `local-code-review` vs. `github-pr-review` matrix |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | the architecture overview — components, relationships, the review pipeline, boundaries, and links to canonical detail |
| [`AGENTS.md`](AGENTS.md) + [`policies/`](policies/) | this repository's canonical development entrypoint — global invariants, instruction precedence, and a routing table into the focused development, Git/PR/merge, validation, documentation, Skill-development, and review-orchestration policies |
| [`docs/runtime-parallelism.md`](docs/runtime-parallelism.md) | the isolated per-runtime facts behind the portable parallel-review contract (linked from the [parallel-review guide](docs/features/parallel-review.md)) |
| [`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md) · [`skills/github-pr-review/SKILL.md`](skills/github-pr-review/SKILL.md) | the complete, normative Skill definitions |
| [`SECURITY.md`](SECURITY.md) | how to report a vulnerability privately |
| [`CHANGELOG.md`](CHANGELOG.md) | notable user-facing changes per release |
| [`docs/RELEASE.md`](docs/RELEASE.md) | how release-worthy changes are detected, CHANGELOG coverage, deterministic SemVer classification, and the automatic publication flow |
