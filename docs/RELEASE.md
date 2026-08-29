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

## The global changelog model

[`../CHANGELOG.md`](../CHANGELOG.md) is the single durable history.
Release worthiness is always evaluated over **all changes since the
previous `v*` tag**, and `## Unreleased` is the coverage for that whole
release set — **not one entry per pull request**.

- A release-worthy change **must** be represented by at least one bullet
  under `## Unreleased` before a release is cut. Prefer a concise
  deterministic entry — a PR title with its number is enough. Do not
  paste commit-message prose.
- A change that is not release-worthy does **not** need to touch
  `CHANGELOG.md`. Trivial PRs stay friction-free.
- The PR template carries a `Changelog:` line so the intent is explicit
  in review.

The `Release worthiness` PR/push check **fails closed**: if the change
set since the last tag is release-worthy and `## Unreleased` has no
entry, the check fails with an actionable message.

## PR / push checks (read-only)

On every pull request and every push to `main`, the `assess` job
(`contents: read`, `persist-credentials: false`) classifies the change
set against the previous `v*` tag (or the PR base) and, when it is
release-worthy:

1. enforces `## Unreleased` coverage (fails closed if missing);
2. builds both archives with `scripts/package-skills.sh all`;
3. verifies archive integrity (`unzip -t` plus the packaging
   runtime-boundary test);
4. uploads the archives and writes a _"release recommended"_ summary.

It never mutates the repository, and it never creates a tag or a Release.

## Cutting a release (authoritative direct-to-main flow)

A release is published only by a maintainer running the `Release
worthiness` workflow via **Run workflow** (`workflow_dispatch`) with the
target `version` (e.g. `1.0.3`, no leading `v`). The `release` job — the
only job granted `contents: write` — then, in order and **failing closed
before publishing** if any step fails:

1. **Preflight** — confirms there are release-worthy changes since the
   previous `v*` tag, that `## Unreleased` has release notes, and that
   `vX.Y.Z` is a valid, not-yet-existing tag.
2. Fails closed if `## Unreleased` has no notes.
3. Validates the semantic version and that the tag is new (local and
   `origin`).
4. Rolls `## Unreleased` into `## vX.Y.Z — <date>` with the release date.
5. Builds **and verifies** both Skill archives (`package-skills.sh all`,
   `unzip -t`, presence checks).
6. Commits the changelog roll directly to `main`
   (`chore(release): vX.Y.Z [skip ci]`).
7. Pushes that commit to `main` and re-fetches to confirm `origin/main`
   advanced to exactly that SHA.
8. Creates an **annotated** `vX.Y.Z` tag pointing at that exact pushed
   commit.
9. Pushes the tag.
10. Creates the GitHub Release from the tag, with notes taken from the
    matching `CHANGELOG.md` section, and attaches both verified Skill
    ZIPs.
11. Verifies the live tag commit, `origin/main`, and the published
    Release's tag and assets all match the release commit before
    reporting success.

No separate `release-prep` branch, no manual tagging step. The workflow
does not listen on tag pushes or on `release` events, and the commit is
`[skip ci]`, so publishing a release cannot re-enter the workflow.

## Repository configuration

Direct pushes to `main` stay **blocked for every human and for the
built-in Actions token**. Only the trusted release automation is exempt,
through a dedicated GitHub App added as the sole bypass actor.

### 1. `main` branch ruleset

Create a **repository ruleset** targeting `main` (Settings → Rules →
Rulesets) with:

- **Restrict deletions**, **Block force pushes**.
- **Require a pull request before merging** (≥1 approval, dismiss stale
  approvals, require review from Code Owners as today).
- **Require status checks to pass**: `Validate repository` and the
  `Release worthiness` `assess` job.
- **Bypass list: the “Skill Release Automation” GitHub App only.** Do
  **not** add `Repository admin`, `Maintain`, `Organization admin`, or
  any team. Humans always go through a pull request; the App is the only
  actor that can push the release commit.

The built-in `GITHUB_TOKEN` (the “GitHub Actions” actor) **cannot** be
selected as a ruleset bypass actor, so the release job does not rely on
it for the protected mutations — it uses the App token instead.

### 2. The “Skill Release Automation” GitHub App

- **Create** a GitHub App (org- or user-owned) with repository
  permissions **Contents: Read and write** and **Metadata: Read-only**
  — nothing else. No webhook.
- **Install** it on this repository only.
- **Add** the App to the `main` ruleset bypass list (step 1).
- **Store** its credentials as repository secrets
  (or, better, as secrets on a protected `release` Environment):
  `RELEASE_APP_ID` and `RELEASE_APP_PRIVATE_KEY`.

The `release` job mints a short-lived installation token with
[`actions/create-github-app-token`](https://github.com/actions/create-github-app-token)
and uses it for every `git push` and `gh release` call. The token
expires in ~1 hour and is scoped to this repo's contents.

### 3. Optional hardening — `release` Environment

The `release` job declares `environment: release`. Add **required
reviewers** to that Environment (Settings → Environments → `release`) so
each publish needs a second maintainer's approval, and restrict it to
the `main` branch. If the Environment has no rules it simply passes
through.

## Permissions model

| Trigger | Job | `permissions` | Runs contributor code | Mutates repo |
| --- | --- | --- | --- | --- |
| `pull_request`, `push` to `main` | `assess` | `contents: read` | yes | never |
| `workflow_dispatch` (maintainer) | `release` | `contents: write` | no — checks out `main` | commits to `main`, tags, publishes a Release, using the App token |

- No `pull_request_target`; the read-only job checks out with
  `persist-credentials: false`.
- The write-capable job is `workflow_dispatch`-only and never runs
  contributor-controlled code.
- Protected mutations use the App token, never `GITHUB_TOKEN`; branch
  protection is not weakened for anyone else.
- `[skip ci]` on the release commit plus the absence of tag/`release`
  triggers prevents recursion.
