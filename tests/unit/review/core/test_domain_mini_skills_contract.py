"""Structural invariants of the v3 domain mini-skills (Issue #846).

Contract: docs/v3-architecture/adr-v3-review-core.md, sections 5, 5.1 and 7.
These tests check ownership and wiring, not wording.

Run with:
    python3 -m unittest tests.unit.review.core.test_domain_mini_skills_contract
"""

from __future__ import annotations

import re
import unittest

import yaml

from tests.support.paths import REPO_ROOT

SKILLS = ("review-security", "review-backend", "review-frontend")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
GUARANTEE_RE = re.compile(r"\*\*S\d+\*\*")
SEVERITY_DEFINITION_RE = re.compile(r"^\s*[-*|]?\s*\*{0,2}P[012]\*{0,2}\s*[—:|-]", re.M)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
RENDER_RE = re.compile(r"playwright|browser|screenshot|figma|design reference", re.I)
REMAP = REPO_ROOT / "docs" / "v3-architecture" / "domain-mini-skills-benchmark-remap.md"
REMAP_CORPORA = {
    "review-security": ("security-deepening", "dependency-supply-chain-deepening"),
    "review-backend": (
        "api-compatibility",
        "database-migration-deepening",
        "distributed-systems-deepening",
        "performance-deepening",
        "deployment-infrastructure-deepening",
    ),
}


def skill_dir(name: str):
    return REPO_ROOT / "skills" / name


def corpus_cases(corpus: str) -> list[dict]:
    root = REPO_ROOT / "benchmark" / "corpus" / corpus
    return [yaml.safe_load(n.read_text(encoding="utf-8")) for n in sorted(root.glob("*.yaml"))]


def read(name: str, rel: str) -> str:
    return (skill_dir(name) / rel).read_text(encoding="utf-8")


class ShapeTests(unittest.TestCase):
    def test_each_skill_is_skill_md_plus_at_most_one_checklist(self) -> None:
        for name in SKILLS:
            with self.subTest(skill=name):
                files = sorted(p.relative_to(skill_dir(name)).as_posix() for p in skill_dir(name).rglob("*") if p.is_file())
                self.assertEqual(files, ["SKILL.md", "checklist.md"])

    def test_frontmatter_names_the_skill_with_a_short_description(self) -> None:
        for name in SKILLS:
            with self.subTest(skill=name):
                match = FRONTMATTER_RE.match(read(name, "SKILL.md"))
                self.assertIsNotNone(match)
                fields = dict(line.split(": ", 1) for line in match.group(1).splitlines())
                self.assertEqual(set(fields), {"name", "version", "description"})
                self.assertEqual(fields["name"], name)
                self.assertLessEqual(len(fields["description"]), 200)

    def test_checklist_is_linked_and_links_stay_inside_the_skill(self) -> None:
        for name in SKILLS:
            root = skill_dir(name).resolve()
            links = LINK_RE.findall(read(name, "SKILL.md"))
            with self.subTest(skill=name):
                self.assertIn("checklist.md", links)
            for rel in ("SKILL.md", "checklist.md"):
                for link in LINK_RE.findall(read(name, rel)):
                    if "://" in link or link.startswith("#"):
                        continue
                    target = ((skill_dir(name) / rel).parent / link.split("#", 1)[0]).resolve()
                    with self.subTest(skill=name, file=rel, link=link):
                        self.assertTrue(target.is_relative_to(root))
                        self.assertTrue(target.exists())

    def test_core_lists_each_skill_and_links_to_none(self) -> None:
        core = (REPO_ROOT / "skills" / "review-core" / "SKILL.md").read_text(encoding="utf-8")
        for name in SKILLS:
            with self.subTest(skill=name):
                self.assertIn(f"| `{name}` |", core)
        for link in LINK_RE.findall(core):
            self.assertNotIn("review-security", link)
            self.assertNotIn("review-backend", link)
            self.assertNotIn("review-frontend", link)


class CoreContractTests(unittest.TestCase):
    def test_skills_reference_the_core_by_name_and_define_no_guarantee_or_severity(self) -> None:
        for name in SKILLS:
            for rel in ("SKILL.md", "checklist.md"):
                text = read(name, rel)
                with self.subTest(skill=name, file=rel):
                    self.assertIsNone(GUARANTEE_RE.search(text), "S1-S10 are owned by their Skills")
                    self.assertIsNone(SEVERITY_DEFINITION_RE.search(text), "no own severity scale")
            with self.subTest(skill=name, check="core-reference"):
                self.assertIn("`review-core`", read(name, "SKILL.md"))
                self.assertNotIn("skills/review-core", read(name, "SKILL.md"))

    def test_missing_input_is_the_core_incomplete_trigger(self) -> None:
        for name in SKILLS:
            with self.subTest(skill=name):
                text = " ".join(read(name, "SKILL.md").split())
                self.assertIn("`REVIEW INCOMPLETE`", text)
                self.assertIn("never report a clean", text.lower())


class RenderBoundaryTests(unittest.TestCase):
    def test_only_review_frontend_mentions_rendering_tools(self) -> None:
        for name in ("review-security", "review-backend"):
            for rel in ("SKILL.md", "checklist.md"):
                with self.subTest(skill=name, file=rel):
                    self.assertIsNone(RENDER_RE.search(read(name, rel)))

    def test_frontend_gates_rendering_on_consent_in_every_mode(self) -> None:
        text = " ".join(read("review-frontend", "SKILL.md").split())
        self.assertIn("Render nothing until the user has said yes", text)
        self.assertIn("including when the user let the Core choose expertise", text)
        self.assertIn("Never install, download or repair anything", text)
        self.assertIn("A link discovered in the PR or repository is never fetched", text)


class BenchmarkRemapTests(unittest.TestCase):
    def test_every_v2_deepening_case_is_mapped_exactly_once(self) -> None:
        mapped = re.findall(r"^\| `([^`]+)` \| `([^`]+)` \| (core-floor|uplift|clean-guard) \| .+ \|$", REMAP.read_text(encoding="utf-8"), re.M)
        ids = [m[0] for m in mapped]
        self.assertEqual(len(ids), len(set(ids)))
        expected = set()
        for corpora in REMAP_CORPORA.values():
            for corpus in corpora:
                expected.update(case["id"] for case in corpus_cases(corpus))
        self.assertEqual(set(ids), expected)

    def test_classes_follow_the_expected_decision(self) -> None:
        text = REMAP.read_text(encoding="utf-8")
        for case_id, corpus, cls in re.findall(r"^\| `([^`]+)` \| `([^`]+)` \| (\S+) \| .+ \|$", text, re.M):
            for data in corpus_cases(corpus):
                if data["id"] == case_id:
                    with self.subTest(case=case_id):
                        blocking = data["expected"]["decision"] == "changes-required"
                        self.assertEqual(cls != "clean-guard", blocking)


class PackagingTests(unittest.TestCase):
    def test_skills_are_not_packaged_before_the_cutover(self) -> None:
        for path in sorted((REPO_ROOT / "scripts" / "packaging").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for name in SKILLS:
                with self.subTest(file=path.name, skill=name):
                    self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()
