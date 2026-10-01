"""Contract checks for the relationship capability contract (Issue #603)."""

from __future__ import annotations

import re
import unittest

from tests.reference.review import relationship_capability as rc
from tests.support.paths import REPO_ROOT

RECORD = REPO_ROOT / "docs" / "repository-intelligence" / "relationship-capability-contract.md"
README = REPO_ROOT / "docs" / "repository-intelligence" / "README.md"
MODEL = REPO_ROOT / "docs" / "repository-intelligence" / "repository-intelligence-model.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "review" / "relationship_capability.py"
SCHEMA = REPO_ROOT / "docs" / "capability-architecture" / "capability-manifest-schema.md"

# The contract must stay vendor- and protocol-neutral.
FORBIDDEN_NAMES = (
    "lsp", "language server", "mcp", "ctags", "tree-sitter", "treesitter",
    "sourcegraph", "kythe", "scip", "lsif", "jedi", "pyright", "gopls",
    "clangd", "codeql", "semgrep", "json-rpc", "jsonrpc", "grpc",
)


def _text(path) -> str:
    return path.read_text(encoding="utf-8")


class NeutralityTests(unittest.TestCase):
    def test_contract_and_reference_name_no_provider_or_protocol(self) -> None:
        for path in (RECORD, REFERENCE):
            lowered = _text(path).lower()
            for name in FORBIDDEN_NAMES:
                with self.subTest(path=path.name, name=name):
                    self.assertIsNone(re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", lowered))


class ContractShapeTests(unittest.TestCase):
    def test_every_question_and_fallback_is_documented(self) -> None:
        text = _text(RECORD)
        fallback = text.split("## 8. Fallback for every question", 1)[1].split("\n## ", 1)[0]
        for question in rc.Question:
            with self.subTest(question=question):
                self.assertIn(f"`{question.value}`", text)
                self.assertIn(f"| `{question.value}` |", fallback)

    def test_consumption_covers_stale_unresolved_absent_and_ambiguous(self) -> None:
        text = _text(RECORD)
        for phrase in (
            "Rejected, whole, with no partial use",
            "stale is rejected, not warned",
            "`unresolved`",
            "Absent",
            "never an edge",
        ):
            self.assertIn(phrase.lower(), text.lower())

    def test_absence_requires_attestation(self) -> None:
        self.assertIn("An empty answer says nothing", _text(RECORD))

    def test_outcomes_are_reused_not_redefined(self) -> None:
        text = _text(RECORD)
        self.assertNotIn("| `resolved_none` |", text)
        for outcome in rc.Outcome:
            self.assertIn(outcome.value, text)

    def test_analogue_is_advisory_with_no_gap(self) -> None:
        self.assertIn("no outcome and never renders a Context gap", _text(RECORD))

    def test_worked_examples_cover_seven_cases(self) -> None:
        table = _text(RECORD).split("## 11. Worked examples", 1)[1].split("\n## ", 1)[0]
        rows = [r for r in table.splitlines() if re.match(r"\| \d \|", r)]
        self.assertEqual(len(rows), 7)


class DeclarationTests(unittest.TestCase):
    def test_declaration_uses_only_manifest_schema_fields(self) -> None:
        schema = _text(SCHEMA).split("## Fields", 1)[1].split("\n## ", 1)[0]
        fields = set(re.findall(r"^\| `(\w+)` \|", schema, flags=re.MULTILINE))
        self.assertTrue(fields)
        self.assertLessEqual(set(rc.DECLARATION), fields)
        required = {"capability", "summary", "loads", "adapters", "files", "requires", "never", "benchmark"}
        self.assertLessEqual(required, set(rc.DECLARATION))

    def test_record_yaml_block_matches_reference_declaration(self) -> None:
        block = _text(RECORD).split("```yaml\n", 1)[1].split("```", 1)[0]
        for field in rc.DECLARATION:
            self.assertRegex(block, rf"(?m)^{field}:", msg=field)
        for item in rc.DECLARATION["never"]:
            self.assertIn(item, block)

    def test_no_capability_manifest_or_packaged_change(self) -> None:
        self.assertFalse((REPO_ROOT / "capabilities" / "relationship-query").exists())


class ThreatModelTests(unittest.TestCase):
    def test_threat_implications_are_recorded(self) -> None:
        section = _text(RECORD).split("## 10. Threat-model implications", 1)[1].split("\n## ", 1)[0]
        for threat in ("Fabricated edge", "Omission", "Injection", "Scope widening",
                       "Exfiltration", "Stale or replayed", "Resource abuse", "downgrade"):
            self.assertIn(threat, section)


class WiringTests(unittest.TestCase):
    def test_listed_in_directory_readme_and_model_extension_noted(self) -> None:
        self.assertIn("relationship-capability-contract.md", _text(README))
        self.assertIn("tested_by", _text(MODEL))

    def test_record_links_resolve(self) -> None:
        for target in re.findall(r"\]\((?!http)([^)#]+)", _text(RECORD)):
            with self.subTest(target=target):
                self.assertTrue((RECORD.parent / target).resolve().exists(), target)


if __name__ == "__main__":
    unittest.main()
