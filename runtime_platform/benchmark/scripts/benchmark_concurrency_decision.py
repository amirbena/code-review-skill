"""TEMPORARY campaign configuration validation and decision evaluation (Issues #681, #682).

`validate_spec` refuses a spec whose schedule, pin or thresholds are inconsistent before any fixture
runs. `evaluate_campaign` turns the sealed experiment records into GO / NO-GO / INCONCLUSIVE against the
thresholds committed in the spec. Neither touches a lane, baseline or the network. Contract:
`runtime_platform/benchmark/concurrency-campaign.md`.
"""

from __future__ import annotations

import re
import statistics
from datetime import date
from itertools import combinations
from typing import Any, Mapping

SHA_RE = re.compile(r"[0-9a-f]{40}")
PROVENANCE_KEYS = ("repo_sha", "model_id", "runtime_version", "subset_id", "corpus_id")
MAX_WINDOW_FRACTION = 0.6
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class SpecError(ValueError):
    """The campaign spec is inconsistent; a run must not start."""


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SpecError(message)


def validate_thresholds(decision: Mapping[str, Any], allowed_workers: list[int]) -> None:
    gates = decision.get("hard_safety_gates", {})
    perf = decision.get("performance_thresholds", {})
    window = decision.get("window", {})
    _require(gates.get("max_isolation_violations") == 0, "hard gate max_isolation_violations must be exactly 0")
    _require(gates.get("min_valid_result_rate") == 1.0, "hard gate min_valid_result_rate must be exactly 1.0")
    keys = gates.get("provenance_must_match_across_experiments")
    _require(isinstance(keys, list) and keys and set(keys) <= set(PROVENANCE_KEYS), f"provenance keys must be a non-empty subset of {PROVENANCE_KEYS}")
    efficiency = perf.get("min_scaling_efficiency")
    expected = {str(w) for w in allowed_workers if w > 1}
    _require(isinstance(efficiency, dict) and set(efficiency) == expected, f"min_scaling_efficiency needs exactly the keys {sorted(expected)}")
    _require(all(_number(v) and 0 < v <= 1 for v in efficiency.values()), "min_scaling_efficiency values must be in (0, 1]")
    _require(_number(perf.get("no_meaningful_speedup_below")) and perf["no_meaningful_speedup_below"] > 1, "no_meaningful_speedup_below must be > 1")
    _require(_number(perf.get("max_same_config_wall_cv")) and 0 < perf["max_same_config_wall_cv"] <= 1, "max_same_config_wall_cv must be in (0, 1]")
    _require(_number(perf.get("max_outcome_disagreement_excess")) and 0 <= perf["max_outcome_disagreement_excess"] <= 1, "max_outcome_disagreement_excess must be in [0, 1]")
    _require(_number(perf.get("max_rate_limited_fixture_fraction")) and 0 <= perf["max_rate_limited_fixture_fraction"] <= 1, "max_rate_limited_fixture_fraction must be in [0, 1]")
    fraction = window.get("max_fraction_of_window")
    _require(_number(fraction) and 0 < fraction <= MAX_WINDOW_FRACTION, f"max_fraction_of_window must be in (0, {MAX_WINDOW_FRACTION}]")
    evidenced = window.get("evidenced_window_s")
    _require(evidenced is None or (_number(evidenced) and evidenced > 0), "evidenced_window_s must be null or a positive number of seconds")
    confirmations = window.get("worst_case_confirmation_invocations")
    _require(isinstance(confirmations, int) and not isinstance(confirmations, bool) and confirmations >= 0, "worst_case_confirmation_invocations must be a non-negative integer")
    diagnostics = decision.get("diagnostic_indicators")
    _require(isinstance(diagnostics, list) and all(isinstance(d, str) and d for d in diagnostics), "diagnostic_indicators must be a list of names")


def validate_campaign(spec: Mapping[str, Any]) -> None:
    """Dates, weekdays, arms, counterbalancing and window_end must agree; an inactive spec (no dates, no window) is allowed."""
    stop = spec["stop_condition"]
    experiments, end = stop.get("experiments") or [], stop.get("window_end")
    if not experiments and end is None:
        return
    _require(experiments and end is not None, "experiments and window_end must be set together")
    _require(len(experiments) == stop["max_experiments"], f"exactly {stop['max_experiments']} experiments must be listed")
    allowed, weekdays = spec["allowed_workers"], spec["intended_start"]["weekdays"]
    dates = [e.get("date") for e in experiments]
    try:
        parsed = [date.fromisoformat(d) for d in dates]
    except (TypeError, ValueError) as exc:
        raise SpecError(f"experiment dates must be ISO dates: {dates}") from exc
    _require(parsed == sorted(set(parsed)), "experiment dates must be unique and ascending")
    _require(all(WEEKDAYS[d.weekday()] in weekdays for d in parsed), f"every experiment date must fall on {weekdays}")
    _require(end == dates[-1], f"window_end {end} must equal the last experiment date {dates[-1]}")
    for entry in experiments:
        arms = entry.get("arms")
        _require(isinstance(arms, list) and len(arms) == len(set(arms)) >= 2, f"{entry.get('date')}: arms must be at least two distinct worker counts")
        _require(all(a in allowed for a in arms), f"{entry.get('date')}: arms {arms} must all be in {allowed}")
    if len(experiments) == 4:
        arms = [e["arms"] for e in experiments]
        _require(arms[2] == arms[0][::-1] and arms[3] == arms[1][::-1], "second-week arm order must reverse the first week's")


