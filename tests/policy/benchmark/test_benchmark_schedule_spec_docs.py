"""Contract checks for the scheduled-benchmark schedule spec (#469).

Pins runtime_platform/benchmark/schedule-spec.md, its manifest, and the thin
Routine prompt template (A12) so they cannot drift apart silently.
"""

import re
import unittest

from runtime_platform.benchmark.scripts import benchmark_schedule_manifest as sm
from tests.support.paths import REPO_ROOT

BENCHMARK = REPO_ROOT / "runtime_platform" / "benchmark"
SPEC = BENCHMARK / "schedule-spec.md"
README = BENCHMARK / "README.md"
ROUTINE_DOC = REPO_ROOT / "docs" / "benchmark" / "cloud-routine-integration.md"
RUNBOOK = BENCHMARK / "scheduled-operations" / "provisioning-runbook.md"


def _prompt_template() -> str:
    text = ROUTINE_DOC.read_text(encoding="utf-8")
    section = text.split("## 9. Routine prompt template", 1)[1].split("### 9.1", 1)[0]
    match = re.search(r"```text\n(.*?)```", section, re.S)
    assert match, "cloud-routine-integration.md §9 has no template block"
    return match.group(1)


class ScheduleSpecDocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = SPEC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())
        cls.manifest = sm.load_manifest()

    def test_is_not_packaged_and_names_its_issues(self) -> None:
        self.assertIn("not packaged into either Skill archive", self.text)
        for token in ("#469", "#466", "#470", "#471", "#473", "#475"):
            self.assertIn(token, self.raw)

    def test_documents_every_manifest_field(self) -> None:
        for field in (
            "repository", "entrypoint", "mode", "intended_cadence", "intended_start",
            "target_completion_local", "max_gap_hours", "tracking_issue", "health_issue",
            "confirmation", "staging_ref_pattern", "pusher_allowlist",
            "max_new_issues_per_run", "missed_run_comment_interval_hours", "labels",
        ):
            self.assertTrue(field in self.raw, field)

    def test_documents_gap_ceilings_and_weekday(self) -> None:
        self.assertIn("Sentinel ≤ 96, comprehensive ≤ 192", self.text)
        self.assertIn("**Friday, 01:00 `Asia/Jerusalem`**", self.text)

    def test_documents_every_label(self) -> None:
        for label in self.manifest["labels"]:
            self.assertIn(f"`{label['name']}`", self.raw)

    def test_provisioning_runbook_creates_exactly_the_manifest_labels(self) -> None:
        created = {
            name: (color, description)
            for name, color, description in re.findall(
                r'^gh label create (\S+)\s+--repo \$R --color (\w+) --description "([^"]+)"$',
                RUNBOOK.read_text(encoding="utf-8"),
                re.M,
            )
        }
        expected = {
            label["name"]: (label["color"], label["description"]) for label in self.manifest["labels"]
        }
        self.assertEqual(created, expected)

    def test_label_creation_is_provisioning_not_runtime(self) -> None:
        self.assertIn("creation is a provisioning step", self.text)
        self.assertIn("fails closed at start-up", self.text)

    def test_prompt_spec_defers_to_the_single_literal_template(self) -> None:
        self.assertIn("cloud-routine-integration.md", self.raw)
        self.assertNotIn("```text", self.raw)

    def test_prompt_spec_ties_failure_handling_to_a12(self) -> None:
        self.assertIn("A12's \"exit non-zero on failure\"", self.text)
        self.assertIn("reports no success", self.text)

    def test_links_resolve(self) -> None:
        for target in re.findall(r"\]\((?!https?:|#)([^)#]+)", self.raw):
            self.assertTrue((SPEC.parent / target).exists(), target)

    def test_readme_lists_the_spec(self) -> None:
        self.assertIn("schedule-spec.md", README.read_text(encoding="utf-8"))


class RoutinePromptTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entrypoint = sm.load_manifest()["entrypoint"]
        cls.lines = [line.rstrip() for line in _prompt_template().splitlines() if line.strip()]

    def _step(self, number: int) -> str:
        steps: dict[int, list[str]] = {}
        current = 0
        for line in self.lines:
            match = re.match(r"^(\d+)\. ", line)
            if match:
                current = int(match.group(1))
            steps.setdefault(current, []).append(line.strip())
        return " ".join(" ".join(steps[number]).split())

    def test_template_has_exactly_the_three_permitted_steps(self) -> None:
        numbered = [line for line in self.lines if re.match(r"^\d+\. ", line)]
        self.assertEqual([line.split(".", 1)[0] for line in numbered], ["1", "2", "3"])

    def test_only_permitted_command_appears(self) -> None:
        step2 = self._step(2).replace(" \\ ", " ")
        allowed = re.compile(
            rf"^2\. Run: python3 {re.escape(self.entrypoint)} --mode \S+"
            r"( \[--case-id <id> \.\.\.\])? --model-id <[^>]+>$"
        )
        self.assertRegex(step2, allowed)
        self.assertNotRegex(re.sub(r"<[^>]*>", "", step2), r"[;&|`$]")

    def test_checkout_step_is_a_fresh_copy_of_the_manifest_repository(self) -> None:
        step1 = self._step(1)
        self.assertIn("fresh copy", step1)
        self.assertIn(sm.load_manifest()["repository"], step1)

    def test_template_takes_a_mode_and_model_id_for_every_lane(self) -> None:
        template = _prompt_template()
        self.assertIn("--mode", template)
        self.assertIn("--model-id", template)
        for lane in sm.load_manifest()["lanes"].values():
            self.assertIn(lane["mode"], template)

    def test_failure_step_stops_without_success_retry_or_publication(self) -> None:
        step3 = self._step(3)
        for clause in (
            "exits non-zero, stop",
            "do not report success",
            "do not retry silently",
            "do not post or push anything to GitHub",
        ):
            self.assertIn(clause, step3)


if __name__ == "__main__":
    unittest.main()
