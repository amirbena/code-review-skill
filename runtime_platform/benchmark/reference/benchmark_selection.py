#!/usr/bin/env python3
"""Deterministic Top-K benchmark selector with weighted coverage policy
(Issue #334). Contract: runtime_platform/benchmark/selection.md.

Test-only reference, like ``benchmark_taxonomy.py`` alongside it: not
runtime logic, not packaged — the packaged Skills stay Markdown/YAML only.
Consumed by both ``tests/unit/benchmark/test_benchmark_selection.py`` and
the real (non-packaged) tooling entrypoint
``runtime_platform/benchmark/scripts/select_benchmark_cases.py``, exactly like
``benchmark_taxonomy.py`` is consumed by
``runtime_platform/benchmark/scripts/build_benchmark_index.py``.

Two distinct, deterministic computations, per the canonical architecture's
§5 ("PR benchmark path") — pure taxonomy-tag arithmetic, never a second
model call, never embeddings/semantic search:

- **Case Relevance Score** — how relevant one candidate case is to a PR's
  classification, computed only over the already-narrowed candidate pool
  (never the full corpus).
- **Selection Coverage Score** — how much of the PR's weighted
  behavioral/risk surface the *selected set* collectively covers.

Greedy Top-K selection maximizes marginal Selection Coverage gain within
the eligible (``>= SECONDARY_BAND_THRESHOLD``) pool, stopping at the
Top-K bound, the coverage threshold, or when no further eligible gain is
available — whichever comes first. ``insufficient-coverage`` is a
distinct, explicit outcome, never folded into a passing result.
"""

from __future__ import annotations

from typing import Any

from runtime_platform.benchmark.reference import benchmark_taxonomy as tax

# --------------------------------------------------------------------------
# Case Relevance Score — per-dimension weighted overlap. A dimension
# contributes its full weight when the case's declared value(s) and the
# PR's classified value(s) share at least one non-`unclassified` member,
# else zero. Sums to 100. Tunable, not architecturally load-bearing
# (runtime_platform/benchmark/selection.md §2).
# --------------------------------------------------------------------------
CASE_RELEVANCE_WEIGHTS: dict[str, int] = {
    "capability": 40,
    "policy_contract": 25,
    "risk_mode": 20,
    "affected_surface": 15,
}
assert sum(CASE_RELEVANCE_WEIGHTS.values()) == 100
assert set(CASE_RELEVANCE_WEIGHTS) == tax.DIMENSION_NAMES

# Policy relevance bands (runtime_platform/benchmark/selection.md §2).
PRIMARY_BAND_THRESHOLD = 60
SECONDARY_BAND_THRESHOLD = 40

BAND_PRIMARY = "primary"
BAND_SECONDARY = "secondary"
BAND_NOT_ELIGIBLE = "not-eligible"

# Golden threshold: Selection Coverage >= 60% (runtime_platform/benchmark/selection.md §3).
SELECTION_COVERAGE_THRESHOLD: float = 60.0

# Top-K bound: a small default, overridable per run within a fixed,
# non-configurable ceiling (runtime_platform/benchmark/selection.md §4).
K_DEFAULT = 6
K_MAX = 12

OUTCOME_SUFFICIENT_COVERAGE = "sufficient-coverage"
OUTCOME_INSUFFICIENT_COVERAGE = "insufficient-coverage"

TaxonomyMap = dict[str, tuple[str, ...]]


def _non_unclassified(values: Any) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple, set, frozenset)):
        return ()
    return tuple(v for v in values if v != tax.UNCLASSIFIED)


def case_taxonomies_from_index(
    index: dict[str, dict[str, list[str]]],
) -> dict[str, TaxonomyMap]:
    """Invert the committed ``corpus-index.json`` shape
    (``{dimension: {value: [case_id, ...]}}``) back into a per-case
    taxonomy map (``{case_id: {dimension: (value, ...)}}``).

    This is a cheap, in-memory transform of the already-loaded index — not
    a corpus re-scan (no YAML re-parsing, no model call) — so building it
    once per selection run does not reintroduce the full-corpus-scan cost
    #333's index exists to avoid. Only cases actually present in a matched
    ``(dimension, value)`` bucket ever appear as a key.
    """
    taxonomies: dict[str, dict[str, set[str]]] = {}
    for dim, values in index.items():
        for value, case_ids in values.items():
            for case_id in case_ids:
                taxonomies.setdefault(case_id, {}).setdefault(dim, set()).add(value)
    return {
        case_id: {dim: tuple(sorted(vals)) for dim, vals in dims.items()}
        for case_id, dims in taxonomies.items()
    }


