"""Per-case lifecycle diagnostics for `run_benchmark.py` (Issue #659); stub CLI, no live model."""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from runtime_platform.benchmark.scripts import benchmark_progress as prog
from runtime_platform.benchmark.scripts import benchmark_review_adapter as adapter_mod
from runtime_platform.benchmark.scripts import run_benchmark as rb
from tests.support.paths import REPO_ROOT

CASE = REPO_ROOT / "benchmark" / "corpus" / "correctness-off-by-one-pagination.yaml"
STUB = """#!/usr/bin/env python3
import os, sys, time
if "reply with the single word" in " ".join(sys.argv):
    print("ok"); sys.exit(0)
mode = os.environ["STUB_MODE"]
if mode == "exit":
    sys.stderr.write("SECRET-STDERR-BODY"); sys.exit(7)
if mode == "hang":
    time.sleep(30)
if mode == "garbage":
    print("SECRET-MODEL-OUTPUT not a report"); sys.exit(0)
print("**Result:** no findings")
"""


class CaseLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.corpus = root / "corpus"
        self.corpus.mkdir()
        shutil.copy(CASE, self.corpus / CASE.name)
        self.stub = root / "stub-cli.py"
        self.stub.write_text(STUB, encoding="utf-8")
        self.stub.chmod(self.stub.stat().st_mode | stat.S_IEXEC)

    def run_main(self, mode: str, timeout: str = "20") -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"STUB_MODE": mode}):
            with redirect_stdout(out), redirect_stderr(err):
                code = rb.main(["--corpus-dir", str(self.corpus), "--cli", str(self.stub), "--timeout", timeout])
        return code, out.getvalue(), err.getvalue()

    def lines(self, err: str) -> list[str]:
        return [re.sub(r"^\[\+\d\d:\d\d\] ", "", ln) for ln in err.splitlines()]

    def test_success_prints_start_stages_and_done_with_index(self) -> None:
        code, out, err = self.run_main("ok")
        lines = self.lines(err)
        self.assertEqual(code, 0)
        for expected in (
            "[run] stage=probe START",
            "[case 1/1] START correctness-off-by-one-pagination",
            "[case 1/1] stage=review START correctness-off-by-one-pagination",
            "[case 1/1] stage=parse START correctness-off-by-one-pagination",
            "[run] stage=metrics START",
        ):
            self.assertIn(expected, lines)
        self.assertTrue(any(re.match(r"\[case 1/1\] DONE correctness-off-by-one-pagination [\d.]+s findings=0$", ln) for ln in lines))
        self.assertIn("run", json.loads(out))

    def test_stdout_is_json_only(self) -> None:
        _, out, _ = self.run_main("ok")
        self.assertEqual(set(json.loads(out)), {"run", "metrics", "severity", "duplicate_noise", "citation_fidelity"})
        self.assertNotIn("[case", out)

    def _error_line(self, err: str) -> str:
        return next(ln for ln in self.lines(err) if "ERROR correctness-off-by-one-pagination" in ln)

    def test_cli_nonzero_exit_names_case_stage_and_category(self) -> None:
        code, out, err = self.run_main("exit")
        self.assertEqual(code, 0)  # run_benchmark exit code is unchanged; the Routine verifier fails the run
        line = self._error_line(err)
        self.assertEqual(json.loads(out)["run"]["cases"][0]["status"], "error")
        self.assertIn("[case 1/1]", line)
        self.assertIn("stage=review", line)
        self.assertIn("category=cli-exit-7", line)
        self.assertNotIn("SECRET-STDERR-BODY", err)

    def test_timeout_is_categorized(self) -> None:
        code, out, err = self.run_main("hang", timeout="1")
        self.assertEqual(code, 0)  # run_benchmark exit code is unchanged; the Routine verifier fails the run
        line = self._error_line(err)
        self.assertIn("stage=review", line)
        self.assertIn("category=timeout", line)

    def test_parse_failure_is_categorized_without_model_output(self) -> None:
        code, out, err = self.run_main("garbage")
        self.assertEqual(code, 0)  # run_benchmark exit code is unchanged; the Routine verifier fails the run
        line = self._error_line(err)
        self.assertIn("stage=parse", line)
        self.assertIn("category=parse-failure", line)
        self.assertNotIn("SECRET-MODEL-OUTPUT", err)

    def test_failed_case_keeps_the_reviewer_adapter_raised_marker_in_the_payload(self) -> None:
        _, out, _ = self.run_main("exit")
        case = json.loads(out)["run"]["cases"][0]
        self.assertEqual(case["error"], "reviewer-adapter-raised")
        self.assertEqual(set(case), {"id", "input_kind", "status", "error"})


