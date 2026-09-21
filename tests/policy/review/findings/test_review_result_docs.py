#!/usr/bin/env python3
"""Documentation-contract checks for the review result schema (Issue #67).

Pins docs/review-result/: the navigational README, the model record, the
schema and example files, that every canonical-owner pointer resolves, that
every finding field traces to finding.md, and that the design is wired into
the architecture map and the reference-module registry without being
packaged.

Run with:
    python3 -m unittest tests.policy.review.findings.test_review_result_docs
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.integration.packaging import _shared
from tests.support.paths import REPO_ROOT

DOCDIR = REPO_ROOT / "docs" / "review-result"
README = DOCDIR / "README.md"
MODEL = DOCDIR / "review-result-model.md"
SCHEMA = DOCDIR / "review-result.schema.json"
EXAMPLE = DOCDIR / "examples" / "review-result.example.json"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
FINDING_TEMPLATE = REPO_ROOT / "shared" / "templates" / "finding.md"
PACKAGE_MANIFEST = REPO_ROOT / "scripts" / "packaging" / "package-manifest.json"

# Directories a `$comment` may name a canonical owner by bare file name.
OWNER_DIRS = (
    REPO_ROOT / "shared" / "templates",
    REPO_ROOT / "shared" / "policies",
    REPO_ROOT / "docs" / "findings",
    REPO_ROOT / "docs" / "finding-confidence",
    REPO_ROOT / "skills" / "local-code-review",
    REPO_ROOT / "skills" / "github-pr-review",
)
OWNER_FILE = re.compile(r"[A-Za-z0-9_./-]+\.(?:md|json|py)")
MARKDOWN_LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")

# Finding properties that are not bold field labels in finding.md: the
# resolution flag lives in its "Fix/action location" section, and identity
# is owned by the identity contract.
NOT_FINDING_TEMPLATE_LABELS = {"fix_location_resolved", "identity"}


def _comments(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$comment" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_comments(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_comments(item))
    return found


def _owner_exists(token: str) -> bool:
    if "/" in token:
        return (REPO_ROOT / token).exists()
    return any(next(d.rglob(token), None) for d in OWNER_DIRS)


class FilesAndLinksTests(unittest.TestCase):
    def test_files_exist(self) -> None:
        for path in (README, MODEL, SCHEMA, EXAMPLE):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())

    def test_readme_maps_every_artifact(self) -> None:
        text = README.read_text(encoding="utf-8")
        for target in (
            "review-result-model.md",
            "review-result.schema.json",
            "examples/review-result.example.json",
            "../../tests/reference/review/review_result.py",
        ):
            with self.subTest(target=target):
                self.assertIn(f"]({target})", text)

    def test_markdown_links_resolve(self) -> None:
        for doc in (README, MODEL):
            for target in MARKDOWN_LINK.findall(doc.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://")):
                    continue
                with self.subTest(doc=doc.name, target=target):
                    self.assertTrue((doc.parent / target).resolve().exists())

    def test_every_schema_comment_owner_resolves(self) -> None:
        comments = _comments(json.loads(SCHEMA.read_text(encoding="utf-8")))
        self.assertTrue(comments)
        for comment in comments:
            for token in OWNER_FILE.findall(comment):
                if token in {"review-result-model.md", "review_result.py"}:
                    continue
                with self.subTest(token=token):
                    self.assertTrue(_owner_exists(token), f"{token!r} names no repository file")


class OwnerPathResolutionTests(unittest.TestCase):
    def test_bare_name_resolves_by_file_name(self) -> None:
        self.assertTrue(_owner_exists("finding.md"))

    def test_qualified_path_must_be_exact(self) -> None:
        self.assertTrue(_owner_exists("shared/templates/finding.md"))
        self.assertFalse(_owner_exists("shared/policies/finding.md"))


class OwnerTraceabilityTests(unittest.TestCase):
    def test_every_finding_field_traces_to_the_canonical_template(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        template = FINDING_TEMPLATE.read_text(encoding="utf-8")
        for name in schema["definitions"]["finding"]["properties"]:
            if name in NOT_FINDING_TEMPLATE_LABELS:
                continue
            spellings = {name, name.replace("_", " "), name.replace("_", "-")}
            with self.subTest(field=name):
                self.assertTrue(
                    any(f"**{s}**" in template for s in spellings),
                    f"{name!r} is not a field in finding.md",
                )

    def test_unresolved_location_flag_is_attributed_to_its_real_section(self) -> None:
        row = next(
            line for line in MODEL.read_text(encoding="utf-8").splitlines()
            if line.startswith("| `findings[].fix_location_resolved`")
        )
        self.assertIn("Fix/action location, evidence location, publication", row)
        self.assertIn("introduced by this schema", row)

    def test_model_names_the_owner_of_each_decision_source(self) -> None:
        text = MODEL.read_text(encoding="utf-8")
        for owner in (
            "shared/templates/finding.md",
            "shared/policies/severity.md",
            "review-stopping-criteria.md",
            "reviewed-sha-state-contract.md",
            "finding-stable-identity.md",
        ):
            with self.subTest(owner=owner):
                self.assertIn(owner, text)

    def test_model_defers_versioning_and_emission(self) -> None:
        text = MODEL.read_text(encoding="utf-8")
        for issue in ("#68", "#69", "#70"):
            with self.subTest(issue=issue):
                self.assertRegex(text, rf"issues/{issue[1:]}\)")


class WiringAndPackagingTests(unittest.TestCase):
    def test_architecture_map_links_the_record(self) -> None:
        self.assertIn("review-result/README.md", ARCHITECTURE.read_text(encoding="utf-8"))

    def test_reference_module_is_registered_as_test_only(self) -> None:
        self.assertIn("review_result.py", _shared.REFERENCE_TEST_MODULES)

    def test_design_record_is_not_packaged(self) -> None:
        manifest = PACKAGE_MANIFEST.read_text(encoding="utf-8")
        self.assertNotIn("review-result", manifest)
        self.assertNotIn("review_result", manifest)


if __name__ == "__main__":
    unittest.main()
