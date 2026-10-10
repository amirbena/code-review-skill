"""Termination safety for the benchmark process tree (Issue #660); stub CLI tree, no live model."""

from __future__ import annotations

import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from runtime_platform.benchmark.scripts import benchmark_termination as term
from tests.support.paths import REPO_ROOT

CASE = REPO_ROOT / "benchmark" / "corpus" / "correctness-off-by-one-pagination.yaml"
ROUTINE = REPO_ROOT / "runtime_platform" / "benchmark" / "scripts" / "run_benchmark_routine.py"
RUN_BENCHMARK = REPO_ROOT / "runtime_platform" / "benchmark" / "scripts" / "run_benchmark.py"
# The review CLI stub spawns a descendant of its own, records both pids, then hangs mid-case.
STUB = """#!/usr/bin/env python3
import os, subprocess, sys, time
if "reply with the single word" in " ".join(sys.argv):
    print("ok"); sys.exit(0)
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
open(os.environ["PID_FILE"], "w").write(f"{os.getpid()} {child.pid}")
time.sleep(60)
"""


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # a zombie awaiting reaping is not a running process
    state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(state) and not state.startswith("Z")


class TerminationTreeTests(unittest.TestCase):
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
        self.pid_file = root / "pids"
        self.results = root / "results.json"

    def start(self, argv: list[str]) -> subprocess.Popen:
        proc = subprocess.Popen(
            [sys.executable, *argv],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PID_FILE": str(self.pid_file)},
        )
        self.addCleanup(self._reap, proc)
        return proc

    def _reap(self, proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            proc.kill()
        proc.communicate()
        if self.pid_file.exists():
            for pid in map(int, self.pid_file.read_text().split()):
                if alive(pid):
                    os.kill(pid, signal.SIGKILL)

    def wait_for_pids(self) -> list[int]:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.pid_file.exists() and len(self.pid_file.read_text().split()) == 2:
                return list(map(int, self.pid_file.read_text().split()))
            time.sleep(0.1)
        self.fail("stub review CLI never started")

    def assert_gone(self, pids: list[int]) -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and any(alive(p) for p in pids):
            time.sleep(0.1)
        self.assertEqual([p for p in pids if alive(p)], [])

    def test_routine_sigterm_stops_child_and_review_tree_and_fails_closed(self) -> None:
        proc = self.start(
            [
                str(ROUTINE), "--mode", "selected", "--case-id", "correctness-off-by-one-pagination",
                "--corpus-dir", str(self.corpus), "--cli", str(self.stub), "--timeout", "120",
                "--runtime-version", "stub", "--results-out", str(self.results),
            ]
        )
        pids = self.wait_for_pids()
        proc.send_signal(signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 128 + signal.SIGTERM)
        self.assertEqual(stdout, "")
        self.assertRegex(stderr, r"\[terminated\] signal=SIGTERM phase=fixtures case=correctness-off-by-one-pagination")
        self.assertFalse(self.results.exists())
        self.assert_gone(pids)

    def test_run_benchmark_sigterm_stops_review_tree_and_names_case(self) -> None:
        proc = self.start(
            [str(RUN_BENCHMARK), "--corpus-dir", str(self.corpus), "--cli", str(self.stub), "--timeout", "120"]
        )
        pids = self.wait_for_pids()
        proc.send_signal(signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 128 + signal.SIGTERM)
        self.assertEqual(stdout, "")
        self.assertRegex(stderr, r"\[terminated\] signal=SIGTERM phase=case-review case=correctness-off-by-one-pagination")
        self.assert_gone(pids)


class TerminationHelperTests(unittest.TestCase):
    def test_a_signal_the_launcher_ignores_stays_ignored(self) -> None:
        previous = signal.signal(signal.SIGHUP, signal.SIG_IGN)
        self.addCleanup(signal.signal, signal.SIGHUP, previous)
        with term.terminate_on_signal():
            self.assertIs(signal.getsignal(signal.SIGHUP), signal.SIG_IGN)
            self.assertIsNot(signal.getsignal(signal.SIGTERM), signal.SIG_IGN)
        self.assertIs(signal.getsignal(signal.SIGHUP), signal.SIG_IGN)

    def test_terminated_reads_as_a_signal_name(self) -> None:
        self.assertEqual(str(term.Terminated(signal.SIGTERM)), "terminated by SIGTERM")

    def test_run_in_own_group_gives_the_cli_no_stdin(self) -> None:
        done = term.run_in_own_group(
            [sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"], cwd=".", timeout=20, env=None
        )
        self.assertEqual(done.stdout.strip(), "''")

    def test_handler_is_restored_and_second_signal_is_ignored(self) -> None:
        before = signal.getsignal(signal.SIGTERM)
        with self.assertRaises(term.Terminated) as ctx:
            with term.terminate_on_signal(lambda: ("p", "c")):
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(1)
        self.assertEqual((ctx.exception.phase, ctx.exception.case), ("p", "c"))
        self.assertEqual(term.terminated_line(ctx.exception), "[terminated] signal=SIGTERM phase=p case=c")
        self.assertIs(signal.getsignal(signal.SIGTERM), before)

    def test_stop_process_tree_escalates_for_a_sigterm_ignoring_child_within_bounds(self) -> None:
        code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('up', flush=True); time.sleep(60)"
        proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, start_new_session=True)
        proc.stdout.readline()
        began = time.monotonic()
        term.stop_process_tree(proc, grace_s=0.5)
        self.assertLess(time.monotonic() - began, 5)
        self.assertIsNotNone(proc.poll())
        proc.stdout.close()

    def test_run_in_own_group_timeout_kills_descendants(self) -> None:
        marker = "time.sleep(63.25)"
        code = f"import subprocess,sys,time;subprocess.Popen([sys.executable,'-c','import time;{marker}']);time.sleep(60)"
        with self.assertRaises(subprocess.TimeoutExpired):
            term.run_in_own_group([sys.executable, "-c", code], cwd=".", timeout=1.5, env=None, grace_s=0.5)
        deadline = time.monotonic() + 5
        while True:
            listing = subprocess.run(["ps", "-ax", "-o", "command="], capture_output=True, text=True).stdout
            if marker not in listing or time.monotonic() > deadline:
                break
            time.sleep(0.1)
        self.assertNotIn(marker, listing)


class TerminationAfterFixturesTests(unittest.TestCase):
    """A signal after the fixtures finished (drift, confirmation, seal) must leave neither results nor seal."""

    def test_results_out_and_seal_are_absent_when_terminated_before_the_seal(self) -> None:
        from unittest import mock

        from runtime_platform.benchmark.scripts import run_benchmark_routine as routine

        with tempfile.TemporaryDirectory() as tmp:
            results, seal_dir = Path(tmp) / "results.json", Path(tmp) / "sealed"
            args = routine.build_arg_parser().parse_args(
                ["--mode", "sentinel", "--cli", "stub", "--runtime-version", "v", "--results-out", str(results), "--seal-dir", str(seal_dir)]
            )
            inv = mock.Mock(output={"run": {}}, verification={}, timing=None)
            plan = routine.Plan("sentinel", [(None, tmp)], mock.Mock())
            with (
                mock.patch.object(routine, "_plan", return_value=plan),
                mock.patch.object(routine, "_load_manifest", return_value={}),
                mock.patch.object(routine, "_destination", return_value=None),
                mock.patch.object(routine, "_history_source", return_value=mock.Mock()),
                mock.patch.object(routine, "spec_sha256", return_value="x"),
                mock.patch.object(routine, "_git_sha", return_value="sha"),
                mock.patch.object(routine, "_git_ref", return_value="HEAD"),
                mock.patch.object(routine, "invoke", return_value=inv),
                mock.patch.object(routine, "build_sealed_run", side_effect=term.Terminated(signal.SIGTERM, "drift-confirmation", None)),
                mock.patch.object(routine, "_hand_off") as hand_off,
            ):
                with self.assertRaises(term.Terminated):
                    routine.run_benchmark_mode(args)
            self.assertFalse(results.exists())
            self.assertFalse(seal_dir.exists())
            hand_off.assert_not_called()


if __name__ == "__main__":
    unittest.main()
