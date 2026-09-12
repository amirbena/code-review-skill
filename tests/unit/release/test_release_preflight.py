"""Tests for scripts/release_worthiness.py preflight / verify gates and the auto-release plan."""

from __future__ import annotations

import unittest
import contextlib
import io
import json
import tempfile
from pathlib import Path

from tests.unit.release._shared import (
    COVERED_CHANGELOG,
    PLACEHOLDER_CHANGELOG,
    _FakeGit,
    _unreleased,
    rw,
)

class ReleasePreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self._real_git = rw.gitgh._git
        self.addCleanup(setattr, rw.gitgh, "_git", self._real_git)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _changelog(self, text: str) -> Path:
        path = Path(self._tmp.name) / "CHANGELOG.md"
        path.write_text(text, encoding="utf-8")
        return path

    def _run(self, version: str, fake: _FakeGit, changelog_text: str) -> int:
        rw.gitgh._git = fake
        cl = self._changelog(changelog_text)
        with contextlib.redirect_stdout(io.StringIO()):
            return rw.main(["--changelog", str(cl), "release-preflight", "--version", version])

    def test_invalid_version_fails(self) -> None:
        self.assertEqual(self._run("v1.0.3", _FakeGit(), COVERED_CHANGELOG), 1)

    def test_existing_local_tag_fails(self) -> None:
        fake = _FakeGit(tag_list="v1.0.3\n", diff="skills/a/SKILL.md\n")
        self.assertEqual(self._run("1.0.3", fake, COVERED_CHANGELOG), 1)

    def test_existing_remote_tag_fails(self) -> None:
        fake = _FakeGit(ls_remote_tags="sha\trefs/tags/v1.0.3\n", diff="skills/a/SKILL.md\n")
        self.assertEqual(self._run("1.0.3", fake, COVERED_CHANGELOG), 1)

    def test_no_release_worthy_changes_fails(self) -> None:
        fake = _FakeGit(diff="docs/x.md\nREADME.md\ntests/unit/test_x.py\n")
        self.assertEqual(self._run("1.0.3", fake, COVERED_CHANGELOG), 1)

    def test_missing_unreleased_coverage_fails(self) -> None:
        fake = _FakeGit(diff="skills/local-code-review/SKILL.md\n")
        self.assertEqual(self._run("1.0.3", fake, PLACEHOLDER_CHANGELOG), 1)

    def test_happy_path_passes(self) -> None:
        fake = _FakeGit(diff="skills/local-code-review/SKILL.md\nshared/policies/severity.md\n")
        self.assertEqual(self._run("1.0.3", fake, COVERED_CHANGELOG), 0)


class ReleaseVerifyTests(unittest.TestCase):
    SHA = "a" * 40

    def setUp(self) -> None:
        self._real_git, self._real_gh = rw.gitgh._git, rw.gitgh._gh
        self.addCleanup(setattr, rw.gitgh, "_git", self._real_git)
        self.addCleanup(setattr, rw.gitgh, "_gh", self._real_gh)

    def _good_git(self, **overrides) -> _FakeGit:
        base = dict(
            rev_parse=self.SHA + "\n",
            ls_remote_tags=f"tagobj\trefs/tags/v1.0.3\n{self.SHA}\trefs/tags/v1.0.3^{{}}\n",
            ls_remote_main=f"{self.SHA}\trefs/heads/main\n",
        )
        base.update(overrides)
        return _FakeGit(**base)

    def _gh_release(self, assets=("local-code-review-skill.zip", "github-pr-review-skill.zip")):
        payload = {
            "tagName": "v1.0.3",
            "targetCommitish": "main",
            "assets": [{"name": name} for name in assets],
        }
        return lambda args, repo_root: json.dumps(payload)

    def _run(self, git: _FakeGit, gh, expected: str = SHA) -> int:
        rw.gitgh._git, rw.gitgh._gh = git, gh
        with contextlib.redirect_stdout(io.StringIO()):
            return rw.main(
                [
                    "release-verify",
                    "--version", "1.0.3",
                    "--expected-sha", expected,
                    "--asset", "local-code-review-skill.zip",
                    "--asset", "github-pr-review-skill.zip",
                ]
            )

    def test_all_match_passes(self) -> None:
        self.assertEqual(self._run(self._good_git(), self._gh_release()), 0)

    def test_tag_points_elsewhere_fails(self) -> None:
        self.assertEqual(self._run(self._good_git(rev_parse="b" * 40 + "\n"), self._gh_release()), 1)

    def test_main_not_advanced_fails(self) -> None:
        git = self._good_git(ls_remote_main="c" * 40 + "\trefs/heads/main\n")
        self.assertEqual(self._run(git, self._gh_release()), 1)

    def test_missing_release_asset_fails(self) -> None:
        self.assertEqual(self._run(self._good_git(), self._gh_release(assets=("local-code-review-skill.zip",))), 1)

    def test_non_sha_expected_fails(self) -> None:
        self.assertEqual(self._run(self._good_git(), self._gh_release(), expected="main"), 1)


