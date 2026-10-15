# code-review-skill

> Two portable **Code Review Agent Skills** that share one review standard —
> one for local changes before they become a PR, one for existing GitHub
> Pull Requests.

Each Skill is a canonical [Agent Skills](https://agentskills.io/specification)
`SKILL.md` and runs on any compatible runtime (Claude Code, Codex, Cursor,
OpenCode, …). Both return evidence-backed **P0 / P1 / P2** findings and never
edit, commit, push, or merge your code. Licensed under the
[Apache License 2.0](LICENSE).

**New here?** [Install](#install) · [Choose a Skill](#which-skill-should-i-use) ·
[Contribute](#contributing) · [Wiki](https://github.com/amirbena/code-review-skill/wiki) ·
[Documentation map](#deeper-documentation)

## Which Skill should I use?

| Skill | Reviews | Delivers |
|---|---|---|
| [`local-code-review`](skills/local-code-review/SKILL.md) | your local changes — committed, staged, unstaged, and untracked, each detected separately | one structured P0/P1/P2 report to the caller |
| [`github-pr-review`](skills/github-pr-review/SKILL.md) | an existing GitHub Pull Request | a report (default), or — with active GitHub access — inline comments, a summary, and an Approve / Request Changes decision |

Rule of thumb: **no PR yet → `local-code-review`; a PR exists and you are not
its author → `github-pr-review`.** An implementing Agent never reviews its own
PR ([policy](policies/review-orchestration-policy.md)). Need a ready-to-run fix
prompt for the findings? Ask `local-code-review` for `include_fix_prompt=true`.
Side-by-side detail: [`docs/CODE_REVIEW_COMPARISON.md`](docs/CODE_REVIEW_COMPARISON.md) §9.

## Install

Install from the generated distribution repository through your tool's own
Skill or plugin mechanism. For the `skills` CLI:

```bash
npx skills add amirbena/code-review-skills --skill local-code-review
```

Use `--skill github-pr-review` for the other Skill.
[`docs/distribution.md`](docs/distribution.md) is the canonical install guide:
commands for Claude Code, Codex, Cursor, and GitHub Copilot, updating, and
which paths are verified.

<details>
<summary>Manual / offline install (only when managed installation is unavailable)</summary>

Building produces one standalone archive per Skill with `SKILL.md` and
`LICENSE` at its root. From the repository root:

| Package | Command (shell · PowerShell) | Output |
|---|---|---|
| Local review only | `./scripts/packaging/package-skills.sh local` · `./scripts/packaging/package-skills.ps1 local` | `dist/local-code-review-skill.zip` |
| GitHub PR review only | `./scripts/packaging/package-skills.sh github` · `./scripts/packaging/package-skills.ps1 github` | `dist/github-pr-review-skill.zip` |
| Both | `./scripts/packaging/package-skills.sh all` · `./scripts/packaging/package-skills.ps1 all` | both archives |

Unzip into your runtime's Skill directory (for example `.claude/skills/<name>/`,
`.agents/skills/<name>/`, `.cursor/skills/<name>/`, or `.opencode/skills/<name>/`).
A ZIP install has no update command and is not counted toward skills.sh.
Packaging needs `zip` and `unzip` on macOS/Linux, or PowerShell on Windows.

</details>

## Quick start

Invoke the Skill from your runtime.

`local-code-review` is opt-in — it runs only when you explicitly ask, every
time. A bare `/local-code-review` is fully supported; optionally pass context
to focus the review:

```text
/local-code-review

Context source: Jira PROJECT-1234
Acceptance criteria:
- reject writes to a record while it is locked
- validation must occur before the write is persisted
```

`github-pr-review` takes a PR URL, or a PR number when the repository is clear
from context. By default it returns the report without posting anything to
GitHub:

```text
/github-pr-review https://github.com/OWNER/REPO/pull/123
```

Missing optional context never fails or degrades a review. Publishing to
GitHub is covered in [`docs/features/github-review-publication.md`](docs/features/github-review-publication.md).

**Requirements:** Git for both Skills; authenticated GitHub access for
`github-pr-review` (extra review permissions only to *publish* an Approve or
Request Changes). Credentials come from the environment and are never stored.
Python 3 is needed only for this repository's own tooling, not by either Skill.

## What makes the review approach different

The durable value is *how* a review is governed, not only what it finds:

- **Read-only** — no edits, commits, pushes, merges, or branch management.
- **Opt-in local review** — fresh, explicit approval for every `local-code-review` run, including re-reviews.
- **Self-review is allowed; self-approval is not** — a reviewer can analyze its own PR but never submits a formal `APPROVE` / `REQUEST_CHANGES` on it.
- **Analysis is separate from GitHub mutation** — publication defaults to non-mutating `PASSIVE`; an explicit `ACTIVE` request publishes, subject to reviewer independence and GitHub permission.
- **Exact reviewed-HEAD tracking** with revalidation before the decision, so a changed HEAD is never approved as the SHA that was reviewed.
- **One P0/P1/P2 severity model** with a mechanical blocking rule, identical in both Skills.

Optional capabilities — review context, requirement coverage, gated runtime
validation, delta re-review, parallel review, human-style output, deployment
and design review, and more — are catalogued in
[`docs/features/`](docs/features/README.md).

**Limits:** neither Skill merges or auto-merges, and neither runs the reviewed
repository's code except through the gated, opt-in
[runtime validation](docs/features/runtime-validation.md) capability.
Branch protection is never changed beyond adding or removing the single
required check, only on explicit request
([details](docs/features/github-merge-enforcement.md)). See
[`docs/CODE_REVIEW_COMPARISON.md`](docs/CODE_REVIEW_COMPARISON.md) §3 and §10.

## Contributing

Contributions are welcome, and issues labeled
[`good first issue`](https://github.com/amirbena/code-review-skill/labels/good%20first%20issue)
or [`help wanted`](https://github.com/amirbena/code-review-skill/labels/help%20wanted)
can be claimed without prior approval:

1. Pick an open, unclaimed issue and comment `/claim`.
2. Fork, work on a `<type>/<short-description>` branch, and open a PR.
3. Follow [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full workflow, ownership
   labels (`good first issue`, `contributor-owned`, `maintainer-led`), review,
   and merge.

Repository development follows [`AGENTS.md`](AGENTS.md) and the focused
[`policies/`](policies/) it routes to. Opening a PR applies
[`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md).

### Development setup

All validation and packaging commands run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` and use
`python` in place of `python3`.

### Local validation before opening a PR

Run only the checks relevant to your change; CI
([`validate.yml`](.github/workflows/validate.yml)) is the authoritative gate
and routes each PR to the tests it needs
([routing rules](policies/validation-and-clean-exit.md#routed-ci-tests)).

| Change | Run |
| --- | --- |
| Docs-only (`docs/`, root `*.md`, `policies/*.md`) | `python3 scripts/validation/ci_test_route.py classify` prints the class, tier, and command CI would use; a pure `docs/` change needs only `ci_test_route.py run-docs`, while a `policies/*.md` or `AGENTS.md` change also needs `python3 -m unittest discover -s tests/policy/governance` |
| Benchmark-related (`runtime_platform/benchmark/`, `benchmark/corpus/`, benchmark tooling/tests) | the benchmark test package, e.g. `python3 -m unittest discover -s tests/policy/benchmark` and/or `tests/unit/benchmark` |
| Skill metadata (`skills/<name>/SKILL.md`, `metadata/skill.yaml`, `package-manifest.json`) | `python3 scripts/validation/validate-skill-metadata.py skills/<name> --containment-root .`, plus `python3 -m unittest tests.policy.governance.test_skill_entrypoint_guards` for a `SKILL.md` change |
| Packaging (`scripts/packaging/**`) | `./scripts/packaging/package-skills.sh <local\|github\|all>`, plus `python3 -m unittest discover -s tests/integration/packaging` |
| Focused code/test change (`shared/**`, `scripts/**`, `tests/**`) | the directly affected module(s), e.g. `python3 -m unittest tests.unit.review.test_reviewer_ownership`; for a test-only change `ci_test_route.py classify` prints the exact command |

If a change doesn't map cleanly, run every test module under the top-level
directory you touched. The full suite is optional locally:

```bash
python3 scripts/validation/validate-skill-metadata.py skills/local-code-review --containment-root .
python3 scripts/validation/validate-skill-metadata.py skills/github-pr-review --containment-root .
python3 scripts/validation/validate-markdown-links.py
python3 -m unittest discover -s tests -t .
./scripts/packaging/package-skills.sh all
```

Packaging internals are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §7.

## Deeper documentation

| Read this | For |
|---|---|
| [GitHub Wiki](https://github.com/amirbena/code-review-skill/wiki) | onboarding, a Skill-selection guide, and a dated AI code-review landscape comparison (explanatory; never overrides files in this repository) |
| [`skills/local-code-review/README.md`](skills/local-code-review/README.md) · [`skills/github-pr-review/README.md`](skills/github-pr-review/README.md) | per-Skill onboarding — purpose, invocation, boundaries |
| [`docs/features/`](docs/features/README.md) | the capability catalog — what each optional capability does and how to ask for it |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | components, the review pipeline, boundaries, and links to canonical detail |
| [`docs/CODE_REVIEW_COMPARISON.md`](docs/CODE_REVIEW_COMPARISON.md) | how these Skills relate to Claude Code, GitHub-native, and third-party reviewers |
| [`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md) · [`skills/github-pr-review/SKILL.md`](skills/github-pr-review/SKILL.md) | the complete, normative Skill definitions |
| [`AGENTS.md`](AGENTS.md) + [`policies/`](policies/) | development entrypoint — invariants, instruction precedence, and focused policies |
| [`docs/distribution.md`](docs/distribution.md) · [`docs/RELEASE.md`](docs/RELEASE.md) | installing/updating, and how releases are versioned and published |
| [`SECURITY.md`](SECURITY.md) · [`CHANGELOG.md`](CHANGELOG.md) | reporting a vulnerability privately; notable changes per release |
