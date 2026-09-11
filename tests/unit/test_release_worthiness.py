#!/usr/bin/env python3
"""Tests for scripts/release_worthiness.py — classification, CHANGELOG
coverage, the Unreleased roll, changelog-section extraction, the release
preflight / verify gates, and the main() / $GITHUB_OUTPUT contract.

The pure logic is tested directly; the Git/GitHub command wrappers are
exercised through a fake runner injected in place of ``rw.gitgh._git`` /
``rw.gitgh._gh`` (the Git/GitHub plumbing module).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
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
            "scripts/package-manifest.json",
            "scripts/package_manifest.py",
            "scripts/validate-skill-metadata.py",
        ):
            self.assertEqual(rw.classify_path(path), "packaging", path)

    def test_skill_metadata_validator_package_is_release_worthy(self) -> None:
        # The validator behind scripts/validate-skill-metadata.py is a
        # package; editing any of its modules stays release-worthy.
        for path in (
            "scripts/skill_metadata/expectations.py",
            "scripts/skill_metadata/orchestrator.py",
            "scripts/skill_metadata/github_family.py",
        ):
            self.assertEqual(rw.classify_path(path), "packaging", path)

    def test_non_packaging_scripts_are_maintenance(self) -> None:
        self.assertEqual(rw.classify_path("scripts/claim_issue.py"), "repo-maintenance")
        self.assertEqual(rw.classify_path("scripts/release_worthiness.py"), "repo-maintenance")
        # CI-only release automation helper — never shipped in an archive.
        self.assertEqual(
            rw.classify_path("scripts/release/verify-skill-archives.sh"), "repo-maintenance"
        )

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

    VALID_INTENT = "## What\n\n- **Release category:** Fixed\n- **Release entry:** Tighten a rule\n"

    def _assess(
        self,
        *changed: str,
        body: str | None = None,
        changelog: str = PLACEHOLDER_CHANGELOG,
        require: bool = True,
        summary: bool = False,
        with_output: bool = True,
    ):
        args = ["--changelog", str(self._write("CHANGELOG.md", changelog)), "assess"]
        for path in changed:
            args += ["--changed-file", path]
        if body is not None:
            os.environ["RW_TEST_PR_BODY"] = body
            self.addCleanup(os.environ.pop, "RW_TEST_PR_BODY", None)
            args += ["--pr-body-env", "RW_TEST_PR_BODY", "--pr-number", "42"]
        if require:
            args.append("--require-release-intent")
        summary_path = Path(self._tmp.name) / "summary.md"
        if summary:
            args += ["--step-summary", str(summary_path)]
        out_path = Path(self._tmp.name) / "gh-out.txt"
        if with_output:
            os.environ["GITHUB_OUTPUT"] = str(out_path)
        else:
            os.environ.pop("GITHUB_OUTPUT", None)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = rw.main(args)
        raw = out_path.read_text(encoding="utf-8") if out_path.is_file() else None
        outputs = None if raw is None else dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
        summary_text = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
        return rc, outputs, buf.getvalue(), summary_text, raw

    def test_valid_release_intent_covers_without_a_changelog_edit(self) -> None:
        rc, outputs, _, _, _ = self._assess("skills/local-code-review/SKILL.md", body=self.VALID_INTENT)
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["release_worthy"], "true")
        self.assertEqual(outputs["release_intent"], "valid")
        self.assertEqual(outputs["release_category"], "Fixed")
        self.assertEqual(outputs["semver_impact"], "patch")

    def test_release_worthy_missing_intent_fails_closed_with_guidance(self) -> None:
        rc, outputs, text, _, _ = self._assess("skills/local-code-review/SKILL.md", body="Just a description.")
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["release_intent"], "invalid")
        self.assertIn("::error::release-worthy change has no valid release intent", text)
        self.assertIn("Release category:", text)
        self.assertIn("do not edit CHANGELOG.md", text)

    def test_release_worthy_malformed_category_fails_closed(self) -> None:
        body = "- **Release category:** Improved\n- **Release entry:** Something\n"
        rc, outputs, _, _, _ = self._assess("skills/local-code-review/SKILL.md", body=body)
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["release_intent"], "invalid")

    def test_release_worthy_none_category_fails_closed(self) -> None:
        body = "- **Release category:** none\n- **Release entry:**\n"
        rc, outputs, text, _, _ = self._assess("skills/local-code-review/SKILL.md", body=body)
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["release_intent"], "none")
        self.assertIn("release-worthy", text)

    def test_hand_edited_unreleased_does_not_substitute_for_intent(self) -> None:
        rc, _, _, _, _ = self._assess("skills/local-code-review/SKILL.md", body="", changelog=COVERED_CHANGELOG)
        self.assertEqual(rc, 1)

    def test_unclassifiable_hand_edited_unreleased_fails_closed(self) -> None:
        rc, _, text, _, _ = self._assess(
            "skills/local-code-review/SKILL.md",
            body=self.VALID_INTENT,
            changelog=_unreleased("- uncategorized entry"),
        )
        self.assertEqual(rc, 1)
        self.assertIn("not classifiable", text)

    def test_unrelated_non_release_worthy_pr_ignores_preexisting_malformed_unreleased(self) -> None:
        # A malformed hand-curated '## Unreleased' left over elsewhere must
        # never fail an unrelated PR that never touches the changelog.
        rc, outputs, text, _, _ = self._assess(
            "docs/typo.md", body="Fix a typo.\nRelease category: none\n", changelog=_unreleased("- uncategorized")
        )
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["release_worthy"], "false")
        self.assertNotIn("not classifiable", text)

    def test_without_require_flag_reports_but_exits_zero(self) -> None:
        rc, outputs, text, _, _ = self._assess("skills/local-code-review/SKILL.md", body="", require=False)
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["release_intent"], "invalid")
        self.assertIn("::warning::", text)

    def test_require_without_a_pr_body_is_a_usage_error(self) -> None:
        rc, _, text, _, _ = self._assess("skills/local-code-review/SKILL.md")
        self.assertEqual(rc, 2)
        self.assertIn("--pr-body-env", text)

    def test_push_mode_classifies_without_checking_intent(self) -> None:
        rc, outputs, _, _, _ = self._assess("skills/local-code-review/SKILL.md", require=False)
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["release_worthy"], "true")
        self.assertEqual(outputs["release_intent"], "not-checked")

    def test_docs_only_is_not_release_worthy(self) -> None:
        rc, outputs, _, _, _ = self._assess("docs/ARCHITECTURE.md", "README.md", body="")
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["release_worthy"], "false")

    def test_tests_only_is_not_release_worthy(self) -> None:
        rc, outputs, _, _, _ = self._assess("tests/unit/test_x.py", body="")
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["release_worthy"], "false")

    def test_entry_declared_on_a_non_release_worthy_pr_is_ignored_with_a_notice(self) -> None:
        rc, _, text, summary, _ = self._assess("docs/x.md", body=self.VALID_INTENT, summary=True)
        self.assertEqual(rc, 0)
        self.assertIn("::notice::", text)
        self.assertEqual(summary, "")

    def test_packaging_change_is_release_worthy_and_gate_applies(self) -> None:
        rc, outputs, _, _, _ = self._assess("scripts/package-skills.sh", body="")
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["release_worthy"], "true")

    def test_runs_without_github_output(self) -> None:
        rc, outputs, _, _, _ = self._assess(
            "skills/local-code-review/SKILL.md", body=self.VALID_INTENT, with_output=False
        )
        self.assertEqual(rc, 0)
        self.assertIsNone(outputs)

    def test_step_summary_previews_the_generated_entry_in_a_fence(self) -> None:
        rc, _, _, summary, _ = self._assess("skills/local-code-review/SKILL.md", body=self.VALID_INTENT, summary=True)
        self.assertEqual(rc, 0)
        self.assertIn("## Release recommended", summary)
        self.assertIn("```markdown\n### Fixed\n\n- Tighten a rule (#42).\n```", summary)
        self.assertIn("**patch**", summary)

    def test_step_summary_fence_outlasts_backticks_in_the_entry(self) -> None:
        body = "Release category: Fixed\nRelease entry: Escape ```` in `x`\n"
        _, _, _, summary, _ = self._assess("skills/local-code-review/SKILL.md", body=body, summary=True)
        self.assertIn("`````markdown", summary)

    def test_contributor_text_never_reaches_stdout_or_outputs(self) -> None:
        body = "Release category: Fixed\nRelease entry: ::warning::pwned\n"
        rc, _, text, _, raw = self._assess("skills/local-code-review/SKILL.md", body=body)
        self.assertEqual(rc, 0)
        self.assertNotIn("pwned", text)
        self.assertNotIn("pwned", raw)

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


VERSIONED_CHANGELOG = """\
# Changelog

