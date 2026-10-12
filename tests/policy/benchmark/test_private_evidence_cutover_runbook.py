"""The private-evidence cutover sequence (#717) cannot drift between the runbook and the ADR."""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT

OPS = REPO_ROOT / "runtime_platform" / "benchmark" / "scheduled-operations"


def _flat(name: str) -> str:
    return " ".join((OPS / name).read_text(encoding="utf-8").split())


def _in_order(text: str, markers: tuple[str, ...]) -> None:
    last = -1
    for marker in markers:
        at = text.find(marker)
        assert at != -1, f"missing: {marker}"
        assert at > last, f"out of order: {marker}"
        last = at


class CutoverSequenceTests(unittest.TestCase):
    def test_the_runbook_states_the_dependency_ordered_sequence(self) -> None:
        _in_order(_flat("private-evidence-cutover-runbook.md"), (
            "Verify the four labels exist",
            "Create, in `$EVD`, one tracking issue per lane",
            "Record the **actual** numbers on #690",
            "Freeze, drain, inventory",
            "Copy by SHA and reconcile",
            "1. Merge the cutover commit: `evidence.phase: private`",
            "each lane's `tracking_issue` and the `health_issue`",
            "Then apply the public creation ruleset",
            "Negative Routine push test (X1), before any Routine is re-enabled",
            "Update every evidence-producing Routine's prompt",
            "Re-enable the Routines, only after step 2 passed",
        ))

    def test_the_adr_orders_preparation_before_the_cutover_and_the_ruleset_test_before_reenablement(self) -> None:
        _in_order(_flat("private-evidence-repository.md"), (
            "**Preparation (before step 0",
            "**Cutover order:**",
            "sets each lane's `tracking_issue` and the `health_issue`",
            "apply the public creation ruleset (Q4)",
            "negative Routine push test",
            "Re-enable the paused Routines, only after step 4's negative push test has passed",
        ))

    def test_a_failed_negative_push_test_keeps_the_routines_paused(self) -> None:
        for name in ("private-evidence-cutover-runbook.md", "private-evidence-repository.md"):
            text = _flat(name)
            self.assertIn("(R-a)" if name.endswith("repository.md") else "(rollback R-a)", text)
            self.assertIn("not waived", text)

    def test_no_private_issue_number_is_invented(self) -> None:
        text = _flat("private-evidence-cutover-runbook.md")
        self.assertIn("Do not derive them from #486–#488", text)

    def test_x1_is_recorded_partial_not_pass(self) -> None:
        for name in ("private-evidence-cutover-runbook.md", "private-evidence-repository.md"):
            self.assertIn("`PARTIAL`", _flat(name))


if __name__ == "__main__":
    unittest.main()
