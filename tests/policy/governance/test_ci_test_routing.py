"""Contracts for fail-safe FAST/FULL routing in validate.yml and its integration-input guard."""

from __future__ import annotations

import re
import unittest

import yaml

from scripts.validation import ci_test_route as router
from tests.integration.packaging._shared import TEMP_ROOT_INPUTS
from tests.support.paths import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "validate.yml"
INTEGRATION_DIR = REPO_ROOT / "tests" / "integration"
FULL_COMMAND = "python -m unittest discover -s tests -t ."

_REPO_ROOT_READ = re.compile(r'REPO_ROOT((?:\s*/\s*"[^"]+")+)')


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _on(workflow: dict) -> dict:
    return workflow.get("on", workflow.get(True))


def _step(job: dict, name: str) -> dict:
    return next(step for step in job["steps"] if step.get("name") == name)


def _overlaps_allowlist(path: str) -> bool:
    # A read of a path, or of any directory containing an allowlisted path, overlaps.
    path = path.strip("/")
    entries = [*router.FAST_FILES, *(d.rstrip("/") for d in router.FAST_DIRS)]
    return any(path == e or e.startswith(path + "/") or path.startswith(e + "/") for e in entries)


def _integration_repo_root_reads() -> set[str]:
    reads = set()
    for module in INTEGRATION_DIR.rglob("*.py"):
        for match in _REPO_ROOT_READ.finditer(module.read_text(encoding="utf-8")):
            reads.add("/".join(re.findall(r'"([^"]+)"', match.group(1))))
    return reads


class ValidateWorkflowRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _load_workflow()
        self.jobs = self.workflow["jobs"]

    def test_required_test_job_is_always_created(self) -> None:
        test = self.jobs["test"]
        self.assertNotIn("name", test)
        self.assertEqual(test["needs"], "route")
        self.assertEqual(test["if"], "${{ !cancelled() }}")

    def test_no_path_filters(self) -> None:
        for event, config in _on(self.workflow).items():
            with self.subTest(event=event):
                self.assertFalse({"paths", "paths-ignore"} & set(config or {}))

    def test_runs_full_on_push_to_main(self) -> None:
        on = _on(self.workflow)
        self.assertIn("pull_request", on)
        self.assertEqual(on["push"], {"branches": ["main"]})

    def test_router_runs_from_the_base_sha(self) -> None:
        route = self.jobs["route"]
        checkout = route["steps"][0]
        self.assertEqual(checkout["uses"], "actions/checkout@v4")
        self.assertEqual(checkout["with"]["ref"], "${{ github.event.pull_request.base.sha || github.sha }}")
        self.assertEqual(checkout["with"]["fetch-depth"], 0)
        step = _step(route, "Route")
        self.assertIn("python3 scripts/validation/ci_test_route.py route", step["run"])
        self.assertIn('echo "tier=full"', step["run"])
        self.assertEqual(route["outputs"]["tier"], "${{ steps.route.outputs.tier }}")

    def test_integration_runs_unless_tier_is_exactly_fast(self) -> None:
        test = self.jobs["test"]
        full = _step(test, "Run repository tests")
        self.assertEqual(full["if"], "${{ needs.route.outputs.tier != 'fast' }}")
        self.assertEqual(full["run"], FULL_COMMAND)
        self.assertEqual(full["env"], {"DISTRIBUTION_INSTALL_CHECK": "1"})
        fast = _step(test, "Run repository tests except tests.integration (FAST tier)")
        self.assertEqual(fast["if"], "${{ needs.route.outputs.tier == 'fast' }}")
        self.assertEqual(fast["run"], "python scripts/validation/ci_test_route.py run-fast")

    def test_non_test_validation_runs_on_both_tiers(self) -> None:
        test = self.jobs["test"]
        for name in (
            "Validate Skill metadata",
            "Build the canonical Skill trees",
            "Validate the built Skill trees against the Agent Skills spec",
        ):
            with self.subTest(step=name):
                self.assertNotIn("if", _step(test, name))
        for job in ("skill-tree-parity", "skill-tree-hash-equality"):
            with self.subTest(job=job):
                self.assertNotIn("if", self.jobs[job])
                self.assertNotEqual(self.jobs[job].get("needs"), "route")


class IntegrationInputGuardTests(unittest.TestCase):
    def test_overlap_helper_catches_parent_and_child_reads(self) -> None:
        for path in ("policies", "policies/x.md", ".github", "README.md", ".github/ISSUE_TEMPLATE/a.yml"):
            with self.subTest(path=path):
                self.assertTrue(_overlaps_allowlist(path))
        for path in ("docs", "skills", "policiesx", "tests/README.md"):
            with self.subTest(path=path):
                self.assertFalse(_overlaps_allowlist(path))

    def test_temp_root_copy_list_shares_no_path_with_the_fast_allowlist(self) -> None:
        for path in TEMP_ROOT_INPUTS:
            with self.subTest(path=path):
                self.assertFalse(_overlaps_allowlist(path))

    def test_integration_repo_root_reads_share_no_path_with_the_fast_allowlist(self) -> None:
        reads = _integration_repo_root_reads()
        self.assertIn("CHANGELOG.md", reads)
        for path in sorted(reads):
            with self.subTest(path=path):
                self.assertFalse(_overlaps_allowlist(path))


if __name__ == "__main__":
    unittest.main()
