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
| Claude Code marketplace | verified | Claude Code 2.1.272, macOS, 2026-09-24, v1.56.0. **Install:** `marketplace add` + `install` from the published repository gave plugin 1.56.0. **Discovery:** both Skills loaded. **Runtime:** `local-code-review` ran scope discovery, found an empty delta, and returned a vacuous `REVIEW CLEAN` with no invented findings; `github-pr-review`, invoked without a valid PR, asked for a PR target and publication mode and made no GitHub write |
| Codex | `codex plugin marketplace add amirbena/code-review-skills`, then `codex plugin add code-review-skills@code-review-skills` | Reads the same `.claude-plugin/marketplace.json`. |
| GitHub Copilot CLI | `copilot plugin marketplace add amirbena/code-review-skills`, then `copilot plugin install code-review-skills@code-review-skills` | Direct `copilot plugin install amirbena/code-review-skills` also works but its CLI warns that direct installs are deprecated. |
| Cursor | install from `amirbena/code-review-skills` in the Cursor app (documented entry point: "Import from Repo") | No Cursor-specific file is needed; see the table below for what was tested. |
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

| Ecosystem | State | Evidence (client, date, observed version) |
| --- | --- | --- |
| CI: `skills` CLI discovery and copy install from the built tree | verified | `tests/integration/packaging/test_distribution_consumer_install.py` (#520) |
| skills.sh: `npx skills add amirbena/code-review-skills --skill <name>` for both Skills | verified | `skills` 1.7.0, macOS, 2026-09-24: both installed, `metadata.version` 1.56.0 |
| skills.sh: `skills update` picking up a newer release | documented | ran `npx skills update -p -y` at 1.56.0 (refreshed both, no newer release exists); a real update needs a subsequent release |
| skills.sh listing | documented | 2026-09-24: per-Skill pages exist under `skills.sh/amirbena/code-review-skills/`, but the directory search does not return the Skills yet (listing depends on install telemetry); re-check after a release |
| Claude Code marketplace | verified | Claude Code 2.1.272, macOS, 2026-09-24, fresh config directory: `marketplace add` + `install` gave plugin 1.56.0 with both Skills |
| Codex Agent Plugin path | verified | Codex CLI 0.156.1 (from the earlier install run; the version of the later runtime run was not re-captured), macOS, 2026-09-24, v1.56.0. **Install:** `plugin marketplace add` + `plugin add` gave 1.56.0. **Discovery and runtime:** both Skills were discovered and invoked. The `"./"` entry path did not block it, so no Codex adapter or separate marketplace entry is needed. Reading only the root `plugin.json`, without the marketplace file, was not exercised |
| GitHub Copilot Agent Plugin path | verified | Copilot CLI 1.0.88, macOS, 2026-09-24: direct install and `marketplace add` + `install` both gave 1.56.0 with two Skills. Not run against a pinned tag |
| Cursor Agent Plugin path | verified | Cursor 3.17.8 (installed app version), macOS, 2026-09-24, manual test of v1.56.0. **Install and discovery:** both Skills installed from `amirbena/code-review-skills`. **Runtime:** both invoked successfully. No Cursor adapter or `.cursor-plugin` was needed. The exact UI steps were not recorded, so "Import from Repo" itself is not claimed as the tested path |

Windows was not exercised for any path.

"Verified" here covers install, discovery, and (where the row says so) a
runtime smoke invocation of the distributed Skills. It is not a review-quality
validation: the smoke runs show the Skills load, follow their input contract,
and do not invent findings, not that their reviews are correct.

Evidence records the client version, date, and the version observed. A path that fails or cannot be exercised is recorded
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
