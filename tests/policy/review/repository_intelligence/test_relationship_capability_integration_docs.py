"""Contract checks for the packaged relationship-capability consumer (Issue #604)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

POLICIES = REPO_ROOT / "shared" / "policies"
EXPANSION = POLICIES / "repository-expansion.md"
POINTERS = (
    POLICIES / "affected-test-analysis.md",
    POLICIES / "architectural-placement.md",
    POLICIES / "large-pr-partitioning.md",
)
SCALE = REPO_ROOT / "capabilities" / "scale" / "capability.yaml"
LOCAL_TEMPLATE = REPO_ROOT / "skills" / "local-code-review" / "templates" / "local-review-report.md"
GITHUB_TEMPLATE = REPO_ROOT / "skills" / "github-pr-review" / "templates" / "external-review-summary.md"
SECTION = "## Optional relationship capability"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", ""))


def _section() -> str:
    text = EXPANSION.read_text(encoding="utf-8")
    return _norm(text.split(SECTION, 1)[1].split("\n## ", 1)[0])


class ConsumerContractTests(unittest.TestCase):
    def test_section_owns_the_consumption_rules(self) -> None:
        section = _section()
        for phrase in (
            "declared by the host only",
            "absence is not itself a Context gap",
            "never a dump",
            "rejected whole",
            "never counted as absence",
            "attests",
            "`source: capability | search`",
            "never supports a finding",
            "does not cross repositories",
        ):
            self.assertIn(phrase, section)
        for question in ("consumers_of", "implementers_of", "tests_exercising", "analogues_of"):
            self.assertIn(f"`{question}`", section)

    def test_no_new_severity_confidence_or_outcome(self) -> None:
        section = _section()
        self.assertIn("No `confidence` value, severity, finding identity, or Decision rule", section)
        outcomes = re.findall(r"`(resolved_\w+|unresolved)`", section)
        self.assertTrue(set(outcomes) <= {"resolved_relevant", "resolved_none", "unresolved"})

    def test_machine_model_records_source(self) -> None:
        self.assertIn("source: search | capability", EXPANSION.read_text(encoding="utf-8"))

    def test_owning_policies_reference_rather_than_restate(self) -> None:
        for path in POINTERS:
            with self.subTest(path=path.name):
                text = _norm(path.read_text(encoding="utf-8"))
                self.assertIn("repository-expansion.md", text)
                self.assertIn("Optional relationship capability", text)
                self.assertNotIn("rejected whole", text)


class LoadingAndPackagingTests(unittest.TestCase):
    def test_no_new_packaged_file_or_always_loaded_surface(self) -> None:
        text = SCALE.read_text(encoding="utf-8")
        self.assertIn("loads: on-activation", text)
        files = re.search(r"^files:\n((?:  - .+\n)+)", text, flags=re.MULTILINE)
        self.assertIsNotNone(files)
        self.assertEqual(
            files.group(1).split(),
            ["-", "shared/policies/repository-expansion.md", "-", "shared/policies/large-pr-partitioning.md"],
        )
        self.assertIn("requiring an optional host relationship capability", _norm(text))
        self.assertFalse((REPO_ROOT / "capabilities" / "relationship-query").exists())

    def test_declared_capability_activates_scale_loading(self) -> None:
        text = _norm(SCALE.read_text(encoding="utf-8"))
        self.assertIn("the host declares the optional relationship-query capability", text)
        self.assertIn("a relationship question is open", text)

    def test_both_skill_templates_mark_capability_sourced_answers(self) -> None:
        self.assertIn("via capability", LOCAL_TEMPLATE.read_text(encoding="utf-8"))
        self.assertIn("via capability", GITHUB_TEMPLATE.read_text(encoding="utf-8"))

    def test_packaged_text_does_not_link_repository_development_docs(self) -> None:
        text = EXPANSION.read_text(encoding="utf-8")
        self.assertNotIn("docs/repository-intelligence", text)


if __name__ == "__main__":
    unittest.main()
