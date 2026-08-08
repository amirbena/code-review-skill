# Shared Template — Finding

The canonical shape of a single finding, shared by both Skills' output
templates: `local-code-review`'s own `templates/local-review-report.md`
and `github-pr-review`'s own `templates/inline-finding.md`. Each Skill
renders this shape for its own delivery surface (a plain-text report vs.
a GitHub inline comment) — the underlying fields do not diverge.

## Fields

- **id** — a stable finding identifier within the review (e.g. `F1`,
  `F2`), for referencing the same finding across a re-review;
- **severity** — exactly one of `P0` / `P1` / `P2`, per
  [`../policies/severity.md`](../policies/severity.md);
- **title** — a short, concrete problem statement;
- **location** — file, and line/range where the reviewed surface exposes
  one (a GitHub diff or a local file always does; some contexts may not);
- **evidence** — the concrete basis for the finding, per
  [`../policies/evidence.md`](../policies/evidence.md);
- **recommended correction** — a concrete direction, not a full patch —
  neither Skill implements fixes.

## Canonical rendering

```text
<id> [<severity>] <short title>
file: <path>
line: <line or range, when available>
evidence: <concrete evidence>
recommended: <recommended direction>
```

## Rules

- one severity per finding, always visible first;
- evidence-based — no generic "this could be improved" without a
  concrete basis;
- no duplicate findings for the same underlying issue;
- a recommended correction is a direction, never an implemented fix.
