# Template — Reviewer Brief

Private, caller-facing rendering. Semantics, boundaries, and synthesis
sources: [`../policies/reviewer-brief.md`](../policies/reviewer-brief.md).
Never part of the GitHub publication payload
([`../templates/external-review-summary.md`](../templates/external-review-summary.md)
is the complete review body; this template is not one of its inputs and
is never rendered into it).

## Canonical shape

```markdown
## Reviewer Brief

- **What changed:** <1-3 sentence synthesis of the actual change>
- **User-provided focus:** <trusted caller focus, or `none provided`>
- **Manual review focus:**
  - <highest-value area to inspect manually>
  - <second area when materially useful>
- **Open questions / assumptions:** <only when unresolved human judgment remains>
```

`Open questions / assumptions` is omitted entirely, not rendered empty,
when nothing unresolved remains.

## Clean review

```markdown
## Reviewer Brief

- **What changed:** Adds a read-only `/healthz` endpoint that reports
  DB and cache connectivity, and wires it into the existing readiness
  probe path.
- **User-provided focus:** none provided.
- **Manual review focus:**
  - Confirm the probe's timeout budget matches the orchestrator's own
    liveness-check timeout so a slow dependency degrades gracefully
    instead of flapping the pod.
  - Skim the new dependency check's error handling — it should classify
    a transient timeout as `degraded`, not `down`.
```

Even with no findings, `What changed` and `Manual review focus` stay
concrete and populated — the brief never degrades to a bare `no issues`
restatement, and `Manual review focus` names areas to inspect, not
invented defects.

## Review with findings

```markdown
## Reviewer Brief

- **What changed:** Adds a new payment-instruction lookup path and
  changes retry eligibility before dispatch.
- **User-provided focus:** Backward compatibility and DynamoDB access
  patterns.
- **Manual review focus:**
  - Confirm the new lookup preserves legacy ordering/visibility
    semantics.
  - Inspect the query/index access pattern for partition concentration
    and pagination behavior.
  - Re-check retry idempotency around the newly introduced state
    transition.
```

The first two bullets track the caller's stated focus, grounded in what
the diff actually does; the third is reviewer-derived and stays useful
even though the caller never asked for it. None of the three duplicates a
finding's `Evidence` / `Impact` / `Fix` block — the inline comments and
review body already own that detail (see
[`../policies/review-output.md`](../policies/review-output.md), "Final
summary").

## Delta re-review

```markdown
## Reviewer Brief

- **What changed:** This delta fixes the retry-idempotency gap the
  previous review flagged and adds a regression test for it; no other
  files changed since the last review.
- **User-provided focus:** none provided.
- **Manual review focus:**
  - Confirm the new regression test actually exercises the double-submit
    path the prior review's finding described, not just the happy path.
```

The brief summarizes the reviewed **delta**, not the full PR history —
per [`../policies/reviewer-brief.md`](../policies/reviewer-brief.md),
"Composition with invocation modes." Noting the prior review's context is
allowed because it is materially relevant to understanding this delta; it
is not a re-synthesis of the whole PR.

## Stacked PR

```markdown
## Reviewer Brief

- **What changed:** Layer 2 of 2 in the detected stack (`main -> #41 ->
  #52`) adds the client-side retry wrapper around the API introduced in
  #41; this brief covers only #52's owned delta against #41.
- **User-provided focus:** none provided.
- **Manual review focus:**
  - Confirm the retry wrapper's backoff policy matches the rate-limit
    behavior #41 introduced in the underlying API.
```

The brief covers the **effective reviewed layer** — this PR's owned delta
— not the entire stack; the lower layer is read-only context exactly as
it is for findings.

## Large-PR partitioning

```markdown
## Reviewer Brief

- **What changed:** A repository-wide rename of the `LegacyClient`
  interface to `PlatformClient`, touching call sites across the API,
  worker, and CLI packages, plus the corresponding config schema update.
- **User-provided focus:** none provided.
- **Manual review focus:**
  - Spot-check that every call site's error-handling branch still
    compiles against the renamed interface's slightly different
    exception type.
  - Confirm the config schema migration ships alongside the rename so a
    partially-deployed cluster doesn't read the old field name.
```

Synthesized **once**, over the final aggregated review target, after
cross-partition de-duplication — never one brief per partition and never
a list of per-partition notes strung together.

## `human_review_output` (wording only)

```markdown
## Reviewer Brief

What changed: a new payment-instruction lookup path, plus a change to
retry eligibility before dispatch.

User-provided focus: backward compatibility and DynamoDB access
patterns.

Manual review focus: confirm the new lookup keeps legacy
ordering/visibility semantics; look at the query/index access pattern
for partition concentration; and re-check retry idempotency around the
new state transition.
```

Same fields, same content, same boundaries — only the prose is
condensed into the concise senior-engineer voice per
[`../policies/review-output.md`](../policies/review-output.md), "Concise
human-style summary (opt-in)." The heading, the set of fields present,
and every semantic constraint in
[`../policies/reviewer-brief.md`](../policies/reviewer-brief.md) are
unchanged.

## Rules

- Always render `## Reviewer Brief` as its own top-level section of the
  **caller-facing returned result**, distinct from and never folded into
  the GitHub-shaped review body.
- `What changed`, `User-provided focus`, and `Manual review focus` are
  always present; `Open questions / assumptions` is present only when it
  carries genuine unresolved judgment.
- 2-4 `Manual review focus` bullets; never exhaustive coverage, never a
  restatement of the findings list.
- No `Evidence` / `Impact` / `Fix` blocks, no finding IDs, no severity
  labels unless citing an actual finalized finding reported elsewhere.
- No scratchpad reasoning, no authorization state, no secrets, no hidden
  runtime metadata.
- Never emitted into, or referenced by, the review body
  ([`external-review-summary.md`](external-review-summary.md)) or an
  inline comment ([`inline-finding.md`](inline-finding.md)).
