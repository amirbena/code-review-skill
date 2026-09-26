# GitHub Review Status Mechanism — Research Recommendation

Repository-development research for GitHub Issue
[#91](https://github.com/amirbena/code-review-skill/issues/91) (parent
Epic #49; relates to #34; blocks #95). It picks the GitHub mechanism for
publishing the aggregated review status that
[`review-status-enforcement.md`](../skills/github-pr-review/policies/review-status-enforcement.md)
deliberately leaves open, and records the permission/auth model. It
**recommends without implementing** and re-derives nothing already decided
there (context identity, SHA binding, verdict mapping, authorization split,
enforcement-state detection, idempotency).

## Decision

**Use the Commit Status API** (`POST /repos/{owner}/{repo}/statuses/{sha}`)
as the default mechanism. Treat the Checks API as a possible future
upgrade that is available **only** under a GitHub App installation.

Rationale in one line: the Commit Status API satisfies every stated need of
the policy under ordinary `gh`/`gh api` token auth, whereas the Checks API's
write path is restricted to GitHub Apps.

## Comparison against the policy's needs

| Policy need | Commit Status API | Checks API |
| --- | --- | --- |
| One stable aggregated context | Yes — the `context` label is the identity; case-insensitive. | Yes — the check run `name`, scoped to a check suite (per app). |
| Bound to one commit SHA | Yes — the SHA is in the endpoint path. | Yes — `head_sha` on the run. |
| Upsert semantics | Yes — a new status for an existing SHA+context updates that status in place; up to 1000 statuses per SHA and context, far beyond one-per-review. | Not natively: create makes a new run; converging requires finding the run and `PATCH`ing it (extra read + write). Old runs beyond 1000 per name per suite are auto-deleted. |
| Neutral "not yet reviewed" state | `pending` (plus `success`/`failure`/`error`). | `queued`/`in_progress` plus conclusions incl. `neutral`, `action_required`. Richer, but the policy only needs non-`success`. |
| Read-back for state detection | `GET /repos/{owner}/{repo}/commits/{ref}/status` (combined) and the list-statuses endpoint. | List check runs for a ref, filterable by name. |
| Usable as a required check | Yes — required status checks can be checks or commit statuses. | Yes. |
| Writable with a PAT / `gh` token | **Yes.** | **No.** Only GitHub Apps can create or update check runs. |
| Rich output (annotations, buttons) | No. | Yes — unused by this policy. |

The Checks API's extras (annotations, requested actions, rich summaries)
are outside the policy's contract, and its App-only write requirement would
make the capability unusable for the default `gh`-driven Skill runtime. That
combination decides the pick.

## Permission and auth requirements

### Ordinary `gh` / `gh api` token auth (recommended path)

- **Fine-grained personal access token or app token:** repository
  permission **Commit statuses: write** (needs push access to the repo).
- **Classic token / `gh auth` OAuth token:** the **`repo:status`** scope
  grants status write without code access; the broader `repo` scope also
  works.
- Reading combined status needs read access to the repository.
- Example:

  ```bash
  gh api -X POST repos/OWNER/REPO/statuses/SHA \
    -f state=failure -f context=code-review/github-pr-review \
    -f description="CHANGES REQUIRED"
  ```

- Enforcement-state detection is a separate read: listing rulesets and
  classic branch protection needs repository administration read access
  and otherwise resolves to `UNKNOWN`, as the policy already specifies.
  Opt-in required-check setup mutates governance and needs administration
  write; it is a distinct permission from status write.

### GitHub App installation

- Required **only** if the Checks API is chosen. The App needs the
  **`checks: write`** permission; OAuth apps and personal tokens can read
  check runs but cannot create them.
- An App is also relevant for **source pinning**: when a required check is
  configured, GitHub lets the repository pick a specific App as the
  expected source, so that a same-named status posted by anyone else does
  not satisfy it. Commit statuses have no such source identity beyond the
  author, so with the status API a repository chooses "any source" and
  relies on the context name plus the authorization split in the policy.
  Repositories that need source pinning are the case where a future App
  integration (and the Checks API) is justified.

## Consequences and caveats

- **Name collisions:** GitHub warns that identical names from multiple
  sources make required-check results ambiguous. Keep the context string
  unique to this Skill (the policy's `code-review/github-pr-review`).
- **Same context, two sources:** if a repository later also runs an App
  check with the same name, the requirement can become ambiguous; choose
  one mechanism per repository.
- **Publisher identity:** a token-published status is attributed to the
  token's user, so it is only as trustworthy as that token's holder — the
  reason the policy's authorization split (blocking always allowed,
  `success` only for `ACTIVE` + independent reviewer) remains necessary.
- **Rate limit:** 1000 statuses per SHA and context; the policy's
  write-only-on-change idempotency stays well under it.

## Follow-ups for #95

Implementation should use `state` values `success`/`failure`/`pending`
mapped per the existing verdict table, a fixed `context`, a short
`description`, read-back through the combined-status endpoint, and no
Checks API code path unless an App integration is separately requested.

## Sources (official GitHub documentation)

- [REST API endpoints for commit statuses](https://docs.github.com/en/rest/commits/statuses)
- [REST API endpoints for check runs](https://docs.github.com/en/rest/checks/runs)
- [Using the REST API to interact with checks](https://docs.github.com/en/rest/guides/using-the-rest-api-to-interact-with-checks)
- [About protected branches — required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