class DiagnosticsAreIsolatedTests(unittest.TestCase):
    def test_a_raising_observer_does_not_change_the_result(self) -> None:
        from runtime_platform.benchmark.reference import benchmark_fixture as bf
        from runtime_platform.benchmark.reference import benchmark_runner as br

        def boom(*_args: object) -> None:
            raise OSError("stderr closed")

        data = __import__("yaml").safe_load(CASE.read_text(encoding="utf-8"))
        case = bf.parse_case(data)
        plain = br.run_cases([case], lambda ws: []).case_results[0]
        observed = br.run_cases([case], lambda ws: [], observer=boom).case_results[0]
        self.assertEqual(plain.as_dict(), observed.as_dict())

    def test_a_raising_stage_hook_does_not_fail_the_review(self) -> None:
        def boom(_name: str) -> None:
            raise OSError("stderr closed")

        adapter = adapter_mod.ProductionReviewerAdapter(executable="x", extra_args=[], timeout=1)
        adapter.stage_hook = boom
        with mock.patch.object(adapter_mod.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="**Result:** clean", stderr="")):
            self.assertEqual(adapter(Path(".")), [])

    def test_a_closed_stderr_does_not_stall_the_child_stream(self) -> None:
        from runtime_platform.benchmark.scripts import benchmark_lane_run as lane_run
        from tests.support.benchmark_records import make_case, run_output

        class Broken:
            def write(self, _s: str) -> int:
                raise BrokenPipeError

            def flush(self) -> None:
                raise BrokenPipeError

        lines = [f"line {i}\n" for i in range(5)]
        child = mock.Mock(stdout=io.StringIO(json.dumps(run_output([make_case("a")]))), stderr=iter(lines), wait=lambda: 0)
        with mock.patch.object(lane_run.subprocess, "Popen", return_value=child), mock.patch.object(lane_run.sys, "stderr", Broken()):
            inv = lane_run.invoke("stub", 5.0, "a", "corpus")
        self.assertTrue(inv.verification["passed"])


class CleanupFailureEventTests(unittest.TestCase):
    def test_cleanup_failure_still_emits_a_terminal_done(self) -> None:
        import yaml

        from runtime_platform.benchmark.reference import benchmark_fixture as bf
        from runtime_platform.benchmark.reference import benchmark_runner as br

        case = bf.parse_case(yaml.safe_load(CASE.read_text(encoding="utf-8")))
        events: list[tuple[str, str]] = []

        def observer(event: str, case_id: str, _i: int, _n: int, result: object) -> None:
            events.append((event, getattr(result, "error", None)))

        def bad_cleanup(_p: Path) -> None:
            raise OSError("nope")

        result = br.run_cases([case], lambda ws: [], cleanup=bad_cleanup, observer=observer)
        self.assertEqual(result.error, "cleanup-failed")
        self.assertEqual(events, [("start", None), ("done", "cleanup-failed")])


class FailureCategoryTests(unittest.TestCase):
    def test_categories(self) -> None:
        cat = adapter_mod.failure_category
        self.assertEqual(cat(subprocess.TimeoutExpired("x", 1)), "timeout")
        self.assertEqual(cat(adapter_mod.ReviewCliExitError("m", 3)), "cli-exit-3")
        self.assertEqual(cat(adapter_mod.ReviewParseError("m")), "parse-failure")
        self.assertEqual(cat(RuntimeError("secret")), "adapter-error")


class CaseLifecycleUnitTests(unittest.TestCase):
    def test_setup_failure_reports_runner_error_as_category(self) -> None:
        err = io.StringIO()
        life = prog.CaseLifecycle(prog.ProgressLog(stream=err), adapter_mod.failure_category)
        life.observe("start", "c", 2, 4, None)
        life.observe("done", "c", 2, 4, mock.Mock(status="error", error="patch-did-not-apply"))
        self.assertIn("[case 2/4] START c", err.getvalue())
        self.assertIn("ERROR c", err.getvalue())
        self.assertIn("stage=setup category=patch-did-not-apply", err.getvalue())


if __name__ == "__main__":
    unittest.main()
