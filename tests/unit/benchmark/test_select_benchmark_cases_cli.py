#!/usr/bin/env python3
"""Behavioral coverage for the selector CLI entrypoint (Issue #334).
Contract: runtime_platform/benchmark/selection.md §5.

Exercises ``runtime_platform/benchmark/scripts/select_benchmark_cases.py`` end to end
against a small synthetic index and PR classification file — never
against the live corpus index (that is exercised implicitly by every
other benchmark test that already depends on ``corpus-index.json``
staying in sync, e.g. ``tests/policy/benchmark/test_benchmark_index_sync.py``).
Proves: the emitted JSON matches
``benchmark_selection.build_explainability``'s shape exactly (no second,
CLI-local computation), the step-summary file is appended to (never
overwritten), and a missing/malformed taxonomy dimension in the input
file is rejected (fail-closed, via ``benchmark_taxonomy.validate_taxonomy``)
rather than silently coerced or defaulted.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime_platform.benchmark.scripts import select_benchmark_cases as cli
from runtime_platform.benchmark.reference import benchmark_selection as sel


class LoadPrClassificationTests(unittest.TestCase):
    def test_loads_a_well_formed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "classification.json"
            path.write_text(
                json.dumps(
                    {
                        "capability": ["security-boundary"],
                        "policy_contract": ["review-scope"],
                        "risk_mode": ["security"],
                        "affected_surface": ["shared-policy"],
                    }
                ),
                encoding="utf-8",
            )
            result = cli.load_pr_classification(path)
        self.assertEqual(result["capability"], ("security-boundary",))

    def test_rejects_a_file_missing_a_dimension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "classification.json"
            path.write_text(json.dumps({"capability": ["core"]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                cli.load_pr_classification(path)

    def test_rejects_a_non_object_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "classification.json"
            path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
            with self.assertRaises(ValueError):
                cli.load_pr_classification(path)

    def test_rejects_a_bare_string_value_instead_of_a_list(self) -> None:
        # A hand-edited file with `"capability": "core"` (a string, not a
        # list) must be rejected, never silently coerced into
        # `tuple("core")` == ('c', 'o', 'r', 'e').
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "classification.json"
            path.write_text(
                json.dumps(
                    {
                        "capability": "core",
                        "policy_contract": ["unclassified"],
                        "risk_mode": ["unclassified"],
                        "affected_surface": ["unclassified"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                cli.load_pr_classification(path)

    def test_rejects_an_unknown_taxonomy_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "classification.json"
            path.write_text(
                json.dumps(
                    {
                        "capability": ["not-a-real-capability"],
                        "policy_contract": ["unclassified"],
                        "risk_mode": ["unclassified"],
                        "affected_surface": ["unclassified"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                cli.load_pr_classification(path)


class MainCliTests(unittest.TestCase):
    def _write_index(self, tmp: Path) -> Path:
        index = {
            "capability": {"security-boundary": ["case-a"]},
            "policy_contract": {},
            "risk_mode": {},
            "affected_surface": {},
        }
        index_path = tmp / "index.json"
        index_path.write_text(json.dumps(index), encoding="utf-8")
        return index_path

    def test_emits_explainability_json_matching_the_reference_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            index_path = self._write_index(tmp)
            classification_path = tmp / "classification.json"
            classification_path.write_text(
                json.dumps(
                    {
                        "capability": ["security-boundary"],
                        "policy_contract": ["unclassified"],
                        "risk_mode": ["unclassified"],
                        "affected_surface": ["unclassified"],
                    }
                ),
                encoding="utf-8",
            )
            output_path = tmp / "out.json"

            exit_code = cli.main(
                [
                    "--pr-classification",
                    str(classification_path),
                    "--index-path",
                    str(index_path),
                    "--output",
                    str(output_path),
                ]
            )
            self.assertEqual(exit_code, 0)

            emitted = json.loads(output_path.read_text(encoding="utf-8"))
            index = json.loads(index_path.read_text(encoding="utf-8"))
            pr_classification = cli.load_pr_classification(classification_path)
            expected = json.loads(
                json.dumps(sel.build_explainability(sel.select_cases(index, pr_classification)))
            )
            self.assertEqual(emitted, expected)

    def test_step_summary_is_appended_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            index_path = self._write_index(tmp)
            classification_path = tmp / "classification.json"
            classification_path.write_text(
                json.dumps(
                    {
                        "capability": ["security-boundary"],
                        "policy_contract": ["unclassified"],
                        "risk_mode": ["unclassified"],
                        "affected_surface": ["unclassified"],
                    }
                ),
                encoding="utf-8",
            )
            step_summary_path = tmp / "summary.md"
            step_summary_path.write_text("# pre-existing content\n", encoding="utf-8")

            cli.main(
                [
                    "--pr-classification",
                    str(classification_path),
                    "--index-path",
                    str(index_path),
                    "--step-summary",
                    str(step_summary_path),
                    "--output",
                    str(tmp / "out.json"),
                ]
            )

            summary = step_summary_path.read_text(encoding="utf-8")
            self.assertIn("# pre-existing content", summary)
            self.assertIn("Benchmark selection (#334)", summary)

    def test_insufficient_coverage_never_fails_the_process(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            index_path = tmp / "empty_index.json"
            index_path.write_text(
                json.dumps({"capability": {}, "policy_contract": {}, "risk_mode": {}, "affected_surface": {}}),
                encoding="utf-8",
            )
            classification_path = tmp / "classification.json"
            classification_path.write_text(
                json.dumps(
                    {
                        "capability": ["security-boundary"],
                        "policy_contract": ["review-scope"],
                        "risk_mode": ["security"],
                        "affected_surface": ["shared-policy"],
                    }
                ),
                encoding="utf-8",
            )
            exit_code = cli.main(
                [
                    "--pr-classification",
                    str(classification_path),
                    "--index-path",
                    str(index_path),
                    "--output",
                    str(tmp / "out.json"),
                ]
            )
            self.assertEqual(exit_code, 0)
            emitted = json.loads((tmp / "out.json").read_text(encoding="utf-8"))
            self.assertEqual(emitted["outcome"], sel.OUTCOME_INSUFFICIENT_COVERAGE)


if __name__ == "__main__":
    unittest.main()
