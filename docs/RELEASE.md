# Releasing

This repository infers whether a change is **release-worthy** from the
files it touches, takes each release-worthy pull request's CHANGELOG entry
from the **release intent** declared in its description, derives the next
SemVer version from those categories, and publishes the GitHub Release
automatically once the work merges to `main` — contributors maintain
neither a release checklist, a version number, nor `CHANGELOG.md`. The
rules are deterministic (no LLM, agent, or paid per-PR execution) and
enforced by [`../scripts/release/release_worthiness.py`](../scripts/release/release_worthiness.py)
through two GitHub Actions workflows that share that same classification
and changelog engine:

- **`Release worthiness`**
  ([`../.github/workflows/release-worthiness.yml`](../.github/workflows/release-worthiness.yml))
  — the PR lifecycle. Triggered only by `pull_request`. A read-only
  preview: `release-gate` (the required check) plus the conditional
  `package` job. It never builds a release and never touches `main`.
- **`Release publish`**
  ([`../.github/workflows/release-publish.yml`](../.github/workflows/release-publish.yml))
  — the main/release lifecycle. Triggered only by `push` to `main` and,
  for recovery, `workflow_dispatch` — never by `pull_request`, so its
  `plan` and `publish` jobs never exist as PR check runs. It recomputes
  the authoritative release assessment itself; it never trusts or
  consumes a previous PR-time `release-gate` result.

## What counts as release-worthy

A change is release-worthy when it affects either:

- **Shipped Skill content** — anything under `skills/` (each `SKILL.md`,
  its `policies/`, `runbooks/`, `templates/`, `metadata/`), or the shared
  review rules under `shared/` that are packaged into both archives.
- **Packaging / distribution** — the files that determine what the
  shipped archives contain or whether they build:
  `scripts/packaging/package-skills.sh`, `scripts/packaging/package-skills.ps1`,
  `scripts/packaging/package-manifest.json`, `scripts/packaging/package_manifest.py`,
  `scripts/packaging/package_adapt.py`, `scripts/validation/validate-skill-metadata.py`.

Everything else is **not** release-worthy on its own: documentation
(including each Skill's `README.md` and `shared/`'s READMEs), tests,
`policies/`, `.github/` workflows, non-packaging scripts, and root
maintenance files such as `CHANGELOG.md` itself.

The classification lives in one place — the module-level constants in
[`../scripts/release/release_lib/classification.py`](../scripts/release/release_lib/classification.py).
Extend it by adding a path prefix or an exact file name there, with a
matching case in
[`../tests/unit/release/test_path_classification.py`](../tests/unit/release/test_path_classification.py).

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
[`../scripts/release/release_lib/release_intent.py`](../scripts/release/release_lib/release_intent.py).

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
[`../scripts/release/release_lib/semver_policy.py`](../scripts/release/release_lib/semver_policy.py)
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
[`../scripts/release/release_lib/changelog_generation.py`](../scripts/release/release_lib/changelog_generation.py).

Release intent is read when the release is planned, so an edit to a merged
PR's description before its release changes the published entry. `plan`
writes the notes it generated to its run summary; with required reviewers
on the `release` Environment, a maintainer sees them before approving
`publish`.

## PR checks (read-only)

### `release-gate` — the required, always-created check

`release-gate` (`contents: read`, `persist-credentials: false`) is the
**stable, required PR-level check**, defined in the PR-triggered
`release-worthiness.yml`. It runs on every pull request (opened,
synchronized, reopened, or its description edited) — this workflow is
never triggered by `push` — and it always reaches a terminal, explicit
result:

```text
PR
 ↓
release-gate always evaluates
 ↓
is release assessment applicable?
 ├─ no  → PASS — "Release gate: not applicable" (explicit, not skipped)
 └─ yes → existing assess --require-release-intent
             ├─ valid   → PASS
             └─ invalid → FAIL
```

It classifies only what the PR itself contributes — the diff against the
**merge-base with the PR's current base branch** — so release-worthy
history that entered the branch through a sync/merge from `main` is never
treated as a new obligation for the PR. This is a read-only preview: the
authoritative assessment of everything accumulated since the previous
`v*` tag happens separately, on `main`, in `release-publish.yml`'s `plan`
job (see "Automatic publication from `main`" below) — `release-gate`'s
per-PR verdict is never trusted or reused there.

