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

[`rendered-inspection.md`](rendered-inspection.md) is never a required pass at
any depth: a skipped, unavailable, or inconclusive rendered inspection is a
`Validation` outcome only and never makes coverage `incomplete`.

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
   **Required material not loaded in time is the same case.** A policy,
   runbook, or template its Skill's loading section requires — a
   conditionally loaded file whose predicate fired included — must be
   loaded before the first decision it governs. Loaded before that
   decision, it is the ordinary case. Loaded only after that decision, or
   still unloaded when coverage is evaluated, the governed pass was not
   produced as required, so coverage is `incomplete`, never `complete`,
   and `detail` names the material — unless the governed decision was
   re-made after loading, which counts as loaded before it. A file counts as loaded only when its
   complete content was read: an excerpt, truncated output, or a read the
   reviewer cannot show to have been complete counts as not loaded unless
   it is resumed to a verified-complete read under "Bounded, resumable
   policy loading" below. This covers
   *known* gaps only: a self-reported load is not proof every required
   file was read, and this rule does not claim to prevent unknown skips.
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

An **unresolved relationship** — outcome `unresolved` in
[`repository-expansion.md`](repository-expansion.md), "Relationship
outcomes and unresolved relationships" — is likewise not a fifth trigger.
The closed set above is deliberately unchanged: the pass that raised it
reached its own stop condition, and the gap is disclosed by the **Context
gaps** section instead of by coverage. The rejected alternative — adding an
incomplete trigger for unresolved relationships — would turn routine
reviews of dynamic or unsupported code into `REVIEW INCOMPLETE`, which
status enforcement can treat as non-passing, and would reverse the
"insufficient evidence is a valid terminal outcome" rule that
`repository-expansion.md` and this policy establish. The trade-off is
accepted: `complete` coverage never asserts that every relationship was
resolved, and a reader learns of gaps from the Context gaps section.

An **optional** step that failed but was itself recoverable by the
reviewer, or a dimension whose absence does not change what depth
requires (for example a `standard`-depth change with no `elevated`/`deep`
sub-passes to begin with), never makes coverage `incomplete`.

## Mandatory-loading checkpoint and pre-verdict recheck

Trigger 1's loading rule is enforced at two fixed points, not left to a
late self-report. Neither adds a trigger, a field, or a state model; both
only decide *when* the existing trigger is evaluated:

