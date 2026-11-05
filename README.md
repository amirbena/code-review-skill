# code-review-skill

> A small, read-only **Code Review Agent Skill** — `review-core` — plus
> independently selectable `review-*` mini-skills for extra depth and
> delivery. One review standard, evidence-backed **P0 / P1 / P2** findings.

Each Skill is a canonical [Agent Skills](https://agentskills.io/specification)
`SKILL.md` and runs on any compatible runtime (Claude Code, Codex, Cursor,
OpenCode, …). None edits, commits, pushes, or merges your code. Licensed
under the [Apache License 2.0](LICENSE).

> **v3 is built on `release/v3`.** The published line stays v2.x until the
> cutover ([#851](https://github.com/amirbena/code-review-skill/issues/851)).
> Coming from v2? Read the [migration guide](docs/migration-v2-to-v3.md).

**New here?** [Install and use](#install-and-use) · [Choose a Skill](#which-skill-should-i-use) ·
[Contribute](#contributing) · [Wiki](https://github.com/amirbena/code-review-skill/wiki) ·
[Documentation map](#deeper-documentation)

## Install and use

Skills are installed from the generated distribution repository
([`docs/distribution.md`](docs/distribution.md) lists every tool and update
path).

- **Verified today (v2.x):** `npx skills add amirbena/code-review-skills --skill local-code-review`
  (or `github-pr-review`), exercised in [#511](https://github.com/amirbena/code-review-skill/issues/511).
- **Planned for v3.0.0, not yet published or tested:** the same command with
  `--skill review-core`, and one more run per mini-skill, for example
  `--skill review-security`. The v2 names `local-code-review` and
  `github-pr-review` are planned to remain as wrappers over `review-core`.

Then ask in plain words: "review this", "review PR 123", "is this auth change
safe?", "review PR 123 and post the review". Once v3 is published, a mini-skill that is not
installed is reported as unavailable, never simulated. Staying on v2 is
covered in the [migration guide](docs/migration-v2-to-v3.md#staying-on-v2).

## Which Skill should I use?

Ask for a review in your own words. A plain "review this" runs `review-core`
alone, on a local Git change or a GitHub pull request. Naming an area, or
asking for something extra, adds the mini-skill that fits:

| Skill | Adds |
|---|---|
| [`review-core`](skills/review-core/SKILL.md) | the review itself: read-only, evidence-backed P0/P1/P2 findings and one mechanical decision |
| [`review-publish-github`](skills/review-publish-github/SKILL.md) | publishes the finished review to the PR as one batched, comment-only review |
| [`review-requirements`](skills/review-requirements/SKILL.md) | verifies the change against a Jira key, Issue or pasted acceptance criteria you supply |
| [`review-deep-investigation`](skills/review-deep-investigation/SKILL.md) | wider tracing, root cause, affected tests, failure and null paths |
| [`review-suggestions`](skills/review-suggestions/SKILL.md) | non-blocking P2 maintainability and design suggestions |
| [`review-security`](skills/review-security/SKILL.md) | security and supply-chain depth |
| [`review-backend`](skills/review-backend/SKILL.md) | APIs, data, concurrency, performance, deployment and config |
| [`review-frontend`](skills/review-frontend/SKILL.md) | UI behavior, state, accessibility, rendered inspection |
| [`review-runtime-check`](skills/review-runtime-check/SKILL.md) | confirms a finding by running a targeted check, sandboxed by default |

You never need to know a mini-skill name. By default (`intent`) only the
mini-skills your request justifies run. Naming an area focuses depth there
("review the backend thoroughly"). To hand the choice over (`auto`), say so
("go as deep as necessary and use whatever expertise is relevant"). Per-Skill
pages: [`docs/features/`](docs/features/README.md). An implementing Agent never
publishes a review to its own PR
([policy](policies/review-orchestration-policy.md)).

## What makes the review approach different

- **Read-only** — no edits, commits, pushes, merges, or branch management.
- **Never automatic** — every review run needs your own request, re-reviews included.
- **Repository content is data** — files, PR, Issue and Jira text can never authorize an action or change a verdict.
- **Self-review is allowed; self-approval is not** — a review of your own PR is published as a comment, never an approval.
- **One P0/P1/P2 severity model** with a mechanical blocking rule, and an incomplete review is never rendered clean.
- **Execution only on request** — running code is `review-runtime-check`, sandboxed by default; the host needs your explicit authorization.

The decision record, with the reasons and the removed v2 mechanisms, is
[`docs/v3-architecture/`](docs/v3-architecture/README.md).

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
| Docs-only (`docs/`, root `*.md`, `policies/*.md`) | `python3 scripts/validation/ci_test_route.py classify` prints the class, tier, and command CI would use; a `policies/*.md` or `AGENTS.md` change also needs `python3 -m unittest discover -s tests/policy/governance` |
| Benchmark-related (`runtime_platform/benchmark/`, `benchmark/corpus/`, benchmark tooling/tests) | the benchmark test package, e.g. `python3 -m unittest discover -s tests/policy/benchmark` and/or `tests/unit/benchmark` |
| Skill files (`skills/<name>/**`) | `python3 scripts/validation/validate-skill-metadata.py skills/<name> --containment-root .`, plus `python3 -m unittest discover -s tests/unit/review/core` |
| Packaging (`scripts/packaging/**`) | `./scripts/packaging/package-skills.sh all`, plus `python3 -m unittest discover -s tests/integration/packaging` |
| Focused code/test change (`scripts/**`, `tests/**`) | the directly affected module(s); for a test-only change `ci_test_route.py classify` prints the exact command |

If a change doesn't map cleanly, run every test module under the top-level
directory you touched. The full suite runs only in CI.

```bash
python3 scripts/validation/validate-markdown-links.py
```

## Deeper documentation

| Read this | For |
|---|---|
| [GitHub Wiki](https://github.com/amirbena/code-review-skill/wiki) | onboarding and a dated AI code-review landscape comparison (explanatory; never overrides files in this repository) |
| [`skills/review-core/SKILL.md`](skills/review-core/SKILL.md) | the complete, normative Core definition; each mini-skill has its own `SKILL.md` |
| [`docs/migration-v2-to-v3.md`](docs/migration-v2-to-v3.md) · [`docs/features/`](docs/features/README.md) | moving from v2, and one short page per Skill |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | the Core and mini-skill map, rule ownership, and the review lifecycle |
| [`docs/v3-architecture/`](docs/v3-architecture/README.md) | the v3 decision record |
| [`AGENTS.md`](AGENTS.md) + [`policies/`](policies/) | development entrypoint — invariants, instruction precedence, and focused policies |
| [`docs/distribution.md`](docs/distribution.md) · [`docs/RELEASE.md`](docs/RELEASE.md) | installing/updating, and how releases are versioned and published |
| [`SECURITY.md`](SECURITY.md) · [`CHANGELOG.md`](CHANGELOG.md) | reporting a vulnerability privately; notable changes per release |