def candidate_pool(
    index: dict[str, dict[str, list[str]]],
    pr_classification: TaxonomyMap,
) -> tuple[str, ...]:
    """The candidate pool: the union of index lookups for every
    non-``unclassified`` ``(dimension, value)`` pair the PR was classified
    into. A lookup, never a scan — cost is bounded by the matched
    candidate set, not total corpus size."""
    ids: set[str] = set()
    for dim, values in pr_classification.items():
        bucket = index.get(dim, {})
        for value in _non_unclassified(values):
            ids.update(bucket.get(value, ()))
    return tuple(sorted(ids))


def relevance_score(
    case_taxonomy: TaxonomyMap, pr_classification: TaxonomyMap
) -> tuple[int, tuple[str, ...]]:
    """Case Relevance Score: the sum of weights of every dimension where
    the case's declared value(s) and the PR's classified value(s) share at
    least one member. Returns ``(score, matched_dimensions)``."""
    score = 0
    matched: list[str] = []
    for dim, weight in CASE_RELEVANCE_WEIGHTS.items():
        case_values = set(case_taxonomy.get(dim, ()))
        pr_values = set(_non_unclassified(pr_classification.get(dim, ())))
        if case_values & pr_values:
            score += weight
            matched.append(dim)
    return score, tuple(matched)


def relevance_band(score: int) -> str:
    if score >= PRIMARY_BAND_THRESHOLD:
        return BAND_PRIMARY
    if score >= SECONDARY_BAND_THRESHOLD:
        return BAND_SECONDARY
    return BAND_NOT_ELIGIBLE


def implicated_pairs(pr_classification: TaxonomyMap) -> dict[tuple[str, str], float]:
    """The ``(dimension, value)`` pairs the PR's classification implicated,
    each with a weight share: its dimension's weight divided across
    however many non-``unclassified`` values were implicated in that
    dimension. A dimension with no implicated value contributes no pairs
    (it cannot be "covered" if nothing was classified into it) — the sum
    across all returned pairs is 100 only when every dimension has at
    least one implicated value; a wholly-``unclassified`` dimension
    lowers the achievable denominator rather than being silently
    renormalized away."""
    pairs: dict[tuple[str, str], float] = {}
    for dim, weight in CASE_RELEVANCE_WEIGHTS.items():
        values = _non_unclassified(pr_classification.get(dim, ()))
        if not values:
            continue
        share = weight / len(values)
        for value in values:
            pairs[(dim, value)] = pairs.get((dim, value), 0.0) + share
    return pairs


def _covers(case_taxonomy: TaxonomyMap, dim: str, value: str) -> bool:
    return value in case_taxonomy.get(dim, ())


def selection_coverage(
    selected_taxonomies: dict[str, TaxonomyMap],
    pairs: dict[tuple[str, str], float],
) -> tuple[float, tuple[tuple[str, str], ...]]:
    """``Selection Coverage = (sum of covered pairs' weight) / 100`` — a
    pair counts as covered once at least one selected case's taxonomy
    matches it. Returns ``(coverage, uncovered_pairs)``; ``coverage`` is
    already on the 0-100 scale ``implicated_pairs`` weights are expressed
    in, so no further division is needed at the call site."""
    covered_weight = 0.0
    uncovered: list[tuple[str, str]] = []
    for (dim, value), weight in pairs.items():
        if any(_covers(t, dim, value) for t in selected_taxonomies.values()):
            covered_weight += weight
        else:
            uncovered.append((dim, value))
    return covered_weight, tuple(sorted(uncovered))


