# Benchmark Duplicate-Noise Metric

Repository-development contract for GitHub Issue
[#57](https://github.com/amirbena/code-review-skill/issues/57). It defines
**how a benchmark run's produced findings are turned into a
duplicate-noise measurement** — how many of a case's produced findings are
redundant restatements of a root cause another produced finding already
names — per case and in aggregate, with the noisiest cases surfaced, and
emitted alongside the regression report's run-to-run deltas. It builds on
the match relation ([`match-criteria.md`](match-criteria.md), #54) — the
same `MATCH` cell, applied to a pair of *produced* findings — the per-case
result shape ([`runner-contract.md`](runner-contract.md) §6, #52), and the
run-to-run report ([`regression-report.md`](regression-report.md), #53).
Parent capability:
[#41](https://github.com/amirbena/code-review-skill/issues/41).

Like [`severity-accuracy.md`](severity-accuracy.md) and the rest of
[`./`](README.md), this is a **repository-development doc: not packaged
into either Skill archive**, and no packaged Skill resource depends on it.
It reuses the shared finding shape, the P0/P1/P2 severity vocabulary of
[`../../shared/policies/severity.md`](../../shared/policies/severity.md),
and the `MATCH` / `NEAR_MISS` / `NO_MATCH` pairwise result and its two axes
(location correspondence, defect correspondence) of
[`match-criteria.md`](match-criteria.md); it does **not** redefine the
match relation, add an axis, add a tolerance, or define a
de-duplication behaviour for the reviewer itself.

## Canonical invariant

> **A benchmark run's duplicate noise is two counts per case over the produced findings alone — how many same-root-cause clusters the produced findings form, and how many findings are therefore redundant (every finding in a cluster past its first) — computed by taking each unordered pair of produced findings, calling it a same-root-cause edge exactly when the #54 relation is `MATCH` (location EXACT and defect CORRESPONDS) in either direction, and grouping the findings into connected components over those edges. The counts use only the #54 criteria and the produced findings' own fields; no expected finding, no #55 pairing, no severity judgement, and no score enters them.**

Every rule below is an elaboration of that sentence. The one ratio the
metric reports, the duplicate **rate** (§4), is a derived fraction of two
of those counts, not an independent judgement. Three neighbouring concerns
are deliberately *out* of it and owned elsewhere (§8): the
produced↔expected pairing and the missed / incorrect counts
([#55](https://github.com/amirbena/code-review-skill/issues/55)), severity
accuracy over the matched set
([#56](https://github.com/amirbena/code-review-skill/issues/56)), and the
`MATCH` relation itself
([#54](https://github.com/amirbena/code-review-skill/issues/54)). A
de-duplication behaviour inside the reviewer is a non-goal of
[#57](https://github.com/amirbena/code-review-skill/issues/57) itself.

## 1. Terminology and ownership

- **Produced finding** — one reviewer result recorded verbatim by the
  runner ([`runner-contract.md`](runner-contract.md) §6), addressed by its
  index in the case's ordered `produced_findings` list. This metric reads
  only produced findings.
- **Same-root-cause edge** — an unordered pair of produced findings whose
  #54 pairwise result is `MATCH`: location correspondence **EXACT** and
  defect correspondence **CORRESPONDS**
  ([`match-criteria.md`](match-criteria.md) §3–§5). A `NEAR_MISS` pair
  (one axis only) is **not** an edge — two findings that are merely near
  each other or merely related are not the same finding.
- **Same-root-cause cluster** — a connected component of the graph whose
  vertices are the case's produced findings and whose edges are the
  same-root-cause edges (§3). A finding that shares an edge with nothing is
  a cluster of one.
- **Duplicate cluster** — a cluster of size ≥ 2.
- **Redundant finding** — a produced finding in a cluster past the first:
  a cluster of size `k` contributes `k − 1` redundant findings. Summed
  over a case, `redundant_findings == produced − clusters`.
- **Duplicate rate** — `redundant_findings / produced` as an exact reduced
  fraction, `null` when the case produced nothing.

This document does **not** define: the match relation itself, its axes or
its tolerances (#54); the produced↔expected pairing or the
false-negative / false-positive counts (#55); severity-accuracy
measurement (#56); the fixture format or the corpus (#50 / #51); how
produced findings are captured (#52); the run-to-run diff (#53); the
P0/P1/P2 definitions
([`../../shared/policies/severity.md`](../../shared/policies/severity.md));
any de-duplication logic the reviewer might run; or any single blended
quality score.

## 2. The same-root-cause edge

For each unordered pair of the case's produced findings, the edge test is
**the #54 matcher, unchanged**. One finding of the pair is viewed as an
expected sub-spec — carrying only the location and defect fields
[`match-criteria.md`](match-criteria.md) §3–§4 already read (intent, path,
symbol, anchor, `lines`, `claim`, `defect_kind`), inventing nothing — and
scored against the other finding with the same
[`match-criteria.md`](match-criteria.md) §5 combination table. The pair is
a same-root-cause edge **iff that result is `MATCH`**.

- **No new axis, no new tolerance.** The ± 3-line proximity window and the
  two claim-overlap thresholds are exactly the ones
  [`match-criteria.md`](match-criteria.md) §3–§4, §7 fixed; this document
  adds none and loosens none. Severity is not consulted (it is not a #54
  axis, and it is [#56](https://github.com/amirbena/code-review-skill/issues/56)).
- **Symmetrized.** [`match-criteria.md`](match-criteria.md) location
  correspondence has a few order-sensitive branches for a degenerate
  finding (a missing path, a repository-scoped side). The edge test runs
  the matcher in **both** directions and takes an edge when **either**
  direction is `MATCH`; whenever both findings carry a path and a line
  span — the ordinary case — the two directions agree and the
  symmetrization is a no-op.
- **`MATCH` only.** A `NEAR_MISS` pair is never an edge. Two findings at
  the same line describing genuinely different defects (`EXACT` +
  `UNRELATED` → `NO_MATCH`), or the same defect one file apart (`NONE`
  location → `NO_MATCH`), or the same location with only *related* claims
  and no `defect_kind` (`EXACT` + `RELATED` → `NEAR_MISS`) are **not**
  redundant.

## 3. Clustering the produced findings

The same-root-cause edges define an undirected graph on the case's
produced findings. The clusters are its **connected components**, computed
by a deterministic union-find over the produced-finding indices:

1. Start every finding in its own singleton.
2. Walk the index pairs `(i, j)` with `i < j` in ascending order; on a
   same-root-cause edge (§2), union the two components, attaching the
   higher representative index under the lower.
3. A component is the ascending list of its member indices; the clusters
   are ordered by each component's smallest member index.

Connectivity is **transitive by construction**: if finding `A` shares an
edge with `B` and `B` with `C`, then `A`, `B`, and `C` are one cluster
even when `A` and `C` share no direct edge (for example three findings at
lines 40, 43, 46 — each within the ± 3-line window of the next, the ends
six lines apart). This is the connected-component definition, not an extra
rule, and it is order-independent.

## 4. Per-case and aggregate output

For every case the metric record carries:

| Field | Meaning |
|---|---|
| `id` | Case id ([`fixture-format.md`](fixture-format.md) §5). |
| `status` | `executed` for a runner `executed` result; `errored` for a runner `error` or a missing per-case result (nothing to cluster). |
| `produced` | Count of produced findings. |
| `clusters` | Count of same-root-cause clusters, **singletons included** (§3). |
| `duplicate_clusters` | Count of clusters of size ≥ 2. |
| `redundant_findings` | `produced − clusters` — every finding in a cluster past its first (§1). |
| `duplicate_rate` | `redundant_findings / produced` as an exact reduced fraction, or `null` when `produced` is `0` (an undefined rate is not `0`). |
| `cluster_members` | One record per duplicate cluster, ordered by representative index — `{representative_index, member_indices: [ascending indices], size}`. Explainability, not a second metric. |

The aggregate record, computed only by summing the per-case counts over
**all** cases in the run:

| Field | Meaning |
|---|---|
| `total_produced` | Σ `produced`. |
| `total_redundant_findings` | Σ `redundant_findings`. |
| `total_duplicate_clusters` | Σ `duplicate_clusters`. |
| `duplicate_rate` | `total_redundant_findings / total_produced` as an exact reduced fraction, or `null` when `total_produced` is `0`. |
| `cases_with_duplication` | How many cases have `redundant_findings > 0`. |

The only ratio here is `duplicate_rate`, and it is reported as an exact
rational (a `fractions.Fraction`, rendered as its canonical string) so it
never depends on binary-float representation — the same reason
[`match-criteria.md`](match-criteria.md) §7 fixes its thresholds as
rationals. No count is weighted or normalized, and the metric emits no
precision, no recall, and no single blended score — those stay out of scope
for [#41](https://github.com/amirbena/code-review-skill/issues/41) by its
Non-Goals.

## 5. Rendering alongside the regression report

Exactly as [`severity-accuracy.md`](severity-accuracy.md) §5 does for the
severity counts:

- When the corpus fixtures' `expected` blocks are available beside a
  candidate run, the benchmark report gains a **`duplicate_noise`** section
  holding the §4 per-case records and aggregate for the candidate run,
  plus a **`highest_noise_cases`** list — the cases with
  `redundant_findings > 0`, ordered by `redundant_findings` descending
  then `id` ascending, each `{id, redundant_findings, duplicate_clusters,
  produced}`. That list is the acceptance criterion's "report lists
  highest-noise cases," and it needs no baseline.
- When a **baseline** run is also being compared
  ([`regression-report.md`](regression-report.md) §3), the section renders
  the metrics **alongside the per-case deltas**: for each case `id` present
  in both runs, the baseline and candidate `redundant_findings` /
  `duplicate_clusters` and their differences (`Δ = candidate − baseline`);
  and the same three-column shape for the aggregate counts. Cases are
  ordered by `id`, exactly as the rest of the report
  ([`regression-report.md`](regression-report.md) §7).
- A case `id` in only one of the two runs has no per-case Δ row; the
  section lists such ids in `added_case_ids` / `removed_case_ids`,
  mirroring the run-to-run report's own added / removed handling
  ([`regression-report.md`](regression-report.md) §3).
- The section is **computed independently** of the run-to-run diff and
  **never changes** `has_regressions` or the report's process exit status
  ([`regression-report.md`](regression-report.md) §6, §9). A rising
  `redundant_findings` Δ is a quality signal a human or a separate gate
  acts on; wiring it to a gate is out of scope here and on
  [#40](https://github.com/amirbena/code-review-skill/issues/40).
- The section obeys the report's determinism rules
  ([`regression-report.md`](regression-report.md) §7): byte-identical for
  identical inputs, no wall-clock or path noise, empty-but-well-formed when
  no case produced a finding (`duplicate_rate` is `null`, every count `0`,
  `highest_noise_cases` empty).
- The `corpus_id` guard still applies: metrics comparing a baseline and a
  candidate that ran against different corpora are not computed
  ([`regression-report.md`](regression-report.md) §3).

## 6. Determinism and two-reader consistency

- **The edge test is the #54 matcher.** §2 calls
  [`match-criteria.md`](match-criteria.md) §5 verbatim on a pair of
  produced findings. Nothing here re-defines an axis or a threshold, so it
  cannot disagree with #54 about what corresponds.
- **Fixed clustering order.** Union-find over ascending index pairs
  `(i, j)`, `i < j`, higher representative attached under lower; clusters
  emitted smallest-member-index first. Connected components are
  independent of that order, but the traversal is pinned anyway.
- **Integers and exact rationals only.** Counts are integer sums;
  `duplicate_rate` is a `fractions.Fraction`. No float, no rounding, no
  platform-dependent comparison.
- **No new tolerances.** The only tolerances in the whole computation are
  the ones [`match-criteria.md`](match-criteria.md) already fixed, and
  they are spent inside the §2 edge test.
- **Two readers, same counts.** The §7 worked examples are the conformance
  bar: two people applying §2–§4 to them must reach the same `produced`,
  `clusters`, `duplicate_clusters`, and `redundant_findings` for every
  case.

## 7. Worked examples

All are encoded verbatim as data-driven cases in
[`../../tests/unit/test_benchmark_dupes.py`](../../tests/unit/test_benchmark_dupes.py);
two readers applying §2–§4 must reach the count columns for every row.
Each produced finding is written as *path*`:`*line* with its `defect_kind`
(or a claim when it has none).

| # | Produced findings | clusters | duplicate_clusters | redundant | `duplicate_rate` | Note |
|---|---|---|---|---|---|---|
| 1 | `a.py:40` command-injection; `b.py:88` path-traversal | 2 | 0 | 0 | `0` | Two unrelated findings — no duplication. |
| 2 | `a.py:40` command-injection; `a.py:40` command-injection | 1 | 1 | 1 | `1/2` | One root cause reported twice. |
| 3 | `a.py:40` sql-injection ×3 | 1 | 1 | 2 | `2/3` | Triple report of one root cause. |
| 4 | `a.py:40` command-injection; `a.py:40` resource-leak | 2 | 0 | 0 | `0` | Same line, genuinely different defects (`EXACT` + `UNRELATED` → `NO_MATCH`). |
| 5 | `a.py:40` sql-injection; `b.py:40` sql-injection | 2 | 0 | 0 | `0` | Same kind, different file (`NONE` location → `NO_MATCH`). |
| 6 | `a.py:40` "SQL injection in the user query builder"; `a.py:41` "SQL injection in user query builder" (no `defect_kind`) | 1 | 1 | 1 | `1/2` | Claim-overlap `CORRESPONDS` with no `defect_kind`, within the ± 3-line window. |
| 7 | `a.py:40` "cache invalidation race timing"; `a.py:40` "cache invalidation missing lock" (no `defect_kind`) | 2 | 0 | 0 | `0` | Same location, only *related* claims (`EXACT` + `RELATED` → `NEAR_MISS`) — not an edge. |
| 8 | `a.py:40`, `a.py:43`, `a.py:46` — same `defect_kind` | 1 | 1 | 2 | `2/3` | Transitive chain: 40–43 and 43–46 are edges, 40–46 is not; one connected component. |
| 9 | *(none — `status: error`)* | 0 | 0 | 0 | `null` | Errored case; contributes nothing to the aggregate. |

**Rows 2, 3, 6, and 8 are the redundancy the acceptance criterion asks to
be measured**; rows 4, 5, and 7 are the deliberate non-duplicates that a
looser rule would over-cluster.

## 8. Explicitly out of scope

| Not defined here | Owner |
|---|---|
| The produced-vs-expected `MATCH` / `NEAR_MISS` / `NO_MATCH` relation, its axes and tolerances | [#54](https://github.com/amirbena/code-review-skill/issues/54) — [`match-criteria.md`](match-criteria.md) |
| The produced↔expected pairing, the missed-finding / incorrect-finding counts, and the `absorbed_extra_match` count (duplicates of one *expected* entry) | [#55](https://github.com/amirbena/code-review-skill/issues/55) — [`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md) |
| Severity accuracy over the matched set (over- vs under-severity, exact-severity rate) | [#56](https://github.com/amirbena/code-review-skill/issues/56) — [`severity-accuracy.md`](severity-accuracy.md) |
| A single blended quality score, precision / recall / pass rate, or a merge gate | out of scope for [#41](https://github.com/amirbena/code-review-skill/issues/41) by its Non-Goals |
| A de-duplication behaviour inside the reviewer itself | non-goal of [#57](https://github.com/amirbena/code-review-skill/issues/57) |
| The run-to-run diff itself (`dropped` / `gained` / `retained`, the severity-rise regression rule) | [#53](https://github.com/amirbena/code-review-skill/issues/53) — [`regression-report.md`](regression-report.md) |
| The fixture format and the corpus | [#50](https://github.com/amirbena/code-review-skill/issues/50) / [#51](https://github.com/amirbena/code-review-skill/issues/51) |
| Capturing produced findings; the per-case result shape | [#52](https://github.com/amirbena/code-review-skill/issues/52) |
| The cross-revision stable finding identity mechanism (produced-vs-earlier-produced) | [#42](https://github.com/amirbena/code-review-skill/issues/42) / [#59](https://github.com/amirbena/code-review-skill/issues/59) |
| CI wiring / a merge gate acting on the metric deltas | [#40](https://github.com/amirbena/code-review-skill/issues/40) |
| The P0/P1/P2 definitions and the decision derivation | [`../../shared/policies/severity.md`](../../shared/policies/severity.md) |
| The finding field shape | [`../../shared/templates/finding.md`](../../shared/templates/finding.md) |

## Status and canonical home

**This document is the authoritative contract** for benchmark
duplicate-noise accounting until a later issue installs an equivalent
runnable component in a canonical home. At that point this document becomes
the design record: it MUST link to that component and MUST NOT keep
evolving the accounting independently — exactly as
[`severity-accuracy.md`](severity-accuracy.md), "Status and canonical
home," and
[`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md),
"Status and canonical home," describe for their own eventual installation.

The test-only reference metric
[`../../tests/reference/benchmark_dupes.py`](../../tests/reference/benchmark_dupes.py)
mirrors this document for regression coverage (executed by
[`../../tests/unit/test_benchmark_dupes.py`](../../tests/unit/test_benchmark_dupes.py),
including every §7 worked example as a data-driven case). It consumes the
single reference matcher
[`../../tests/reference/benchmark_match.py`](../../tests/reference/benchmark_match.py)
and defines no second match relation or pairing. It is not packaged and is
not a Skill.
