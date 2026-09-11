# Releasing

This repository infers whether a change is **release-worthy** from the
files it touches, takes each release-worthy pull request's CHANGELOG entry
from the **release intent** declared in its description, derives the next
SemVer version from those categories, and publishes the GitHub Release
automatically once the work merges to `main` — contributors maintain
neither a release checklist, a version number, nor `CHANGELOG.md`. The
rules are deterministic (no LLM, agent, or paid per-PR execution) and
enforced by [`../scripts/release_worthiness.py`](../scripts/release_worthiness.py)
and the `Release worthiness` GitHub Action
([`../.github/workflows/release-worthiness.yml`](../.github/workflows/release-worthiness.yml)).

## What counts as release-worthy

A change is release-worthy when it affects either:

- **Shipped Skill content** — anything under `skills/` (each `SKILL.md`,
  its `policies/`, `runbooks/`, `templates/`, `metadata/`), or the shared
  review rules under `shared/` that are packaged into both archives.
- **Packaging / distribution** — the files that determine what the
  shipped archives contain or whether they build:
  `scripts/package-skills.sh`, `scripts/package-skills.ps1`,
  `scripts/package-manifest.json`, `scripts/package_manifest.py`,
  `scripts/validate-skill-metadata.py`.

Everything else is **not** release-worthy on its own: documentation
(including each Skill's `README.md` and `shared/`'s READMEs), tests,
`policies/`, `.github/` workflows, non-packaging scripts, and root
maintenance files such as `CHANGELOG.md` itself.

The classification lives in one place — the module-level constants in
[`../scripts/release_lib/classification.py`](../scripts/release_lib/classification.py).
Extend it by adding a path prefix or an exact file name there, with a
matching case in
[`../tests/unit/test_release_worthiness.py`](../tests/unit/test_release_worthiness.py).

## Release intent

A pull request declares its CHANGELOG entry in its **description**, never by
editing `CHANGELOG.md`. The PR template carries the two lines:

```text
- **Release category:** Fixed
- **Release entry:** Clarify how re-review reconciles resolved threads
```

- `Release category:` is one of `Added`, `Changed`, `Deprecated`, `Fixed`,
  `Security`, `Removed`, `Breaking`, or `none` (case-insensitive; the list
  marker, bold, and backticks are optional). Choose it by the SemVer rules
  below.
- `Release entry:` is one line of prose written for users — not a heading,
  list item, or quote. The PR number is appended at release time
  (`… (#123).`), so there is no need to add it.
- A release-worthy PR **must** declare a real category and an entry.
  `none` — the template default — is for PRs that ship nothing.
- A PR that is not release-worthy needs nothing; a category it declares
  anyway is ignored, and the check says so.

Parsing is strict and deterministic: HTML comments (the template's
guidance) and fenced code blocks are ignored, each line may appear only
once, and prose is never guessed at. Parser:
[`../scripts/release_lib/release_intent.py`](../scripts/release_lib/release_intent.py).

Maintainers may still curate `## Unreleased` by hand, for example a
cross-cutting note. Hand-written bullets must sit under a recognized
`### <Category>` heading; they are kept, and a PR whose `(#N)` already
appears in one is not generated a second time.

## Deterministic SemVer classification

The release's version bump is decided from the **Keep a Changelog
category** of every pending entry — the `Release category:` each merged
pull request declared, which becomes that entry's `### <Category>` heading
under `## Unreleased` — never from free judgement:

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
(`major` > `minor` > `patch`). A change declared `Changed` that actually
breaks compatibility must be declared `Removed` or `Breaking` so the bump
reflects it.

Classification **fails closed**. An unrecognized `Release category:`, or a
hand-written `## Unreleased` entry outside any recognized
`### <Category>` heading or under an unrecognized one, stops the automation
before any tag/release mutation. The PR check catches these at review
time; `release_worthiness.py classify-semver --strict` reports the impact
of the current `## Unreleased` for a maintainer.

### One-time migration

