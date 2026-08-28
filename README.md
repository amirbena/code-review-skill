# code-review-skill

> Two portable **Code Review Agent Skills** that share one review standard —
> one for local changes before they become a PR, one for existing GitHub
> Pull Requests.

Each Skill is packaged around a canonical
[Agent Skills](https://agentskills.io/specification) `SKILL.md` and runs on
any Agent Skills-compatible runtime (Claude Code, Codex, Cursor, OpenCode,
…). Optional runtime adapters may improve discovery but never change review
behavior.

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

Building a Skill produces one standalone archive with `SKILL.md` at its
root (never nested under a `skills/` path), so a consumer never needs to
know this repository's layout. Pick the archive that matches how the
reviewer will be used — packaging both is rarely needed.

| Package | Command (shell · PowerShell) | Output |
|---|---|---|
| Local review only | `./scripts/package-skills.sh local` · `./scripts/package-skills.ps1 local` | `dist/local-code-review-skill.zip` |
| GitHub PR review only | `./scripts/package-skills.sh github` · `./scripts/package-skills.ps1 github` | `dist/github-pr-review-skill.zip` |
| Both entry points | `./scripts/package-skills.sh all` · `./scripts/package-skills.ps1 all` | both archives above |

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

     Context source: Jira BILLPAY-1234
     Acceptance criteria:
     - reject unsupported CC + RTP combinations
     - validation must occur before execution
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
- **Self-review prevention** — `github-pr-review` compares the
  authenticated identity against the PR author and skips self-review before
  any analysis.
- **One reviewer owner per scope**, **exact reviewed-HEAD tracking**, and
  **HEAD revalidation before the decision**, so a changed HEAD is never
  approved as the SHA that was actually reviewed.
- **Shared P0/P1/P2 severity model** with a mechanical blocking rule,
  identical in both Skills.

Implemented: an opt-in isolated read-only temporary PR checkout, and opt-in
parallel review with a sequential fallback. **Not** implemented: GitHub
merge-blocking / required status checks, and any execution of the target
repository's code. See
[`docs/CODE_REVIEW_COMPARISON.md`](docs/CODE_REVIEW_COMPARISON.md) §3 and §10.

### Review context and prior review evidence (optional)

Both Skills accept an optional **review context** — free-form requirements,
explicit user instructions, a Jira/tracker ticket, an explicitly supplied
GitHub Issue (no automatic PR↔Issue discovery), an HLD/ADR, or an
implementation plan. It focuses attention and enables scope-boundary
reasoning; it never widens the review target. Relevant **prior review
evidence** is reconciled against the *current* target, not blindly
inherited — a resolved thread is evidence of a past conclusion, not proof
the current code is correct, and automation/bot comments contribute
observations only. Both are defined once in
[`shared/policies/review-context.md`](shared/policies/review-context.md) and
[`shared/policies/review-evidence.md`](shared/policies/review-evidence.md).

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

Development of this repository follows its own canonical rules in
[`AGENTS.md`](AGENTS.md) and the focused [`policies/`](policies/) it
routes to — a dedicated branch per task, squash-merge by default,
read-only Git safety, and the documentation-UX standards in
[`policies/documentation-policy.md`](policies/documentation-policy.md).
Opening a PR here applies
[`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)
automatically — it walks through change surface, behavioral change,
governance impact, and reviewer focus.

Validation and packaging run from the repository root:

```bash
python3 --version
python3 scripts/validate-skill-metadata.py skills/local-code-review --containment-root .
python3 scripts/validate-skill-metadata.py skills/github-pr-review --containment-root .
python3 -m unittest discover -s tests -t .
```

Run one test module with, e.g.,
`python3 -m unittest tests.unit.test_reviewer_ownership`.

Packaging internals — how the source layout under `skills/<name>/` and
`shared/` becomes the flat archive layout, and how package-relative links
are rewritten during staging — are described in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §7.

## Deeper documentation

| Read this | For |
|---|---|
| [`docs/CODE_REVIEW_COMPARISON.md`](docs/CODE_REVIEW_COMPARISON.md) | why these Skills exist alongside Claude Code, GitHub-native, and third-party reviewers, and the full `local-code-review` vs. `github-pr-review` matrix |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | the high-level mental model, module boundaries, the review pipeline, and the orchestration boundary between the Skills and their caller |
| [`AGENTS.md`](AGENTS.md) + [`policies/`](policies/) | this repository's canonical development entrypoint — global invariants, instruction precedence, and a routing table into the focused development, Git/PR/merge, validation, documentation, Skill-development, and review-orchestration policies |
| [`docs/runtime-parallelism.md`](docs/runtime-parallelism.md) | the isolated per-runtime facts behind the portable parallel-review contract |
| [`skills/local-code-review/README.md`](skills/local-code-review/README.md) · [`skills/github-pr-review/README.md`](skills/github-pr-review/README.md) | per-Skill onboarding |
| [`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md) · [`skills/github-pr-review/SKILL.md`](skills/github-pr-review/SKILL.md) | the complete, normative Skill definitions |
