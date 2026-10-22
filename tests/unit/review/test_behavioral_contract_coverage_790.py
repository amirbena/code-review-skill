"""Behavioral regression coverage for review contracts (Issue #790).

Complements the rendered-sample checks added for #784. Each contract below is
exercised over shipped text (Skill ``SKILL.md`` files and the per-mode report
samples) and every guard is proven sensitive: the same check is rerun against a
mutated input and must report the mutation.

* Policy-loading checkpoint: the unconditional set parsed from each
  ``SKILL.md`` section 2 must resolve to packaged files, exclude
  context-conditional members, and an unopened member must yield
  ``REVIEW INCOMPLETE``.
* Finding evidence: every rendered finding keeps Location, Evidence, Impact
  and Fix with non-empty content.
* Result/Decision agreement under complete coverage.
"""

from __future__ import annotations

import re
import unittest

from tests.reference.review.change_risk_signals import Depth
from tests.reference.review.review_stopping_criteria import (
    PassResult,
    decision_label,
    evaluate_coverage,
)
from tests.support.paths import REPO_ROOT
from tests.unit.review.observability.test_incomplete_verdict_rendering_784 import (
    CANONICAL,
    _DECISION,
    _RESULT,
    shipped_samples,
    with_decision,
    with_result,
)

SKILLS = ("local-code-review", "github-pr-review")
_CONTEXT = re.compile(r"(?:In\s+orchestrated/\s*multi-Agent\s+contexts,|with\s+parallel\s+workers\s+—)", re.I)
_LINK = re.compile(r"\]\(([^)\s]+\.md)\)")

# What a verdict cannot be derived without; the checkpoint must never drop these.
VERDICT_CRITICAL = {"severity.md", "evidence.md", "review-stopping-criteria.md"}