1. *Before review execution.* Before step 1 of the Skill's runbook, the
   reviewer confirms that every **unconditional** mandatory file is
   actually open: each file its Skill's `SKILL.md` section 2 lists as
   always loaded, except a member that section introduces with a context
   phrase (for example "with parallel workers" or "in orchestrated/
   multi-Agent contexts"), which joins the set only when that context
   holds for this review. A file not yet open is loaded now; one that
   cannot be loaded is a trigger-1 incomplete reason whose `detail`
   names that file. The checkpoint never makes a required file optional,
   never requires a context-conditional file whose predicate has not
   fired, and never substitutes for loading it. A file `SKILL.md` section 2
   lists under "Always, by phase" is required like the rest but is checked
   at its named phase instead: confirmed open before the first candidate
   finding is formed or reconciled for the finding schema and `Fix`
   direction, and before the coverage step for the rendering and summary
   files. A file first opened after the decision it governs is not loaded
   in time, however early it is opened relative to the verdict. A phase
   may be earlier than the coverage step, never later, so the `Coverage:`
   line is still derived from files actually opened.
   Delegation does not move this checkpoint. It binds every reviewer that
   renders a verdict or contributes a dimension, delegated or not
   ([`agent-delegation.md`](agent-delegation.md), "Delegated reviewers
   inherit the policy-loading contract"); a required file a delegate did not
   confirm in full counts as not loaded here.
2. *Immediately before the Decision is derived.* Coverage is
   recomputed once over the final state — the unconditional set, the
   by-phase group, every
   context-conditional file whose context held, and every conditionally
   loaded file whose predicate fired at any point during the review —
   after any re-review, finding re-finalization, or change of the
   reviewed HEAD or delta. A coverage value reached earlier is never
   carried over to the verdict.

## Bounded, resumable policy loading

"Open in full" is met by the procedure below, so a runtime that delivers
less than it was asked for is neither missed nor a reason to restart. It
decides how required files are read, never which are required, and adds
no trigger, field, or state.

1. *Bounded groups, in sequence.* Read the required files in groups, one
   group per call, in any order. Size a group to what this runtime has
   actually delivered whole during this review, not to a fixed limit: with
   no evidence yet read one file per call, widen only after a group arrived
   whole, and narrow after any shortfall. One call over the whole set is
   not a loading method.
2. *Completeness is verified per file, independently of the read.* A
   successful call, a clean exit status, or a plausible ending does not show
   a file arrived whole. Before reading a file, obtain its extent in lines
   from a source other than that read (the runtime's file query or a
   line-count command; one small call can return the extents of many
   files). A line is newline-terminated or the final unterminated one, so
   a file without a trailing newline has one more line than `wc -l`
   reports, and the empty row some viewers number after the last newline
   is not a line. The file is loaded only when the lines received are
   contiguous from line 1 and equal that extent. When no extent can be
   obtained, it is complete only when, after at least one line was
   received, a read starting after the last line received returns nothing
   (an end-of-file probe).
3. *Resume from the verified position.* The verified position is the last
   line of the contiguous prefix received and checked. A shortfall (fewer
   lines than the extent, output marked or cut short, a read that fails
   partway) is continued with a ranged read from the next line, no longer
   than the longest span the runtime has delivered in one read, and
   narrowed after each further shortfall. Verified content is not read again, and the review
   is neither restarted nor its earlier steps repeated.
4. *Only a failed recovery is a trigger-1 reason.* Recovery has failed for
   a file when, with lines still outstanding, a single-line read from the
   verified position returns nothing, when the lines received disagree with the extent (the file
   changed or the delivery is inconsistent), or when the runtime cannot read
   from a given line and the whole-file read stays short. Then, and only
   then, the file is an incomplete reason, and `detail` names it with its
   verified position (for example `severity.md verified through line 120 of
   154`). A read that needed several attempts and ended verified is loaded,
   and is not a gap or a finding.

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

The three outcomes are exclusive and ranked `REVIEW INCOMPLETE` >
`CHANGES REQUIRED` > `REVIEW CLEAN`: `REVIEW INCOMPLETE` represents
incomplete coverage and overrides a blocking finding, which is still
reported in full; `CHANGES REQUIRED` represents a blocking finding under
complete coverage; `REVIEW CLEAN` requires complete coverage and no
blocking (P0/P1) finding. P0 = 0 and P1 = 0 alone never imply
`REVIEW CLEAN`. There is no hybrid
rendering: a success marker, `Review Clean`, `REVIEW CLEAN`, or an
approving outcome never appears in the Result or Decision of a review
whose coverage is `incomplete`, with or without a qualifier such as
"coverage incomplete, see Metadata". The Metadata `Coverage` line cannot
excuse or replace the Result, and the incomplete Result names the unmet
requirements from `incomplete_reasons`.

**Coverage invariant.** Neither definitive verdict (`REVIEW CLEAN`,
`CHANGES REQUIRED`) is valid unless coverage is `complete`, which includes
every required policy loaded in full before the decision it governs.
Coverage is derived from the files actually opened, never from memory. A
missing Coverage field, or a report that states unloaded required policies
or incomplete coverage anywhere in its text, is `incomplete` and renders
`REVIEW INCOMPLETE` in Result and Decision; a definitive verdict never
coexists with such a statement. This is an obligation on the reviewer, not a
technical guarantee.

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
consumed identically by `local-code-review`, whose report template
renders the same `REVIEW INCOMPLETE` outcome.

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

## Relationship to review execution telemetry (Issue #182)

This policy's `coverage` field is **decision-affecting**: `incomplete`
overrides a review's top-level outcome to `REVIEW INCOMPLETE` (see
"Labeling"). A separate, deliberately different concept — an
observational, machine-readable record of what a review actually
inspected and executed (files, symbols, repository-intelligence
expansions, runtime validations, partitions, per-stage timing where
available) — exists as repository-development design work under a
different name and is **purely observational**: it can never influence a
finding, a finding's severity or confidence, suppression, or this
policy's own coverage/decision derivation, in either direction. A review
can have full telemetry coverage of that other record and still be
behaviorally wrong, and this policy's `coverage` value is computed
exactly as described above whether or not that record exists for the
run. Do not copy, extend, or reference this policy's coverage model from
that other record, and do not read that record's completeness as a
substitute for this policy's own `coverage` computation.
