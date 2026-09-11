# Shared Policy — Review Stopping Criteria

Applies identically to `local-code-review` and `github-pr-review`. It
defines when a review has done **enough** work to stop — the **coverage
and exit conditions**, scaled by the change-risk depth from
[`change-risk-signals.md`](change-risk-signals.md) and, when it activated,
every partition from [`large-pr-partitioning.md`](large-pr-partitioning.md)
— how an incomplete review is **labeled**, and the one hard rule this
policy exists to enforce: **an incomplete review must never present as a
clean result.**

Without a stated stopping point, a review can run indefinitely on an
ambitious reviewer, or stop arbitrarily short on a rushed one, and a
reader of the final report has no way to tell which happened. This policy
gives "the review is done" a checkable definition instead of leaving it to
per-review judgement.

## Relationship to the rest of the depth/partitioning family

This is the completeness counterpart to the other always-on passes in
this family:
[`change-risk-signals.md`](change-risk-signals.md) decides *how deep* a
review must go; [`repository-expansion.md`](repository-expansion.md)
decides *how far* it looks beyond the diff for a fixed set of triggers;
[`large-pr-partitioning.md`](large-pr-partitioning.md) decides *how an
oversized diff is organized* for review. This policy decides *when all of
that is done* — it introduces no fourth depth model, no new investigation
procedure, and no new evidence standard. It consumes each pass's own
already-defined stop condition (for example
[`review-scope.md`](review-scope.md), "Stop conditions" for bounded
context expansion, or [`repository-expansion.md`](repository-expansion.md)'s
ring ceiling) and asks only whether every pass required for this change
actually reached the stop condition that pass itself already defines.

## Coverage

A review's **coverage** is `complete` when every pass required for the
change's classified depth reached its own defined stop condition, and
`incomplete` otherwise. "Required for the depth" is exactly the set each
owning policy already activates for this change — this policy adds no
passes of its own and removes none:

| Depth (from `change-risk-signals.md`) | Coverage requires |
| --- | --- |
| `standard` | [`review-scope.md`](review-scope.md)'s always-applicable sections reached a conclusion on the complete Review Target; the two always-on classification passes ([`change-risk-signals.md`](change-risk-signals.md), [`repository-expansion.md`](repository-expansion.md)) reported their result, including "none" outcomes. |
| `elevated` | Everything `standard` requires, plus every signal-triggered sub-pass that this change's own facts activated — [`affected-test-analysis.md`](affected-test-analysis.md) when signal-triggered, "Architectural placement and execution-lifecycle fidelity" when its own semantic-risk triggers fired, and every expansion ring [`repository-expansion.md`](repository-expansion.md) scales to this depth — actually reached its own stop condition, not merely attempted. |
| `deep` | Everything `elevated` requires, at `deep`'s wider expansion ring ceiling and diff-size-scaled scope. |

When [`large-pr-partitioning.md`](large-pr-partitioning.md) activated,
coverage requires the above to hold **for every partition individually**,
plus that the aggregation stage in that policy's "Aggregation and
cross-partition de-duplication" actually ran to completion over the full
partition set. A single partition that could not be completed makes the
*whole* review's coverage `incomplete` — coverage is never averaged or
reported per-partition to a reader.

Coverage additionally requires that the complete Review Target itself
— the full changed-file/delta set this review is scoped to — was
actually established. A review that could only inspect part of its own
target (an unresolved pagination limit, an inaccessible file, a required
checkout that could not be prepared, or an equivalent gap in establishing
what the target even is) never reaches `complete` coverage regardless of
how thoroughly the portion it *did* see was reviewed.

## Incomplete triggers (closed set, evaluated per-pass)

Coverage becomes `incomplete` only for one of these reasons — this policy
does not invent open-ended "reviewer felt rushed" grounds, and a pass that
reached its own stop condition (including "insufficient evidence, stop
here" per [`review-scope.md`](review-scope.md), "Stop conditions," which
is itself a *valid, complete* terminal outcome, not a coverage gap) never
counts as incomplete:

1. **A required pass could not be produced** — a tool, worker, or
   investigation step needed by the change's classified depth failed,
   timed out, or returned unusable output, and the reviewer could not
   perform it directly either. (The consuming Skill's own concrete
   instances of this — for example a required GitHub integration that
   cannot establish complete PR state, or a required repository checkout
   that fails to prepare — are owned and enumerated by that Skill's own
   policies; this policy states the general rule they are instances of,
   not a replacement for their own triggers or wording.)
2. **A partition could not be completed**, per
   [`large-pr-partitioning.md`](large-pr-partitioning.md), "Aggregation
   and cross-partition de-duplication."
3. **The complete Review Target could not be established** — see
   "Coverage" above.
