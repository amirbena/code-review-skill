"""Structural contract checks for the finding lifecycle design (#62)."""

import unittest

from tests.support.paths import REPO_ROOT


DOC = REPO_ROOT / "docs" / "finding-lifecycle-contract.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"


class FindingLifecycleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_persistent_state_set_is_minimal(self) -> None:
        self.assertIn("Persist only two lifecycle states", self.text)
        self.assertIn("| `OPEN` |", self.raw)
        self.assertIn("| `RESOLVED` |", self.raw)
        self.assertIn(
            "`NEW`, `STILL_PRESENT` / `UNCHANGED`, and `REOPENED`", self.text
        )

    def test_event_set_is_complete(self) -> None:
        for event in (
            "`DETECTED`",
            "`STILL_PRESENT`",
            "`RESOLVED`",
            "`REOPENED`",
            "`UNCERTAIN`",
        ):
            self.assertIn(f"| {event} |", self.raw)

    def test_matching_boundary_names_all_outcomes(self) -> None:
        for heading in ("### `MATCH`", "### `NO MATCH`", "### `AMBIGUOUS`"):
            self.assertIn(heading, self.raw)
        self.assertIn(
            "This does **not** establish that the prior identity is resolved",
            self.text,
        )
        self.assertIn("authorizes no lifecycle transition", self.text)

    def test_resolution_requires_positive_evidence(self) -> None:
        for requirement in (
            "**Completed review.**",
            "**Verified relevant coverage.**",
            "**Positive absence evidence.**",
            "**No continuity ambiguity.**",
        ):
            self.assertIn(requirement, self.raw)
        self.assertIn(
            "Merely failing to emit a finding is not an observation of absence",
            self.text,
        )

    def test_ambiguity_cannot_resolve_or_reopen(self) -> None:
        self.assertIn("`AMBIGUOUS → RESOLVED`", self.raw)
        self.assertIn("`AMBIGUOUS → REOPENED`", self.raw)
        self.assertIn("preserve its established state", self.text)

    def test_recurrence_handshake_is_acyclic_and_ordered(self) -> None:
        section = self.raw.split("### Canonical recurrence handshake", 1)[1].split(
            "## 7. State-transition table", 1
        )[0]
        ordered_markers = (
            "**Read prior lifecycle state.**",
            "**Obtain positive current recurrence evidence.**",
            "**Activate #59 recurrence evaluation.**",
            "**Consume #59's outcome.**",
        )
        positions = [section.index(marker) for marker in ordered_markers]
        self.assertEqual(sorted(positions), positions)
        for value in ("`RESOLVED`", "`MATCH`", "`REOPENED`", "`OPEN`"):
            self.assertIn(value, section)

    def test_recurrence_evidence_does_not_prove_identity_or_reopen(self) -> None:
        self.assertIn(
            "Recurrence evidence permits matching to reconsider a previously resolved",
            self.text,
        )
        self.assertIn("it does not prove sameness", self.text)
        self.assertIn("Only a definite #59 `MATCH` may produce", self.text)

    def test_recurrence_matching_needs_no_pre_emitted_reopen_event(self) -> None:
        self.assertIn(
            "#59 does not require an already-emitted `REOPENED` event",
            self.text,
        )

    def test_resolved_recurrence_outcome_rows_fail_closed(self) -> None:
        table = self.raw.split("## 7. State-transition table", 1)[1].split(
            "Impossible or unsupported transitions:", 1
        )[0]
        self.assertIn(
            "| `RESOLVED` | yes; enables recurrence evaluation | `MATCH`", table
        )
        self.assertIn(
            "| `RESOLVED` | yes; enables recurrence evaluation | `NO MATCH`", table
        )
        self.assertIn(
            "| `RESOLVED` | yes; enables recurrence evaluation | `AMBIGUOUS`", table
        )
        self.assertIn("`NO TRANSITION` for prior identity | `RESOLVED`", table)
        self.assertIn("`UNCERTAIN` | `RESOLVED` preserved", table)

    def test_required_scenarios_are_present(self) -> None:
        rows = [line for line in self.raw.splitlines() if line.startswith("| ")]
        scenario_rows = [line for line in rows if line.split("|")[1].strip().isdigit()]
        self.assertEqual(15, len(scenario_rows))

    def test_cross_issue_boundaries_are_explicit(self) -> None:
        for issue in ("#59", "#60", "#64", "#65", "#66"):
            self.assertIn(f"- **{issue} —", self.raw)

    def test_architecture_links_to_contract(self) -> None:
        self.assertIn(
            "finding-lifecycle-contract.md",
            ARCHITECTURE.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