The `## Unreleased` entries that existed before this contract predate the
category rules. They ship as a **single PATCH release** regardless of
their headings: with the latest release at `v1.0.2`, the accumulated
pre-policy set publishes as `v1.0.3`. This is encoded as
`PRE_POLICY_BASELINE_TAG` in
[`../scripts/release_lib/semver_policy.py`](../scripts/release_lib/semver_policy.py)
and retires itself
automatically — once `v1.0.3` is the latest tag, every later release uses
the category rules above. Historical entries can never trigger a `minor`
or `major` bump.

## The global changelog model

[`../CHANGELOG.md`](../CHANGELOG.md) is the single durable history. Release
planning is evaluated over **all changes since the latest `vX.Y.Z` tag**,
and its `## Unreleased` section is **generated** — only by the trusted
release flow on `main`, never on a contributor branch. For each
first-parent commit since that tag that is release-worthy on its own, the
generator:

1. reads the pull request number from the squash-merge subject (`… (#N)`)
   or a `Merge pull request #N` subject;
2. reads that pull request through the GitHub API and requires it to be
   merged, with exactly that commit as its merge commit;
3. parses its release intent and renders `- <entry> (#N).` under
   `### <Category>`.

Sections render in a fixed order (`Breaking`, `Removed`, `Added`,
`Changed`, `Deprecated`, `Fixed`, `Security`), hand-curated bullets first
and generated ones in merge order, so the same repository state always
generates the same bytes. Generation **fails closed**, naming the reason,
in two distinct cases with two distinct fixes:

- the pull request's release intent is missing, malformed, or `none` (or
  the PR cannot be read, or is not the one behind that commit) — edit the
  merged PR's description, then re-run the workflow (`workflow_dispatch`);
- a release-worthy commit's own subject on `main` names no pull request
  (its trailing `(#N)`, or the `Merge pull request #N` form, is missing —
  trailing punctuation such as a period or `!` is tolerated) — this is
  **not** fixed by editing any PR description; the commit itself needs
  correcting (for example, by cutting the next release from a later
  commit once a fixed workflow run is possible, or by a maintainer's
  manual, out-of-band release that advances the baseline tag past it).

Generator:
[`../scripts/release_lib/changelog_generation.py`](../scripts/release_lib/changelog_generation.py).

Release intent is read when the release is planned, so an edit to a merged
PR's description before its release changes the published entry. `plan`
writes the notes it generated to its run summary; with required reviewers
on the `release` Environment, a maintainer sees them before approving
`publish`.

## PR / push checks (read-only)

On every pull request (opened, synchronized, reopened, or its description
edited) and every push to `main`, the `assess` job (`contents: read`,
`persist-credentials: false`) classifies the change set. On a push it
classifies everything since the previous `v*` tag. On a pull request it
classifies only what the PR itself contributes — the diff against the
**merge-base with the PR's current base branch** — so release-worthy
history that entered the branch through a sync/merge from `main` is never
treated as a new obligation for the PR. When the classified set is
release-worthy the job:

1. on a pull request, requires valid release intent in the description
   (fails closed if it is missing, malformed, or `none`), and fails closed
   if a hand-edited `## Unreleased` is unclassifiable;
2. writes a _"release recommended"_ run summary with the proposed bump and
   the exact CHANGELOG entry the release will generate;
3. builds both archives with `scripts/package-skills.sh all`;
4. verifies archive integrity (`unzip -t` plus the packaging
   runtime-boundary test);
5. uploads the archives.

A push to `main` has no PR description, so release intent is not checked
there; `plan` is the authoritative gate.

The PR description reaches the script only through an environment variable
(`--pr-body-env PR_BODY`). It is never interpolated into a shell `run:`
step, never written to `$GITHUB_OUTPUT` or the log, and appears in the run
summary only inside a code fence. The job needs no token, so it behaves
identically on a fork pull request. It never mutates the repository, never
receives the release App credentials, and never creates a tag or a
Release.

## Automatic publication from `main`

Once release-worthy work merges to `main`, the automation publishes it —
no maintainer runs anything, and no one supplies a version.

The read-only **`plan`** job runs on every non-`[skip ci]` push to `main`
(and on `workflow_dispatch` for recovery). It holds `contents: read` and
`pull-requests: read` only and never touches the release App credentials.
It **plans** the release with `release_worthiness.py auto-release-plan`:

