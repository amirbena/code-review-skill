# Template — Inline Finding

Canonical form for a single inline GitHub review comment (see
[`../policies/github-review.md`](../policies/github-review.md)):

```text
[P1] Short finding title

<brief explanation of what is wrong and why it matters>

<recommended direction, when useful>
```

## Rules

- severity always visible first, in the `[P0]` / `[P1]` / `[P2]` form;
- title is concise (a few words, not a sentence);
- description is short — normally no more than **five short lines**
  total;
- evidence-based (see [`../policies/evidence.md`](../policies/evidence.md))
  — no generic "this could be improved" comments with no concrete basis;
- no duplicated findings across multiple lines or against an
  already-reviewed, unchanged HEAD (see
  [`../policies/github-review.md`](../policies/github-review.md), "Existing
  review awareness");
- attach to the narrowest relevant changed line; if a finding is
  cross-cutting and cannot attach meaningfully to one line, it belongs in
  the final summary instead (see
  [`external-review-summary.md`](external-review-summary.md)).

## Example

```text
[P1] Missing null check before dereference

`user` may be `nil` here when the lookup misses (see the early-return
above). Dereferencing it will panic.

Guard with an explicit nil check and return the existing not-found error.
```
