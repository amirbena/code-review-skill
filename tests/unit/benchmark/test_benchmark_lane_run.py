"""`invoke` (the per-invocation fail-closed boundary) and the spec digest (#470)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime_platform.benchmark.scripts import benchmark_lane_run as lane_run
from tests.support.benchmark_records import make_case, run_output


def _completed(stdout: str, returncode: int = 0) -> mock.Mock:
    return mock.Mock(stdout=stdout, stderr="", returncode=returncode)


def _invoke(completed: mock.Mock, case_id: str | None = None):
    with mock.patch.object(lane_run.subprocess, "run", return_value=completed) as run:
        return run, lane_run.invoke("stub-cli", 12.5, case_id, "/corpus/dir")


class InvokeTests(unittest.TestCase):
    def test_verified_output_returns_an_invocation(self) -> None:
        output = run_output([make_case("a")])
        _, inv = _invoke(_completed(json.dumps(output)))
        self.assertEqual(inv.output, output)
        self.assertTrue(inv.verification["passed"])
        self.assertEqual(inv.verification["case_ids"], ["a"])

    def test_sentinel_style_call_passes_no_case_id(self) -> None:
        run, _ = _invoke(_completed(json.dumps(run_output([make_case("a")]))))
        argv = run.call_args.args[0]
        self.assertEqual(argv[argv.index("--corpus-dir") + 1], "/corpus/dir")
        self.assertEqual(argv[argv.index("--cli") + 1], "stub-cli")
        self.assertEqual(argv[argv.index("--timeout") + 1], "12.5")
        self.assertNotIn("--case-id", argv)

    def test_a_case_id_is_passed_through(self) -> None:
        run, _ = _invoke(_completed(json.dumps(run_output([make_case("a")]))), case_id="a")
        argv = run.call_args.args[0]
        self.assertEqual(argv[argv.index("--case-id") + 1], "a")

    def test_a_case_that_did_not_execute_fails_closed(self) -> None:
        bad = {"run": {"ok": False, "cases": [{"id": "a", "status": "error", "error": "boom"}]}}
        with self.assertRaisesRegex(lane_run.RoutineExecutionError, "fail-closed"):
            _invoke(_completed(json.dumps(bad), returncode=1))

    def test_non_zero_exit_with_no_output_fails_closed(self) -> None:
        with self.assertRaisesRegex(lane_run.RoutineExecutionError, "runtime-unavailable"):
            _invoke(_completed("", returncode=1))

    def test_unparseable_output_fails_closed(self) -> None:
        with self.assertRaises(lane_run.RoutineExecutionError):
            _invoke(_completed("not json"))


class SpecDigestTests(unittest.TestCase):
    MANIFEST = {"confirmation": {"reruns": 2}}

    def _digest(self, text: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            doc.write_text(text, encoding="utf-8")
            with mock.patch.object(lane_run, "ROUTINE_DOC", doc):
                return lane_run.spec_sha256(self.MANIFEST)

    @staticmethod
    def _doc(prose: str = "intro", template: str = "1. run it\n") -> str:
        return f"{prose}\n\n## 9. Routine prompt template\n\n```text\n{template}```\n\n### 9.1 Two lanes\n\ntail\n"

    def test_edits_outside_the_template_do_not_change_it(self) -> None:
        self.assertEqual(self._digest(self._doc()), self._digest(self._doc(prose="reworded intro")))

    def test_a_template_edit_changes_it(self) -> None:
        self.assertNotEqual(self._digest(self._doc()), self._digest(self._doc(template="1. run something else\n")))

    def test_the_manifest_is_part_of_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "doc.md"
            doc.write_text(self._doc(), encoding="utf-8")
            with mock.patch.object(lane_run, "ROUTINE_DOC", doc):
                self.assertNotEqual(lane_run.spec_sha256({"a": 1}), lane_run.spec_sha256({"a": 2}))

    def test_a_missing_template_fails_closed(self) -> None:
        with self.assertRaises(lane_run.RoutineExecutionError):
            self._digest("no template here\n")

    def test_the_committed_doc_has_a_template(self) -> None:
        self.assertIn("run_benchmark_routine.py", lane_run._prompt_template())


if __name__ == "__main__":
    unittest.main()
