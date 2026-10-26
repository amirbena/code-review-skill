#!/usr/bin/env python3
"""Bounded, resumable policy loading: truncation, partial reads, recovery, failure (Issue #812)."""

from __future__ import annotations

import re
import unittest

from runtime_platform.benchmark.reference import benchmark_blocking_verdict as bbv
from runtime_platform.benchmark.reference import benchmark_policy_loading as pl
from tests.support.paths import REPO_ROOT

STOPPING = (REPO_ROOT / "shared/policies/review-stopping-criteria.md").read_text(encoding="utf-8")
HEADING = "Bounded, resumable policy loading"
SKILLS = {
    "local-code-review": REPO_ROOT / "skills/local-code-review",
    "github-pr-review": REPO_ROOT / "skills/github-pr-review",
}
RUNBOOKS = {
    "local-code-review": ("local-review",),
    "github-pr-review": ("passive-pr-review", "active-pr-review"),
}
INCOMPLETE = "⚠️ Review Incomplete"
CLEAN = "✅ Review Clean"
BLOCKING = "⚠️ Changes Requested"


def runtime(total: int, *, cap: int | None = None, cutoff: int | None = None):
    """A reader that returns lines first..first+n-1, cut by a per-call `cap` or a hard `cutoff`."""

    calls = []

    def read(path, first, max_lines):
        calls.append(first)
        if len(calls) > 5000:
            raise AssertionError("loading does not terminate")
        end = total if max_lines is None else min(total, first - 1 + max_lines)
        if cap is not None:
            end = min(end, first - 1 + cap)
        if cutoff is not None:
            end = min(end, cutoff)
        return [f"{path}:{i}" for i in range(first, end + 1)]

    return read


class TruncationTests(unittest.TestCase):
    def test_whole_delivery_needs_one_read(self) -> None:
        load = pl.load_file(runtime(500), "a.md", 500)
        self.assertTrue(load.loaded)
        self.assertEqual((load.verified_through, len(load.reads)), (500, 1))

    def test_silent_truncation_is_not_taken_as_complete(self) -> None:
        # The call "succeeds" with 120 of 500 lines; only the extent comparison exposes it.
        first = runtime(500, cap=120)("a.md", 1, None)
        self.assertEqual(len(first), 120)
        load = pl.load_file(runtime(500, cap=120), "a.md", 500)
        self.assertGreater(len(load.reads), 1)
        self.assertEqual(load.verified_through, 500)

    def test_the_cap_is_not_assumed_any_limit_works(self) -> None:
        for cap in (1, 3, 17, 120, 499, 500, 10_000):
            with self.subTest(cap=cap):
                load = pl.load_file(runtime(500, cap=cap), "a.md", 500)
                self.assertTrue(load.loaded)
                self.assertEqual(load.verified_through, 500)


def text_reader(text: str, cap: int | None = None):
    rows = text.split("\n")
    if text == "" or text.endswith("\n"):
        rows.pop()

    def read(path, first, max_lines):
        n = len(rows) if max_lines is None else max_lines
        return rows[first - 1 : first - 1 + (n if cap is None else min(n, cap))]

    return read


class LineCountTests(unittest.TestCase):
    def test_a_final_unterminated_line_counts_and_the_trailing_segment_does_not(self) -> None:
        for text, lines in (("", 0), ("\n", 1), ("a", 1), ("a\n", 1), ("a\nb", 2), ("a\nb\n", 2), ("a\n\nb", 3)):
            with self.subTest(text=text):
                self.assertEqual(pl.count_lines(text), lines)

    def test_a_file_without_a_trailing_newline_loads_with_the_policy_extent(self) -> None:
        text = "a\nb\nc"
        for cap in (None, 1, 2):
            load = pl.load_file(text_reader(text, cap), "a.md", pl.count_lines(text))
            self.assertEqual((load.loaded, load.verified_through), (True, 3))

    def test_the_naive_newline_count_would_reject_the_same_file(self) -> None:
        text = "a\nb\nc"
        load = pl.load_file(text_reader(text), "a.md", text.count("\n"))
        self.assertFalse(load.loaded)
        self.assertIn("disagree", load.reason)

    def test_a_terminated_file_loads_with_both_counts(self) -> None:
        text = "a\nb\nc\n"
        self.assertEqual(pl.count_lines(text), text.count("\n"))
        self.assertTrue(pl.load_file(text_reader(text, 2), "a.md", pl.count_lines(text)).loaded)


