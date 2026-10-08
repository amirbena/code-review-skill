#!/usr/bin/env python3
"""Test-only reduction of workspace-sibling-context measurement runs (Issue #664).

Contract: runtime_platform/benchmark/workspace-sibling-context-measurement.md.
Turns live runs of the ``workspace-sibling-context`` sub-corpus, with the
workspace grant handed to the reviewer (``on``) and withheld (``off``), into
one gate outcome per review adapter. Pairing is the #55 matcher; nothing here
changes a baseline, a matcher, or a Skill rule. Not runtime logic, not packaged.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_metrics as bmx
from runtime_platform.benchmark.reference import benchmark_runner as br

RECORD_FORMAT = "workspace-sibling-context-measurement/v1"

LOCAL = "local"
GITHUB = "github"
ADAPTERS = (LOCAL, GITHUB)

# Case roles. The id prefix is the only adapter-scope marker: `wsib-gh-` cases
# run through the github adapter only; every other case is shared and runs once
# per adapter.
RESOLVING = "resolving"
ESCALATION = "escalation"
ABSENCE = "absence"
POLLUTION = "pollution"
PUBLISHED = "published"

CASE_ROLES: Mapping[str, str] = {
    "wsib-resolves-from-relevant-sibling": RESOLVING,
    "wsib-no-relevant-sibling-fallback": ESCALATION,
    "wsib-ambiguous-siblings-no-overreach": ESCALATION,
    "wsib-insufficient-evidence-question-preserved": ESCALATION,
    "wsib-absence-in-inspected-sibling-no-claim": ABSENCE,
    "wsib-unrelated-sibling-no-pollution": POLLUTION,
    "wsib-gh-pr-repository-excluded-by-identity": ESCALATION,
    "wsib-gh-api-only-grant-unavailable": ESCALATION,
    "wsib-gh-published-output-reference-only": PUBLISHED,
}
GITHUB_ONLY_PREFIX = "wsib-gh-"

# The question every escalation case leaves open is about this enum member.
ESCALATION_SUBJECT = "refunded"
# The marker planted in the sibling of the published-output case.
LEAK_MARKER = "LDGR-CANARY-7f3a91c2"
# Phrases that assert absence from a sibling that cannot support it.
ABSENCE_CLAIM_RE = re.compile(
    r"\b(no (other |known |downstream |existing )?(consumers?|subscribers?|dependents?|callers?|readers?|users?)|"
    r"nothing (else )?(consumes|depends|subscribes|reads|uses|relies)|"
    r"(not|never) (consumed|used|read|subscribed to|depended on) by (any|anything|anyone)|"
    r"(is|are) (dead|unused|unconsumed|orphaned)|"
    r"(safe|harmless) to (add|ship|remove)|"
    r"(does|do) not (have|has) any (consumers?|subscribers?|dependents?))\b",
    re.IGNORECASE,
)

# A sentence naming a repository at a revision (repo@sha) states what was
# searched, which the policy allows; it is not an absence claim.
SCOPE_MARKER_RE = re.compile(r"@[0-9a-f]{6,40}\b", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def has_absence_claim(report: str) -> bool:
    """True when a sentence matches an absence phrase and is not scoped to a
    repository at a revision."""
    return any(
        ABSENCE_CLAIM_RE.search(sentence) and not SCOPE_MARKER_RE.search(sentence)
        for sentence in _SENTENCE_SPLIT_RE.split(report)
    )


# --- Pre-registered gate (committed before the first measured run) ---------
MIN_RUNS_PER_ARM = 2
RESOLUTION_MIN_ON_RATE = 2 / 3  # share of on-runs of a resolving case that find the required finding
MAX_WRONG_GROWTH = 0  # on-arm wrong findings may exceed the off-arm total by this much
MAX_WALL_TIME_RATIO = 2.0  # median on-arm run time over median off-arm run time
MAX_TOKEN_RATIO = 2.0  # same, where the adapter reports tokens

PASS = "pass"
FAIL = "fail"
NOT_EVALUATED = "not-evaluated"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def applies_to(case_id: str, adapter: str) -> bool:
    return adapter == GITHUB or not case_id.startswith(GITHUB_ONLY_PREFIX)


def escalation_sections(report: str) -> str:
    """Text under every Context gaps / Reasoning check heading of a report."""
    lines = report.splitlines()
    kept: list[str] = []
    level = 0
    for line in lines:
        match = _HEADING_RE.match(line)
        if match:
            title = match.group(2).lower()
            if level and len(match.group(1)) <= level:
                level = 0
            if "context gaps" in title or "reasoning check" in title:
                level = len(match.group(1))
                continue
        if level:
            kept.append(line)
    return "\n".join(kept)


@dataclass(frozen=True)
class RunObservation:
    case_id: str
    arm: str  # "on" | "off"
    status: str  # "executed" | "error"
    error: str | None = None
    required: int = 0
    found: int = 0
    wrong: int = 0
    escalated: bool = False
    absence_claim: bool = False
    leaked: bool = False
    seconds: float | None = None
    tokens: int | None = None

    @property
    def executed(self) -> bool:
        return self.status == "executed"

    @property
    def missed(self) -> int:
        return self.required - self.found

    def as_dict(self) -> dict[str, Any]:
        if not self.executed:
            return {"arm": self.arm, "status": self.status, "error": self.error}
        return {
            "arm": self.arm,
            "status": self.status,
            "required": self.required,
            "found": self.found,
            "missed": self.missed,
            "wrong": self.wrong,
            "escalated": self.escalated,
            "absence_claim": self.absence_claim,
            "leaked": self.leaked,
            "seconds": self.seconds,
            "tokens": self.tokens,
        }


def observe_run(
    case: bf.BenchmarkCase,
    result: br.CaseResult,
    report: str | None,
    *,
    arm: str,
    seconds: float | None = None,
    tokens: int | None = None,
) -> RunObservation:
    """Reduce one run. `wrong` is every produced finding no expected entry
    consumed (#55), which includes any finding where none is expected."""
    if result.status != "executed" or report is None:
        return RunObservation(case.id, arm, "error", error=result.error or "no-report")
    produced = result.produced_findings
    pairing = bmx.resolve_pairing(case, produced, post_image=result.post_image)
    required_keys = {e.key for e in case.findings if e.required}
    return RunObservation(
        case.id,
        arm,
        "executed",
        required=len(required_keys),
        found=len(required_keys & set(pairing.paired)),
        wrong=len(pairing.unconsumed_indices),
        escalated=ESCALATION_SUBJECT in escalation_sections(report).lower(),
        absence_claim=has_absence_claim(report),
        leaked=LEAK_MARKER in report,
        seconds=seconds,
        tokens=tokens,
    )


def _executed(runs: Iterable[RunObservation], arm: str, roles: Sequence[str]) -> list[RunObservation]:
    return [r for r in runs if r.arm == arm and r.executed and CASE_ROLES.get(r.case_id) in roles]


def _rate(values: Sequence[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def _ratio(on: Sequence[float], off: Sequence[float]) -> float | None:
    if not on or not off or statistics.median(off) <= 0:
        return None
    return statistics.median(on) / statistics.median(off)


def _per_case_enough(runs: Sequence[RunObservation], case_ids: Iterable[str]) -> bool:
    return all(
        sum(1 for r in runs if r.case_id == cid and r.arm == arm and r.executed) >= MIN_RUNS_PER_ARM
        for cid in case_ids
        for arm in ("on", "off")
    )


def evaluate_adapter(runs: Sequence[RunObservation], case_ids: Sequence[str]) -> dict[str, Any]:
    """The pre-registered gate for one adapter. Criteria that cannot be
    evaluated say so; the overall outcome is `pass` only when every criterion
    passes and none is `not-evaluated` except cost telemetry the adapter does
    not report."""
    criteria: dict[str, dict[str, Any]] = {}
    if not _per_case_enough(runs, case_ids):
        return {
            "outcome": NOT_EVALUATED,
            "reason": f"a case has fewer than {MIN_RUNS_PER_ARM} executed runs in an arm",
            "criteria": criteria,
        }

    resolving = [c for c in case_ids if CASE_ROLES.get(c) == RESOLVING]
    on_rate = _rate([r.found == r.required for r in _executed(runs, "on", (RESOLVING,))])
    off_rate = _rate([r.found == r.required for r in _executed(runs, "off", (RESOLVING,))])
    criteria["quality_gain"] = {
        "status": PASS if resolving and on_rate is not None and off_rate is not None
        and on_rate >= RESOLUTION_MIN_ON_RATE and on_rate > off_rate else FAIL,
        "on_rate": on_rate,
        "off_rate": off_rate,
    }

    guarded = (ESCALATION, ABSENCE, POLLUTION)
    on_wrong = sum(r.wrong for r in _executed(runs, "on", guarded))
    off_wrong = sum(r.wrong for r in _executed(runs, "off", guarded))
    criteria["false_positive_growth"] = {
        "status": PASS if on_wrong <= off_wrong + MAX_WRONG_GROWTH else FAIL,
        "on_wrong": on_wrong,
        "off_wrong": off_wrong,
    }

    on_esc = _rate([r.escalated for r in _executed(runs, "on", (ESCALATION,))])
    off_esc = _rate([r.escalated for r in _executed(runs, "off", (ESCALATION,))])
    criteria["preserved_escalation"] = {
        "status": PASS if on_esc is not None and off_esc is not None and on_esc >= off_esc else FAIL,
        "on_rate": on_esc,
        "off_rate": off_esc,
    }

    absence = sum(r.absence_claim for r in _executed(runs, "on", (ABSENCE,)))
    criteria["no_absence_claim"] = {"status": PASS if absence == 0 else FAIL, "on_runs_with_claim": absence}

    published = [c for c in case_ids if CASE_ROLES.get(c) == PUBLISHED]
    if published:
        leaks = sum(r.leaked for r in _executed(runs, "on", (PUBLISHED,)))
        criteria["no_published_sibling_content"] = {"status": PASS if leaks == 0 else FAIL, "on_runs_leaking": leaks}

    on_all = _executed(runs, "on", tuple(CASE_ROLES.values()))
    off_all = _executed(runs, "off", tuple(CASE_ROLES.values()))
    time_ratio = _ratio([r.seconds for r in on_all if r.seconds], [r.seconds for r in off_all if r.seconds])
    token_ratio = _ratio([r.tokens for r in on_all if r.tokens], [r.tokens for r in off_all if r.tokens])
    criteria["acceptable_cost"] = {
        "status": FAIL
        if (time_ratio is not None and time_ratio > MAX_WALL_TIME_RATIO)
        or (token_ratio is not None and token_ratio > MAX_TOKEN_RATIO)
        else (PASS if time_ratio is not None else NOT_EVALUATED),
        "wall_time_ratio": time_ratio,
        "token_ratio": token_ratio,
        "tokens_reported": token_ratio is not None,
    }

    failed = sorted(k for k, v in criteria.items() if v["status"] == FAIL)
    unevaluated = sorted(k for k, v in criteria.items() if v["status"] == NOT_EVALUATED)
    outcome = FAIL if failed else (PASS if not unevaluated else NOT_EVALUATED)
    return {"outcome": outcome, "failed": failed, "not_evaluated": unevaluated, "criteria": criteria}


def measurement_record(
    adapters: Mapping[str, Sequence[RunObservation] | None],
    case_ids: Mapping[str, Sequence[str]],
    *,
    runs_per_arm: int,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """One record. A skipped adapter is `not-run`; outcomes are never merged."""
    record_adapters: dict[str, Any] = {}
    for adapter in ADAPTERS:
        runs = adapters.get(adapter)
        if runs is None:
            record_adapters[adapter] = {"outcome": "not-run", "runs": []}
            continue
        record_adapters[adapter] = {
            **evaluate_adapter(runs, case_ids[adapter]),
            "runs": [r.as_dict() | {"case_id": r.case_id} for r in runs],
        }
    return {
        "format": RECORD_FORMAT,
        "runs_per_arm": runs_per_arm,
        "metadata": dict(metadata),
        "adapters": record_adapters,
        "summary": {a: record_adapters[a]["outcome"] for a in ADAPTERS},
    }
