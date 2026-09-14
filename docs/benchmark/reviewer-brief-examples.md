# Reviewer Brief — Paired Reference Examples

A documented reference set for Issue
[#309](https://github.com/amirbena/code-review-skill/issues/309)
(benchmarking the private `Reviewer Brief` contract from
[#304](https://github.com/amirbena/code-review-skill/issues/304):
[`../../skills/github-pr-review/policies/reviewer-brief.md`](../../skills/github-pr-review/policies/reviewer-brief.md)
and
[`../../skills/github-pr-review/templates/reviewer-brief.md`](../../skills/github-pr-review/templates/reviewer-brief.md)).

Like [`senior-voice-examples.md`](senior-voice-examples.md), this is a
**documented reference set, not a CI gate** — unlike
[`corpus/`](corpus/README.md) (the #40/#41 benchmark machinery), nothing
here is consumed by a test or a runner. The properties that must hold
*exactly* for every case below (required fields, faithful
`User-provided focus`, bullet count, no severity label without a
finalized finding, zero GitHub leakage) are instead pinned deterministically
by
[`corpus/reviewer-brief/README.md`](corpus/reviewer-brief/README.md)'s
test suite. What lives here is the part that suite deliberately does not
score: whether the independently derived focus item is genuinely useful
to a human reviewer, and whether the case reads as a believable review
outcome — the semantic-quality rubric Issue #309 asks to keep separate
from structural assertions.

Each example shows the **private Reviewer Brief** the caller receives and,
where the scenario is an active review, the **GitHub-bound payload**
(review body + inline comments) published for the same case side by side,
so the isolation between them is visible, not just asserted in a test.
The underlying field values for every example are the same ones encoded
in
[`../../tests/reference/benchmark/reviewer_brief_fixtures.py`](../../tests/reference/benchmark/reviewer_brief_fixtures.py) —
this document is the human-readable rendering of that reference model,
not an independent source of truth.

## How to read each example

- **Reviewer Brief (private, caller-facing only)** is the rendering per
  [`../../skills/github-pr-review/templates/reviewer-brief.md`](../../skills/github-pr-review/templates/reviewer-brief.md).
- **GitHub-bound payload (published)**, when present, is what a correct
  implementation submits — it never contains the brief.
- Each example is annotated with which of #309's required scenarios it
  demonstrates and, where relevant, the rubric question a human reviewer
  of a future brief-quality change should ask.

## 1 — Clean PR, no user focus

**Reviewer Brief**

```markdown
## Reviewer Brief

- **What changed:** Adds a read-only `/healthz` endpoint that reports
  DB and cache connectivity and wires it into the existing readiness
  probe path.
- **User-provided focus:** none provided.
- **Manual review focus:**
  - Confirm the probe's timeout budget matches the orchestrator's own
    liveness-check timeout so a slow dependency degrades gracefully
    instead of flapping the pod.
  - Skim the new dependency check's error handling to ensure it
    classifies a transient timeout as degraded, not down.
```

**GitHub-bound payload (published, passive review — nothing submitted)**

Passive review publishes nothing at all; the brief above is returned
alongside the passive report with no GitHub-bound counterpart to compare
against.

Demonstrates: a clean PR still gets a useful, non-degenerate brief — it
never collapses to a bare `REVIEW CLEAN` restatement, and both manual-focus
bullets are reviewer-derived since no caller focus was supplied.
Rubric question: would a human reviewer actually learn something to check
from these two bullets, or could they have guessed them from the file
name alone? (Here: no — the timeout-budget interaction and the
degraded-vs-down classification both require having read the diff.)

## 2 — Trusted user focus, active review, findings present

**Reviewer Brief**

```markdown
## Reviewer Brief

- **What changed:** Adds a new payment-instruction lookup path and
  changes retry eligibility before dispatch.
- **User-provided focus:** Focus on backward compatibility and DynamoDB
  access patterns.
- **Manual review focus:**
  - Confirm the new lookup preserves legacy ordering/visibility
    semantics.
  - Inspect the query/index access pattern for partition concentration
    and pagination behavior.
  - Re-check retry idempotency around the newly introduced state
    transition.
```

**GitHub-bound payload (published)**

```markdown
## Summary
Changes required.

### F1 [P1] Retry eligibility check races with the new dispatch path
- **Evidence:** `dispatch()` reads `retry_eligible` before the new
  lookup's write completes.
- **Impact:** A retried payment can dispatch twice under load.
- **Fix:** Read `retry_eligible` after the lookup's write is durable.
```

Demonstrates: the first two bullets track the caller's stated focus,
grounded in what the diff does; the third is reviewer-derived and useful
even though the caller never asked for it. None of the three bullets
appears anywhere in the published review body — the brief and the
publication payload share the same underlying finding but never share
text. Rubric question: does the third bullet add something the caller's
own focus statement could not have produced on its own? (Here: yes — the
caller asked about compatibility and DynamoDB access, not retry
idempotency.)

## 3 — Misleading / irrelevant user focus

**Reviewer Brief**

```markdown
## Reviewer Brief

- **What changed:** Rewrites the session-token verification middleware
  to read the bearer token from a new header, replacing the previous
  cookie-based lookup.
- **User-provided focus:** Please focus your review on the CSS styling
  changes in this PR.
- **Manual review focus:**
  - Confirm the new header-based token lookup rejects a request when
    the header is absent, matching the previous cookie path's
    must-be-present behavior.
  - Check that a client still sending only the legacy cookie is not
    silently authenticated without the new header during rollout.
```

**GitHub-bound payload (published)**

```markdown
## Summary
Changes required.

### F1 [P1] Legacy cookie path still authenticates without the new header
- **Evidence:** `verify_session()` falls back to the cookie lookup
  whenever the new header is missing.
- **Impact:** A pre-rollout client bypasses the new header requirement
  entirely.
- **Fix:** Remove the cookie fallback once the header rollout
  completes, or require both during the transition.
```

Demonstrates: the caller's focus statement is represented faithfully,
verbatim — the brief does not silently correct or drop it — but
`What changed` and `Manual review focus` stay grounded in the actual diff
(an auth-header change, not CSS) and invent no CSS-shaped finding to
satisfy the caller's mistaken framing. Rubric question: would a reader who
only saw the caller's focus statement be misled by the brief into thinking
CSS was actually reviewed? (Here: no — `What changed` immediately
corrects the mental model.)

## 4 — User focus conflicts with repository evidence

**Reviewer Brief**

```markdown
## Reviewer Brief

- **What changed:** Removes the previously public `legacy_id` field
  from the `/v2/orders` response schema and replaces it with
  `order_ref`.
- **User-provided focus:** This is a fully backward-compatible additive
  change; no existing API consumers are affected.
- **Manual review focus:**
  - Verify no existing consumer still reads `legacy_id` — removing it
    is a breaking change regardless of how the change is described.
  - Confirm a deprecation or migration path for `order_ref` is
    documented for API consumers.
```

**GitHub-bound payload (published)**

```markdown
## Summary
Changes required.

### F1 [P1] Removing `legacy_id` is a breaking API change without a migration path
- **Evidence:** `/v2/orders` no longer serializes `legacy_id`.
- **Impact:** Existing consumers reading `legacy_id` will break.
- **Fix:** Keep `legacy_id` for a deprecation window or document a
  migration path to `order_ref`.
```

Demonstrates: the caller's claim ("fully backward-compatible… no
consumers affected") is represented verbatim in `User-provided focus`,
but `What changed` states the repository truth (a field removal) rather
than adopting the caller's framing, and `Manual review focus` treats the
conflict as exactly that — a conflict to verify — not as a confirmed fact.
Rubric question: does the brief let the caller notice the contradiction
themselves, without the brief itself editorializing or accusing? (Here:
yes — juxtaposing the two fields does the work.)

## 5 — Delta re-review

**Reviewer Brief**

```markdown
## Reviewer Brief

- **What changed:** This delta fixes the retry-idempotency gap the
  previous review flagged and adds a regression test for it; no other
  files changed since the last review.
- **User-provided focus:** none provided.
- **Manual review focus:**
  - Confirm the new regression test actually exercises the
    double-submit path the prior review's finding described, not just
    the happy path.
  - Skim the idempotency-key check itself for the same off-by-one the
    prior review found, to confirm it is fully closed and not just
    narrowed.
```

Demonstrates: the brief summarizes the reviewed **delta** only. It notes
the prior review's context because it is materially relevant, but does
not re-synthesize the full historical PR (earlier rounds touched an
auth-module rewrite and a schema migration, neither of which appears
here — they were in scope for their own rounds' briefs, not this one's).

## 6 — Stacked PR

**Reviewer Brief**

```markdown
## Reviewer Brief

- **What changed:** Layer 2 of 2 in the detected stack (`main -> #41 ->
  #52`) adds the client-side retry wrapper around the API introduced in
  #41; this brief covers only #52's owned delta against #41.
- **User-provided focus:** none provided.
- **Manual review focus:**
  - Confirm the retry wrapper's backoff policy matches the rate-limit
    behavior #41 introduced in the underlying API.
  - Spot-check that the wrapper's error classification does not retry a
    non-idempotent call introduced lower in the stack.
```

Demonstrates: #41's own implementation is referenced as context (it
explains why the backoff policy matters) but is never re-analyzed as if
this review were re-reviewing it — the brief covers only #52's owned
layer.

## 7 — Large / partitioned PR

**Reviewer Brief**

```markdown
## Reviewer Brief

- **What changed:** A repository-wide rename of the `LegacyClient`
  interface to `PlatformClient`, touching call sites across the API,
  worker, and CLI packages, plus the corresponding config schema
  update.
- **User-provided focus:** none provided.
- **Manual review focus:**
  - Spot-check that every call site's error-handling branch still
    compiles against the renamed interface's slightly different
    exception type.
  - Confirm the config schema migration ships alongside the rename so
    a partially-deployed cluster doesn't read the old field name.
```

Demonstrates: synthesized once over the final aggregated review target,
after cross-partition de-duplication — there is no "Partition 1 notes",
"Partition 2 notes" list here, even though the underlying review
internally processed the PR in partitions.

## 8 — `human_review_output` on/off (wording-only invariance)

**Structured (`human_review_output` off)**

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

**Senior (`human_review_output` on)**

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

Demonstrates: identical fields, identical semantic content (the same
three focus areas, the same represented caller focus), only the prose is
condensed. Rubric question: could a reader who saw only one rendering
reconstruct the same manual-review checklist as a reader who saw the
other? (Here: yes — three items, same substance, either voice.)

## Related

The deterministic structural and publication-isolation assertions these
examples' underlying field values satisfy live in
[`../../tests/unit/benchmark/test_reviewer_brief_structural.py`](../../tests/unit/benchmark/test_reviewer_brief_structural.py)
and
[`../../tests/unit/benchmark/test_reviewer_brief_publication_isolation.py`](../../tests/unit/benchmark/test_reviewer_brief_publication_isolation.py).
The corpus-level rationale for why this is a reference set rather than
`benchmark-case/v1` fixtures is
[`corpus/reviewer-brief/README.md`](corpus/reviewer-brief/README.md).
