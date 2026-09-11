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
[<severity> (<compact meaning>)] <short, concrete title>

Evidence: <concrete evidence — what the code actually does>

Impact: <concrete engineering consequence — why it matters>

Fix: <concrete correction direction, when useful>
```

`<compact meaning>` is this Skill's severity legend — `P0 (Critical)` /
`P1 (Blocking)` / `P2 (Non-Blocking)` — per
[`../policies/review-output.md`](../policies/review-output.md),
"Reader-visible severity legend": e.g. `[P1 (Blocking)] Incomplete
pagination can produce a false clean review`. It is rendered once, in
this heading, never repeated as a separate explanatory sentence in
`Evidence`, `Impact`, or `Fix`.

A finding that meets
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"When a longer explanation is justified" (non-obvious cross-file
behavior, a concurrency/ordering bug, a security implication, a complex
invariant violation, or evidence needing brief context) adds one
`Details:` line after `Fix`, kept to a short paragraph, only when
`include_finding_details=true` or a finding-level decision enables it. The
GitHub default is `false`. An ordinary finding does not.

```text
Details: <supporting technical context, concise>
```

## Rules

- severity always visible first, in the `[P0 (Critical)]` /
  `[P1 (Blocking)]` / `[P2 (Non-Blocking)]` form (see
  [`../policies/review-output.md`](../policies/review-output.md),
  "Reader-visible severity legend");
- **one authoritative representation, minimum self-contained unit.** This
  inline comment is the finding's one full representation once published:
  severity + compact title in the heading, then the concrete what/why/fix
  carried by `Evidence` / `Impact` / `Fix`. It is self-contained — a
  reader needs nothing else to act on it — and it is never a near-
  duplicate of the review-body line that points to it: the body carries
  only the summary-pointer form (severity, title, location), never a
  second copy of this comment's `Evidence` / `Impact` / `Fix` content
  (see [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "Rules");
- no meta-commentary about the review process — state the result, not
  that a file was inspected or a reproduction attempted, beyond what the
  `Validation` / runtime-validation contract already records;
- no agent/model/tool disclosure anywhere in this comment (see
  [`../policies/review-output.md`](../policies/review-output.md), "No
  agent/model/tool disclosure");
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
  — no generic "this could be improved" / "consider refactoring" comments
  with no concrete basis, and no praise on an inline comment;
- `Fix` is concise and reviewer-facing; never append a local full
  **Implementation prompt** or a coding-agent workflow;
- no duplicated findings across multiple lines or against an
  already-reviewed, unchanged HEAD (see
  [`../policies/pr-scope.md`](../policies/pr-scope.md), "Existing
  review awareness");
- anchor at the finding's canonical fix/action location — the line an
  author changes to resolve it — not merely where the problem is
  observable and not a line chosen because GitHub allows a comment there
  (see
  [`../policies/finding-placement.md`](../policies/finding-placement.md),
  "Anchor at the fix/action location"). The `Evidence` text may name a
  distinct evidence/source location, including one in another file. If
  the fix/action location is unresolved, is not inline-commentable, or
  the finding is cross-cutting / spans multiple files, the finding
  belongs in the review body instead (see the same policy, "Inline
  comment eligibility");
- a **consolidated root-cause finding** (one shared cause reaching two or
  more call paths) is placed in the review body, not inline, and is never
  split into one inline comment per affected call path (see
  [`../policies/finding-placement.md`](../policies/finding-placement.md),
  "Inline comment eligibility"). If a short non-authoritative inline
  pointer at the shared cause is used, it names the affected call paths in
  its prose — the required, exhaustive affected-locations list lives with
  the body finding, per
  [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
  "Affected locations on a consolidated finding".

## Example

```text
[P1 (Blocking)] Incomplete pagination can produce a false clean review

Evidence: This path retrieves only the first page of changed files and
does not continue using the returned pagination cursor.

Impact: Files outside the first page may never be reviewed while the
workflow can still reach REVIEW CLEAN.

Fix: Exhaust pagination and verify scope completeness before permitting
a clean review decision.
```

## Human-rendered inline finding (opt-in)

When the invocation normalizes `human_inline_findings` (see
[`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
"`human_inline_findings` derived default and phrasings" — its default is
derived from `human_review_output`, so senior-mode reviews get this by
default), this comment is rendered in the concise senior-engineer voice
from
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md),
"Canonical human inline rendering" instead of the
`[<severity>] / Evidence / Impact / Fix` block above — a short heading
that keeps the severity, its compact legend meaning, and names the
finding, then compact prose:

```text
P2 (Non-Blocking): Retry eligibility logic is duplicated

The same eligibility decision is implemented in both the sync and async
flows, so the behaviour can drift when one path changes and the other is
missed. I'd centralise it behind one policy/helper and have both flows
call that.
```

This is a re-voicing of the **same finding**, not a different or weaker
one. Unchanged:

- **severity** — still shown first, in the heading, with the same
  compact legend meaning as the structured form (`P2 (Non-Blocking): …`,
  not `[P2] …`);
- the mandatory What / Where / Evidence / Impact / Fix core — evidence,
  the engineering consequence when it is material, and the actionable
  correction direction are still all present, carried by the prose; a
  genuine open question stays a question; no praise, no generic
  "consider refactoring";
- evidence and remediation requirements, finding identity and
  deduplication, the one-authoritative-representation rule, same-HEAD /
  re-review awareness, and the batched single review submission;
- the **publication anchor** — the comment still sits at the finding's
  canonical fix/action location per
  [`../policies/finding-placement.md`](../policies/finding-placement.md),
  "Anchor at the fix/action location", the prose may still name a
  distinct evidence/source location (including one in another file), and
  an unresolved or not-inline-commentable fix/action location still
  falls back to the review body per that policy. Rendering voice never
  moves a finding.

A justified longer explanation (`include_finding_details` or a
finding-level decision) folds into the prose as one extra short
paragraph rather than a `Details:` label. When `human_inline_findings`
is off — explicitly, or because `human_review_output` is off and nothing
enabled it — this comment uses the structured block above, unchanged.
