# Shared Policy — Large-PR Partitioning

Applies identically to `local-code-review` and `github-pr-review`. It
defines when a change is large enough that a single review pass would
produce shallow or truncated output, the **deterministic procedure** for
partitioning such a change into coherent **review units**, how each unit
is reviewed, and how the units' results **aggregate and de-duplicate**
into the one final review.

This is the large-change counterpart to the always-on passes in
[`change-risk-signals.md`](change-risk-signals.md) and
[`repository-expansion.md`](repository-expansion.md): those classify risk
and bound how far a review looks *beyond* the diff; this policy bounds how
a review is organized *across* an unusually large diff so that size alone
never degrades review depth. It introduces **no second scope model and no
second evidence standard**: every partition is reviewed against
[`review-scope.md`](review-scope.md) and [`evidence.md`](evidence.md)
exactly as an unpartitioned change would be, findings keep the same
`confirmed defect` / `credible engineering risk` / `optional improvement`
labels, and [`severity.md`](severity.md) still derives the one final
decision mechanically, once, over the combined finding set.

## Relationship to parallel-review.md

[`parallel-review.md`](parallel-review.md) already defines how one review
may split across independent **workers by analysis dimension** (scope,
architecture, correctness, tests, existing-review reconciliation) — every
worker still sees the *same, complete* diff. This policy instead splits
the **diff itself** into coherent content partitions when it is too large
for one pass to cover well. The two are independent axes and compose:
each partition this policy produces may itself be reviewed sequentially or
further split by dimension per `parallel-review.md` — either is a valid,
complete implementation. This policy owns only *what the partitions are*
and *how their results combine*; it never owns execution-infrastructure
specifics (spawning mechanics, concurrency limits, runtime capability
detection) — those stay `parallel-review.md`'s, and sequential,
one-partition-at-a-time review is always a valid, complete implementation
of this policy on its own.

## Activation

Unlike [`change-risk-signals.md`](change-risk-signals.md) and
[`repository-expansion.md`](repository-expansion.md), this pass is
**conditional**, not always-active: it activates only when the change's
diff-size measurement reaches the partitioning threshold below. A change
that stays under the threshold is reviewed as a single unit exactly as it
always has been — that is the normal, complete outcome, and this policy
contributes nothing further to it.

## Partitioning threshold

Authoritative, policy-level, and **not** left to per-review judgement.
Measured the same way [`change-risk-signals.md`](change-risk-signals.md),
"Diff-size thresholds" measures diff size: changed lines (added plus
deleted) and changed files across the in-scope change, **excluding** files
classified non-reviewable per
[`file-reviewability.md`](file-reviewability.md).

| Boundary | Partitioning activates when |
| --- | --- |
| Partitioning threshold | changed lines **≥ 1200**, or changed files **≥ 60** |

Boundary semantics are **`≥` (at or above the number)**, matching
`change-risk-signals.md`. This threshold is exactly double
`change-risk-signals.md`'s `deep` threshold (`≥ 600` lines / `≥ 30`
files) by design: a change already large enough to be `deep` by itself is
not automatically large enough to need partitioning — partitioning exists
for the tier of change that exceeds even that.

## Partition construction (deterministic)

Given an activated change, build partitions by this exact, reproducible
ordering over the in-scope changed files:

1. **Seed by directory.** Assign every in-scope changed file to a seed
   cluster keyed by its immediate parent directory. Files in the same
   directory start in the same cluster; a file in a directory with no
   other changed file starts as a singleton cluster.
2. **Coherence merge.** Merge any two clusters that
   [`review-scope.md`](review-scope.md), "Related changes as one unit"
   already requires reviewing together — an API contract with its
   DTO/schema and controller, a producer with its consumer, a persistence
   model with its repository and migration, an implementation with its
   corresponding tests, or any other evidenced cross-file relationship
   that one of this change's own facts establishes. This merge is
   evidence-based, not name- or directory-based, exactly as
   [`review-scope.md`](review-scope.md), "Technology neutrality" already
   requires elsewhere: a shared symbol, call site, schema reference, or
   producer/consumer pairing is evidence; directory proximity alone is
   not, and directory distance alone never blocks a merge the evidence
   supports.
