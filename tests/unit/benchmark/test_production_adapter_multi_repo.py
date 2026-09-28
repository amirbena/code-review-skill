#!/usr/bin/env python3
"""Behavioural coverage for the multi-repository extension to the
production reviewer adapter (Issue #558, parent #555, impl #556).

Driven through the single production adapter module
(``runtime_platform/benchmark/scripts/benchmark_review_adapter.py``) every other adapter
test uses; this module never defines a second normalizer or a second
subprocess-invocation boundary. Proven here, beyond what
``test_production_adapter.py`` already covers for the single-repository
call shape:

1. calling the adapter with a ``Mapping[str, Path]`` (never a bare
   ``Path``) builds a prompt naming every admitted alias and its absolute
   path, and never leaks anything about an unadmitted sibling (the adapter
   is only ever handed the admitted mapping in the first place — see
   ``test_benchmark_runner_multi_repo.py``);
2. the subprocess runs with ``cwd`` set to the admitted workspaces' shared
   parent directory — never a path outside it;
3. ``<alias>:<path>:<line>`` locations in the CLI's stdout parse into
   ``location.repo_alias`` + the ordinary path/line/lines/symbol fields,
   using the alias set the adapter itself was called with — never guessed;
4. a single-repository call (a bare ``Path``) is entirely unaffected: no
   ``repo_alias`` is ever produced, and a location that happens to contain
   a colon is parsed exactly as before this extension.
"""

from __future__ import annotations

import stat
import tempfile
import textwrap
import unittest
from pathlib import Path

from runtime_platform.benchmark.scripts.benchmark_review_adapter import (
    ProductionReviewerAdapter,
    parse_review_output,
)


class _StubCliMixin:
    def _write_stub(self, directory: Path, *, stdout: str, exit_code: int = 0) -> Path:
        stub = directory / "stub.py"
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"sys.stdout.write({stdout!r})\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        return stub

    def _write_argv_and_cwd_recording_stub(self, directory: Path, argv_marker: Path, cwd_marker: Path) -> Path:
        stub = directory / "recording-stub.py"
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            f"open({str(argv_marker)!r}, 'w').write('\\x1e'.join(sys.argv[1:]))\n"
            f"open({str(cwd_marker)!r}, 'w').write(os.getcwd())\n"
            "sys.stdout.write('**Result: \u2705 Review Clean**\\n')\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        return stub


class ParseReviewOutputKnownAliasesTests(unittest.TestCase):
    def test_alias_prefixed_location_splits_into_repo_alias_and_path(self) -> None:
        report = textwrap.dedent(
            """
            **Result: ⚠️ Changes Requested**

            #### F1 [P1] A cross-repository finding

            - **Location:** `billing-worker:billing/reconcile.py:12`
            """
        )
        findings = parse_review_output(report, known_aliases=("api-service", "billing-worker"))
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].location,
            {"path": "billing/reconcile.py", "line": 12, "repo_alias": "billing-worker"},
        )

    def test_alias_prefixed_location_with_line_range(self) -> None:
        report = "**Result: ⚠️ Changes Requested**\n\n#### F1 [P2] X\n\n- **Location:** `repo-a:app/x.py:10-15`\n"
        findings = parse_review_output(report, known_aliases=("repo-a", "repo-b"))
        self.assertEqual(
            findings[0].location,
            {"path": "app/x.py", "lines": {"start": 10, "end": 15}, "repo_alias": "repo-a"},
        )

    def test_unknown_alias_prefix_is_not_split_off(self) -> None:
        """A prefix that looks like `alias:` but was never in the admitted
        set (e.g. a typo, or a path segment that happens to precede a
        colon) is left as ordinary path content — never guessed."""
        report = "**Result: ⚠️ Changes Requested**\n\n#### F1 [P2] X\n\n- **Location:** `unknown-repo:app/x.py:10`\n"
        findings = parse_review_output(report, known_aliases=("repo-a", "repo-b"))
        self.assertEqual(findings[0].location, {"path": "unknown-repo:app/x.py", "line": 10})

    def test_no_known_aliases_never_produces_repo_alias(self) -> None:
        """Default behavior (no ``known_aliases`` argument at all) is
        byte-for-byte what every pre-existing single-repository test in
        ``test_production_adapter.py`` already pins."""
        report = "**Result: ⚠️ Changes Requested**\n\n#### F1 [P2] X\n\n- **Location:** `app/x.py:10`\n"
        findings = parse_review_output(report)
        self.assertEqual(findings[0].location, {"path": "app/x.py", "line": 10})
        self.assertNotIn("repo_alias", findings[0].location)


