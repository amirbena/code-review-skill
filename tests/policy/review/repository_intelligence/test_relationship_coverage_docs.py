"""Contract checks for relationship coverage semantics (Issue #601)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

EXPANSION = REPO_ROOT / "shared" / "policies" / "repository-expansion.md"
STOPPING = REPO_ROOT / "shared" / "policies" / "review-stopping-criteria.md"
SUMMARY = REPO_ROOT / "shared" / "templates" / "review-summary.md"
RECORD = REPO_ROOT / "docs" / "repository-intelligence" / "relationship-coverage-semantics.md"
RECORD_README = REPO_ROOT / "docs" / "repository-intelligence" / "README.md"
LOCAL_TEMPLATE = REPO_ROOT / "skills" / "local-code-review" / "templates" / "local-review-report.md"
GITHUB_TEMPLATE = REPO_ROOT / "skills" / "github-pr-review" / "templates" / "external-review-summary.md"

OUTCOMES = ("resolved_relevant", "resolved_none", "unresolved")
CLASSES = ("caller_consumer", "implementation_interface", "affected_test")


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").replace("**", ""))


def _section(path: Path, heading: str) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


class RelationshipOutcomeContractTests(unittest.TestCase):
    def test_outcomes_and_classes_are_defined_once(self) -> None:
        section = _section(EXPANSION, "## Relationship outcomes and unresolved relationships")
        for token in OUTCOMES + CLASSES:
            self.assertIn(f"`{token}`", section)
        for path in (STOPPING, SUMMARY, LOCAL_TEMPLATE, GITHUB_TEMPLATE):
            with self.subTest(path=path):
                self.assertNotIn("| `resolved_none` |", path.read_text(encoding="utf-8"))

    def test_absence_is_established_not_inferred(self) -> None:
        norm = _norm(EXPANSION)
        self.assertIn("Absence is established, never inferred", norm)
        self.assertIn("The ring ceiling is not a verdict", norm)

    def test_unlisted_classes_are_out_of_scope(self) -> None:
        norm = _norm(EXPANSION)
        self.assertIn("architectural analogue and relevant dependency", norm)
        self.assertIn("out of scope", norm)

    def test_machine_model_carries_the_outcome(self) -> None:
        text = EXPANSION.read_text(encoding="utf-8")
        self.assertIn("outcome: resolved_relevant | resolved_none | unresolved", text)

    def test_ring_ceiling_and_stop_at_first_ring_unchanged(self) -> None:
        text = EXPANSION.read_text(encoding="utf-8")
        self.assertIn("Stop at the first ring", text)
        self.assertIn("| `standard` | Ring 1", text)
        self.assertIn("| `deep` | Ring 3.", text)


class CoverageDecisionTests(unittest.TestCase):
    def test_incomplete_trigger_set_stays_closed_at_four(self) -> None:
        section = _section(STOPPING, "## Incomplete triggers")
        numbered = re.findall(r"^\d+\. \*\*", section, flags=re.MULTILINE)
        self.assertEqual(len(numbered), 4)
        self.assertIn("is likewise not a fifth trigger", _norm(STOPPING))

    def test_rejected_alternative_is_recorded(self) -> None:
        self.assertIn("The rejected alternative", _norm(STOPPING))
        record = _norm(RECORD)
        self.assertIn("Rejected.", record)
        self.assertIn("maintainer sign-off", record)

    def test_unresolved_never_changes_coverage_or_decision(self) -> None:
        norm = _norm(EXPANSION)
        self.assertIn("never turns coverage to incomplete", norm.replace("`", ""))
        self.assertIn("No second evidence-state model", norm)
        self.assertIn("adds no `confidence` value", norm)


class UnresolvedPresentationTests(unittest.TestCase):
    def test_summary_renders_context_gaps_before_validation(self) -> None:
        text = SUMMARY.read_text(encoding="utf-8")
        self.assertLess(text.index("### Context gaps"), text.index("### Validation"))
        self.assertIn("omitted entirely", _norm(SUMMARY))

    def test_both_skill_templates_carry_outcomes_and_gap_note(self) -> None:
        self.assertIn("Relationship outcomes:", LOCAL_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("repository_relationship_outcomes:", GITHUB_TEMPLATE.read_text(encoding="utf-8"))
        for path in (LOCAL_TEMPLATE, GITHUB_TEMPLATE):
            with self.subTest(path=path):
                self.assertIn("Context gaps", path.read_text(encoding="utf-8"))


class DesignRecordTests(unittest.TestCase):
    def test_worked_example_per_class_and_outcome(self) -> None:
        record = RECORD.read_text(encoding="utf-8")
        table = record.split("## 5. Worked examples", 1)[1].split("\n## ", 1)[0]
        rows = [r for r in table.splitlines() if r.startswith("| `")]
        self.assertEqual([r.split("`")[1] for r in rows], list(CLASSES))
        for row in rows:
            self.assertEqual(len(row.strip("|").split("|")), 4)

    def test_listed_in_directory_readme(self) -> None:
        self.assertIn("relationship-coverage-semantics.md", RECORD_README.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
