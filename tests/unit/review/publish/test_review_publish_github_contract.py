"""Structural invariants of the v3 review-publish-github Skill (Issue #844).

Contract: docs/v3-architecture/adr-v3-review-core.md, sections 5, 5.1 and 7 (S7).
These tests check ownership and wiring, not wording.

Run with:
    python3 -m unittest tests.unit.review.publish.test_review_publish_github_contract
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

SKILL = REPO_ROOT / "skills" / "review-publish-github"
SKILL_MD = SKILL / "SKILL.md"
CORE_MD = REPO_ROOT / "skills" / "review-core" / "SKILL.md"

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
DEFINITION_RE = re.compile(r"\*\*(S\d+)\*\*")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
NON_OWNED = ("S1", "S2", "S3", "S4", "S5", "S6", "S8", "S9", "S10")


def files() -> list:
    return sorted(p for p in SKILL.rglob("*") if p.is_file())


def texts() -> dict[str, str]:
    return {p.relative_to(SKILL).as_posix(): p.read_text(encoding="utf-8") for p in files() if p.suffix == ".md"}


class OwnershipTests(unittest.TestCase):
    def test_s7_is_defined_once_in_skill_md_and_no_other_guarantee_is_defined(self) -> None:
        definitions = {rel: DEFINITION_RE.findall(t) for rel, t in texts().items()}
        self.assertEqual(definitions["SKILL.md"], ["S7"])
        for rel, labels in definitions.items():
            if rel != "SKILL.md":
                self.assertEqual(labels, [], rel)
        for text in texts().values():
            for label in NON_OWNED:
                self.assertNotIn(f"**{label}**", text)


class StructureTests(unittest.TestCase):
    def test_every_file_is_linked_and_links_stay_inside_the_skill(self) -> None:
        linked = {(SKILL / link.split("#", 1)[0]).resolve() for link in LINK_RE.findall(SKILL_MD.read_text(encoding="utf-8"))}
        for path in files():
            if path != SKILL_MD:
                self.assertIn(path.resolve(), linked, path.name)
        for rel, text in texts().items():
            for link in LINK_RE.findall(text):
                if "://" in link or link.startswith("#"):
                    continue
                target = ((SKILL / rel).parent / link.split("#", 1)[0]).resolve()
                with self.subTest(file=rel, link=link):
                    self.assertTrue(target.is_relative_to(SKILL.resolve()))
                    self.assertTrue(target.exists())

    def test_procedure_is_inline_and_numbered_and_there_is_no_loading_inventory(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        steps = [int(n) for n in re.findall(r"^(\d+)\. ", text.split("## Procedure", 1)[1], re.M)]
        self.assertEqual(steps, list(range(1, len(steps) + 1)))
        self.assertIsNone(re.search(r"^## 2\.", text, re.M))
        self.assertFalse((SKILL / "runbooks").exists())

    def test_frontmatter_matches_the_name_the_core_lists(self) -> None:
        fields = dict(line.split(": ", 1) for line in FRONTMATTER_RE.match(SKILL_MD.read_text(encoding="utf-8")).group(1).splitlines())
        self.assertEqual(fields["name"], "review-publish-github")
        self.assertLessEqual(len(fields["description"]), 300)
        self.assertIn("| `review-publish-github` |", CORE_MD.read_text(encoding="utf-8"))

    def test_it_does_not_reach_into_another_skill_folder(self) -> None:
        for rel, text in texts().items():
            self.assertNotIn("skills/review-core", text, rel)
            self.assertNotIn("../review-core", text, rel)


class BoundaryTests(unittest.TestCase):
    def test_removed_v2_machinery_is_not_reintroduced(self) -> None:
        body = "\n".join(texts().values()).lower()
        for term in ("semi", "required check", "review status", "delta re-review", "reviewer brief"):
            self.assertNotIn(term, body)

    def test_authority_file_states_the_comment_only_and_fail_closed_rules(self) -> None:
        text = texts()["rules/authority.md"]
        self.assertIn("Self-review, any decision | `COMMENT`", text)
        self.assertIn("## Fails closed", text)

    def test_it_is_not_packaged_before_the_cutover(self) -> None:
        for path in sorted((REPO_ROOT / "scripts" / "packaging").rglob("*.py")):
            self.assertNotIn("review-publish-github", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