def validate_pin(pin: Mapping[str, Any]) -> None:
    _require(pin.get("mechanism") == "cli-expected-sha" and pin.get("flag") == "--pinned-sha", "pin must use the cli-expected-sha mechanism")


def validate_subset(subset: Mapping[str, Any]) -> None:
    strata = subset.get("strata")
    if not strata:
        return
    listed = [c for ids in strata.values() for c in ids]
    _require(all(strata.values()), "every stratum needs at least one fixture")
    _require(len(listed) == len(set(listed)), "a fixture may belong to only one stratum")
    _require(subset.get("case_ids") == sorted(listed), "case_ids must be the sorted union of the strata")
    _require(subset.get("size") == len(listed), f"size {subset.get('size')} must equal the {len(listed)} listed fixtures")
    identity = subset.get("subset_id")
    _require(identity is None or re.fullmatch(r"[0-9a-f]{64}", identity) is not None, "subset_id must be a sha256 hex digest")


def validate_spec(spec: Mapping[str, Any]) -> None:
    validate_subset(spec.get("subset", {}))
    validate_pin(spec.get("pin", {}))
    validate_thresholds(spec.get("decision", {}), spec["allowed_workers"])
    validate_campaign(spec)


def check_pinned_sha(expected: str | None, actual: str, clean: bool) -> None:
    _require(expected is not None and SHA_RE.fullmatch(expected) is not None, "a scheduled run needs --pinned-sha as a full 40-character lowercase hex commit")
    _require(actual == expected, f"checkout {actual[:12]} does not match the pinned source {expected[:12]}")
    _require(clean, "the checkout has uncommitted changes; the pinned source must be exact")


def _check(check_id: str, klass: str, passed: bool | None, observed: Any, threshold: Any, workers: int | None = None) -> dict[str, Any]:
    return {"id": check_id, "class": klass, "passed": passed, "observed": observed, "threshold": threshold, "workers": workers}


def _arms(experiments: list[Mapping[str, Any]]) -> list[tuple[int, Mapping[str, Any]]]:
    return [(i, arm) for i, e in enumerate(experiments) for arm in e["arms"]]


def _counts(arm: Mapping[str, Any]) -> dict[str, Any]:
    return {f["case_id"]: f.get("produced_finding_count") for f in arm["fixtures"]}


def _disagreement(a: Mapping[str, Any], b: Mapping[str, Any]) -> float | None:
    left, right = _counts(a), _counts(b)
    if set(left) != set(right) or not left or None in left.values() or None in right.values():
        return None
    return sum(1 for c in left if left[c] != right[c]) / len(left)


def _provenance(experiment: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "repo_sha": experiment["provenance"]["repo_sha"],
        "model_id": experiment["runtime"]["model_id"],
        "runtime_version": experiment["runtime"]["runtime_version"],
        "subset_id": experiment["manifest"]["subset_id"],
        "corpus_id": experiment["manifest"]["corpus_id"],
    }


