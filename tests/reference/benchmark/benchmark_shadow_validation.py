#!/usr/bin/env python3
"""Shadow-validation methodology for the Top-K benchmark selector
(Issue #335). Contract: docs/benchmark/shadow-validation.md.

Test-only reference, like ``benchmark_selection.py`` and
``benchmark_taxonomy.py`` alongside it: not runtime logic, not packaged —
the packaged Skills stay Markdown/YAML only. Consumed by
``tests/unit/benchmark/test_benchmark_shadow_validation.py`` and the real
(non-packaged) tooling entrypoint ``scripts/benchmark/shadow_validate.py``.

This module owns exactly the comparison this issue is responsible for: how
trustworthy is #334's Top-K selection when measured against #339's
already-classified full-corpus drift? It never re-derives a selection
(#334's job) or re-derives drift classification (#339's job) — it consumes
a pre-joined ``BurnInSample`` (one PR's Top-K selected case ids, paired
with the distinct case ids a nightly comparison found real regressions in
over that PR's burn-in window) and computes two figures over one or more
samples:

- **Miss rate** — of the regressions the full corpus caught, how many
  would the PR's Top-K selection, had it been the only signal, have
  missed?
- **Redundancy** — of the cases the selector ever picked across the
  window, how many never once corresponded to a real caught regression?

Both are case-level, not finding-level: the selector (docs/benchmark/
selection.md) picks whole cases, so "would this selection have caught the
regression" is answered at the same granularity it operates at.

Redundancy is deliberately *not* defined as "zero marginal coverage gain
at pick time" — selection.md §4's stopping rule guarantees every picked
case has a strictly positive marginal gain when it is picked, so that
signal can never fire by construction. Redundancy here instead measures
whether the selector's taxonomy-coverage proxy for "this case matters"
ever cashes out as an actually-observed regression over real burn-in
evidence — a case can look required by coverage and still never once be
the case a nightly comparison caught something in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Sequence


@dataclass(frozen=True)
class BurnInSample:
    """One join of a PR-time Top-K selection to the nightly full-corpus
    evidence for the burn-in window it overlaps. Produced externally —
    this module never runs a selection (#334) or classifies drift (#339);
    it only consumes their already-computed outputs, exactly as
    docs/benchmark/shadow-validation.md §1 describes.

    ``selected_case_ids`` — the case ids from a #334 explainability
    object's ``selected_cases`` for one PR (deduplicated; order does not
    matter here).
    ``regressed_case_ids`` — the distinct case ids that had at least one
    #339 ``DriftRecord`` in the nightly comparison(s) this PR's burn-in
    window overlaps.
    """

    sample_id: str
    selected_case_ids: tuple[str, ...]
    regressed_case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_case_ids", tuple(sorted(set(self.selected_case_ids))))
        object.__setattr__(self, "regressed_case_ids", tuple(sorted(set(self.regressed_case_ids))))


@dataclass(frozen=True)
class SampleEvaluation:
    """Pure set arithmetic over one :class:`BurnInSample` — deterministic,
    no aggregation or threshold judgment yet (that is :func:`aggregate_burn_in`)."""

    sample_id: str
    missed_case_ids: tuple[str, ...]
    caught_case_ids: tuple[str, ...]
    unexercised_selected_case_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "missed_case_ids": list(self.missed_case_ids),
            "caught_case_ids": list(self.caught_case_ids),
            "unexercised_selected_case_ids": list(self.unexercised_selected_case_ids),
        }


def evaluate_sample(sample: BurnInSample) -> SampleEvaluation:
    """A regression is **missed** when its case id was not selected;
    **caught** when it was. A selected case is **unexercised** in this one
    sample when the nightly comparison found no regression in it — that
    alone is not redundancy (most cases are unexercised on most nights by
    construction); redundancy is only meaningful aggregated across the
    whole window (:func:`aggregate_burn_in`)."""
    selected = set(sample.selected_case_ids)
    regressed = set(sample.regressed_case_ids)
    return SampleEvaluation(
        sample_id=sample.sample_id,
        missed_case_ids=tuple(sorted(regressed - selected)),
        caught_case_ids=tuple(sorted(regressed & selected)),
        unexercised_selected_case_ids=tuple(sorted(selected - regressed)),
    )


@dataclass(frozen=True)
class BurnInAggregate:
    """The window-level evidence: a miss rate over every regression the
    full corpus caught across the window, and a redundancy rate over
    every case the selector ever picked across the window. Both rates are
    ``None`` — not zero — when their denominator is empty, matching the
    "vacuous, not spuriously passing" convention #334's own
    ``insufficient-coverage``/pairs-vacuously-covered handling already
    established (docs/benchmark/selection.md §3.3)."""

    sample_count: int
    total_regressions: int
    total_missed: int
    miss_rate: Fraction | None
    distinct_selected_case_ids: tuple[str, ...]
    cases_never_caught_a_regression: tuple[str, ...]
    redundancy_rate: Fraction | None
    per_sample: tuple[SampleEvaluation, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "total_regressions": self.total_regressions,
            "total_missed": self.total_missed,
            "miss_rate": _fraction_or_none(self.miss_rate),
            "distinct_selected_case_ids": list(self.distinct_selected_case_ids),
            "cases_never_caught_a_regression": list(self.cases_never_caught_a_regression),
            "redundancy_rate": _fraction_or_none(self.redundancy_rate),
            "per_sample": [s.as_dict() for s in self.per_sample],
        }


def _fraction_or_none(value: Fraction | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {"numerator": value.numerator, "denominator": value.denominator, "float": float(value)}


def aggregate_burn_in(samples: Sequence[BurnInSample]) -> BurnInAggregate:
    """Aggregate every sample in the burn-in window into the two window-
    level figures docs/benchmark/shadow-validation.md §2/§3 define.

    A regression is counted fresh in every sample it appears in (the same
    real-world regression recurring across nights is, correctly, evidence
    the selector keeps missing it, not a single event to dedupe) —
    consistent with #339's own fingerprint carrying no run-specific data
    while a "still reproducing" comment is posted every night it recurs
    (docs/benchmark/drift-detection-and-regression-lifecycle.md §3/§4.3).

    Redundancy, by contrast, is evaluated over the *distinct* set of cases
    ever selected in the window — a case selected ten times and never
    once corresponding to a caught regression is one redundant case, not
    ten.
    """
    evaluations = tuple(evaluate_sample(sample) for sample in samples)

    total_regressions = sum(len(s.regressed_case_ids) for s in samples)
    total_missed = sum(len(e.missed_case_ids) for e in evaluations)
    miss_rate = Fraction(total_missed, total_regressions) if total_regressions else None

    distinct_selected: set[str] = set()
    ever_caught: set[str] = set()
    for sample, evaluation in zip(samples, evaluations):
        distinct_selected.update(sample.selected_case_ids)
        ever_caught.update(evaluation.caught_case_ids)
    never_caught = tuple(sorted(distinct_selected - ever_caught))
    redundancy_rate = Fraction(len(never_caught), len(distinct_selected)) if distinct_selected else None

    return BurnInAggregate(
        sample_count=len(samples),
        total_regressions=total_regressions,
        total_missed=total_missed,
        miss_rate=miss_rate,
        distinct_selected_case_ids=tuple(sorted(distinct_selected)),
        cases_never_caught_a_regression=never_caught,
        redundancy_rate=redundancy_rate,
        per_sample=evaluations,
    )


def build_burn_in_report(aggregate: BurnInAggregate, *, window_description: str) -> dict[str, Any]:
    """Render an aggregate into the one machine-readable report object
    docs/benchmark/shadow-validation.md §5 describes: the figures alone,
    with no embedded pass/fail verdict — the evidence bar that turns a
    miss rate/redundancy rate into a decision is a methodology, applied by
    a maintainer reading the report, not a threshold this function
    encodes (§4)."""
    return {
        "window_description": window_description,
        **aggregate.as_dict(),
    }
