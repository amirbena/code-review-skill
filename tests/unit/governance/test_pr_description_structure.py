"""Tests for canonical-PR-template structure enforcement (Issue #135)."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from scripts.validation import pr_description_length as pr_length
from tests.support.pr_body_fixtures import (
    COMPLIANT_BODY,
    COMPLIANT_BODY_NO_ISSUE,
    RUNTIME_DEFAULT_SUMMARY_BODY,
)


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

    def test_explicit_fixes_na_passes_for_issue_less_maintainer_work(self) -> None:
        result = pr_length.validate_structure(COMPLIANT_BODY_NO_ISSUE)
        self.assertTrue(result.passes, result.issues)

    def test_fixes_na_is_case_insensitive(self) -> None:
        body = _replace(COMPLIANT_BODY, "Fixes #135", "Fixes #n/a")
        result = pr_length.validate_structure(body)
        self.assertTrue(result.passes, result.issues)

    def test_fixes_na_does_not_relax_the_blank_placeholder_check(self) -> None:
        # "N/A" is a deliberate, distinct value — not a loophole that makes
        # any non-empty-looking suffix pass.
        body = _replace(COMPLIANT_BODY, "Fixes #135", "Fixes #not-a-real-issue")
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


class LocalPreflightTests(unittest.TestCase):
    """Regression coverage for the local `--pr-body-env` preflight (Issue #135
    follow-up): an agent must be able to validate a drafted PR body before
    `gh pr create` / `gh pr edit`, using the exact same logic CI runs."""

    def test_body_from_env_reads_the_named_variable(self) -> None:
        with mock.patch.dict("os.environ", {"PR_BODY": COMPLIANT_BODY}, clear=False):
            self.assertEqual(pr_length.body_from_env("PR_BODY"), COMPLIANT_BODY)

    def test_body_from_env_missing_variable_raises(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                pr_length.body_from_env("PR_BODY")

    def test_compliant_body_passes_the_local_preflight(self) -> None:
        with mock.patch.dict("os.environ", {"PR_BODY": COMPLIANT_BODY}, clear=False):
            with redirect_stdout(StringIO()):
                self.assertEqual(pr_length.main(["--pr-body-env", "PR_BODY"]), 0)

    def test_runtime_default_summary_test_plan_body_fails_the_local_preflight(self) -> None:
        # Regression for the competing-instruction failure mode: a body
        # shaped like a generic coding-agent default, never read from the
        # live .github/PULL_REQUEST_TEMPLATE.md, must not pass.
        with mock.patch.dict("os.environ", {"PR_BODY": RUNTIME_DEFAULT_SUMMARY_BODY}, clear=False):
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(pr_length.main(["--pr-body-env", "PR_BODY"]), 1)
            self.assertIn("does not match the PR template", output.getvalue())

    def test_runtime_default_body_fails_direct_structure_validation_too(self) -> None:
        result = pr_length.validate_structure(RUNTIME_DEFAULT_SUMMARY_BODY)
        self.assertFalse(result.passes)
        sections = {issue.section for issue in result.issues}
        self.assertIn("What", sections)
        self.assertIn("Fixes", sections)

    def test_missing_required_section_fails_the_local_preflight(self) -> None:
        broken = COMPLIANT_BODY.split("## Validation")[0]
        with mock.patch.dict("os.environ", {"PR_BODY": broken}, clear=False):
            with redirect_stdout(StringIO()):
                self.assertEqual(pr_length.main(["--pr-body-env", "PR_BODY"]), 1)

    def test_unresolved_placeholder_fails_the_local_preflight(self) -> None:
        broken = _replace(
            COMPLIANT_BODY,
            "**Behavior / contracts:** Adds a thing.",
            "**Behavior / contracts:** <explain the behavior change>",
        )
        with mock.patch.dict("os.environ", {"PR_BODY": broken}, clear=False):
            with redirect_stdout(StringIO()):
                self.assertEqual(pr_length.main(["--pr-body-env", "PR_BODY"]), 1)

    def test_event_path_and_pr_body_env_are_mutually_exclusive(self) -> None:
        with self.assertRaises(SystemExit):
            with redirect_stdout(StringIO()), mock.patch("sys.stderr", StringIO()):
                pr_length.main(["--event-path", "x", "--pr-body-env", "PR_BODY"])

    def test_one_source_is_required(self) -> None:
        with self.assertRaises(SystemExit):
            with redirect_stdout(StringIO()), mock.patch("sys.stderr", StringIO()):
                pr_length.main([])

    def test_local_preflight_and_ci_entrypoint_share_the_same_validation_logic(self) -> None:
        """CI (`--event-path`) and the local preflight (`--pr-body-env`) must
        reach identical verdicts for the same body — they call the same
        `_report`/`validate_structure`/`validate_body` functions, never a
        second parallel implementation."""
        for body in (COMPLIANT_BODY, RUNTIME_DEFAULT_SUMMARY_BODY):
            directory = tempfile.TemporaryDirectory()
            self.addCleanup(directory.cleanup)
            event_path = Path(directory.name) / "event.json"
            event_path.write_text(json.dumps({"pull_request": {"body": body}}), encoding="utf-8")

            with redirect_stdout(StringIO()):
                ci_result = pr_length.main(["--event-path", str(event_path)])
            with mock.patch.dict("os.environ", {"PR_BODY": body}, clear=False):
                with redirect_stdout(StringIO()):
                    local_result = pr_length.main(["--pr-body-env", "PR_BODY"])

            self.assertEqual(ci_result, local_result)


if __name__ == "__main__":
    unittest.main()
