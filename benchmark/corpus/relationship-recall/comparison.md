# Search-Only vs. Relationship-Enriched Comparison: Results and Decision

Results for GitHub Issue
[#605](https://github.com/amirbena/code-review-skill/issues/605). The protocol
and decision rule were committed first, in
[`comparison-protocol.md`](comparison-protocol.md) (`72b05fd`); the machine
record is [`comparison-observations.json`](comparison-observations.json).

## Decision

**A local deterministic relationship index is not justified by this evidence.**
The decision rule fails condition 1 (quality gain); the other four conditions
hold. This feeds [#606](https://github.com/amirbena/code-review-skill/issues/606),
which closes as not justified on this record.

The enriched arm was an **ideal provider**: perfect, free, never stale. It
still did not clear the quality bar, so a real index, which can only match that
recall and adds build cost, would not either on this corpus.

**No #129 §11 deferral is reopened.** The deferred real index or static-analysis
backend, the runtime graph, and the `influential_relationships` field all stay
deferred.

## What was run

Both arms ran the Skill packaged from this checkout (1.63.0, carrying #601 and
#604), 13 cases (the [class map](README.md#relationship-classes) plus the second
consumer positive), 2 repetitions per arm, one execution per case-repetition,
52 reviews in all. Arm A declared no capability. Arm B declared
`relationship-query` and supplied the ground-truth answers in
[`relationship-answers.json`](relationship-answers.json), bound to each
workspace's snapshot. Scoring is the existing runner, matcher and metrics.
Model and effort were the CLI defaults, not pinned.

## Benchmark result

| Measure | A: search-only | B: enriched |
|---|---|---|
| Counted reviews | 26 | 24 (2 errored) |
| Gain (B − A), case-repetitions | | **2.0**, from 2 cases (needs ≥ 3) |
| False positives (total) | 22 | 15 |
| Inflation control | | 0 |
| Median seconds per review | 83.4 | 109.3 (1.31×) |
| Mean tokens per review | 0.98 M | 1.14 M (1.17×) |
| Analogue consistency across reps | 0.67 | 0.33 |
| Context gaps rendered on unresolvable cases | 1 of 8 | 3 of 7 |

| Rule condition | Result |
|---|---|
| 1 Quality gain ≥ 3 case-reps, ≥ 2 cases | **fail** (2.0) |
| 2 No class regression | pass |
| 3 No inflation | pass |
| 4 Cost ≤ 1.5× | pass |
| 5 Valid arms (≤ 25% excluded) | pass (B 7.7%) |

The two cases that gained were the affected-test positive (B correct in both
repetitions, A in one) and a clean test-split control (B correct once, A never).
Per-case, per-repetition outcomes are in the observations file.

## Reading the result

- **Both arms mostly miss the same positives.** Consumer, interface and
  analogue positives were missed or wrong in nearly every run of both arms,
  with or without the answers. Where the reviewer reported the right defect,
  the matcher often scored it as missed plus a false positive because the
  finding was anchored at a different location than the fixture expects. That
  is a scoring-strictness effect, not a relationship-discovery effect, and it
  dominates the comparison.
- **One fixture is contaminated.** The interface positive's base lacks
  `errors.ts`, so both arms reported a non-existent-import P0 instead of, or
  beside, the expected finding. This is the same defect the
  [baseline](baseline.md) found and fixed in a sibling fixture.
- **The fixtures are small.** Each repository is two to six files, so search-only
  can see every relationship by reading it. That limits what enrichment can add.
- **Unresolved visibility improved, but is not a quality gain.** Context gaps
  rendered more often with the answers present. The rule scores outcome, not
  disclosure, so this does not count toward the decision.
- **Noise.** Two repetitions of 13 cases is a targeted comparison, not a
  statistical sample. Single-case swings, such as the control cases that flipped
  between repetitions in both arms, are within run-to-run variation.

## What would change the decision

A rerun could reach a different answer only if all of these hold:

1. Fixtures where the relationship is **not** recoverable by reading the whole
   repository, for example a large repository or a cross-partition change, so
   search-only cannot see it.
2. The interface positive fixed (add `errors.ts` to its base) and the matcher
   tolerant of the same defect at an equivalent location, as the affected-test
   positive already is through `alternatives`.
3. Enough repetitions per case that a gain of 3 or more case-repetitions exceeds
   run-to-run variation.
4. A real provider, not the ideal one, that still reaches the ideal arm's
   recall at the cost bound. That is the #606 spike's question, and it starts
   only if 1–3 show a gain.

## Failed and excluded reviews

Two arm-B repetition-1 reviews errored (`reviewer-adapter-raised`):
`relrecall-interface-optional-member-implementers-compatible-control` and
`relrecall-interface-config-registered-implementers-unresolvable`. They are
excluded from rates, not retried, and not classified as correct or wrong. No
arm-A review failed. Every counted review invoked the Skill under test.

## Usage telemetry

Reported by Claude Code in each result event; it is telemetry, not a billing
record. `total_cost_usd` is not asserted to be a charge or a dollar-denominated
quota. Totals over all 52 reviews: `total_cost_usd` telemetry 34.80, 984 input,
358,579 output, 47,892,303 cache-read and 5,169,444 cache-creation tokens, 6,361
review-seconds summed (the four jobs ran in parallel). Per run:

| Run | Reviews | Failed | `total_cost_usd` telemetry | Output tokens | Cache read | Cache creation | Seconds summed |
|---|---|---|---|---|---|---|---|
| A rep 1 | 13 | 0 | 8.84 | 91,484 | 13,713,186 | 1,295,619 | 1,357 |
| A rep 2 | 13 | 0 | 7.82 | 71,587 | 9,281,407 | 1,072,751 | 1,210 |
| B rep 1 | 13 | 2 | 8.14 | 92,614 | 11,205,472 | 1,243,130 | 1,814 |
| B rep 2 | 13 | 0 | 10.00 | 102,894 | 13,692,238 | 1,557,944 | 1,981 |

## Reproducing

The inputs are the harness command in the observations file, the packaged
1.63.0 Skill at `5e8533d`, the answers file (hash recorded), and the corpus
fixtures. Model output is not deterministic, so a rerun is a new observation,
not a replay. The results use the runner's own `run` and `metrics` shape;
`benchmark-result/v1` is not used because it seals scheduled lane runs over the
full comprehensive corpus, as the [baseline](baseline.md) also notes.
