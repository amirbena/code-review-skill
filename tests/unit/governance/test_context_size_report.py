"""Tests for the mandatory review-context size report."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validation import context_size_report as report
from tests.support.paths import REPO_ROOT

SECTION_TWO = """\
## 2. Required Policy Loading

Always, as one batched operation:
[`a.md`](../../shared/a.md), and [`b.md`](../../shared/b.md#anchor).
In orchestrated contexts, also [`ctx.md`](../../shared/ctx.md).

This Skill's own, always: [`own.md`](policies/own.md).

Conditionally, only when asked: [`cond.md`](../../shared/cond.md) and [`a.md`](../../shared/a.md).

Before step 1, recheck [`stop.md`](../../shared/stop.md).

## 3. Output
"""


def build_repo(root: Path, section_two: str = SECTION_TWO, skill: str = "local-code-review") -> Path:
    files = {
        f"skills/{skill}/SKILL.md": (
            "# Skill\n\nRead [`run.md`](runbooks/run.md) then use [`tpl.md`](templates/tpl.md).\n\n" + section_two
        ),
        f"skills/{skill}/runbooks/run.md": "run\n",
        f"skills/{skill}/templates/tpl.md": "tpl\n",
        f"skills/{skill}/policies/own.md": "own\n",
        "shared/a.md": "aaaa\n",
        "shared/b.md": "bb\n",
        "shared/ctx.md": "ctx\n",
        "shared/cond.md": "cond\n",
        "shared/stop.md": "stop\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = build_repo(Path(self._tmp.name))

    def build(self):
        return report.build_skill_report(self.repo, "local-code-review")

    def test_unconditional_set_comes_from_always_paragraphs(self):
        paths = [f.path for f in self.build().unconditional]
        self.assertEqual(paths, ["shared/a.md", "shared/b.md", "skills/local-code-review/policies/own.md"])

    def test_context_member_is_not_in_the_default_set(self):
        r = self.build()
        self.assertEqual([f.path for f in r.context_conditional], ["shared/ctx.md"])
        self.assertNotIn("shared/ctx.md", [f.path for f in r.unconditional])

    def test_conditional_excludes_files_already_unconditional(self):
        self.assertEqual([f.path for f in self.build().conditional], ["shared/cond.md"])

    def test_paragraphs_without_a_loading_cue_are_ignored(self):
        every = {f.path for g in (self.build().unconditional, self.build().conditional) for f in g}
        self.assertNotIn("shared/stop.md", every)

    def test_procedure_and_templates_come_from_skill_links_outside_section_two(self):
        r = self.build()
        self.assertEqual([f.path for f in r.procedure], ["skills/local-code-review/runbooks/run.md"])
        self.assertEqual([f.path for f in r.output_templates], ["skills/local-code-review/templates/tpl.md"])

    def test_sizes_count_bytes_and_lines(self):
        a = next(f for f in self.build().unconditional if f.path == "shared/a.md")
        self.assertEqual((a.lines, a.bytes, a.est_tokens), (1, 5, 2))

    def test_unresolvable_link_fails_instead_of_being_skipped(self):
        (self.repo / "shared" / "a.md").unlink()
        with self.assertRaises(report.ReportError):
            self.build()

    def test_missing_section_two_fails(self):
        skill_md = self.repo / "skills" / "local-code-review" / "SKILL.md"
        skill_md.write_text("# Skill\n\n## 1. Inputs\n\ntext\n", encoding="utf-8")
        with self.assertRaises(report.ReportError):
            self.build()

    def test_changing_a_listed_file_changes_the_default_set_total(self):
        before = report.total(self.build().unconditional)["bytes"]
        (self.repo / "shared" / "a.md").write_text("aaaa\n" * 10, encoding="utf-8")
        self.assertEqual(report.total(self.build().unconditional)["bytes"], before + 45)


PHASED_SECTION_TWO = SECTION_TWO.replace(
    "This Skill's own, always:",
    "Always, by phase — opened where first used: [`b.md`](../../shared/b.md).\n\nThis Skill's own, always:",
)


class PhaseReportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = build_repo(Path(self._tmp.name), PHASED_SECTION_TWO)

    def test_phased_file_is_reported_apart_from_before_step_1(self):
        r = report.build_skill_report(self.repo, "local-code-review")
        self.assertEqual([f.path for f in r.phased], ["shared/b.md"])
        self.assertNotIn("shared/b.md", [f.path for f in r.unconditional])

    def test_before_step_1_and_whole_review_are_separate_totals(self):
        d = report.report_dict(report.build_skill_report(self.repo, "local-code-review"))
        self.assertEqual(d["whole_review_default"]["bytes"] - d["before_step_1"]["bytes"], 3)

    def test_savings_separate_genuine_from_deferral(self):
        before = {"before_step_1": {"bytes": 100}, "whole_review_default": {"bytes": 100}}
        after = {"before_step_1": {"bytes": 60}, "whole_review_default": {"bytes": 90}}
        self.assertEqual(
            report.savings(before, after), {"before_step_1_bytes": 40, "genuine_bytes": 10, "deferral_bytes": 30}
        )


class RepositoryReportTests(unittest.TestCase):
    def test_output_is_deterministic(self):
        first = json.dumps(report.build(REPO_ROOT), sort_keys=True)
        self.assertEqual(first, json.dumps(report.build(REPO_ROOT), sort_keys=True))

    def test_each_skill_default_set_includes_its_entry_and_core_policies(self):
        data = report.build(REPO_ROOT)
        self.assertEqual([s["skill"] for s in data["skills"]], list(report.SKILLS))
        for skill in data["skills"]:
            paths = {f["path"] for f in skill["entry"]["files"] + skill["unconditional"]["files"]}
            self.assertIn(f"skills/{skill['skill']}/SKILL.md", paths)
            self.assertIn("shared/policies/review-stopping-criteria.md", paths)
            self.assertGreater(skill["headline_entry_plus_unconditional"]["bytes"], 0)

    def test_main_returns_failure_for_an_invalid_repository(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(report.main(["--repo", tmp]), 1)


if __name__ == "__main__":
    unittest.main()
