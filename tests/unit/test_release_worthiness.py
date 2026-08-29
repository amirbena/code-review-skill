#!/usr/bin/env python3
"""Tests for scripts/release_worthiness.py — classification, CHANGELOG
coverage, the Unreleased roll, and the main() / $GITHUB_OUTPUT contract.

Git plumbing is out of scope; only the pure, deterministic logic the
workflow depends on.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import release_worthiness as rw  # noqa: E402


PLACEHOLDER_CHANGELOG = """\
# Changelog

## Unreleased

_Nothing yet. New entries land here and move under a version heading at
release time._

## v1.0.2 — 2026-08-29

### Changed

- Something shipped earlier.
"""

COVERED_CHANGELOG = """\
# Changelog

## Unreleased

### Changed

- Add release-worthiness automation (#104).

## v1.0.2 — 2026-08-29

- Something shipped earlier.
"""


class ClassifyPathTests(unittest.TestCase):
    def test_skill_content_is_release_worthy(self) -> None:
        for path in (
            "skills/local-code-review/SKILL.md",
            "skills/github-pr-review/policies/github-review.md",
            "skills/local-code-review/runbooks/local-review.md",
            "skills/github-pr-review/metadata/skill.yaml",
        ):
            self.assertEqual(rw.classify_path(path), "skill-content", path)

    def test_skill_readme_is_not_release_worthy(self) -> None:
        self.assertEqual(rw.classify_path("skills/local-code-review/README.md"), "docs")

    def test_packaged_shared_is_release_worthy(self) -> None:
        self.assertEqual(rw.classify_path("shared/policies/severity.md"), "shared-runtime")
        self.assertEqual(rw.classify_path("shared/templates/finding.md"), "shared-runtime")

    def test_shared_readme_is_not_release_worthy(self) -> None:
        self.assertEqual(rw.classify_path("shared/policies/README.md"), "docs")

    def test_packaging_files_are_release_worthy(self) -> None:
        for path in (
            "scripts/package-skills.sh",
            "scripts/package-skills.ps1",
            "scripts/validate-skill-metadata.py",
        ):
            self.assertEqual(rw.classify_path(path), "packaging", path)

    def test_non_packaging_scripts_are_maintenance(self) -> None:
        self.assertEqual(rw.classify_path("scripts/claim_issue.py"), "repo-maintenance")
        self.assertEqual(rw.classify_path("scripts/release_worthiness.py"), "repo-maintenance")

    def test_docs_tests_ci_policy_are_not_release_worthy(self) -> None:
        for path, category in (
            ("docs/ARCHITECTURE.md", "docs"),
            ("docs/RELEASE.md", "docs"),
            ("tests/unit/test_release_worthiness.py", "tests"),
            (".github/workflows/validate.yml", "ci"),
            (".github/workflows/release-worthiness.yml", "ci"),
            ("policies/git-pr-merge-policy.md", "repo-policy"),
        ):
            self.assertEqual(rw.classify_path(path), category, path)

    def test_root_maintenance_files(self) -> None:
        for path, category in (
            ("CHANGELOG.md", "changelog"),
            ("README.md", "docs"),
            ("AGENTS.md", "repo-policy"),
            ("CONTRIBUTING.md", "docs"),
            ("LICENSE", "repo-maintenance"),
            ("requirements-dev.txt", "repo-maintenance"),
        ):
            self.assertEqual(rw.classify_path(path), category, path)

    def test_unknown_path(self) -> None:
        self.assertEqual(rw.classify_path("weird/thing.txt"), "unknown")

    def test_normalizes_separators_and_prefix(self) -> None:
        self.assertEqual(rw.classify_path("./skills/local-code-review/SKILL.md"), "skill-content")
        self.assertEqual(rw.classify_path("skills\\github-pr-review\\SKILL.md"), "skill-content")


class ClassifyPathsTests(unittest.TestCase):
    def test_skill_change_is_release_worthy(self) -> None:
        c = rw.classify_paths(["skills/local-code-review/SKILL.md"])
        self.assertTrue(c.release_worthy)
        self.assertEqual([p for p, _ in c.triggering], ["skills/local-code-review/SKILL.md"])

    def test_packaging_change_is_release_worthy(self) -> None:
        c = rw.classify_paths(["scripts/package-skills.ps1"])
        self.assertTrue(c.release_worthy)

    def test_docs_only_is_not_release_worthy(self) -> None:
        c = rw.classify_paths(["docs/ARCHITECTURE.md", "README.md", "skills/github-pr-review/README.md"])
        self.assertFalse(c.release_worthy)
        self.assertEqual(c.triggering, ())

    def test_tests_and_maintenance_only_is_not_release_worthy(self) -> None:
        c = rw.classify_paths(
            ["tests/unit/test_x.py", "scripts/claim_issue.py", ".github/workflows/validate.yml"]
        )
        self.assertFalse(c.release_worthy)

    def test_mixed_set_with_one_skill_file_is_release_worthy(self) -> None:
        c = rw.classify_paths(["docs/ARCHITECTURE.md", "skills/local-code-review/policies/pr-context.md"])
        self.assertTrue(c.release_worthy)
        self.assertEqual(len(c.triggering), 1)
        self.assertEqual(len(c.other), 1)

    def test_empty_set_is_not_release_worthy(self) -> None:
        self.assertFalse(rw.classify_paths([]).release_worthy)
        self.assertFalse(rw.classify_paths(["", "  "]).release_worthy)

    def test_reason_mentions_a_triggering_path(self) -> None:
        c = rw.classify_paths(["skills/local-code-review/SKILL.md"])
        self.assertIn("skills/local-code-review/SKILL.md", c.reason)


class ChangelogCoverageTests(unittest.TestCase):
    def test_placeholder_only_is_not_covered(self) -> None:
        self.assertFalse(rw.unreleased_has_coverage(PLACEHOLDER_CHANGELOG))

    def test_bullet_entry_is_covered(self) -> None:
        self.assertTrue(rw.unreleased_has_coverage(COVERED_CHANGELOG))

    def test_missing_unreleased_heading_is_not_covered(self) -> None:
        self.assertFalse(rw.unreleased_has_coverage("# Changelog\n\n## v1.0.0 — 2026-01-01\n\n- x\n"))

    def test_star_bullets_count(self) -> None:
        text = "# Changelog\n\n## Unreleased\n\n* Did a thing.\n\n## v1.0.0 — 2026-01-01\n"
        self.assertTrue(rw.unreleased_has_coverage(text))

    def test_real_repository_changelog_is_parseable(self) -> None:
        text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        # Should not raise and returns a bool for the current file.
        self.assertIn(rw.unreleased_has_coverage(text), (True, False))


class RollUnreleasedTests(unittest.TestCase):
    def test_rolls_entries_and_restores_placeholder(self) -> None:
        out = rw.roll_unreleased(COVERED_CHANGELOG, "1.0.3", "2026-09-01")
        self.assertIn("## v1.0.3 — 2026-09-01", out)
        self.assertIn("- Add release-worthiness automation (#104).", out)
        # Fresh placeholder is back above the new version section.
        head = out.split("## v1.0.3", 1)[0]
        self.assertIn("## Unreleased", head)

    def test_placeholder_after_roll_has_no_entries(self) -> None:
        out = rw.roll_unreleased(COVERED_CHANGELOG, "1.0.3", "2026-09-01")
        self.assertFalse(rw.unreleased_has_coverage(out))

    def test_refuses_when_no_entries(self) -> None:
        with self.assertRaises(ValueError):
            rw.roll_unreleased(PLACEHOLDER_CHANGELOG, "1.0.3", "2026-09-01")

    def test_refuses_bad_version(self) -> None:
        with self.assertRaises(ValueError):
            rw.roll_unreleased(COVERED_CHANGELOG, "v1.0.3", "2026-09-01")
        with self.assertRaises(ValueError):
            rw.roll_unreleased(COVERED_CHANGELOG, "1.0", "2026-09-01")

    def test_preserves_prior_release_section(self) -> None:
        out = rw.roll_unreleased(COVERED_CHANGELOG, "1.0.3", "2026-09-01")
        self.assertIn("## v1.0.2 — 2026-08-29", out)


class MainAssessContractTests(unittest.TestCase):
    """The exact seam the workflow consumes: assess exit code and the
    release_worthy / changelog_covered / reason lines in $GITHUB_OUTPUT."""

    def setUp(self) -> None:
        self._saved = os.environ.get("GITHUB_OUTPUT")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._restore_env)

    def _restore_env(self) -> None:
        if self._saved is None:
            os.environ.pop("GITHUB_OUTPUT", None)
        else:
            os.environ["GITHUB_OUTPUT"] = self._saved

    def _write(self, name: str, text: str) -> Path:
        path = Path(self._tmp.name) / name
        path.write_text(text, encoding="utf-8")
        return path

    def _run(self, *args: str, with_output: bool = True):
        out_path = None
        if with_output:
            out_path = Path(self._tmp.name) / "gh-out.txt"
            os.environ["GITHUB_OUTPUT"] = str(out_path)
        else:
            os.environ.pop("GITHUB_OUTPUT", None)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = rw.main(list(args))
        outputs = None
        if out_path is not None and out_path.is_file():
            outputs = dict(
                line.split("=", 1) for line in out_path.read_text(encoding="utf-8").splitlines() if "=" in line
            )
        return rc, outputs

    def test_release_worthy_missing_changelog_fails_closed(self) -> None:
        cl = self._write("CHANGELOG.md", PLACEHOLDER_CHANGELOG)
        rc, outputs = self._run(
            "--changelog", str(cl),
            "assess",
            "--changed-file", "skills/local-code-review/SKILL.md",
            "--require-changelog",
        )
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["release_worthy"], "true")
        self.assertEqual(outputs["changelog_covered"], "false")

    def test_release_worthy_without_require_flag_still_exits_zero(self) -> None:
        cl = self._write("CHANGELOG.md", PLACEHOLDER_CHANGELOG)
        rc, outputs = self._run(
            "--changelog", str(cl),
            "assess",
            "--changed-file", "skills/local-code-review/SKILL.md",
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["release_worthy"], "true")
        self.assertEqual(outputs["changelog_covered"], "false")

    def test_release_worthy_with_coverage_passes(self) -> None:
        cl = self._write("CHANGELOG.md", COVERED_CHANGELOG)
        rc, outputs = self._run(
            "--changelog", str(cl),
            "assess",
            "--changed-file", "skills/local-code-review/SKILL.md",
            "--require-changelog",
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["release_worthy"], "true")
        self.assertEqual(outputs["changelog_covered"], "true")

    def test_docs_only_is_not_release_worthy(self) -> None:
        cl = self._write("CHANGELOG.md", PLACEHOLDER_CHANGELOG)
        rc, outputs = self._run(
            "--changelog", str(cl),
            "assess",
            "--changed-file", "docs/ARCHITECTURE.md",
            "--changed-file", "README.md",
            "--require-changelog",
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["release_worthy"], "false")

    def test_tests_only_is_not_release_worthy(self) -> None:
        cl = self._write("CHANGELOG.md", PLACEHOLDER_CHANGELOG)
        rc, outputs = self._run(
            "--changelog", str(cl),
            "assess",
            "--changed-file", "tests/unit/test_x.py",
            "--require-changelog",
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["release_worthy"], "false")

    def test_packaging_change_is_release_worthy_and_build_gate_applies(self) -> None:
        cl = self._write("CHANGELOG.md", PLACEHOLDER_CHANGELOG)
        rc, outputs = self._run(
            "--changelog", str(cl),
            "assess",
            "--changed-file", "scripts/package-skills.sh",
            "--require-changelog",
        )
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["release_worthy"], "true")

    def test_runs_without_github_output(self) -> None:
        cl = self._write("CHANGELOG.md", COVERED_CHANGELOG)
        rc, outputs = self._run(
            "--changelog", str(cl),
            "assess",
            "--changed-file", "skills/local-code-review/SKILL.md",
            "--require-changelog",
            with_output=False,
        )
        self.assertEqual(rc, 0)
        self.assertIsNone(outputs)

    def test_prepare_changelog_check_mode_does_not_write(self) -> None:
        cl = self._write("CHANGELOG.md", COVERED_CHANGELOG)
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = rw.main(
                ["--changelog", str(cl), "prepare-changelog", "--version", "1.0.3",
                 "--date", "2026-09-01", "--check"]
            )
        self.assertEqual(rc, 0)
        self.assertEqual(cl.read_text(encoding="utf-8"), COVERED_CHANGELOG)
        self.assertIn("## v1.0.3 — 2026-09-01", buf.getvalue())

    def test_prepare_changelog_writes_file(self) -> None:
        cl = self._write("CHANGELOG.md", COVERED_CHANGELOG)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = rw.main(
                ["--changelog", str(cl), "prepare-changelog", "--version", "1.0.3", "--date", "2026-09-01"]
            )
        self.assertEqual(rc, 0)
        self.assertIn("## v1.0.3 — 2026-09-01", cl.read_text(encoding="utf-8"))

    def test_prepare_changelog_fails_on_empty_unreleased(self) -> None:
        cl = self._write("CHANGELOG.md", PLACEHOLDER_CHANGELOG)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = rw.main(["--changelog", str(cl), "prepare-changelog", "--version", "1.0.3"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
