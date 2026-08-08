# Policy — Finding Placement

Governs where a finalized finding's one authoritative representation
lives (inline comment vs. review body) for `github-pr-review`. Canonical
index: [`github-review.md`](github-review.md). Builds on the shared
[`evidence.md`](../../../shared/policies/evidence.md) and
[`severity.md`](../../../shared/policies/severity.md) policies, which
this file does not duplicate.

## Inline comment eligibility

Not every finding is forced inline. During finalization, resolve each
finding's placement:

- **Inline** — prefer this when the finding maps to a specific changed
  file, a specific changed line or narrow changed range represents the
  issue, that location is valid in the PR diff, and inline placement
  materially improves understanding. Rendered with
  [`../templates/inline-finding.md`](../templates/inline-finding.md).
- **Review body** — used when the issue spans multiple files, is
  architectural/systemic, concerns missing behavior with no natural
  changed-line anchor, the relevant location falls outside the changed
  diff, GitHub cannot attach a comment there, the finding concerns review
  completeness itself, or forcing an inline location would mislead.
  Rendered with the full-finding form in
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md)
  inside [`../templates/external-review-summary.md`](../templates/external-review-summary.md).

No valid inline anchor is never a reason to drop a finding — it changes
where the finding's one authoritative full representation lives, never
whether it is represented at all.

## No duplicate findings

Each finding has exactly one authoritative full representation, per
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Rules." When a finding is published in full as an inline comment, the
review body's Findings section uses only the summary-pointer form
(severity, title, file:line) for it — never the full evidence/impact/
recommended-direction text a second time. When a finding has no inline
comment (no valid anchor, or a rejected location moved to the body per
below), its full representation appears once, in the body.

## Rejected inline location fallback

If GitHub rejects a resolved inline location while constructing or
submitting the review (for example, the line is outside the diff's
commentable range, or a side/position mismatch), the finding MUST NOT be
dropped and MUST NOT be silently reattached to an unrelated line.
Instead, move that finding's full representation into the review body
(the same full-finding form used for non-inline findings) and continue
constructing/submitting the rest of the review normally. Prefer
completing one coherent review submission over abandoning the whole
submission; if the integration cannot recover mid-submission, retry the
review construction once with the affected finding moved to the body,
rather than repeatedly retrying the same rejected inline location.
