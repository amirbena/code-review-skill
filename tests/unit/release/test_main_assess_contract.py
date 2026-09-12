"""Tests for scripts/release_worthiness.py main() / $GITHUB_OUTPUT assess contract."""

from __future__ import annotations

import unittest
import contextlib
import io
import os
import tempfile
from pathlib import Path

from tests.unit.release._shared import (
    COVERED_CHANGELOG,
    PLACEHOLDER_CHANGELOG,
    _unreleased,
    rw,
)

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


if __name__ == "__main__":
    unittest.main()
