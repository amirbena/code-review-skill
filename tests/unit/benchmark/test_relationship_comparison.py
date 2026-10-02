"""Search-only vs. relationship-enriched comparison harness (Issue #605); no live model."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from runtime_platform.benchmark.scripts import run_relationship_comparison as rc
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "relationship-recall"
PROTOCOL = CORPUS_DIR / "comparison-protocol.md"


def _row(outcome="correct", role="control", fp=0, seconds=100.0, tokens=1000, gaps=False):
    return {
        "outcome": outcome,
        "role": role,
        "false_positives": fp,
        "context_gaps_rendered": gaps,
        "telemetry": {"wall_seconds": seconds, "input_tokens": tokens},
    }


def _rows(a_outcomes, b_outcomes, **kwargs):
    ids = sorted(rc.CLASS_OF)

    def arm(outcomes):
        return {cid: [_row(outcomes.get(cid, "correct"), **kwargs)] for cid in ids}

    return {"A": arm(a_outcomes), "B": arm(b_outcomes)}


class AnswersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.answers = json.loads(rc.ANSWERS_PATH.read_text(encoding="utf-8"))["cases"]

    def test_answers_cover_exactly_the_compared_cases(self) -> None:
        self.assertEqual(set(self.answers), set(rc.CLASS_OF))

    def test_every_compared_case_resolves_to_one_fixture(self) -> None:
        for case_id in rc.CLASS_OF:
            self.assertEqual(rc.find_case(case_id).id, case_id)

    def test_answers_use_only_the_closed_questions_and_no_free_text(self) -> None:
        questions = {"consumers_of", "implementers_of", "tests_exercising", "analogues_of"}
        for case_id, answers in self.answers.items():
            for answer in answers:
                self.assertIn(answer["question"], questions, case_id)
                self.assertEqual(
                    set(answer), {"question", "subject", "edges", "candidates", "complete"}, case_id
                )
                self.assertIsInstance(answer["candidates"], int)

    def test_rendered_answer_is_bound_to_the_snapshot_with_closed_candidates(self) -> None:
        answers = self.answers["repo-intel-python-dynamic-dispatch-safe-failure"]
        rendered = json.loads(rc.render_answers(answers, "abc123"))
        self.assertEqual(rendered[0]["snapshot_id"], "abc123")
        self.assertEqual(rendered[0]["candidates"], [{"reason": "ambiguous resolution"}])
        self.assertFalse(rendered[0]["complete"])


class StreamAndRoleTests(unittest.TestCase):
    def test_parse_stream_captures_skill_invocation_and_result(self) -> None:
        lines = [
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "p:local-code-review"}}]}},
            {"type": "result", "result": "report", "usage": {"output_tokens": 5}},
        ]
        parsed = rc.parse_stream("\n".join(json.dumps(line) for line in lines) + "\nnot json")
        self.assertEqual(parsed["skills"], ["p:local-code-review"])
        self.assertEqual(parsed["result"]["result"], "report")

    def test_roles_cover_every_case_and_match_the_fixtures(self) -> None:
        self.assertEqual(set(rc.ROLE_OF), set(rc.CLASS_OF))
        for case_id, role in rc.ROLE_OF.items():
            expects_finding = any(f.required for f in rc.find_case(case_id).findings)
            self.assertEqual(role == "positive", expects_finding, case_id)

    def test_every_class_has_one_positive_control_and_unresolvable_case(self) -> None:
        for klass in set(rc.CLASS_OF.values()):
            roles = sorted(rc.ROLE_OF[c] for c, k in rc.CLASS_OF.items() if k == klass and klass != "consumer")
            if klass != "consumer":
                self.assertEqual(roles, ["control", "positive", "unresolvable"], klass)

    def test_context_gaps_requires_the_heading_not_a_mention(self) -> None:
        self.assertTrue(rc.CONTEXT_GAPS_HEADING.search("### Context gaps\n- x"))
        self.assertFalse(rc.CONTEXT_GAPS_HEADING.search("There are no context gaps here."))

    def test_run_that_did_not_invoke_the_skill_under_test_is_excluded(self) -> None:
        entry = {
            "status": "executed",
            "metrics": {"false_negatives": 0, "false_positives": 0},
            "telemetry": {"skills_invoked": ["code-review-skills:local-code-review"]},
        }
        self.assertEqual(rc.classify("relrecall-affected-test-still-holds-control", entry)["outcome"], "excluded")
        entry["telemetry"]["skills_invoked"] = [f"{rc.PLUGIN_NAME}:local-code-review"]
        self.assertEqual(rc.classify("relrecall-affected-test-still-holds-control", entry)["outcome"], "correct")


class DecisionRuleTests(unittest.TestCase):
    def test_no_difference_is_not_justified(self) -> None:
        result = rc.evaluate(_rows({}, {}))
        self.assertEqual(result["gain"], 0)
        self.assertFalse(result["conditions"]["1_quality_gain"])
        self.assertFalse(result["index_justified"])

    def test_gain_across_enough_cases_without_regression_or_cost_is_justified(self) -> None:
        a = {cid: "missed" for cid in sorted(rc.CLASS_OF)[:3]}
        result = rc.evaluate(_rows(a, {}))
        self.assertEqual(result["gain"], 3)
        self.assertTrue(result["index_justified"], result["conditions"])

    def test_unequal_exclusions_do_not_create_a_gain(self) -> None:
        rows = _rows({}, {})
        for cid in sorted(rc.CLASS_OF)[:4]:
            rows["A"][cid] = [_row("correct"), _row("excluded")]
        self.assertEqual(rc.evaluate(rows)["gain"], 0)

    def test_cost_is_per_review_not_total(self) -> None:
        rows = _rows({}, {})
        for cid in sorted(rc.CLASS_OF)[:3]:
            rows["B"][cid] = [_row(seconds=100.0), _row(seconds=100.0)]
        self.assertTrue(rc.evaluate(rows)["conditions"]["4_acceptable_cost"])

    def test_gain_concentrated_in_one_case_does_not_count(self) -> None:
        rows = _rows({}, {})
        cid = sorted(rc.CLASS_OF)[0]
        rows["A"][cid] = [_row("missed") for _ in range(3)]
        rows["B"][cid] = [_row("correct") for _ in range(3)]
        result = rc.evaluate(rows)
        self.assertEqual(result["gain"], 3)
        self.assertFalse(result["conditions"]["1_quality_gain"])

    def test_cost_over_one_and_a_half_times_fails(self) -> None:
        a = {cid: "missed" for cid in sorted(rc.CLASS_OF)[:3]}
        rows = _rows(a, {})
        for cid in rows["B"]:
            rows["B"][cid] = [_row(seconds=200.0)]
        self.assertFalse(rc.evaluate(rows)["conditions"]["4_acceptable_cost"])

    def test_false_positive_on_a_control_in_arm_b_is_inflation(self) -> None:
        a = {cid: "missed" for cid in sorted(rc.CLASS_OF)[:3]}
        rows = _rows(a, {})
        cid = "relrecall-affected-test-still-holds-control"
        rows["B"][cid] = [_row("wrong", fp=1)]
        result = rc.evaluate(rows)
        self.assertEqual(result["inflation_control"], 1)
        self.assertFalse(result["index_justified"])

    def test_many_excluded_runs_make_the_comparison_inconclusive(self) -> None:
        rows = _rows({}, {})
        for cid in rows["B"]:
            rows["B"][cid] = [_row("excluded")]
        self.assertFalse(rc.evaluate(rows)["conditions"]["5_valid_arms"])


class AdapterTelemetryTests(unittest.TestCase):
    def test_a_failed_review_keeps_partial_telemetry(self) -> None:
        adapter = rc.ComparisonAdapter(plugin_dir=Path("."), answers=None, timeout=1.0)
        timeout = subprocess.TimeoutExpired(cmd="claude", timeout=1.0)
        with mock.patch.object(rc.subprocess, "run", side_effect=timeout):
            with self.assertRaises(subprocess.TimeoutExpired):
                adapter._run("prompt", cwd=Path("."))
        self.assertEqual(adapter.telemetry["prompt_chars"], len("prompt"))
        self.assertIn("wall_seconds", adapter.telemetry)


class ProtocolTests(unittest.TestCase):
    def test_protocol_states_the_rule_and_names_the_deferrals(self) -> None:
        text = PROTOCOL.read_text(encoding="utf-8")
        for needle in ("## Decision rule", "1.5×", "#129 §11", "upper bound"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
