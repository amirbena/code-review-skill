#!/usr/bin/env python3
"""Test-only reference for the benchmark regression report (Issue #53).

Test-only: not runtime logic, not packaged — the packaged Skills are
Markdown/YAML only. This module mirrors
``docs/benchmark/regression-report.md``: the baseline result artifact, the
identity guard, the per-case and aggregate deltas between a candidate run
and a stored baseline, the metric-free rule that separates a *regression*
from an *improvement*, deterministic output, and the "the report never
writes the baseline" rule.

It consumes the runner's recorded per-case results
(``tests/reference/benchmark_runner.py``, Issue #52) verbatim and never
re-runs a reviewer. It is a *run-to-run diff*, not a scorer: it never
reads a fixture's ``expected`` block, and it computes no precision, recall,
or pass rate — that is Issue #41.

The contract is the *behaviour and guarantees*; this module is one
executable projection of them so a test can prove the report flags a
seeded regression, separates it from an improvement, and serializes
identically for identical inputs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from tests.reference import benchmark_runner as br

# Ordinal severity: a *rise* is toward P0 (more severe).
_SEVERITY_ORDINAL = {"P2": 0, "P1": 1, "P0": 2}
_SEVERITIES = ("P0", "P1", "P2")

# Class render order (regression-report.md §7). ``added`` / ``removed`` are
# reported as their own top-level id lists, not grouped case deltas, so the
# per-case section iterates ``_GROUPED_CLASSES``.
CLASS_ORDER = ("regression", "mixed", "improvement", "added", "removed", "unchanged")
_GROUPED_CLASSES = tuple(c for c in CLASS_ORDER if c not in ("added", "removed"))


class ReportError(RuntimeError):
    """The report cannot produce a trustworthy comparison.

    Raised only for the process-health failures in
    ``docs/benchmark/regression-report.md`` §9: an unparseable artifact or
    a ``corpus_id`` mismatch (§3). Finding regressions is never this error
    — it is a well-formed report with ``has_regressions`` true.

    This reference model is handed already-decoded run results, so the only
    failure it raises here is the ``corpus_id`` mismatch (plus a duplicate
    case id); artifact/candidate *parsing* is the caller's concern and is
    out of this projection's scope.
    """


# --------------------------------------------------------------------------
# Corpus identity (regression-report.md §2 `corpus_id`).
# --------------------------------------------------------------------------


def corpus_digest(corpus_dir: Path) -> str:
    """A stable digest of the corpus: every fixture id + a content digest.

    Distinguishes "the reviewer changed" from "the corpus changed" so §3's
    identity guard can fail closed on a stale baseline.
    """
    h = hashlib.sha256()
    for path in sorted(corpus_dir.glob("*.yaml")):
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


# --------------------------------------------------------------------------
# Baseline artifact (regression-report.md §2).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class BaselineArtifact:
    """A stored run result plus the closed identity block.

    ``created_at`` is informational only and never an input to a delta
    (§7); it is accepted and ignored here.
    """

    results: tuple[br.CaseResult, ...]
    corpus_id: str
    adapter_id: str
    created_at: str | None = None

    @staticmethod
    def from_run(
        run: br.RunResult, *, corpus_id: str, adapter_id: str, created_at: str | None = None
    ) -> "BaselineArtifact":
        """Promote a completed candidate run to a baseline (§8). This is the
        only constructor path — the report itself never calls it."""
        if not run.ok:
            raise ReportError(f"cannot baseline a failed run: {run.error}")
        return BaselineArtifact(
            results=tuple(run.case_results),
            corpus_id=corpus_id,
            adapter_id=adapter_id,
            created_at=created_at,
        )


# --------------------------------------------------------------------------
# Cross-run stability key (regression-report.md §4).
# --------------------------------------------------------------------------


# Identity-bearing location fields only. Positional / coordinate fields
# (`line`, `lines`, `col`, …) are deliberately excluded from the stability
# key: line numbers drift as code moves (regression-report.md §4, and
# fixture-format.md "Advisory only … line numbers move"), so folding them
# in would make a reviewer whose output shifts by a line look like a
# simultaneous drop + gain (a spurious `mixed`).
_IDENTITY_LOCATION_FIELDS = ("location_intent", "path", "file", "symbol", "anchor")


def _normalize_location(location: Any) -> str:
    """Coarse, identity-only rendering of whatever location shape the
    adapter supplied. Deliberately lossy — this only has to be stable
    across two runs of the same case, not semantically precise (§4), and it
    excludes positional fields so a one-line drift still pairs as
    *retained* rather than drop + gain."""
    if isinstance(location, Mapping):
        parts = []
        for key in _IDENTITY_LOCATION_FIELDS:
            if key not in location:
                continue
            value = location[key]
            if key in {"path", "file"} and isinstance(value, str):
                value = _normalize_path(value)
            parts.append(f"{key}={value}")
        return "|".join(parts)
    if isinstance(location, str):
        return location.replace("\\", "/").strip()
    return repr(location)


def _normalize_path(path: str) -> str:
    """Backslashes to slashes, drop a single leading ``./``. Deliberately
    minimal — enough to pair ``./a/b`` with ``a/b`` without mangling a
    dotfile like ``.env`` (which ``str.lstrip('./')`` would turn into
    ``env``)."""
    path = path.replace("\\", "/").strip()
    return path[2:] if path.startswith("./") else path


def stability_key(finding: br.ProducedFinding) -> tuple[str, str]:
    """Pair findings across two runs of the same case for delta display.

    NOT the #41 expected-vs-produced match relation and carries no
    correctness judgement. Severity is intentionally excluded so a
    persisted finding at a changed severity is a *retained* finding with a
    reported severity change, not a drop + gain (§4).
    """
    discriminator = ""
    extra = finding.extra or {}
    for candidate in ("defect_kind", "key", "id"):
        value = extra.get(candidate)
        if isinstance(value, str) and value.strip():
            discriminator = f"{candidate}:{value.strip()}"
            break
    if not discriminator and isinstance(finding.claim, str) and finding.claim.strip():
        discriminator = f"claim:{finding.claim.strip()}"
    return (_normalize_location(finding.location), discriminator)


# --------------------------------------------------------------------------
# Per-case delta (regression-report.md §4–§5).
# --------------------------------------------------------------------------


def _histogram(findings: Iterable[br.ProducedFinding]) -> dict[str, int]:
    hist = {sev: 0 for sev in _SEVERITIES}
    for f in findings:
        if f.severity in hist:
            hist[f.severity] += 1
    return hist


def _hist_delta(base: Mapping[str, int], cand: Mapping[str, int]) -> dict[str, int]:
    return {sev: cand.get(sev, 0) - base.get(sev, 0) for sev in _SEVERITIES}


@dataclass(frozen=True)
class RetainedFinding:
    key: tuple[str, str]
    baseline_severity: str
    candidate_severity: str

    @property
    def severity_changed(self) -> bool:
        return self.baseline_severity != self.candidate_severity

    @property
    def severity_rose(self) -> bool:
        return (
            _SEVERITY_ORDINAL.get(self.candidate_severity, -1)
            > _SEVERITY_ORDINAL.get(self.baseline_severity, -1)
        )

    @property
    def severity_fell(self) -> bool:
        return (
            _SEVERITY_ORDINAL.get(self.candidate_severity, -1)
            < _SEVERITY_ORDINAL.get(self.baseline_severity, -1)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "location": self.key[0],
            "discriminator": self.key[1],
            "baseline_severity": self.baseline_severity,
            "candidate_severity": self.candidate_severity,
            "severity_changed": self.severity_changed,
        }


@dataclass(frozen=True)
class CaseDelta:
    id: str
    baseline_status: str
    candidate_status: str
    baseline_error: str | None
    candidate_error: str | None
    dropped: tuple[br.ProducedFinding, ...]
    gained: tuple[br.ProducedFinding, ...]
    retained: tuple[RetainedFinding, ...]
    severity_histogram_baseline: Mapping[str, int]
    severity_histogram_candidate: Mapping[str, int]
    ambiguous: bool
    classification: str = field(default="unchanged")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "classification": self.classification,
            "status": {
                "baseline": self.baseline_status,
                "candidate": self.candidate_status,
                **(
                    {"baseline_error": self.baseline_error}
                    if self.baseline_error is not None
                    else {}
                ),
                **(
                    {"candidate_error": self.candidate_error}
                    if self.candidate_error is not None
                    else {}
                ),
            },
            "dropped": [f.as_dict() for f in self.dropped],
            "gained": [f.as_dict() for f in self.gained],
            # Every retained finding is listed; `severity_changed` flags the
            # ones whose severity moved. Emitting all of them keeps the
            # per-case view reconcilable with `totals.retained` (§6).
            "retained": [r.as_dict() for r in self.retained],
            "severity_histogram": {
                "baseline": dict(self.severity_histogram_baseline),
                "candidate": dict(self.severity_histogram_candidate),
                "delta": _hist_delta(
                    self.severity_histogram_baseline, self.severity_histogram_candidate
                ),
            },
        }


def _partition(
    baseline: Sequence[br.ProducedFinding], candidate: Sequence[br.ProducedFinding]
) -> tuple[
    tuple[br.ProducedFinding, ...],
    tuple[br.ProducedFinding, ...],
    tuple[RetainedFinding, ...],
    bool,
]:
    """Split candidate vs baseline produced findings into dropped / gained /
    retained by the cross-run stability key. ``ambiguous`` is True when a
    key is not unique within a run — the report must not guess (§4)."""

    def _by_key(items: Sequence[br.ProducedFinding]) -> dict[tuple[str, str], list[br.ProducedFinding]]:
        out: dict[tuple[str, str], list[br.ProducedFinding]] = {}
        for it in items:
            out.setdefault(stability_key(it), []).append(it)
        return out

    base_by_key = _by_key(baseline)
    cand_by_key = _by_key(candidate)
    ambiguous = any(len(v) > 1 for v in base_by_key.values()) or any(
        len(v) > 1 for v in cand_by_key.values()
    )

    dropped = [
        f
        for key, group in sorted(base_by_key.items())
        for f in group
        if key not in cand_by_key
    ]
    gained = [
        f
        for key, group in sorted(cand_by_key.items())
        for f in group
        if key not in base_by_key
    ]
    retained = [
        RetainedFinding(
            key=key,
            baseline_severity=base_by_key[key][0].severity,
            candidate_severity=cand_by_key[key][0].severity,
        )
        for key in sorted(set(base_by_key) & set(cand_by_key))
    ]
    return tuple(dropped), tuple(gained), tuple(retained), ambiguous


def _classify(delta: CaseDelta) -> str:
    status_regressed = delta.baseline_status == "executed" and delta.candidate_status == "error"
    status_improved = delta.baseline_status == "error" and delta.candidate_status == "executed"

    sev_rose = any(r.severity_rose for r in delta.retained)
    sev_fell = any(r.severity_fell for r in delta.retained)

    dropped, gained = bool(delta.dropped), bool(delta.gained)

    regression_signals = status_regressed or (dropped and not gained) or (sev_rose and not sev_fell)
    improvement_signals = status_improved or (gained and not dropped) or (sev_fell and not sev_rose)

    if delta.ambiguous:
        return "mixed"
    if regression_signals and improvement_signals:
        return "mixed"
    if (dropped and gained):
        return "mixed"
    if regression_signals:
        return "regression"
    if improvement_signals:
        return "improvement"
    return "unchanged"


def _case_delta(baseline: br.CaseResult, candidate: br.CaseResult) -> CaseDelta:
    b_findings = baseline.produced_findings if baseline.status == "executed" else ()
    c_findings = candidate.produced_findings if candidate.status == "executed" else ()
    dropped, gained, retained, ambiguous = _partition(b_findings, c_findings)
    delta = CaseDelta(
        id=baseline.id,
        baseline_status=baseline.status,
        candidate_status=candidate.status,
        baseline_error=baseline.error,
        candidate_error=candidate.error,
        dropped=dropped,
        gained=gained,
        retained=retained,
        severity_histogram_baseline=_histogram(b_findings),
        severity_histogram_candidate=_histogram(c_findings),
        ambiguous=ambiguous,
    )
    return replace(delta, classification=_classify(delta))


# --------------------------------------------------------------------------
# The report (regression-report.md §6).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RegressionReport:
    corpus_id: str
    baseline_adapter_id: str
    candidate_adapter_id: str
    case_deltas: tuple[CaseDelta, ...]
    added_case_ids: tuple[str, ...]
    removed_case_ids: tuple[str, ...]

    def _by_class(self, name: str) -> list[CaseDelta]:
        return [d for d in self.case_deltas if d.classification == name]

    @property
    def counts(self) -> dict[str, int]:
        out = {name: len(self._by_class(name)) for name in _GROUPED_CLASSES}
        out["added"] = len(self.added_case_ids)
        out["removed"] = len(self.removed_case_ids)
        return out

    @property
    def total_dropped(self) -> int:
        return sum(len(d.dropped) for d in self.case_deltas)

    @property
    def total_gained(self) -> int:
        return sum(len(d.gained) for d in self.case_deltas)

    @property
    def total_retained(self) -> int:
        return sum(len(d.retained) for d in self.case_deltas)

    @property
    def aggregate_severity_delta(self) -> dict[str, int]:
        agg = {sev: 0 for sev in _SEVERITIES}
        for d in self.case_deltas:
            for sev, n in _hist_delta(
                d.severity_histogram_baseline, d.severity_histogram_candidate
            ).items():
                agg[sev] += n
        return agg

    @property
    def has_regressions(self) -> bool:
        return bool(
            self._by_class("regression") or self._by_class("mixed") or self.removed_case_ids
        )

    def as_dict(self) -> dict[str, Any]:
        """Deterministic serialization (§7): cases ordered by id within each
        section, classes in a fixed order, no run-specific noise."""
        grouped = {
            name: [d.as_dict() for d in sorted(self._by_class(name), key=lambda x: x.id)]
            for name in _GROUPED_CLASSES
        }
        return {
            "identity": {
                "corpus_id": self.corpus_id,
                "baseline_adapter_id": self.baseline_adapter_id,
                "candidate_adapter_id": self.candidate_adapter_id,
            },
            "has_regressions": self.has_regressions,
            "counts": self.counts,
            "totals": {
                "dropped": self.total_dropped,
                "gained": self.total_gained,
                "retained": self.total_retained,
                "severity_delta": self.aggregate_severity_delta,
            },
            "cases": grouped,
            "added_case_ids": list(self.added_case_ids),
            "removed_case_ids": list(self.removed_case_ids),
        }


def compare(
    baseline: BaselineArtifact,
    candidate_results: Sequence[br.CaseResult] | br.RunResult,
    *,
    candidate_corpus_id: str,
    candidate_adapter_id: str,
) -> RegressionReport:
    """Join a candidate run to ``baseline`` by case ``id`` and emit the
    regression report (§3–§6).

    Raises :class:`ReportError` on a ``corpus_id`` mismatch (§3) — a delta
    across two different corpora is not a regression signal, and the remedy
    is a deliberate baseline refresh (§8), not a silent comparison.
    """
    if isinstance(candidate_results, br.RunResult):
        if not candidate_results.ok:
            raise ReportError(
                f"candidate run did not complete: {candidate_results.error}"
            )
        candidate_seq: Sequence[br.CaseResult] = candidate_results.case_results
    else:
        candidate_seq = candidate_results

    if candidate_corpus_id != baseline.corpus_id:
        raise ReportError(
            "corpus_id mismatch: baseline and candidate ran against different "
            "corpora; refresh the baseline (regression-report.md §8) instead "
            "of comparing across corpora"
        )

    base_by_id = {r.id: r for r in baseline.results}
    cand_by_id = {r.id: r for r in candidate_seq}
    if len(base_by_id) != len(baseline.results) or len(cand_by_id) != len(candidate_seq):
        raise ReportError("duplicate case id in a run result")

    common = sorted(set(base_by_id) & set(cand_by_id))
    added = tuple(sorted(set(cand_by_id) - set(base_by_id)))
    removed = tuple(sorted(set(base_by_id) - set(cand_by_id)))

    deltas = tuple(_case_delta(base_by_id[cid], cand_by_id[cid]) for cid in common)

    return RegressionReport(
        corpus_id=baseline.corpus_id,
        baseline_adapter_id=baseline.adapter_id,
        candidate_adapter_id=candidate_adapter_id,
        case_deltas=deltas,
        added_case_ids=added,
        removed_case_ids=removed,
    )