class AutoReleasePlanTests(unittest.TestCase):
    """The seam the release job consumes: should_release / version / impact
    and the exit code (1 only on a hard fault such as ambiguous impact)."""

    SKILL_DIFF = "skills/local-code-review/SKILL.md\n"

    def setUp(self) -> None:
        self._real_git = rw.gitgh._git
        self.addCleanup(setattr, rw.gitgh, "_git", self._real_git)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _run(self, fake: _FakeGit, changelog_text: str):
        rw.gitgh._git = fake
        cl = Path(self._tmp.name) / "CHANGELOG.md"
        cl.write_text(changelog_text, encoding="utf-8")
        out = Path(self._tmp.name) / "gh-out.txt"
        if out.exists():
            out.unlink()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = rw.main(["--changelog", str(cl), "auto-release-plan", "--github-output", str(out)])
        outputs = dict(
            line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines() if "=" in line
        ) if out.is_file() else {}
        return rc, outputs, buf.getvalue()

    def _tags(self, *tags: str) -> str:
        return "".join(f"{t}\n" for t in tags)

    def test_migration_forces_patch_regardless_of_categories(self) -> None:
        # Baseline is the pre-policy tag; Unreleased has an Added entry that
        # would otherwise be a minor bump.
        fake = _FakeGit(sorted_tags=self._tags("v1.0.2", "v1.0.1", "v1.0.0"), diff=self.SKILL_DIFF)
        rc, outputs, _ = self._run(fake, _unreleased("### Added", "", "- a capability (#34)"))
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["should_release"], "true")
        self.assertEqual(outputs["impact"], "patch")
        self.assertEqual(outputs["version"], "1.0.3")
        self.assertEqual(outputs["baseline"], "v1.0.2")

    def test_post_migration_patch_only_release(self) -> None:
        fake = _FakeGit(sorted_tags=self._tags("v1.0.3", "v1.0.2"), diff=self.SKILL_DIFF)
        rc, outputs, _ = self._run(fake, _unreleased("### Fixed", "", "- a fix"))
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["impact"], "patch")
        self.assertEqual(outputs["version"], "1.0.4")

    def test_post_migration_minor_release(self) -> None:
        fake = _FakeGit(sorted_tags=self._tags("v1.0.3"), diff=self.SKILL_DIFF)
        rc, outputs, _ = self._run(fake, _unreleased("### Added", "", "- a capability"))
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["impact"], "minor")
        self.assertEqual(outputs["version"], "1.1.0")

    def test_post_migration_major_release(self) -> None:
        fake = _FakeGit(sorted_tags=self._tags("v1.0.3"), diff=self.SKILL_DIFF)
        rc, outputs, _ = self._run(fake, _unreleased("### Removed", "", "- dropped a mode"))
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["impact"], "major")
        self.assertEqual(outputs["version"], "2.0.0")

    def test_mixed_set_takes_the_highest_bump(self) -> None:
        body = _unreleased(
            "### Fixed", "", "- fix", "", "### Added", "", "- feat", "", "### Removed", "", "- drop"
        )
        fake = _FakeGit(sorted_tags=self._tags("v1.2.0"), diff=self.SKILL_DIFF)
        rc, outputs, _ = self._run(fake, body)
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["impact"], "major")
        self.assertEqual(outputs["version"], "2.0.0")

    def test_ambiguous_classification_fails_closed(self) -> None:
        fake = _FakeGit(sorted_tags=self._tags("v1.0.3"), diff=self.SKILL_DIFF)
        rc, outputs, text = self._run(fake, _unreleased("- uncategorized entry"))
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["should_release"], "false")
        self.assertEqual(outputs["ambiguous"], "true")
        self.assertIn("::error::", text)
        # No version was derived, so nothing downstream can mutate a tag.
        self.assertNotIn("version", outputs)

    def test_no_release_when_nothing_release_worthy_accumulated(self) -> None:
        fake = _FakeGit(sorted_tags=self._tags("v1.0.3"), diff="docs/x.md\ntests/unit/test_x.py\n")
        rc, outputs, _ = self._run(fake, _unreleased("### Added", "", "- feat"))
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["should_release"], "false")
        self.assertIn("no release-worthy changes since v1.0.3", outputs["reason"])

    def test_retry_after_successful_release_is_a_no_op(self) -> None:
        # Latest tag is the just-published version and nothing new is
        # release-worthy since it: a re-run must not cut another release.
        fake = _FakeGit(sorted_tags=self._tags("v1.0.3", "v1.0.2"), diff="")
        rc, outputs, _ = self._run(fake, PLACEHOLDER_CHANGELOG)
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["should_release"], "false")

    def test_rolled_changelog_after_partial_publish_is_a_no_op(self) -> None:
        # Changelog already rolled (no Unreleased entries) but the skill
        # delta is still in the diff: still no new release.
        fake = _FakeGit(sorted_tags=self._tags("v1.0.2"), diff=self.SKILL_DIFF)
        rc, outputs, _ = self._run(fake, PLACEHOLDER_CHANGELOG)
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["should_release"], "false")

    def test_derived_tag_already_exists_is_a_no_op(self) -> None:
        fake = _FakeGit(
            sorted_tags=self._tags("v1.0.3", "v1.0.2"),
            tag_list=self._tags("v1.0.4", "v1.0.3", "v1.0.2"),
            diff=self.SKILL_DIFF,
        )
        rc, outputs, _ = self._run(fake, _unreleased("### Fixed", "", "- a fix"))
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["should_release"], "false")
        self.assertIn("already exists", outputs["reason"])

    def test_no_baseline_tag_is_a_hard_fault(self) -> None:
        fake = _FakeGit(sorted_tags="", diff=self.SKILL_DIFF)
        rc, outputs, text = self._run(fake, _unreleased("### Added", "", "- feat"))
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["should_release"], "false")
        self.assertIn("::error::", text)


if __name__ == "__main__":
    unittest.main()