def evaluate_campaign(
    experiments: list[Mapping[str, Any]], decision: Mapping[str, Any], *, corpus_size: int, pinned_sha: str | None, max_experiments: int = 4
) -> dict[str, Any]:
    gates, perf, window = decision["hard_safety_gates"], decision["performance_thresholds"], decision["window"]
    if not experiments:
        return {"decision": "INCONCLUSIVE", "checks": [], "eligible_worker_counts": [], "reason": "no experiment has run"}
    arms = _arms(experiments)
    checks: list[dict[str, Any]] = []

    violations = sum(len(e["isolation"]["violations"]) for e in experiments)
    checks.append(_check("isolation", "hard", violations <= gates["max_isolation_violations"], violations, gates["max_isolation_violations"]))
    planned = sum(a["planned"] for _, a in arms)
    valid_rate = sum(a["completed"] for _, a in arms) / planned if planned else 0.0
    checks.append(_check("valid-results", "hard", valid_rate >= gates["min_valid_result_rate"], round(valid_rate, 4), gates["min_valid_result_rate"]))
    drift = [k for k in gates["provenance_must_match_across_experiments"] if len({str(_provenance(e)[k]) for e in experiments}) > 1]
    pin_ok = pinned_sha is None or all(_provenance(e)["repo_sha"] == pinned_sha for e in experiments)
    checks.append(_check("provenance", "hard", not drift and pin_ok, {"differs": drift, "pin_matches": pin_ok}, gates["provenance_must_match_across_experiments"]))

    unfinished = [i for i, e in enumerate(experiments) if e.get("status") != "complete" or len(e["arms"]) != len(e.get("planned_arms", []))]
    checks.append(_check("experiments-complete", "hard", not unfinished, unfinished, []))
    checks.append(_check("coverage", "coverage", len(experiments) == max_experiments, len(experiments), max_experiments))

    pairs: dict[int, list[tuple[float, float]]] = {}
    for e in experiments:
        by_workers = {a["workers"]: a["wall_s"] for a in e["arms"]}
        for low, high in combinations(sorted(by_workers), 2):
            if by_workers[high] > 0:
                speedup = by_workers[low] / by_workers[high]
                pairs.setdefault(high, []).append((speedup, speedup / (high / low)))
    best_speedup = max((s for runs in pairs.values() for s, _ in runs), default=None)
    floor = perf["no_meaningful_speedup_below"]
    checks.append(_check("meaningful-speedup", "performance", None if best_speedup is None else best_speedup >= floor, best_speedup, floor))
    eligible = {}
    for high, runs in sorted(pairs.items()):
        needed = perf["min_scaling_efficiency"][str(high)]
        mean = statistics.fmean(eff for _, eff in runs)
        checks.append(_check(f"efficiency-{high}-workers", "performance", mean >= needed, round(mean, 4), needed, high))
        eligible[high] = mean >= needed

    two = [a["wall_s"] for _, a in arms if a["workers"] == 2]
    cv = statistics.pstdev(two) / statistics.fmean(two) if len(two) >= 2 and statistics.fmean(two) > 0 else None
    checks.append(_check("same-config-wall-cv", "performance", None if cv is None else cv <= perf["max_same_config_wall_cv"], cv, perf["max_same_config_wall_cv"]))

    two_arms = [a for _, a in arms if a["workers"] == 2]
    baseline = [d for x, y in combinations(two_arms, 2) if (d := _disagreement(x, y)) is not None]
    cross = [d for e in experiments for x, y in combinations(e["arms"], 2) if x["workers"] != y["workers"] and (d := _disagreement(x, y)) is not None]
    excess = None if not baseline or not cross else max(0.0, max(cross) - max(baseline))
    limit = perf["max_outcome_disagreement_excess"]
    checks.append(_check("outcome-disagreement-excess", "performance", None if excess is None else excess <= limit, excess, limit))

    for high in sorted(pairs):
        multi = [a for _, a in arms if a["workers"] == high]
        throttled = max((sum(1 for f in a["fixtures"] if f["rate_limit_hits"]) / max(a["attempted"], 1) for a in multi), default=0.0)
        ok = throttled <= perf["max_rate_limited_fixture_fraction"]
        checks.append(_check(f"rate-limited-fixtures-{high}-workers", "performance", ok, round(throttled, 4), perf["max_rate_limited_fixture_fraction"], high))
        eligible[high] = eligible.get(high, False) and ok

    evidenced = window["evidenced_window_s"]
    invocations = corpus_size + window["worst_case_confirmation_invocations"]
    for high in sorted(pairs):
        per_fixture = statistics.fmean(a["wall_s"] / a["planned"] for _, a in arms if a["workers"] == high and a["planned"])
        projected = round(per_fixture * invocations, 1)
        budget = None if evidenced is None else evidenced * window["max_fraction_of_window"]
        passed = None if budget is None else projected <= budget
        checks.append(_check(f"projected-full-corpus-{high}-workers", "window", passed, projected, budget, high))
        eligible[high] = eligible.get(high, False) and passed is True

    campaign_wide = [c for c in checks if c["workers"] is None]
    hard_failed = any(c["class"] == "hard" and c["passed"] is False for c in checks)
    no_speedup = best_speedup is not None and best_speedup < floor
    if hard_failed or no_speedup:
        verdict = "NO-GO"
    elif all(c["passed"] is True for c in campaign_wide) and any(eligible.values()):
        verdict = "GO"
    else:
        verdict = "INCONCLUSIVE"
    return {
        "decision": verdict,
        "checks": checks,
        "eligible_worker_counts": sorted(w for w, ok in eligible.items() if ok),
        "projection_basis": f"per-fixture wall mean of the measured subset, extrapolated to {invocations} invocations",
        "projection_is_not_a_seal": "a projection is not a sealed Comprehensive run; GO only authorizes a separate production issue",
    }
