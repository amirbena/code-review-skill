"""Tests for canonical-PR-template structure enforcement (Issue #135)."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.validation import pr_description_length as pr_length
from tests.support.pr_body_fixtures import COMPLIANT_BODY


def _replace(body: str, old: str, new: str) -> str:
    assert old in body, f"fixture drifted: {old!r} not found"
    return body.replace(old, new, 1)


class TemplateContractDerivationTests(unittest.TestCase):
    """The contract is derived from the live template, not hardcoded."""

    def test_required_headings_exclude_the_template_declared_optional_one(self) -> None:
        contract = pr_length.load_template_contract()
        self.assertIn("What", contract.required_headings)
        self.assertIn("Validation", contract.required_headings)
        self.assertNotIn("Review", contract.required_headings)
        self.assertIn("Review", contract.optional_headings)

    def test_only_the_truly_blank_field_is_required(self) -> None:
        contract = pr_length.load_template_contract()
        required_labels = {label for _, label in contract.required_blank_fields}
        self.assertIn("Behavior / contracts", required_labels)
        # Owned by scripts/release/release_lib/release_intent.py, not here.
        self.assertNotIn("Release entry", required_labels)
        self.assertNotIn("Release category", required_labels)
        # Fields the template already defaults to non-empty text are optional.
        self.assertNotIn("Governance / policy", required_labels)
        self.assertNotIn("Changelog", required_labels)

    def test_a_synthetic_template_derives_its_own_contract(self) -> None:
        synthetic = (
            "Fixes #\n\n"
            "## Summary\n\n"
            "- **Impact:**\n"
            "- **Notes:** None\n\n"
            "## Optional Extra\n\n"
            "<!-- Optional: skip when not applicable. -->\n"
            "-\n"
        )
        contract = pr_length.load_template_contract(synthetic)
        self.assertEqual(contract.required_headings, ("Summary",))
        self.assertEqual(contract.optional_headings, ("Optional Extra",))
        self.assertEqual(contract.required_blank_fields, (("Summary", "Impact"),))


class ValidateStructureTests(unittest.TestCase):
    def test_compliant_body_passes(self) -> None:
        result = pr_length.validate_structure(COMPLIANT_BODY)
        self.assertTrue(result.passes, result.issues)

    def test_missing_required_heading_fails_and_names_it(self) -> None:
        body = COMPLIANT_BODY.split("## Validation")[0]
        result = pr_length.validate_structure(body)
        self.assertFalse(result.passes)
        self.assertTrue(any("Validation" in issue.section for issue in result.issues))

    def test_missing_review_heading_is_not_an_error(self) -> None:
        self.assertNotIn("## Review", COMPLIANT_BODY)
        result = pr_length.validate_structure(COMPLIANT_BODY)
        self.assertTrue(result.passes, result.issues)

    def test_empty_required_field_fails_and_names_it(self) -> None:
        body = _replace(COMPLIANT_BODY, "**Behavior / contracts:** Adds a thing.", "**Behavior / contracts:**")
        result = pr_length.validate_structure(body)
        self.assertFalse(result.passes)
        self.assertTrue(any("Behavior / contracts" in issue.message for issue in result.issues))

    def test_placeholder_field_value_fails(self) -> None:
        body = _replace(
            COMPLIANT_BODY,
            "**Behavior / contracts:** Adds a thing.",
            "**Behavior / contracts:** <explain the behavior change>",
        )
        result = pr_length.validate_structure(body)
        self.assertFalse(result.passes)

    def test_missing_field_entirely_fails(self) -> None:
        body = _replace(COMPLIANT_BODY, "- **Behavior / contracts:** Adds a thing.\n", "")
        result = pr_length.validate_structure(body)
        self.assertFalse(result.passes)

    def test_unresolved_fixes_placeholder_fails(self) -> None:
        body = _replace(COMPLIANT_BODY, "Fixes #135", "Fixes #")
        result = pr_length.validate_structure(body)
        self.assertFalse(result.passes)
        self.assertTrue(any(issue.section == "Fixes" for issue in result.issues))

    def test_missing_fixes_line_fails(self) -> None:
        body = _replace(COMPLIANT_BODY, "Fixes #135\n\n", "")
        result = pr_length.validate_structure(body)
        self.assertFalse(result.passes)
        self.assertTrue(any(issue.section == "Fixes" for issue in result.issues))

    def test_empty_validation_section_fails(self) -> None:
        body = _replace(
            COMPLIANT_BODY,
            "- [x] Relevant validation was run, or the reason it could not be run is stated.\n"
            "- Ran `python -m unittest discover -s tests -t .`.\n",
            "- [ ] Relevant validation was run, or the reason it could not be run is stated.\n-\n",
        )
        result = pr_length.validate_structure(body)
        self.assertFalse(result.passes)
        self.assertTrue(any(issue.section == "Validation" for issue in result.issues))

    def test_checked_box_alone_with_no_note_is_sufficient(self) -> None:
        body = _replace(
            COMPLIANT_BODY,
            "- [x] Relevant validation was run, or the reason it could not be run is stated.\n"
            "- Ran `python -m unittest discover -s tests -t .`.\n",
            "- [x] Relevant validation was run, or the reason it could not be run is stated.\n-\n",
        )
        result = pr_length.validate_structure(body)
        self.assertTrue(result.passes, result.issues)

    def test_unchecked_box_with_real_evidence_note_is_sufficient(self) -> None:
        body = _replace(
            COMPLIANT_BODY,
            "- [x] Relevant validation was run, or the reason it could not be run is stated.\n"
            "- Ran `python -m unittest discover -s tests -t .`.\n",
            "- [ ] Relevant validation was run, or the reason it could not be run is stated.\n"
            "- Not run: docs-only change.\n",
        )
        result = pr_length.validate_structure(body)
        self.assertTrue(result.passes, result.issues)

    def test_untouched_release_entry_default_is_not_flagged(self) -> None:
        # "Release entry:" is blank by default and owned by release_intent.py.
        self.assertIn("**Release entry:**\n", COMPLIANT_BODY)
        result = pr_length.validate_structure(COMPLIANT_BODY)
        self.assertTrue(result.passes, result.issues)

    def test_legitimate_prose_with_angle_brackets_is_not_flagged_as_placeholder(self) -> None:
        body = _replace(
            COMPLIANT_BODY,
            "**Behavior / contracts:** Adds a thing.",
            "**Behavior / contracts:** Adds a thing.",  # baseline, kept
        )
        body = body + "\nSee generic type `List<Item>` for details.\n"
        result = pr_length.validate_structure(body)
        self.assertTrue(result.passes, result.issues)

    def test_html_markup_mentioned_in_prose_is_not_flagged_as_placeholder(self) -> None:
        # A bracketed phrase with internal whitespace (an HTML/JSX tag with
        # an attribute) is not swept as a guidance stub merely because it
        # appears somewhere in a filled-in field's prose.
        body = _replace(
            COMPLIANT_BODY,
            "**Behavior / contracts:** Adds a thing.",
            '**Behavior / contracts:** Renders a new `<input type="text">` element for the search box.',
        )
        result = pr_length.validate_structure(body)
        self.assertTrue(result.passes, result.issues)

    def test_issue_messages_name_the_offending_section(self) -> None:
        body = COMPLIANT_BODY.split("## Validation")[0]
        result = pr_length.validate_structure(body)
        self.assertTrue(all(issue.section for issue in result.issues))
        self.assertTrue(all(str(issue).startswith(f"[{issue.section}]") for issue in result.issues))


class CliStructureIntegrationTests(unittest.TestCase):
    def _event(self, body: str | None) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "event.json"
        path.write_text(json.dumps({"pull_request": {"body": body}}), encoding="utf-8")
        return path

    def test_compliant_body_passes_end_to_end(self) -> None:
        event = self._event(COMPLIANT_BODY)
        with redirect_stdout(StringIO()):
            self.assertEqual(pr_length.main(["--event-path", str(event)]), 0)

    def test_structurally_broken_body_fails_and_names_section(self) -> None:
        broken = COMPLIANT_BODY.split("## Validation")[0]
        event = self._event(broken)
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(pr_length.main(["--event-path", str(event)]), 1)
        self.assertIn("Validation", output.getvalue())

    def test_editing_into_compliance_turns_the_check_green(self) -> None:
        broken = _replace(COMPLIANT_BODY, "**Behavior / contracts:** Adds a thing.", "**Behavior / contracts:**")
        fixed = COMPLIANT_BODY
        with redirect_stdout(StringIO()):
            self.assertEqual(pr_length.main(["--event-path", str(self._event(broken))]), 1)
            self.assertEqual(pr_length.main(["--event-path", str(self._event(fixed))]), 0)


if __name__ == "__main__":
    unittest.main()
