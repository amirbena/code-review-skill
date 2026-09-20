#!/usr/bin/env python3
"""Drift classification (Issue #339): meaning, fingerprint identity, and the `detect` CLI.

Full contract: `runtime_platform/benchmark/drift-detection-and-regression-lifecycle.md`.
The GitHub issue lifecycle lives in `benchmark_regression_lifecycle.py`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Reused, not reinvented (see the contract doc §1): `runtime_platform/benchmark/reference`
# is the only executable projection of #53/#54/#55/#56/#57 today.
from runtime_platform.benchmark.reference import benchmark_metrics as bmet  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_severity as bsev  # noqa: E402

# --------------------------------------------------------------------------
# Meaningful drift vs. noise (contract §2).
# --------------------------------------------------------------------------

DRIFT_MISSED_REQUIRED_FINDING = "missed-required-finding"
DRIFT_DECISION_FLIP = "decision-flip"
DRIFT_SEVERITY_ACCURACY_DROP = "severity-accuracy-drop"

# Sentinel `expected_finding_key` for a case-level (not per-finding) drift_type.
CASE_LEVEL_FINDING_KEY = "-"

# More than a 20-percentage-point exact-rate drop is meaningful; at or below
# absorbs single-run flakiness in a small matched set (contract §2).
DEFAULT_SEVERITY_EXACT_RATE_TOLERANCE = Fraction(1, 5)


@dataclass(frozen=True)
class DriftRecord:
    case_id: str
    drift_type: str
    expected_finding_key: str
    detail: str

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.case_id, self.drift_type, self.expected_finding_key)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "drift_type": self.drift_type,
            "expected_finding_key": self.expected_finding_key,
            "detail": self.detail,
            "fingerprint": self.fingerprint,
        }


def fingerprint(case_id: str, drift_type: str, expected_finding_key: str) -> str:
    """Stable identity for a regression (contract §3): sha256 of the
    canonical `{case_id, drift_type, expected_finding_key}` triple, built
    from the fields directly so a caller's key ordering/whitespace never
    changes the result."""
    canonical = json.dumps(
        {
            "case_id": case_id,
            "drift_type": drift_type,
            "expected_finding_key": expected_finding_key,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def classify_drift(
    baseline_metrics: Mapping[str, bmet.CaseMetrics],
    candidate_metrics: Mapping[str, bmet.CaseMetrics],
    baseline_severity: Mapping[str, bsev.CaseSeverityAccuracy],
    candidate_severity: Mapping[str, bsev.CaseSeverityAccuracy],
    *,
    severity_exact_rate_tolerance: Fraction = DEFAULT_SEVERITY_EXACT_RATE_TOLERANCE,
) -> list[DriftRecord]:
    """The §2 policy, applied per case. Cases present in only one run, and
    every noise example the contract lists, never reach a `DriftRecord`."""
    records: list[DriftRecord] = []

    for case_id in sorted(set(baseline_metrics) & set(candidate_metrics)):
        base, cand = baseline_metrics[case_id], candidate_metrics[case_id]

        newly_missed = sorted(set(cand.missed_keys) - set(base.missed_keys))
        for key in newly_missed:
            records.append(
                DriftRecord(
                    case_id,
                    DRIFT_MISSED_REQUIRED_FINDING,
                    key,
                    f"required finding '{key}' was matched in the baseline and is now missed",
                )
            )

        if not base.missed_keys and cand.missed_keys:
            records.append(
                DriftRecord(
                    case_id,
                    DRIFT_DECISION_FLIP,
                    CASE_LEVEL_FINDING_KEY,
                    "case satisfied every required finding in the baseline and no longer does",
                )
            )

    for case_id in sorted(set(baseline_severity) & set(candidate_severity)):
        base_sev, cand_sev = baseline_severity[case_id], candidate_severity[case_id]
        base_rate, cand_rate = base_sev.exact_rate, cand_sev.exact_rate
        if base_rate is None or cand_rate is None:
            continue  # undefined rate (nothing matched) is not comparable.
        if base_rate - cand_rate > severity_exact_rate_tolerance:
            records.append(
                DriftRecord(
                    case_id,
                    DRIFT_SEVERITY_ACCURACY_DROP,
                    CASE_LEVEL_FINDING_KEY,
                    f"severity exact-match rate dropped from {base_rate} to {cand_rate}",
                )
            )

    return sorted(records, key=lambda r: (r.case_id, r.drift_type, r.expected_finding_key))


# Labels the publication side applies; owned here so the manifest test can pin them.
REGRESSION_LABEL = "benchmark-regression"
KEEP_OPEN_LABEL = "keep-open"


def _load_case_metrics_and_severity(
    path: Path,
) -> tuple[dict[str, bmet.CaseMetrics], dict[str, bsev.CaseSeverityAccuracy]]:
    """`path` is a pre-computed per-case metrics/severity JSON file, the
    shape a caller (e.g. a nightly Routine step) is expected to produce by
    running #55/#56 over #338's history entries before invoking this CLI —
    this CLI never re-runs the reviewer or the matcher itself."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    metrics = {
        row["id"]: bmet.CaseMetrics(
            id=row["id"],
            status=row["status"],
            findings_completeness=row["findings_completeness"],
            false_negatives=row["false_negatives"],
            false_positives=row["false_positives"],
            missed_keys=tuple(row["missed_keys"]),
            incorrect_indices=tuple(row["incorrect_indices"]),
            near_misses=row["near_misses"],
            absorbed_extra_match=row["absorbed_extra_match"],
            tolerated_unexpected=row["tolerated_unexpected"],
        )
        for row in raw["metrics"]
    }
    severity = {
        row["id"]: bsev.CaseSeverityAccuracy(
            id=row["id"],
            status=row["status"],
            matched=row["matched"],
            severity_exact=row["severity_exact"],
            over_severity=row["over_severity"],
            under_severity=row["under_severity"],
            mismatches=tuple(row.get("mismatches", ())),
        )
        for row in raw["severity"]
    }
    return metrics, severity


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    detect = sub.add_parser("detect", help="Classify drift between a baseline and candidate metrics/severity file.")
    detect.add_argument("--baseline-file", required=True, type=Path)
    detect.add_argument("--candidate-file", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    base_metrics, base_sev = _load_case_metrics_and_severity(args.baseline_file)
    cand_metrics, cand_sev = _load_case_metrics_and_severity(args.candidate_file)
    records = classify_drift(base_metrics, cand_metrics, base_sev, cand_sev)
    print(json.dumps([r.as_dict() for r in records], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
