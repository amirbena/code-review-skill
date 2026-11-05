"""Structural invariants of the v3 review-core Skill (Issue #843).

Contract: docs/v3-architecture/adr-v3-review-core.md, sections 4, 5.1 and 7.
These tests check ownership and wiring, not wording.

Run with:
    python3 -m unittest tests.unit.review.core.test_review_core_contract
"""

from __future__ import annotations

import json
import re
import unittest

from tests.support.paths import REPO_ROOT

CORE = REPO_ROOT / "skills" / "review-core"
SKILL_MD = CORE / "SKILL.md"
SCHEMA = json.loads((CORE / "templates" / "result.schema.json").read_text(encoding="utf-8"))

# ADR section 7: the guarantees review-core owns, and the file that states each.
CORE_GUARANTEES = {
    "S1": "rules/safety.md",
    "S2": "SKILL.md",
    "S3": "rules/findings.md",
    "S4": "rules/findings.md",
    "S5": "rules/safety.md",
    "S6": "SKILL.md",
    "S10": "rules/safety.md",
}
MINI_SKILL_GUARANTEES = ("S7", "S8", "S9")

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
DEFINITION_RE = re.compile(r"\*\*(S\d+)\*\*")
TRIGGER_RE = re.compile(r"^\d+\. \*\*([a-z-]+)\*\*", re.M)
MINI_SKILL_ROW_RE = re.compile(r"^\| `(review-[a-z-]+)` \|", re.M)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def core_files() -> list:
    return sorted(p for p in CORE.rglob("*") if p.is_file())


def text_files() -> dict[str, str]:
    return {p.relative_to(CORE).as_posix(): p.read_text(encoding="utf-8") for p in core_files() if p.suffix == ".md"}


def skill_md() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


class GuaranteeOwnershipTests(unittest.TestCase):
    def test_each_core_guarantee_is_stated_once_in_its_owner(self) -> None:
        definitions: dict[str, list[str]] = {}
        for rel, text in text_files().items():
            for label in DEFINITION_RE.findall(text):
                definitions.setdefault(label, []).append(rel)
        for label, owner in CORE_GUARANTEES.items():
            with self.subTest(guarantee=label):
                self.assertEqual(definitions.get(label), [owner])

    def test_mini_skill_guarantees_are_not_defined_in_the_core(self) -> None:
        for rel, text in text_files().items():
            for label in DEFINITION_RE.findall(text):
                with self.subTest(file=rel, guarantee=label):
                    self.assertNotIn(label, MINI_SKILL_GUARANTEES)


class LoadingTests(unittest.TestCase):
    def test_every_core_file_is_linked_from_skill_md(self) -> None:
        linked = {(CORE / link.split("#", 1)[0]).resolve() for link in LINK_RE.findall(skill_md())}
        for path in core_files():
            if path != SKILL_MD:
                with self.subTest(file=path.relative_to(CORE).as_posix()):
                    self.assertIn(path.resolve(), linked)

    def test_there_is_no_runbook_or_loading_inventory(self) -> None:
        self.assertFalse((CORE / "runbooks").exists())
        self.assertIsNone(re.search(r"^## 2\.", skill_md(), re.M), "no numbered §2 loading inventory")

    def test_procedure_is_inline_and_numbered(self) -> None:
        procedure = skill_md().split("## Procedure", 1)
        self.assertEqual(len(procedure), 2, "SKILL.md has a Procedure section")
        steps = [int(n) for n in re.findall(r"^(\d+)\. ", procedure[1], re.M)]
        self.assertGreater(len(steps), 1)
        self.assertEqual(steps, list(range(1, len(steps) + 1)))


class LinkBoundaryTests(unittest.TestCase):
    def test_links_stay_inside_the_core_and_resolve(self) -> None:
        for rel, text in text_files().items():
            base = (CORE / rel).parent
            for link in LINK_RE.findall(text):
                if "://" in link or link.startswith("#"):
                    continue
                target = (base / link.split("#", 1)[0]).resolve()
                with self.subTest(file=rel, link=link):
                    self.assertTrue(target.is_relative_to(CORE.resolve()), "links no file outside review-core")
                    self.assertTrue(target.exists())


class SelectionSurfaceTests(unittest.TestCase):
    def test_skill_md_lists_exactly_the_mini_skills_the_result_can_name(self) -> None:
        listed = MINI_SKILL_ROW_RE.findall(skill_md())
        enum = SCHEMA["properties"]["mini_skills"]["items"]["properties"]["name"]["enum"]
        self.assertEqual(listed, enum)
        self.assertNotIn("review-core", listed)

    def test_frontmatter_names_the_skill_and_has_a_short_description(self) -> None:
        match = FRONTMATTER_RE.match(skill_md())
        self.assertIsNotNone(match)
        fields = dict(line.split(": ", 1) for line in match.group(1).splitlines())
        self.assertEqual(fields["name"], "review-core")
        self.assertLessEqual(len(fields["description"]), 200)


class IncompleteTriggerTests(unittest.TestCase):
    def test_incomplete_triggers_are_the_closed_set_of_four(self) -> None:
        stated = TRIGGER_RE.findall((CORE / "rules" / "findings.md").read_text(encoding="utf-8"))
        enum = SCHEMA["properties"]["incomplete"]["items"]["enum"]
        self.assertEqual(stated, enum)
        self.assertEqual(len(stated), 4)

    def test_report_and_result_use_the_same_three_decisions(self) -> None:
        report = (CORE / "templates" / "report.md").read_text(encoding="utf-8")
        result_line = re.search(r"\*\*Result: <([^>]+)>\*\*", report)
        self.assertIsNotNone(result_line)
        rendered = [d.strip() for d in result_line.group(1).split("|")]
        self.assertEqual(rendered, SCHEMA["properties"]["decision"]["enum"])


class PackagingTests(unittest.TestCase):
    def test_core_is_not_packaged_before_the_cutover(self) -> None:
        packaging = REPO_ROOT / "scripts" / "packaging"
        for path in sorted(packaging.rglob("*.py")):
            with self.subTest(file=path.relative_to(REPO_ROOT).as_posix()):
                self.assertNotIn("review-core", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