def skill_text(skill: str) -> str:
    return (REPO_ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")


def loading_section(text: str) -> str:
    """Section 2 up to its first conditional paragraph: the unconditional span."""
    body = text.split("## 2. Required Policy Loading", 1)[1]
    return re.split(r"\n\s*\nConditionally", body, maxsplit=1)[0]


def unconditional_files(text: str, context_holds: bool = False) -> tuple[list[str], list[str]]:
    """(always-required links, context-conditional links) from section 2.

    A context-conditional member is the run of links after a context phrase up
    to the end of that paragraph; it joins the required set only when the
    context holds for the review.
    """
    span = loading_section(text)
    always: list[str] = []
    contextual: list[str] = []
    for paragraph in re.split(r"\n\s*\n", span):
        match = _CONTEXT.search(paragraph)
        if match:
            always += _LINK.findall(paragraph[: match.start()])
            contextual += _LINK.findall(paragraph[match.end() :])
        else:
            always += _LINK.findall(paragraph)
    return always, (contextual if context_holds else [])


def required_set(skill: str, text: str | None = None, context_holds: bool = False) -> set[str]:
    always, contextual = unconditional_files(text if text is not None else skill_text(skill), context_holds)
    return set(always) | set(contextual)


def unresolvable(skill: str, links: set[str]) -> list[str]:
    base = REPO_ROOT / "skills" / skill
    return sorted(link for link in links if not (base / link).resolve().is_file())


def checkpoint_label(required: set[str], opened: set[str], mechanical: str) -> str:
    """Apply the Mandatory-loading checkpoint through the coverage reference:
    each required file is a pass that reaches its stop condition only if opened."""
    passes = tuple(PassResult(f"{name} loaded", name in opened) for name in sorted(required))
    return decision_label(evaluate_coverage(Depth.STANDARD, passes=passes), mechanical)


class PolicyLoadingCheckpointTests(unittest.TestCase):
    def test_every_unconditional_file_resolves_to_a_packaged_file(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill=skill):
                required = required_set(skill, context_holds=True)
                self.assertGreater(len(required), 10)
                self.assertEqual(unresolvable(skill, required), [])

    def test_mutation_retargeted_link_is_reported_unresolvable(self) -> None:
        for skill in SKILLS:
            with self.subTest(skill=skill):
                text = skill_text(skill).replace("shared/policies/evidence.md", "shared/policies/evidence-gone.md", 1)
                self.assertEqual(
                    unresolvable(skill, required_set(skill, text)),
                    ["../../shared/policies/evidence-gone.md"],
                )

    def test_verdict_critical_policies_are_always_required(self) -> None:
        for skill in SKILLS:
            names = {link.rsplit("/", 1)[-1] for link in required_set(skill)}
            with self.subTest(skill=skill):
                self.assertTrue(VERDICT_CRITICAL <= names, VERDICT_CRITICAL - names)

    def test_mutation_dropping_a_critical_policy_is_detected(self) -> None:
        for skill in SKILLS:
            original = skill_text(skill)
            span = loading_section(original)
            text = original.replace(span, re.sub(r"\[`severity\.md`\]\([^)]*\),?\n?", "", span, count=1), 1)
            self.assertNotEqual(text, original)
            names = {link.rsplit("/", 1)[-1] for link in required_set(skill, text)}
            with self.subTest(skill=skill):
                self.assertNotIn("severity.md", names)
                self.assertFalse(VERDICT_CRITICAL <= names)

    def test_context_conditional_members_join_only_when_the_context_holds(self) -> None:
        expected = {
            "local-code-review": {"review-ownership.md"},
            "github-pr-review": {"parallel-review.md", "agent-delegation.md"},
        }
        for skill, members in expected.items():
            with self.subTest(skill=skill):
                without = {link.rsplit("/", 1)[-1] for link in required_set(skill)}
                with_ctx = {link.rsplit("/", 1)[-1] for link in required_set(skill, context_holds=True)}
                self.assertEqual(with_ctx - without, members)

    def test_an_unopened_required_file_is_incomplete_never_clean(self) -> None:
        for skill in SKILLS:
            required = required_set(skill)
            for mechanical in ("REVIEW CLEAN", "CHANGES REQUIRED"):
                self.assertEqual(checkpoint_label(required, required, mechanical), mechanical)
                for missing in sorted(required):
                    with self.subTest(skill=skill, missing=missing, mechanical=mechanical):
                        self.assertEqual(
                            checkpoint_label(required, required - {missing}, mechanical),
                            "REVIEW INCOMPLETE",
                        )

    def test_an_unfired_context_member_is_never_required(self) -> None:
        for skill in SKILLS:
            required = required_set(skill)
            extra = required_set(skill, context_holds=True) - required
            self.assertTrue(extra)
            # Opening exactly the unconditional set is enough when the context does not hold.
            self.assertEqual(checkpoint_label(required, required, "REVIEW CLEAN"), "REVIEW CLEAN")
            # Mutation: promoting the member to required makes the same session incomplete.
            self.assertEqual(
                checkpoint_label(required | extra, required, "REVIEW CLEAN"), "REVIEW INCOMPLETE"
            )

    def test_each_clean_sample_skill_checkpoint_gates_its_clean_outcome(self) -> None:
        # A shipped clean sample is only valid when nothing required was left unopened.
        clean = [p for p in shipped_samples() if _label(p.read_text(encoding="utf-8")) == "REVIEW CLEAN"]
        self.assertTrue(clean)
        for path in clean:
            skill = path.parent.name
            required = required_set(skill)
            with self.subTest(sample=path.name):
                self.assertEqual(checkpoint_label(required, required, "REVIEW CLEAN"), "REVIEW CLEAN")
                self.assertEqual(
                    checkpoint_label(required, required - {sorted(required)[0]}, "REVIEW CLEAN"),
                    "REVIEW INCOMPLETE",
                )


def _label(text: str) -> str:
    raw = _DECISION.search(text).group(1)
    return CANONICAL.get(raw, raw)


_FINDING = re.compile(r"^#### (F\d+) \[(P[012])\][^\n]*\n(.*?)(?=^#{1,4} |\Z)", re.M | re.S)
MANDATORY_LABELS = ("Location", "Evidence", "Impact", "Fix")


def finding_gaps(text: str) -> list[str]:
    """Findings (by id) missing a mandatory field or carrying an empty one."""
    gaps: list[str] = []
    for fid, _severity, body in _FINDING.findall(text):
        for label in MANDATORY_LABELS:
            line = re.search(rf"^- \*\*{label}:\*\*[ \t]*(.*)$", body, re.M)
            if not line or not line.group(1).strip():
                gaps.append(f"{fid} {label}")
    return gaps


def drop_field(text: str, label: str, fid: str) -> str:
    pattern = re.compile(
        rf"(^#### {fid} \[P[012]\].*?)^- \*\*{label}:\*\*[^\n]*\n", re.M | re.S
    )
    return pattern.sub(lambda m: m.group(1), text, count=1)


def blank_field(text: str, label: str, fid: str) -> str:
    pattern = re.compile(
        rf"(^#### {fid} \[P[012]\].*?^- \*\*{label}:\*\*)[^\n]*\n", re.M | re.S
    )
    return pattern.sub(lambda m: m.group(1) + " \n", text, count=1)


class FindingEvidenceTests(unittest.TestCase):
    def test_every_shipped_finding_keeps_its_mandatory_fields(self) -> None:
        seen = 0
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            seen += len(_FINDING.findall(text))
            with self.subTest(sample=path.relative_to(path.parents[1]).as_posix()):
                self.assertEqual(finding_gaps(text), [])
        self.assertGreaterEqual(seen, 4)

    def test_mutation_dropping_a_field_is_reported_for_every_finding(self) -> None:
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            for fid, _severity, _body in _FINDING.findall(text):
                for label in MANDATORY_LABELS:
                    with self.subTest(sample=path.name, finding=fid, dropped=label):
                        mutated = drop_field(text, label, fid)
                        self.assertNotEqual(mutated, text)
                        self.assertIn(f"{fid} {label}", finding_gaps(mutated))

    def test_mutation_blanking_a_field_is_reported(self) -> None:
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            for fid, _severity, _body in _FINDING.findall(text):
                with self.subTest(sample=path.name, finding=fid):
                    mutated = blank_field(text, "Evidence", fid)
                    self.assertNotEqual(mutated, text)
                    self.assertEqual(finding_gaps(mutated), [f"{fid} Evidence"])


def result_outcome(text: str) -> str:
    line = _RESULT.search(text).group(0).lower()
    if "incomplete" in line:
        return "REVIEW INCOMPLETE"
    if "changes requested" in line or "changes required" in line or "request" in line:
        return "CHANGES REQUIRED"
    if "clean" in line:
        return "REVIEW CLEAN"
    return "UNRECOGNIZED"


CLEAN_RESULT = "**Result: ✅ Review Clean**"
BLOCKING_RESULT = "**Result: ⚠️ Changes Requested**"


class ResultDecisionAgreementTests(unittest.TestCase):
    def test_every_shipped_result_line_names_the_decision_outcome(self) -> None:
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            with self.subTest(sample=path.name):
                self.assertEqual(result_outcome(text), _label(text))

    def test_mutation_flipping_only_the_result_line_is_detected(self) -> None:
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            label = _label(text)
            for replacement in (CLEAN_RESULT, BLOCKING_RESULT):
                if result_outcome(replacement + "\n") == label:
                    continue
                with self.subTest(sample=path.name, result=replacement):
                    mutated = with_result(text, replacement)
                    self.assertNotEqual(result_outcome(mutated), _label(mutated))

    def test_mutation_flipping_only_the_decision_is_detected(self) -> None:
        for path in shipped_samples():
            text = path.read_text(encoding="utf-8")
            outcome = result_outcome(text)
            for flipped in ("REVIEW CLEAN", "CHANGES REQUIRED", "REVIEW INCOMPLETE"):
                if flipped == outcome:
                    continue
                with self.subTest(sample=path.name, decision=flipped):
                    mutated = with_decision(text, flipped)
                    self.assertNotEqual(mutated, text)
                    self.assertNotEqual(result_outcome(mutated), _label(mutated))


if __name__ == "__main__":
    unittest.main()
