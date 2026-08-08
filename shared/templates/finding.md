# Shared Template — Finding

The canonical shape of a single finding, shared by both Skills' output:
`local-code-review`'s own `templates/local-review-report.md` and
`github-pr-review`'s own `templates/inline-finding.md` /
`templates/external-review-summary.md`. Each Skill renders this shape for
its own delivery surface (a plain-text report, a GitHub inline comment, or
a review-body entry) — the underlying fields and quality contract do not
diverge.

## Fields

- **id** — a stable finding identifier within the review (e.g. `F1`,
  `F2`), for referencing the same finding across a re-review;
- **severity** — exactly one of `P0` / `P1` / `P2`, per
  [`../policies/severity.md`](../policies/severity.md), always visible
  first;
- **title** — a short, concrete problem statement (what is actually
  wrong — not a vague category like "pagination issue");
- **location** — the most precise useful location available: file,
  changed line/range, symbol/function, or narrow section. Prefer
  precision; never invent a location that doesn't exist;
- **evidence** — the concrete implementation behavior supporting the
  finding, per [`../policies/evidence.md`](../policies/evidence.md) — not
  speculation;
- **impact** — the concrete engineering consequence (incorrect behavior,
  missed review scope, false clean decision, runtime failure, data
  corruption, security exposure, unsafe merge, maintainability
  regression, misleading output, loss of portability, etc.) — this must
  say *why it matters*, not merely restate the title;
- **recommended direction** — a concrete correction direction, not a
  full patch. The reviewer identifies the problem and the direction of
  the fix; it does not implement the fix.

## Finding quality contract

Every finding must independently answer: **What? Where? Evidence?
Impact? Recommended direction?** A finding is not publishable until all
five are present. Do not present a finding as factual without evidence
sufficient to support it; label genuine uncertainty as such rather than
asserting it as a confirmed defect (see
[`../policies/evidence.md`](../policies/evidence.md)).

## Canonical full rendering

Used wherever a finding needs its complete, standalone representation —
a local review report, or a GitHub review body when no valid inline
anchor exists:

```markdown
### <id> [<severity>] <short, concrete title>

**File:** `<path>:<line-or-range>`

**Evidence**
<concrete evidence>

**Impact**
<concrete engineering consequence>

**Recommended direction**
<concrete correction direction, not a patch>
```

## Canonical summary-pointer rendering

Used when the finding's full representation is published elsewhere (for
example, a GitHub inline comment) and the review body only needs to
reference it — never both in full:

```markdown
- **<severity> — <short title>**
  `<path>:<line-or-range>`
```

## Rules

- one severity per finding, always visible first;
- evidence-based — no generic "this could be improved" without a
  concrete basis;
- impact is explicit and distinct from the title — it explains
  consequence, not just restates the defect;
- no duplicate findings for the same underlying issue;
- a finding has exactly one authoritative full representation. If it is
  published in full at one location (e.g. inline), every other location
  uses the summary-pointer form instead of repeating the full finding;
- a recommended correction is a direction, never an implemented fix.
