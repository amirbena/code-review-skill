"""The private-evidence validation gate checklist (#689) cannot drift from the tests it cites or from the ADR."""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

OPS = REPO_ROOT / "runtime_platform" / "benchmark" / "scheduled-operations"
GATE = OPS / "private-evidence-validation-gate.md"
ADR = OPS / "private-evidence-repository.md"
REFERENCE = re.compile(r"`(?:(test_\w+\.py))?::(test_\w+)`")
INVARIANTS = (
    *(f"V{i}" for i in range(1, 11)), *(f"F{i}" for i in range(1, 14)), "F4a", "F9a",
    *(f"I{i}" for i in range(1, 5)), *(f"P{i}" for i in range(1, 4)), *(f"R{i}" for i in range(1, 5)),
)


class GateChecklistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = GATE.read_text(encoding="utf-8")
        cls.tests = {p.name: p.read_text(encoding="utf-8") for p in (REPO_ROOT / "tests").rglob("test_*.py")}

    def test_every_cited_test_exists(self) -> None:
        cited = 0
        for line in self.text.splitlines():
            current = None
            for file, name in REFERENCE.findall(line):
                current = file or current
                self.assertIsNotNone(current, f"{name}: a reference needs a file on its row")
                self.assertIn(current, self.tests, current)
                self.assertRegex(self.tests[current], rf"def {name}\(", f"{current}::{name}")
                cited += 1
        self.assertGreater(cited, 40)

    def test_the_rerun_command_names_real_modules(self) -> None:
        for module in re.findall(r"tests\.(?:unit|policy)\.benchmark\.(\w+)", self.text):
            self.assertIn(f"{module}.py", self.tests, module)

    @staticmethod
    def expand(cell: str) -> set[str]:
        """`V1–V10` and `F9, F9a` cells as explicit invariant ids; a range is expanded, never pattern-matched."""
        ids: set[str] = set()
        for token in re.findall(r"[VFIPR]\d+[a-z]?(?:–[VFIPR]\d+)?", cell):
            if "–" in token:
                (letter, low), high = (token[0], int(re.findall(r"\d+", token)[0])), int(re.findall(r"\d+", token)[1])
                ids |= {f"{letter}{n}" for n in range(low, high + 1)}
            else:
                ids.add(token)
        return ids

    def test_every_adr_invariant_has_a_row_and_a_result(self) -> None:
        checklist = self.text.split("## 2. ADR invariant checklist", 1)[1].split("\n## ", 1)[0]
        rows = [r for r in checklist.splitlines() if r.startswith("| ") and not r.startswith(("| Invariant", "| ---"))]
        covered: set[str] = set()
        for row in rows:
            covered |= self.expand(row.split("|")[1])
            self.assertRegex(row.split("|")[2], r"pass|open \(G-open-\d\)", row)
        self.assertEqual(set(INVARIANTS) - covered, set())

    def test_the_invariant_expander_is_exact(self) -> None:
        self.assertEqual(self.expand(" V1–V3 "), {"V1", "V2", "V3"})
        self.assertEqual(self.expand(" F9, F9a "), {"F9", "F9a"})
        self.assertNotIn("F5", self.expand(" F9, F9a "))

    def test_open_items_are_carried_not_hidden(self) -> None:
        for token in ("G-open-1", "G-open-2", "F12, F13"):
            self.assertIn(token, self.text)

    def test_the_pre_688_snapshot_is_committed(self) -> None:
        self.assertIn("tests/support/pre_688_sentinel_record.json", self.text)
        self.assertTrue((REPO_ROOT / "tests" / "support" / "pre_688_sentinel_record.json").is_file())


class GateWiringTests(unittest.TestCase):
    def test_the_adr_blocks_the_cutover_on_the_gate(self) -> None:
        adr = " ".join(ADR.read_text(encoding="utf-8").split())
        self.assertIn("0. **Gate.** The [validation gate](private-evidence-validation-gate.md)", adr)
        self.assertIn("is not merged before this", adr)

    def test_the_gate_is_in_the_directory_map(self) -> None:
        self.assertIn("(private-evidence-validation-gate.md)", (OPS / "README.md").read_text(encoding="utf-8"))

    def test_the_gate_is_not_packaged(self) -> None:
        self.assertIn("not packaged into either Skill archive", " ".join(GATE.read_text(encoding="utf-8").split()))


if __name__ == "__main__":
    unittest.main()
