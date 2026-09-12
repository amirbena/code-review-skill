#!/usr/bin/env python3
"""Behavioural coverage for the benchmark runner (Issue #52).

Contract: docs/benchmark/runner-contract.md. Driven through the single
test-only reference runner (tests/reference/benchmark/benchmark_runner.py); this
module never defines a second one. What is proven here:

1. a run executes the whole on-disk corpus and a single selected case, and
   emits a stable machine-readable per-case result;
2. every case executes in an isolated, disposable workspace that is a real
   materialization of the fixture input, and is cleaned up afterwards —
   on both the success and the failure path;
3. the repository-safety regression from the issue's Validation section: a
   deliberately dirty source repository (staged + unstaged + untracked) is
   byte-for-byte unchanged after a passing run, after an induced failing
   case, with no benchmark-created residue;
4. run exit status reflects execution health, never whether reviewers
   found defects.

Matching produced findings to a fixture's expectations and scoring are out
of scope (Issues #41 / #53).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.reference.benchmark import benchmark_fixture as bf
from tests.reference.benchmark import benchmark_runner as br
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus"

_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "T",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "T",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_TERMINAL_PROMPT": "0",
}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={**os.environ, **_GIT_ENV},
        check=True,
    ).stdout.strip()


# --- reviewer adapters (test doubles) -------------------------------------


def clean_reviewer(_workspace: Path):
    return []


def noisy_reviewer(workspace: Path):
    # Returns blocking findings regardless of the code — proves a run with
    # many "defects" is still an execution success.
    return [
        br.ProducedFinding(severity="P0", location={"path": "x", "line": 1}, claim="a"),
        br.ProducedFinding(severity="P1", location="file:y", claim="b"),
    ]


def inspecting_reviewer(seen: list):
    def _review(workspace: Path):
        seen.append(Path(workspace))
        return []

    return _review


def recording_reviewer(record: dict):
    """Records the workspace path and, for the pagination case, the
    post-image content of the file the patch touches — proving the patch
    was really applied in the workspace."""

    def _review(workspace: Path):
        record["workspace"] = Path(workspace)
        record["is_git_repo"] = (Path(workspace) / ".git").is_dir()
        target = Path(workspace) / "app" / "pagination.py"
        if target.is_file():
            record["content"] = target.read_text(encoding="utf-8")
        return []

    return _review


# --- helpers ------------------------------------------------------------


def _dirty_source_repo(parent: Path) -> Path:
    repo = Path(tempfile.mkdtemp(prefix="src-", dir=str(parent)))
    _git(repo, "init", "-q", "-b", "main", ".")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "kept.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "also.py").write_text("y = 2\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "branch", "feature/pre-existing")
    # representative pre-existing dirt: staged edit, unstaged edit, untracked
    (repo / "kept.py").write_text("x = 1  # staged change\n", encoding="utf-8")
    _git(repo, "add", "kept.py")
    (repo / "also.py").write_text("y = 2  # unstaged change\n", encoding="utf-8")
    (repo / "scratch.txt").write_text("untracked\n", encoding="utf-8")
    return repo


def _repo_ref_origin(parent: Path) -> tuple[Path, str]:
    work = Path(tempfile.mkdtemp(prefix="rr-work-", dir=str(parent)))
    _git(work, "init", "-q", "-b", "main", ".")
    _git(work, "config", "commit.gpgsign", "false")
    (work / "mod.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "c1")
    sha = _git(work, "rev-parse", "HEAD")
    origin = Path(tempfile.mkdtemp(prefix="rr-origin-", dir=str(parent))) / "origin.git"
    _git(parent, "clone", "-q", "--bare", str(work), str(origin))
    return origin, sha


def _case(data: dict) -> bf.BenchmarkCase:
    return bf.parse_case(data)


class CorpusExecutionTests(unittest.TestCase):
    def test_run_executes_the_full_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = br.run_corpus(CORPUS_DIR, clean_reviewer, workspace_parent=Path(tmp))
        self.assertTrue(run.ok)
        self.assertEqual(run.exit_code, 0)
        ids = {r.id for r in run.case_results}
        on_disk = {p.stem for p in CORPUS_DIR.glob("*.yaml")}
        self.assertEqual(ids, on_disk)
        self.assertTrue(all(r.status == "executed" for r in run.case_results))

    def test_run_executes_a_single_selected_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = br.run_selected(
                CORPUS_DIR, "security-command-injection", clean_reviewer,
                workspace_parent=Path(tmp),
            )
        self.assertTrue(run.ok)
        self.assertEqual([r.id for r in run.case_results], ["security-command-injection"])

    def test_unknown_single_case_id_is_a_run_failure_not_a_no_op(self) -> None:
        run = br.run_selected(CORPUS_DIR, "does-not-exist", clean_reviewer)
        self.assertFalse(run.ok)
        self.assertNotEqual(run.exit_code, 0)
        self.assertEqual(run.error, "unknown-case-id")
        self.assertEqual(run.case_results, ())

    def test_per_case_result_shape_is_stable_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = br.run_corpus(CORPUS_DIR, noisy_reviewer, workspace_parent=Path(tmp))
        with tempfile.TemporaryDirectory() as tmp:
            b = br.run_corpus(CORPUS_DIR, noisy_reviewer, workspace_parent=Path(tmp))
        self.assertEqual(a.as_dict(), b.as_dict())
        one = next(r for r in a.case_results if r.id == "security-command-injection")
        self.assertEqual(
            one.as_dict(),
            {
                "id": "security-command-injection",
                "input_kind": "patch",
                "status": "executed",
                "produced_findings": [
                    {"severity": "P0", "location": {"path": "x", "line": 1}, "claim": "a"},
                    {"severity": "P1", "location": "file:y", "claim": "b"},
                ],
            },
        )

    def test_finding_defects_is_not_a_runner_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run = br.run_corpus(CORPUS_DIR, noisy_reviewer, workspace_parent=Path(tmp))
        self.assertTrue(run.ok)
        self.assertEqual(run.exit_code, 0)
        self.assertTrue(all(r.produced_findings for r in run.case_results))

    def test_malformed_yaml_fixture_fails_the_run_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp)
            (corpus / "bad.yaml").write_text("a:\n  - b\n c\n", encoding="utf-8")
            run = br.run_corpus(corpus, clean_reviewer)
        self.assertFalse(run.ok)
        self.assertEqual(run.error, "corpus-parse-failed")
        self.assertEqual(run.case_results, ())
        self.assertNotEqual(run.exit_code, 0)


class IsolationTests(unittest.TestCase):
    def test_reviewer_sees_a_real_materialized_workspace(self) -> None:
        record: dict = {}
        with tempfile.TemporaryDirectory() as tmp:
            run = br.run_selected(
                CORPUS_DIR, "correctness-off-by-one-pagination", recording_reviewer(record),
                workspace_parent=Path(tmp),
            )
            self.assertTrue(run.ok)
            ws = record["workspace"]
            self.assertTrue(str(ws).startswith(tmp), "workspace is under our parent, not a source checkout")
            self.assertTrue(record["is_git_repo"], "workspace is a real git repo")
            # the patch was applied in the workspace: post-image content present
            self.assertIn("offset + page_size + 1", record["content"])
        self.assertFalse(ws.exists(), "workspace must be cleaned up after the case")

    def test_workspace_is_cleaned_up_on_the_success_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            run = br.run_corpus(CORPUS_DIR, clean_reviewer, workspace_parent=parent)
            self.assertTrue(run.ok)
            self.assertEqual(list(parent.iterdir()), [], "no workspace residue")

    def test_patch_that_does_not_apply_is_a_per_case_error_and_is_cleaned_up(self) -> None:
        bad = _case(
            {
                "format": "benchmark-case/v1",
                "id": "synthetic-bad-patch",
                "title": "patch will not apply",
                "input": {
                    "patch": (
                        "diff --git a/nope.txt b/nope.txt\n"
                        "--- a/nope.txt\n+++ b/nope.txt\n"
                        "@@ -1 +1 @@\n-old line\n+new line\n"
                    )
                },
                "expected": {"findings": []},
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            run = br.run_cases([bad], clean_reviewer, workspace_parent=parent)
            self.assertTrue(run.ok, "a per-case patch failure is not a run failure")
            (res,) = run.case_results
            self.assertEqual(res.status, "error")
            self.assertEqual(res.error, "patch-did-not-apply")
            self.assertEqual(list(parent.iterdir()), [], "failed case still cleaned up")

    def test_reviewer_that_raises_is_a_per_case_error_and_is_cleaned_up(self) -> None:
        def boom(_ws: Path):
            raise RuntimeError("adapter blew up")

        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            run = br.run_selected(
                CORPUS_DIR, "no-op-comment-and-rename", boom, workspace_parent=parent
            )
            self.assertTrue(run.ok)
            (res,) = run.case_results
            self.assertEqual(res.status, "error")
            self.assertEqual(res.error, "reviewer-adapter-raised")
            self.assertEqual(list(parent.iterdir()), [])

    def test_repo_ref_input_runs_in_an_isolated_clone(self) -> None:
        seen: list[Path] = []
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            origin, sha = _repo_ref_origin(parent)
            case = _case(
                {
                    "format": "benchmark-case/v1",
                    "id": "synthetic-repo-ref",
                    "title": "repo_ref isolation",
                    "input": {"repo_ref": {"repo": "local/x", "commit": sha}},
                    "expected": {"findings": []},
                }
            )
            run = br.run_cases(
                [case],
                inspecting_reviewer(seen),
                workspace_parent=parent,
                repo_ref_resolver=lambda ref: origin,
            )
            self.assertTrue(run.ok)
            (res,) = run.case_results
            self.assertEqual(res.status, "executed")
            self.assertEqual(res.input_kind, "repo_ref")
            (ws,) = seen
            self.assertNotEqual(ws.resolve(), origin.resolve())
        self.assertFalse(ws.exists(), "isolated clone cleaned up")

    def test_pr_repo_ref_is_an_explicit_setup_error_not_a_wrong_checkout(self) -> None:
        # A `pr` ref needs GitHub retrieval (out of scope); the reference
        # runner must fail explicitly rather than silently check out `base`
        # or the clone's default branch.
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            origin, _sha = _repo_ref_origin(parent)
            src = _dirty_source_repo(parent)
            before = br.capture_repo_state(src)
            case = _case(
                {
                    "format": "benchmark-case/v1",
                    "id": "synthetic-pr-ref",
                    "title": "pr ref is not materializable here",
                    "input": {"repo_ref": {"repo": "local/x", "pr": 7}},
                    "expected": {"findings": []},
                }
            )
            run = br.run_cases(
                [case], clean_reviewer, source_repo=src, workspace_parent=parent,
                repo_ref_resolver=lambda ref: origin,
            )
            self.assertTrue(run.ok, "a per-case setup failure is not a run failure")
            (res,) = run.case_results
            self.assertEqual(res.status, "error")
            self.assertEqual(res.error, "workspace-setup-failed")
            self.assertEqual(br.capture_repo_state(src), before)


class SourceRepositorySafetyTests(unittest.TestCase):
    """The issue's Validation section: a deliberately dirty source repo is
    byte-for-byte unchanged after passing and failing runs, no residue."""

    def _snapshot(self, repo: Path) -> br.RepoState:
        return br.capture_repo_state(repo)

    def test_dirty_source_repo_is_unchanged_after_a_passing_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            src = _dirty_source_repo(parent)
            before = self._snapshot(src)
            wsp = Path(tempfile.mkdtemp(prefix="wsp-", dir=str(parent)))
            run = br.run_corpus(
                CORPUS_DIR, noisy_reviewer, source_repo=src, workspace_parent=wsp
            )
            self.assertTrue(run.ok)
            self.assertEqual(self._snapshot(src), before)
            self.assertEqual(list(wsp.iterdir()), [], "no workspace residue")
            # explicit: no benchmark-created branch or stash entry
            self.assertEqual(before.branches, self._snapshot(src).branches)
            self.assertEqual(before.stash, self._snapshot(src).stash)

    def test_dirty_source_repo_is_unchanged_through_induced_failures(self) -> None:
        bad_patch = _case(
            {
                "format": "benchmark-case/v1",
                "id": "synthetic-bad-patch",
                "title": "will not apply",
                "input": {
                    "patch": "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
                },
                "expected": {"findings": []},
            }
        )

        def boom(_ws: Path):
            raise RuntimeError("kaboom")

        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            src = _dirty_source_repo(parent)
            before = self._snapshot(src)
            wsp = Path(tempfile.mkdtemp(prefix="wsp-", dir=str(parent)))

            r1 = br.run_cases([bad_patch], clean_reviewer, source_repo=src, workspace_parent=wsp)
            self.assertTrue(r1.ok)
            self.assertEqual(r1.case_results[0].error, "patch-did-not-apply")

            r2 = br.run_selected(
                CORPUS_DIR, "quality-duplicated-branch-logic", boom,
                source_repo=src, workspace_parent=wsp,
            )
            self.assertTrue(r2.ok)
            self.assertEqual(r2.case_results[0].error, "reviewer-adapter-raised")

            self.assertEqual(self._snapshot(src), before)
            self.assertEqual(list(wsp.iterdir()), [], "no residue after failing cases")

    def test_runner_detects_and_reports_a_mutated_source_checkout(self) -> None:
        # The runner never hands a protected checkout to the adapter; this
        # exercises the before/after integrity net directly by mutating the
        # source repo from within the reviewer.
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            src = _dirty_source_repo(parent)

            def mutating(_ws: Path):
                (src / "intrusion.txt").write_text("!", encoding="utf-8")
                return []

            run = br.run_selected(
                CORPUS_DIR, "correctness-off-by-one-pagination", mutating,
                source_repo=src, workspace_parent=parent,
            )
        self.assertFalse(run.ok)
        self.assertNotEqual(run.exit_code, 0)
        self.assertEqual(run.error, "source-checkout-mutated")

    def test_content_only_mutation_of_pre_existing_dirt_is_detected(self) -> None:
        # `git status --porcelain` codes are unchanged by a content-only
        # edit to an already-dirty file; the snapshot must still catch it
        # (contract §4 "byte for byte").
        for target, kind in (
            ("also.py", "pre-existing unstaged-modified tracked file"),
            ("scratch.txt", "pre-existing untracked file"),
        ):
            with self.subTest(mutation=kind):
                with tempfile.TemporaryDirectory() as tmp:
                    parent = Path(tmp)
                    src = _dirty_source_repo(parent)
                    porcelain_before = br.capture_repo_state(src).porcelain

                    def append_bytes(_ws: Path, _t=target):
                        (src / _t).write_text("EXTRA\n", encoding="utf-8")
                        return []

                    run = br.run_selected(
                        CORPUS_DIR, "no-op-comment-and-rename", append_bytes,
                        source_repo=src, workspace_parent=parent,
                    )
                    porcelain_after = br.capture_repo_state(src).porcelain
                # porcelain codes really are unchanged...
                self.assertEqual(porcelain_before, porcelain_after)
                # ...but the run still fails on the content digest / diff.
                self.assertFalse(run.ok)
                self.assertEqual(run.error, "source-checkout-mutated")

    def test_failed_cleanup_is_a_run_level_execution_failure(self) -> None:
        def refuse_cleanup(_p: Path):
            raise OSError("cannot remove")

        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            run = br.run_selected(
                CORPUS_DIR, "no-op-comment-and-rename", clean_reviewer,
                workspace_parent=parent, cleanup=refuse_cleanup,
            )
            # tidy the leaked workspace ourselves so TemporaryDirectory cleanup succeeds
            for leftover in parent.iterdir():
                shutil.rmtree(leftover, ignore_errors=True)
        self.assertFalse(run.ok)
        self.assertEqual(run.error, "cleanup-failed")
        self.assertNotEqual(run.exit_code, 0)


class ReferenceModuleTests(unittest.TestCase):
    def test_module_is_declared_test_only(self) -> None:
        head = (REPO_ROOT / "tests" / "reference" / "benchmark" / "benchmark_runner.py").read_text(
            encoding="utf-8"
        )[:600]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_runner_consumes_the_single_fixture_validator(self) -> None:
        raw = (REPO_ROOT / "tests" / "reference" / "benchmark" / "benchmark_runner.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("from tests.reference.benchmark import benchmark_fixture as bf", raw)


if __name__ == "__main__":
    unittest.main()
