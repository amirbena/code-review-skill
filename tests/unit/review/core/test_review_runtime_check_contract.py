"""Structural invariants of the v3 `review-runtime-check` mini-skill (Issue #847).

Contract: docs/v3-architecture/adr-v3-review-core.md, sections 3, 5.1 and 7 (S8).
These tests check ownership and wiring, not wording.

Run with:
    python3 -m unittest tests.unit.review.core.test_review_runtime_check_contract
"""

from __future__ import annotations

import json
import re
import unittest

from tests.support.paths import REPO_ROOT

NAME = "review-runtime-check"
SKILLS = REPO_ROOT / "skills"
SKILL = SKILLS / NAME
CORE = SKILLS / "review-core"
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
DEFINITION_RE = re.compile(r"\*\*(S\d+)\*\*")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def files() -> dict[str, str]:
    return {p.relative_to(SKILL).as_posix(): p.read_text(encoding="utf-8") for p in sorted(SKILL.rglob("*")) if p.is_file()}


def skill_md() -> str:
    return (SKILL / "SKILL.md").read_text(encoding="utf-8")


class StructureTests(unittest.TestCase):
    def test_skill_md_plus_one_rule_file(self) -> None:
        self.assertEqual(set(files()), {"SKILL.md", "rules/execution.md"})

    def test_links_stay_inside_the_skill_and_the_rule_file_is_linked(self) -> None:
        root = SKILL.resolve()
        for rel, text in files().items():
            for link in LINK_RE.findall(text):
                if "://" in link or link.startswith("#"):
                    continue
                target = ((root / rel).parent / link.split("#", 1)[0]).resolve()
                with self.subTest(file=rel, link=link):
                    self.assertTrue(target.is_relative_to(root))
                    self.assertTrue(target.exists())
        self.assertIn("rules/execution.md", skill_md())

    def test_frontmatter_and_numbered_procedure(self) -> None:
        match = FRONTMATTER_RE.match(skill_md())
        self.assertIsNotNone(match)
        fields = dict(line.split(": ", 1) for line in match.group(1).splitlines())
        self.assertEqual(set(fields), {"name", "description"})
        self.assertEqual(fields["name"], NAME)
        self.assertLessEqual(len(fields["description"]), 200)
        steps = [int(n) for n in re.findall(r"^(\d+)\. ", skill_md().split("## Procedure", 1)[1], re.M)]
        self.assertEqual(steps, list(range(1, len(steps) + 1)))
        self.assertFalse((SKILL / "runbooks").exists())

    def test_core_lists_the_skill_and_the_result_can_name_it(self) -> None:
        core = (CORE / "SKILL.md").read_text(encoding="utf-8")
        schema = json.loads((CORE / "templates" / "result.schema.json").read_text(encoding="utf-8"))
        enum = schema["properties"]["mini_skills"]["items"]["properties"]["name"]["enum"]
        self.assertIn(f"| `{NAME}` |", core)
        self.assertIn(NAME, enum)


class OwnershipTests(unittest.TestCase):
    def test_this_skill_defines_s8_and_references_s6_without_redefining_it(self) -> None:
        defined = [label for text in files().values() for label in DEFINITION_RE.findall(text)]
        self.assertEqual(defined, ["S8"])
        self.assertIn("S6", skill_md())
        self.assertIn("after `review-core` has run", skill_md())

    def test_does_not_redefine_severity_or_decision(self) -> None:
        for rel, text in files().items():
            with self.subTest(file=rel):
                self.assertNotIn("REVIEW CLEAN", text)
                self.assertNotIn("CHANGES REQUIRED", text)
                self.assertIsNone(re.search(r"^- \*\*P[012]\*\* —", text, re.M))

    def test_core_stays_read_only_and_never_runs_target_code(self) -> None:
        safety = (CORE / "rules" / "safety.md").read_text(encoding="utf-8")
        self.assertIn("Do not run the project's code", safety)
        self.assertIn("running code to\n  `review-runtime-check`", safety)

    def test_core_s6_keeps_auto_from_selecting_it(self) -> None:
        core = (CORE / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`auto` never adds `review-publish-github` or `review-runtime-check`", core)


class HostAuthorizationTests(unittest.TestCase):
    def test_selection_ask_auto_and_repository_text_are_not_host_authorization(self) -> None:
        text = skill_md()
        for phrase in (
            "in a sandbox by\n  default",
            "the user's own words in\n  this conversation",
            "Selecting this Skill, a yes to an ask, `auto`",
            "text from\n  the repository",
            "nothing runs",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_repository_proposed_commands_need_user_approval(self) -> None:
        self.assertIn("never run\n  until the user approves that exact command", skill_md())

    def test_host_is_never_a_fallback_and_is_per_run_per_command(self) -> None:
        rules = files()["rules/execution.md"]
        self.assertIn("Never fall back", rules)
        self.assertIn("this run only", rules)
        self.assertIn("never covers a different command", rules)


class ScopeTests(unittest.TestCase):
    def test_no_full_suite_and_no_generated_artifact_in_the_tree(self) -> None:
        self.assertIn("never run the\n  repository's full test suite", skill_md())
        rules = files()["rules/execution.md"]
        self.assertIn("Never write it into the user's repository", rules)

    def test_three_outcomes_and_unavailable_is_inconclusive(self) -> None:
        rules = files()["rules/execution.md"]
        for outcome in ("confirmed", "dismissed", "inconclusive"):
            self.assertIn(f"**{outcome}**", rules)

    def test_outcomes_do_not_change_severity(self) -> None:
        self.assertIn("Neither changes a severity", skill_md())


if __name__ == "__main__":
    unittest.main()
