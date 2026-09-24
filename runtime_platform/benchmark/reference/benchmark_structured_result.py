#!/usr/bin/env python3
"""Test-only measurement of runtime-only structured-result properties (Issue #529).

Contract: runtime_platform/benchmark/structured-result-runtime-properties.md.
Turns live `local-code-review` runs of one fixture, with the
`structured_review_result` option on and off, into two verdicts: whether a
matched finding keeps its `identity.stable_id` across on-runs, and whether
the option changes the review. Pairing is the #55 matcher, report <-> result
agreement is the #71 comparator, the decision is the #350 label classifier.
Not runtime logic, not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from runtime_platform.benchmark.reference import benchmark_blocking_verdict as bbv
from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_metrics as bmx
from runtime_platform.benchmark.reference import benchmark_runner as br
from tests.reference.review import structured_output_contract as soc

RECORD_FORMAT = "structured-result-runtime-properties/v1"

# The illustrative value in shared/policies/structured-output.md "Example";
# a run that emits it copied the example instead of computing a digest.
POLICY_EXAMPLE_STABLE_ID = "fid_v1_2c7a0d6b2c80a885a1752c05f15d70c0"

# Per-component verdicts, ordered by how much they demand attention.
CONSISTENT = "consistent"
INCONCLUSIVE = "inconclusive"
DIVERGENT = "divergent"
NOT_EVALUATED = "not-evaluated"
_VERDICT_RANK = {NOT_EVALUATED: 0, CONSISTENT: 1, INCONCLUSIVE: 2, DIVERGENT: 3}

STABLE = "stable"
UNSTABLE = "unstable"
INSUFFICIENT = "insufficient-runs"

COMPONENTS = ("decision", "finding_set", "severities", "unpaired")

# Executed runs an arm needs before an invariance verdict other than inconclusive.
MIN_RUNS_PER_ARM = 2


@dataclass(frozen=True)
class RunObservation:
    """One live run of one case, reduced to what the two properties compare."""

    case_id: str
    structured: bool
    status: str  # "executed" | "error"
    error: str | None = None
    decision: str | None = None
    # (expected entry key, produced severity), fixture order.
    paired: tuple[tuple[str, str], ...] = ()
    # Severities of produced findings no expected entry consumed, sorted.
    unpaired: tuple[str, ...] = ()
    contract_errors: tuple[str, ...] = ()
    # Paired entry key -> stable_id; on-runs with an agreeing result only.
    stable_ids: Mapping[str, str] = field(default_factory=dict)
    # Every stable_id the result carried, in finding order.
    all_stable_ids: tuple[str, ...] = ()
    # Paired entry key -> the produced claim, to tell wording drift from fabrication.
    claims: Mapping[str, str] = field(default_factory=dict)

    @property
    def executed(self) -> bool:
        return self.status == "executed"

    def component(self, name: str) -> Any:
        if name == "decision":
            return self.decision
        if name == "finding_set":
            return tuple(sorted(key for key, _ in self.paired))
        if name == "severities":
            return tuple(sorted(self.paired))
        return self.unpaired

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"structured": self.structured, "status": self.status}
        if not self.executed:
            out["error"] = self.error
            return out
        out.update(
            decision=self.decision,
            paired=[list(pair) for pair in self.paired],
            unpaired=list(self.unpaired),
        )
        if self.structured:
            out["contract_errors"] = list(self.contract_errors)
            out["stable_ids"] = dict(sorted(self.stable_ids.items()))
            out["claims"] = dict(sorted(self.claims.items()))
        return out


def observe_run(
    case: bf.BenchmarkCase, result: br.CaseResult, report: str | None, *, structured: bool
) -> RunObservation:
    """Reduce one executed (or failed) run; `report` is the adapter's raw stdout."""
    if result.status != "executed" or report is None:
        return RunObservation(case.id, structured, "error", error=result.error or "no-report")
    produced = result.produced_findings
    pairing = bmx.resolve_pairing(case, produced, post_image=result.post_image)
    decision = bbv.classify_rendered_label(
        soc.parse_human_report(report, soc.LOCAL).decision_label
    ).value
    base = dict(
        case_id=case.id,
        structured=structured,
        status="executed",
        decision=decision,
        paired=tuple((key, produced[i].severity) for key, i in pairing.paired.items()),
        unpaired=tuple(sorted(produced[i].severity for i in pairing.unconsumed_indices)),
    )
    if not structured:
        return RunObservation(**base)

    # The workspace target is always uncommitted (the runner applies the patch
    # without committing), so the result's reviewed head must be null.
    errors = soc.contract_errors(report, soc.LOCAL, known_head=None, target_committed=False)
    try:
        emitted = soc.split_output(report, soc.LOCAL).result
    except soc.ContractError:
        emitted = None
    findings = emitted.get("findings", []) if isinstance(emitted, dict) else []
    ids = tuple(
        f["identity"]["stable_id"]
        for f in findings
        if isinstance(f, dict) and isinstance(f.get("identity"), dict) and "stable_id" in f["identity"]
    )
    stable_ids: dict[str, str] = {}
    # Index i of the parsed report is finding i of the result only when #71
    # agreement holds and the parser kept every finding.
    if not errors and len(findings) == len(produced) == len(ids):
        stable_ids = {key: ids[i] for key, i in pairing.paired.items()}
    elif not errors:
        errors = (f"report parser kept {len(produced)} of {len(findings)} findings; stable ids not attributed",)
    claims = {key: produced[i].claim or "" for key, i in pairing.paired.items()}
    return RunObservation(
        **base, contract_errors=tuple(errors), stable_ids=stable_ids, all_stable_ids=ids, claims=claims
    )


