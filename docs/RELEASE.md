# Releasing

This repository infers whether a change is **release-worthy** from the
files it touches, derives the next SemVer version from the CHANGELOG
categories, and publishes the GitHub Release automatically once the work
merges to `main` — contributors maintain neither a release checklist nor
a version number. The rules are deterministic and enforced by
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

## Deterministic SemVer classification

The release's version bump is decided from the **Keep a Changelog
category headings** under `## Unreleased`, never from free judgement. Each
entry must sit under one of these `### <Category>` headings:

| Category | Bump | Meaning |
| --- | --- | --- |
| `Added`, `Changed`, `Deprecated` | **minor** | backward-compatible user-facing capability |
| `Fixed`, `Security` | **patch** | compatible fix or refinement |
| `Removed`, `Breaking` (`Breaking Changes`) | **major** | breaking compatibility change |

Choose between `Changed` and `Fixed` by SemVer intent:

- Use `Changed` for an **intentional backward-compatible behavior or capability
  change**: behavior changes by design, supported behavior broadens or changes,
  workflow or contract semantics change, or users face a new behavioral
  expectation. This is a minor bump.
- Use `Fixed` for a **compatible correction or refinement** that restores or
  cleans up intended behavior without adding a capability. Examples include a
  bug or regression fix; wording, example, or stale runtime-guidance correction;
  product-neutral or compatibility-preserving cleanup; an accompanying
  regression guard; or fail-closed tightening to already-intended semantics.
  This is a patch bump.

**Decision rule:** if users receive a new or intentionally changed capability,
use `Added` or `Changed`; if the change corrects, cleans up, or restores intended
compatible behavior, use `Fixed`. The canonical category-selection contract is
[`../policies/release-changelog-policy.md`](../policies/release-changelog-policy.md).

When entries span several categories, the **highest** bump wins
(`major` > `minor` > `patch`). A `### Changed` entry that actually breaks
compatibility must be moved under `### Removed` or `### Breaking` so the
bump reflects it.

Classification **fails closed**. If `## Unreleased` has an entry outside
any recognized `### <Category>` heading, or under an unrecognized one, the
automation stops before any tag/release mutation and a maintainer must fix
the section. `release_worthiness.py classify-semver` reports the impact;
the PR check runs it with `--strict` so ambiguity is caught at review
time.

### One-time migration

The `## Unreleased` entries that existed before this contract predate the
category rules. They ship as a **single PATCH release** regardless of
their headings: with the latest release at `v1.0.2`, the accumulated
pre-policy set publishes as `v1.0.3`. This is encoded as
`PRE_POLICY_BASELINE_TAG` in `release_worthiness.py` and retires itself
automatically — once `v1.0.3` is the latest tag, every later release uses
the category rules above. Historical entries can never trigger a `minor`
or `major` bump.

## The global changelog model

[`../CHANGELOG.md`](../CHANGELOG.md) is the single durable history.
Release worthiness is always evaluated over **all changes since the
previous `v*` tag**, and `## Unreleased` is the coverage for that whole
release set — **not one entry per pull request**.

- A release-worthy change **must** be represented by at least one bullet
  under `## Unreleased`, beneath a recognized `### <Category>` heading
  (see **Deterministic SemVer classification**), before a release is cut.
  Prefer a concise deterministic entry — a PR title with its number is
  enough. Do not paste commit-message prose.
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
2. classifies the proposed SemVer impact with `classify-semver --strict`
   (fails closed if the section is ambiguous — see above);
3. builds both archives with `scripts/package-skills.sh all`;
4. verifies archive integrity (`unzip -t` plus the packaging
   runtime-boundary test);
5. uploads the archives and writes a _"release recommended"_ summary that
   names the proposed bump.

It never mutates the repository, it never receives the release App
credentials, and it never creates a tag or a Release.

## Automatic publication from `main`

Once release-worthy work merges to `main`, the automation publishes it —
no maintainer runs anything, and no one supplies a version.

The read-only **`plan`** job runs on every non-`[skip ci]` push to `main`
(and on `workflow_dispatch` for recovery). It holds no write permission
and never touches the release App credentials. It **plans** the release
with `release_worthiness.py auto-release-plan`:

