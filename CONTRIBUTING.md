# Contributing

Contributions are welcome. You do not need maintainer permission before
starting an open issue labeled `help wanted` or `good first issue`.

## Choose and claim an issue

1. Choose an open, unclaimed issue with one of the contribution-ready labels.
2. Comment `/claim`. The bot adds `claimed` and records you as the claimant.
3. If you stop working on it, comment `/unclaim` so someone else can take it.

Claims do not use GitHub assignees, so contributors do not need repository
write access. A claim is a coordination signal, not a guarantee that a pull
request will be merged.

If a claim has no meaningful contributor activity for seven days, a
maintainer may release it with `/unclaim`. Maintainers should first check for
a linked pull request that is still progressing.

## Make the change

1. Fork the repository.
2. Create a focused branch in your fork using the convention below.
3. Implement the issue without adding unrelated changes.
4. Run the relevant validation listed in the root [README](README.md#contributing-to-this-repository).
5. Open a pull request against this repository and use `Fixes #<issue>` when
   the pull request should close the issue.

The issue form should define the problem, scope, acceptance criteria, and
validation before work is claimed. Ask on the issue if those boundaries are
unclear.

### Branch names

Use `<type>/<short-description>`, with a lowercase, concise, descriptive
kebab-case name for one logical task:

| Prefix | Use for |
| --- | --- |
| `feat/` | New functionality |
| `fix/` | Bug fixes |
| `docs/` | Documentation-only changes |
| `test/` | Test-only changes |
| `refactor/` | Restructuring without intended behavior changes |
| `chore/` | Repository, tooling, or maintenance work |
| `research/` | Research or analysis without implementation |

Describe the work, not its author: do not include usernames, coding-agent
names, timestamps, or random identifiers. An Issue number is optional (for
example, `fix/42-checkpoint-recovery`); the rest of the name must remain
understandable without GitHub. Good standalone names include
`chore/open-source-release-readiness` and `docs/contribution-workflow`.

## Changelog

You do not need to touch `CHANGELOG.md` for a trivial change. You **do**
need one bullet under `## Unreleased` when your change is *release-worthy*
— it affects shipped Skill content (`skills/`, packaged `shared/`) or the
packaging/distribution scripts. A concise entry (your PR title with its
number) is enough; do not paste commit prose.

The PR template has a `Changelog:` line for stating this explicitly, and
the `Release worthiness` check fails closed if a release-worthy change has
no `## Unreleased` entry. Full convention: [`docs/RELEASE.md`](docs/RELEASE.md).

## Review and merge

Starting work does not require approval; merging does. `main` remains
protected, and every pull request must satisfy the repository's checks and
review requirements before an authorized maintainer merges it. Claiming an
issue never bypasses review or guarantees merge.