def stable_id_stability(on_runs: Sequence[RunObservation]) -> dict[str, Any]:
    """Per matched expected entry: one distinct stable_id across >= 2 on-runs is stable.

    Flags number runs by position in `on_runs`, the same order the record lists them.
    """
    runs = [(index, r) for index, r in enumerate(on_runs) if r.executed]
    per_entry: dict[str, list[str]] = {}
    for _, run in runs:
        for key, stable_id in run.stable_ids.items():
            per_entry.setdefault(key, []).append(stable_id)
    entries = {}
    for key, ids in sorted(per_entry.items()):
        distinct = sorted(set(ids))
        status = INSUFFICIENT if len(ids) < 2 else (STABLE if len(distinct) == 1 else UNSTABLE)
        entries[key] = {"status": status, "runs": len(ids), "stable_ids": distinct}

    flags: list[str] = []
    for key, entry in entries.items():
        if entry["status"] == UNSTABLE:
            flags.append(f"unstable: {key} carried {len(entry['stable_ids'])} stable_ids over {entry['runs']} runs")
    for index, run in runs:
        if POLICY_EXAMPLE_STABLE_ID in run.all_stable_ids:
            flags.append(f"example-copy: run {index} emitted the policy's illustrative stable_id")
        owners: dict[str, set[str]] = {}
        for key, stable_id in run.stable_ids.items():
            owners.setdefault(stable_id, set()).add(key)
        for stable_id, keys in sorted(owners.items()):
            if len(keys) > 1:
                flags.append(f"collision: run {index} gave {stable_id} to distinct entries {sorted(keys)}")
    return {"entries": entries, "flags": flags}


def _classify(on_values: set, off_values: set, runs_per_arm: int) -> str:
    if runs_per_arm < MIN_RUNS_PER_ARM:
        return NOT_EVALUATED if not on_values or not off_values else INCONCLUSIVE
    if on_values == off_values:
        return CONSISTENT
    if on_values.isdisjoint(off_values) and len(on_values) == len(off_values) == 1:
        return DIVERGENT
    return INCONCLUSIVE


def option_invariance(on_runs: Sequence[RunObservation], off_runs: Sequence[RunObservation]) -> dict[str, Any]:
    """Compare each component's observed values across the two arms.

    Equal value sets are consistent. Each arm repeating one value, and the two
    values differing, is divergent: the option changed the review. Either needs
    at least two executed runs in each arm. Anything else is variance the run
    count cannot separate from an option effect, so it is inconclusive, never a
    pass.
    """
    on = [r for r in on_runs if r.executed]
    off = [r for r in off_runs if r.executed]
    runs_per_arm = min(len(on), len(off))
    components = {}
    for name in COMPONENTS:
        on_values = {r.component(name) for r in on}
        off_values = {r.component(name) for r in off}
        components[name] = {
            "verdict": _classify(on_values, off_values, runs_per_arm),
            "on": sorted(map(_jsonable, on_values), key=repr),
            "off": sorted(map(_jsonable, off_values), key=repr),
        }
    verdict = max((c["verdict"] for c in components.values()), key=_VERDICT_RANK.__getitem__)
    return {"verdict": verdict, "components": components}


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    return value


def case_record(case_id: str, observations: Iterable[RunObservation]) -> dict[str, Any]:
    runs = list(observations)
    on = [r for r in runs if r.structured]
    off = [r for r in runs if not r.structured]
    contract = [
        f"run {i}: {error}" for i, r in enumerate(on) if r.executed for error in r.contract_errors
    ]
    return {
        "case_id": case_id,
        "runs": {"on": [r.as_dict() for r in on], "off": [r.as_dict() for r in off]},
        "errored_runs": {"on": sum(not r.executed for r in on), "off": sum(not r.executed for r in off)},
        "contract_errors": contract,
        "stable_id": stable_id_stability(on),
        "invariance": option_invariance(on, off),
    }


def measurement_record(
    cases: Sequence[dict[str, Any]], *, runs_per_arm: int, metadata: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """The recorded result: per-case sections plus the flags a reader checks first."""
    return {
        "format": RECORD_FORMAT,
        "runs_per_arm": runs_per_arm,
        "metadata": dict(metadata or {}),
        "cases": list(cases),
        "summary": {
            "stable_id_flags": [f"{c['case_id']}: {flag}" for c in cases for flag in c["stable_id"]["flags"]],
            "option_dependent": [c["case_id"] for c in cases if c["invariance"]["verdict"] == DIVERGENT],
            "inconclusive": [c["case_id"] for c in cases if c["invariance"]["verdict"] == INCONCLUSIVE],
            "not_evaluated": [c["case_id"] for c in cases if c["invariance"]["verdict"] == NOT_EVALUATED],
            "contract_errors": [f"{c['case_id']}: {e}" for c in cases for e in c["contract_errors"]],
        },
    }
