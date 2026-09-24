# Installing and updating the Skills

How to install `local-code-review` and `github-pr-review`, keep them
current, and tell which release you have. This page is explanatory; the
publication mechanics are canonical in [`RELEASE.md`](RELEASE.md).

## Which channel

| Channel | Command | Updates | Listed on skills.sh |
| --- | --- | --- | --- |
| skills.sh (`skills` CLI) | `npx skills add amirbena/code-review-skills` | `npx skills update` | yes, once public installs are recorded |
| Claude marketplace | not available yet ([#510](https://github.com/amirbena/code-review-skill/issues/510)) | — | — |
| GitHub Release archive | download `local-code-review-skill.zip` / `github-pr-review-skill.zip` from a release and unzip into your runtime's Skill directory | manual: download the newer archive | **no** |

A direct archive install is **not** equivalent to the skills.sh path: it
sends no install tracking, is never listed on skills.sh, and cannot be
updated with `npx skills update`. Prefer the CLI unless you need an
offline or pinned copy.

## Install with skills.sh

```bash
npx skills add amirbena/code-review-skills --list
npx skills add amirbena/code-review-skills --skill local-code-review --skill github-pr-review
```

`--list` shows the two Skills the repository offers; `--skill` installs
the ones you name. Add `-a <agent>` to choose your runtime, and `--copy`
to copy files instead of symlinking. Each installed Skill is self-contained:
it has its own `SKILL.md`, policies, runbooks, templates, and shared review
rules, and needs nothing from this repository.

## Update

```bash
npx skills update
```

Updates are **release-only**: the distribution repository changes only when
a source release is published, so an update never picks up unreleased work
from `main` of the source repository.

## Which version do I have

- The installed `SKILL.md` carries the release in its frontmatter as
  `metadata.version`.
- The distribution repository's `DISTRIBUTION.json` records the source
  repository, source commit, version, and content hash of a release. The
  installed Skill directories do not include it; read it from the
  repository at the release tag.

## Two repositories, two roles

| | Source repository | Distribution repository |
| --- | --- | --- |
| Where | [`amirbena/code-review-skill`](https://github.com/amirbena/code-review-skill) | `amirbena/code-review-skills` |
| Holds | the Skills' source, shared rules, policies, tests, and release automation | only generated, self-contained Skill trees per release |
| Issues, PRs, contributions | here | disabled; never edited by hand |

Report problems and propose changes in the source repository. The
distribution repository is overwritten by each release.

## How this is verified

- **CI** builds the Skill trees, assembles the exact file set the
  distribution repository publishes, and runs `npx skills add <path> --list`
  and an install against it: exactly both Skills are discovered and every
  link in the installed copies resolves inside them
  ([`test_skills_cli_install.py`](../tests/integration/packaging/test_skills_cli_install.py)).
- **Live check** against the published repository (`npx skills add` for
  both Skills, then `npx skills update` after a following release) is run
  by a maintainer after the first distribution release, on macOS/Linux and
  Windows, and recorded in
  [#511](https://github.com/amirbena/code-review-skill/issues/511).
  skills.sh listing depends on install telemetry from public installs, so
  its appearance is recorded with a date rather than assumed.
