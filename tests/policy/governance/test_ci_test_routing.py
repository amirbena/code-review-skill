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

    def test_required_test_job_is_always_created_and_routes_itself(self) -> None:
        test = self.jobs["test"]
        self.assertNotIn("name", test)
        self.assertNotIn("needs", test)
        self.assertNotIn("if", test)
        self.assertEqual(set(self.jobs), {"test", "skill-tree-parity", "skill-tree-hash-equality"})

    def test_no_path_filters(self) -> None:
        for event, config in _on(self.workflow).items():
            with self.subTest(event=event):
                self.assertFalse({"paths", "paths-ignore"} & set(config or {}))

    def test_runs_on_pull_requests_only(self) -> None:
        # A push to main is reserved for release-publish.yml (#538).
        self.assertEqual(set(_on(self.workflow)), {"pull_request"})

    def test_router_runs_from_the_base_sha_outside_the_checkout(self) -> None:
        test = self.jobs["test"]
        self.assertEqual(test["steps"][0]["with"], {"persist-credentials": False})
        route = _step(test, "Route tests (FAST/FULL)")
        self.assertEqual(route["id"], "route")
        self.assertIs(route["continue-on-error"], True)
        run = route["run"]
        self.assertIn('route_repo="$RUNNER_TEMP/ci-route"', run)
        self.assertIn('fetch -q --no-tags --filter=blob:none origin "$BASE_SHA" "$HEAD_SHA"', run)
        self.assertIn('show "$BASE_SHA:scripts/validation/ci_test_route.py" > "$router"', run)
        self.assertIn('--repo "$route_repo"', run)
        self.assertIn('echo "tier=full"', run)
        self.assertNotIn("HEAD_SHA:scripts", run)
        steps = [step.get("name") for step in test["steps"]]
        self.assertLess(steps.index("Route tests (FAST/FULL)"), steps.index("Run repository tests"))

    def test_integration_runs_unless_tier_is_exactly_fast(self) -> None:
        test = self.jobs["test"]
        full = _step(test, "Run repository tests")
        self.assertEqual(full["if"], "${{ steps.route.outputs.tier != 'fast' }}")
        self.assertEqual(full["run"], FULL_COMMAND)
        self.assertEqual(full["env"], {"DISTRIBUTION_INSTALL_CHECK": "1"})
        fast = _step(test, "Run repository tests except tests.integration (FAST tier)")
        self.assertEqual(fast["if"], "${{ steps.route.outputs.tier == 'fast' }}")
        self.assertEqual(fast["run"], 'python "$RUNNER_TEMP/ci_test_route.py" run-fast')

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
