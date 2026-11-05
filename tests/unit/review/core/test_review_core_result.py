"""The review-core JSON result validates against its schema (Issue #843).

Contract: skills/review-core/templates/result.schema.json, with meanings
owned by skills/review-core/rules/findings.md. Each way a result can be
malformed is rejected, and the examples obey the mechanical decision.

Run with:
    python3 -m unittest tests.unit.review.core.test_review_core_result
"""

from __future__ import annotations

import copy
import json
import unittest

from tests.support.json_schema_subset import validate
from tests.support.paths import REPO_ROOT

SCHEMA = json.loads(
    (REPO_ROOT / "skills" / "review-core" / "templates" / "result.schema.json").read_text(encoding="utf-8")
)
SHA_A = "3f9c1e2a7b4d5c60918273645a1b2c3d4e5f6071"
SHA_B = "9a8b7c6d5e4f30211203f4e5d6c7b8a9f0e1d2c3"

LOCAL_RESULT = {
    "schema_version": "2.0.0",
    "skill": "review-core",
    "target": {
        "kind": "local",
        "repository": "acme/payments",
        "base_ref": "main",
        "base_sha": SHA_A,
        "base_source": "upstream-merge-base",
        "head_sha": SHA_B,
        "pr_number": None,
        "categories": {"committed": 2, "staged": 0, "unstaged": 1, "untracked": 0},
    },
    "mode": "intent",
    "mini_skills": [],
    "summary": "Adds bounded retries around the charge call.",
    "findings": [
        {
            "id": "F1",
            "severity": "P1",
            "title": "Retry loop reports a timed-out charge as successful",
            "location": "src/payments/retry.py:88",
            "evidence": "`charge_with_retry` returns `ChargeResult.ok()` after every attempt times out.",
            "impact": "A charge that never completed is recorded as paid.",
            "fix": "Return a failure result when every attempt timed out.",
        }
    ],
    "not_investigated": [{"concern": "Token refresh on retry", "reason": "declined"}],
    "not_reviewed": [],
    "incomplete": [],
    "counts": {"p0": 0, "p1": 1, "p2": 0},
    "decision": "CHANGES REQUIRED",
}

PR_RESULT = {
    **copy.deepcopy(LOCAL_RESULT),
    "target": {
        "kind": "pr",
        "repository": "acme/payments",
        "base_ref": "main",
        "base_sha": SHA_A,
        "base_source": "pr-base",
        "head_sha": SHA_B,
        "pr_number": 42,
        "categories": None,
    },
    "mode": "auto",
    "mini_skills": [{"name": "review-backend", "reason": "The change adds a migration."}],
    "findings": [],
    "not_investigated": [],
    "incomplete": ["head-moved"],
    "counts": {"p0": 0, "p1": 0, "p2": 0},
    "decision": "REVIEW INCOMPLETE",
}


def mechanical_decision(result: dict) -> str:
    """rules/findings.md, "Decision": incomplete overrides; else any P0/P1 blocks."""
    if result["incomplete"]:
        return "REVIEW INCOMPLETE"
    blocking = sum(1 for f in result["findings"] if f["severity"] in ("P0", "P1"))
    return "CHANGES REQUIRED" if blocking else "REVIEW CLEAN"


def tally(result: dict) -> dict[str, int]:
    return {key: sum(1 for f in result["findings"] if f["severity"] == key.upper()) for key in ("p0", "p1", "p2")}


class ValidResultTests(unittest.TestCase):
    def test_examples_validate(self) -> None:
        for name, result in (("local", LOCAL_RESULT), ("pr", PR_RESULT)):
            with self.subTest(example=name):
                self.assertEqual(validate(result, SCHEMA), ())

    def test_examples_follow_the_mechanical_decision(self) -> None:
        for name, result in (("local", LOCAL_RESULT), ("pr", PR_RESULT)):
            with self.subTest(example=name):
                self.assertEqual(result["counts"], tally(result))
                self.assertEqual(result["decision"], mechanical_decision(result))

    def test_p2_only_result_is_clean(self) -> None:
        result = copy.deepcopy(LOCAL_RESULT)
        result["findings"][0]["severity"] = "P2"
        result["counts"] = tally(result)
        result["decision"] = mechanical_decision(result)
        self.assertEqual(result["decision"], "REVIEW CLEAN")
        self.assertEqual(validate(result, SCHEMA), ())


def mutated(path: tuple, value=None, *, delete: bool = False) -> dict:
    result = copy.deepcopy(LOCAL_RESULT)
    node = result
    for key in path[:-1]:
        node = node[key]
    if delete:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return result


class InvalidResultTests(unittest.TestCase):
    CASES = {
        "unknown top-level key": mutated(("confidence",), "credible"),
        "unknown finding key": mutated(("findings", 0, "confidence"), "credible"),
        "missing finding fix": mutated(("findings", 0, "fix"), delete=True),
        "empty finding evidence": mutated(("findings", 0, "evidence"), ""),
        "unknown severity": mutated(("findings", 0, "severity"), "P3"),
        "bad finding id": mutated(("findings", 0, "id"), "1"),
        "unknown decision": mutated(("decision",), "APPROVED"),
        "trigger outside the closed set": mutated(("incomplete",), ["too-large"]),
        "unknown mini-skill": mutated(("mini_skills",), [{"name": "review-everything", "reason": "x"}]),
        "core listed as a mini-skill": mutated(("mini_skills",), [{"name": "review-core", "reason": "x"}]),
        "unknown mode": mutated(("mode",), "deep"),
        "abbreviated sha": mutated(("target", "head_sha"), "3f9c1e2"),
        "unknown base source": mutated(("target", "base_source"), "guessed"),
        "negative count": mutated(("counts", "p1"), -1),
        "missing not_investigated": mutated(("not_investigated",), delete=True),
        "wrong schema version": mutated(("schema_version",), "1.0.0"),
    }

    def test_each_malformed_result_is_rejected(self) -> None:
        for name, result in self.CASES.items():
            with self.subTest(case=name):
                self.assertNotEqual(validate(result, SCHEMA), ())


if __name__ == "__main__":
    unittest.main()
