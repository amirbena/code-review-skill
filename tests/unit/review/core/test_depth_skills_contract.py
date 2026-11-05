"""Structural invariants of the v3 depth mini-skills (Issue #845).

Contract: docs/v3-architecture/adr-v3-review-core.md, sections 5, 5.1 and 7.
These tests check ownership and wiring, not wording.

Run with:
    python3 -m unittest tests.unit.review.core.test_depth_skills_contract
"""

from __future__ import annotations

import json
import re
import unittest

from tests.support.paths import REPO_ROOT

SKILLS = REPO_ROOT / "skills"
CORE = SKILLS / "review-core"
DEPTH = ("review-requirements", "review-deep-investigation", "review-suggestions")
RULE_FILE = {
    "review-requirements": "rules/requirements.md",
    "review-deep-investigation": "rules/investigation.md",
}

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
DEFINITION_RE = re.compile(r"\*\*(S\d+)\*\*")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)
SEVERITY_RE = re.compile(r"\bP[012]\b")


def skill_dir(name: str):
    return SKILLS / name


def md_files(name: str) -> dict[str, str]:
    root = skill_dir(name)
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in sorted(root.rglob("*")) if p.is_file()}


def skill_md(name: str) -> str:
    return (skill_dir(name) / "SKILL.md").read_text(encoding="utf-8")


class StructureTests(unittest.TestCase):
    def test_each_skill_is_skill_md_plus_at_most_one_rule_file(self) -> None:
        for name in DEPTH:
            with self.subTest(skill=name):
                files = set(md_files(name))
                expected = {"SKILL.md"} | ({RULE_FILE[name]} if name in RULE_FILE else set())
                self.assertEqual(files, expected)

    def test_every_rule_file_is_linked_and_links_stay_inside_the_skill(self) -> None:
        for name in DEPTH:
            root = skill_dir(name).resolve()
            for rel, text in md_files(name).items():
                base = (root / rel).parent
                for link in LINK_RE.findall(text):
                    if "://" in link or link.startswith("#"):
                        continue
                    target = (base / link.split("#", 1)[0]).resolve()
                    with self.subTest(skill=name, file=rel, link=link):
                        self.assertTrue(target.is_relative_to(root), "no link into another Skill")
                        self.assertTrue(target.exists())
            if name in RULE_FILE:
                linked = {(root / link).resolve() for link in LINK_RE.findall(skill_md(name))}
                with self.subTest(skill=name):
                    self.assertIn((root / RULE_FILE[name]).resolve(), linked)

    def test_no_runbook_loading_inventory_or_version_line(self) -> None:
        for name in DEPTH:
            text = skill_md(name)
            with self.subTest(skill=name):
                self.assertFalse((skill_dir(name) / "runbooks").exists())
                self.assertIsNone(re.search(r"^## 2\.", text, re.M))
                self.assertIsNone(re.search(r"^version:", text, re.M))

    def test_procedure_is_inline_and_numbered(self) -> None:
        for name in DEPTH:
            parts = skill_md(name).split("## Procedure", 1)
            with self.subTest(skill=name):
                self.assertEqual(len(parts), 2)
                steps = [int(n) for n in re.findall(r"^(\d+)\. ", parts[1], re.M)]
                self.assertEqual(steps, list(range(1, len(steps) + 1)))
                self.assertGreater(len(steps), 1)


class SelectionSurfaceTests(unittest.TestCase):
    def test_frontmatter_names_the_skill_with_a_short_description(self) -> None:
        for name in DEPTH:
            match = FRONTMATTER_RE.match(skill_md(name))
            with self.subTest(skill=name):
                self.assertIsNotNone(match)
                fields = dict(line.split(": ", 1) for line in match.group(1).splitlines())
                self.assertEqual(set(fields), {"name", "description"})
                self.assertEqual(fields["name"], name)
                self.assertLessEqual(len(fields["description"]), 200)

    def test_core_lists_every_depth_skill_and_the_result_can_name_it(self) -> None:
        core = (CORE / "SKILL.md").read_text(encoding="utf-8")
        schema = json.loads((CORE / "templates" / "result.schema.json").read_text(encoding="utf-8"))
        enum = schema["properties"]["mini_skills"]["items"]["properties"]["name"]["enum"]
        for name in DEPTH:
            with self.subTest(skill=name):
                self.assertIn(f"| `{name}` |", core)
                self.assertIn(name, enum)


