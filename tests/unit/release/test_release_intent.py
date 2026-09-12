#!/usr/bin/env python3
"""Parsing and rendering of a pull request description's release intent.

Contract: docs/RELEASE.md, "Release intent".
"""

from __future__ import annotations

import sys
import unittest

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from release_lib.release_intent import (  # noqa: E402
    NO_RELEASE,
    ReleaseIntent,
    ReleaseIntentError,
    parse_release_intent,
    render_bullet,
)

TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"


def _body(category: str, entry: str = "") -> str:
    return (
        "## What\n\n"
        "- **Behavior / contracts:** something\n"
        f"- **Release category:** {category}\n"
        f"- **Release entry:** {entry}\n"
    )


class ParseReleaseIntentTests(unittest.TestCase):
    def test_template_shaped_lines_parse(self) -> None:
        intent = parse_release_intent(_body("Fixed", "Tighten a rule"))
        self.assertEqual(intent, ReleaseIntent("Fixed", "Tighten a rule"))
        self.assertEqual(intent.impact, "patch")
        self.assertTrue(intent.ships_entry)

    def test_plain_lines_and_case_insensitive_category(self) -> None:
        intent = parse_release_intent("Release category: added\nRelease entry: New mode\n")
        self.assertEqual(intent, ReleaseIntent("Added", "New mode"))
        self.assertEqual(intent.impact, "minor")

    def test_backticks_and_bold_around_the_key(self) -> None:
        intent = parse_release_intent("* **Release category**: `Security`\n* **Release entry**: Patch a hole\n")
        self.assertEqual(intent, ReleaseIntent("Security", "Patch a hole"))

    def test_every_category_maps_to_its_bump(self) -> None:
        for value, category, impact in (
            ("Added", "Added", "minor"),
            ("Changed", "Changed", "minor"),
            ("Deprecated", "Deprecated", "minor"),
            ("Fixed", "Fixed", "patch"),
            ("Security", "Security", "patch"),
            ("Removed", "Removed", "major"),
            ("Breaking", "Breaking", "major"),
            ("Breaking Changes", "Breaking", "major"),
        ):
            with self.subTest(value=value):
                intent = parse_release_intent(_body(value, "Entry"))
                self.assertEqual(intent.category, category)
                self.assertEqual(intent.impact, impact)

    def test_none_needs_no_entry(self) -> None:
        intent = parse_release_intent(_body("none"))
        self.assertEqual(intent.category, NO_RELEASE)
        self.assertFalse(intent.ships_entry)
        self.assertIsNone(intent.impact)

    def test_crlf_bodies_parse(self) -> None:
        intent = parse_release_intent(_body("Changed", "Reword output").replace("\n", "\r\n"))
        self.assertEqual(intent, ReleaseIntent("Changed", "Reword output"))

    def test_missing_category_fails_closed(self) -> None:
        for body in (None, "", "Just a description.", "Release entry: orphan\n"):
            with self.subTest(body=body), self.assertRaises(ReleaseIntentError):
                parse_release_intent(body)

    def test_unknown_category_fails_closed_without_echoing_it(self) -> None:
        with self.assertRaises(ReleaseIntentError) as ctx:
            parse_release_intent(_body("$(curl evil)", "x"))
        self.assertNotIn("curl", str(ctx.exception))

    def test_shipping_category_needs_a_real_entry(self) -> None:
        for entry in ("", "<one line>", "TBD", "_No response_", "..."):
            with self.subTest(entry=entry), self.assertRaises(ReleaseIntentError):
                parse_release_intent(_body("Fixed", entry))

    def test_entry_must_be_one_line_of_prose(self) -> None:
        for entry in ("# heading", "- nested bullet", "> quote", "1. numbered"):
            with self.subTest(entry=entry), self.assertRaises(ReleaseIntentError):
                parse_release_intent(_body("Fixed", entry))

    def test_duplicate_fields_fail_closed(self) -> None:
        with self.assertRaises(ReleaseIntentError):
            parse_release_intent(_body("Fixed", "a") + "Release category: Added\n")

    def test_guidance_in_html_comments_is_ignored(self) -> None:
        body = "<!-- Release category: Added\nRelease entry: from a comment -->\n" + _body("Fixed", "real")
        self.assertEqual(parse_release_intent(body), ReleaseIntent("Fixed", "real"))

    def test_examples_in_fenced_code_are_ignored(self) -> None:
        body = "```text\nRelease category: Removed\nRelease entry: example\n```\n" + _body("Fixed", "real")
        self.assertEqual(parse_release_intent(body), ReleaseIntent("Fixed", "real"))

    def test_the_pr_template_defaults_to_none(self) -> None:
        intent = parse_release_intent(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(intent.category, NO_RELEASE)


class RenderBulletTests(unittest.TestCase):
    def test_appends_the_pr_reference_in_house_style(self) -> None:
        self.assertEqual(render_bullet(ReleaseIntent("Fixed", "Tighten a rule."), 42), "- Tighten a rule (#42).")
        self.assertEqual(render_bullet(ReleaseIntent("Fixed", "Tighten a rule"), 42), "- Tighten a rule (#42).")

    def test_keeps_an_existing_reference(self) -> None:
        self.assertEqual(
            render_bullet(ReleaseIntent("Fixed", "Tighten a rule (#42)."), 42), "- Tighten a rule (#42)."
        )

    def test_none_renders_no_bullet(self) -> None:
        with self.assertRaises(ValueError):
            render_bullet(ReleaseIntent(NO_RELEASE, ""), 42)


if __name__ == "__main__":
    unittest.main()
