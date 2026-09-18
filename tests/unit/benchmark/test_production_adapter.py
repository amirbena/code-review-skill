#!/usr/bin/env python3
"""Behavioural coverage for the production reviewer adapter (Issue #250).

Driven through the single production adapter module
(``runtime_platform/benchmark/scripts/benchmark_review_adapter.py``); this module never defines a
second normalizer or a second subprocess-invocation boundary. What is
proven here:

1. ``parse_review_output`` normalizes representative canonical-full-
   rendering Markdown into ``ProducedFinding`` objects: a single finding
   with a line, a finding with a line range, multiple findings, a genuine
   clean/no-findings report (``[]``, not an error), and a malformed report
   (raises, rather than being silently treated as clean);
2. the runtime-availability preflight check raises a clear,
   ``RuntimeUnavailableError`` when the configured executable cannot be
   found — proven against a nonexistent executable name, never against the
   real ``claude`` CLI;
3. the adapter's subprocess-invocation boundary, exercised through a stub
   executable script (never the real ``claude`` CLI): it runs with
   ``cwd=<workspace>``, captures stdout, and turns it into
   ``ProducedFinding`` objects; and a stub that exits non-zero makes the
   adapter raise, which is exactly what lets ``run_case``'s existing
   per-case ``reviewer-adapter-raised`` handling take over.

Real end-to-end execution against the actual ``claude`` CLI (skipped when
unavailable) is covered separately in
``tests/unit/benchmark/test_production_adapter_e2e.py``.
"""

from __future__ import annotations

import stat
import tempfile
import textwrap
import unittest
from pathlib import Path

from runtime_platform.benchmark.scripts.benchmark_review_adapter import (
    SKILL_PLUGIN_DIR,
    ProductionReviewerAdapter,
    RuntimeUnavailableError,
    check_runtime_available,
    parse_review_output,
    resolve_cli_executable,
    resolve_cli_extra_args,
)
import runtime_platform.benchmark.reference.benchmark_fixture as bf
import runtime_platform.benchmark.reference.benchmark_match as bm
from runtime_platform.benchmark.reference.benchmark_runner import ProducedFinding


