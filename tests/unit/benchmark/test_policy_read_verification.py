#!/usr/bin/env python3
"""Mandatory policy reads versus the rendered coverage and verdict (Issues #806, #808)."""

from __future__ import annotations

import json
import re
import unittest

from runtime_platform.benchmark.reference import benchmark_blocking_verdict as bbv
from runtime_platform.benchmark.reference.benchmark_blocking_verdict import ReadState
from runtime_platform.benchmark.scripts import benchmark_run_evidence as bre
from tests.support.paths import REPO_ROOT

CORPUS = REPO_ROOT / "benchmark" / "corpus" / "policy-loading"
LOCAL_SKILL = (REPO_ROOT / "skills/local-code-review/SKILL.md").read_text(encoding="utf-8")
GITHUB_SKILL = (REPO_ROOT / "skills/github-pr-review/SKILL.md").read_text(encoding="utf-8")
BLOCKING = {"result_label": "⚠️ Changes Requested", "decision_label": "CHANGES REQUIRED", "coverage": "complete"}
INCOMPLETE = {"result_label": "⚠️ Review Incomplete", "decision_label": "REVIEW INCOMPLETE", "coverage": "incomplete"}
CLEAN = {"result_label": "✅ Review Clean", "decision_label": "REVIEW CLEAN", "coverage": "complete"}
SEVERITY = "shared/policies/severity.md"
VERDICT_CONSISTENCY = "shared/policies/verdict-consistency.md"
RUNTIME_VALIDATION = "shared/policies/runtime-validation.md"
SKILLS = {
    "local-code-review": LOCAL_SKILL,
    "github-pr-review": GITHUB_SKILL,
}
RUNBOOKS = {
    "local-code-review": ("local-review",),
    "github-pr-review": ("passive-pr-review", "active-pr-review"),
}


def _replayed(fixture: dict) -> list[tuple[str, dict]]:
    """Calls as the benchmark's own stream parser extracts them."""
    events = [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": c["name"], "input": c["input"]}]}}
        for c in fixture["tool_calls"]
    ]
    return list(bre.parse_stream("\n".join(json.dumps(e) for e in events)).tool_calls)


def _fixture(name: str) -> dict:
    return json.loads((CORPUS / name).read_text(encoding="utf-8"))


def _check(calls, rendered, skill=LOCAL_SKILL, fired_conditional=()) -> bbv.PolicyReadCheck:
    return bbv.check_policy_reads(skill, calls, fired_conditional=fired_conditional, **rendered)


def _bash(command: str) -> tuple[str, dict]:
    return ("Bash", {"command": command})


class RequiredSetTests(unittest.TestCase):
    def test_local_set_is_the_unconditional_section_2_files(self) -> None:
        required = bbv.required_policy_files(LOCAL_SKILL)
        self.assertEqual(len(required), 16)
        self.assertNotIn(RUNTIME_VALIDATION, required)
        self.assertIn(VERDICT_CONSISTENCY, required)
        self.assertIn("policies/repository-state.md", required)
        self.assertNotIn("shared/policies/review-ownership.md", required)
        self.assertNotIn("shared/policies/repository-expansion.md", required)

    def test_github_set_keeps_ownership_and_drops_context_members(self) -> None:
        required = bbv.required_policy_files(GITHUB_SKILL)
        self.assertIn("shared/policies/review-ownership.md", required)
        self.assertIn(VERDICT_CONSISTENCY, required)
        for dropped in ("parallel-review", "agent-delegation", "repository-expansion", "stacked-pr-review"):
            self.assertFalse([p for p in required if dropped in p], dropped)

    def test_github_set_includes_the_unconditional_github_only_policies(self) -> None:
        required = bbv.required_policy_files(GITHUB_SKILL)
        self.assertEqual(len(required), 28)
        for name in ("review-action-authorization", "review-authority", "review-output", "github-review", "finding-placement"):
            self.assertIn(f"policies/{name}.md", required)

    def test_a_shared_read_does_not_confirm_the_same_named_local_policy(self) -> None:
        calls = [("Read", {"file_path": "/repo/skills/github-pr-review/../../shared/policies/review-context.md"})]
        states = bbv.classify_policy_reads(["policies/review-context.md", "shared/policies/review-context.md"], calls)
        self.assertEqual(states["policies/review-context.md"], ReadState.MISSING)
        self.assertEqual(states["shared/policies/review-context.md"], ReadState.CONFIRMED)

    def test_valid_fixture_confirms_exactly_the_current_required_set(self) -> None:
        calls = _replayed(_fixture("complete-review-confirmed-reads.json"))
        states = bbv.classify_policy_reads(bbv.required_policy_files(LOCAL_SKILL), calls)
        self.assertEqual(set(states.values()), {ReadState.CONFIRMED})


class RegressionFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.failing = _fixture("v1.80.2-skipped-policies.json")
        self.calls = _replayed(self.failing)

    def test_failing_v1_80_2_review_is_detected(self) -> None:
        result = _check(self.calls, self.failing["rendered"])
        self.assertFalse(result.ok)
        self.assertEqual(result.files(ReadState.CONFIRMED), ())
        self.assertEqual(result.files(ReadState.UNVERIFIABLE), (SEVERITY,))
        self.assertEqual(len(result.files(ReadState.MISSING)), 15)
        self.assertIn(VERDICT_CONSISTENCY, result.files(ReadState.MISSING))
        self.assertEqual(len(result.violations), 3)
        self.assertEqual(sum("blocking" in v for v in result.violations), 2)
        self.assertIn("Coverage line missing", result.violations[-1])

    def test_same_trace_rendered_incomplete_is_consistent(self) -> None:
        self.assertTrue(_check(self.calls, INCOMPLETE).ok)

    def test_complete_coverage_line_is_a_violation_even_with_incomplete_labels(self) -> None:
        result = _check(self.calls, {**INCOMPLETE, "coverage": "complete"})
        self.assertEqual([v.split(" rendered")[0] for v in result.violations], ["Coverage"])

    def test_missing_mandatory_reads_never_pass_with_a_clean_verdict(self) -> None:
        self.assertFalse(_check(self.calls, CLEAN).ok)

    def test_valid_complete_review_passes(self) -> None:
        valid = _fixture("complete-review-confirmed-reads.json")
        self.assertTrue(_check(_replayed(valid), valid["rendered"]).ok)

    def test_fixtures_hold_no_user_paths_or_session_data(self) -> None:
        for path in CORPUS.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            for forbidden in ("/Users/", "sessionId", "finance", ".claude/"):
                self.assertNotIn(forbidden, text, path.name)


class MutationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid = _replayed(_fixture("complete-review-confirmed-reads.json"))

    def _without(self, path: str) -> list[tuple[str, dict]]:
        calls = []
        for name, tool_input in self.valid:
            text = json.dumps(tool_input)
            if name == "Read" and text.endswith(f"/{path}\"}}"):
                continue
            calls.append((name, json.loads(text.replace(f" {path}", ""))))
        return calls

    def test_dropping_one_required_file_fails_and_names_it(self) -> None:
        result = _check(self._without("shared/policies/review-scope.md"), CLEAN)
        self.assertFalse(result.ok)
        self.assertEqual(result.files(ReadState.MISSING), ("shared/policies/review-scope.md",))
        self.assertTrue(_check(self._without("shared/policies/review-scope.md"), INCOMPLETE).ok)

    def test_dropping_a_read_tool_member_is_detected(self) -> None:
        self.assertEqual(_check(self._without(SEVERITY), CLEAN).files(ReadState.MISSING), (SEVERITY,))

    def test_an_unfired_conditional_file_is_not_required(self) -> None:
        calls = [c for c in self.valid if "repository-expansion" not in json.dumps(c[1])]
        self.assertTrue(_check(calls, CLEAN).ok)

    def test_indirect_or_bounded_reads_are_unverifiable_never_confirmed(self) -> None:
        cases = {
            "glob": "cd $SKILL_DIR && cat shared/policies/*.md",
            "basename after cd": "cd $SKILL_DIR/shared/policies && cat severity.md",
            "truncated pipe": f"cat $SKILL_DIR/{SEVERITY} | head -c 9000",
            "line range": f"sed -n 1,60p $SKILL_DIR/{SEVERITY}",
            "redirected": f"cat $SKILL_DIR/{SEVERITY} > /tmp/dump.txt",
            "loop with cap": f"for f in {SEVERITY}; do cat $f; done | head -c 90000",
        }
        for label, command in cases.items():
            with self.subTest(label):
                states = bbv.classify_policy_reads([SEVERITY], [_bash(command)])
                self.assertEqual(states[SEVERITY], ReadState.UNVERIFIABLE)

    def test_bounded_read_tool_is_unverifiable_and_full_read_is_confirmed(self) -> None:
        for tool_input, expected in (
            ({"file_path": f"$SKILL_DIR/{SEVERITY}", "limit": 100}, ReadState.UNVERIFIABLE),
            ({"file_path": f"$SKILL_DIR/{SEVERITY}", "offset": 10}, ReadState.UNVERIFIABLE),
            ({"file_path": f"$SKILL_DIR/{SEVERITY}"}, ReadState.CONFIRMED),
        ):
            self.assertEqual(bbv.classify_policy_reads([SEVERITY], [("Read", tool_input)])[SEVERITY], expected)

    def test_a_resumed_ranged_chain_stays_unverifiable_because_traces_hold_no_lengths(self) -> None:
        chain = [("Read", {"file_path": f"$SKILL_DIR/{SEVERITY}", "offset": o, "limit": 60}) for o in (1, 61, 121)]
        self.assertEqual(bbv.classify_policy_reads([SEVERITY], chain)[SEVERITY], ReadState.UNVERIFIABLE)
        self.assertFalse(_check(chain, CLEAN).ok)

    def test_listing_or_sizing_a_file_is_not_a_read(self) -> None:
        for command in (f"wc -c $SKILL_DIR/{SEVERITY}", "ls $SKILL_DIR/shared/policies", f"grep -c P0 {SEVERITY}"):
            with self.subTest(command):
                self.assertEqual(bbv.classify_policy_reads([SEVERITY], [_bash(command)])[SEVERITY], ReadState.MISSING)

    def test_an_unverifiable_read_cannot_support_a_complete_verdict(self) -> None:
        calls = [c for c in self.valid if "review-scope" not in json.dumps(c[1])]
        calls.append(_bash("cat $SKILL_DIR/shared/policies/review-scope.md | head -50"))
        result = _check(calls, CLEAN)
        self.assertFalse(result.ok)
        self.assertEqual(result.files(ReadState.UNVERIFIABLE), ("shared/policies/review-scope.md",))

    def test_required_set_drift_is_caught(self) -> None:
        grown = LOCAL_SKILL.replace(
            "[`git-safety.md`](../../shared/policies/git-safety.md),",
            "[`git-safety.md`](../../shared/policies/git-safety.md),\n[`new-policy.md`](../../shared/policies/new-policy.md),",
        )
        self.assertNotEqual(grown, LOCAL_SKILL)
        result = _check(self.valid, CLEAN, skill=grown)
        self.assertEqual(result.files(ReadState.MISSING), ("shared/policies/new-policy.md",))


