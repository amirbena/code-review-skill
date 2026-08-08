# Template — Inline Finding

Canonical form for a single inline GitHub review comment, submitted only
as part of one batched review submission (see
[`../policies/review-output.md`](../policies/review-output.md), "Batched
review construction and submission" — never published individually as
findings are discovered). Renders the shared finding shape from
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md)
for GitHub's inline-comment surface.

```text
[<severity>] <short, concrete title>

Evidence: <concrete evidence — what the code actually does>

Impact: <concrete engineering consequence — why it matters>

Recommended direction: <concrete correction direction, when useful>
```

## Rules

- severity always visible first, in the `[P0]` / `[P1]` / `[P2]` form;
- title is concise (a few words, not a sentence) and names the actual
  defect, not a vague category;
- Evidence and Impact are each a line or two — the GitHub UI already
  supplies file and line context, so do not add redundant `file:`,
  `line:`, `reviewed_head:`, or other machine fields;
- evidence-based (see
  [`../../../shared/policies/evidence.md`](../../../shared/policies/evidence.md))
  — no generic "this could be improved" comments with no concrete basis;
- this is the finding's one authoritative full representation once
  published — the review body references it only via the
  summary-pointer form (see
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "Rules") rather than repeating it;
- no duplicated findings across multiple lines or against an
  already-reviewed, unchanged HEAD (see
  [`../policies/pr-scope.md`](../policies/pr-scope.md), "Existing
  review awareness");
- attach to the narrowest relevant changed line; if a finding is
  cross-cutting, spans multiple files, or otherwise cannot attach
  meaningfully to one line, it belongs in the review body instead (see
  [`../policies/finding-placement.md`](../policies/finding-placement.md), "Inline
  comment eligibility").

## Example

```text
[P1] Incomplete pagination can produce a false clean review

Evidence: This path retrieves only the first page of changed files and
does not continue using the returned pagination cursor.

Impact: Files outside the first page may never be reviewed while the
workflow can still reach REVIEW CLEAN.

Recommended direction: Exhaust pagination and verify scope completeness
before permitting a clean review decision.
```