class ParseReviewOutputTests(unittest.TestCase):
    def test_single_finding_with_line(self) -> None:
        report = textwrap.dedent(
            """
            ## Code Review

            **Result: ⚠️ Changes Requested**

            ### Findings

            #### F1 [P1] Retry can duplicate processing

            - **Location:** `app/retry.py:42`
            - **Evidence:** the retry loop re-runs the side effect before checking idempotency.
            - **Impact:** a transient failure can process the same job twice.
            - **Fix:** check the idempotency key before retrying.

            ### Decision
            **CHANGES REQUESTED**
            """
        )
        findings = parse_review_output(report)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertIsInstance(f, ProducedFinding)
        self.assertEqual(f.severity, "P1")
        self.assertEqual(f.location, {"path": "app/retry.py", "line": 42})
        # The claim carries the Evidence/Impact content too (issue #342),
        # not only the heading title — this is what lets the matcher's
        # claim-comparison step evaluate the actual defect claim.
        self.assertIn("Retry can duplicate processing", f.claim)
        self.assertIn("retry loop re-runs the side effect", f.claim)
        self.assertIn("process the same job twice", f.claim)

    def test_single_finding_with_line_range(self) -> None:
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            ### F3 [P2] Sync and async retry paths decide eligibility separately

            - **Location:** `app/retry.py:41-58`
            - **Evidence:** two divergent eligibility checks.
            - **Impact:** inconsistent retry behavior between the sync and async paths.
            - **Fix:** move eligibility into one shared helper.
            """
        )
        findings = parse_review_output(report)
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].location,
            {"path": "app/retry.py", "lines": {"start": 41, "end": 58}},
        )

    def test_multiple_findings(self) -> None:
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [P0] Command injection via unsanitized shell argument

            - **Location:** `app/exec.py:10`
            - **Evidence:** user input is interpolated into a shell string.
            - **Impact:** arbitrary command execution.
            - **Fix:** use an argument list, never shell=True with interpolated input.

            #### F2 [P2] Missing regression test for pagination boundary

            - **Location:** `app/pagination.py`
            - **Evidence:** no test pins page boundaries.
            - **Impact:** a future change could silently duplicate rows again.
            - **Fix:** add a test asserting no overlap between consecutive pages.
            """
        )
        findings = parse_review_output(report)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].severity, "P0")
        self.assertEqual(findings[0].location, {"path": "app/exec.py", "line": 10})
        self.assertEqual(findings[1].severity, "P2")
        self.assertEqual(findings[1].location, {"path": "app/pagination.py"})

    def test_clean_report_returns_empty_list(self) -> None:
        report = textwrap.dedent(
            """
            ## Code Review

            **Result: ✅ Review Clean**

            Safe to proceed: no blocking or non-blocking findings were identified.

            ### Decision
            **REVIEW CLEAN**

            No P0, P1, or P2 findings were identified in the reviewed implementation
            state.
            """
        )
        self.assertEqual(parse_review_output(report), [])

    def test_malformed_report_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_review_output("I couldn't complete the review due to an internal error.")

    def test_finding_with_unrecognized_severity_is_skipped_not_fatal(self) -> None:
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [WEIRD] Some anomalous heading

            - **Location:** `app/x.py:1`

            #### F2 [P1] A real finding

            - **Location:** `app/y.py:2`
            """
        )
        findings = parse_review_output(report)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "P1")

    def test_finding_without_location_is_skipped_not_fatal(self) -> None:
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [P1] A finding whose location line is missing

            - **Evidence:** something is wrong but no location was given.

            #### F2 [P2] A real, well-formed finding

            - **Location:** `app/y.py:2`
            """
        )
        findings = parse_review_output(report)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "P2")

    def test_non_numeric_location_tail_is_parsed_as_symbol(self) -> None:
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [P1] Off-by-one page end index duplicates a row

            - **Location:** `app/pagination.py:page`
            - **Evidence:** the page end index adds one to offset + page_size.
            - **Impact:** each page returns one extra item that also appears
              as the first item of the next page.
            """
        )
        findings = parse_review_output(report)
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].location, {"path": "app/pagination.py", "symbol": "page"}
        )

    def test_claim_excludes_fix_content(self) -> None:
        """Only Evidence/Impact/Details describe the defect claim itself;
        Fix is remediation guidance, not part of what the matcher should
        compare the expected claim against."""
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [P1] A real finding

            - **Location:** `app/y.py:2`
            - **Evidence:** concrete evidence text.
            - **Impact:** concrete impact text.
            - **Fix:** do this specific unrelated-to-claim correction.
            """
        )
        findings = parse_review_output(report)
        self.assertNotIn("unrelated-to-claim correction", findings[0].claim)
        self.assertIn("concrete evidence text", findings[0].claim)
        self.assertIn("concrete impact text", findings[0].claim)

    def test_defect_kind_captured_into_extra(self) -> None:
        """A rendered `Defect kind:` line (finding.md, "Defect
        classification") reaches `ProducedFinding.extra["defect_kind"]",
        mirroring the existing Evidence/Impact/Details extraction (issue
        #355) so the matcher's `defect_kind`-equality path
        (match-criteria.md §4.1) is actually exercised."""
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [P0] Command injection via unsanitized shell argument

            - **Location:** `app/exec.py:10`
            - **Evidence:** user input is interpolated into a shell string.
            - **Defect kind:** `command-injection`
            - **Impact:** arbitrary command execution.
            - **Fix:** use an argument list, never shell=True with interpolated input.
            """
        )
        findings = parse_review_output(report)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].extra.get("defect_kind"), "command-injection")
        # It is a distinct, backticked field, never folded into the free-text
        # claim the lexical fallback path compares.
        self.assertNotIn("command-injection", findings[0].claim)

    def test_defect_kind_absent_when_not_rendered(self) -> None:
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [P1] A real finding

            - **Location:** `app/y.py:2`
            - **Evidence:** concrete evidence text.
            - **Impact:** concrete impact text.
            - **Fix:** concrete fix text.
            """
        )
        findings = parse_review_output(report)
        self.assertEqual(len(findings), 1)
        self.assertNotIn("defect_kind", findings[0].extra)

    def test_defect_kind_does_not_leak_across_findings(self) -> None:
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [P0] Path traversal via unsanitized export filename

            - **Location:** `app/export.py:20`
            - **Evidence:** user input reaches the filesystem path unsanitized.
            - **Defect kind:** `path-traversal`
            - **Impact:** arbitrary file read.
            - **Fix:** sanitize/validate the export path.

            #### F2 [P2] Missing regression test for pagination boundary

            - **Location:** `app/pagination.py`
            - **Evidence:** no test pins page boundaries.
            - **Impact:** a future change could silently duplicate rows again.
            - **Fix:** add a test asserting no overlap between consecutive pages.
            """
        )
        findings = parse_review_output(report)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].extra.get("defect_kind"), "path-traversal")
        self.assertNotIn("defect_kind", findings[1].extra)


class DefectKindMatcherIntegrationTests(unittest.TestCase):
    """Issue #355 acceptance criteria: a matcher test that equal produced/
    expected `defect_kind` slugs reach `CORRESPONDS` through the *real*
    parse path — `parse_review_output` on rendered Markdown, not a
    hand-constructed `Descriptor`/`ProducedFinding` fixture."""

    def test_equal_defect_kind_reaches_corresponds_via_real_parse(self) -> None:
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [P0] Shell command built from unsanitized user name

            - **Location:** `auth/login.py:41`
            - **Evidence:** the display name is interpolated into a shell
              string passed to subprocess with shell=True.
            - **Defect kind:** `command-injection`
            - **Impact:** an attacker-controlled name can run arbitrary
              commands.
            - **Fix:** pass an argument list; never shell=True with
              interpolated input.
            """
        )
        produced = parse_review_output(report)
        self.assertEqual(len(produced), 1)

        expected = bf.ExpectedFinding(
            key="security-command-injection",
            severities=("P0",),
            required=True,
            location={"path": "auth/login.py", "lines": {"start": 40, "end": 40}, "symbol": "authenticate"},
            claim="unsanitized name reaches a shell true command injection",
            defect_kind="command-injection",
        )

        outcome = bm.match_pair(expected, produced[0])
        # Equal defect_kind slugs decide the defect axis outright
        # (match-criteria.md §4.1) — never the free-text claim fallback,
        # even though the produced claim shares almost no tokens with the
        # expected claim.
        self.assertEqual(outcome.defect, bm.DefectMatch.CORRESPONDS)
        self.assertEqual(outcome.result, bm.MatchResult.MATCH)

    def test_conflicting_defect_kind_reaches_unrelated_via_real_parse(self) -> None:
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [P1] Export path argument is not validated

            - **Location:** `report/export.py:88`
            - **Evidence:** the export path argument is used as-is with no
              validation before being passed to the filesystem.
            - **Defect kind:** `missing-input-validation`
            - **Impact:** a caller can supply a malformed path.
            - **Fix:** validate the argument before use.
            """
        )
        produced = parse_review_output(report)
        self.assertEqual(len(produced), 1)

        expected = bf.ExpectedFinding(
            key="security-path-traversal",
            severities=("P1",),
            required=True,
            location={"path": "report/export.py", "lines": {"start": 88, "end": 88}},
            claim="user controlled export path escapes the export directory path traversal",
            defect_kind="path-traversal",
        )

        outcome = bm.match_pair(expected, produced[0])
        self.assertEqual(outcome.defect, bm.DefectMatch.UNRELATED)
        self.assertEqual(outcome.result, bm.MatchResult.NO_MATCH)


class ConfigurationTests(unittest.TestCase):
    def test_resolve_cli_executable_default(self) -> None:
        self.assertEqual(resolve_cli_executable(env={}), "claude")

    def test_resolve_cli_executable_env_override(self) -> None:
        self.assertEqual(
            resolve_cli_executable(env={"BENCHMARK_REVIEW_CLI": "my-claude"}),
            "my-claude",
        )

    def test_resolve_cli_extra_args_parses_shell_quoting(self) -> None:
        self.assertEqual(
            resolve_cli_extra_args(env={"BENCHMARK_REVIEW_CLI_ARGS": "--model sonnet --flag 'a b'"}),
            ["--model", "sonnet", "--flag", "a b"],
        )

    def test_resolve_cli_extra_args_empty_by_default(self) -> None:
        self.assertEqual(resolve_cli_extra_args(env={}), [])


class _StubCliMixin:
    """Writes an executable stub script standing in for the real `claude`
    CLI, so the subprocess-invocation boundary is tested without depending
    on the real CLI at all."""

    def _write_stub(self, tmp: Path, *, stdout: str, exit_code: int = 0) -> Path:
        script = tmp / "stub-review-cli.py"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"sys.stdout.write({stdout!r})\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return script


class RuntimeAvailabilityTests(unittest.TestCase, _StubCliMixin):
    def test_missing_executable_raises_clear_error(self) -> None:
        with self.assertRaises(RuntimeUnavailableError) as ctx:
            check_runtime_available("definitely-not-a-real-benchmark-review-cli-xyz")
        message = str(ctx.exception)
        self.assertIn("definitely-not-a-real-benchmark-review-cli-xyz", message)
        self.assertIn("BENCHMARK_REVIEW_CLI", message)

    def test_present_and_usable_executable_returns_resolved_path(self) -> None:
        # A stub that exits 0 for any invocation (including the preflight's
        # own probe call) stands in for a present-and-working review CLI,
        # without depending on the real `claude` CLI being installed or
        # authenticated.
        with tempfile.TemporaryDirectory() as tmp:
            stub = self._write_stub(Path(tmp), stdout="**Result: ✅ Review Clean**\n", exit_code=0)
            resolved = check_runtime_available(str(stub))
            self.assertEqual(Path(resolved), stub)

    def test_present_but_unusable_executable_raises_clear_error(self) -> None:
        # A stub that exists and is executable (so `shutil.which` finds
        # it) but that fails when actually invoked — e.g. `claude` present
        # on PATH but unauthenticated, which prints "Not logged in" and
        # exits non-zero. The preflight must catch this, not just
        # "missing entirely".
        with tempfile.TemporaryDirectory() as tmp:
            stub = self._write_stub(
                Path(tmp), stdout="Not logged in · Please run /login\n", exit_code=1
            )
            with self.assertRaises(RuntimeUnavailableError) as ctx:
                check_runtime_available(str(stub))
            message = str(ctx.exception)
            self.assertIn(str(stub), message)
            self.assertIn("probe invocation", message)


class ProductionReviewerAdapterTests(unittest.TestCase, _StubCliMixin):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    def test_adapter_runs_with_workspace_cwd_and_parses_stdout(self) -> None:
        workspace = self.tmp_path / "workspace"
        workspace.mkdir()
        cwd_marker = workspace / "cwd-marker.txt"

        clean_report = "**Result: ✅ Review Clean**\n"
        stub = self.tmp_path / "stub.py"
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            "with open('cwd-marker.txt', 'w') as fh:\n"
            "    fh.write(os.getcwd())\n"
            f"sys.stdout.write({clean_report!r})\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

        adapter = ProductionReviewerAdapter(executable=str(stub))
        findings = adapter(workspace)

        self.assertEqual(findings, [])
        self.assertTrue(cwd_marker.exists())
        self.assertEqual(Path(cwd_marker.read_text(encoding="utf-8")).resolve(), workspace.resolve())

    def test_adapter_parses_findings_from_stub_output(self) -> None:
        workspace = self.tmp_path / "workspace2"
        workspace.mkdir()
        report = (
            "**Result: ⚠️ Changes Requested**\n\n"
            "#### F1 [P1] A real finding\n\n"
            "- **Location:** `app/y.py:2`\n"
        )
        stub = self._write_stub(self.tmp_path, stdout=report)
        adapter = ProductionReviewerAdapter(executable=str(stub))

        findings = adapter(workspace)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "P1")
        self.assertEqual(findings[0].location, {"path": "app/y.py", "line": 2})

    def test_adapter_raises_when_subprocess_exits_nonzero(self) -> None:
        workspace = self.tmp_path / "workspace3"
        workspace.mkdir()
        stub = self._write_stub(self.tmp_path, stdout="boom", exit_code=1)
        adapter = ProductionReviewerAdapter(executable=str(stub))

        with self.assertRaises(RuntimeError):
            adapter(workspace)

    def test_adapter_raises_when_output_unparseable(self) -> None:
        workspace = self.tmp_path / "workspace4"
        workspace.mkdir()
        stub = self._write_stub(self.tmp_path, stdout="not a review report at all")
        adapter = ProductionReviewerAdapter(executable=str(stub))

        with self.assertRaises(ValueError):
            adapter(workspace)

    def test_adapter_passes_plugin_dir_hint_pointing_at_this_checkout(self) -> None:
        """The adapter passes a best-effort ``--plugin-dir`` hint pointing at
        this checkout's own Skill directory, instead of relying purely on
        ambient discovery — proven by a stub that records its own argv.

        This proves only that the CLI *receives* this path as an argument;
        it does not and cannot prove the CLI actually loads/executes that
        Skill from it (this repository's ``skills/`` tree is not currently a
        valid Claude Code plugin directory, so recognition isn't guaranteed
        — see ``SKILL_PLUGIN_DIR``'s docstring). Verified runtime-to-Skill
        binding is out of scope for this manual tool; see issue #255."""
        workspace = self.tmp_path / "workspace5"
        workspace.mkdir()
        argv_marker = self.tmp_path / "argv.txt"
        stub = self.tmp_path / "argv-stub.py"
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"open({str(argv_marker)!r}, 'w').write('\\n'.join(sys.argv[1:]))\n"
            "sys.stdout.write('**Result: \u2705 Review Clean**\\n')\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)

        adapter = ProductionReviewerAdapter(executable=str(stub))
        adapter(workspace)

        argv = argv_marker.read_text(encoding="utf-8").splitlines()
        self.assertIn("--plugin-dir", argv)
        plugin_dir = argv[argv.index("--plugin-dir") + 1]
        plugin_path = Path(plugin_dir)
        self.assertTrue(plugin_path.is_absolute())
        self.assertEqual(plugin_path, SKILL_PLUGIN_DIR)
        self.assertTrue((plugin_path / "skills" / "local-code-review").is_dir())

    def test_adapter_raised_exception_is_absorbed_by_run_case_as_per_case_error(self) -> None:
        """Proves the integration point: an adapter failure (subprocess
        non-zero exit here) is exactly what makes
        ``benchmark_runner.run_case`` record a per-case
        ``reviewer-adapter-raised`` error rather than crashing the whole
        run — the correct place for a single case's review to fail, as
        opposed to the runtime-unavailable preflight check."""
        from runtime_platform.benchmark.reference import benchmark_fixture as bf
        from runtime_platform.benchmark.reference import benchmark_runner as br

        workspace_parent = self.tmp_path / "workspaces"
        workspace_parent.mkdir()
        stub = self._write_stub(self.tmp_path, stdout="boom", exit_code=1)
        adapter = ProductionReviewerAdapter(executable=str(stub))

        case = bf.parse_case(
            {
                "format": "benchmark-case/v2",
                "id": "stub-failure-case",
                "title": "stub",
                "input": {
                    "patch": "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
                    "base": {"x": "a\n"},
                },
                "expected": {"findings": []},
                "metadata": {
                    "taxonomy": {
                        "capability": ["unclassified"],
                        "policy_contract": ["unclassified"],
                        "risk_mode": ["unclassified"],
                        "affected_surface": ["unclassified"],
                    }
                },
            }
        )
        result = br.run_case(case, adapter, workspace_parent=workspace_parent)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.error, "reviewer-adapter-raised")


if __name__ == "__main__":
    unittest.main()
