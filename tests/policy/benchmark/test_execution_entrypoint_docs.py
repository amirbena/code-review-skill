"""Contract checks for the execution entrypoint's canonical text (#470).

Pins `cloud-routine-integration.md` §2.2 to the CLI and to the manifest's confirmation
parameters, so the documented protocol cannot drift from what the code does.
"""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.scripts import benchmark_schedule_manifest as sm
from runtime_platform.benchmark.scripts import run_benchmark_routine as routine
from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "benchmark" / "cloud-routine-integration.md"


def _section_2_2() -> str:
    text = DOC.read_text(encoding="utf-8")
    return " ".join(text.split("### 2.2", 1)[1].split("## 3.", 1)[0].split())


class ExecutionEntrypointDocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.section = _section_2_2()
        cls.options = {a.dest: a.option_strings[0] for a in routine.build_arg_parser()._actions if a.option_strings}

    def test_every_seal_and_evaluation_option_is_documented(self) -> None:
        for dest in ("trigger", "seal_dir", "seal_remote", "history_root", "confirmation_budget_s"):
            self.assertIn(f"`{self.options[dest]}", self.section, dest)

    def test_confirmation_parameters_are_the_manifests(self) -> None:
        for name in sm.load_manifest()["confirmation"]:
            self.assertIn(f"`{name}`", self.section, name)
        for reason in ("systemic-cap", "unconfirmed-timeout", "drift.systemic"):
            self.assertIn(reason, self.section, reason)

    def test_states_the_seal_boundary(self) -> None:
        for phrase in (
            "claude/benchmark-result-<run_id>",
            "never forced",
            "no token",
            "outside `claude/`",
            "fails the run closed",
        ):
            self.assertIn(phrase, self.section, phrase)

    def test_states_what_a_failed_seal_can_leave_behind(self) -> None:
        self.assertIn("A failure before the push completes leaves nothing durable", self.section)
        self.assertIn("can leave a sealed ref while the run reports failure", self.section)

    def test_retired_evidence_argument_is_documented_as_gone(self) -> None:
        self.assertIn("`--evidence-issue` argument is no longer accepted", self.section)
        self.assertNotIn("evidence_issue", self.options)

    def test_the_canonical_protocol_states_the_unverified_rerun_outcome(self) -> None:
        text = " ".join((REPO_ROOT / "runtime_platform" / "benchmark" / "scheduled-operations" / "drift-issue-lifecycle-and-recovery.md").read_text(encoding="utf-8").split())
        self.assertIn("A confirmation rerun that does not pass positive completion verification fails the whole run closed", text)

    def test_the_schema_doc_defines_the_spec_digest(self) -> None:
        text = " ".join((REPO_ROOT / "runtime_platform" / "benchmark" / "benchmark-result-schema.md").read_text(encoding="utf-8").split())
        self.assertIn("`provenance.spec_sha256` is the SHA-256 of the canonical JSON of the expected-run manifest", text)


if __name__ == "__main__":
    unittest.main()
