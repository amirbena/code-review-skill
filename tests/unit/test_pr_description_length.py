"""Tests for deterministic pull-request body length enforcement."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts import pr_description_length as pr_length


class UsefulContentTests(unittest.TestCase):
    def test_empty_and_null_body(self) -> None:
        self.assertEqual(pr_length.measure_body(None), 0)
        self.assertEqual(pr_length.measure_body(""), 0)

    def test_below_exact_boundary_and_above(self) -> None:
        self.assertTrue(pr_length.validate_body("x" * 9, limit=10).passes)
        self.assertTrue(pr_length.validate_body("x" * 10, limit=10).passes)
        result = pr_length.validate_body("x" * 11, limit=10)
        self.assertFalse(result.passes)
        self.assertEqual(result.over_by, 1)

    def test_multiline_markdown_counts_after_outer_trim(self) -> None:
        body = "\n# What\n\n- first\n- second\n"
        self.assertEqual(pr_length.useful_content(body), "# What\n\n- first\n- second")
        self.assertEqual(pr_length.measure_body(body), 24)

    def test_unicode_counts_code_points_not_utf8_bytes(self) -> None:
        body = "שלום 🚀 café"
        self.assertEqual(pr_length.measure_body(body), len(body))
        self.assertGreater(len(body.encode("utf-8")), pr_length.measure_body(body))

    def test_html_comments_and_template_guidance_are_excluded(self) -> None:
        body = "<!-- template guidance\nspans lines -->\nVisible"
        self.assertEqual(pr_length.useful_content(body), "Visible")
        self.assertEqual(pr_length.measure_body(body), 7)

    def test_content_around_comments_remains_counted(self) -> None:
        self.assertEqual(pr_length.useful_content("before<!-- hidden -->after"), "beforeafter")

    def test_markdown_links_and_syntax_count_as_written(self) -> None:
        body = "[Issue](https://example.test/149)"
        self.assertEqual(pr_length.measure_body(body), len(body))

    def test_line_endings_normalize_deterministically(self) -> None:
        expected = "one\ntwo\nthree"
        self.assertEqual(pr_length.useful_content("one\r\ntwo\rthree"), expected)

    def test_motivating_outlier_size_exceeds_canonical_limit(self) -> None:
        result = pr_length.validate_body("x" * (pr_length.PR_BODY_HARD_LIMIT + 543))
        self.assertFalse(result.passes)


class EventPayloadTests(unittest.TestCase):
    def _event(self, body: str | None) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "event.json"
        path.write_text(json.dumps({"pull_request": {"body": body}}), encoding="utf-8")
        return path

    def test_reads_actual_pull_request_body(self) -> None:
        self.assertEqual(pr_length.body_from_event(self._event("current body")), "current body")

    def test_missing_pull_request_body_fails_closed(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "event.json"
        path.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pull_request.body"):
            pr_length.body_from_event(path)

    def test_body_only_correction_changes_failure_to_success(self) -> None:
        overlong = self._event("x" * (pr_length.PR_BODY_HARD_LIMIT + 1))
        concise = self._event("short summary")
        with redirect_stdout(StringIO()):
            self.assertEqual(pr_length.main(["--event-path", str(overlong)]), 1)
            self.assertEqual(pr_length.main(["--event-path", str(concise)]), 0)

    def test_failure_output_is_actionable(self) -> None:
        event = self._event("x" * (pr_length.PR_BODY_HARD_LIMIT + 23))
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(pr_length.main(["--event-path", str(event)]), 1)
        text = output.getvalue()
        self.assertIn(f"{pr_length.PR_BODY_HARD_LIMIT + 23:,}", text)
        self.assertIn(f"{pr_length.PR_BODY_HARD_LIMIT:,}", text)
        self.assertIn("23 over", text)
        self.assertIn("canonical Issues, docs, policies, or runbooks", text)


if __name__ == "__main__":
    unittest.main()