- finds the latest valid `vX.Y.Z` tag — the version baseline;
- classifies everything since that tag; if nothing is release-worthy it
  reports `should_release=false` and the job is a **clean no-op**;
- generates `## Unreleased` in memory from the merged PRs' release intent,
  **failing closed** as described above;
- if `## Unreleased` is still empty, it is likewise a no-op;
- derives the bump (`patch` / `minor` / `major`, or `patch` under the
  one-time migration), **failing closed** if classification is ambiguous;
- derives the next version from the baseline tag;
- if that tag already exists, treats the set as already released (no-op) —
  this is what makes a **retry after a completed release** safe; if
  `CHANGELOG.md` already has that version's heading, the release was
  partially published (see below) and it is also a no-op;
- writes the generated release notes to the run summary.

Only when `plan` reports `should_release=true` does the **`publish`** job
run — the sole job granted `contents: write` and the only one behind the
`release` Environment. A merge that ships nothing releasable never starts
it. Its ordered flow fails closed before publishing if any step fails:

1. **Generates** `## Unreleased` from the merged PRs' release intent — the
   same deterministic generation `plan` previewed.
2. **Preflight** — release-worthy changes since the baseline tag,
   `## Unreleased` has notes, `vX.Y.Z` is a valid, not-yet-existing tag.
3. Rolls `## Unreleased` into `## vX.Y.Z — <date>`.
4. Builds **and verifies** both Skill archives (`package-skills.sh all`,
   `unzip -t`, presence checks).
5. Commits the generated, rolled changelog directly to `main`
   (`chore(release): vX.Y.Z [skip ci]`).
6. Pushes that commit and re-fetches to confirm `origin/main` advanced to
   exactly that SHA.
7. Creates an **annotated** `vX.Y.Z` tag at that exact pushed commit.
8. Pushes the tag.
9. Creates the GitHub Release from the tag, notes taken from the matching
   `CHANGELOG.md` section, both verified Skill ZIPs attached.
10. Verifies the live tag commit, `origin/main`, and the published
    Release's tag and assets all match the release commit.

The `release-publish` concurrency group serializes publication. The
release commit is `[skip ci]` and the workflow listens on no tag or
`release` event, so publishing cannot re-enter the flow.

**Retry and recovery.** A re-run after a completed release is a safe
no-op (the accumulated set is already published). If a publish fails
**after** the changelog roll was committed to `main` but before the tag
was pushed, `auto-release-plan` reports nothing to release (`CHANGELOG.md`
already has the `## vX.Y.Z` heading); a maintainer finishes that one
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
it for the protected mutations — it uses the App token instead. It only
uses `GITHUB_TOKEN` to *read* merged pull requests for generation.

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
| `push` to `main` (non-`[skip ci]`), `workflow_dispatch` | `plan` | `contents: read`, `pull-requests: read` | no — checks out `main` | never — generates notes and derives the version in memory |
| after `plan`, when a release is due | `publish` | `contents: write`, `pull-requests: read` | no — checks out `main` | commits to `main`, tags, publishes a Release, using the App token |

- No `pull_request_target`; the read-only jobs check out with
  `persist-credentials: false`. Neither `plan` nor `publish` runs on
  `pull_request`, so contributor-controlled code never reaches the App
  credentials.
- Contributor-controlled text (a PR description) is passed to scripts
  through environment variables or read through the API by trusted code,
  never interpolated into a shell `run:` step. It enters `CHANGELOG.md`
  only through the `publish` job's generation step on `main`; no bot ever
  commits to a contributor or fork branch.
- The write-capable `publish` job checks out `main` and runs only
  repository code from that trusted ref.
- Protected mutations use the App token, never `GITHUB_TOKEN`; branch
  protection is not weakened for anyone else.
- `[skip ci]` on the release commit, the `main`-ref guard, and the
  absence of tag/`release` triggers together prevent recursion.
- The version is always derived (`auto-release-plan`); it is never a
  workflow input, so it cannot be set by an LLM or a contributor.
