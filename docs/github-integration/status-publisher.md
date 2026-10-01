# Review Status Publisher

Design record for GitHub Issue
[#548](https://github.com/amirbena/code-review-skill/issues/548) (parent
Epic #546). It describes the repository tooling that publishes the
SHA-bound review status; the canonical behavior stays in
[`review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md),
and the mechanism choice stays in
[`review-status-recommendation.md`](review-status-recommendation.md). This
page restates neither.

## Behavior

`publish_status()` in
[`status_publisher.py`](../../scripts/github_integration/status_publisher.py)
takes already-resolved facts (canonical result, aggregator role,
self-review, `ACTIVE` mode, reviewer independence) and goes through the
shared [`GitHubClient`](execution-surface.md) only:

- **Upsert.** One context, `code-review/github-pr-review`, on the exact
  reviewed SHA. If the live status already has the same state and
  description, nothing is written.
- **Retry.** Transport failures and 5xx responses are retried (3 attempts,
  exponential backoff); the POST is an upsert, so a retry cannot duplicate.
  4xx responses are not retried.
- **Stale HEAD.** The live PR HEAD is read right before publishing; if it
  moved, the outcome is `STATUS WITHHELD (HEAD advanced)` and a new SHA
  starts with no status.
- **Mapping and authorization.** Result-to-state mapping, `success` gating,
  and the self-review rule are those of the policy; they are mirrored, not
  redefined, and the unit tests compare every case against the #34
  reference model.
- **Permissions.** A refused write raises an error naming `Commit statuses:
  write` (fine-grained) or `repo:status` (classic).

## Governance boundary

Publishing a status is not a governance mutation. The publisher calls only
`read()` and `write()` against `repos/{repo}/statuses/{sha}`; it never
imports `mutate_governance` or `GovernanceAuthorization` and needs no setup
authorization. Required-check detection and setup are separate children of
Epic #546.

## Commit Status limitation and when to revisit

A Commit Status context is identified only by its name: any principal with
`Commit statuses: write` can post the same context, and a required check
cannot be pinned to the publisher. The Checks API can pin a required check
to a specific GitHub App (`integration_id`) but its write path is
App-only. Move to a Checks API / App follow-up only when a repository
needs that source pinning or Check-run features the policy does not use
(annotations, re-run actions); until then Commit Status stays the default
per [#91](../github-review-status-mechanism-research.md).

## Entry point

The runtime calls `publish_status()` from a repository checkout. A CLI
wrapper is intentionally not included; nothing here is packaged into a
Skill archive.
