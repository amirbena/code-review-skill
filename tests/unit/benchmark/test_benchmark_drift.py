#!/usr/bin/env python3
"""Unit coverage for drift fingerprinting and drift-vs-noise classification
(Issue #339). Contract: docs/benchmark/drift-detection-and-regression-lifecycle.md.

Proves:

1. `fingerprint` is stable across a caller's JSON key ordering/whitespace
   and distinct across genuinely different regressions (§3);
2. `classify_drift` emits exactly the three §2 drift types under their
   documented conditions, and never emits anything for a noise example.
"""

from __future__ import annotations

import json
import unittest
from fractions import Fraction

from scripts.benchmark import benchmark_drift as bd
from tests.reference.benchmark import benchmark_metrics as bmet
from tests.reference.benchmark import benchmark_severity as bsev


def _metrics(case_id: str, *, missed: tuple[str, ...] = (), false_positives: int = 0) -> bmet.CaseMetrics:
    return bmet.CaseMetrics(
        id=case_id,
        status="executed",
        findings_completeness="exhaustive",
        false_negatives=len(missed),
        false_positives=false_positives,
        missed_keys=missed,
        incorrect_indices=(),
        near_misses=0,
        absorbed_extra_match=0,
        tolerated_unexpected=0,
    )


def _severity(case_id: str, *, matched: int, exact: int) -> bsev.CaseSeverityAccuracy:
    return bsev.CaseSeverityAccuracy(
        id=case_id,
        status="executed",
        matched=matched,
        severity_exact=exact,
        over_severity=matched - exact,
        under_severity=0,
        mismatches=(),
    )


class FingerprintTests(unittest.TestCase):
    def test_stable_across_construction_order(self) -> None:
        fp1 = bd.fingerprint("case-a", "missed-required-finding", "sqli-key")
        fp2 = bd.fingerprint(
            expected_finding_key="sqli-key",
            case_id="case-a",
            drift_type="missed-required-finding",
        )
        self.assertEqual(fp1, fp2)

    def test_stable_across_json_key_ordering_and_whitespace(self) -> None:
        payload_a = json.loads('{"case_id": "case-a", "drift_type": "decision-flip", "expected_finding_key": "-"}')
        payload_b = json.loads(
            '{\n  "expected_finding_key" : "-",\n  "drift_type": "decision-flip",\n  "case_id":   "case-a"\n}'
        )
        fp_a = bd.fingerprint(**payload_a)
        fp_b = bd.fingerprint(**payload_b)
        self.assertEqual(fp_a, fp_b)

    def test_distinct_across_case_id(self) -> None:
        fp1 = bd.fingerprint("case-a", "decision-flip", "-")
        fp2 = bd.fingerprint("case-b", "decision-flip", "-")
        self.assertNotEqual(fp1, fp2)

    def test_distinct_across_drift_type(self) -> None:
        fp1 = bd.fingerprint("case-a", "decision-flip", "-")
        fp2 = bd.fingerprint("case-a", "severity-accuracy-drop", "-")
        self.assertNotEqual(fp1, fp2)

    def test_distinct_across_expected_finding_key(self) -> None:
        fp1 = bd.fingerprint("case-a", "missed-required-finding", "sqli-key")
        fp2 = bd.fingerprint("case-a", "missed-required-finding", "path-key")
        self.assertNotEqual(fp1, fp2)

    def test_drift_record_fingerprint_property_matches_function(self) -> None:
        record = bd.DriftRecord("case-a", "decision-flip", "-", "detail")
        self.assertEqual(record.fingerprint, bd.fingerprint("case-a", "decision-flip", "-"))

    def test_output_is_64_hex_chars(self) -> None:
        fp = bd.fingerprint("case-a", "decision-flip", "-")
        self.assertRegex(fp, r"^[0-9a-f]{64}$")


