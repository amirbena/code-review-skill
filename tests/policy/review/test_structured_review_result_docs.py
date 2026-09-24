#!/usr/bin/env python3
"""Drift guards for the opt-in structured review result (Issue #69).

The packaged policy restates the review-result schema's shape and the
finding-identity minting recipe so a portable Skill can emit them without
the repository's `docs/`. These tests keep that restatement pinned to the
schema and to the test-only identity reference model.
"""

from __future__ import annotations

import json
import re
import unittest

from tests.reference.review import finding_identity
from tests.reference.review.review_result import validate_review_result
from tests.support.paths import REPO_ROOT

POLICY = REPO_ROOT / "shared/policies/structured-output.md"
SCHEMA = REPO_ROOT / "docs/review-result/review-result.schema.json"
SKILL = REPO_ROOT / "skills/local-code-review/SKILL.md"
RUNBOOK = REPO_ROOT / "skills/local-code-review/runbooks/local-review.md"
TEMPLATE = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
OPTIONS = REPO_ROOT / "shared/policies/invocation-options.md"
LOCAL_YAML = REPO_ROOT / "skills/local-code-review/metadata/skill.yaml"


def _keys_in_policy(text: str, keys: list[str]) -> list[str]:
    return [k for k in keys if f"`{k}`" not in text]


class StructuredReviewResultPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = POLICY.read_text(encoding="utf-8")
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_every_schema_key_is_named(self) -> None:
        props = self.schema["properties"]
        finding = self.schema["definitions"]["finding"]["properties"]
        for label, keys in (
            ("top-level", list(props)),
            ("reviewed_state", list(props["reviewed_state"]["properties"])),
            ("finding", list(finding)),
            ("identity", list(finding["identity"]["properties"])),
        ):
            with self.subTest(label=label):
                self.assertEqual(_keys_in_policy(self.policy, keys), [])

    def test_schema_version_matches_current_schema(self) -> None:
        self.assertIn(f'`"{self.schema["properties"]["schema_version"]["const"]}"`', self.policy)

    def test_enum_values_are_named(self) -> None:
        finding = self.schema["definitions"]["finding"]["properties"]
        enums = [
            self.schema["properties"]["skill"]["enum"][:1],
            self.schema["properties"]["coverage"]["enum"],
            self.schema["properties"]["decision"]["properties"]["outcome"]["enum"],
            finding["severity"]["enum"],
            finding["runtime_validation"]["enum"],
            finding["confidence"]["enum"],
        ]
        for values in enums:
            for value in values:
                with self.subTest(value=value):
                    self.assertIn(f'"{value}"', self.policy)

    def test_required_keys_are_documented_as_required(self) -> None:
        finding = self.schema["definitions"]["finding"]
        optional = set(finding["properties"]) - set(finding["required"])
        section = self.policy.split("## Finding object", 1)[1].split("## Finding identity", 1)[0]
        for key in finding["required"]:
            with self.subTest(key=key):
                self.assertRegex(section, rf"`{key}`[^\n]*\| yes \|")
        for key in optional:
            with self.subTest(key=key):
                self.assertRegex(section, rf"`{key}`[^\n]*\| no \|")

    def test_identity_recipe_matches_reference_model(self) -> None:
        text = self.policy
        for connective in finding_identity.CAUSE_BEHAVIOR_CONNECTIVES:
            self.assertIn(f"`{connective}`", text)
        for value in finding_identity.LOCATION_INTENTS + finding_identity.CONSTRUCT_KINDS:
            self.assertIn(f"`{value}`", text)
        rows = re.findall(r"^\| `([a-z_]+)`(?: / `([a-z_]+)`)? \|", text.split("**Descriptor fields**", 1)[1], re.M)
        documented = [name for row in rows for name in row if name]
        self.assertEqual(documented, list(finding_identity.DISCRIMINATING_FIELDS))
        self.assertIn(f"`{finding_identity.IDENTITY_SCHEME}\\x1e`", text)
        self.assertIn("fid_v1_", text)
        self.assertIn("first 32 lowercase hex", text)
        for field in finding_identity.STRONG_SEMANTIC_FIELDS:
            self.assertIn(f"`{field}`", text.split("**`matching_eligible`**", 1)[1])

    def test_policy_example_is_a_valid_review_result(self) -> None:
        blocks = re.findall(r"```json\n(.*?)\n```", self.policy, re.S)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(validate_review_result(json.loads(blocks[0])), ())

    def test_policy_is_portable_and_defaults_off(self) -> None:
        self.assertNotIn("](../../skills/", self.policy)
        self.assertNotIn("AGENTS.md", self.policy)
        self.assertIn("default `false`", self.policy)
        self.assertIn("unchanged", self.policy)

    def test_skill_wiring_is_opt_in_and_registered(self) -> None:
        for path in (SKILL, RUNBOOK, TEMPLATE, LOCAL_YAML, OPTIONS):
            with self.subTest(path=path.name):
                self.assertIn("structured", path.read_text(encoding="utf-8").lower())
        self.assertIn("structured_review_result", SKILL.read_text(encoding="utf-8"))
        self.assertIn("If, and only if", RUNBOOK.read_text(encoding="utf-8").split("13b.", 1)[1])


if __name__ == "__main__":
    unittest.main()