4. **A validation run the change's classified depth genuinely depends on**
   to establish or disprove a finding was `unavailable` or `failed` with
   no other way to reach the same conclusion — an ordinary `skipped`
   validation that was optional does not trigger this; only one the
   review had no alternative path to complete.

An **optional** step that failed but was itself recoverable by the
reviewer, or a dimension whose absence does not change what depth
requires (for example a `standard`-depth change with no `elevated`/`deep`
sub-passes to begin with), never makes coverage `incomplete`.

## Labeling — incomplete must never present as clean

Coverage is always emitted with the review, complete or not, the same way
change-risk depth and repository-expansion decisions are always emitted
(see [`../templates/review-summary.md`](../templates/review-summary.md),
"Machine metadata is subordinate"). Coverage is the **one exception** to
that block being purely subordinate: when coverage is `incomplete`, it
also changes what the review's primary Result/Decision renders, because
the whole point of this policy is that an incomplete review must never be
mistaken for a clean one.

```text
coverage == incomplete  → primary outcome is the incomplete/ungraded state
                            (`REVIEW INCOMPLETE`), never the clean/approved
                            state, regardless of what severity.md's
                            mechanical derivation would otherwise produce
coverage == complete    → severity.md, "Decision derivation (mechanical)"
                            runs unchanged and its result is the primary
                            outcome, exactly as before this policy existed
```

An incomplete review still reports every finding it actually produced
before coverage was interrupted — this policy never discards or hides a
real finding, and a finding already backed by sufficient evidence remains
a finding regardless of coverage. It only changes the outcome *label*: an
incomplete review is never presented as safe to merge/proceed, and a
reader must never have to infer incompleteness from an absent section or
a suspiciously thin review — the label states it plainly, with its
reason(s), alongside whatever findings and validation results were
actually produced.

`REVIEW INCOMPLETE` is not a new value this policy invents for
`github-pr-review` — it is the existing outcome already defined in that
Skill's own `policies/review-output.md`, "Final decision" (not linked
from here: this shared policy is packaged standalone into every
consuming Skill's own archive and must never depend on another Skill's
directory existing alongside it — see
[`finding-rendering.md`](../templates/finding-rendering.md), "Location
source annotation" for the same packaging constraint), and already
produced by several of that Skill's own policies for their own specific
triggers (incomplete PR-scope enumeration, a required repository checkout
that fails, a required parallel-review dimension that cannot be
produced). This policy gives that existing outcome **one shared,
risk/partition-scaled definition of when it applies in general**,
consumed identically by `local-code-review`, which does not yet have an
equivalent labeled outcome of its own.

## Machine-readable model

```yaml
review_stopping_criteria:
  coverage: complete | incomplete
  depth: standard | elevated | deep   # from change-risk-signals.md
  partitioned: true | false           # from large-pr-partitioning.md
  incomplete_reasons:
    - trigger: required-pass-not-produced | partition-not-completed |
               review-target-not-established | required-validation-unavailable
      detail: <concrete, evidence-backed reason>
```

`incomplete_reasons` is present only when `coverage` is `incomplete`.

## Non-goals and ownership boundary

- **Not the GitHub enforcement/status mapping.** How `REVIEW INCOMPLETE`
  (or any other reasoning outcome) maps to a published GitHub review
  event, a machine-readable status check, or any other enforcement
  surface is owned entirely by `github-pr-review`'s own
  `policies/review-status-enforcement.md` (not linked from here — see
  "Labeling" above for why this shared policy never links into a
  Skill-specific directory) and is not restated or extended here.
- **Not a merge gate of its own.** This policy defines when the *review
  itself* is done and how that is labeled; it does not define who is
  allowed to merge, block, or override that label — that stays each
  Skill's own publication/authorization policies.
- **Defers depth and partitioning.** The `standard`/`elevated`/`deep`
  depth and the partition set are owned by
  [`change-risk-signals.md`](change-risk-signals.md) and
  [`large-pr-partitioning.md`](large-pr-partitioning.md) respectively;
  this policy only reads their already-computed results.
- **Defers each pass's own stop condition.** Whether one pass (bounded
  context expansion, an expansion ring, affected-test analysis, a
  partition) itself reached completion is decided entirely by that pass's
  own owning policy; this policy only aggregates those already-made
  determinations into one review-level coverage signal.
- **Never lowers the evidence bar.** A finding still requires exactly the
  evidence [`evidence.md`](evidence.md) and [`severity.md`](severity.md)
  already require; incomplete coverage never substitutes for missing
  evidence on any individual finding, and complete coverage never excuses
  a finding that lacks it.

## Not a second scope or evidence model

Coverage changes only the review's stated completeness and, when
incomplete, its top-level outcome label. It never changes what counts as
a finding, a finding's evidence label, its severity, or the mechanical
decision derivation `severity.md` performs once coverage is `complete`.
