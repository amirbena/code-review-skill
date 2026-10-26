"""Single-source ownership guards for the Skill entry points and runbooks (#810).

`SKILL.md` section 2 is the one loading inventory per Skill; the numbered
runbook Steps are the one execution sequence. Expectations are derived from
those files, never from a second list kept here.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

SKILLS = {
    "local-code-review": ("local-review",),
    "github-pr-review": ("active-pr-review", "passive-pr-review"),
}
_LINK = re.compile(r"\]\(([^)\s#]+\.md)")
_SECTION = re.compile(r"^## 2\.[^\n]*\n(.*?)(?=^## \d+\.)", re.M | re.S)
_STAGES = (
    ("coverage", r"Evaluate review coverage"),
    ("decision", r"Derive the [Dd]ecision"),
    ("verdict-consistency", r"Check verdict consistency"),
)


def _skill_dir(skill: str) -> Path:
    return REPO_ROOT / "skills" / skill


def _resolve(base: Path, link: str) -> Path:
    return (base / link).resolve()


def declared(skill_md: str, skill: str) -> tuple[set[Path], set[Path]]:
    """(unconditional, conditional) files declared by section 2."""
    section = _SECTION.search(skill_md).group(1)
    unconditional: set[Path] = set()
    conditional: set[Path] = set()
    for paragraph in re.split(r"\n\s*\n", section):
        bucket = conditional if paragraph.lstrip().startswith("Conditionally") else unconditional
        bucket.update(_resolve(_skill_dir(skill), link) for link in _LINK.findall(paragraph))
    return unconditional, conditional


def steps_text(skill: str, runbook: str) -> str:
    text = (_skill_dir(skill) / "runbooks" / f"{runbook}.md").read_text(encoding="utf-8")
    return text.split("\n## Steps", 1)[1]


def undeclared(skill: str, runbook: str, skill_md: str, index_text: str = "") -> list[str]:
    """Policies/templates a step applies that section 2 (or the named index) does not declare."""
    unconditional, conditional = declared(skill_md, skill)
    known = unconditional | conditional
    runbook_dir = _skill_dir(skill) / "runbooks"
    missing = []
    for link in sorted(set(_LINK.findall(steps_text(skill, runbook)))):
        target = _resolve(runbook_dir, link)
        rel = target.relative_to(REPO_ROOT).as_posix()
        owned_policy = rel.startswith(("shared/policies/", "shared/templates/", f"skills/{skill}/policies/"))
        if owned_policy and target not in known and target.name not in index_text:
            missing.append(rel)
    return missing


class LoadingInventoryTests(unittest.TestCase):
    def test_every_policy_a_step_applies_is_declared_in_section_2(self) -> None:
        for skill, runbooks in SKILLS.items():
            skill_md = (_skill_dir(skill) / "SKILL.md").read_text(encoding="utf-8")
            index = ""
            if skill == "github-pr-review":
                index = (_skill_dir(skill) / "policies" / "github-review.md").read_text(encoding="utf-8")
            for runbook in runbooks:
                with self.subTest(skill=skill, runbook=runbook):
                    self.assertEqual(undeclared(skill, runbook, skill_md, index), [])

    def test_mutation_dropping_a_conditional_declaration_is_detected(self) -> None:
        skill_md = (_skill_dir("local-code-review") / "SKILL.md").read_text(encoding="utf-8")
        mutated = skill_md.replace("[`code-hygiene.md`](../../shared/policies/code-hygiene.md)", "code-hygiene", 1)
        self.assertNotEqual(mutated, skill_md)
        self.assertIn("shared/policies/code-hygiene.md", undeclared("local-code-review", "local-review", mutated))

    def test_a_policy_is_never_both_unconditional_and_conditional(self) -> None:
        for skill in SKILLS:
            skill_md = (_skill_dir(skill) / "SKILL.md").read_text(encoding="utf-8")
            unconditional, conditional = declared(skill_md, skill)
            with self.subTest(skill=skill):
                self.assertEqual(sorted(p.name for p in unconditional & conditional), [])

    def test_every_conditional_declaration_states_a_fail_closed_rule(self) -> None:
        for skill in SKILLS:
            section = _SECTION.search((_skill_dir(skill) / "SKILL.md").read_text(encoding="utf-8")).group(1)
            for paragraph in re.split(r"\n\s*\n", section):
                if paragraph.lstrip().startswith("Conditionally"):
                    with self.subTest(skill=skill, start=paragraph[:60]):
                        self.assertRegex(paragraph, r"fail-closed|fails? closed|treated as not supplied|only when")

    def test_declared_files_exist(self) -> None:
        for skill in SKILLS:
            skill_md = (_skill_dir(skill) / "SKILL.md").read_text(encoding="utf-8")
            for group in declared(skill_md, skill):
                for path in group:
                    with self.subTest(skill=skill, path=path.name):
                        self.assertTrue(path.is_file())


class SingleSourceStructureTests(unittest.TestCase):
    def test_runbooks_carry_no_flow_diagram_or_policy_header_inventory(self) -> None:
        for skill, runbooks in SKILLS.items():
            for runbook in runbooks:
                text = (_skill_dir(skill) / "runbooks" / f"{runbook}.md").read_text(encoding="utf-8")
                head = text.split("\n## ", 1)[0]
                with self.subTest(runbook=runbook):
                    self.assertNotIn("\n## Flow", text)
                    self.assertNotIn("Applies shared policies", head)
                    self.assertEqual([l for l in _LINK.findall(head) if "shared/policies" in l], [])

    def test_skill_entry_points_carry_no_independent_execution_order(self) -> None:
        for skill in SKILLS:
            text = (_skill_dir(skill) / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertNotIn("## Review flow", text)
                self.assertIn("only authoritative execution sequence", " ".join(text.split()))

    def test_steps_keep_coverage_then_decision_then_verdict_check_in_order(self) -> None:
        for skill, runbooks in SKILLS.items():
            for runbook in runbooks:
                steps = steps_text(skill, runbook)
                offsets = [(name, re.search(pattern, steps)) for name, pattern in _STAGES]
                with self.subTest(runbook=runbook):
                    self.assertTrue(all(m for _, m in offsets), offsets)
                    positions = [m.start() for _, m in offsets]
                    self.assertEqual(positions, sorted(positions))

    def test_checkpoint_precedes_step_1_and_reasoning_check_follows_the_decision(self) -> None:
        for skill, runbooks in SKILLS.items():
            for runbook in runbooks:
                steps = steps_text(skill, runbook)
                decision = re.search(r"Derive the [Dd]ecision", steps).start()
                with self.subTest(runbook=runbook):
                    self.assertLess(steps.index("Mandatory-loading checkpoint"), steps.index("\n1. "))
                    self.assertGreater(steps.index("reasoning-checkpoint.md"), decision)

    def test_active_flow_keeps_prepublish_consistency_check_before_submission(self) -> None:
        steps = steps_text("github-pr-review", "active-pr-review")
        gate = steps.index("Apply the review-action authorization gate")
        recheck = steps.index("Re-check verdict consistency against the literal event")
        submit = steps.index("Submit the one review")
        self.assertLess(gate, recheck)
        self.assertLess(recheck, submit)


if __name__ == "__main__":
    unittest.main()
