# Installing from the distribution repository

Both Skills are published, on every release, to a generated repository,
[`amirbena/code-review-skills`](https://github.com/amirbena/code-review-skills).
This page says how to install and update from it, which install paths have
been exercised, and how to tell which release you have. It is explanatory;
the publication mechanics are owned by [`RELEASE.md`](RELEASE.md).

## Which repository does what

| | Source repository (`amirbena/code-review-skill`) | Distribution repository (`amirbena/code-review-skills`) |
| --- | --- | --- |
| Purpose | development, issues, PRs, releases, GitHub Release zips | what consumers install from |
| Skill content | `skills/<name>/` source folders (not self-contained: they depend on `shared/`) | `skills/<name>/` built, self-contained trees |
| Edited by | contributors | nobody: generated at release time, never by hand |
| Report problems here | yes | no |

Install from the distribution repository, not from a checkout of the source
repository: the source `skills/<name>/` folders are not standalone.

## Install

Replace `<name>` with `local-code-review` or `github-pr-review`.

| Path | Command | Notes |
| --- | --- | --- |
| skills.sh (`skills` CLI) | `npx skills add amirbena/code-review-skills --skill <name>` | Lists what is available with `--list`. |
| Claude Code marketplace | `/plugin marketplace add amirbena/code-review-skills`, then `/plugin install code-review-skills@code-review-skills` | One plugin exposing both Skills. |
| Codex, Cursor, GitHub Copilot | via the root `plugin.json` (Agent Plugins 1.0.0) | See the table below; not yet exercised. |
| GitHub Release zip | download `local-code-review-skill.zip` or `github-pr-review-skill.zip` from the [source repository's releases](https://github.com/amirbena/code-review-skill/releases) and unzip into your runtime's Skill directory | Manual. Not the same as the paths above; see the note below. |

A direct release-zip install is **not** equivalent to a skills.sh install:
it sends no install telemetry, so it is never counted toward, or listed on,
skills.sh, and it has no update command.

## Compatibility: documented vs. verified

Each row is one of two states. **Verified** means the path was exercised by
a real install from the distribution repository, with evidence recorded in
[#511](https://github.com/amirbena/code-review-skill/issues/511). **Documented**
means the ecosystem's own documentation says it should work and nothing here
has shown that it does. An unexercised path is never to be read as working.

| Ecosystem | State | Evidence |
| --- | --- | --- |
| skills.sh (`skills` CLI): discovery and copy install from the built tree | verified | CI, against a local copy of the built tree: `tests/integration/packaging/test_distribution_consumer_install.py` |
| skills.sh: install from `amirbena/code-review-skills`, `skills update`, listing on skills.sh | documented | pending live evidence in #511 |
| Claude Code marketplace | verified | run locally in #510 (`claude plugin validate`, `marketplace add`, `install`), see [`RELEASE.md`](RELEASE.md); clean-install outcome still to be recorded in #511 |
| Codex Agent Plugin path | documented | pending; the marketplace entry-path (`"./"`) restriction is unresolved |
| Cursor Agent Plugin path ("Import from Repo") | documented | pending |
| GitHub Copilot Agent Plugin path | documented | pending |

Live evidence for each row records the client version, date, command, and
the version observed. A path that fails or cannot be exercised is recorded
as such. Gemini CLI and any vendor-specific adapter are out of scope here.

## Updates

Updates are release-only: the distribution repository changes only when a
new release is published, and the Claude plugin entry pins that release
version, so nothing updates between releases. To pick up a release, use your
client's update command (for the `skills` CLI, `npx skills update`) or
reinstall.

## Which release do I have?

- The installed `SKILL.md` carries the release in its frontmatter
  `metadata.version` field.
- In the distribution repository, `DISTRIBUTION.json` records the version,
  the source repository and commit, and a hash of the published contents.
  Tags `vX.Y.Z` in that repository match the source repository's releases.
