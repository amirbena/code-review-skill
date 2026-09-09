# Benchmark Missed & Incorrect Finding Metrics

Repository-development contract for GitHub Issue
[#55](https://github.com/amirbena/code-review-skill/issues/55). It defines
**how a benchmark run's produced findings are turned into missed-finding
(false-negative) and incorrect-finding (false-positive) counts** — per
case and in aggregate — the produced↔expected set-pairing resolution the
counts are built on, how the fixture format's variance constructs and
`findings_completeness` change the accounting, and how the counts are
emitted alongside the regression report's run-to-run deltas. It builds on
the match relation ([`match-criteria.md`](match-criteria.md), #54), the
per-case result shape ([`runner-contract.md`](runner-contract.md) §6,
#52), the fixture format ([`fixture-format.md`](fixture-format.md) §8–§9,
#50), and the run-to-run report ([`regression-report.md`](regression-report.md),
#53). Parent capability:
[#41](https://github.com/amirbena/code-review-skill/issues/41).

Like [`match-criteria.md`](match-criteria.md) and the rest of
[`./`](README.md), this is a **repository-development doc: not packaged
into either Skill archive**, and no packaged Skill resource depends on it.
It reuses the shared finding shape, the P0/P1/P2 severity vocabulary, and
the `MATCH` / `NEAR_MISS` / `NO_MATCH` pairwise result of
[`match-criteria.md`](match-criteria.md); it does **not** redefine the
match relation, re-derive a location model, or define a parallel review
model.

## Canonical invariant

> **A benchmark run's quality, on this axis, is two counts per case — how many expected findings the reviewer missed (false negatives) and how many findings it produced that correspond to no expected finding (false positives) — computed by first resolving a one-to-one pairing between produced findings and expected entries using only the #54 `MATCH` relation, then counting what is left unpaired on each side, gated by the fixture's `match` flags and `findings_completeness`. The counts derive entirely from the documented match criteria and the fixture's structured fields; no score, ratio, severity judgement, or duplicate-clustering enters them.**

Every rule below is an elaboration of that sentence. Three neighbouring
concerns are deliberately *out* of it and owned elsewhere (§9): a blended
score / precision / recall / pass rate or a merge gate (out of scope for
[#41](https://github.com/amirbena/code-review-skill/issues/41) by its
Non-Goals), severity accuracy over the paired set
([#56](https://github.com/amirbena/code-review-skill/issues/56)), and
duplicate / same-root-cause noise
([#57](https://github.com/amirbena/code-review-skill/issues/57)).

## 1. Terminology and ownership

- **Expected entry** — one entry under `expected.findings`
  ([`fixture-format.md`](fixture-format.md) §8): a single spec, a spec
  with `alternatives`, or an `any_of` group. Each carries a `key` unique
  across the case and a `match` flag (`required` — default — or
  `optional`).
- **Produced finding** — one reviewer result recorded verbatim by the
  runner ([`runner-contract.md`](runner-contract.md) §6), addressed by its
  index in the case's ordered `produced_findings` list.
- **Pairwise result** — `MATCH` / `NEAR_MISS` / `NO_MATCH` for one
  produced finding against one expected spec ([`match-criteria.md`](match-criteria.md)
  §5). **Only `MATCH` pairs** for accounting here; a `NEAR_MISS` never
  satisfies an expected entry and never absolves a produced finding (§2,
  §3).
- **Entry outcome** — the best pairwise result for a whole expected entry
  once its `alternatives` / `any_of` members are resolved
  ([`match-criteria.md`](match-criteria.md) §6).
- **Pairing** — the one-to-one assignment (§2) between produced findings
  and expected entries where every assigned pair is a `MATCH`.
- **False negative (missed finding)** — a `required` expected entry left
  unpaired after §2 (§3).
- **False positive (incorrect finding)** — a produced finding left
  unpaired after §2 that also corresponds to no acceptable spec, counted
  only under `findings_completeness: exhaustive` (§4).
- **Near-miss** — an unpaired `required` expected entry whose best entry
  outcome is `NEAR_MISS` (the reviewer produced a finding at the right
  location for a related-but-not-same defect, or the right defect one
  location off). Reported as its own count for human context (§5); it is a
  strict **subset of the false negatives**, never a separate penalty and
  never subtracted from them.

This document does **not** define: the match relation itself (#54); the
fixture format or the corpus (#50 / #51); how produced findings are
captured (#52); the run-to-run diff (#53); severity-accuracy measurement
(#56); duplicate-noise measurement (#57); or any single blended quality
score.

## 2. The produced↔expected pairing

The counts are meaningful only once each produced finding is credited to
**at most one** expected entry and each expected entry consumes **at most
one** produced finding — [`match-criteria.md`](match-criteria.md) §5
fixed the pairwise relation and explicitly deferred this set-level
resolution here.

The pairing is computed by a **deterministic greedy pass in fixture
document order**:

1. Walk `expected.findings` in the order the fixture author wrote them
   (`any_of` groups and `optional` entries included).
2. For the current entry, evaluate its entry outcome
   ([`match-criteria.md`](match-criteria.md) §6) against the produced
   findings **not yet paired**. If that outcome is `MATCH`, pair the entry
   with the achieving produced finding — [`match-criteria.md`](match-criteria.md)
   §7's tie-break (lowest index in the runner's ordered
   `produced_findings`) picks the finding when several tie — and mark that
   finding consumed.
3. If the outcome against the unpaired findings is not `MATCH`, the entry
   stays unpaired; do **not** steal a finding already paired to an earlier
   entry.

Document order is the priority rule: when two entries could each be
satisfied only by the *same* single produced finding, the earlier entry
wins it and the later entry is a miss. This is deterministic and
independent of machine, run, and iteration order, matching
[`match-criteria.md`](match-criteria.md) §7.

`optional` entries take part in the pairing exactly like `required` ones
— pairing an `optional` entry consumes its produced finding so that
finding is not later counted as a false positive (§4). Optionality only
changes the miss side (§3).

### 2.1 `any_of` groups in the pairing

An `any_of` group is satisfied by **exactly one** member `MATCH`
([`fixture-format.md`](fixture-format.md) §8.4). In the pairing the group
is one entry: it consumes the single produced finding that achieves the
best member `MATCH` (recording which member, per
[`match-criteria.md`](match-criteria.md) §6), and nothing more.

A second produced finding that would `MATCH` a *different* member of the
same already-satisfied group is **absorbed**: it corresponds to an
acceptable spec in the fixture's union
([`fixture-format.md`](fixture-format.md) §9), so it is **not** a false
positive, and it does not satisfy a second entry, so it does not reduce
the false-negative count. It is recorded as an informational
`absorbed_extra_match` on the case (its only accounting effect is here);
turning duplicate corresponding findings into a noise measure is
[#57](https://github.com/amirbena/code-review-skill/issues/57).

## 3. False negatives (missed findings)

After the §2 pairing, for each case:

- **`required` entry, unpaired → one false negative.** The reviewer did
  not produce a `MATCH` for a finding a correct review must contain.
- **`required` entry, paired → not a false negative**, regardless of the
  produced finding's severity (that is [#56](https://github.com/amirbena/code-review-skill/issues/56)).
- **`optional` entry, unpaired → not a false negative**
  ([`fixture-format.md`](fixture-format.md) §9 construct 3: "not reporting
  it is not a miss").
- **`any_of` group with `match: required`, no member paired → one false
  negative** (the whole group is one missed finding, not one per member).
  With `match: optional`, an unsatisfied group is not a false negative.

`alternatives` never change this: a `required` entry with `alternatives`
is paired when the produced finding `MATCH`es the primary spec **or** any
alternative ([`match-criteria.md`](match-criteria.md) §6), and is a single
false negative when none is `MATCH`ed.

The per-case false-negative count is the number of unpaired `required`
entries (counting each `any_of` group once).

## 4. False positives (incorrect findings)

After the §2 pairing, a produced finding that was **not** consumed by any
entry is examined once more against **every acceptable spec in the
fixture's union** — every entry's primary spec and `alternatives`, and
every `any_of` member ([`fixture-format.md`](fixture-format.md) §9) —
using [`match-criteria.md`](match-criteria.md) §5:

- **Best result `MATCH`** — an absorbed extra corresponding finding (§2.1).
  **Not a false positive.**
- **Best result `NEAR_MISS`** — the reviewer is imprecisely describing a
  real expected defect. **Not a false positive.** Counting it as a false
  positive *and* letting the expected entry it is close to count as a
  false negative would double-penalize one imperfect report; the contract
  deliberately does not. The nuance is surfaced once, on the expected
  side, as the entry's `near_miss` (§5).
- **Best result `NO_MATCH` against the whole union** — an **unexpected
  finding** ([`fixture-format.md`](fixture-format.md) §9).

An unexpected finding is a **false positive only when
`findings_completeness` is `exhaustive`** (the default). Under
`findings_completeness: at-least` — for inherently noisy real-`repo_ref`
cases — unexpected findings are tolerated by the fixture format, so the
per-case false-positive count is **0 by contract** and the tolerated
unexpected findings are reported as an informational
`tolerated_unexpected` count instead.

The per-case false-positive count is therefore: the number of
union-`NO_MATCH` unconsumed produced findings when the case is
`exhaustive`, and `0` when it is `at-least`.

A case whose execution `status` is `error`
([`runner-contract.md`](runner-contract.md) §6) produced nothing: its
false-positive count is `0` and its false-negative count is the number of
`required` entries (every one is missed). The case is flagged `errored`
so a reader does not mistake the maximal miss count for a review that ran
and performed badly.

## 5. Per-case and aggregate output

For every case the metric record carries:

| Field | Meaning |
|---|---|
| `id` | Case id ([`fixture-format.md`](fixture-format.md) §5). |
| `status` | Derived from the runner's per-case result (§4): a runner `executed` passes through as `executed`; a runner `error` (or a missing per-case result) is flagged `errored`. |
| `findings_completeness` | `exhaustive` / `at-least`, echoed — it changes how `false_positives` is read (§4). |
| `false_negatives` | Count — unpaired `required` entries (§3). |
| `false_positives` | Count — §4. |
| `missed_keys` | The `key`s of the unpaired `required` entries, in fixture order — explainability, not a second metric. |
| `incorrect_indices` | The `produced_findings` indices counted as false positives, ascending. |
| `near_misses` | Count of unpaired `required` entries whose best entry outcome is `NEAR_MISS` — a strict subset of `false_negatives`, reported so a reader sees "close" separately. Never changes `false_negatives` or `false_positives`. |
| `absorbed_extra_match` | Count — §2.1. Informational. |
| `tolerated_unexpected` | Count — §4, `at-least` cases only. Informational. |

The aggregate record, computed only by summing the per-case counts over
**all** cases in the run:

| Field | Meaning |
|---|---|
| `total_false_negatives` | Σ `false_negatives`. |
| `total_false_positives` | Σ `false_positives`. |
| `cases_with_false_negatives` | How many cases have `false_negatives > 0`. |
| `cases_with_false_positives` | How many cases have `false_positives > 0`. |
| `total_near_misses` | Σ `near_misses`. |
| `errored_cases` | How many cases have `status == errored`. |

No aggregate here is weighted, normalized, or turned into a rate: there is
no precision, no recall, no pass percentage, no single number. Those are
out of scope for [#41](https://github.com/amirbena/code-review-skill/issues/41)
by its Non-Goals. A ratio can be derived by a reader from these counts;
this contract does not bless one.

## 6. Rendering alongside the regression report

[`regression-report.md`](regression-report.md) §11 anticipated this: the
run-to-run diff "gains an *optional* extra section keyed off #41's match
verdicts; the run-to-run diff defined here remains valid on its own."
This contract defines that section.

- When the corpus fixtures' `expected` blocks are available beside a
  candidate run, the benchmark report gains a **`quality_metrics`**
  section holding the §5 per-case records and aggregate for the candidate
  run.
- When a **baseline** run is also being compared
  ([`regression-report.md`](regression-report.md) §3), the section renders
  the metrics **alongside the per-case deltas**: for each case `id`
  present in both runs, the baseline `false_negatives` / `false_positives`,
  the candidate values, and their differences (`Δ = candidate −
  baseline`); and the same three-column shape for the aggregate. Cases are
  ordered by `id`, exactly as the rest of the report
  ([`regression-report.md`](regression-report.md) §7).
- A case `id` in only one of the two runs has no per-case Δ row (there is
  nothing to difference); the baseline-vs-candidate section lists such ids
  in `added_case_ids` / `removed_case_ids`, mirroring the run-to-run
  report's own added/removed handling
  ([`regression-report.md`](regression-report.md) §3). The aggregate
  three-column row is still a whole-run count on each side per §5, so an
  added or removed case is reflected in the aggregate Δ even though it has
  no per-case row.
- The section is **computed independently** of the run-to-run diff and
  **never changes** `has_regressions` or the report's process exit status
  ([`regression-report.md`](regression-report.md) §6, §9). A rising
  `false_negatives` Δ is a quality signal a human or a separate gate acts
  on; wiring it to a gate is out of scope here and on
  [#40](https://github.com/amirbena/code-review-skill/issues/40).
- The section obeys the report's determinism rules
  ([`regression-report.md`](regression-report.md) §7): byte-identical for
  identical inputs, no wall-clock or path noise, empty-but-well-formed
  when every count is zero.
- The `corpus_id` guard still applies: metrics comparing a baseline and a
  candidate that ran against different corpora are not computed
  ([`regression-report.md`](regression-report.md) §3) — the remedy is a
  baseline refresh, not a cross-corpus metric.

## 7. Determinism and two-reader consistency

- **Fixed computation order.** §2 pairing (fixture document order) → §3
  false negatives → §4 false positives → §5 counts. No step is reordered
  and no step depends on a later step's result.
- **Only `MATCH` counts.** A `NEAR_MISS` never satisfies an entry (§3) and
  never makes a produced finding a false positive (§4). The only
  tolerances in the whole computation are the ones
  [`match-criteria.md`](match-criteria.md) already fixed (the ± 3-line
  proximity window and the two claim-overlap thresholds); this contract
  adds none.
- **No scores.** No weighting, no rate, no blended number, no verdict that
  changes between runs.
- **Ties resolve deterministically** via
  [`match-criteria.md`](match-criteria.md) §7 (lowest produced index; then
  primary spec, then `alternatives` / `any_of` members in document order),
  and expected entries are consumed in fixture document order (§2).
- **Two readers, same counts.** The §8 worked examples are the
  conformance bar: two people applying §2–§5 to them must reach the same
  `false_negatives`, `false_positives`, and `near_misses` for every case.

## 8. Worked examples

All are encoded verbatim as data-driven cases in
[`../../tests/unit/test_benchmark_metrics.py`](../../tests/unit/test_benchmark_metrics.py);
two readers applying §2–§5 must reach the count columns for every row.
Each case is `findings_completeness: exhaustive` unless the row says
otherwise.

| # | Expected entries | Produced findings | Pairing (§2) | FN | FP | Near | Note |
|---|---|---|---|---|---|---|---|
| 1 | `r1` required, `r2` required | one `MATCH`es `r1`, one `MATCH`es `r2` | `r1`↔0, `r2`↔1 | 0 | 0 | 0 | Perfect review. |
| 2 | `r1` required, `r2` required | one `MATCH`es `r1` only | `r1`↔0 | 1 | 0 | 0 | `r2` unpaired → one false negative. |
| 3 | `r1` required | one `MATCH`es `r1`, one `NO_MATCH` against the whole union | `r1`↔0 | 0 | 1 | 0 | The second produced finding is an unexpected finding → false positive (`exhaustive`). |
| 4 | `r1` required | one `NEAR_MISS` against `r1` (right location, related-but-not-same defect) | — (no `MATCH`) | 1 | 0 | 1 | `r1` is a false negative **and** a near-miss; the produced finding is **not** a false positive (§4). |
| 5 | `opt` **optional** | nothing produced | — | 0 | 0 | 0 | Unsatisfied `optional` entry is not a miss. |
| 6 | `opt` **optional** | one `MATCH`es `opt` | `opt`↔0 | 0 | 0 | 0 | Pairing consumes the finding, so it is not a false positive. |
| 7 | `grp` required `any_of` {`m1`, `m2`} | one `MATCH`es `m2`, one `MATCH`es `m1` | `grp`↔0 (via `m2`) | 0 | 0 | 0 | Group satisfied once; the second finding is `absorbed_extra_match`, not a false positive and not a second satisfied entry. |
| 8 | `r1` required | one `NO_MATCH` unexpected finding; case is `findings_completeness: at-least` | — | 1 | 0 | 0 | `at-least` tolerates the unexpected finding (`tolerated_unexpected = 1`); `r1` still a false negative. |
| 9 | `r1` required, `r2` required | `status: error` (reviewer adapter raised) | — | 2 | 0 | 0 | Every `required` entry missed; case flagged `errored`; no false positives. |

**Row 4 is the anti-double-count rule.** One imperfect produced finding
that is `NEAR_MISS` against a real expected entry costs exactly one false
negative (on the expected side) and zero false positives (on the produced
side), and is surfaced as one near-miss so a reader sees the reviewer was
close.

## 9. Explicitly out of scope

| Not defined here | Owner |
|---|---|
| The produced-vs-expected `MATCH` / `NEAR_MISS` / `NO_MATCH` relation, its axes and tolerances | [#54](https://github.com/amirbena/code-review-skill/issues/54) — [`match-criteria.md`](match-criteria.md) |
| Severity accuracy over the paired set (over- vs under-severity, exact-severity rate) | [#56](https://github.com/amirbena/code-review-skill/issues/56) |
| Duplicate / same-root-cause clustering and the noise metric | [#57](https://github.com/amirbena/code-review-skill/issues/57) |
| A single blended quality score, precision / recall / pass rate, or a merge gate | out of scope for [#41](https://github.com/amirbena/code-review-skill/issues/41) by its Non-Goals |
| The run-to-run diff itself (`dropped` / `gained` / `retained`, regression vs improvement) | [#53](https://github.com/amirbena/code-review-skill/issues/53) — [`regression-report.md`](regression-report.md) |
| The fixture format, the variance constructs, and the corpus | [#50](https://github.com/amirbena/code-review-skill/issues/50) / [#51](https://github.com/amirbena/code-review-skill/issues/51) |
| Capturing produced findings; the per-case result shape this metric consumes | [#52](https://github.com/amirbena/code-review-skill/issues/52) |
| The cross-revision stable finding identity mechanism (produced-vs-earlier-produced) | [#42](https://github.com/amirbena/code-review-skill/issues/42) / [#59](https://github.com/amirbena/code-review-skill/issues/59) |
| CI wiring / a merge gate acting on the metric deltas | [#40](https://github.com/amirbena/code-review-skill/issues/40) |
| The P0/P1/P2 definitions | [`../../shared/policies/severity.md`](../../shared/policies/severity.md) |
| The finding field shape | [`../../shared/templates/finding.md`](../../shared/templates/finding.md) |

## Status and canonical home

**This document is the authoritative contract** for benchmark
missed-finding / incorrect-finding accounting until a later issue installs
an equivalent runnable component in a canonical home. At that point this
document becomes the design record: it MUST link to that component and
MUST NOT keep evolving the accounting independently — exactly as
[`match-criteria.md`](match-criteria.md), "Status and canonical home,"
and [`regression-report.md`](regression-report.md), "Status and canonical
home," describe for their own eventual installation.

The test-only reference metric
[`../../tests/reference/benchmark_metrics.py`](../../tests/reference/benchmark_metrics.py)
mirrors this document for regression coverage (executed by
[`../../tests/unit/test_benchmark_metrics.py`](../../tests/unit/test_benchmark_metrics.py),
including every §8 worked example as a data-driven case). It builds on the
single reference matcher
[`../../tests/reference/benchmark_match.py`](../../tests/reference/benchmark_match.py)
and never defines a second match relation. It is not packaged and is not a
Skill.
