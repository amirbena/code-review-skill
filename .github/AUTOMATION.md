# GitHub Actions automation

An architectural map of this repository's CI/CD automation under
[`workflows/`](workflows/). It orients a newcomer to how PR validation,
issue operations, and release automation fit together, then points at the
canonical docs and scripts that own the exact contracts.

**This file is a map, not a policy source of truth.** Where a detailed
contract lives elsewhere — [`../docs/RELEASE.md`](../docs/RELEASE.md),
[`../scripts/release/release_worthiness.py`](../scripts/release/release_worthiness.py) and
[`../scripts/release/release_lib/`](../scripts/release/release_lib/), the
[`../scripts/governance/claim_issue.py`](../scripts/governance/claim_issue.py),
[`../scripts/governance/sync_issue_labels.py`](../scripts/governance/sync_issue_labels.py) and
[`../scripts/validation/pr_description_length.py`](../scripts/validation/pr_description_length.py)
validators, or [`../AGENTS.md`](../AGENTS.md) and
[`../policies/`](../policies/) for instruction architecture — this file
links to it rather than restating it. Keep the table below refreshed when
workflows change.

## Workflow inventory

| Workflow | File | Trigger | Responsibility | GitHub state |
| --- | --- | --- | --- | --- |
| Validate repository | [`workflows/validate.yml`](workflows/validate.yml) | `pull_request`, `push` to `main` | `test` (required): set up Python 3.13, extract the trusted router (`scripts/validation/ci_test_route.py`) from the PR base SHA through a separate blobless clone and pick the FAST or FULL tier (FULL by default, on any error, and on every push to `main`), validate both Skills' metadata (`scripts/validation/validate-skill-metadata.py`), build and spec-validate the Skill trees, then run `python -m unittest discover -s tests -t .` (FULL) or the same discovery minus `tests.integration.*` (FAST). Skill-tree shell/PowerShell parity on both tiers | Read-only (`contents: read`) |
| Validate PR description length | [`workflows/pr-description-length.yml`](workflows/pr-description-length.yml) | `pull_request` (opened, edited, synchronize) | Check out the trusted validator from the PR base SHA (bootstrapping from head only for the PR that introduces the script), enforce the useful-content limit and the canonical PR-template structure via `scripts/validation/pr_description_length.py` | Read-only (`contents: read`) |
| Sync Engineering Task labels | [`workflows/sync-issue-labels.yml`](workflows/sync-issue-labels.yml) | `issues` (opened, edited) | Compute managed-label changes from the issue body (`scripts/governance/sync_issue_labels.py`), then `gh issue edit` to apply the add/remove set; per-issue `concurrency` with cancel-in-progress | Mutates issue labels (`issues: write`) |
| Claim contribution issue | [`workflows/claim-issue.yml`](workflows/claim-issue.yml) | `issue_comment` (created) | On `/claim` or `/unclaim` on a non-PR issue: check out trusted default-branch automation, read the issue and comment history, plan via `scripts/governance/claim_issue.py` with churn/cooldown thresholds, persist a trusted receipt and a reconciled-state checkpoint comment, then project state onto the `claimed` label; repo-wide serialized `concurrency` queue | Mutates issue comments + the `claimed` label (`issues: write`) |
| Release worthiness | [`workflows/release-worthiness.yml`](workflows/release-worthiness.yml) | `pull_request` | PR lifecycle, read-only preview. `release-gate` (required check): classify the change set the PR itself contributes, and — only when release-worthy — enforce release intent (CHANGELOG category + entry in the PR description, passed via env); always resolves, with an explicit not-applicable result when the change isn't release-worthy. `package` (not required, `needs: release-gate` when release-worthy): build/verify the Skill archives as a dry run. Never builds a release; never touches `main`. | `release-gate` / `package` read-only |
| Release publish | [`workflows/release-publish.yml`](workflows/release-publish.yml) | `push` to `main`, `workflow_dispatch` | Main/release lifecycle, authoritative. Never triggered by `pull_request`, so `plan`/`publish` never exist as PR check runs; recomputes the release assessment itself rather than trusting `release-gate`'s preview. `plan` (read-only, trusted `main` only): the authoritative release-worthiness assessment — classify everything since the latest `v*` tag, generate `## Unreleased` from merged PRs' release intent, and derive the next version. `publish` (only when `plan` reports release-worthy): mint a trusted release GitHub App token, generate and roll the CHANGELOG, build + verify both archives, commit to `main` `[skip ci]`, create an annotated tag, verify. `distribute` (publisher App): publish and verify the distribution repository. `finalize` (only after `distribute` succeeds): create, complete, or no-op the GitHub Release with the same build's archives and verify their digests. `recover-tag` (dispatch recovery only): tag a release commit whose tag push failed | `plan` read-only; `publish`, `recover-tag`, `finalize` mutate (`contents: write` via the release GitHub App: commit to `main`, tag, GitHub Release) behind the `release` Environment; `distribute` writes only the distribution repository |