## Unreleased

_Nothing yet._

## v1.0.3 — 2026-09-01

### Added

- Release-worthiness automation (#104).

### Changed

- Tightened packaging checks.

## v1.0.2 — 2026-08-29

- Something shipped earlier.
"""


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


class _FakeGit:
    """Stand-in for rw.gitgh._git dispatching on the leading git args."""

    def __init__(
        self,
        *,
        describe: str = "v1.0.2\n",
        diff: str = "",
        tag_list: str = "",
        sorted_tags: str | None = None,
        ls_remote_tags: str = "",
        ls_remote_main: str = "",
        rev_parse: str | None = None,
        merge_base: str | None = None,
        log: str = "",
    ) -> None:
        self.describe = describe
        self.diff = diff
        self.merge_base = merge_base
        self.log = log
        self.tag_list = tag_list
        # `git tag --list --sort=-v:refname <glob>` output; defaults to the
        # exact-match tag_list when the test does not distinguish them.
        self.sorted_tags = tag_list if sorted_tags is None else sorted_tags
        self.ls_remote_tags = ls_remote_tags
        self.ls_remote_main = ls_remote_main
        self.rev_parse = rev_parse
        self.calls: list[list[str]] = []

    def __call__(self, args, repo_root):  # noqa: ANN001 - test shim
        a = list(args)
        self.calls.append(a)
        if a[:1] == ["log"]:
            return self.log
        if a[:1] == ["describe"]:
            return self.describe
        if a[:2] == ["diff", "--name-only"]:
            return self.diff
        if a[:2] == ["tag", "--list"]:
            if any(part.startswith("--sort") for part in a):
                return self.sorted_tags
            pattern = a[-1]
            names = [line.strip() for line in self.tag_list.splitlines() if line.strip()]
            return f"{pattern}\n" if pattern in names else ""
        if a[:1] == ["rev-parse"]:
            if self.rev_parse is None:
                raise subprocess.CalledProcessError(128, ["git", *a])
            return self.rev_parse
        if a[:1] == ["merge-base"]:
            if self.merge_base is None:
                raise subprocess.CalledProcessError(1, ["git", *a])
            return self.merge_base
        if a[:1] == ["ls-remote"]:
            return self.ls_remote_tags if "--tags" in a else self.ls_remote_main
        raise AssertionError(f"unexpected git call: {a}")


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


class ChangelogSectionCommandTests(unittest.TestCase):
    def test_prints_version_section(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cl = Path(tmp.name) / "CHANGELOG.md"
        cl.write_text(VERSIONED_CHANGELOG, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = rw.main(["--changelog", str(cl), "changelog-section", "--version", "1.0.3"])
        self.assertEqual(rc, 0)
        self.assertIn("Release-worthiness automation (#104).", buf.getvalue())
        self.assertNotIn("Something shipped earlier.", buf.getvalue())


# --- Deterministic SemVer classification --------------------------------


def _unreleased(*body: str) -> str:
    return "# Changelog\n\n## Unreleased\n\n" + "\n".join(body) + "\n\n## v1.0.2 — 2026-08-29\n\n- old\n"


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