- finds the latest valid `vX.Y.Z` tag — the version baseline;
- classifies everything since that tag; if nothing is release-worthy it
  reports `should_release=false` and the job is a **clean no-op**;
- if `## Unreleased` has no entries (the accumulated set is already
  released), it is likewise a no-op — this is what makes a **retry after a
  completed release** safe;
- derives the bump (`patch` / `minor` / `major`, or `patch` under the
  one-time migration), **failing closed** if classification is ambiguous;
- derives the next version from the baseline tag;
- if that tag already exists, treats the set as already released (no-op).

Only when `plan` reports `should_release=true` does the **`publish`** job
run — the sole job granted `contents: write` and the only one behind the
`release` Environment. A merge that ships nothing releasable never starts
it. Its ordered flow fails closed before publishing if any step fails:

1. **Preflight** — release-worthy changes since the baseline tag,
   `## Unreleased` has notes, `vX.Y.Z` is a valid, not-yet-existing tag.
2. Rolls `## Unreleased` into `## vX.Y.Z — <date>`.
3. Builds **and verifies** both Skill archives (`package-skills.sh all`,
   `unzip -t`, presence checks).
4. Commits the changelog roll directly to `main`
   (`chore(release): vX.Y.Z [skip ci]`).
5. Pushes that commit and re-fetches to confirm `origin/main` advanced to
   exactly that SHA.
6. Creates an **annotated** `vX.Y.Z` tag at that exact pushed commit.
7. Pushes the tag.
8. Creates the GitHub Release from the tag, notes taken from the matching
   `CHANGELOG.md` section, both verified Skill ZIPs attached.
9. Verifies the live tag commit, `origin/main`, and the published
   Release's tag and assets all match the release commit.

The `release-publish` concurrency group serializes publication. The
release commit is `[skip ci]` and the workflow listens on no tag or
`release` event, so publishing cannot re-enter the flow.

**Retry and recovery.** A re-run after a completed release is a safe
no-op (the accumulated set is already published). If a publish fails
**after** the changelog roll was committed to `main` but before the tag
was pushed, `auto-release-plan` will report nothing to release (the
`## Unreleased` section is already rolled); a maintainer finishes that one
release by hand — tag the pushed `chore(release): vX.Y.Z` commit and
`gh release create` from it — after which automation resumes normally.

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
  actor that can push the automatic release commit.

The built-in `GITHUB_TOKEN` (the “GitHub Actions” actor) **cannot** be
selected as a ruleset bypass actor, so the `publish` job does not rely on
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

The `publish` job mints a short-lived installation token with
[`actions/create-github-app-token`](https://github.com/actions/create-github-app-token)
and uses it for every `git push` and `gh release` call. The token
expires in ~1 hour and is scoped to this repo's contents.

### 3. Optional hardening — `release` Environment

The `publish` job declares `environment: release`. Add **required
reviewers** to that Environment (Settings → Environments → `release`) so
each automatic publish needs a maintainer's approval, and restrict it to
the `main` branch. Because `publish` starts only when a release is
actually due, this prompts a maintainer per real release, not per merge.
If the Environment has no rules it simply passes through.

## Permissions model

| Trigger | Job | `permissions` | Runs contributor code | Mutates repo |
| --- | --- | --- | --- | --- |
| `pull_request`, `push` to `main` | `assess` | `contents: read` | yes | never |
| `push` to `main` (non-`[skip ci]`), `workflow_dispatch` | `plan` | `contents: read` | no — checks out `main` | never — derives the version only |
| after `plan`, when a release is due | `publish` | `contents: write` | no — checks out `main` | commits to `main`, tags, publishes a Release, using the App token |

- No `pull_request_target`; the read-only jobs check out with
  `persist-credentials: false`. Neither `plan` nor `publish` runs on
  `pull_request`, so contributor-controlled code never reaches the App
  credentials.
- The write-capable `publish` job checks out `main` and runs only
  repository code from that trusted ref.
- Protected mutations use the App token, never `GITHUB_TOKEN`; branch
  protection is not weakened for anyone else.
- `[skip ci]` on the release commit, the `main`-ref guard, and the
  absence of tag/`release` triggers together prevent recursion.
- The version is always derived (`auto-release-plan`); it is never a
  workflow input, so it cannot be set by an LLM or a contributor.