class ResumptionTests(unittest.TestCase):
    def test_resume_continues_from_the_last_verified_line_without_rereading(self) -> None:
        load = pl.load_file(runtime(500, cap=120), "a.md", 500)
        expected_start = 1
        for read in load.reads:
            self.assertEqual(read.first_line, expected_start)
            expected_start += read.delivered
        self.assertEqual(expected_start - 1, 500)
        self.assertEqual(sum(r.delivered for r in load.reads), 500)

    def test_ranges_never_exceed_the_longest_span_delivered(self) -> None:
        load = pl.load_file(runtime(500, cap=120), "a.md", 500)
        for read in load.reads[1:]:
            self.assertLessEqual(read.max_lines, 120)

    def test_no_extent_uses_an_end_of_file_probe(self) -> None:
        load = pl.load_file(runtime(500, cap=120), "a.md", None)
        self.assertTrue(load.loaded)
        self.assertEqual(load.verified_through, 500)
        self.assertEqual(load.reads[-1].delivered, 0)

    def test_empty_probe_on_a_short_file_still_loads(self) -> None:
        load = pl.load_file(runtime(40), "a.md", None)
        self.assertEqual((load.loaded, load.verified_through), (True, 40))

    def test_probe_with_no_lines_delivered_is_not_a_complete_load(self) -> None:
        load = pl.load_file(runtime(500, cutoff=0), "a.md", None)
        self.assertEqual((load.loaded, load.verified_through), (False, 0))

    def test_a_bound_learned_on_one_file_carries_to_the_next(self) -> None:
        report = pl.load_required(runtime(500, cap=120), {"a.md": 500, "b.md": 500})
        self.assertEqual(report.coverage, "complete")
        self.assertEqual(report.files[1].reads[0].max_lines, 120)
        self.assertEqual(len(report.files[1].reads), 5)

    def test_a_recovered_load_is_complete_and_has_no_reasons(self) -> None:
        report = pl.load_required(runtime(900, cap=64), {"a.md": 900, "b.md": 900})
        self.assertEqual((report.coverage, report.incomplete_reasons), ("complete", ()))

    def test_a_cap_that_tightens_mid_file_is_followed(self) -> None:
        caps = iter([200, 90, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40])

        def shrinking(path, first, max_lines):
            n = min(next(caps), 500 - first + 1, max_lines or 500)
            return [f"{path}:{i}" for i in range(first, first + n)]

        load = pl.load_file(shrinking, "a.md", 500)
        self.assertEqual((load.loaded, load.verified_through), (True, 500))


class UnrecoverableTests(unittest.TestCase):
    def test_hard_cutoff_fails_with_the_verified_position(self) -> None:
        load = pl.load_file(runtime(500, cap=120, cutoff=300), "severity.md", 500)
        self.assertFalse(load.loaded)
        self.assertEqual(load.verified_through, 300)
        self.assertIn("severity.md verified through line 300 of 500", load.detail)

    def test_failure_ends_on_a_single_line_read(self) -> None:
        load = pl.load_file(runtime(500, cutoff=0), "a.md", 500)
        self.assertEqual(load.reads[-1].max_lines, 1)
        self.assertEqual(load.verified_through, 0)

    def test_over_delivery_disagrees_with_the_extent(self) -> None:
        load = pl.load_file(lambda p, first, n: ["x"] * 50, "a.md", 20)
        self.assertEqual(load.state, pl.LoadState.UNRECOVERABLE)
        self.assertIn("disagree", load.reason)

    def test_a_changed_file_is_not_verified(self) -> None:
        load = pl.load_file(runtime(480), "a.md", 500)
        self.assertFalse(load.loaded)
        self.assertEqual(load.verified_through, 480)

    def test_one_unrecoverable_file_makes_coverage_incomplete_and_names_it(self) -> None:
        def mixed(path, first, n):
            return runtime(100 if path == "ok.md" else 500, cutoff=None if path == "ok.md" else 200, cap=60)(path, first, n)

        report = pl.load_required(mixed, {"ok.md": 100, "bad.md": 500})
        self.assertEqual(report.coverage, "incomplete")
        self.assertEqual(len(report.incomplete_reasons), 1)
        self.assertIn("bad.md verified through line 200 of 500", report.incomplete_reasons[0])

    def test_only_a_failed_recovery_makes_a_definitive_verdict_invalid(self) -> None:
        recovered = pl.load_required(runtime(500, cap=120), {"a.md": 500})
        failed = pl.load_required(runtime(500, cap=120, cutoff=300), {"a.md": 500})
        self.assertEqual((recovered.coverage, failed.coverage), ("complete", "incomplete"))
        incomplete = bbv.classify_rendered_label(INCOMPLETE)
        self.assertIs(incomplete, bbv.RenderedKind.INCOMPLETE)
        for label in (CLEAN, BLOCKING):
            self.assertIsNot(bbv.classify_rendered_label(label), incomplete)



