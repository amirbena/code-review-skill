# Policy — PR Scope

Governs complete PR scope retrieval, pagination, and awareness of prior
review activity for `github-pr-review`. Canonical index:
[`github-review.md`](github-review.md). Distinct from the shared,
technology-neutral
[`review-scope.md`](../../../shared/policies/review-scope.md) policy
(what any Code Review Skill examines) — this file adds only what is
specific to retrieving that scope from GitHub.

## Complete PR scope and pagination

Never assume one API/CLI response contains the complete PR. Follow pagination
to exhaustion for changed files and for every collection used to establish
review state or deduplication, including reviews, review comments, issue
comments, commits, and relevant checks/statuses. Prefer page sizes up to the
documented maximum, but use response pagination metadata rather than a short
page guess where available.

Compare the retrieved changed-file total with authoritative PR metadata when
available. GitHub's REST changed-files endpoint is paginated and returns at
most 3,000 files. If the authoritative count exceeds an API cap, pages cannot
be exhausted, or totals disagree, obtain the complete name/status set from
repository Git data (base...reviewed HEAD) when available. Otherwise return
`REVIEW INCOMPLETE`; never approve or claim the full PR was reviewed.

Treat per-file API patches and aggregate diff media as potentially absent or
truncated. Fall back to fetching the exact base and reviewed HEAD and computing
the diff locally, or retrieve exact file blobs/diffs individually. Validate
that every changed path has an inspectable representation or an explicit
binary/opaque limitation under
[`../../../shared/policies/file-reviewability.md`](../../../shared/policies/file-reviewability.md).
If material scope remains unavailable, report what is missing, publish no
formal Approve/Request Changes decision, and do not lower review standards or
sample arbitrary files.

## Existing review awareness

Before publishing an active review, retrieve all relevant paginated reviews,
review comments, and issue comments from the authenticated reviewer/workflow.
Do not suppress another human reviewer's independent feedback merely because
it is similar.

For each candidate finding, compute a deterministic internal identity from
the PR HEAD SHA, normalized file path, relevant side and line/range (or a
stable cross-cutting location), severity, and normalized finding title or
category. Human-facing `F1`, `F2`, ... display IDs remain separate; a hash or
serialized identity need not be exposed. When the same workflow already
published the same identity for the same PR and HEAD, do not publish the
finding again, though it may still appear in returned reasoning. If complete
prior activity cannot be retrieved, report deduplication uncertainty rather
than asserting idempotency.

A changed HEAD starts a new authoritative review state. Prior findings may
inform investigation, but they are neither automatically resolved nor
automatically applicable. Retrieve and review the complete new state; an old
approval or duplicate identity never authorizes the new HEAD.
