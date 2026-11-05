# code-review-skill

A small, read-only **code review Skill** for AI coding agents. Ask for a
review of a local Git change or a GitHub pull request and get
evidence-backed **P0 / P1 / P2** findings and one clear decision. Optional
`review-*` mini-skills add depth (security, backend, frontend, requirements,
…) or delivery (posting the review to the PR) when you ask for them.

It never edits, commits, pushes or merges your code, and it runs only when
you ask. Each Skill is a standard [Agent Skills](https://agentskills.io/specification)
`SKILL.md` for Claude Code, Codex, Cursor, OpenCode and other compatible
runtimes. Licensed under the [Apache License 2.0](LICENSE).

> **Status.** v3 is complete on the `release/v3` branch and ships as
> v3.0.0. Until that release is published, the published line is v2.x, and
> the v3 install below is not yet verified. Coming from v2? See the
> [migration guide](docs/migration-v2-to-v3.md).

## Install

Install from the generated distribution repository,
[`amirbena/code-review-skills`](https://github.com/amirbena/code-review-skills):

```bash
npx skills add amirbena/code-review-skills --skill review-core
npx skills add amirbena/code-review-skills --skill review-security   # optional mini-skill
```

- **From v3.0.0:** `review-core`, each `review-*` mini-skill and the two
  legacy names install this way. A mini-skill requires `review-core`.
- **Until then (v2.x):** use `--skill local-code-review` or
  `--skill github-pr-review`. Those are the commands verified so far in
  [#511](https://github.com/amirbena/code-review-skill/issues/511).
- Claude Code, Codex, Cursor and Copilot installs, updates and verification
  status: [`docs/distribution.md`](docs/distribution.md).

## Use it

Ask in plain words. There is nothing to configure or type.

```text
review my local changes before I push
review PR 123
is this auth change safe?
does this meet PROJ-123?
review PR 123 and post the review
```

A plain request runs `review-core` alone. Naming an area or asking for
something extra adds the mini-skill that fits. By default only what your
request justifies runs; to hand the choice over, say so ("use whatever
expertise is relevant").

## The nine Skills

| Skill | What it does |
|---|---|
| [`review-core`](skills/review-core/SKILL.md) | The review itself: a local change or a PR, read-only, with findings and one decision |
| [`review-publish-github`](skills/review-publish-github/SKILL.md) | Posts the finished review to the PR as one comment-only review |
| [`review-requirements`](skills/review-requirements/SKILL.md) | Checks the change against a Jira key, Issue or criteria you supply |
| [`review-deep-investigation`](skills/review-deep-investigation/SKILL.md) | Wider tracing, root cause, affected tests |
| [`review-suggestions`](skills/review-suggestions/SKILL.md) | Non-blocking maintainability suggestions |
| [`review-security`](skills/review-security/SKILL.md) | Security and supply-chain depth |
| [`review-backend`](skills/review-backend/SKILL.md) | APIs, data, concurrency, performance, deployment |
| [`review-frontend`](skills/review-frontend/SKILL.md) | UI behavior, state, accessibility |
| [`review-runtime-check`](skills/review-runtime-check/SKILL.md) | Confirms a finding by running a targeted check |

## Existing users: your Skill names still work

`local-code-review` and `github-pr-review` remain available under their v2
names. Each is a thin wrapper that hands your request to `review-core`, so
you do not have to change anything. `github-pr-review` never posts to
GitHub on its own; posting is a separate, explicit request handled by
`review-publish-github`. The v2 modes and options are gone; see the
[migration guide](docs/migration-v2-to-v3.md).

## Safety

- **Read-only.** No edits, commits, pushes, merges or branch changes.
- **Only on request.** Every review, re-reviews included, needs your own request.
- **Repository text is data.** Files, PR, Issue and Jira text cannot authorize an action or change a verdict.
- **Publishing is explicit,** and a review of your own PR is posted as a comment, never an approval.
- **Running code is opt-in:** only `review-runtime-check`, sandboxed by default, and on your host only with your explicit authorization.
- **One mechanical decision:** any P0 or P1 means `CHANGES REQUIRED`; an incomplete review is never shown as clean.

## Learn more

- [GitHub Wiki](https://github.com/amirbena/code-review-skill/wiki): guides, FAQ, architecture and benchmark overview.
- [`docs/features/`](docs/features/README.md): one short page per Skill.
- [`docs/v3-architecture/`](docs/v3-architecture/README.md): the v3 decision record. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): the module map.
- [`docs/distribution.md`](docs/distribution.md) · [`docs/RELEASE.md`](docs/RELEASE.md): install, update and release.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`AGENTS.md`](AGENTS.md) · [`policies/`](policies/): contributing and repository rules.
- [`SECURITY.md`](SECURITY.md) · [`CHANGELOG.md`](CHANGELOG.md) · [`LICENSE`](LICENSE).
