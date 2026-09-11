# GitHub Actions automation

An architectural map of this repository's CI/CD automation under
[`workflows/`](workflows/). It orients a newcomer to how PR validation,
issue operations, and release automation fit together, then points at the
canonical docs and scripts that own the exact contracts.

**This file is a map, not a policy source of truth.** Where a detailed
contract lives elsewhere — [`../docs/RELEASE.md`](../docs/RELEASE.md),
[`../scripts/release_worthiness.py`](../scripts/release_worthiness.py) and
[`../scripts/release_lib/`](../scripts/release_lib/), the
[`../scripts/claim_issue.py`](../scripts/claim_issue.py),
[`../scripts/sync_issue_labels.py`](../scripts/sync_issue_labels.py) and
[`../scripts/pr_description_length.py`](../scripts/pr_description_length.py)
validators, or [`../AGENTS.md`](../AGENTS.md) and
[`../policies/`](../policies/) for instruction architecture — this file
links to it rather than restating it. Keep the table below refreshed when
workflows change.

## Workflow inventory

| Workflow | File | Trigger | Responsibility | GitHub state |
| --- | --- | --- | --- | --- |
| Validate repository | [`workflows/validate.yml`](workflows/validate.yml) | `pull_request` | Set up Python 3.13, validate both Skills' metadata (`scripts/validate-skill-metadata.py`), run `python -m unittest discover -s tests` | Read-only (`contents: read`) |
| Validate PR description length | [`workflows/pr-description-length.yml`](workflows/pr-description-length.yml) | `pull_request` (opened, edited, synchronize) | Check out the trusted validator from the PR base SHA (bootstrapping from head only for the PR that introduces the script), enforce the useful-content limit via `scripts/pr_description_length.py` | Read-only (`contents: read`) |
| Sync Engineering Task labels | [`workflows/sync-issue-labels.yml`](workflows/sync-issue-labels.yml) | `issues` (opened, edited) | Compute managed-label changes from the issue body (`scripts/sync_issue_labels.py`), then `gh issue edit` to apply the add/remove set; per-issue `concurrency` with cancel-in-progress | Mutates issue labels (`issues: write`) |
| Claim contribution issue | [`workflows/claim-issue.yml`](workflows/claim-issue.yml) | `issue_comment` (created) | On `/claim` or `/unclaim` on a non-PR issue: check out trusted default-branch automation, read the issue and comment history, plan via `scripts/claim_issue.py` with churn/cooldown thresholds, persist a trusted receipt and a reconciled-state checkpoint comment, then project state onto the `claimed` label; repo-wide serialized `concurrency` queue | Mutates issue comments + the `claimed` label (`issues: write`) |
| Release worthiness | [`workflows/release-worthiness.yml`](workflows/release-worthiness.yml) | `pull_request`, `push` to `main`, `workflow_dispatch` | `assess` (read-only): classify the change set vs. the latest `v*` tag, on a PR enforce release intent (CHANGELOG category + entry in the PR description, passed via env), build/verify the Skill archives as a dry run. `plan` (read-only, trusted `main` only): generate `## Unreleased` from merged PRs' release intent and derive the next version. `publish` (only when `plan` reports release-worthy): mint a trusted release GitHub App token, generate and roll the CHANGELOG, build + verify both archives, commit to `main` `[skip ci]`, create an annotated tag, publish the GitHub Release with archives, verify | `assess` / `plan` read-only; `publish` mutates (`contents: write` via the release GitHub App: commit to `main`, tag, GitHub Release) behind the `release` Environment |

## Automation areas

### 1. PR quality and validation

Runs on the pull request, read-only. `validate.yml` and the `Release
worthiness` `assess` job are the required status checks on the `main`
ruleset ([`../docs/RELEASE.md`](../docs/RELEASE.md)):

- **`validate.yml`** — Skill metadata validation plus the full
  `tests/` suite.