class CoreContractTests(unittest.TestCase):
    def test_each_skill_runs_after_the_core_and_references_it_by_name(self) -> None:
        for name in DEPTH:
            text = skill_md(name)
            with self.subTest(skill=name):
                self.assertIn("`review-core`", text)
                self.assertIn("after `review-core` has run", text)

    def test_s6_selection_is_referenced_not_redefined(self) -> None:
        for name in DEPTH:
            for rel, text in md_files(name).items():
                with self.subTest(skill=name, file=rel):
                    self.assertNotIn("S6", DEFINITION_RE.findall(text))
        for name in DEPTH:
            with self.subTest(skill=name, check="references S6"):
                self.assertIn("S6", skill_md(name))

    def test_only_review_requirements_defines_s9_and_no_skill_defines_core_guarantees(self) -> None:
        owned = {"review-requirements": ["S9"], "review-deep-investigation": [], "review-suggestions": []}
        for name in DEPTH:
            defined = [label for text in md_files(name).values() for label in DEFINITION_RE.findall(text)]
            with self.subTest(skill=name):
                self.assertEqual(defined, owned[name])

    def test_no_skill_redefines_severity_decision_or_incomplete_triggers(self) -> None:
        for name in DEPTH:
            for rel, text in md_files(name).items():
                with self.subTest(skill=name, file=rel):
                    self.assertNotIn("REVIEW CLEAN", text)
                    self.assertNotIn("CHANGES REQUIRED", text)
                    self.assertIsNone(re.search(r"^- \*\*P[012]\*\* —", text, re.M))


class SuggestionsTests(unittest.TestCase):
    def test_suggestions_emit_p2_only_and_cannot_change_the_decision(self) -> None:
        text = skill_md("review-suggestions")
        self.assertIn("severity **P2**", text)
        self.assertIn("Never emit P0 or P1", text)
        # No instruction to raise P0/P1 anywhere except the prohibition itself.
        for line in text.splitlines():
            if re.search(r"\bP[01]\b", line):
                self.assertRegex(line, r"(?i)never|can never|counts P0 and P1|do not raise")

    def test_suggestions_preserve_an_existing_verdict(self) -> None:
        text = skill_md("review-suggestions")
        self.assertIn("never lowers, removes or\nre-rates an existing P0 or P1", text)
        self.assertIn("never clears a `REVIEW INCOMPLETE` trigger", text)
        findings = (CORE / "rules" / "findings.md").read_text(encoding="utf-8")
        # The Core rule it relies on: P2 is outside the blocking count and never overrides a trigger.
        self.assertIn("P2 findings never\n  block", findings)

    def test_suggestions_are_capped(self) -> None:
        self.assertIn("at most five", skill_md("review-suggestions"))


class RequirementsTests(unittest.TestCase):
    def test_all_four_statuses_are_defined(self) -> None:
        rules = md_files("review-requirements")["rules/requirements.md"]
        for status in ("met", "partially met", "not met", "not verifiable"):
            with self.subTest(status=status):
                self.assertIn(f"**{status}**", rules)

    def test_runs_only_with_a_user_supplied_reference_in_every_mode(self) -> None:
        text = skill_md("review-requirements")
        self.assertIn("supplied in this conversation for\n  this run", text)
        self.assertIn("in every mode", text)

    def test_unresolved_reference_stops_the_run_via_core_trigger_4(self) -> None:
        text = skill_md("review-requirements")
        self.assertIn("mini-skill-input-missing", text)
        self.assertIn("Never infer", text)
        schema = json.loads((CORE / "templates" / "result.schema.json").read_text(encoding="utf-8"))
        self.assertIn("mini-skill-input-missing", schema["properties"]["incomplete"]["items"]["enum"])

    def test_jira_and_issue_access_is_read_only(self) -> None:
        text = skill_md("review-requirements")
        self.assertIn("read-only", text)
        self.assertIn("gh api", text)
        self.assertNotRegex(text, r"gh issue (comment|edit|close)")


class InvestigationTests(unittest.TestCase):
    def test_tracing_uses_only_git_and_grep(self) -> None:
        text = skill_md("review-deep-investigation")
        self.assertIn("git log -S", text)
        self.assertIn("no graph, index, AST or cache", text)
        rules = md_files("review-deep-investigation")["rules/investigation.md"]
        self.assertIn("git grep", rules)

    def test_it_stops_on_confirm_or_dismiss_and_reports_what_it_traced(self) -> None:
        rules = md_files("review-deep-investigation")["rules/investigation.md"]
        self.assertIn("confirms or\ndismisses", rules)
        self.assertIn("### Investigation", rules)

    def test_it_covers_the_four_depth_topics(self) -> None:
        rules = md_files("review-deep-investigation")["rules/investigation.md"]
        for topic in ("Multi-hop tracing", "Root cause and model completeness", "Affected tests", "Failure and retry", "Null and absence"):
            with self.subTest(topic=topic):
                self.assertIn(topic, rules)


class PackagingTests(unittest.TestCase):
    def test_depth_skills_are_not_packaged_before_the_cutover(self) -> None:
        for path in sorted((REPO_ROOT / "scripts" / "packaging").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for name in DEPTH:
                with self.subTest(file=path.relative_to(REPO_ROOT).as_posix(), skill=name):
                    self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()
