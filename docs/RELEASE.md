# Releasing

This repository infers whether a change is **release-worthy** from the
files it touches, so contributors do not maintain a long release
checklist. The rule is deterministic and enforced by
[`../scripts/release_worthiness.py`](../scripts/release_worthiness.py) and
the `Release worthiness` GitHub Action
([`../.github/workflows/release-worthiness.yml`](../.github/workflows/release-worthiness.yml)).

## What counts as release-worthy

A change is release-worthy when it affects either:

- **Shipped Skill content** — anything under `skills/` (each `SKILL.md`,
  its `policies/`, `runbooks/`, `templates/`, `metadata/`), or the shared
  review rules under `shared/` that are packaged into both archives.
- **Packaging / distribution** — the files that determine what the
  shipped archives contain or whether they build:
  `scripts/package-skills.sh`, `scripts/package-skills.ps1`,
  `scripts/validate-skill-metadata.py`.

Everything else is **not** release-worthy on its own: documentation
(including each Skill's `README.md` and `shared/`'s READMEs), tests,
`policies/`, `.github/` workflows, non-packaging scripts, and root
maintenance files such as `CHANGELOG.md` itself.

The classification lives in one place — the module-level constants in
`release_worthiness.py`. Extend it by adding a path prefix or an exact
file name there, with a matching case in
[`../tests/unit/test_release_worthiness.py`](../tests/unit/test_release_worthiness.py).

## CHANGELOG coverage

[`../CHANGELOG.md`](../CHANGELOG.md) is the single durable history. Its
`## Unreleased` section is the staging area for the next release.

- A release-worthy change **must** be represented by at least one bullet
  under `## Unreleased`. Prefer a concise deterministic entry — the PR
  title with its number is enough. Do not paste commit-message prose.
- A change that is not release-worthy does **not** need to touch
  `CHANGELOG.md`. Trivial PRs stay friction-free.
- The PR template carries a `Changelog:` line so the intent is explicit
  in review.

The `Release worthiness` check **fails closed**: if the change is
release-worthy and `## Unreleased` has no entry, the check fails with an
actionable message.

## What the workflow does

On every pull request and every push to `main`, the `assess` job
(read-only) classifies the change set against the previous `v*` tag (or
the PR base) and, when the change is release-worthy:

1. enforces `## Unreleased` coverage (fails closed if missing);
2. builds both archives with `scripts/package-skills.sh all`;
3. verifies archive integrity (`unzip -t` plus the packaging
   runtime-boundary test);
4. uploads the archives and writes a release-preparation summary:
   _"This change affects a Skill or its packaged distribution. A release
   is recommended."_

It does **not** create a tag or publish a GitHub Release.

## Preparing a release

When you are ready to cut `vX.Y.Z`:

1. Run the `Release worthiness` workflow via **Run workflow**
   (`workflow_dispatch`) with the target version. The `release-prep` job
   — the only job granted `contents: write` — rolls `## Unreleased` into
   `## vX.Y.Z — <date>`, rebuilds and verifies the archives, and pushes a
   `release-prep/vX.Y.Z` branch with a `[skip ci]` commit. It never
   commits to `main`, never tags, and never publishes a Release.
2. Open a pull request from `release-prep/vX.Y.Z`, review the rolled
   CHANGELOG, and merge it through the normal review process
   ([`../policies/git-pr-merge-policy.md`](../policies/git-pr-merge-policy.md)).
3. A maintainer then creates the `vX.Y.Z` tag and the GitHub Release,
   with release notes derived from the matching `CHANGELOG.md` section so
   the two stay consistent.

The `assess` side is safe to re-run at any time; re-running step 1 for the
same version needs the previous `release-prep/vX.Y.Z` branch deleted
first. Step 3 stays a deliberate maintainer action.

## Permissions model

| Trigger | Job | Permissions | Runs contributor code | Commits |
| --- | --- | --- | --- | --- |
| `pull_request`, `push` to `main` | `assess` | `contents: read` | yes | no |
| `workflow_dispatch` (maintainer) | `release-prep` | `contents: write` | no (default branch) | pushes `release-prep/*` only |

The workflow never uses `pull_request_target`, never runs
contributor-controlled code with write credentials, and cannot loop:
`release-prep` only runs on manual dispatch, pushes a non-`main` branch,
and marks its commit `[skip ci]`.