3. **Per-partition size cap.** No partition may exceed
   `change-risk-signals.md`'s own `deep` diff-size threshold measured on
   itself: changed lines **< 600** and changed files **< 30**. Split an
   oversized cluster further by its changed files' sub-directory
   structure, repeating the directory-seed step one level deeper, as long
   as no step-2 coherence link is broken by the split.
4. **Size-floor merge.** A cluster left with very few changed lines after
   steps 1–3 merges into the coherence-adjacent partition it merged toward
   in step 2, or otherwise into the directory-adjacent partition with the
   nearest parent path, so partitioning does not manufacture many
   trivially small partitions out of an otherwise ordinary change.
5. **Oversized-partition flag.** A coherence-linked cluster that still
   exceeds the step-3 cap after step 3's split attempt (a single
   changed file or an inseparable coherent group that alone is larger
   than the cap) is kept whole — coherence is never broken merely to
   satisfy the size cap — and is flagged `capped: true` in this policy's
   machine-readable model and reporting. See "Limits" below.

The same deterministic ordering applied to the same diff always yields the
same partitions; there is no reviewer discretion over partition boundaries
beyond applying the coherence evidence in step 2.

## Per-partition review

Each partition is reviewed against the complete, unchanged shared policy
stack — [`review-scope.md`](review-scope.md),
[`evidence.md`](evidence.md), [`severity.md`](severity.md), and the rest
— as if it were the review's target, with one exception: a partition's
investigation is not barred from the evidence a coherence merge already
established connects it to another partition (the two were merged, or
left distinct, by step 2's evidence, not arbitrarily). Blast radius still
scopes per [`evidence.md`](evidence.md); partitioning narrows *how the
diff is organized for review*, never *what evidence a finding may rest
on*.

- **Change-risk depth and repository expansion are computed once, for the
  whole change**, not separately per partition — both
  [`change-risk-signals.md`](change-risk-signals.md) and
  [`repository-expansion.md`](repository-expansion.md) classify "the
  change," and partitioning does not redefine what "the change" means for
  those policies. Each partition's own review still detects and resolves
  whichever expansion triggers actually fall inside it, bounded by the
  one ring ceiling the whole change's depth already set.
- **Existing behavior ownership**, root-cause reasoning, affected-test
  analysis, and every other review-scope sub-pass apply per partition
  exactly as they would to an unpartitioned review of that same content —
  this policy adds no partition-local exception to any of them.

## Aggregation and cross-partition de-duplication

Partition results never stand alone. They flow through one centralized
aggregation stage before anything is finalized, mirroring
[`parallel-review.md`](parallel-review.md), "Centralized aggregation":

```text
per-partition findings → normalize → reconcile cross-partition duplicates
  → apply root-cause-consolidation.md across partition boundaries
  → apply severity.md (one severity per finding)
  → derive one decision (severity.md, "Decision derivation")
```

- **Cross-partition duplicate.** The same underlying defect surfaced from
  two partitions — most often because a coherence-linked relationship
  still produced evidence on both sides of a partition boundary — is
  reported **once**, attributed to the partition holding the defect's
  root cause/canonical owner, not once per partition that observed it.
- **Cross-partition consolidation.** When a shared defect-bearing element
  reaches manifestation sites in two or more different partitions, it
  still resolves to the single authoritative consolidated finding per
  [`root-cause-consolidation.md`](root-cause-consolidation.md), "The
  authoritative consolidated finding" — partitioning the diff for review
  never fragments a root-cause finding along partition boundaries, and
  the required affected-locations list names every site regardless of
  which partition it fell in.
- **Partition completion order never affects the result.** Findings,
  severities, and the decision are the same regardless of the order
  partitions were reviewed in, exactly as
  [`parallel-review.md`](parallel-review.md) already requires of worker
  completion order.
- **A partition that could not be completed** (review failure, timeout, or
  an equivalent gap) is reported as missing coverage, never silently
  absorbed into a clean result — the same failure-handling posture
  [`parallel-review.md`](parallel-review.md) already applies to a missing
  required dimension.

## Determinism

Given the same diff and the same repository state, the same partitions are
built, in the same composition, and partition completion order never
changes the final finding set, severities, or decision. Reviewer judgement
applies only to evaluating the coherence evidence within step 2 of
"Partition construction," never to inventing a different partitioning
scheme.

## Reporting

Whether partitioning activated, and — when it did — the partitions built
and whether aggregation found any cross-partition duplicate or
consolidation, are reported alongside the change-risk classification and
repository-expansion decisions in the review's subordinate metadata (see
[`../templates/review-summary.md`](../templates/review-summary.md),
"Machine metadata is subordinate"). Unlike that pair, this field is
**conditional**, not always-on: it is rendered only when this change
activated partitioning; a change that stayed under the threshold carries
no partitioning line at all, the same way an inactive requirement-coverage
pass renders nothing. It is never part of the primary human-facing body,
never a finding, and never a way of implying a verdict — the human-facing
review stays one unified review of one change regardless of how many
partitions built it.