class ProductionReviewerAdapterMultiRepoTests(unittest.TestCase, _StubCliMixin):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    def _admitted_workspaces(self) -> dict[str, Path]:
        parent = self.tmp_path / "workspaces"
        repo_a = parent / "repo-a"
        repo_b = parent / "repo-b"
        repo_a.mkdir(parents=True)
        repo_b.mkdir(parents=True)
        return {"repo-a": repo_a, "repo-b": repo_b}

    def test_prompt_names_every_admitted_alias_and_absolute_path(self) -> None:
        workspaces = self._admitted_workspaces()
        argv_marker = self.tmp_path / "argv.txt"
        cwd_marker = self.tmp_path / "cwd.txt"
        stub = self._write_argv_and_cwd_recording_stub(self.tmp_path, argv_marker, cwd_marker)

        adapter = ProductionReviewerAdapter(executable=str(stub))
        adapter(workspaces)

        argv = argv_marker.read_text(encoding="utf-8").split("\x1e")
        prompt = argv[argv.index("-p") + 1]
        self.assertIn(f"- repo-a: {workspaces['repo-a'].resolve()}", prompt)
        self.assertIn(f"- repo-b: {workspaces['repo-b'].resolve()}", prompt)
        self.assertIn("multi-repository Review Target", prompt)
        self.assertIn("no other local repository is part of this Review Target", prompt)

    def test_subprocess_cwd_is_the_admitted_workspaces_shared_parent(self) -> None:
        workspaces = self._admitted_workspaces()
        argv_marker = self.tmp_path / "argv.txt"
        cwd_marker = self.tmp_path / "cwd.txt"
        stub = self._write_argv_and_cwd_recording_stub(self.tmp_path, argv_marker, cwd_marker)

        adapter = ProductionReviewerAdapter(executable=str(stub))
        adapter(workspaces)

        recorded_cwd = Path(cwd_marker.read_text(encoding="utf-8")).resolve()
        for path in workspaces.values():
            self.assertEqual(path.resolve().parent, recorded_cwd)

    def test_findings_are_parsed_with_the_admitted_aliases_known(self) -> None:
        workspaces = self._admitted_workspaces()
        report = (
            "**Result: ⚠️ Changes Requested**\n\n"
            "#### F1 [P1] A cross-repository finding\n\n"
            "- **Location:** `repo-b:billing/reconcile.py:12`\n"
        )
        stub = self._write_stub(self.tmp_path, stdout=report)
        adapter = ProductionReviewerAdapter(executable=str(stub))

        findings = adapter(workspaces)
        self.assertEqual(len(findings), 1)
        self.assertEqual(
            findings[0].location,
            {"path": "billing/reconcile.py", "line": 12, "repo_alias": "repo-b"},
        )

    def test_clean_multi_repo_report_returns_empty_list(self) -> None:
        workspaces = self._admitted_workspaces()
        stub = self._write_stub(self.tmp_path, stdout="**Result: \u2705 Review Clean**\n")
        adapter = ProductionReviewerAdapter(executable=str(stub))
        self.assertEqual(adapter(workspaces), [])

    def test_adapter_raises_when_multi_repo_subprocess_exits_nonzero(self) -> None:
        workspaces = self._admitted_workspaces()
        stub = self._write_stub(self.tmp_path, stdout="boom", exit_code=1)
        adapter = ProductionReviewerAdapter(executable=str(stub))
        with self.assertRaises(RuntimeError):
            adapter(workspaces)

    def test_single_repo_call_is_dispatched_separately_from_multi_repo(self) -> None:
        """A bare ``Path`` still takes the pre-existing single-repository
        path — the dispatch on ``isinstance(workspace, Mapping)`` never
        misroutes a ``Path`` (which is not a ``Mapping``)."""
        workspace = self.tmp_path / "single"
        workspace.mkdir()
        argv_marker = self.tmp_path / "argv.txt"
        cwd_marker = self.tmp_path / "cwd.txt"
        stub = self._write_argv_and_cwd_recording_stub(self.tmp_path, argv_marker, cwd_marker)

        adapter = ProductionReviewerAdapter(executable=str(stub))
        adapter(workspace)

        prompt = argv_marker.read_text(encoding="utf-8").split("\x1e")[
            argv_marker.read_text(encoding="utf-8").split("\x1e").index("-p") + 1
        ]
        self.assertNotIn("multi-repository Review Target", prompt)
        self.assertEqual(Path(cwd_marker.read_text(encoding="utf-8")).resolve(), workspace.resolve())


if __name__ == "__main__":
    unittest.main()
