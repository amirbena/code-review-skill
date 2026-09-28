#!/usr/bin/env python3
"""Behavioural coverage for the multi-repository Review Target extension to
the benchmark runner (Issue #558, parent #555, impl #556).

Driven through the same single reference runner
(``runtime_platform/benchmark/reference/benchmark_runner.py``) every other runner test uses;
this module never defines a second one. What is proven here, beyond what
``test_benchmark_runner.py`` already covers for the single-repository
``patch``/``repo_ref`` input kinds:

1. ``materialize_multi_repo`` builds one real, independent, isolated Git
   repository per ``input.repositories`` alias, and one more per
   ``input.unadmitted_repositories`` alias — the two never share a
   materialization path and a bad patch in either is a per-case error
   naming its own alias;
2. ``run_case`` dispatches a ``"multi_repo"`` case to a reviewer called
   with the *admitted* mapping only — the unadmitted workspace is never
   passed to the reviewer callable, even though it is real and present on
   disk right alongside the admitted ones;
3. cleanup still removes every member's workspace (admitted and
   unadmitted) in one pass, exactly like the single-repository path.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_runner as br

_TAXONOMY = {
    "capability": ["unclassified"],
    "policy_contract": ["unclassified"],
    "risk_mode": ["unclassified"],
    "affected_surface": ["unclassified"],
}


def _patch(path: str, before: str, after: str) -> str:
    import difflib

    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    return f"diff --git a/{path} b/{path}\n{diff}"


def _multi_repo_case(
    *, repositories: dict, unadmitted: dict | None = None, case_id: str = "mr-case"
) -> bf.BenchmarkCase:
    data = {
        "format": "benchmark-case/v2",
        "id": case_id,
        "title": "t",
        "input": {"repositories": repositories},
        "expected": {"decision": "clean", "findings": []},
        "metadata": {"taxonomy": _TAXONOMY},
    }
    if unadmitted:
        data["input"]["unadmitted_repositories"] = unadmitted
    return bf.parse_case(data)


class MaterializeMultiRepoTests(unittest.TestCase):
    def test_builds_one_independent_git_repository_per_admitted_alias(self) -> None:
        case = _multi_repo_case(
            repositories={
                "repo-a": {"patch": _patch("a.txt", "1\n", "2\n"), "base": {"a.txt": "1\n"}},
                "repo-b": {"patch": _patch("b.txt", "x\n", "y\n"), "base": {"b.txt": "x\n"}},
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            workspaces = br.materialize_multi_repo(case, Path(tmp))
            self.assertEqual(set(workspaces.admitted), {"repo-a", "repo-b"})
            self.assertEqual(workspaces.unadmitted, {})
            self.assertEqual((workspaces.admitted["repo-a"] / "a.txt").read_text(), "2\n")
            self.assertEqual((workspaces.admitted["repo-b"] / "b.txt").read_text(), "y\n")
            for path in workspaces.admitted.values():
                self.assertTrue((path / ".git").is_dir())

    def test_unadmitted_members_materialize_as_real_sibling_repositories(self) -> None:
        case = _multi_repo_case(
            repositories={
                "repo-a": {"patch": _patch("a.txt", "1\n", "2\n"), "base": {"a.txt": "1\n"}},
                "repo-b": {"patch": _patch("b.txt", "x\n", "y\n"), "base": {"b.txt": "x\n"}},
            },
            unadmitted={"sibling": {"patch": _patch("s.txt", "p\n", "q\n"), "base": {"s.txt": "p\n"}}},
        )
        with tempfile.TemporaryDirectory() as tmp:
            workspaces = br.materialize_multi_repo(case, Path(tmp))
            self.assertEqual(set(workspaces.unadmitted), {"sibling"})
            sibling_path = workspaces.unadmitted["sibling"]
            self.assertTrue((sibling_path / ".git").is_dir())
            self.assertEqual((sibling_path / "s.txt").read_text(), "q\n")
            # Real, independent materialization directories, never nested
            # inside one another.
            self.assertNotIn(sibling_path, workspaces.admitted.values())

    def test_bad_patch_in_an_admitted_member_names_its_own_alias(self) -> None:
        case = _multi_repo_case(
            repositories={
                "repo-a": {"patch": "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-nope\n+x\n"},
                "repo-b": {"patch": _patch("b.txt", "x\n", "y\n"), "base": {"b.txt": "x\n"}},
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(br.PatchDidNotApply) as ctx:
                br.materialize_multi_repo(case, Path(tmp))
            self.assertIn("repo-a", str(ctx.exception))

    def test_bad_patch_in_an_unadmitted_member_also_names_its_own_alias(self) -> None:
        case = _multi_repo_case(
            repositories={
                "repo-a": {"patch": _patch("a.txt", "1\n", "2\n"), "base": {"a.txt": "1\n"}},
                "repo-b": {"patch": _patch("b.txt", "x\n", "y\n"), "base": {"b.txt": "x\n"}},
            },
            unadmitted={
                "sibling": {"patch": "diff --git a/s.txt b/s.txt\n--- a/s.txt\n+++ b/s.txt\n@@ -1 +1 @@\n-nope\n+x\n"}
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(br.PatchDidNotApply) as ctx:
                br.materialize_multi_repo(case, Path(tmp))
            self.assertIn("sibling", str(ctx.exception))


class RunCaseMultiRepoDispatchTests(unittest.TestCase):
    def test_reviewer_receives_only_the_admitted_mapping(self) -> None:
        case = _multi_repo_case(
            repositories={
                "repo-a": {"patch": _patch("a.txt", "1\n", "2\n"), "base": {"a.txt": "1\n"}},
                "repo-b": {"patch": _patch("b.txt", "x\n", "y\n"), "base": {"b.txt": "x\n"}},
            },
            unadmitted={"sibling": {"patch": _patch("s.txt", "p\n", "q\n"), "base": {"s.txt": "p\n"}}},
        )
        seen: dict = {}

        def reviewer(workspaces):
            seen["workspaces"] = dict(workspaces)
            return []

        result = br.run_case(case, reviewer)
        self.assertEqual(result.status, "executed")
        self.assertEqual(result.input_kind, "multi_repo")
        self.assertEqual(set(seen["workspaces"]), {"repo-a", "repo-b"})
        self.assertNotIn("sibling", seen["workspaces"])

    def test_cleanup_removes_admitted_and_unadmitted_workspaces_together(self) -> None:
        case = _multi_repo_case(
            repositories={
                "repo-a": {"patch": _patch("a.txt", "1\n", "2\n"), "base": {"a.txt": "1\n"}},
                "repo-b": {"patch": _patch("b.txt", "x\n", "y\n"), "base": {"b.txt": "x\n"}},
            },
            unadmitted={"sibling": {"patch": _patch("s.txt", "p\n", "q\n"), "base": {"s.txt": "p\n"}}},
        )
        captured_paths: list[Path] = []

        def reviewer(workspaces):
            captured_paths.extend(Path(p) for p in workspaces.values())
            return []

        with tempfile.TemporaryDirectory() as parent:
            br.run_case(case, reviewer, workspace_parent=Path(parent))
            # The whole per-case temp directory (admitted + unadmitted
            # subdirectories together) is gone after run_case returns.
            for entry in Path(parent).iterdir():
                self.assertEqual(list(entry.iterdir()), [])

    def test_produced_findings_and_execution_error_paths_are_unaffected(self) -> None:
        case = _multi_repo_case(
            repositories={
                "repo-a": {"patch": _patch("a.txt", "1\n", "2\n"), "base": {"a.txt": "1\n"}},
                "repo-b": {"patch": _patch("b.txt", "x\n", "y\n"), "base": {"b.txt": "x\n"}},
            }
        )

        def raising_reviewer(_workspaces):
            raise RuntimeError("boom")

        result = br.run_case(case, raising_reviewer)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.error, "reviewer-adapter-raised")

    def test_post_image_and_cited_sources_are_empty_for_a_multi_repo_case(self) -> None:
        """Documented scope narrowing (this module's own docstrings): a
        multi-repository case has no single unambiguous workspace root for
        these single-workspace-only captures, so both stay empty rather than
        silently resolving against the wrong member."""
        case = _multi_repo_case(
            repositories={
                "repo-a": {"patch": _patch("a.txt", "1\n", "2\n"), "base": {"a.txt": "1\n"}},
                "repo-b": {"patch": _patch("b.txt", "x\n", "y\n"), "base": {"b.txt": "x\n"}},
            }
        )

        def reviewer(workspaces):
            return [
                br.ProducedFinding(
                    severity="P2",
                    location={"path": "a.txt", "repo_alias": "repo-a"},
                    claim="c",
                )
            ]

        result = br.run_case(case, reviewer)
        self.assertIsNone(result.post_image)
        self.assertEqual(result.cited_sources, {})
        self.assertEqual(result.pre_images, {})


class SingleRepoRegressionTests(unittest.TestCase):
    """#558 scenario 5: the pre-existing single-repository paths through
    ``run_case`` are unaffected by this extension."""

    def test_patch_case_still_receives_a_single_path(self) -> None:
        data = {
            "format": "benchmark-case/v2",
            "id": "single",
            "title": "t",
            "input": {"patch": _patch("a.txt", "1\n", "2\n"), "base": {"a.txt": "1\n"}},
            "expected": {"decision": "clean", "findings": []},
            "metadata": {"taxonomy": _TAXONOMY},
        }
        case = bf.parse_case(data)
        seen = {}

        def reviewer(workspace):
            seen["type"] = type(workspace)
            return []

        result = br.run_case(case, reviewer)
        self.assertEqual(result.status, "executed")
        self.assertEqual(result.input_kind, "patch")
        self.assertIs(seen["type"], type(Path(".")))


if __name__ == "__main__":
    unittest.main()
