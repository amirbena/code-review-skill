"""Tests for the fail-safe FAST/FULL CI test router."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from scripts.validation import ci_test_route as router
from tests.support.paths import REPO_ROOT

ROUTER = REPO_ROOT / "scripts" / "validation" / "ci_test_route.py"

ALLOWLISTED = (
    ".gitignore",
    "policies/validation-and-clean-exit.md",
    "policies/nested/x.md",
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "README.md",
    ".github/ISSUE_TEMPLATE/bug.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/AUTOMATION.md",
)

INTEGRATION_SENSITIVE = (
    "skills/local-code-review/SKILL.md",
    "shared/policies/review-scope.md",
    "capabilities/x/capability.yaml",
    "scripts/packaging/package-skills.sh",
    "scripts/release/release_worthiness.py",
    "scripts/skill_metadata/x.py",
    "scripts/sandbox/x.py",
    "scripts/validation/validate-skill-metadata.py",
    "CHANGELOG.md",
    "LICENSE",
    "distribution/x.md",
    "dist/skills/x/SKILL.md",
    "runtime_platform/benchmark/x.py",
    "docs/ARCHITECTURE.md",
    "tests/unit/test_x.py",
    ".github/workflows/release-publish.yml",
    ".github/CODEOWNERS",
    "requirements-dev.txt",
)

NEAR_MISSES = (
    "Docs/a.md",
    "./README.md",
    "policiesx/a.md",
    "policies",
    "policies/",
    "sub/README.md",
    "README.md.bak",
    "readme.md",
    "skills/local-code-review/README.md",
    ".github/ISSUE_TEMPLATE",
    "new/x",
    "NEW.md",
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


class ClassifyTests(unittest.TestCase):
    def test_each_allowlisted_path_is_fast(self) -> None:
        for path in ALLOWLISTED:
            with self.subTest(path=path):
                self.assertEqual(router.classify([path]).tier, router.FAST)

    def test_each_integration_sensitive_category_is_full(self) -> None:
        for path in INTEGRATION_SENSITIVE:
            with self.subTest(path=path):
                result = router.classify([path])
                self.assertEqual(result.tier, router.FULL)
                self.assertEqual(result.first_full_path, path)

    def test_unknown_paths_and_near_misses_are_full(self) -> None:
        for path in NEAR_MISSES:
            with self.subTest(path=path):
                self.assertEqual(router.classify([path]).tier, router.FULL)

    def test_router_and_workflow_changes_are_full(self) -> None:
        for path in ("scripts/validation/ci_test_route.py", ".github/workflows/validate.yml"):
            with self.subTest(path=path):
                self.assertEqual(router.classify([path]).tier, router.FULL)

    def test_mixed_change_set_is_full_and_names_first_forcing_path(self) -> None:
        result = router.classify(["README.md", "shared/x.md", "skills/y.md"])
        self.assertEqual(result.tier, router.FULL)
        self.assertEqual(result.first_full_path, "shared/x.md")

    def test_empty_change_set_is_full(self) -> None:
        self.assertEqual(router.classify([]).tier, router.FULL)


class RouteTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "t")
        self._write("policies/x.md", "p\n")
        self._write("skills/y.md", "s\n")
        self._write("shared/z.md", "z\n")
        self.base = self._commit("base")

    def _write(self, rel: str, text: str) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _commit(self, message: str) -> str:
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "--allow-empty", "-m", message)
        return _git(self.repo, "rev-parse", "HEAD")

    def _route(self, head: str) -> router.Route:
        return router.safe_route("pull_request", self.repo, self.base, head)

    def test_allowlisted_edit_is_fast(self) -> None:
        self._write("policies/x.md", "changed\n")
        self.assertEqual(self._route(self._commit("edit")).tier, router.FAST)

    def test_renames_across_the_boundary_are_full(self) -> None:
        for old, new in (("policies/x.md", "skills/x.md"), ("skills/y.md", "policies/y.md")):
            with self.subTest(old=old, new=new):
                _git(self.repo, "checkout", "-q", "--detach", self.base)
                _git(self.repo, "mv", old, new)
                head = self._commit("rename")
                self.assertEqual(set(router.changed_paths(self.repo, self.base, head)), {old, new})
                self.assertEqual(self._route(head).tier, router.FULL)

    def test_deletions(self) -> None:
        _git(self.repo, "rm", "-q", "policies/x.md")
        self.assertEqual(self._route(self._commit("delete policy")).tier, router.FAST)
        _git(self.repo, "rm", "-q", "shared/z.md")
        self.base = _git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(self._route(self._commit("delete shared")).tier, router.FULL)

    def test_three_dot_diff_ignores_base_commits_merged_after_the_fork(self) -> None:
        _git(self.repo, "checkout", "-q", "-b", "pr")
        self._write("README.md", "r\n")
        head = self._commit("pr")
        _git(self.repo, "checkout", "-q", "main")
        self._write("shared/z.md", "moved on\n")
        self.base = self._commit("main moves")
        self.assertEqual(self._route(head).tier, router.FAST)

    def test_empty_change_set_is_full(self) -> None:
        self.assertEqual(self._route(self._commit("empty")).tier, router.FULL)

    def test_git_failure_is_full(self) -> None:
        result = self._route("0" * 40)
        self.assertEqual((result.tier, result.reason), (router.FULL, "git diff failed"))

    def test_missing_sha_or_non_pull_request_event_is_full(self) -> None:
        self._write("README.md", "r\n")
        head = self._commit("readme")
        self.assertEqual(router.safe_route("pull_request", self.repo, "", head).tier, router.FULL)
        self.assertEqual(router.safe_route("pull_request", self.repo, self.base, None).tier, router.FULL)
        for event in ("push", "workflow_dispatch", ""):
            with self.subTest(event=event):
                self.assertEqual(router.safe_route(event, self.repo, self.base, head).tier, router.FULL)

    def test_router_exception_is_full(self) -> None:
        with mock.patch.object(router, "changed_paths", side_effect=RuntimeError("boom")):
            result = self._route("HEAD")
        self.assertEqual(result.tier, router.FULL)
        self.assertIn("RuntimeError", result.reason)

    def test_unrecognized_tier_is_full(self) -> None:
        with mock.patch.object(router, "classify", return_value=router.Route("FAST", "x")):
            self.assertEqual(self._route("HEAD").tier, router.FULL)


class CliTests(unittest.TestCase):
    def test_route_writes_tier_output_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output, summary = Path(tmp) / "out", Path(tmp) / "summary"
            with redirect_stdout(StringIO()):
                code = router.main(
                    ["route", "--event-name", "push", "--github-output", str(output), "--step-summary", str(summary)]
                )
            self.assertEqual(code, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "tier=full\n")
            text = summary.read_text(encoding="utf-8")
        self.assertIn("Tier: **FULL**", text)
        self.assertIn("Reason: non-pull_request event (push)", text)

    def test_tier_is_written_last_so_a_failed_write_leaves_it_unset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            with redirect_stdout(StringIO()), self.assertRaises(OSError):
                router.main(["route", "--event-name", "push", "--github-output", str(output), "--step-summary", tmp])
            self.assertFalse(output.exists())

    def test_summary_names_the_first_path_that_forced_full(self) -> None:
        text = router.summary_markdown(router.classify(["README.md", "shared/x.md"]))
        self.assertIn("First path that forced FULL: `shared/x.md`", text)


class FastSuiteTests(unittest.TestCase):
    def test_fast_ids_are_full_ids_minus_exactly_integration(self) -> None:
        full = {t.id() for t in router._iter_tests(unittest.defaultTestLoader.discover(str(REPO_ROOT / "tests"), top_level_dir=str(REPO_ROOT)))}
        fast = {t.id() for t in router._iter_tests(router.fast_suite(REPO_ROOT / "tests", REPO_ROOT))}
        self.assertTrue(any(i.startswith(router.INTEGRATION_PREFIX) for i in full))
        self.assertEqual(fast, {i for i in full if not i.startswith(router.INTEGRATION_PREFIX)})

    def test_a_new_test_directory_is_not_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = "import unittest\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n"
            for package in ("tests", "tests/newdir", "tests/integration"):
                (root / package).mkdir(parents=True, exist_ok=True)
                (root / package / "__init__.py").write_text("", encoding="utf-8")
            (root / "tests/newdir/test_x.py").write_text(body, encoding="utf-8")
            (root / "tests/integration/test_y.py").write_text(body, encoding="utf-8")
            listed = subprocess.run(
                [sys.executable, str(ROUTER), "run-fast", "--list"], cwd=root, capture_output=True, text=True, check=True
            ).stdout.split()
        self.assertEqual(listed, ["tests.newdir.test_x.T.test_a"])


if __name__ == "__main__":
    unittest.main()
