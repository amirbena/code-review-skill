#!/usr/bin/env python3
"""Coverage for the `scripts/run_benchmark.py` CLI entrypoint (Issue #250).

Proves the one behavior the issue calls out explicitly: when the
configured review runtime is unavailable, the entrypoint exits non-zero
with a clear, actionable stderr message *before* touching the corpus —
never a fabricated clean result, never a silent no-op. Exercised as a real
subprocess (matching how a user actually runs this script) with
``BENCHMARK_REVIEW_CLI`` pointed at a nonexistent executable, so the test
never depends on the real `claude` CLI being installed.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "run_benchmark.py"


class RunBenchmarkCliRuntimeAvailabilityTests(unittest.TestCase):
    def _run(self, extra_env: dict) -> subprocess.CompletedProcess:
        env = {**os.environ, **extra_env}
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            env=env,
        )

    def test_missing_runtime_exits_nonzero_with_actionable_stderr(self) -> None:
        proc = self._run({"BENCHMARK_REVIEW_CLI": "definitely-not-a-real-benchmark-review-cli-xyz"})

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("definitely-not-a-real-benchmark-review-cli-xyz", proc.stderr)
        self.assertIn("BENCHMARK_REVIEW_CLI", proc.stderr)
        # Never fabricates a result: nothing that looks like a run/metrics
        # payload should reach stdout when the preflight check fails.
        self.assertEqual(proc.stdout.strip(), "")

    def test_present_but_broken_runtime_exits_nonzero_with_actionable_stderr(self) -> None:
        # Present on PATH (an absolute path `shutil.which` will resolve)
        # and executable, but fails when actually invoked — e.g. `claude`
        # installed but unauthenticated. Must be caught by the preflight
        # probe before any corpus/case work happens, exactly like the
        # "not found at all" case above.
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "broken-review-cli.py"
            stub.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "sys.stderr.write('Not logged in \\u00b7 Please run /login\\n')\n"
                "sys.exit(1)\n",
                encoding="utf-8",
            )
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

            proc = self._run({"BENCHMARK_REVIEW_CLI": str(stub)})

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("probe invocation", proc.stderr)
        self.assertEqual(proc.stdout.strip(), "")

    def test_missing_runtime_via_cli_flag_also_fails_fast(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--cli", "definitely-not-a-real-benchmark-review-cli-xyz"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("definitely-not-a-real-benchmark-review-cli-xyz", proc.stderr)


if __name__ == "__main__":
    unittest.main()