class ContractWiringTests(unittest.TestCase):
    """Fail when the shipped wording drops the loading procedure (mutation: delete or reword it)."""

    section = re.search(rf"^## {HEADING}\n(.*?)(?=^## )", STOPPING, re.M | re.S)

    def test_policy_section_exists_with_four_steps(self) -> None:
        self.assertIsNotNone(self.section)
        steps = re.findall(r"^\d\. \*", self.section.group(1), re.M)
        self.assertEqual(len(steps), 4)

    def test_policy_states_verification_resumption_and_failure_rules(self) -> None:
        text = re.sub(r"\s+", " ", self.section.group(1))
        for needle in (
            "independently of the read",
            "equal that extent",
            "end-of-file probe",
            "Verified content is not read again",
            "neither restarted",
            "Only a failed recovery",
            "verified position",
        ):
            self.assertIn(needle, text)

    def test_policy_hard_codes_no_universal_size(self) -> None:
        sized = re.findall(r"\b\d[\d,]*\s*(?:lines?|KB|MB|bytes?|characters?|chars|tokens?)\b", self.section.group(1))
        self.assertEqual([s for s in sized if not s.startswith(("1 ", "1\n"))], [])

    def test_incomplete_reason_rule_points_at_the_procedure(self) -> None:
        self.assertIn(f'under "{HEADING}"', re.sub(r"\s+", " ", STOPPING))

    def test_neither_skill_prescribes_one_oversized_batch(self) -> None:
        for skill, root in SKILLS.items():
            text = (root / "SKILL.md").read_text(encoding="utf-8")
            section = bbv._SECTION_RE.search(text).group(1)
            with self.subTest(skill=skill):
                self.assertNotIn("one batched operation", section)
                self.assertNotIn("single batched", section)
                self.assertIn("bounded resumable groups", section)
                self.assertIn(HEADING, section)

    def test_every_runbook_checkpoint_resumes_instead_of_restarting(self) -> None:
        for skill, names in RUNBOOKS.items():
            for name in names:
                text = (SKILLS[skill] / "runbooks" / f"{name}.md").read_text(encoding="utf-8")
                checkpoint = next(l for l in text.splitlines() if l.startswith("**Mandatory-loading checkpoint"))
                with self.subTest(skill=skill, runbook=name):
                    self.assertIn(HEADING, checkpoint)
                    self.assertIn("without restarting the review", checkpoint)
                    self.assertIn("only a failed recovery is unloadable", checkpoint)

    def test_both_skills_open_the_pre_runbook_sentence_identically(self) -> None:
        sentences = set()
        for root in SKILLS.values():
            section = bbv._SECTION_RE.search((root / "SKILL.md").read_text(encoding="utf-8")).group(1)
            sentences.add(re.search(r"Before step 1 of the runbook, load the unconditional files above in bounded resumable groups per \[`review-stopping-criteria.md`\]\([^)]+\), \"Bounded, resumable policy loading,\" and confirm each is open in full", section).group(0).split("](")[0])
        self.assertEqual(len(sentences), 1)

    def test_policy_defines_a_line_for_the_extent(self) -> None:
        text = re.sub(r"\s+", " ", self.section.group(1))
        self.assertIn("a file without a trailing newline has one more line than `wc -l` reports", text)

    def test_fail_closed_wording_is_unchanged(self) -> None:
        for skill, root in SKILLS.items():
            text = (root / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertIn("Coverage invariant (mandatory)", text)
                self.assertIn("render `REVIEW INCOMPLETE`, never a definitive verdict", text)


if __name__ == "__main__":
    unittest.main()
