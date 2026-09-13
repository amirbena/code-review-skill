#!/usr/bin/env python3
"""End-to-end coverage for the production reviewer adapter (Issue #250),
conditional on the real review runtime actually being available.

This test never fabricates success when the runtime is unavailable. It
checks two things before attempting the real path, and skips with a clear
reason (rather than faking a clean/empty result) if either fails:

1. ``shutil.which("claude")`` (the configured default,
   ``scripts.benchmark_review_adapter.DEFAULT_CLI``) — is the executable on
   PATH at all;
2. a lightweight probe invocation of that CLI actually succeeds — the
   binary being on PATH is not sufficient by itself (e.g. it may be
   installed but not authenticated, which exits non-zero with "Not logged
   in" rather than reviewing anything).

When both checks pass, it drives one real corpus case through the
production adapter end-to-end via ``run_selected`` and asserts only that
the pipeline executes and that metrics can be computed from the result —
never specific finding content, since a real LLM's output is not
deterministic.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest

from scripts.benchmark_review_adapter import DEFAULT_CLI, ProductionReviewerAdapter
from tests.reference.benchmark import benchmark_metrics as bm
from tests.reference.benchmark import benchmark_runner as br
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus"
REAL_CASE_ID = "correctness-off-by-one-pagination"


def _probe_runtime() -> str | None:
    """Return None if the real review runtime is actually usable, else a
    human-readable reason it is not (used as the skip reason)."""
    if not shutil.which(DEFAULT_CLI):
        return f"real review runtime ({DEFAULT_CLI!r}) not found on PATH"
    try:
        probe = subprocess.run(
            [DEFAULT_CLI, "-p", "reply with the single word: ok", "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as exc:  # noqa: BLE001 - any probe failure means "not usable here"
        return f"probe invocation of {DEFAULT_CLI!r} raised: {exc}"
    if probe.returncode != 0:
        return (
            f"probe invocation of {DEFAULT_CLI!r} exited {probe.returncode} "
            f"(e.g. not authenticated): {probe.stderr.strip()[:300]!r}"
        )
    return None


_SKIP_REASON = _probe_runtime()


@unittest.skipUnless(
    _SKIP_REASON is None,
    f"skipping the live end-to-end path rather than fabricating a result — {_SKIP_REASON}",
)
class ProductionAdapterEndToEndTests(unittest.TestCase):
    def test_real_case_executes_through_the_real_runtime(self) -> None:
        adapter = ProductionReviewerAdapter(timeout=600.0)
        run_result = br.run_selected(CORPUS_DIR, REAL_CASE_ID, adapter)

        self.assertTrue(run_result.ok, run_result.error)
        self.assertEqual(len(run_result.case_results), 1)
        case_result = run_result.case_results[0]
        self.assertEqual(case_result.status, "executed")
        for finding in case_result.produced_findings:
            self.assertIsInstance(finding, br.ProducedFinding)

        from tests.reference.benchmark import benchmark_fixture as bf
        import yaml

        case = bf.parse_case(
            yaml.safe_load((CORPUS_DIR / f"{REAL_CASE_ID}.yaml").read_text(encoding="utf-8"))
        )
        metrics = bm.compute_run_metrics([case], run_result)
        self.assertEqual(len(metrics.as_dict()["cases"]), 1)


if __name__ == "__main__":
    unittest.main()
