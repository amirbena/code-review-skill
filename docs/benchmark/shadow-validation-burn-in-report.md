# Worked Example: A Reconstructed Shadow-Validation Burn-In Report

Companion to [`shadow-validation.md`](shadow-validation.md) (#335). This
is a **worked example demonstrating the methodology**, not a live
production evidence bar: no real burn-in window exists yet, because the
Class 2 nightly Routine target
([`cloud-routine-integration.md`](cloud-routine-integration.md),
[`nightly-history-and-baseline.md`](nightly-history-and-baseline.md)) is
maintainer-triggered and has not yet accumulated a real schedule of paired
PR-selection / nightly-comparison evidence. Per
[`shadow-validation.md`](shadow-validation.md)'s own issue text, the
Validation section explicitly permits "real or reconstructed PRs" for
this deliverable — this report uses **reconstructed** samples.

## What "reconstructed" means here

The eight samples below are hand-authored scenarios, not real PRs or real
nightly runs. What is *not* hand-authored is the arithmetic: every figure
in this document was produced by actually running
[`scripts/benchmark/shadow_validate.py`](../../scripts/benchmark/shadow_validate.py)
against
[`examples/shadow-validation-burn-in-samples.json`](examples/shadow-validation-burn-in-samples.json),
and the committed output is
[`examples/shadow-validation-burn-in-report.json`](examples/shadow-validation-burn-in-report.json) —
regenerate it with:

```bash
python3 scripts/benchmark/shadow_validate.py \
    --samples docs/benchmark/examples/shadow-validation-burn-in-samples.json \
    --window-description "Reconstructed worked example, 8 synthetic PR samples over the existing corpus (not live production evidence)" \
    --output docs/benchmark/examples/shadow-validation-burn-in-report.json
```

The case ids used (`analogue-placement-test-file-split-clean`,
`cfv-unproven-regression-not-asserted`, `api-compat-remove-field-breaking`,
`api-compat-rename-response-property-breaking`,
`cfv-disconfirmed-severe-candidate-dropped`,
`api-compat-optional-to-required-breaking`) are real corpus case ids from
[`corpus-index.json`](corpus-index.json), chosen only so the example reads
against real identifiers; the selections and "regressions" attributed to
them are synthetic scenarios, not anything those cases actually did in a
real run.

## The scenario

Eight reconstructed PRs, each pairing a synthetic Top-K selection with a
synthetic set of case ids a nightly comparison "found a regression in,"
designed to exercise every path §2/§3 of
[`shadow-validation.md`](shadow-validation.md) describe: a clean catch, a
selector-side miss (the regressed case was never in the candidate pool
selected), a case selected repeatedly that never once corresponds to a
caught regression, and a vacuous no-regression night.

| Sample | Selected | Regressed | Outcome |
| --- | --- | --- | --- |
| `reconstructed-pr-101` | placement-clean, unproven-regression, remove-field | unproven-regression | caught |
| `reconstructed-pr-102` | placement-clean, rename-response-property | rename-response-property | caught |
| `reconstructed-pr-103` | placement-clean, unproven-regression | disconfirmed-severe-candidate | **missed** (not selected) |
| `reconstructed-pr-104` | unproven-regression, remove-field | remove-field | caught |
| `reconstructed-pr-105` | placement-clean, remove-field | — | vacuous (no regression this night) |
| `reconstructed-pr-106` | placement-clean, optional-to-required | optional-to-required, unproven-regression | one caught, one **missed** (unproven-regression not selected this time) |
| `reconstructed-pr-107` | placement-clean, rename-response-property | rename-response-property | caught |
| `reconstructed-pr-108` | placement-clean, unproven-regression, remove-field | remove-field | caught |

## Observed figures

From [`examples/shadow-validation-burn-in-report.json`](examples/shadow-validation-burn-in-report.json):

- **Miss rate: 2/8 = 25.00%.** Two regressions
  (`cfv-disconfirmed-severe-candidate-dropped` in `reconstructed-pr-103`,
  `cfv-unproven-regression-not-asserted` in `reconstructed-pr-106`) were
  not in that PR's selected set.
- **Redundancy rate: 1/5 = 20.00%.** Of the five distinct cases ever
  selected across the window,
  `analogue-placement-test-file-split-clean` was selected in seven of the
  eight samples and never once corresponded to a caught regression — the
  one case `cases_never_caught_a_regression` names.

## Applying §4's methodology to this example

This is exactly the size of window [`shadow-validation.md`](shadow-validation.md)
§4.1 warns against drawing a bar from: eight samples is enough to
demonstrate the report shape and prove the arithmetic, not enough to
distinguish a genuine 25% miss rate from sampling noise on a four-
regression denominator (`total_regressions: 4` — one bad night could swing
this figure by 25 points on its own). No evidence bar is set from this
report. Once a real burn-in window accumulates from actual paired PR/
nightly evidence, a maintainer applies the same §4 process — read the
per-sample breakdown, not just the aggregate; check whether a case like
`analogue-placement-test-file-split-clean` above stays redundant across a
much larger window before treating that as a real over-selection finding
rather than this example's small-sample artifact; and record the
resulting bar as an update to [`shadow-validation.md`](shadow-validation.md)
§4, citing the report it came from.
