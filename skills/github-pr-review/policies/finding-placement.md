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
  completeness itself, or forcing an inline location would mislead. A
  **consolidated root-cause finding** (one shared cause reaching multiple
  call paths, per
  [`../../../shared/policies/review-scope.md`](../../../shared/policies/review-scope.md),
  "The authoritative consolidated finding") is placed here with its
  affected-locations list — one finding, not one inline comment per
  affected call path. An optional short, non-authoritative inline pointer
  at the shared cause is allowed on the same terms as the other body
  cases below.
  Rendered with the full-finding form in
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md)
  inside [`../templates/external-review-summary.md`](../templates/external-review-summary.md).

No valid inline anchor is never a reason to drop a finding — it changes
where the finding's one authoritative full representation lives, never
whether it is represented at all. Where an inline comment *is* used,
resolve its anchor per "Anchor at the fix/action location" below.

## Anchor at the fix/action location

An inline finding's **publication anchor** is its canonical fix/action
location — the line an author changes to resolve the finding — when that
location is resolved and GitHub permits an inline comment there. It is
not a line merely where the problem is observable, and not a line chosen
because GitHub happens to allow a comment there. "Commentable in the
GitHub diff" is a publication constraint; it is never evidence that a
line is the correct semantic anchor, and it never discovers or overrides
the fix/action location. The three concepts — evidence/detection
location, canonical fix/action location, and publication anchor — are
defined in
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Fix/action location, evidence location, publication."

### Anchor selection order

Resolve the anchor in this fixed order; the earlier steps are semantic
and outrank the later ones:

1. Identify the semantically valid fix/action candidate(s) — the place(s)
   the repository must change to resolve the finding.
2. Discard candidates that are only evidence/observation locations unless
   they are also valid fix/action locations.
3. If more than one equally valid fix/action candidate remains, select
   deterministically: the narrowest changed range enclosing the
   fix/action location, then the lowest changed line number, then the
   `/`-normalized path in lexical order. Same finding + same target state
   → the same choice every run.
4. Only now evaluate GitHub inline-commentability. A lower line number or
   a merely commentable diff line never outranks a semantically better
   fix/action location, and this step never sends the selection back to a
   candidate discarded in step 2.

### When evidence and fix/action locations differ

When the fix/action location is resolved, differs from where evidence was
observed, and is inline-commentable, anchor the inline comment at the
fix/action location. The comment body may reference the evidence/source
location — including one in another file — as supporting context. The
finding's `Location` stays the fix/action location.

### Fix/action location resolved but not inline-commentable

When the canonical fix/action location is resolved but GitHub cannot take
an inline comment there (outside the PR diff, not within an added/changed
hunk, or a GitHub API/diff limitation), the canonical fix/action location
is unchanged. Move the finding's full representation into the review body
(the full-finding form) with its explicit `path:line(-range)` and
actionable remediation. Do not attach it to an unrelated or merely-nearby
line to obtain an inline comment. An inline pointer at an in-diff
evidence location is optional, short, and clearly non-authoritative — a
navigation aid to the body finding, not a second copy — and is omitted
when it would add ambiguity rather than help.

### Fix/action location unresolved

When evidence is established but no actionable fix/action location can be
confidently determined, the finding's full representation goes in the
review body and states explicitly that the actionable location is
unresolved, carrying the evidence location and the evidence per
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"No silent promotion." It is never anchored to the evidence line as
though that were the fix.

### What anchor selection does not change

Anchor selection and any inline→body fallback change only *where* the
finding is published. They never change the finding's `Location`, its
identity, its severity, deduplication, the
one-authoritative-representation rule, or the single batched review
submission. Finding identity is keyed on the canonical semantic
fix/action location, not on the GitHub publication anchor — see
[`pr-scope.md`](pr-scope.md), "Existing review awareness."

### Rendering voice does not change placement

`human_inline_findings` (see
[`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
"`human_inline_findings` derived default and phrasings") re-voices an
inline finding as concise senior-engineer prose instead of the
`[<severity>] / Evidence / Impact / Fix` block. `human_review_output`
similarly re-voices a finding rendered in full **in the body** (per
"Fallback: a finding with no valid inline anchor" above, and passive
review's own always-in-body findings) via the human full rendering in
[`../../../shared/templates/finding-rendering.md`](../../../shared/templates/finding-rendering.md),
"Canonical human full rendering." Both are **presentation-only and
orthogonal to this policy**: rendering voice never changes inline-comment
eligibility, the anchor-selection order above, the deterministic tie-break, the
canonical fix/action location, the evidence/detection location, or the
inline→body fallback for a fix/action location that is unresolved or not
inline-commentable. A finding is *placed* identically whether it renders
as the structured block or as its human rendering (inline or full);
only the comment's or body finding's wording differs. Rendering voice
never moves a finding between the body and an inline comment — that
decision is made only by this policy's anchor-selection and fallback
rules above, independent of which rendering voice is in effect. This
policy remains authoritative for placement regardless of rendering
voice.

## No duplicate findings

Each finding has exactly one authoritative full representation, per
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Rules." When a finding is published in full as an inline comment, the
review body's Findings section uses only the summary-pointer form
(severity, title, file:line) for it — never the full evidence/impact/fix
text a second time. When a finding has no inline
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

This reactive fallback and the proactive "Fix/action location resolved
but not inline-commentable" case above converge on the same shape: the
review-body full finding keeps its canonical `Location` and its identity,
and the GitHub rejection never rewrites either.