class InventoryAlignmentTests(unittest.TestCase):
    """Issues #808/#810: `SKILL.md` section 2 owns the load set, so a shared policy a runbook
    step applies must be named there (unconditionally or with an activation rule), or the
    checkpoint and the checker cannot see it."""

    def test_every_shared_policy_a_runbook_applies_is_named_in_section_2(self) -> None:
        for skill, skill_md in SKILLS.items():
            section = bbv._SECTION_RE.search(skill_md).group(1)
            named = set(re.findall(r"\]\(\.\./\.\./(shared/[^)#\s]+\.md)\)", section))
            for runbook in RUNBOOKS[skill]:
                text = (REPO_ROOT / "skills" / skill / "runbooks" / f"{runbook}.md").read_text(encoding="utf-8")
                applied = set(re.findall(r"\]\(\.\./\.\./\.\./(shared/[^)#\s]+\.md)\)", text.split("\n## Steps", 1)[1]))
                with self.subTest(skill=skill, runbook=runbook):
                    self.assertGreater(len(applied), 10)
                    self.assertEqual(sorted(applied - named), [])

    def test_removing_a_policy_from_section_2_is_detected_by_the_alignment_rule(self) -> None:
        stripped = LOCAL_SKILL.replace(
            " [`verdict-consistency.md`](../../shared/policies/verdict-consistency.md)", "", 1
        )
        self.assertNotEqual(stripped, LOCAL_SKILL)
        self.assertNotIn(VERDICT_CONSISTENCY, bbv.required_policy_files(stripped))

    def test_conditional_policies_stay_out_of_the_required_set(self) -> None:
        for skill, skill_md in SKILLS.items():
            required = bbv.required_policy_files(skill_md)
            for conditional in ("repository-expansion", "large-pr-partitioning", "invocation-options", "finding-rendering-human"):
                with self.subTest(skill=skill, conditional=conditional):
                    self.assertEqual([p for p in required if p.endswith(f"/{conditional}.md")], [])


