# Benchmark Severity-Accuracy Metric

Repository-development contract for GitHub Issue
[#56](https://github.com/amirbena/code-review-skill/issues/56). It defines
**how a benchmark run's matched findings are turned into a severity-accuracy
measurement** — for every produced finding that `MATCH`es an expected
entry, whether the produced severity is one the fixture permits, and, when
it is not, whether the reviewer called the finding **more** severe
(over-severity) or **less** severe (under-severity) than expected — per
case and in aggregate, emitted alongside the regression report's run-to-run
deltas. It builds on the produced↔expected pairing
([`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md) §2,
#55), the match relation ([`match-criteria.md`](match-criteria.md), #54),
the fixture's expected severity and its permitted-variance construct
([`fixture-format.md`](fixture-format.md) §8–§9, #50), the per-case result
shape ([`runner-contract.md`](runner-contract.md) §6, #52), and the
run-to-run report ([`regression-report.md`](regression-report.md), #53).
Parent capability:
[#41](https://github.com/amirbena/code-review-skill/issues/41).

Like [`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md)
and the rest of [`./`](README.md), this is a **repository-development doc:
not packaged into either Skill archive**, and no packaged Skill resource
depends on it. It reuses the shared finding shape, the P0/P1/P2 severity
vocabulary of [`../../shared/policies/severity.md`](../../shared/policies/severity.md),
the `MATCH` / `NEAR_MISS` / `NO_MATCH` pairwise result of
[`match-criteria.md`](match-criteria.md), and the one-to-one pairing of
[`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md); it
does **not** redefine the match relation, re-derive a pairing, or restate
what P0/P1/P2 mean.

## Canonical invariant

> **A benchmark run's severity accuracy is three counts per case over the matched set — how many matched findings carry a permitted expected severity (exact), how many the reviewer rated more severe than expected (over-severity), and how many less severe (under-severity) — computed by taking the #55 produced↔expected pairing unchanged, then, for each pair, comparing the produced severity against the permitted expected severities for the entry that pair satisfied. The comparison uses only the P0/P1/P2 ordinal and the fixture's `severity` field; a `NEAR_MISS`, an unpaired entry, or an unpaired produced finding never enters it, and no rule here changes which findings are paired.**

Every rule below is an elaboration of that sentence. The exact-match
**rate** the metric reports is a derived ratio of two of those counts (§4),
not an independent judgement. Three neighbouring concerns are deliberately
*out* of it and owned elsewhere (§8): the pairing and the missed / incorrect
counts themselves
([#55](https://github.com/amirbena/code-review-skill/issues/55)), the
`MATCH` relation
([#54](https://github.com/amirbena/code-review-skill/issues/54)), and
duplicate / same-root-cause noise
([#57](https://github.com/amirbena/code-review-skill/issues/57)). Redefining
P0/P1/P2 is a non-goal of
[#56](https://github.com/amirbena/code-review-skill/issues/56) itself.

## 1. Terminology and ownership

- **Matched pair** — one `(expected entry, produced finding)` assignment in
  the #55 pairing
  ([`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md)
  §2): every such pair is a `MATCH`. `required` and `optional` entries that
  got paired both take part here — a matched `optional` finding still has an
  expected severity to check.
- **Permitted expected severities** — the `severity` field of the entry the
  pair satisfied ([`fixture-format.md`](fixture-format.md) §8.1, §9
  construct 4): a single value means that exact value only; a list of ≥ 2
  distinct values means **any one** of them is acceptable. For an `any_of`
  group the entry that was satisfied is the achieving **member**
  ([`match-criteria.md`](match-criteria.md) §6), so the member's `severity`
  is used, not the group's.
- **Produced severity** — the `severity` a produced finding was recorded
  with ([`runner-contract.md`](runner-contract.md) §6): exactly one of
  `P0` / `P1` / `P2`.
- **Severity ordinal** — `P0` more severe than `P1` more severe than `P2`,
  the same ordering
  [`regression-report.md`](regression-report.md) §5 uses for a severity
  rise. This document reads that ordering; it does not define the levels.
- **Exact** — a matched pair whose produced severity is one of the
  permitted expected severities.
- **Over-severity** — a matched pair whose produced severity is **more
  severe than every** permitted expected severity.
- **Under-severity** — a matched pair that is neither exact nor
  over-severity: the produced severity is less severe than the most severe
  permitted value and is not itself permitted.

This document does **not** define: the match relation (#54); the pairing or
the false-negative / false-positive counts (#55); the fixture format or the
corpus (#50 / #51); how produced findings are captured (#52); the
run-to-run diff (#53); duplicate-noise measurement (#57); the P0/P1/P2
definitions ([`../../shared/policies/severity.md`](../../shared/policies/severity.md));
or any single blended quality score.

## 2. The matched set

The severity check runs over **exactly** the pairs the #55 pairing
produced — its `paired` map from expected-entry key to produced-finding
index
([`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md)
§2). This document consumes that map; it never re-runs the greedy pass,
re-orders it, or promotes a `NEAR_MISS` into it.

- An **unpaired `required` entry** (a false negative, #55 §3) contributes
  nothing here — a finding the reviewer never produced has no severity to
  score. Its absence is already counted by #55.
- An **unpaired produced finding** — a false positive, an
  `absorbed_extra_match`, or a `tolerated_unexpected`
  ([`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md)
  §2.1, §4) — contributes nothing here: it satisfied no expected entry, so
  there is no expected severity to compare it against.
- A **`NEAR_MISS`** never pairs (#55 §2), so it is never severity-scored.
- An **errored case** ([`runner-contract.md`](runner-contract.md) §6)
  produced nothing: its matched set is empty and all three counts are `0`.

## 3. Classifying a matched pair

For each matched pair, let `E` be the set of permitted expected severities
(§1) for the satisfied entry and `p` the produced severity:

1. **`p ∈ E` → exact.** The reviewer's severity is one the fixture author
   declared acceptable — whether `E` is a single value or a permitted list.
2. **`p` more severe than `max(E)` → over-severity**, where `max(E)` is the
   most severe permitted value on the P0 > P1 > P2 ordinal. The reviewer
   rated the finding above the whole permitted band.
3. **Otherwise → under-severity.** `p` is not permitted and not above the
   band, so it is below the most severe permitted value. The reviewer
   under-called the finding.

`E` is expected to be a contiguous band on the ordinal (the fixture
format's own example is "`P1` or `P2`"). The classification stays total and
deterministic for a non-contiguous `E` too — an interior value such as `P1`
against `E = {P0, P2}` is `p ∉ E` and not above `max(E) = P0`, so it counts
as **under-severity** (the reviewer did not reach the most severe permitted
value).

Over-severity and under-severity are the two directions the acceptance
criterion asks to be distinguished; together with exact they partition the
matched set, so `exact + over_severity + under_severity == matched` for
every case.

## 4. Per-case and aggregate output

For every case the metric record carries:

| Field | Meaning |
|---|---|
| `id` | Case id ([`fixture-format.md`](fixture-format.md) §5). |
| `status` | `executed` for a runner `executed` result; `errored` for a runner `error` or a missing per-case result (matched set empty). |
| `matched` | Count of matched pairs scored (§2). |
| `severity_exact` | Count of exact pairs (§3 rule 1). |
| `over_severity` | Count of over-severity pairs (§3 rule 2). |
| `under_severity` | Count of under-severity pairs (§3 rule 3). |
| `exact_rate` | `severity_exact / matched` as an exact reduced fraction, or `null` when `matched` is `0` (an undefined rate is not `0`). |
| `mismatches` | One record per non-exact pair, in fixture entry order — `{key, produced_index, expected: [permitted severities], produced, direction: "over" | "under"}`. Explainability, not a second metric. |

The aggregate record, computed only by summing the per-case counts over
**all** cases in the run:

| Field | Meaning |
|---|---|
| `total_matched` | Σ `matched`. |
| `total_severity_exact` | Σ `severity_exact`. |
| `total_over_severity` | Σ `over_severity`. |
| `total_under_severity` | Σ `under_severity`. |
| `exact_rate` | `total_severity_exact / total_matched` as an exact reduced fraction, or `null` when `total_matched` is `0`. |
| `cases_with_severity_mismatch` | How many cases have `over_severity + under_severity > 0`. |

The only ratio here is `exact_rate`, and it is reported as an exact
rational (a `fractions.Fraction`, rendered as its canonical string) so it
never depends on binary-float representation — the same reason
[`match-criteria.md`](match-criteria.md) §7 fixes its thresholds as
rationals. No count is weighted or normalized, and the metric emits no
precision, no recall, and no single blended score — those stay out of scope
for [#41](https://github.com/amirbena/code-review-skill/issues/41) by its
Non-Goals.

## 5. Rendering alongside the regression report

Exactly as
[`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md) §6
does for the missed / incorrect counts:

- When the corpus fixtures' `expected` blocks are available beside a
  candidate run, the benchmark report gains a **`severity_accuracy`**
  section holding the §4 per-case records and aggregate for the candidate
  run.
- When a **baseline** run is also being compared
  ([`regression-report.md`](regression-report.md) §3), the section renders
  the metrics **alongside the per-case deltas**: for each case `id` present
  in both runs, the baseline and candidate `severity_exact` /
  `over_severity` / `under_severity` and their differences (`Δ = candidate
  − baseline`); and the same three-column shape for the aggregate counts.
  Cases are ordered by `id`, exactly as the rest of the report
  ([`regression-report.md`](regression-report.md) §7).
- A case `id` in only one of the two runs has no per-case Δ row; the
  section lists such ids in `added_case_ids` / `removed_case_ids`,
  mirroring the run-to-run report's own added / removed handling
  ([`regression-report.md`](regression-report.md) §3).
- The section is **computed independently** of the run-to-run diff and
  **never changes** `has_regressions` or the report's process exit status
  ([`regression-report.md`](regression-report.md) §6, §9). A rising
  `under_severity` Δ is a quality signal a human or a separate gate acts
  on; wiring it to a gate is out of scope here and on
  [#40](https://github.com/amirbena/code-review-skill/issues/40).
- The section obeys the report's determinism rules
  ([`regression-report.md`](regression-report.md) §7): byte-identical for
  identical inputs, no wall-clock or path noise, empty-but-well-formed when
  the matched set is empty (`exact_rate` is `null`, every count `0`).
- The `corpus_id` guard still applies: metrics comparing a baseline and a
  candidate that ran against different corpora are not computed
  ([`regression-report.md`](regression-report.md) §3).

## 6. Determinism and two-reader consistency

- **The pairing is an input, not a step.** §2 takes the #55 `paired` map
  verbatim. Nothing in this document can pair, unpair, or re-order a
  finding, so it cannot disagree with #55 or #54 about what matched.
- **Fixed classification order.** For each pair: resolve `E` (the satisfied
  entry, or the achieving `any_of` member) → apply §3 rules 1, 2, 3 in that
  order. The three outcomes partition the matched set.
- **Integers and exact rationals only.** Counts are integer sums;
  `exact_rate` is a `fractions.Fraction`. No float, no rounding, no
  platform-dependent comparison.
- **No new tolerances.** The only tolerances in the whole computation are
  the ones [`match-criteria.md`](match-criteria.md) already fixed, and they
  are spent before this document runs. Severity comparison is exact on the
  three-value ordinal.
- **Two readers, same counts.** The §7 worked examples are the conformance
  bar: two people applying §2–§4 to them must reach the same `matched`,
  `severity_exact`, `over_severity`, and `under_severity` for every case.

## 7. Worked examples

All are encoded verbatim as data-driven cases in
[`../../tests/unit/test_benchmark_severity.py`](../../tests/unit/test_benchmark_severity.py);
two readers applying §2–§4 must reach the count columns for every row. Each
pair is written as *permitted expected severities* → *produced severity*.

| # | Matched pairs | matched | exact | over | under | `exact_rate` | Note |
|---|---|---|---|---|---|---|---|
| 1 | `{P1}`→`P1`, `{P0}`→`P0` | 2 | 2 | 0 | 0 | `1` | Every matched finding at the expected severity. |
| 2 | `{P1}`→`P0` | 1 | 0 | 1 | 0 | `0` | Reviewer over-calls a `P1` as `P0`. |
| 3 | `{P0}`→`P1` | 1 | 0 | 0 | 1 | `0` | Reviewer under-calls a `P0` as `P1`. |
| 4 | `{P1}`→`P1`, `{P0}`→`P2` | 2 | 1 | 0 | 1 | `1/2` | One exact, one under-severity (`P0` reported `P2`). |
| 5 | `{P1, P2}`→`P2` | 1 | 1 | 0 | 0 | `1` | Permitted severity variance: `P2` is in the band → exact. |
| 6 | `{P1, P2}`→`P0` | 1 | 0 | 1 | 0 | `0` | `P0` is above the whole permitted band → over-severity. |
| 7 | *(none — every entry missed, or `status: error`)* | 0 | 0 | 0 | 0 | `null` | Empty matched set; contributes nothing to the aggregate. |
| 8 | `any_of` satisfied via member with `severity: P2`; produced `P1` | 1 | 0 | 1 | 0 | `0` | The achieving member's severity is the reference, not the group's. |
| 9 | matched **optional** entry `{P2}`→`P2` | 1 | 1 | 0 | 0 | `1` | A paired `optional` finding is in the matched set. |

**Rows 2, 3, 4, 6, and 8 are the deliberate severity mismatches** the
acceptance criterion asks to be validated: each is classified as exactly
one of over-severity or under-severity, and the exact-match rate drops
accordingly.

## 8. Explicitly out of scope

| Not defined here | Owner |
|---|---|
| The produced↔expected pairing, and the missed-finding / incorrect-finding counts it feeds | [#55](https://github.com/amirbena/code-review-skill/issues/55) — [`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md) |
| The produced-vs-expected `MATCH` / `NEAR_MISS` / `NO_MATCH` relation, its axes and tolerances | [#54](https://github.com/amirbena/code-review-skill/issues/54) — [`match-criteria.md`](match-criteria.md) |
| Duplicate / same-root-cause clustering and the noise metric | [#57](https://github.com/amirbena/code-review-skill/issues/57) — [`duplicate-noise.md`](duplicate-noise.md) |
| A single blended quality score, precision / recall / pass rate, or a merge gate | out of scope for [#41](https://github.com/amirbena/code-review-skill/issues/41) by its Non-Goals |
| The run-to-run diff itself (`dropped` / `gained` / `retained`, the severity-rise regression rule) | [#53](https://github.com/amirbena/code-review-skill/issues/53) — [`regression-report.md`](regression-report.md) |
| The fixture format, the `severity` list construct, and the corpus | [#50](https://github.com/amirbena/code-review-skill/issues/50) / [#51](https://github.com/amirbena/code-review-skill/issues/51) |
| Capturing produced findings and their severities; the per-case result shape | [#52](https://github.com/amirbena/code-review-skill/issues/52) |
| CI wiring / a merge gate acting on the metric deltas | [#40](https://github.com/amirbena/code-review-skill/issues/40) |
| The P0/P1/P2 definitions and the decision derivation | [`../../shared/policies/severity.md`](../../shared/policies/severity.md) |
| The finding field shape | [`../../shared/templates/finding.md`](../../shared/templates/finding.md) |

## Status and canonical home

**This document is the authoritative contract** for benchmark
severity-accuracy accounting until a later issue installs an equivalent
runnable component in a canonical home. At that point this document becomes
the design record: it MUST link to that component and MUST NOT keep
evolving the accounting independently — exactly as
[`missed-and-incorrect-findings.md`](missed-and-incorrect-findings.md),
"Status and canonical home," and
[`match-criteria.md`](match-criteria.md), "Status and canonical home,"
describe for their own eventual installation.

The test-only reference metric
[`../../tests/reference/benchmark_severity.py`](../../tests/reference/benchmark_severity.py)
mirrors this document for regression coverage (executed by
[`../../tests/unit/test_benchmark_severity.py`](../../tests/unit/test_benchmark_severity.py),
including every §7 worked example as a data-driven case). It consumes the
single reference pairing
[`../../tests/reference/benchmark_metrics.py`](../../tests/reference/benchmark_metrics.py)
and the single reference matcher
[`../../tests/reference/benchmark_match.py`](../../tests/reference/benchmark_match.py)
and defines no second pairing or match relation. It is not packaged and is
not a Skill.
