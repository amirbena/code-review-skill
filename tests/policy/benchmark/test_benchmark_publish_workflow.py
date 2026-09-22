"""The publication-only workflow's triggers, credentials, and imports (#474; A13).

Contract: runtime_platform/benchmark/scheduled-operations/publication-architecture.md §4–§5
and runtime_platform/benchmark/publication-cli.md §8.
"""

from __future__ import annotations

import ast
import re
import sys
import unittest

import yaml

from tests.policy.benchmark.test_execution_no_github_writes import import_closure
from tests.support.paths import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "benchmark-publish.yml"
CLI = "runtime_platform/benchmark/scripts/publish_benchmark.py"
ENTRYPOINT = REPO_ROOT / CLI
APP_SECRETS = {"BENCHMARK_APP_ID", "BENCHMARK_APP_PRIVATE_KEY"}
APP_TOKEN_ACTION = "actions/create-github-app-token"
ALLOWED_ACTIONS = {"actions/checkout", "actions/setup-python", APP_TOKEN_ACTION}
STEP_ENV = {
    "BENCHMARK_CONTENTS_TOKEN", "BENCHMARK_ISSUES_TOKEN", "BENCHMARK_READ_TOKEN",
    "RUN_ID", "ACCEPT_UNATTRIBUTED", "DRY_RUN", "SWEEP_REPORT", "CONTENTS_SLUG", "ISSUES_SLUG",
}
MODEL_CREDENTIAL = re.compile(r"anthropic|openai|claude|gemini|model|api[_-]?key|oauth", re.IGNORECASE)
EXECUTION_MODULES = {
    "run_benchmark", "run_benchmark_routine", "benchmark_lane_run", "benchmark_review_adapter",
    "benchmark_routine_verify", "benchmark_drift", "benchmark_drift_evaluation", "benchmark_baseline",
    "benchmark_history", "benchmark_run_record", "benchmark_seal", "select_benchmark_cases", "shadow_validate",
}
STAGING_OR_HISTORY = ("benchmark-history", "claude/benchmark-result-")


def _triggers(workflow: dict) -> dict:
    # PyYAML reads the bare key `on` as boolean True.
    triggers = workflow.get("on", workflow.get(True))
    return {"workflow_dispatch": None} if triggers == "workflow_dispatch" else dict(triggers or {})


def _load(path=WORKFLOW) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _uncommented(path=WORKFLOW) -> str:
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#"))


class TriggerTests(unittest.TestCase):
    def test_triggers_are_exactly_schedule_and_workflow_dispatch(self) -> None:
        self.assertEqual(set(_triggers(_load())), {"schedule", "workflow_dispatch"})

    def test_the_job_runs_only_on_the_default_branch(self) -> None:
        (job,) = _load()["jobs"].values()
        self.assertEqual(job["if"], "github.ref == 'refs/heads/main'")
        self.assertEqual(job["environment"], "benchmark-publication")

    def test_sweeps_are_serialized(self) -> None:
        self.assertEqual(_load()["concurrency"], {"group": "benchmark-publish", "cancel-in-progress": False})

    def test_no_workflow_listens_to_history_or_staging_refs(self) -> None:
        for path in sorted(WORKFLOWS.glob("*.y*ml")):
            triggers = _triggers(_load(path))
            self.assertNotIn("create", triggers, path.name)
            self.assertNotIn("delete", triggers, path.name)
            self.assertNotIn("workflow_run", triggers, path.name)
            push = triggers.get("push") or {}
            branches = push.get("branches", ["**"] if "push" in triggers else [])
            self.assertTrue(set(branches) <= {"main"}, f"{path.name} pushes on {branches}")
            for ref in STAGING_OR_HISTORY:
                self.assertNotIn(ref, _uncommented(path), path.name)


class CredentialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.workflow = _load()
        (self.job,) = self.workflow["jobs"].values()
        self.steps = self.job["steps"]

    def test_job_token_is_contents_read_and_the_default_is_none(self) -> None:
        self.assertEqual(self.workflow["permissions"], {})
        self.assertEqual(self.job["permissions"], {"contents": "read"})

    def test_the_only_secrets_are_the_app_credentials(self) -> None:
        self.assertEqual(set(re.findall(r"secrets\.([A-Za-z0-9_]+)", self.text)), APP_SECRETS)
        self.assertNotRegex(self.text, r"secrets\s*\[|toJSON\(\s*secrets")

    def test_no_other_workflow_holds_the_app_key_or_runs_the_publisher(self) -> None:
        for path in sorted(WORKFLOWS.glob("*.y*ml")):
            if path != WORKFLOW:
                self.assertIsNone(re.search(r"BENCHMARK_APP|publish_benchmark", path.read_text(encoding="utf-8")), path.name)

    def test_two_app_tokens_each_one_permission_and_this_repository(self) -> None:
        mints = [s for s in self.steps if s.get("uses", "").startswith(APP_TOKEN_ACTION + "@")]
        granted = []
        for step in mints:
            inputs = step["with"]
            permissions = {k: v for k, v in inputs.items() if k.startswith("permission-")}
            self.assertEqual(len(permissions), 1, step["name"])
            granted += [f"{k}:{v}" for k, v in permissions.items()]
            self.assertEqual(inputs["repositories"], "code-review-skill")
            self.assertEqual(inputs["app-id"], "${{ secrets.BENCHMARK_APP_ID }}")
        self.assertEqual(granted, ["permission-contents:write", "permission-issues:write"])

    def test_no_model_or_provider_credential(self) -> None:
        for step in self.steps:
            for name in step.get("env", {}):
                self.assertIn(name, STEP_ENV, step["name"])
        for name in list(self.job.get("env", {})) + list(self.workflow.get("env", {})):
            self.assertEqual(name, "BENCHMARK_APP_SLUG")
        self.assertIsNone(MODEL_CREDENTIAL.search(_uncommented()))

    def test_the_watchdog_never_receives_the_contents_write_token(self) -> None:
        watchdog = self._step("Watchdog")
        self.assertNotIn("BENCHMARK_CONTENTS_TOKEN", watchdog["env"])
        self.assertEqual(watchdog["env"]["BENCHMARK_READ_TOKEN"], "${{ github.token }}")

    def test_actions_are_first_party_and_pinned_to_a_commit(self) -> None:
        for step in self.steps:
            if "uses" in step:
                action, _, ref = step["uses"].partition("@")
                self.assertIn(action, ALLOWED_ACTIONS)
                self.assertRegex(ref, r"^[0-9a-f]{40}$")
        checkout = next(s for s in self.steps if s.get("uses", "").startswith("actions/checkout@"))
        self.assertIs(checkout["with"]["persist-credentials"], False)

    def _step(self, name: str) -> dict:
        return next(s for s in self.steps if s["name"] == name)


class CommandTests(unittest.TestCase):
    def setUp(self) -> None:
        (job,) = _load()["jobs"].values()
        self.steps = job["steps"]
        self.runs = [s for s in self.steps if "run" in s]

    def test_run_blocks_interpolate_no_expression(self) -> None:
        for step in self.runs:
            self.assertNotIn("${{", step["run"], step["name"])

    def test_only_the_publication_cli_runs_and_nothing_is_installed(self) -> None:
        commands = [line.strip() for s in self.runs for line in s["run"].splitlines() if line.strip().startswith("python")]
        self.assertEqual([c.split()[1:3] for c in commands], [[CLI, "sweep"], [CLI, "watchdog"]])
        for step in self.runs:
            self.assertNotRegex(step["run"], r"\bpip\b|\bcurl\b|\bgh\b|\bgit\b")

    def test_the_watchdog_follows_the_sweep_even_when_it_fails_and_reads_its_report(self) -> None:
        names = [s["name"] for s in self.steps]
        sweep, watchdog = self.steps[names.index("Sweep sealed results")], self.steps[names.index("Watchdog")]
        self.assertEqual(names.index("Watchdog"), names.index("Sweep sealed results") + 1)
        self.assertEqual(watchdog["if"], "${{ !cancelled() }}")
        self.assertEqual(sweep["env"]["SWEEP_REPORT"], watchdog["env"]["SWEEP_REPORT"])
        self.assertIn('> "$SWEEP_REPORT"', sweep["run"])
        self.assertIn('--sweep-report "$SWEEP_REPORT"', watchdog["run"])
        # An empty report (the sweep died before printing) must not stop the watchdog.
        self.assertIn('if [ -s "$SWEEP_REPORT" ]', watchdog["run"])


class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closure = import_closure(ENTRYPOINT)

    def test_closure_is_the_publisher(self) -> None:
        self.assertLessEqual({"cli", "sweep", "watchdog", "benchmark_result", "benchmark_fingerprint"}, set(self.closure))

    def test_no_benchmark_execution_evaluation_or_reference_module_is_imported(self) -> None:
        self.assertEqual(EXECUTION_MODULES & set(self.closure), set())
        for path in self.closure.values():
            self.assertNotIn("reference", path.relative_to(REPO_ROOT).parts, path)

    def test_no_drift_derivation_or_process_spawning(self) -> None:
        for stem, path in sorted(self.closure.items()):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                self.assertFalse(_top_level_names(node) & {"subprocess", "multiprocessing"}, stem)
                if isinstance(node, (ast.Name, ast.Attribute)):
                    self.assertNotEqual(getattr(node, "id", getattr(node, "attr", None)), "classify_drift", stem)

    def test_module_level_imports_are_stdlib_so_the_job_installs_nothing(self) -> None:
        # A function-local import (the corpus loader's `yaml`) never runs on the publication path.
        for stem, path in sorted(self.closure.items()):
            for node in ast.parse(path.read_text(encoding="utf-8")).body:
                for top in _top_level_names(node):
                    self.assertTrue(top in sys.stdlib_module_names or top == "runtime_platform", f"{stem} imports {top}")


def _top_level_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {a.name.split(".")[0] for a in node.names}
    if isinstance(node, ast.ImportFrom) and node.module and not node.level:
        return {node.module.split(".")[0]}
    return set()


if __name__ == "__main__":
    unittest.main()
