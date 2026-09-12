"""Tests for scripts/release_worthiness.py's pure SemVer classification and ref-resolution helpers."""

from __future__ import annotations

import unittest
import contextlib
import io
import subprocess
import tempfile
from pathlib import Path

from tests.unit.release._shared import (
    PLACEHOLDER_CHANGELOG,
    VERSIONED_CHANGELOG,
    _FakeGit,
    _unreleased,
    rw,
)

class PureReleaseHelperTests(unittest.TestCase):
    def test_validate_semver_accepts_plain_triplet(self) -> None:
        rw.validate_semver("1.0.3")

    def test_validate_semver_rejects_leading_v_and_odd_shapes(self) -> None:
        for bad in ("v1.0.3", "1.0", "1.0.3.4", "1.0.x", "1.0.3-rc1", ""):
            with self.assertRaises(ValueError, msg=bad):
                rw.validate_semver(bad)

    def test_parse_ref_lines(self) -> None:
        text = "abc123\trefs/heads/main\ndef456\trefs/tags/v1.0.3\n"
        self.assertEqual(
            rw.parse_ref_lines(text),
            {"refs/heads/main": "abc123", "refs/tags/v1.0.3": "def456"},
        )

    def test_resolved_tag_commit_prefers_peeled_annotated_ref(self) -> None:
        text = "tagobj\trefs/tags/v1.0.3\ncommit99\trefs/tags/v1.0.3^{}\n"
        self.assertEqual(rw.resolved_tag_commit(text, "1.0.3"), "commit99")

    def test_resolved_tag_commit_falls_back_to_bare_ref(self) -> None:
        text = "commit77\trefs/tags/v1.0.3\n"
        self.assertEqual(rw.resolved_tag_commit(text, "1.0.3"), "commit77")
        self.assertIsNone(rw.resolved_tag_commit("", "1.0.3"))

    def test_release_assets_present(self) -> None:
        rel = {"assets": [{"name": "a.zip"}, {"name": "b.zip"}]}
        self.assertTrue(rw.release_assets_present(rel, ["a.zip", "b.zip"]))
        self.assertFalse(rw.release_assets_present(rel, ["a.zip", "c.zip"]))

    def test_extract_version_section_returns_only_that_version(self) -> None:
        section = rw.extract_version_section(VERSIONED_CHANGELOG, "1.0.3")
        self.assertIn("Release-worthiness automation (#104).", section)
        self.assertIn("Tightened packaging checks.", section)
        self.assertNotIn("Something shipped earlier.", section)
        self.assertNotIn("Unreleased", section)

    def test_extract_version_section_missing_raises(self) -> None:
        with self.assertRaises(ValueError):
            rw.extract_version_section(VERSIONED_CHANGELOG, "9.9.9")


class ClassifySemverImpactTests(unittest.TestCase):
    def test_added_or_changed_is_minor(self) -> None:
        self.assertEqual(rw.classify_semver_impact(_unreleased("### Added", "", "- a new thing")), "minor")
        self.assertEqual(rw.classify_semver_impact(_unreleased("### Changed", "", "- reworked x")), "minor")

    def test_fixed_or_security_is_patch(self) -> None:
        self.assertEqual(rw.classify_semver_impact(_unreleased("### Fixed", "", "- fixed x")), "patch")
        self.assertEqual(rw.classify_semver_impact(_unreleased("### Security", "", "- hardened y")), "patch")

    def test_removed_or_breaking_is_major(self) -> None:
        self.assertEqual(rw.classify_semver_impact(_unreleased("### Removed", "", "- dropped z")), "major")
        self.assertEqual(rw.classify_semver_impact(_unreleased("### Breaking", "", "- changed contract")), "major")

    def test_highest_impact_wins_across_categories(self) -> None:
        mixed_patch_minor = _unreleased("### Fixed", "", "- fix", "", "### Added", "", "- feat")
        self.assertEqual(rw.classify_semver_impact(mixed_patch_minor), "minor")
        mixed_all = _unreleased(
            "### Fixed", "", "- fix", "", "### Added", "", "- feat", "", "### Removed", "", "- drop"
        )
        self.assertEqual(rw.classify_semver_impact(mixed_all), "major")
        mixed_patch_only = _unreleased("### Fixed", "", "- fix", "", "### Security", "", "- hard")
        self.assertEqual(rw.classify_semver_impact(mixed_patch_only), "patch")

    def test_entry_outside_any_category_is_ambiguous(self) -> None:
        with self.assertRaises(rw.AmbiguousReleaseImpact):
            rw.classify_semver_impact(_unreleased("- a bullet with no category heading"))

    def test_unrecognized_category_is_ambiguous(self) -> None:
        with self.assertRaises(rw.AmbiguousReleaseImpact):
            rw.classify_semver_impact(_unreleased("### Notes", "", "- something"))

    def test_no_entries_is_ambiguous(self) -> None:
        with self.assertRaises(rw.AmbiguousReleaseImpact):
            rw.classify_semver_impact(PLACEHOLDER_CHANGELOG)

    def test_missing_unreleased_section_is_ambiguous(self) -> None:
        with self.assertRaises(rw.AmbiguousReleaseImpact):
            rw.classify_semver_impact("# Changelog\n\n## v1.0.0 — 2026-01-01\n\n- x\n")


