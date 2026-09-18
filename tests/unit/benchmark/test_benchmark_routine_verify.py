#!/usr/bin/env python3
"""Fail-closed positive completion verification for Issue #415.

Proves ``verify_benchmark_output`` never treats a Routine's own non-zero
exit, a malformed/missing per-case shape, or an unexecuted case as passing
evidence — and that a genuinely well-formed run does pass.
"""

from __future__ import annotations

import json
import unittest

from runtime_platform.benchmark.scripts.benchmark_routine_verify import verify_benchmark_output


def _run_json(cases: list[dict], ok: bool = True) -> str:
    return json.dumps({"run": {"ok": ok, "cases": cases}})


class VerifyBenchmarkOutputTest(unittest.TestCase):
    def test_passes_on_well_formed_executed_run(self) -> None:
        stdout = _run_json(
            [{"id": "case-a", "input_kind": "diff", "status": "executed", "produced_findings": []}]
        )
        result = verify_benchmark_output(stdout, exit_code=0)
        self.assertTrue(result.passed)
        self.assertEqual(result.case_count, 1)
        self.assertEqual(result.case_ids, ("case-a",))

    def test_fails_closed_on_nonzero_exit_with_no_stdout(self) -> None:
        # The check_runtime_available preflight failure path: stderr-only,
        # no stdout JSON at all.
        result = verify_benchmark_output("", exit_code=1)
        self.assertFalse(result.passed)
        self.assertEqual(result.reason, "runtime-unavailable-or-execution-error")

    def test_fails_closed_on_unparseable_stdout(self) -> None:
        result = verify_benchmark_output("not json", exit_code=0)
        self.assertFalse(result.passed)
        self.assertTrue(result.reason.startswith("parse-error"))

    def test_fails_closed_on_missing_run_key(self) -> None:
        result = verify_benchmark_output(json.dumps({"unexpected": True}), exit_code=0)
        self.assertFalse(result.passed)
        self.assertEqual(result.reason, "missing-run-key")

    def test_fails_closed_on_empty_cases(self) -> None:
        result = verify_benchmark_output(_run_json([]), exit_code=0)
        self.assertFalse(result.passed)
        self.assertEqual(result.reason, "no-cases-executed")

    def test_fails_closed_on_error_status_case(self) -> None:
        stdout = _run_json(
            [{"id": "case-a", "input_kind": "diff", "status": "error", "error": "runtime unavailable"}],
            ok=False,
        )
        result = verify_benchmark_output(stdout, exit_code=1)
        self.assertFalse(result.passed)
        self.assertIn("case-a", result.reason)
        self.assertIn("runtime unavailable", result.reason)

    def test_fails_closed_on_malformed_case_shape(self) -> None:
        result = verify_benchmark_output(_run_json([{"id": "case-a"}]), exit_code=0)
        self.assertFalse(result.passed)
        self.assertTrue(result.reason.startswith("malformed-case-shape"))

    def test_fails_closed_on_executed_case_missing_produced_findings(self) -> None:
        stdout = _run_json([{"id": "case-a", "input_kind": "diff", "status": "executed"}])
        result = verify_benchmark_output(stdout, exit_code=0)
        self.assertFalse(result.passed)
        self.assertIn("missing produced_findings", result.reason)

    def test_fails_closed_when_run_ok_is_false_despite_executed_cases(self) -> None:
        stdout = _run_json(
            [{"id": "case-a", "input_kind": "diff", "status": "executed", "produced_findings": []}],
            ok=False,
        )
        result = verify_benchmark_output(stdout, exit_code=1)
        self.assertFalse(result.passed)
        self.assertEqual(result.reason, "run-not-ok")


if __name__ == "__main__":
    unittest.main()