## Machine-readable model

```yaml
large_pr_partitioning:
  activated: true | false
  threshold: { changed_lines: 1200, changed_files: 60 }
  partitions:
    - id: P1
      files: [<path>, ...]
      changed_lines: <n>
      changed_files: <n>
      coherence_merges: [<brief evidenced reason>, ...]
      capped: true | false
  cross_partition_dedup:
    - owning_partition: P<n>
      also_surfaced_in: [P<n>, ...]
```

`partitions` and `cross_partition_dedup` are present only when `activated`
is `true`.

## Limits

This policy reduces, but does not eliminate, the risk a single pass over
an enormous diff produces shallow output — stating that honestly rather
than implying unbounded coverage:

- **An inseparable oversized partition stays oversized.** Step 5 of
  "Partition construction" never breaks a coherence-evidenced cluster to
  satisfy the size cap. A single enormous, internally coherent change
  (for example one very large generated-but-reviewable file, or one
  migration touched by many dependent call sites that all genuinely
  belong together) remains one large partition, flagged `capped: true`
  rather than silently reviewed as if it were ordinarily sized.
- **Coherence merging is bounded, not exhaustive.** Step 2 merges clusters
  the current change's own evidence connects; like
  [`repository-expansion.md`](repository-expansion.md)'s ring procedure,
  it is not a repository-wide relationship discovery pass and will not
  surface every conceivable cross-partition relationship in an
  arbitrarily tangled change. An unresolved, only-plausible cross-partition
  link fails open to separate findings exactly as
  [`root-cause-consolidation.md`](root-cause-consolidation.md), "Fail open
  toward separate findings" already requires — this policy never guesses
  a shared cause into existence to produce a tidier partition boundary.
- **Assumes a stable diff for the duration of the review.** Determinism
  is stated given one fixed diff and repository state; reconciling a
  partitioned review against a diff that changed mid-review is owned by
  each Skill's own re-review/staleness handling, not restated here.

## Non-goals and ownership boundary

- **Not a merge gate.** Partitioning, the partition count, and any
  `capped` flag never block a merge on their own and are never themselves
  a finding.
- **Never produces a shallower review.** The point of this policy is the
  opposite of its problem statement: an activated change still receives
  full-depth review of every partition: nothing is skipped, sampled, or
  truncated because the change was large.
- **No PR splitting.** This policy partitions a change for review
  purposes only; it never splits a pull request, never asks the author to
  split one, and never changes what is merged.
- **Not a parallel-execution specification.** How (or whether) partitions
  run concurrently is entirely [`parallel-review.md`](parallel-review.md)'s
  concern; this policy's contract holds unchanged whether partitions are
  reviewed one at a time or concurrently.
- **Defers change-risk and expansion classification.** This policy
  consumes, but never redefines, the diff-size measurement, the
  `standard`/`elevated`/`deep` depth, and the expansion-ring ceiling owned
  by [`change-risk-signals.md`](change-risk-signals.md) and
  [`repository-expansion.md`](repository-expansion.md).
- **Defers consolidation semantics.** The evidence bar, the
  consolidate-vs-keep-separate contrast, and the affected-locations
  requirement on a cross-partition consolidated finding are owned by
  [`root-cause-consolidation.md`](root-cause-consolidation.md) and are not
  restated here.

## Not a second scope or evidence model

Everything a finding needs — blast-radius scope, evidence, labels,
severity, and the mechanical decision — is unchanged by this policy. It
only changes how a large change's review is organized and how the
resulting findings are combined; it never lowers the evidence bar a
finding must clear and never substitutes for the evidence a finding must
carry.