class DefinitiveVerdictTests(unittest.TestCase):
    """Issue #808: no definitive verdict survives a missing or unverifiable mandatory read."""

    @staticmethod
    def _full(skill_md: str) -> list[tuple[str, dict]]:
        return [("Read", {"file_path": f"$SKILL_DIR/{p}"}) for p in bbv.required_policy_files(skill_md)]

    def test_complete_trace_passes_a_definitive_verdict_in_both_skills(self) -> None:
        for skill, skill_md in SKILLS.items():
            for label, rendered in (("clean", CLEAN), ("blocking", BLOCKING)):
                with self.subTest(skill=skill, verdict=label):
                    self.assertTrue(_check(self._full(skill_md), rendered, skill=skill_md).ok)

    def test_dropping_any_required_file_blocks_every_definitive_verdict(self) -> None:
        for skill, skill_md in SKILLS.items():
            full = self._full(skill_md)
            for index, (_, tool_input) in enumerate(full):
                path = tool_input["file_path"].removeprefix("$SKILL_DIR/")
                calls = full[:index] + full[index + 1 :]
                for label, rendered in (("clean", CLEAN), ("blocking", BLOCKING)):
                    with self.subTest(skill=skill, dropped=path, verdict=label):
                        result = _check(calls, rendered, skill=skill_md)
                        self.assertFalse(result.ok)
                        self.assertEqual(result.files(ReadState.MISSING), (path,))
                with self.subTest(skill=skill, dropped=path, verdict="incomplete"):
                    self.assertTrue(_check(calls, INCOMPLETE, skill=skill_md).ok)

    def test_a_missing_verdict_consistency_read_is_named_in_both_skills(self) -> None:
        for skill, skill_md in SKILLS.items():
            calls = [c for c in self._full(skill_md) if not c[1]["file_path"].endswith(VERDICT_CONSISTENCY)]
            with self.subTest(skill=skill):
                result = _check(calls, CLEAN, skill=skill_md)
                self.assertEqual(result.files(ReadState.MISSING), (VERDICT_CONSISTENCY,))
                self.assertTrue(any(VERDICT_CONSISTENCY in v for v in result.violations))

    def test_a_bounded_verdict_consistency_read_is_unverifiable_and_blocks(self) -> None:
        calls = [c for c in self._full(LOCAL_SKILL) if not c[1]["file_path"].endswith(VERDICT_CONSISTENCY)]
        calls.append(("Read", {"file_path": f"$SKILL_DIR/{VERDICT_CONSISTENCY}", "limit": 40}))
        result = _check(calls, BLOCKING)
        self.assertEqual(result.files(ReadState.UNVERIFIABLE), (VERDICT_CONSISTENCY,))
        self.assertFalse(result.ok)

    def test_a_definitive_verdict_without_a_coverage_line_is_a_violation(self) -> None:
        full = self._full(LOCAL_SKILL)
        for label, rendered in (("clean", CLEAN), ("blocking", BLOCKING)):
            with self.subTest(verdict=label):
                result = _check(full, {**rendered, "coverage": None})
                self.assertEqual(result.violations, ("Coverage line missing although a definitive verdict was rendered",))
        self.assertTrue(_check(full, {**INCOMPLETE, "coverage": None}).ok)


class FiredConditionalTests(unittest.TestCase):
    """Issue #816: `runtime-validation.md` loads on activation; a fixture declares when it fired."""

    def setUp(self) -> None:
        self.fired = _fixture("declared-command-runtime-validation-fired.json")
        self.quiet = _fixture("no-command-runtime-validation-not-fired.json")

    def _check_fixture(self, fixture: dict, rendered: dict | None = None, calls=None) -> bbv.PolicyReadCheck:
        return _check(
            calls if calls is not None else _replayed(fixture),
            rendered or fixture["rendered"],
            fired_conditional=fixture["fired_conditional"],
        )

    def test_both_skills_declare_the_file_conditional_with_the_predicate(self) -> None:
        for skill, skill_md in SKILLS.items():
            with self.subTest(skill=skill):
                self.assertNotIn(RUNTIME_VALIDATION, bbv.required_policy_files(skill_md))
                self.assertIn("(a command is named in the instruction sources resolved at repository-instruction discovery", skill_md)
                # The explicit no-command Validation entry and the default `reasoned` state stay unconditional.
                for owner in ("shared/templates/review-summary.md", "shared/templates/finding.md"):
                    self.assertIn(owner, bbv.required_policy_files(skill_md))

    def test_fired_read_before_a_definitive_verdict_is_consistent(self) -> None:
        self.assertTrue(self._check_fixture(self.fired).ok)

    def test_no_command_review_is_consistent_without_the_read(self) -> None:
        self.assertEqual(self.quiet["fired_conditional"], [])
        self.assertIn("No repository command", self.quiet["validation_entry"])
        self.assertNotIn(RUNTIME_VALIDATION, json.dumps(self.quiet["tool_calls"]))
        self.assertTrue(self._check_fixture(self.quiet).ok)

    def test_fired_predicate_without_the_read_and_a_definitive_verdict_is_a_violation(self) -> None:
        calls = [c for c in _replayed(self.fired) if RUNTIME_VALIDATION not in json.dumps(c[1])]
        result = self._check_fixture(self.fired, calls=calls)
        self.assertFalse(result.ok)
        self.assertEqual(result.files(ReadState.MISSING), (RUNTIME_VALIDATION,))
        self.assertTrue(any(RUNTIME_VALIDATION in v for v in result.violations))
        self.assertTrue(self._check_fixture(self.fired, INCOMPLETE, calls).ok)


if __name__ == "__main__":
    unittest.main()
