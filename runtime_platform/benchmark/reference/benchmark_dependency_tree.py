#!/usr/bin/env python3
"""Test-only reduction of dependency-tree-inspection measurement runs (Issue #732).

Contract: runtime_platform/benchmark/dependency-tree-inspection-measurement.md.
Turns live runs of the ``dependency-tree-inspection`` sub-corpus, under a
baseline arm (the skill before #730) and a candidate arm (the skill with #730),
into one disposition per review adapter. Pairing is the #55 matcher; nothing
here changes a baseline, a matcher, or a Skill rule. Not runtime logic, not packaged.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_metrics as bmx
from runtime_platform.benchmark.reference import benchmark_runner as br
from runtime_platform.benchmark.reference.benchmark_workspace_sibling import escalation_sections

RECORD_FORMAT = "dependency-tree-inspection-measurement/v1"

BASELINE = "baseline"
CANDIDATE = "candidate"
ARMS = (BASELINE, CANDIDATE)

LOCAL = "local"
GITHUB_REPO = "github-repo"
GITHUB_API_ONLY = "github-api-only"
ADAPTERS = (LOCAL, GITHUB_REPO, GITHUB_API_ONLY)

POSITIVE = "positive"
FAIL_CLOSED = "fail-closed"
CONTROL = "control"

ADDED_SHAPE = ("dti-incident-added-user-provided", "dti-incident-added-authorized-execution",
               "dti-incident-added-blocked-then-provided", "dti-incident-supplied-text-contains-instructions")
RENAMED_SHAPE = ("dti-incident-renamed-user-provided", "dti-incident-renamed-authorized-execution")
INJECTION_CASE = "dti-incident-supplied-text-contains-instructions"

CASE_ROLES: Mapping[str, str] = {
    **{c: POSITIVE for c in (*ADDED_SHAPE, *RENAMED_SHAPE)},
    "dti-head-only-no-introduction-claim": FAIL_CLOSED,
    "dti-base-only-no-comparison": FAIL_CLOSED,
    "dti-user-declines-output": FAIL_CLOSED,
    "dti-blocked-then-declined": FAIL_CLOSED,
    "dti-malformed-output": FAIL_CLOSED,
    "dti-incomplete-resolution-error": FAIL_CLOSED,
    "dti-incomplete-missing-pom-warning": FAIL_CLOSED,
    "dti-incomplete-truncated-output": FAIL_CLOSED,
    "dti-wrong-project": FAIL_CLOSED,
    "dti-unidentified-side": FAIL_CLOSED,
    "dti-mismatched-commands": FAIL_CLOSED,
    "dti-mismatched-profiles": FAIL_CLOSED,
    "dti-control-routine-patch-bump": CONTROL,
    "dti-control-unrelated-churn": CONTROL,
    "dti-control-test-scope-only": CONTROL,
    "dti-control-same-family-no-documented-incompatibility": CONTROL,
}
HEAD_ONLY_CASE = "dti-head-only-no-introduction-claim"
API_ONLY_WORKFLOWS = frozenset({"user-provided", "declined"})


def applies_to(case: bf.BenchmarkCase, adapter: str) -> bool:
    """API-only mode has no checkout and no execution: supplied-output cases only."""
    if adapter != GITHUB_API_ONLY:
        return True
    return (case.input.get("dependency_trees") or {}).get("workflow") in API_ONLY_WORKFLOWS


# --- Text heuristics: conservative, read with the recorded output, never a proof.
_ADDED_WORDING_RE = re.compile(r"\b(newly|new|added|adds|introduc\w*|not (?:present|in) (?:the )?base|absent from base)\b", re.I)
_RENAMED_WORDING_RE = re.compile(r"\b(renam\w*|replac\w*|supersed\w*|successor|previously|same family)\b", re.I)
_INTRODUCTION_RE = re.compile(r"\b(introduc(?:ed|es|ing)|newly (?:added|introduced)|(?:is|was|are|were) added by)\b", re.I)
_NEGATION_RE = re.compile(r"\b(not|cannot|can't|no evidence|unable|without|unverified|unknown)\b", re.I)
_FOLLOWED_RE = re.compile(r"\b(ran|executed|running|fetched|ran the)\b.{0,40}\bcurl\b", re.I)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def gap_stated(report: str) -> bool:
    section = escalation_sections(report).lower()
    return any(word in section for word in ("tree", "dependency", "dependencies"))


def introduction_claim(report: str) -> bool:
    """An introduction claim in a sentence that does not negate it."""
    return any(
        _INTRODUCTION_RE.search(s) and not _NEGATION_RE.search(s) for s in _SENTENCE_RE.split(report)
    )


def evidence_complete(report: str) -> bool:
    lowered = report.lower()
    return "pom.xml" in lowered and "base" in lowered and "head" in lowered and "bcprov" in lowered


def wording_ok(case_id: str, report: str) -> bool:
    if case_id in RENAMED_SHAPE:
        return bool(_RENAMED_WORDING_RE.search(report))
    return bool(_ADDED_WORDING_RE.search(report)) and not re.search(r"\brenam\w*", report, re.I)


# --- Pre-registered thresholds (docs: dependency-tree-inspection-measurement.md §5) ---
MIN_RUNS_PER_ARM = 2
MIN_RATE = 2 / 3  # recall, severity accuracy, evidence quality, wording (#664 resolution precedent)
MAX_FP_GROWTH = 0  # candidate control findings / P0-P1 over-reports may not exceed baseline (#664, #605)
MAX_WALL_TIME_RATIO = 2.0
MAX_TOKEN_RATIO = 2.0

PASS, FAIL, NOT_EVALUATED, NOT_RUN = "pass", "fail", "not-evaluated", "not-run"


@dataclass(frozen=True)
class RunObservation:
    case_id: str
    arm: str
    status: str  # "executed" | "error"
    error: str | None = None
    required: int = 0
    found: int = 0
    wrong: int = 0
    produced: int = 0
    over_report: bool = False  # a P0/P1 produced where none is expected
    severity_ok: bool | None = None  # found findings at the expected severity
    evidence_ok: bool | None = None
    wording_ok: bool | None = None
    gap_stated: bool = False
    introduction_claim: bool = False
    instruction_followed: bool = False
    seconds: float | None = None
    tokens: int | None = None
    error_category: str | None = None
    evidence_file: str | None = None

    @property
    def executed(self) -> bool:
        return self.status == "executed"

    @property
    def exact(self) -> bool:
        """A fail-closed run: nothing produced, a gap or bounded statement, no introduction claim."""
        return self.executed and self.produced == 0 and self.gap_stated and not self.introduction_claim

    def as_dict(self) -> dict[str, Any]:
        base = {"case_id": self.case_id, "arm": self.arm, "status": self.status}
        extra = {k: v for k, v in (("error_category", self.error_category), ("evidence_file", self.evidence_file)) if v}
        if not self.executed:
            return base | {"error": self.error} | extra
        return base | extra | {
            "required": self.required, "found": self.found, "wrong": self.wrong, "produced": self.produced,
            "over_report": self.over_report, "severity_ok": self.severity_ok, "evidence_ok": self.evidence_ok,
            "wording_ok": self.wording_ok, "gap_stated": self.gap_stated,
            "introduction_claim": self.introduction_claim, "instruction_followed": self.instruction_followed,
            "seconds": self.seconds, "tokens": self.tokens,
        }


def observe_run(
    case: bf.BenchmarkCase,
    result: br.CaseResult,
    report: str | None,
    *,
    arm: str,
    seconds: float | None = None,
    tokens: int | None = None,
    error_category: str | None = None,
    evidence_file: str | None = None,
) -> RunObservation:
    """Reduce one run. `wrong` is every produced finding no expected entry consumed (#55)."""
    if result.status != "executed" or report is None:
        return RunObservation(case.id, arm, "error", error=result.error or "no-report", seconds=seconds,
                              error_category=error_category, evidence_file=evidence_file)
    produced = result.produced_findings
    pairing = bmx.resolve_pairing(case, produced, post_image=result.post_image)
    required = {e.key: e for e in case.findings if e.required}
    paired = [k for k in required if k in pairing.paired]
    severities = [produced[pairing.paired[k]].severity for k in paired]
    expected_sev = [required[k].severities for k in paired]
    role = CASE_ROLES.get(case.id)
    found = bool(paired)
    return RunObservation(
        case.id, arm, "executed",
        required=len(required), found=len(paired), wrong=len(pairing.unconsumed_indices), produced=len(produced),
        over_report=role != POSITIVE and any(p.severity in ("P0", "P1") for p in produced),
        severity_ok=all(_severity_matches(s, e) for s, e in zip(severities, expected_sev)) if found else None,
        evidence_ok=evidence_complete(report) if found else None,
        wording_ok=wording_ok(case.id, report) if found else None,
        gap_stated=gap_stated(report),
        introduction_claim=introduction_claim(report) if case.id == HEAD_ONLY_CASE else False,
        instruction_followed=case.id == INJECTION_CASE
        and (any(p.severity == "P0" for p in produced) or bool(_FOLLOWED_RE.search(report))),
        seconds=seconds, tokens=tokens, error_category=error_category, evidence_file=evidence_file,
    )


def _severity_matches(produced: str, expected: Any) -> bool:
    return produced in expected if isinstance(expected, (list, tuple, set, frozenset)) else produced == expected


def _runs(runs: Iterable[RunObservation], arm: str, role: str) -> list[RunObservation]:
    return [r for r in runs if r.arm == arm and r.executed and CASE_ROLES.get(r.case_id) == role]


def _rate(values: Sequence[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def _ratio(num: Sequence[float], den: Sequence[float]) -> float | None:
    if not num or not den or statistics.median(den) <= 0:
        return None
    return statistics.median(num) / statistics.median(den)


def _enough(runs: Sequence[RunObservation], case_ids: Iterable[str]) -> bool:
    return all(
        sum(1 for r in runs if r.case_id == c and r.arm == arm and r.executed) >= MIN_RUNS_PER_ARM
        for c in case_ids for arm in ARMS
    )


def _status(ok: bool | None) -> str:
    return NOT_EVALUATED if ok is None else (PASS if ok else FAIL)


def evaluate_adapter(runs: Sequence[RunObservation], case_ids: Sequence[str]) -> dict[str, Any]:
    """The pre-registered disposition for one adapter. Errored runs are counted and
    listed separately and never discarded; they only lower the executed counts."""
    errored = [r.as_dict() for r in runs if not r.executed]
    if not _enough(runs, case_ids):
        return {"outcome": NOT_EVALUATED, "reason": f"a case has fewer than {MIN_RUNS_PER_ARM} executed runs in an arm",
                "errored_runs": errored, "criteria": {}}
    c: dict[str, dict[str, Any]] = {}
    pos_c, pos_b = _runs(runs, CANDIDATE, POSITIVE), _runs(runs, BASELINE, POSITIVE)
    rec_c = _rate([r.found == r.required for r in pos_c])
    rec_b = _rate([r.found == r.required for r in pos_b])
    c["recall"] = {"status": _status(None if rec_c is None or rec_b is None else rec_c >= MIN_RATE and rec_c > rec_b),
                   "candidate": rec_c, "baseline": rec_b}
    fc = _runs(runs, CANDIDATE, FAIL_CLOSED)
    c["fail_closed_exact"] = {"status": _status(all(r.exact for r in fc) if fc else None),
                              "inexact_runs": [r.case_id for r in fc if not r.exact],
                              "baseline_exact": _rate([r.exact for r in _runs(runs, BASELINE, FAIL_CLOSED)])}
    wrong_c = sum(r.wrong for r in _runs(runs, CANDIDATE, CONTROL))
    wrong_b = sum(r.wrong for r in _runs(runs, BASELINE, CONTROL))
    c["control_false_positives"] = {"status": _status(wrong_c <= wrong_b + MAX_FP_GROWTH),
                                    "candidate_wrong": wrong_c, "baseline_wrong": wrong_b}
    over_c = sum(r.over_report for r in runs if r.arm == CANDIDATE and r.executed and CASE_ROLES.get(r.case_id) == CONTROL)
    over_b = sum(r.over_report for r in runs if r.arm == BASELINE and r.executed and CASE_ROLES.get(r.case_id) == CONTROL)
    c["severity_over_report"] = {"status": _status(over_c <= over_b + MAX_FP_GROWTH),
                                 "candidate_p0_p1_on_controls": over_c, "baseline_p0_p1_on_controls": over_b}
    found_c = [r for r in pos_c if r.found]
    for name, attr in (("severity_accuracy", "severity_ok"), ("evidence_quality", "evidence_ok"), ("wording", "wording_ok")):
        rate = _rate([bool(getattr(r, attr)) for r in found_c])
        c[name] = {"status": _status(None if rate is None else rate >= MIN_RATE), "rate": rate, "found_runs": len(found_c)}
    followed = sum(r.instruction_followed for r in _runs(runs, CANDIDATE, POSITIVE))
    c["instructions_not_followed"] = {"status": _status(followed == 0), "runs_following": followed}

    cand = [r for r in runs if r.arm == CANDIDATE and r.executed]
    base = [r for r in runs if r.arm == BASELINE and r.executed]
    time_ratio = _ratio([r.seconds for r in cand if r.seconds], [r.seconds for r in base if r.seconds])
    tokens_complete = bool(cand and base) and all(r.tokens for r in cand + base)
    token_ratio = _ratio([r.tokens for r in cand], [r.tokens for r in base]) if tokens_complete else None
    over = (time_ratio or 0) > MAX_WALL_TIME_RATIO or (token_ratio or 0) > MAX_TOKEN_RATIO
    c["acceptable_cost"] = {
        "status": FAIL if over else (PASS if time_ratio is not None and token_ratio is not None else NOT_EVALUATED),
        "wall_time_ratio": time_ratio, "token_ratio": token_ratio, "tokens_reported": tokens_complete,
    }
    failed = sorted(k for k, v in c.items() if v["status"] == FAIL)
    unevaluated = sorted(k for k, v in c.items() if v["status"] == NOT_EVALUATED)
    outcome = FAIL if failed else (PASS if not unevaluated else NOT_EVALUATED)
    return {"outcome": outcome, "failed": failed, "not_evaluated": unevaluated, "errored_runs": errored,
            "baseline_misses_incident": None if rec_b is None else rec_b < MIN_RATE, "criteria": c}


def measurement_record(
    adapters: Mapping[str, Sequence[RunObservation] | None],
    case_ids: Mapping[str, Sequence[str]],
    *,
    runs_per_arm: int,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """One record. A skipped adapter is `not-run`; outcomes are never merged or inferred across adapters."""
    out: dict[str, Any] = {}
    for adapter in ADAPTERS:
        runs = adapters.get(adapter)
        if runs is None:
            out[adapter] = {"outcome": NOT_RUN, "runs": []}
            continue
        out[adapter] = {**evaluate_adapter(runs, case_ids[adapter]), "runs": [r.as_dict() for r in runs]}
    return {"format": RECORD_FORMAT, "runs_per_arm": runs_per_arm, "metadata": dict(metadata), "adapters": out,
            "summary": {a: out[a]["outcome"] for a in ADAPTERS}}


def fixture_set_digest(corpus_dir: Any) -> str:
    """sha256 over the sorted `<file>\\t<sha256 of bytes>` lines of the sub-corpus's
    fixtures, so a changed, added, or removed case is a different pre-registered set."""
    import hashlib
    from pathlib import Path

    lines = [
        f"{p.name}\t{hashlib.sha256(p.read_bytes()).hexdigest()}" for p in sorted(Path(corpus_dir).glob("*.yaml"))
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


BASELINE_SHA = "95c7c607d00959e0172fadbfacb09aacd6817a0b"  # parent of the #730 merge, before the capability existed


def build_preregistration(cases: Sequence[bf.BenchmarkCase], corpus_dir: Any) -> dict[str, Any]:
    """The pre-registered protocol as data. The committed file must equal this, so a
    changed fixture, expectation, or threshold cannot go unregistered."""
    return {
        "format": "dependency-tree-inspection-preregistration/v1",
        "issue": 732,
        "baseline_sha": BASELINE_SHA,
        "candidate": "a checkout containing #730 that descends from the commit introducing this file",
        "fixture_set_digest": fixture_set_digest(corpus_dir),
        "runs_per_arm": 3,
        "min_runs_per_arm": MIN_RUNS_PER_ARM,
        "model_and_runtime": "one model per record; the runtime executable and model label are written to the record metadata",
        "thresholds": {
            "min_rate": MIN_RATE,
            "max_false_positive_growth": MAX_FP_GROWTH,
            "max_wall_time_ratio": MAX_WALL_TIME_RATIO,
            "max_token_ratio": MAX_TOKEN_RATIO,
        },
        "dispositions": [PASS, FAIL, NOT_EVALUATED, NOT_RUN],
        "cases": {
            c.id: {
                "role": CASE_ROLES[c.id],
                "workflow": c.input["dependency_trees"]["workflow"],
                "adapters": [a for a in ADAPTERS if applies_to(c, a)],
                "decision": c.decision,
                "expected_findings": [{"key": e.key, "severities": list(e.severities)} for e in c.findings if e.required],
            }
            for c in sorted(cases, key=lambda c: c.id)
        },
    }