def select_cases(
    index: dict[str, dict[str, list[str]]],
    pr_classification: TaxonomyMap,
    k: int = K_DEFAULT,
) -> dict[str, Any]:
    """Greedy, coverage-maximizing bounded Top-K selection over the
    eligible (``>= SECONDARY_BAND_THRESHOLD``) candidate pool.

    At each step, picks the remaining eligible case with the largest
    marginal Selection Coverage gain over the pairs still uncovered, ties
    broken by higher relevance score and then, deterministically, by the
    lexicographically first case id. Stops once the Top-K bound is
    reached, ``SELECTION_COVERAGE_THRESHOLD`` is reached, or no further
    eligible case offers a positive marginal gain — whichever comes
    first. Returns a fully JSON-serializable explainability-ready result.
    """
    k = max(1, min(k, K_MAX))
    candidates = candidate_pool(index, pr_classification)
    full_taxonomies = case_taxonomies_from_index(index)

    eligible: dict[str, dict[str, Any]] = {}
    for case_id in candidates:
        case_taxonomy = full_taxonomies.get(case_id, {})
        score, matched = relevance_score(case_taxonomy, pr_classification)
        band = relevance_band(score)
        if band == BAND_NOT_ELIGIBLE:
            continue
        eligible[case_id] = {
            "taxonomy": case_taxonomy,
            "score": score,
            "band": band,
            "matched": matched,
        }

    pairs = implicated_pairs(pr_classification)

    if not pairs:
        # Nothing was implicated to cover (e.g. a PR whose diff classified
        # every dimension as unclassified) — vacuously fully covered, no
        # case selection is required to satisfy the coverage policy.
        return {
            "pr_classification": dict(pr_classification),
            "candidate_pool_size": len(candidates),
            "selected": (),
            "steps": (),
            "selection_coverage": 100.0,
            "coverage_threshold": SELECTION_COVERAGE_THRESHOLD,
            "top_k_bound": k,
            "uncovered_pairs": (),
            "outcome": OUTCOME_SUFFICIENT_COVERAGE,
        }

    selected: list[str] = []
    steps: list[dict[str, Any]] = []
    selected_taxonomies: dict[str, TaxonomyMap] = {}
    covered_pairs: set[tuple[str, str]] = set()

    while len(selected) < k:
        remaining = [cid for cid in eligible if cid not in selected_taxonomies]
        if not remaining:
            break

        best_id: str | None = None
        best_key: tuple[float, int] | None = None
        best_gain = 0.0
        for case_id in sorted(remaining):
            case_taxonomy = eligible[case_id]["taxonomy"]
            gain = sum(
                weight
                for (dim, value), weight in pairs.items()
                if (dim, value) not in covered_pairs and _covers(case_taxonomy, dim, value)
            )
            key = (gain, eligible[case_id]["score"])
            if best_key is None or key > best_key:
                best_key = key
                best_id = case_id
                best_gain = gain

        if best_id is None or best_gain <= 0:
            break

        case_taxonomy = eligible[best_id]["taxonomy"]
        newly_covered = {
            (dim, value)
            for (dim, value) in pairs
            if (dim, value) not in covered_pairs and _covers(case_taxonomy, dim, value)
        }
        covered_pairs |= newly_covered
        selected.append(best_id)
        selected_taxonomies[best_id] = case_taxonomy
        steps.append(
            {
                "case_id": best_id,
                "relevance_score": eligible[best_id]["score"],
                "band": eligible[best_id]["band"],
                "matched_taxonomy_keys": eligible[best_id]["matched"],
                "marginal_coverage_gain": round(best_gain, 4),
            }
        )

        coverage_so_far, _ = selection_coverage(selected_taxonomies, pairs)
        if coverage_so_far >= SELECTION_COVERAGE_THRESHOLD:
            break

    coverage, uncovered = selection_coverage(selected_taxonomies, pairs)
    outcome = (
        OUTCOME_SUFFICIENT_COVERAGE
        if coverage >= SELECTION_COVERAGE_THRESHOLD
        else OUTCOME_INSUFFICIENT_COVERAGE
    )

    return {
        "pr_classification": dict(pr_classification),
        "candidate_pool_size": len(candidates),
        "selected": tuple(selected),
        "steps": tuple(steps),
        "selection_coverage": round(coverage, 4),
        "coverage_threshold": SELECTION_COVERAGE_THRESHOLD,
        "top_k_bound": k,
        "uncovered_pairs": uncovered,
        "outcome": outcome,
    }


def build_explainability(result: dict[str, Any]) -> dict[str, Any]:
    """Render :func:`select_cases`'s result into the one machine-readable
    JSON object per run described by runtime_platform/benchmark/selection.md §5 —
    resolved taxonomy classification, candidate-pool size, each selected
    case's id/score/band/matched keys/marginal gain at the moment picked,
    final aggregate Selection Coverage, the configured threshold/Top-K
    bound, and the outcome. A thin, explicit key rename/ordering pass over
    an already fully-serializable result — never a second computation."""
    return {
        "resolved_taxonomy_classification": result["pr_classification"],
        "candidate_pool_size": result["candidate_pool_size"],
        "selected_cases": [
            {
                "case_id": step["case_id"],
                "relevance_score": step["relevance_score"],
                "band": step["band"],
                "matched_taxonomy_keys": list(step["matched_taxonomy_keys"]),
                "marginal_coverage_gain": step["marginal_coverage_gain"],
            }
            for step in result["steps"]
        ],
        "selection_coverage": result["selection_coverage"],
        "coverage_threshold": result["coverage_threshold"],
        "top_k_bound": result["top_k_bound"],
        "uncovered_pairs": [list(pair) for pair in result["uncovered_pairs"]],
        "outcome": result["outcome"],
    }