class DeriveNextVersionTests(unittest.TestCase):
    def test_patch_minor_major_bumps(self) -> None:
        self.assertEqual(rw.derive_next_version("v1.0.2", "patch"), "1.0.3")
        self.assertEqual(rw.derive_next_version("v1.0.2", "minor"), "1.1.0")
        self.assertEqual(rw.derive_next_version("v1.4.7", "major"), "2.0.0")

    def test_rejects_missing_or_malformed_tag(self) -> None:
        for bad in (None, "", "1.0.2", "v1.0", "vX.Y.Z"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                rw.derive_next_version(bad, "patch")

    def test_rejects_bad_impact(self) -> None:
        with self.assertRaises(ValueError):
            rw.derive_next_version("v1.0.2", "huge")


class MigrationForcedImpactTests(unittest.TestCase):
    def test_forces_patch_only_at_the_pre_policy_baseline(self) -> None:
        self.assertEqual(rw.migration_forced_impact(rw.PRE_POLICY_BASELINE_TAG), "patch")

    def test_no_force_after_the_baseline_moves_on(self) -> None:
        self.assertIsNone(rw.migration_forced_impact("v1.0.3"))
        self.assertIsNone(rw.migration_forced_impact("v2.0.0"))
        self.assertIsNone(rw.migration_forced_impact(None))


class ClassifySemverCommandTests(unittest.TestCase):
    def _run(self, changelog_text: str, *extra: str):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cl = Path(tmp.name) / "CHANGELOG.md"
        cl.write_text(changelog_text, encoding="utf-8")
        out = Path(tmp.name) / "gh-out.txt"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = rw.main(
                ["--changelog", str(cl), "classify-semver", "--github-output", str(out), *extra]
            )
        outputs = dict(
            line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines() if "=" in line
        ) if out.is_file() else {}
        return rc, outputs, buf.getvalue()

    def test_reports_impact_and_exits_zero(self) -> None:
        rc, outputs, _ = self._run(_unreleased("### Added", "", "- feat"))
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["semver_impact"], "minor")

    def test_ambiguous_is_a_warning_without_strict(self) -> None:
        rc, outputs, text = self._run(_unreleased("### Notes", "", "- x"))
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["semver_impact"], "ambiguous")
        self.assertIn("::warning::", text)

    def test_ambiguous_fails_closed_with_strict(self) -> None:
        rc, outputs, text = self._run(_unreleased("### Notes", "", "- x"), "--strict")
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["semver_impact"], "ambiguous")
        self.assertIn("::error::", text)


class ResolveBaseRefTests(unittest.TestCase):
    """The seam the assess job consumes: `ref=` in $GITHUB_OUTPUT — the
    merge-base with the PR's current base branch on a pull_request, the
    previous v* tag otherwise, empty when there is no prior release."""

    def setUp(self) -> None:
        self._real_git = rw.gitgh._git
        self.addCleanup(setattr, rw.gitgh, "_git", self._real_git)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _run(self, *args: str, git: _FakeGit | None = None):
        if git is not None:
            rw.gitgh._git = git
        out = Path(self._tmp.name) / "gh-out.txt"
        if out.exists():
            out.unlink()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = rw.main(["resolve-base-ref", "--github-output", str(out), *args])
        outputs = dict(
            line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines() if "=" in line
        ) if out.is_file() else {}
        return rc, outputs

    def test_pull_request_uses_merge_base_with_current_base_branch(self) -> None:
        # origin/main resolves to its live tip; the emitted ref is the fork
        # point, not the (possibly stale) payload base.sha.
        rc, outputs = self._run(
            "--event-name", "pull_request",
            "--pr-base-ref", "main",
            "--pr-base-sha", "d" * 40,
            git=_FakeGit(rev_parse="a" * 40 + "\n", merge_base="f" * 40 + "\n"),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["ref"], "f" * 40)

    def test_pull_request_unresolvable_base_ref_falls_back_to_base_sha(self) -> None:
        # origin/main is not present (fetch step skipped / older payload):
        # fall back to base.sha, which assess still diffs three-dot.
        rc, outputs = self._run(
            "--event-name", "pull_request",
            "--pr-base-ref", "main",
            "--pr-base-sha", "d" * 40,
            git=_FakeGit(rev_parse=None),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["ref"], "d" * 40)

    def test_pull_request_merge_base_failure_falls_back_to_the_tip(self) -> None:
        rc, outputs = self._run(
            "--event-name", "pull_request",
            "--pr-base-ref", "main",
            "--pr-base-sha", "d" * 40,
            git=_FakeGit(rev_parse="a" * 40 + "\n", merge_base=None),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["ref"], "a" * 40)

    def test_pull_request_without_a_base_ref_uses_the_pr_base_sha(self) -> None:
        rc, outputs = self._run(
            "--event-name", "pull_request", "--pr-base-sha", "d" * 40,
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["ref"], "d" * 40)

    def test_pull_request_without_a_base_sha_passes_through_empty(self) -> None:
        # Matches the shell block this replaced: emit an empty ref and let
        # `assess` fall back to the previous v* tag, rather than hard-failing.
        rc, outputs = self._run("--event-name", "pull_request", "--pr-base-sha", "")
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["ref"], "")

    def test_push_uses_the_previous_release_tag(self) -> None:
        rc, outputs = self._run(
            "--event-name", "push", git=_FakeGit(describe="v1.2.3\n"),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["ref"], "v1.2.3")

    def test_push_with_no_prior_tag_emits_empty_ref(self) -> None:
        def _no_tag(args, repo_root):  # noqa: ANN001 - test shim
            raise subprocess.CalledProcessError(128, ["git", *args])

        rc, outputs = self._run("--event-name", "workflow_dispatch", git=_no_tag)
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["ref"], "")

    def test_pr_base_sha_is_ignored_off_a_pull_request(self) -> None:
        rc, outputs = self._run(
            "--event-name", "push", "--pr-base-sha", "e" * 40,
            git=_FakeGit(describe="v9.9.9\n"),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["ref"], "v9.9.9")


