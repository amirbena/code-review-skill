# GitHub Merge Enforcement — End-to-End Evidence

Acceptance record for GitHub Issue
[#553](https://github.com/amirbena/code-review-skill/issues/553) (parent Epic
#546). It proves, on a disposable repository, that GitHub itself blocks and
allows merge according to the review status. It adds no behavior; defects
found are filed against the owning child (#548 publisher, #549 detection,
#550 setup, #551 corpus), not patched here.

**Status: awaiting maintainer run.** The tables below are filled by the
procedure; until then every result is `PENDING`.

## Procedure (maintainer, by hand)

CI never runs this and the driver refuses `CI` / `GITHUB_ACTIONS`, the
canonical repository, and any repository whose name lacks `disposable`,
`sandbox`, or `scratch`.

1. Create a private repository such as `<owner>/review-enforcement-disposable`
   with a `main` branch and an open, mergeable PR (`topic` → `main`).
   Use a token scoped to that repository only (Administration: write,
   Commit statuses: write, Contents: write, Pull requests: read).
2. For each mechanism, from a clean disposable state (no rulesets, no branch
   protection), run:

   ```bash
   python3 -m scripts.github_integration.lifecycle_proof OWNER/REPO PR_NUMBER --mechanism ruleset --confirm-disposable
   ```

   The driver removes the governance it seeded when it finishes, even on
   failure (partial evidence is still printed), so repeat with
   `--mechanism classic` on the same repository.
3. Paste each run's output (already sanitized: tokens, repository slug, and
   full SHAs are stripped) into the matching section below.
4. Tear down: `gh repo delete OWNER/REPO --yes`, or reset by removing the
   ruleset and branch protection. Record which.

The driver seeds one unrelated required check (`proof/unrelated`) plus
unrelated rules, so "unrelated governance intact" is observable; setup
refuses to create governance from nothing by design (#550).

## Lifecycle points covered

| Point (Issue #553) | Driver step |
| --- | --- |
| Status published on reviewed SHA | `failure` / `success published on reviewed SHA` |
| Setup only with explicit authorization; same run without it does not mutate | `Setup without explicit authorization refuses`, `No mutation without authorization` |
| `failure` blocks, `success` satisfies | `blocks merge on failure`, `satisfied on success` (GitHub `mergeable_state`) |
| New HEAD inherits no status or authorization | `PR HEAD advanced`, `New HEAD inherits no status`, `…is merge-blocked`, `…success withheld`, `…own authorized review publishes success`, `New HEAD satisfied by its own review`, `Prior SHA status unchanged` |
| Unrelated governance intact after setup and removal | `intact after setup`, `restored after removal` |

## Evidence

### Ruleset run

PENDING

### Classic branch protection run

PENDING

## Deviations

None recorded. Any deviation is filed against the owning child Issue and
linked here.
