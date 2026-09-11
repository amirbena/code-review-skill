#!/usr/bin/env python3
"""Deterministic generation of `## Unreleased` from merged PRs' release
intent, and the `generate-changelog` / `auto-release-plan` commands that
consume it.

Contract: docs/RELEASE.md, "The global changelog model".
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import release_worthiness as rw  # noqa: E402
from release_lib.changelog_generation import (  # noqa: E402
    ChangelogGenerationError,
    GeneratedEntry,
    collect_entries,
    compose_unreleased,
    pr_number_from_subject,
)

PLACEHOLDER = """\
# Changelog

## Unreleased

_Nothing yet. New entries land here and move under a version heading at
release time._

## v1.1.0 — 2026-09-01

### Added

- Earlier capability (#1).
"""

_PLACEHOLDER_LINES = (
    "_Nothing yet. New entries land here and move under a version heading at\nrelease time._"
)

SKILL = "skills/local-code-review/SKILL.md"
DOCS = "docs/x.md"


def _with_unreleased(*body: str) -> str:
    return PLACEHOLDER.replace(_PLACEHOLDER_LINES, "\n".join(body))


def _sha(n: int) -> str:
    return f"{n:040x}"


def _body(category: str, entry: str = "") -> str:
    return f"- **Release category:** {category}\n- **Release entry:** {entry}\n"


def _merged(number: int, sha: str, body: str) -> dict:
    return {"number": number, "merged_at": "2026-09-10T00:00:00Z", "merge_commit_sha": sha, "body": body}


class _FakeRepo:
    """Stand-in for gitgh._git / gitgh._gh over a scripted first-parent history."""

    def __init__(self, commits, prs=None, *, tags: str = "v1.1.0\n", tag_list: str = "") -> None:
        self.commits = commits  # [(sha, subject, paths)]
        self.prs = prs or {}
        self.tags = tags
        self.tag_list = tag_list
        self.fetched: list[int] = []

    def git(self, args, repo_root):  # noqa: ANN001 - test shim
        a = list(args)
        if a[:1] == ["log"]:
            return "".join(f"{sha}\x1f{subject}\n" for sha, subject, _ in self.commits)
        if a[:2] == ["diff", "--name-only"]:
            if len(a) == 4:  # one commit against its first parent
                return "".join(f"{p}\n" for sha, _, paths in self.commits if sha == a[3] for p in paths)
            return "".join(sorted({f"{p}\n" for _, _, paths in self.commits for p in paths}))
        if a[:2] == ["tag", "--list"]:
            if any(part.startswith("--sort") for part in a):
                return self.tags
            return f"{a[-1]}\n" if a[-1] in self.tag_list.split() else ""
        if a[:1] == ["ls-remote"]:
            return ""
        raise AssertionError(f"unexpected git call: {a}")

    def gh(self, args, repo_root):  # noqa: ANN001 - test shim
        a = list(args)
        number = int(a[1].rsplit("/", 1)[1])
        self.fetched.append(number)
        if number not in self.prs:
            raise subprocess.CalledProcessError(1, ["gh", *a])
        return json.dumps(self.prs[number])


class _PatchedRepoCase(unittest.TestCase):
    def setUp(self) -> None:
        real_git, real_gh = rw.gitgh._git, rw.gitgh._gh
        self.addCleanup(setattr, rw.gitgh, "_git", real_git)
        self.addCleanup(setattr, rw.gitgh, "_gh", real_gh)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def use(self, repo: _FakeRepo) -> _FakeRepo:
        rw.gitgh._git = repo.git
        rw.gitgh._gh = repo.gh
        return repo

    def changelog(self, text: str = PLACEHOLDER) -> Path:
        path = self.root / "CHANGELOG.md"
        path.write_text(text, encoding="utf-8")
        return path

    def run_cli(self, *args: str) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = rw.main(list(args))
        return rc, buf.getvalue()


class PrNumberFromSubjectTests(unittest.TestCase):
    def test_squash_and_merge_subjects(self) -> None:
        self.assertEqual(pr_number_from_subject("Tighten a rule (#12)"), 12)
        self.assertEqual(pr_number_from_subject("Mentions (#3) mid-title (#9)"), 9)
        self.assertEqual(pr_number_from_subject("Merge pull request #7 from a/b"), 7)
        self.assertIsNone(pr_number_from_subject("chore(release): v1.2.0 [skip ci]"))


class ComposeUnreleasedTests(unittest.TestCase):
    ENTRIES = [
        GeneratedEntry(12, "Fixed", "- Tighten a rule (#12)."),
        GeneratedEntry(13, "Added", "- New mode (#13)."),
    ]

    def test_generates_sections_into_the_placeholder_byte_for_byte(self) -> None:
        expected = """\
# Changelog

## Unreleased

### Added

- New mode (#13).

### Fixed

- Tighten a rule (#12).

## v1.1.0 — 2026-09-01

### Added

- Earlier capability (#1).
"""
        self.assertEqual(compose_unreleased(PLACEHOLDER, self.ENTRIES), expected)

    def test_keeps_curated_bullets_first_and_skips_prs_they_reference(self) -> None:
        curated = _with_unreleased("### Fixed", "", "- Hand-written note", "  wrapped (#12).")
        out = compose_unreleased(curated, [*self.ENTRIES, GeneratedEntry(14, "Fixed", "- Other (#14).")])
        self.assertIn("### Fixed\n\n- Hand-written note\n  wrapped (#12).\n- Other (#14).\n", out)
        self.assertNotIn("Tighten a rule", out)

    def test_is_idempotent(self) -> None:
        once = compose_unreleased(PLACEHOLDER, self.ENTRIES)
        self.assertEqual(compose_unreleased(once, self.ENTRIES), once)

    def test_generated_output_classifies_and_rolls(self) -> None:
        out = compose_unreleased(PLACEHOLDER, self.ENTRIES)
        self.assertEqual(rw.classify_semver_impact(out), "minor")
        rolled = rw.roll_unreleased(out, "1.2.0", "2026-09-11")
        self.assertIn("## v1.2.0 — 2026-09-11\n\n### Added\n\n- New mode (#13).", rolled)

    def test_canonicalizes_a_breaking_changes_heading(self) -> None:
        out = compose_unreleased(_with_unreleased("### Breaking Changes", "", "- Drop a mode."), [])
        self.assertIn("### Breaking\n\n- Drop a mode.\n", out)
        self.assertNotIn("Breaking Changes", out)

    def test_uncategorized_curated_entry_fails_closed(self) -> None:
        with self.assertRaises(rw.AmbiguousReleaseImpact):
            compose_unreleased(_with_unreleased("- stray entry"), self.ENTRIES)

    def test_unrecognized_curated_heading_fails_closed(self) -> None:
        with self.assertRaises(rw.AmbiguousReleaseImpact):
            compose_unreleased(_with_unreleased("### Improved", "", "- x"), self.ENTRIES)

    def test_nothing_to_generate_leaves_the_file_untouched(self) -> None:
        self.assertEqual(compose_unreleased(PLACEHOLDER, []), PLACEHOLDER)

    def test_missing_unreleased_heading_fails_closed(self) -> None:
        with self.assertRaises(rw.AmbiguousReleaseImpact):
            compose_unreleased("# Changelog\n\n## v1.0.0 — 2026-01-01\n", self.ENTRIES)


class CollectEntriesTests(_PatchedRepoCase):
    def test_collects_release_worthy_prs_in_merge_order_and_skips_the_rest(self) -> None:
        repo = self.use(_FakeRepo(
            [
                (_sha(1), "Docs tweak (#10)", [DOCS]),
                (_sha(2), "Tighten rule (#11)", [SKILL]),
                (_sha(3), "Merge pull request #12 from a/b", [SKILL, DOCS]),
                (_sha(4), "chore(release): v1.1.0 [skip ci]", ["CHANGELOG.md"]),
            ],
            {
                11: _merged(11, _sha(2), _body("Fixed", "Tighten a rule")),
                12: _merged(12, _sha(3), _body("Added", "New mode")),
            },
        ))
        self.assertEqual(
            collect_entries(self.root, "v1.1.0"),
            [
                GeneratedEntry(11, "Fixed", "- Tighten a rule (#11)."),
                GeneratedEntry(12, "Added", "- New mode (#12)."),
            ],
        )
        self.assertEqual(repo.fetched, [11, 12])

    def test_every_problem_is_reported_and_fails_closed(self) -> None:
        self.use(_FakeRepo(
            [
                (_sha(1), "Direct push without a PR", [SKILL]),
                (_sha(2), "No intent (#21)", [SKILL]),
                (_sha(3), "Opted out (#22)", [SKILL]),
                (_sha(4), "Wrong commit (#23)", [SKILL]),
                (_sha(5), "Unmerged (#24)", [SKILL]),
                (_sha(6), "Unreadable (#25)", [SKILL]),
            ],
            {
                21: _merged(21, _sha(2), "Just a description."),
                22: _merged(22, _sha(3), _body("none")),
                23: _merged(23, _sha(99), _body("Fixed", "x")),
                24: {**_merged(24, _sha(5), _body("Fixed", "x")), "merged_at": None},
            },
        ))
        with self.assertRaises(ChangelogGenerationError) as ctx:
            collect_entries(self.root, "v1.1.0")
        problems = ctx.exception.problems
        self.assertEqual(len(problems), 6)
        self.assertIn(_sha(1)[:12], problems[0])
        self.assertIn("PR #21", problems[1])
        self.assertIn("'Release category: none'", problems[2])
        self.assertIn("PR #23", problems[3])
        self.assertIn("PR #24", problems[4])
        self.assertIn("could not be read", problems[5])

    def test_problems_never_echo_contributor_text(self) -> None:
        self.use(_FakeRepo(
            [(_sha(1), "Evil (#31)", [SKILL])],
            {31: _merged(31, _sha(1), _body("$(curl evil)", "x"))},
        ))
        with self.assertRaises(ChangelogGenerationError) as ctx:
            collect_entries(self.root, "v1.1.0")
        self.assertNotIn("curl", str(ctx.exception))


class GenerateChangelogCommandTests(_PatchedRepoCase):
    def _repo(self, body: str = _body("Fixed", "Tighten a rule")) -> _FakeRepo:
        return self.use(_FakeRepo([(_sha(2), "Tighten rule (#11)", [SKILL])], {11: _merged(11, _sha(2), body)}))

    def test_writes_the_generated_section(self) -> None:
        self._repo()
        cl = self.changelog()
        rc, _ = self.run_cli("--changelog", str(cl), "generate-changelog")
        self.assertEqual(rc, 0)
        self.assertIn("## Unreleased\n\n### Fixed\n\n- Tighten a rule (#11).\n", cl.read_text(encoding="utf-8"))

    def test_check_mode_does_not_write(self) -> None:
        self._repo()
        cl = self.changelog()
        rc, out = self.run_cli("--changelog", str(cl), "generate-changelog", "--check")
        self.assertEqual(rc, 0)
        self.assertEqual(cl.read_text(encoding="utf-8"), PLACEHOLDER)
        self.assertIn("- Tighten a rule (#11).", out)

    def test_same_state_generates_the_same_bytes(self) -> None:
        self._repo()
        first = self.run_cli("--changelog", str(self.changelog()), "generate-changelog", "--check")[1]
        second = self.run_cli("--changelog", str(self.changelog()), "generate-changelog", "--check")[1]
        self.assertEqual(first, second)
        rerun = self.run_cli("--changelog", str(self.changelog(first)), "generate-changelog", "--check")[1]
        self.assertEqual(rerun, first)

    def test_missing_intent_fails_closed_without_writing(self) -> None:
        self._repo(body="Just a description.")
        cl = self.changelog()
        rc, out = self.run_cli("--changelog", str(cl), "generate-changelog")
        self.assertEqual(rc, 1)
        self.assertIn("::error::PR #11", out)
        self.assertEqual(cl.read_text(encoding="utf-8"), PLACEHOLDER)


class PlanFromReleaseIntentTests(_PatchedRepoCase):
    def _plan(self, changelog_text: str = PLACEHOLDER, summary: bool = False):
        out = self.root / "gh-out.txt"
        args = ["--changelog", str(self.changelog(changelog_text)), "auto-release-plan", "--github-output", str(out)]
        summary_path = self.root / "summary.md"
        if summary:
            args += ["--step-summary", str(summary_path)]
        rc, text = self.run_cli(*args)
        outputs = dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines() if "=" in line)
        return rc, outputs, text, summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""

    def test_version_is_derived_from_generated_entries_alone(self) -> None:
        self.use(_FakeRepo(
            [(_sha(2), "Tighten rule (#11)", [SKILL]), (_sha(3), "New mode (#13)", [SKILL])],
            {
                11: _merged(11, _sha(2), _body("Fixed", "Tighten a rule")),
                13: _merged(13, _sha(3), _body("Added", "New mode")),
            },
        ))
        rc, outputs, _, summary = self._plan(summary=True)
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["should_release"], "true")
        self.assertEqual(outputs["impact"], "minor")
        self.assertEqual(outputs["version"], "1.2.0")
        self.assertIn("## Release notes for v1.2.0", summary)
        self.assertIn("- New mode (#13).", summary)

    def test_patch_only_release(self) -> None:
        self.use(_FakeRepo(
            [(_sha(2), "Tighten rule (#11)", [SKILL])],
            {11: _merged(11, _sha(2), _body("Fixed", "Tighten a rule"))},
        ))
        rc, outputs, _, _ = self._plan()
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["version"], "1.1.1")

    def test_missing_intent_fails_closed_without_contributor_text_in_outputs(self) -> None:
        self.use(_FakeRepo(
            [(_sha(2), "Evil (#11)", [SKILL])],
            {11: _merged(11, _sha(2), _body("$(curl evil)", "x"))},
        ))
        rc, outputs, text, _ = self._plan()
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["should_release"], "false")
        self.assertNotIn("version", outputs)
        self.assertIn("::error::PR #11", text)
        self.assertNotIn("curl", outputs["reason"])

    def test_partially_published_release_is_a_no_op(self) -> None:
        # The release commit (rolled CHANGELOG) landed on main but its tag
        # was never pushed: regenerating must not cut v1.1.1 a second time.
        rolled = PLACEHOLDER.replace(
            "## v1.1.0", "## v1.1.1 — 2026-09-11\n\n### Fixed\n\n- Tighten a rule (#11).\n\n## v1.1.0"
        )
        self.use(_FakeRepo(
            [
                (_sha(2), "Tighten rule (#11)", [SKILL]),
                (_sha(3), "chore(release): v1.1.1 [skip ci]", ["CHANGELOG.md"]),
            ],
            {11: _merged(11, _sha(2), _body("Fixed", "Tighten a rule"))},
        ))
        rc, outputs, _, _ = self._plan(rolled)
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["should_release"], "false")
        self.assertIn("v1.1.1", outputs["reason"])


if __name__ == "__main__":
    unittest.main()