- **`pr-description-length.yml`** — enforces the PR-description
  useful-content limit, checking out the validator from the trusted PR
  **base** SHA so a PR cannot weaken its own check. Contract:
  [`../scripts/pr_description_length.py`](../scripts/pr_description_length.py).
- **`release-worthiness.yml` → `assess` job** — a read-only preview that
  classifies whether the change ships a Skill or its packaged
  distribution, requires a release-worthy PR to declare valid release
  intent (CHANGELOG category + one-line entry) in its description — read
  through an env var, failing closed — and dry-runs archive build +
  verification. Contract:
  [`../docs/RELEASE.md`](../docs/RELEASE.md) ("PR / push checks").

### 2. Issue operations

- **`sync-issue-labels.yml`** — on issue open/edit, derives the managed
  label set from the issue body and applies the diff. A newer edit
  supersedes an in-flight run (per-issue `concurrency`,
  cancel-in-progress). Contract:
  [`../scripts/sync_issue_labels.py`](../scripts/sync_issue_labels.py).
- **`claim-issue.yml`** — on a `/claim` or `/unclaim` comment on a
  non-PR issue, reconciles ownership: it checks out trusted
  default-branch automation, reads the issue and repository comment
  history, and plans the action with
  [`../scripts/claim_issue.py`](../scripts/claim_issue.py) under
  churn/cooldown thresholds (the `CLAIM_*` env values). It persists a
  **trusted command receipt**, then a **reconciled-state checkpoint**
  comment, before projecting the logical state onto the `claimed`
  label — so a failed label mutation is recoverable from the
  receipt/checkpoint pair. A repo-wide serialized `concurrency` queue
  makes cross-issue churn limits deterministic. Contributor-facing
  behavior: [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

### 3. Release automation

The `plan` and `publish` jobs of **`release-worthiness.yml`**, driven by
the release intent of the pull requests merged since the last tag — no
maintainer runs anything, no one supplies a version, and no contributor
edits `CHANGELOG.md`.

- **`plan`** (read-only, trusted `main` only) generates `## Unreleased`
  from the merged PRs' release intent and derives the next SemVer
  version from its categories, or reports nothing to release.
- **`publish`** runs only when `plan` reports a release-worthy set. It is
  the sole job granted `contents: write` and the only one behind the
  `release` Environment; it mints a short-lived token from the trusted
  release GitHub App (the sole `main`-ruleset bypass actor) for the
  protected push/tag/release mutations.

Canonical reference — release-worthiness rules, SemVer classification,
the permissions model, and the required repository configuration
(`main` ruleset + release GitHub App):
[`../docs/RELEASE.md`](../docs/RELEASE.md). Category-selection contract:
[`../policies/release-changelog-policy.md`](../policies/release-changelog-policy.md).

## PR / release lifecycle

Conceptual stages from a pull request to a published release:

```text
  pull request opened / updated
        │
        ├─ validate.yml ............. Skill metadata + tests
        ├─ pr-description-length.yml . description contract
        └─ release-worthiness: assess  classify change (READ-ONLY)
                                       + PR release intent + dry-run packaging
        │
        ▼
  merge to main   (assess re-runs read-only on the push)
        │
        ▼
  release-worthiness: plan (READ-ONLY, trusted main)
        │   generate "## Unreleased" from merged PRs' release intent,
        │   derive the next version from its categories
        │
        ├─ nothing release-worthy ──▶ no-op
        │
        ▼  release-worthy
  release-worthiness: publish  (contents: write, release Environment,
        │                       release GitHub App token)
        ├─ generate + roll CHANGELOG "## Unreleased" → "## vX.Y.Z"
        ├─ build + verify both Skill archives
        ├─ commit to main  "chore(release): vX.Y.Z [skip ci]"
        ├─ create annotated tag vX.Y.Z at that commit
        └─ publish GitHub Release with both Skill archives, then verify
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