class ClassifyDriftMeaningfulTests(unittest.TestCase):
    def test_missed_required_finding_on_newly_missed_key(self) -> None:
        base = {"case-a": _metrics("case-a", missed=())}
        cand = {"case-a": _metrics("case-a", missed=("sqli-key",))}
        records = bd.classify_drift(base, cand, {}, {})
        drift_types = {(r.case_id, r.drift_type, r.expected_finding_key) for r in records}
        self.assertIn(("case-a", bd.DRIFT_MISSED_REQUIRED_FINDING, "sqli-key"), drift_types)

    def test_decision_flip_when_case_stops_satisfying_every_required_entry(self) -> None:
        base = {"case-a": _metrics("case-a", missed=())}
        cand = {"case-a": _metrics("case-a", missed=("sqli-key",))}
        records = bd.classify_drift(base, cand, {}, {})
        drift_types = {(r.case_id, r.drift_type, r.expected_finding_key) for r in records}
        self.assertIn(("case-a", bd.DRIFT_DECISION_FLIP, bd.CASE_LEVEL_FINDING_KEY), drift_types)

    def test_no_decision_flip_when_baseline_already_had_a_missed_required_finding(self) -> None:
        base = {"case-a": _metrics("case-a", missed=("sqli-key",))}
        cand = {"case-a": _metrics("case-a", missed=("sqli-key", "path-key"))}
        records = bd.classify_drift(base, cand, {}, {})
        # A new miss is still reported, but the case-level flip already
        # happened in an earlier run, so it is not reported again.
        self.assertTrue(any(r.drift_type == bd.DRIFT_MISSED_REQUIRED_FINDING for r in records))
        self.assertFalse(any(r.drift_type == bd.DRIFT_DECISION_FLIP for r in records))

    def test_severity_accuracy_drop_beyond_tolerance(self) -> None:
        base_sev = {"case-a": _severity("case-a", matched=10, exact=10)}  # 1.0
        cand_sev = {"case-a": _severity("case-a", matched=10, exact=7)}  # 0.7, drop of 0.3 > 0.2
        records = bd.classify_drift({}, {}, base_sev, cand_sev)
        drift_types = {(r.case_id, r.drift_type, r.expected_finding_key) for r in records}
        self.assertIn(("case-a", bd.DRIFT_SEVERITY_ACCURACY_DROP, bd.CASE_LEVEL_FINDING_KEY), drift_types)

    def test_deterministic_ordering(self) -> None:
        base = {"case-b": _metrics("case-b"), "case-a": _metrics("case-a")}
        cand = {"case-b": _metrics("case-b", missed=("k",)), "case-a": _metrics("case-a", missed=("k",))}
        records = bd.classify_drift(base, cand, {}, {})
        self.assertEqual([r.case_id for r in records], sorted(r.case_id for r in records))


class ClassifyDriftNoiseTests(unittest.TestCase):
    def test_optional_finding_churn_is_invisible_to_missed_keys(self) -> None:
        # missed_keys only ever contains required entries (#55's own
        # contract) -- an unrelated false-positive/near-miss change alone
        # must never produce a drift record.
        base = {"case-a": _metrics("case-a", missed=(), false_positives=0)}
        cand = {"case-a": _metrics("case-a", missed=(), false_positives=3)}
        records = bd.classify_drift(base, cand, {}, {})
        self.assertEqual(records, [])

    def test_severity_accuracy_drop_within_tolerance_is_noise(self) -> None:
        base_sev = {"case-a": _severity("case-a", matched=10, exact=10)}  # 1.0
        cand_sev = {"case-a": _severity("case-a", matched=10, exact=9)}  # 0.9, drop of 0.1 <= 0.2
        records = bd.classify_drift({}, {}, base_sev, cand_sev)
        self.assertEqual(records, [])

    def test_undefined_exact_rate_in_either_run_is_not_comparable(self) -> None:
        base_sev = {"case-a": _severity("case-a", matched=0, exact=0)}  # exact_rate None
        cand_sev = {"case-a": _severity("case-a", matched=5, exact=1)}
        records = bd.classify_drift({}, {}, base_sev, cand_sev)
        self.assertEqual(records, [])

    def test_case_present_in_only_one_run_is_not_classified(self) -> None:
        base = {"case-a": _metrics("case-a")}
        cand = {"case-b": _metrics("case-b", missed=("k",))}
        records = bd.classify_drift(base, cand, {}, {})
        self.assertEqual(records, [])

    def test_recovering_to_zero_missed_keys_is_not_a_drift_record(self) -> None:
        # The reverse direction of decision-flip is a resolution, handled by
        # the lifecycle's auto-close (see test_benchmark_drift_lifecycle.py),
        # never a new drift record.
        base = {"case-a": _metrics("case-a", missed=("sqli-key",))}
        cand = {"case-a": _metrics("case-a", missed=())}
        records = bd.classify_drift(base, cand, {}, {})
        self.assertEqual(records, [])

    def test_tolerance_is_configurable(self) -> None:
        base_sev = {"case-a": _severity("case-a", matched=10, exact=10)}
        cand_sev = {"case-a": _severity("case-a", matched=10, exact=9)}  # 0.1 drop
        records = bd.classify_drift(
            {}, {}, base_sev, cand_sev, severity_exact_rate_tolerance=Fraction(1, 20)
        )
        self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
