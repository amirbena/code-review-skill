"""Single-source ownership guards for the Skill entry points and runbooks (#810).

`SKILL.md` section 2 is the one loading inventory per Skill; the numbered
runbook Steps are the one execution sequence. Expectations are derived from
those files, never from a second list kept here.

Limits: this is structural integrity of the declarations. It does not prove a
reviewer loaded a file, loaded it in full, or loaded it before the decision it
governs (see `test_policy_read_verification.py` for recorded-trace checks), and
it has no ground truth for which non-pipeline policies *should* be mandatory.
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


def _github_index() -> str:
    return (_skill_dir("github-pr-review") / "policies" / "github-review.md").read_text(encoding="utf-8")


def steps_text(skill: str, runbook: str) -> str:
    text = (_skill_dir(skill) / "runbooks" / f"{runbook}.md").read_text(encoding="utf-8")
    return text.split("\n## Steps", 1)[1]


_INDEX_ENTRY = re.compile(r"^([a-z0-9][a-z0-9-]*\.md)[ \t]{2,}(\S.*)$", re.M)
_ENTRY_JOIN = re.compile(r"^\s*(?:and|plus|,)?\s*$")
_PREDICATE_CUE = re.compile(r"\(|\b(?:when|per|only|if|for)\b")
_STEP_START = re.compile(r"\n\d+[a-z]?\. ")


def indexed_policies(skill: str, index_text: str) -> set[Path]:
    """Skill-local sub-policies listed as structured entries of the `github-review.md` index.

    Only the entry list of the first fenced block counts; prose mentions and
    entries marked `(shared)` never do, and identity is the resolved path.
    """
    if skill != "github-pr-review":
        return set()
    block = re.search(r"## Canonical sub-policies[^\n]*\n+```[a-z]*\n(.*?)```", index_text, re.S)
    if block is None:
        return set()
    local = _skill_dir(skill) / "policies"
    return {
        (local / name).resolve()
        for name, description in _INDEX_ENTRY.findall(block.group(1))
        if not description.startswith("(shared)")
    }


def undeclared(
    skill: str, runbook: str, skill_md: str, index_text: str = "", steps: str | None = None
) -> list[str]:
    """Policies/templates a step applies that section 2 (or an indexed local sub-policy) does not declare."""
    unconditional, conditional = declared(skill_md, skill)
    known = unconditional | conditional | indexed_policies(skill, index_text)
    runbook_dir = _skill_dir(skill) / "runbooks"
    missing = []
    for link in sorted(set(_LINK.findall(steps if steps is not None else steps_text(skill, runbook)))):
        target = _resolve(runbook_dir, link)
        rel = target.relative_to(REPO_ROOT).as_posix()
        owned_policy = rel.startswith(("shared/policies/", "shared/templates/", f"skills/{skill}/policies/"))
        if owned_policy and target not in known:
            missing.append(rel)
    return missing


def _step_body(steps: str, pattern: str) -> str:
    start = re.search(pattern, steps).start()
    following = _STEP_START.search(steps, start)
    body = steps[start : following.start() if following else len(steps)]
    # The post-decision reasoning-checkpoint evaluation may sit inside the decision Step; by its own
    # text it follows the Decision and never changes it, so it is not part of the mandatory pipeline.
    return re.split(r"(?i)evaluate\s+the\s+shared", body, maxsplit=1)[0]


def pipeline_misclassified(skill: str, runbook: str, skill_md: str, steps: str | None = None) -> list[str]:
    """Shared policies applied by the coverage, decision, and verdict-check Steps that §2 does not declare
    unconditionally. Those Steps run on every review, so what they apply is mandatory by the Steps' own
    sequence; demoting one to a conditional entry would let a verdict render without it."""
    steps = steps if steps is not None else steps_text(skill, runbook)
    unconditional, _ = declared(skill_md, skill)
    runbook_dir = _skill_dir(skill) / "runbooks"
    gaps = set()
    for _, pattern in _STAGES:
        for link in _LINK.findall(_step_body(steps, pattern)):
            target = _resolve(runbook_dir, link)
            if target.relative_to(REPO_ROOT).as_posix().startswith("shared/policies/") and target not in unconditional:
                gaps.add(target.relative_to(REPO_ROOT).as_posix())
    return sorted(gaps)


def predicate_gaps(skill_md: str) -> list[str]:
    """Conditional entries (links joined by and/plus) with no activation predicate of their own."""
    section = _SECTION.search(skill_md).group(1)
    gaps = []
    for paragraph in re.split(r"\n\s*\n", section):
        if not paragraph.lstrip().startswith("Conditionally"):
            continue
        for segment in paragraph.split(";"):
            links = list(re.finditer(r"\[[^\]]*\]\([^)\s]+\.md[^)]*\)", segment))
            groups: list[list[re.Match]] = []
            for match in links:
                if groups and _ENTRY_JOIN.match(segment[groups[-1][-1].end() : match.start()]):
                    groups[-1].append(match)
                else:
                    groups.append([match])
            for index, group in enumerate(groups):
                end = groups[index + 1][0].start() if index + 1 < len(groups) else len(segment)
                if not _PREDICATE_CUE.search(segment[group[-1].end() : end]):
                    gaps.append(group[0].group(0))
    return gaps


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

    def test_github_index_exception_is_exercised_and_limited_to_local_entries(self) -> None:
        skill = "github-pr-review"
        skill_md = (_skill_dir(skill) / "SKILL.md").read_text(encoding="utf-8")
        index = _github_index()
        indexed = indexed_policies(skill, index)
        local_dir = (_skill_dir(skill) / "policies").resolve()
        self.assertTrue(indexed)
        for path in indexed:
            with self.subTest(path=path.name):
                self.assertEqual(path.parent, local_dir)
                self.assertTrue(path.is_file())
        # Without the index the local sub-policies are undeclared, so the exception is really used.
        self.assertTrue(undeclared(skill, "active-pr-review", skill_md, ""))
        self.assertEqual(undeclared(skill, "active-pr-review", skill_md, index), [])

    def test_mandatory_pipeline_policies_are_declared_unconditionally(self) -> None:
        for skill, runbooks in SKILLS.items():
            skill_md = (_skill_dir(skill) / "SKILL.md").read_text(encoding="utf-8")
            for runbook in runbooks:
                with self.subTest(skill=skill, runbook=runbook):
                    self.assertEqual(pipeline_misclassified(skill, runbook, skill_md), [])
                    applied = {
                        Path(link).name
                        for _, pattern in _STAGES
                        for link in _LINK.findall(_step_body(steps_text(skill, runbook), pattern))
                        if "shared/policies" in link
                    }
                    self.assertTrue({"severity.md", "review-stopping-criteria.md"} <= applied)

    def test_every_conditional_entry_states_its_own_activation_predicate(self) -> None:
        for skill in SKILLS:
            skill_md = (_skill_dir(skill) / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertEqual(predicate_gaps(skill_md), [])

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


class DetectorMutationTests(unittest.TestCase):
    """Each mutation edits an in-memory copy and must be reported (#810 audit false negatives)."""

    @staticmethod
    def _md(skill: str) -> str:
        return (_skill_dir(skill) / "SKILL.md").read_text(encoding="utf-8")

    @staticmethod
    def _in_section_2(skill_md: str, edit) -> str:
        span = _SECTION.search(skill_md).span(1)
        return skill_md[: span[0]] + edit(skill_md[span[0] : span[1]]) + skill_md[span[1] :]

    def _unlink(self, skill: str, name: str) -> str:
        pattern = re.compile(r"\[`?([^\]]*?)`?\]\([^)\s]*" + re.escape(name) + r"\)")
        mutated = self._in_section_2(self._md(skill), lambda s: pattern.sub(r"\1", s))
        self.assertNotEqual(mutated, self._md(skill), name)
        return mutated

    def test_github_mandatory_severity_declaration_removed(self) -> None:
        mutated = self._unlink("github-pr-review", "shared/policies/severity.md")
        for runbook in SKILLS["github-pr-review"]:
            self.assertIn("shared/policies/severity.md", undeclared("github-pr-review", runbook, mutated, _github_index()))

    def test_shared_policy_whose_basename_is_also_a_github_index_entry(self) -> None:
        # parallel-review.md and structured-output.md exist as shared and as indexed local policies.
        mutated = self._unlink("github-pr-review", "shared/policies/parallel-review.md")
        found = undeclared("github-pr-review", "active-pr-review", mutated, _github_index())
        self.assertIn("shared/policies/parallel-review.md", found)
        steps = steps_text("github-pr-review", "active-pr-review") + "\n[x](../../../shared/policies/structured-output.md)\n"
        mutated = self._unlink("github-pr-review", "shared/policies/structured-output.md")
        found = undeclared("github-pr-review", "active-pr-review", mutated, _github_index(), steps=steps)
        self.assertIn("shared/policies/structured-output.md", found)

    def test_incidental_filename_mention_in_index_prose_is_not_a_declaration(self) -> None:
        skill_md = self._md("github-pr-review")
        steps = steps_text("github-pr-review", "active-pr-review") + "\n[x](../../../shared/policies/null-absence-risk.md)\n"
        prose = _github_index() + "\nUnrelated prose that names null-absence-risk.md in passing.\n"
        self.assertEqual(undeclared("github-pr-review", "active-pr-review", skill_md, prose, steps=steps), ["shared/policies/null-absence-risk.md"])

    def test_removed_index_entry_no_longer_excuses_a_local_policy(self) -> None:
        index = re.sub(r"(?m)^review-output\.md .*\n", "", _github_index(), count=1)
        self.assertNotEqual(index, _github_index())
        found = undeclared("github-pr-review", "active-pr-review", self._md("github-pr-review"), index)
        self.assertIn("skills/github-pr-review/policies/review-output.md", found)

    def test_shared_entry_in_the_index_never_establishes_a_declaration(self) -> None:
        self.assertNotIn("review-base-policy.md", {p.name for p in indexed_policies("github-pr-review", _github_index())})

    def test_mandatory_policy_demoted_to_conditional(self) -> None:
        for skill, runbook in (("local-code-review", "local-review"), ("github-pr-review", "active-pr-review")):
            link = "[`severity.md`](../../shared/policies/severity.md)"

            def demote(section: str) -> str:
                section = section.replace(link + ", ", "", 1)
                return section.replace("Conditionally,", "Conditionally, " + link + " (demoted) —", 1)

            mutated = self._in_section_2(self._md(skill), demote)
            self.assertNotEqual(mutated, self._md(skill))
            with self.subTest(skill=skill):
                self.assertEqual(undeclared(skill, runbook, mutated, _github_index()), [])  # still "declared"
                self.assertEqual(pipeline_misclassified(skill, runbook, mutated), ["shared/policies/severity.md"])

    def test_single_conditional_activation_predicate_removed(self) -> None:
        for skill in SKILLS:
            skill_md = self._md(skill)
            predicate = "(at least one material finding exists — it then applies to every one)"
            self.assertIn(predicate, skill_md)
            mutated = skill_md.replace(" " + predicate, "", 1)
            with self.subTest(skill=skill):
                self.assertEqual(len(predicate_gaps(mutated)), 1)
                self.assertIn("remediation-scope-boundary.md", predicate_gaps(mutated)[0])

    def test_nonexistent_policy_reference_in_a_step(self) -> None:
        steps = steps_text("local-code-review", "local-review") + "\n[x](../../../shared/policies/ghost-policy.md)\n"
        self.assertEqual(
            undeclared("local-code-review", "local-review", self._md("local-code-review"), steps=steps),
            ["shared/policies/ghost-policy.md"],
        )

    def test_new_undeclared_policy_reference_in_a_step(self) -> None:
        for skill, runbook in (("local-code-review", "local-review"), ("github-pr-review", "passive-pr-review")):
            steps = steps_text(skill, runbook) + "\n[x](../../../shared/policies/null-absence-risk.md)\n"
            with self.subTest(skill=skill):
                self.assertEqual(
                    undeclared(skill, runbook, self._md(skill), _github_index(), steps=steps),
                    ["shared/policies/null-absence-risk.md"],
                )


if __name__ == "__main__":
    unittest.main()