class ResolveAppIdentityTests(unittest.TestCase):
    """The seam the publish job consumes: `login=` / `email=` for the
    release commit, resolved from the minted App's slug, failing closed
    with no fallback identity."""

    def setUp(self) -> None:
        self._real_gh = rw.gitgh._gh
        self.addCleanup(setattr, rw.gitgh, "_gh", self._real_gh)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _run(self, slug: str, gh):
        rw.gitgh._gh = gh
        out = Path(self._tmp.name) / "gh-out.txt"
        if out.exists():
            out.unlink()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = rw.main(["resolve-app-identity", "--app-slug", slug, "--github-output", str(out)])
        outputs = dict(
            line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines() if "=" in line
        ) if out.is_file() else {}
        return rc, outputs, buf.getvalue()

    def _gh_user_id(self, user_id: str, expect_login: str | None = None):
        def _gh(args, repo_root):  # noqa: ANN001 - test shim
            self.assertEqual(args[:1], ["api"])
            if expect_login is not None:
                self.assertEqual(args[1], f"/users/{expect_login}")
            return f"{user_id}\n"

        return _gh

    def test_resolves_login_and_canonical_noreply_email(self) -> None:
        rc, outputs, _ = self._run(
            "my-release-app", self._gh_user_id("12345", expect_login="my-release-app[bot]")
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["login"], "my-release-app[bot]")
        self.assertEqual(outputs["email"], "12345+my-release-app[bot]@users.noreply.github.com")

    def test_empty_slug_fails_closed(self) -> None:
        called = []
        rc, outputs, text = self._run("", lambda *a, **k: called.append(a))
        self.assertEqual(rc, 1)
        self.assertEqual(outputs, {})
        self.assertEqual(called, [])
        self.assertIn("::error::", text)

    def test_non_numeric_user_id_fails_closed(self) -> None:
        rc, outputs, text = self._run("slug", self._gh_user_id("not-a-number"))
        self.assertEqual(rc, 1)
        self.assertEqual(outputs, {})
        self.assertIn("fallback identity", text)

    def test_github_api_failure_fails_closed(self) -> None:
        def _boom(args, repo_root):  # noqa: ANN001 - test shim
            raise subprocess.CalledProcessError(1, ["gh", *args])

        rc, outputs, text = self._run("slug", _boom)
        self.assertEqual(rc, 1)
        self.assertEqual(outputs, {})
        self.assertIn("::error::", text)


class LatestReleaseTagTests(unittest.TestCase):
    def setUp(self) -> None:
        self._real_git = rw.gitgh._git
        self.addCleanup(setattr, rw.gitgh, "_git", self._real_git)

    def test_picks_highest_valid_semver_tag(self) -> None:
        rw.gitgh._git = _FakeGit(sorted_tags="v1.0.10\nv1.0.9\nv1.0.2\n")
        self.assertEqual(rw.latest_release_tag(Path(".")), "v1.0.10")

    def test_skips_non_semver_lines(self) -> None:
        rw.gitgh._git = _FakeGit(sorted_tags="v1.2\nnightly\nv1.0.3\nv1.0.2\n")
        self.assertEqual(rw.latest_release_tag(Path(".")), "v1.0.3")

    def test_none_when_no_tags(self) -> None:
        rw.gitgh._git = _FakeGit(sorted_tags="")
        self.assertIsNone(rw.latest_release_tag(Path(".")))


if __name__ == "__main__":
    unittest.main()
