# Template — Inline Finding

Canonical form for a single inline GitHub review comment, submitted only
as part of one batched review submission (see
[`../policies/review-output.md`](../policies/review-output.md), "Batched
review construction and submission" — never published individually as
findings are discovered). Renders the shared finding shape from
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md)
for GitHub's inline-comment surface — the same fields and quality
contract, projected onto a surface that already supplies the file/line
anchor and the comment's own identity, so `id` and `Location` are
omitted here (see
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Canonical inline rendering").

```text
[<severity>] <short, concrete title>

Evidence: <concrete evidence — what the code actually does>

Impact: <concrete engineering consequence — why it matters>

Fix: <concrete correction direction, when useful>
```

A finding that meets
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"When a longer explanation is justified" (non-obvious cross-file
behavior, a concurrency/ordering bug, a security implication, a complex
invariant violation, or evidence needing brief context) adds one
`Details:` line between `Evidence:` and `Impact:`, kept to a short
paragraph. An ordinary finding does not.

## Rules

- severity always visible first, in the `[P0]` / `[P1]` / `[P2]` form;
- title is concise (a few words, not a sentence) and names the actual
  defect, not a vague category;
- each field is concise by default — `Evidence`, `Impact`, and `Fix` are
  a line or two; the GitHub UI already supplies file and line context, so
  do not add redundant `id:`, `Location:`, `file:`, `line:`,
  `reviewed_head:`, or other machine fields;
- a longer explanation is the controlled exception, not the default —
  only a finding in one of the
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "When a longer explanation is justified" categories gets a `Details:`
  line, and even then it stays a short paragraph, never an essay;
- evidence-based (see
  [`../../../shared/policies/evidence.md`](../../../shared/policies/evidence.md))
  — no generic "this could be improved" comments with no concrete basis;
- `Fix` is concise and reviewer-facing; never append a local full
  **Implementation prompt** or a coding-agent workflow;
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

Fix: Exhaust pagination and verify scope completeness before permitting
a clean review decision.
```