## Automation areas

### 1. PR quality and validation

Runs on the pull request, read-only. `validate.yml` and the `Release
worthiness` `release-gate` job are the required status checks on the
`main` ruleset ([`../docs/RELEASE.md`](../docs/RELEASE.md)):

- **`validate.yml`** — Skill metadata validation plus the `tests/`
  suite, routed per PR: FULL by default, or FAST (omitting only
  `tests/integration/`) when every changed path is on the router's
  allowlist; every push to `main` runs FULL. Contract:
  [`../policies/validation-and-clean-exit.md`](../policies/validation-and-clean-exit.md#routed-ci-tests).
- **`pr-description-length.yml`** — enforces the PR-description
  useful-content limit and the canonical PR-template structure (required
  headings/fields, unresolved placeholders), checking out the validator
  from the trusted PR **base** SHA so a PR cannot weaken its own check.
  Contract:
  [`../scripts/validation/pr_description_length.py`](../scripts/validation/pr_description_length.py).
- **`release-worthiness.yml` → `release-gate` job** — the required,
  always-resolving check: classifies whether the change ships a Skill or
  its packaged distribution, and — only when it does — requires the PR to
  declare valid release intent (CHANGELOG category + one-line entry) in
  its description, read through an env var, failing closed. A
  non-release-worthy PR still gets an explicit not-applicable pass, never
  a skipped or absent check. The conditional archive build/verify dry run
  lives in the separate, non-required `package` job instead, so a
  packaging failure never fails this gate. Contract:
  [`../docs/RELEASE.md`](../docs/RELEASE.md) ("PR checks").

### 2. Issue operations

- **`sync-issue-labels.yml`** — on issue open/edit, derives the managed
  label set from the issue body and applies the diff. A newer edit
  supersedes an in-flight run (per-issue `concurrency`,
  cancel-in-progress). Contract:
  [`../scripts/governance/sync_issue_labels.py`](../scripts/governance/sync_issue_labels.py).
- **`claim-issue.yml`** — on a `/claim` or `/unclaim` comment on a
  non-PR issue, reconciles ownership: it checks out trusted
  default-branch automation, reads the issue and repository comment
  history, and plans the action with
  [`../scripts/governance/claim_issue.py`](../scripts/governance/claim_issue.py) under
  churn/cooldown thresholds (the `CLAIM_*` env values). It persists a
  **trusted command receipt**, then a **reconciled-state checkpoint**
  comment, before projecting the logical state onto the `claimed`
  label — so a failed label mutation is recoverable from the
  receipt/checkpoint pair. A repo-wide serialized `concurrency` queue
  makes cross-issue churn limits deterministic. Contributor-facing
  behavior: [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

### 3. Release automation

The `plan` and `publish` jobs of **`release-publish.yml`** — a separate
workflow triggered only by `push` to `main` and `workflow_dispatch`, never
`pull_request` — driven by the release intent of the pull requests merged
since the last tag. No maintainer runs anything, no one supplies a
version, and no contributor edits `CHANGELOG.md`. This workflow recomputes
the release assessment itself; it never trusts or consumes
`release-worthiness.yml`'s PR-time `release-gate` preview.

- **`plan`** (read-only, trusted `main` only) generates `## Unreleased`
  from the merged PRs' release intent and derives the next SemVer
  version from its categories, or reports nothing to release.
- **`publish`** runs only when `plan` reports a release-worthy set. It is
  the sole job granted `contents: write` and the only one behind the
  `release` Environment; it mints a short-lived token from the trusted
  release GitHub App (the sole `main`-ruleset bypass actor) for the
  protected push/tag mutations. It creates no GitHub Release.
- **`distribute`** publishes and verifies the generated distribution
  repository with the separate publisher App.
- **`finalize`** runs only after `distribute` succeeded and is the only
  job that creates the GitHub Release: a version never becomes an official
  source release before its distribution is verified (#528). If a version
  stops before that, `plan` fails closed on the next push and
  `workflow_dispatch` finishes the same version (`recover-tag` covers a
  missing source tag).

Canonical reference — release-worthiness rules, SemVer classification,
the permissions model, and the required repository configuration
(`main` ruleset + release GitHub App):
[`../docs/RELEASE.md`](../docs/RELEASE.md). Category-selection contract:
[`../policies/release-changelog-policy.md`](../policies/release-changelog-policy.md).

## PR / release lifecycle

Conceptual stages from a pull request to a published release:

```text
  pull request opened / updated          [release-worthiness.yml, pull_request only]
        │
        ├─ validate.yml ............. Skill metadata + tests
        ├─ pr-description-length.yml . description contract
        └─ release-worthiness: release-gate (READ-ONLY, REQUIRED)
                                       classify change + PR release intent;
                                       explicit not-applicable when N/A
                 │
                 └─ release-worthiness: package (READ-ONLY, not required)
                                       dry-run archive build, only if
                                       release-gate says release-worthy
        │
        ▼
  merge to main                          [release-publish.yml, push/dispatch only —
        │                                  never pull_request; recomputes the
        │                                  assessment itself, trusts nothing above]
        ▼
  release-publish: plan (READ-ONLY, trusted main; authoritative assessment)
        │   classify everything since the latest v* tag, generate
        │   "## Unreleased" from merged PRs' release intent, derive the
        │   next version from its categories
        │
        ├─ nothing release-worthy ──▶ no-op
        │
        ▼  release-worthy
  release-publish: publish  (contents: write, release Environment,
        │                    release GitHub App token)
        ├─ generate + roll CHANGELOG "## Unreleased" → "## vX.Y.Z"
        ├─ build + verify both Skill archives
        ├─ commit to main  "chore(release): vX.Y.Z [skip ci]"
        ├─ create annotated tag vX.Y.Z at that commit
        └─ verify tag + main (no GitHub Release yet)
        │
        ▼
  release-publish: distribute  (publisher App, release-skills-distribution)
        └─ distribution commit + tag, distribution-verify
        │
        ▼  only on distribute success
  release-publish: finalize  (release App, release Environment)
        └─ create/complete GitHub Release with the same archives, verify digests
```

## Issue-operations flow

```text
  issue opened / edited
        │
        ▼
  sync-issue-labels.yml
        └─ derive managed labels from issue body → apply add/remove diff


  issue comment "/claim" or "/unclaim"  (non-PR issue)
        │
        ▼
  claim-issue.yml → claim_issue.py
        │   reconcile ownership against issue + comment history,
        │   bounded by churn/cooldown thresholds
        ├─ persist trusted command receipt
        ├─ persist reconciled-state checkpoint comment
        └─ project state onto the "claimed" label
```

Both diagrams are conceptual. The authoritative step sequence is the YAML
under [`workflows/`](workflows/) and the scripts it calls.