The applicability decision ("is this PR release-relevant?") is not a
workflow-YAML `paths:` filter or job `if:` condition — it is the same
`scripts/release/release_worthiness.py assess` classification the job always
runs, from `scripts/release/release_lib/classification.py`. The job:

1. classifies the change set;
2. when **not** release-worthy, writes an explicit `## Release gate: not
   applicable` run summary and exits successfully — this is a distinct,
   intentional outcome, not an absent or skipped check;
3. when release-worthy and given a pull request, requires valid release
   intent in the description (fails closed if missing, malformed, or
   `none`), and fails closed if a hand-edited `## Unreleased` is
   unclassifiable; on a pass it writes a _"release recommended"_ run
   summary with the proposed bump and the exact CHANGELOG entry the
   release will generate.

`release-gate` never builds, verifies, or uploads anything — it does not
depend on packaging succeeding, so a packaging regression can never fail
this required check. Its identity (the job id, which is the GitHub check
context "Release worthiness / release-gate") stays constant regardless of
how packaging is implemented.

The PR description reaches the script only through an environment variable
(`--pr-body-env PR_BODY`). It is never interpolated into a shell `run:`
step, never written to `$GITHUB_OUTPUT` or the log, and appears in the run
summary only inside a code fence. The job needs no token, so it behaves
identically on a fork pull request (see "Fork / first-time-contributor
workflow approval" below for the one residual gap this does not close).
It never mutates the repository, never receives the release App
credentials, and never creates a tag or a Release.

### `package` — conditional, non-required packaging work

`package` (`contents: read`) `needs: release-gate` and runs only when
`needs.release-gate.outputs.release_worthy == 'true'` — the same
classification output `release-gate` already computed, not a second
relevance decision. It is **not** a required status check: it

1. builds both archives with `scripts/packaging/package-skills.sh all`;
2. verifies archive integrity (`unzip -t` plus the packaging
   runtime-boundary test);
3. uploads the archives.

Keeping this out of the required gate means a packaging failure (a flaky
build, a dependency hiccup, a genuine packaging bug) never blocks an
otherwise-mergeable PR through the required check — it is visible on the
PR's checks list, but only `release-gate` decides mergeability.

### Fork / first-time-contributor workflow approval

This is a **public** repository that accepts outside contributions. For a
`pull_request`-triggered workflow, GitHub's own fork-approval policy
("Require approval for first-time contributors", the default and
recommended non-public-only setting) holds the *entire* workflow run —
every job in `release-worthiness.yml`, `release-gate` included — pending a
maintainer's manual approval in the Actions tab, for a contributor's
**first** pull request. This is enforced by GitHub Actions itself, at the
workflow-run level, before any job starts; it cannot be narrowed per-job
or worked around from workflow YAML or from `scripts/release/release_lib`.

**This is a real residual risk, not solved by this change:** if
`release-gate` is a required status check and a first-time contributor's
run sits unapproved, the check stays "Expected" and the PR cannot merge
until a maintainer approves the run (Actions tab → the pending workflow
run → *Approve and run*). After that one approval, every subsequent PR
from that same contributor runs automatically — the gap is limited to
each contributor's first PR.

Recommended, documented mitigation (a repository setting, not code):

- Keep **Settings → Actions → General → Fork pull request workflows from
  outside collaborators** set to *"Require approval for first-time
  contributors"* — not the stricter *"Require approval for all outside
  collaborators"*, which would reintroduce the same wait on every fork PR
  instead of only the first one.
- Maintainers watch the Actions tab for pull requests from contributors
  they don't recognize and approve the pending run promptly, the same way
  they already need to for `Validate repository` and the PR-description
  check today (identical constraint, not new to this gate).
- `release-gate` needs no secrets and never runs with elevated
  permissions, so approving it is always safe to do quickly — there is
  nothing sensitive a first-time contributor's PR content can reach
  through this job.

## Automatic publication from `main`

Once release-worthy work merges to `main`, the automation publishes it —
no maintainer runs anything, and no one supplies a version. This is the
authoritative main/release lifecycle, defined entirely in the separate
`release-publish.yml` workflow (triggered only by `push` to `main` and
`workflow_dispatch`, never `pull_request`), and it recomputes everything
itself rather than consuming any PR-time `release-gate` result.

The read-only **`plan`** job runs on every non-`[skip ci]` push to `main`
(and on `workflow_dispatch` for recovery). It is both the authoritative
release-worthiness assessment (classification plus real CHANGELOG
coverage over everything accumulated since the previous `v*` tag — not
merely a version calculator) and the version-planning step. It holds
`contents: read` and
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
4. **Stamps** `vX.Y.Z` (as `X.Y.Z`) into the `version:` frontmatter line of
   both Skills' `SKILL.md`, so the committed files match the release.
5. Builds **and verifies** both Skill archives (`package-skills.sh all`,
   which also leaves the validated `dist/skills/<name>/` trees the zips are
   built from, `unzip -t`, presence checks, and that each archive's
   `SKILL.md` version is exactly `X.Y.Z` — a mismatch fails the run before anything is
   pushed or tagged).
6. Commits the generated, rolled changelog and the stamped `SKILL.md`
   files directly to `main` (`chore(release): vX.Y.Z [skip ci]`).
7. Pushes that commit and re-fetches to confirm `origin/main` advanced to
   exactly that SHA.
8. Creates an **annotated** `vX.Y.Z` tag at that exact pushed commit.
9. Pushes the tag.
10. Creates the GitHub Release from the tag, notes taken from the matching
    `CHANGELOG.md` section, both verified Skill ZIPs attached.
11. Verifies the live tag commit, `origin/main`, and the published
    Release's tag and assets all match the release commit.

### Skill archive version

The version authority is the newest `## vX.Y.Z` heading in `CHANGELOG.md`,
which only the release flow writes (alongside the `vX.Y.Z` tag). Every
archive `package-skills.sh` / `package-skills.ps1` builds — a release, a
local build, or the PR `package` job — has its `SKILL.md` frontmatter
`version` stamped from it, so an archive never reports a stale committed
value:

- **Release build:** the heading just rolled in step 3 is the planned
  version, and step 5 verifies the archives against it.
- **Local / PR build:** the archives report the newest published release
  version the tree builds on. If the committed `SKILL.md` value differs,
  packaging prints a note and uses the authority; if `CHANGELOG.md` is
  missing or has no release heading, packaging fails with no archive.
- The committed `version:` is only a mirror that step 4 keeps equal to the
  release; nobody bumps it by hand, and it is unrelated to
  `metadata/skill.yaml`'s own independently maintained `version`.

In the built tree and archive the version is written as `metadata.version`
rather than the source's top-level `version:` line, because the Agent Skills
reference validator rejects the latter (#507; see
[`ARCHITECTURE.md`](ARCHITECTURE.md), section 7). That is the only change to
any packaged file's content. The archives are also now written from the
`dist/skills/<name>/` tree with sorted entries and fixed timestamps, so
they carry no explicit directory entries and are byte-reproducible; names and
layout are unchanged. The source `SKILL.md` keeps its top-level `version:`,
which the release flow stamps as before.

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
- **Require status checks to pass**: `Validate repository` and
  `Release worthiness` / `release-gate`. `release-gate` is safe to
  require because it always resolves — release-relevant or not (see
  "`release-gate` — the required, always-created check" above) — modulo
  the documented fork/first-time-contributor approval gap in "Fork /
  first-time-contributor workflow approval" above, which is a GitHub-level
  constraint on the whole workflow run, not something this ruleset entry
  can close. Do **not** require `package` — it is conditional,
  release-worthy-only work and would leave every non-release-worthy PR
  stuck on a job that never runs for it.
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

## Generated distribution repository

Marketplace publication (parent #506) does not commit built Skill trees to
this repository: a committed copy would put three copies of `shared/` in
one repo, and the `skills` CLI's standard discovery would find the
non-self-contained `skills/<name>/` source folders first. The built
output is published to a separate, **generated-only** public repository,
`amirbena/code-review-skills`.

### Layout (written by #509 and #510, fixed here)

| Path | Content | Written by |
| --- | --- | --- |
| `skills/<name>/` | the self-contained built tree of each Skill (from #507) | #509 |
| `README.md` | generated; points back to this repository | #509 |
| `LICENSE` | copied from this repository | #509 |
| `DISTRIBUTION.json` | source repo, source commit, version, content manifest hash | #509 |
| `.claude-plugin/marketplace.json` and other adapter files | Claude adapter layer | #510 |

The only hand-authored content allowed is one optional bootstrap commit.
Issues and Discussions are disabled, and the repository description links
back to this repository.

### Generated-only policy

Humans never edit the distribution repository. Every fix — including a
typo in the generated `README.md` — goes through this repository and a
release, and the next publication overwrites the output. There is no
routine human bypass on the default branch or on `v*` tags.

### Rulesets

Create two repository rulesets on the distribution repository:

- **Default branch:** restrict creations, updates, and deletions, and
  block force pushes; only the bypass actor below can push.
- **Tags matching `v*`:** restrict creation, updates, and deletions, and
  block force pushes; only the bypass actor below can create tags.
- **Bypass list (both rulesets): the publishing identity only.** No
  `Repository admin`, no team, no human.

### Publishing identity decision

The identity that pushes to the distribution repository is one of two
options. This section records the analysis and the confirmed decision.

| | A. Reuse the "Skill Release Automation" App | B. Dedicated publication App |
| --- | --- | --- |
| What a leaked key can write | `contents: write` on this repo **and** the distribution repo: it can push to this repo's `main` (it is that ruleset's sole bypass actor) and to the distribution repo | `contents: write` on the distribution repo only; it cannot touch this repo |
| Ruleset bypass lists | the App is added to a second ruleset, and the same key now bypasses two repos | this App is the only entry in the distribution rulesets; this repo's `main` bypass list is unchanged |
| Rotation | rotating the one key affects both the release and the publication jobs at once | rotate the publication key independently; the release flow is unaffected |
| Revocation | uninstalling from the distribution repo is possible, but revoking the key stops source releases too | uninstall the App or delete its key; publication stops, source releases continue |
| Operational cost | no new App, secrets, or installation | one more App, two secrets, and one more installation to maintain |

Option A widens the blast radius of the key that can already bypass this
repository's `main` protection. Option B costs one extra App but keeps a
leaked publication key from ever reaching the source repository, and it
keeps this repository's release App permissions unchanged (see the
non-goal in #508).

**Decision (confirmed):** a dedicated publication App,
`code-review-skills-publisher` (App ID `5058568`), installed only on
`amirbena/code-review-skills`. It is not installed on this repository, and
the source-repository release App is unchanged.

Grant the chosen identity **Contents: Read and write** and **Metadata:
Read-only** on the distribution repository only — install it there and
nowhere else — with no webhook. Store its credentials as
`DISTRIBUTION_APP_ID` and `DISTRIBUTION_APP_PRIVATE_KEY` on the
`release-skills-distribution` Environment of this repository (not the
`release` Environment, which belongs to source releases), and mint a
short-lived installation token scoped to the distribution repository at
publication time (#509), as the release job does today.

**Rotate:** generate a new private key in the App settings, update the
secret, run a publication dry run, then delete the old key.
**Revoke (suspected leak):** delete the key in the App settings first
(the token minting fails closed), then rotate, then review the
distribution repository's commit and tag history against `DISTRIBUTION.json`
provenance.

### Provisioning validation (recorded 2026-09-24)

The private key was never exposed to a maintainer or agent session; the
dry run ran inside GitHub Actions on the `release-skills-distribution`
Environment, minting a token scoped to `code-review-skills` and refusing
any App slug other than `code-review-skills-publisher`.

1. **Negative control.** Before the App was added to the rulesets, a push
   of `main` and of a `v*` tag from the maintainer account was rejected:
   "push declined due to repository rule violations" (creations
   restricted). The repository still had no branches.
2. **Bypass.** The App (integration `5058568`, `bypass_mode: always`) is
   the sole bypass actor on both rulesets.
3. **Mutation.** The App pushed the single bootstrap commit to `main`
   (an empty commit, `39294c6`) and created the annotated scratch tag
   `v0.0.0-scratch-508`; GitHub reported "Bypassed rule violations" for
   both refs. The commit author and the repository events actor are
   `code-review-skills-publisher[bot]`.
4. **Cleanup.** The App deleted the scratch tag and the scratch branch
   with the same token; the rulesets stayed active throughout and were
   never weakened. Final refs: `refs/heads/main` only.
5. The dry-run workflow lived on a scratch branch of this repository and
   was deleted with it; it is not part of this change.

The `release-skills-distribution` Environment currently has no branch
restriction or required reviewers. Restricting it to `main` before #509
lands is recommended, so only the reviewed publication workflow can reach
the key.

## Publishing each release to the distribution repository (#509)

Order: **source release first, distribution second.** The `publish` job
builds the #507 tree once (zips and tree come from that one build),
commits, tags, publishes the GitHub Release and runs `release-verify`,
then uploads the build as the `distribution-build` artifact. The
`distribute` job (Environment `release-skills-distribution`, the
publisher App token scoped to `code-review-skills`) then runs
`release_worthiness.py distribution-publish` and `distribution-verify`:

- **Publish** commits `skills/<name>/`, `DISTRIBUTION.json` (source
  repository, source commit, version, content manifest hash), `LICENSE`,
  a generated `README.md`, and any adapter files the build emits under
  `dist/distribution-root/` as a fast-forward on `main`, with
  `Source-Repository` / `Source-Commit` / `Source-Tag` trailers, then
  pushes the annotated tag `vX.Y.Z`. It never force-pushes. The zips are
  first checked byte-for-byte against the tree being published.
- **Verify** fetches the distribution tag and requires its file manifest
  and commit trailers to equal the build's.
- **Idempotent:** an existing `vX.Y.Z` with identical content is a no-op;
  with different content the command fails and changes nothing.
- **Fail closed:** a rejected push, a failed tag push, or a mismatch fails
  the run with an actionable message. A tag is only pushed after its
  commit is on `main`, so no half-written tag exists; a commit pushed
  without its tag is completed (tag only) by the next run.

The version is the source tag, never an input; `auto-release-plan` remains
the only version authority.

### Authority boundary and earlier releases

`amirbena/code-review-skills` is authoritative for distribution artifacts
beginning with the first marketplace-enabled distribution release, that
is, the first `vX.Y.Z` tag successfully written by the `distribute` job.
Until that first publication happens the boundary is not yet established;
record the concrete version here once it is.

Releases before that boundary are represented only by their original
GitHub Release archives in this repository. They are not backfilled: those
archives were built under earlier packaging contracts (for example,
before the canonical Skill tree and its distribution-only `metadata.version`
normalization), so no marketplace artifact for them would be equivalent to
what was released. Do not read the absence of an older tag in the
distribution repository as a missing release.

### Recovery

If `distribute` fails after the source release, the run is red — it is
never skipped. Fix the cause (credentials, ruleset, network), then run
**Release publish** via `workflow_dispatch` on `main`. When `plan` finds
nothing new to release, `distribute` rebuilds the latest source release tag
and publishes it, completing a lagging distribution without re-releasing
the source. A mismatch error means the distribution tag holds different
content than the source tag builds; investigate before any manual action
(humans do not edit the distribution repository; do not delete the tag
without maintainer review).

## Permissions model

| Workflow | Trigger | Job | `permissions` | Runs contributor code | Mutates repo |
| --- | --- | --- | --- | --- | --- |
| `release-worthiness.yml` | `pull_request` | `release-gate` (required) | `contents: read` | yes | never |
| `release-worthiness.yml` | after `release-gate`, when release-worthy | `package` (not required) | `contents: read` | yes | never |
| `release-publish.yml` | `push` to `main` (non-`[skip ci]`), `workflow_dispatch` | `plan` | `contents: read`, `pull-requests: read` | no — checks out `main` | never — generates notes and derives the version in memory |
| `release-publish.yml` | after `publish` succeeds, or on `workflow_dispatch` recovery | `distribute` | `contents: read` | no — checks out the source release commit/tag | pushes only to the distribution repository, using the publisher App token; never force |
| `release-publish.yml` | after `plan`, when a release is due | `publish` | `contents: write`, `pull-requests: read` | no — checks out `main` | commits to `main`, tags, publishes a Release, using the App token |

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
