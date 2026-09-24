# Installing, updating, and verifying the distributed Skills

This is the consumer-facing guide for installing and updating
`local-code-review` and `github-pr-review`, and for seeing which install
paths have actually been exercised. It is explanatory; the publication
mechanics are owned by [`RELEASE.md`](RELEASE.md).

**Recommended:** install from the generated distribution repository,
[`amirbena/code-review-skills`](https://github.com/amirbena/code-review-skills),
through your tool's own Skill or plugin mechanism (below). Downloading and
copying release ZIPs by hand is a fallback, covered last under
[Manual / offline installation](#manual--offline-installation).

## Why a distribution repository

```text
source repository (amirbena/code-review-skill)
       ↓
canonical deterministic build
       ↓
amirbena/code-review-skills   (generated, never edited by hand)
       ↓
skills.sh / Claude Code / Codex / Cursor / GitHub Copilot
```

- The source repository stays canonical for development, issues, PRs and
  releases. Its `skills/<name>/` folders are not standalone (they depend on
  `shared/`), so do not install from a checkout of it.
- Each release builds deterministic, self-contained Skill trees. The
  distribution repository is the consumer-facing publication surface for
  those trees.
- Every consumer therefore receives the same canonical Skill trees.
  Vendor-specific metadata (the Claude marketplace file, the portable
  `plugin.json`) is an adapter around those trees and does not change the
  Skill content.

Build and publication details: [`RELEASE.md`](RELEASE.md), "Generated
distribution repository" and "Publishing each release to the distribution
repository".

## Install by consumer

Use `<name>` = `local-code-review` or `github-pr-review`. Every command below
was run during [#511](https://github.com/amirbena/code-review-skill/issues/511)
(client versions in the matrix).

| Consumer | Install |
| --- | --- |
| skills CLI / skills.sh | `npx skills add amirbena/code-review-skills --skill <name>` (`--list` shows what is available) |
| Claude Code | `/plugin marketplace add amirbena/code-review-skills`, then `/plugin install code-review-skills@code-review-skills` (one plugin, both Skills) |
| Codex | `codex plugin marketplace add amirbena/code-review-skills`, then `codex plugin add code-review-skills@code-review-skills` (reads the same `.claude-plugin/marketplace.json`) |
| Cursor | install from `amirbena/code-review-skills` in the Cursor app; the exact UI steps were not recorded, so "Import from Repo" is not claimed as the tested path |
| GitHub Copilot CLI | `copilot plugin marketplace add amirbena/code-review-skills`, then `copilot plugin install code-review-skills@code-review-skills`; a direct `copilot plugin install amirbena/code-review-skills` also worked, but the CLI warns direct installs are deprecated |

The `skills` run in #511 targeted Claude Code (`-a claude-code --copy`).

## Updating

Updates are release-only: the distribution repository changes only when a
release is published, and the plugin entry pins that release version, so
nothing changes between releases. **Update mechanisms are consumer-specific.**
`npx skills update` manages Skills installed by the `skills` CLI; it does not
update Claude Code, Codex, Cursor, or Copilot plugin installations, which use
their own tools.

| Consumer | Update path | State |
| --- | --- | --- |
| skills CLI / skills.sh | `npx skills update` | **pending verification**: run once at v1.56.0 it only refreshed the same version. A real cross-release update can only be verified after a later release |
| Codex | the CLI documents `plugin marketplace upgrade` | documented, not exercised |
| GitHub Copilot CLI | the CLI documents `plugin update` | documented, not exercised |
| Claude Code | the plugin/marketplace update flow of Claude Code | documented, not exercised |
| Cursor | not investigated | not exercised |

If in doubt, reinstall from the distribution repository. Installing
successfully is never evidence that a path's update mechanism works.

## Compatibility and verification

**Verified** means exercised by a real run against the published
distribution repository, with evidence recorded in
[#511](https://github.com/amirbena/code-review-skill/issues/511).
**Documented** means the tool's own documentation says it should work and
nothing here has shown that it does. A "not recorded" or "not verified" cell
is unverified, never assumed working.

All runs below are v1.56.0, macOS, 2026-09-24.

| Consumer (client version) | Installation | Discovery of both Skills | Runtime smoke | Update |
| --- | --- | --- | --- | --- |
| CI, `skills` CLI against a local copy of the built tree | verified | verified | not applicable | not applicable |
| skills CLI / skills.sh (`skills` 1.7.0) | verified | verified | not recorded | pending verification |
| Claude Code (2.1.272) | verified | verified | verified | not verified |
| Codex (CLI 0.156.1) | verified | verified | verified | not verified |
| Cursor (3.17.8, installed app version) | verified | verified | verified | not verified |
| GitHub Copilot (CLI 1.0.88) | verified | verified (the CLI reported two installed Skills) | not recorded | not verified |

Notes on the evidence:

- **skills.sh listing:** per-Skill pages exist under
  `skills.sh/amirbena/code-review-skills/`, but the directory search did not
  return the Skills on 2026-09-24. Listing depends on install telemetry;
  re-check after a later release.
- **Claude Code:** `local-code-review` ran scope discovery, found an empty
  delta, and returned a vacuous `REVIEW CLEAN` with no invented findings.
  `github-pr-review`, invoked without a valid PR, asked for a PR target and
  publication mode and made no GitHub write.
- **Codex:** no Codex adapter was needed; the `"./"` marketplace entry path
  did not block installation. The version shown is from the install run and
  was not re-captured for the later runtime run. Reading only the root
  `plugin.json`, without the marketplace file, was not exercised.
- **Cursor:** no Cursor adapter or `.cursor-plugin` was needed. The version is
  the locally installed app version.
- **Copilot:** tested through both the marketplace and the direct install;
  not run against a pinned tag.
- **Not exercised anywhere:** Windows, and a clean machine (runs used isolated
  config directories).

**What "runtime smoke" means.** It shows that the distributed Skill can be
discovered, loaded, and invoked, and that it follows its basic invocation and
input contract. It does not show that reviews are correct. Review behavior
and quality are validated separately by the repository's deterministic tests
and benchmark system.

## Which release do I have?

- The installed `SKILL.md` carries the release in its frontmatter
  `metadata.version` field.
- In the distribution repository, `DISTRIBUTION.json` records the version,
  the source repository and commit, and a hash of the published contents.
  Tags `vX.Y.Z` there match the source repository's releases.

## Manual / offline installation

Use this only when managed installation is unavailable: offline machines,
archival, or debugging. Download `local-code-review-skill.zip` or
`github-pr-review-skill.zip` from the
[source repository's releases](https://github.com/amirbena/code-review-skill/releases)
and unzip it into your runtime's Skill directory (for example
`.claude/skills/<name>/`, `.agents/skills/<name>/`, or `.cursor/skills/<name>/`);
each archive keeps `SKILL.md` at its root. To build an archive yourself, see
the root [README](../README.md#install).

A ZIP install is **not** equivalent to a managed install: it sends no install
telemetry, so it is never counted toward or listed on skills.sh, it has no
update command, and none of the verification above applies to it.
