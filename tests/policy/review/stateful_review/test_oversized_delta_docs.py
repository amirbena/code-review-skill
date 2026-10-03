"""Doc wiring markers for oversized reviewed-SHA delta handling (Issue #203)."""

import unittest

from tests.support.paths import REPO_ROOT

SKILL_DIR = REPO_ROOT / "skills" / "github-pr-review"
PARTITIONING = REPO_ROOT / "shared" / "policies" / "large-pr-partitioning.md"
DELTA_REVIEW = SKILL_DIR / "policies" / "reviewer-delta-review.md"
STATEFUL = SKILL_DIR / "policies" / "stateful-delta-rereview.md"
CONTRACT = REPO_ROOT / "docs" / "findings" / "delta-re-review-contract.md"
RUNBOOKS = (
    SKILL_DIR / "runbooks" / "active-pr-review.md",
    SKILL_DIR / "runbooks" / "passive-pr-review.md",
)


def _norm(path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class OversizedDeltaDocsTests(unittest.TestCase):
    def test_measurement_scope_stated_once_in_activation(self) -> None:
        text = PARTITIONING.read_text(encoding="utf-8")
        activation = text.split("## Activation", 1)[1].split("\n## ", 1)[0]
        norm = " ".join(activation.split())
        self.assertIn("Measurement scope", norm)
        self.assertIn("bounded delta alone", norm)
        self.assertIn("never as an input to selecting it", norm)
        self.assertEqual(text.count("**Measurement scope.**"), 1)

    def test_delta_review_policy_has_oversized_delta_section(self) -> None:
        raw = DELTA_REVIEW.read_text(encoding="utf-8")
        self.assertIn("## Oversized delta", raw)
        section = " ".join(raw.split("## Oversized delta", 1)[1].split("\n## ", 1)[0].split())
        for marker in (
            "large-pr-partitioning.md",
            "aggregate and de-duplicate across partitions first",
            "reconcile once",
            "REVIEW INCOMPLETE",
            "does not advance",
            "never escalates a delta to a full review",
        ):
            self.assertIn(marker, section)

    def test_stateful_policy_says_size_is_not_a_trigger(self) -> None:
        section = " ".join(
            STATEFUL.read_text(encoding="utf-8")
            .split("## 6. Escalation", 1)[1]
            .split("\n## 7.", 1)[0]
            .split()
        )
        self.assertIn("not a trigger", section)
        self.assertIn("Oversized delta", section)

    def test_runbooks_reference_the_shared_scope(self) -> None:
        for runbook in RUNBOOKS:
            norm = _norm(runbook)
            self.assertIn("per that policy's \"Activation\"", norm, runbook.name)
            self.assertIn("reviewer-delta-review.md", norm, runbook.name)
            self.assertIn("Oversized delta", norm, runbook.name)

    def test_contract_notes_size_never_escalates(self) -> None:
        self.assertIn("size alone is never an escalation input", _norm(CONTRACT))


if __name__ == "__main__":
    unittest.main()
