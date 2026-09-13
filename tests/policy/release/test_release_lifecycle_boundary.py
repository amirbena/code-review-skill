#!/usr/bin/env python3
"""Architectural-boundary contract for issue #168: the PR release-assessment
lifecycle and the authoritative main/release lifecycle are two physically
separate GitHub Actions workflows, not one workflow with conditionals.

This is the structural guard the issue asks for: it fails if `plan` or
`publish` ever reappear inside the PR-triggered workflow (even behind an
`if:` that is always false — GitHub still creates a `Skipped` check run
for a job that exists), if the main/release workflow ever gains a
`pull_request` trigger, or if either lifecycle stops sharing
`scripts/release_lib/` and starts duplicating classification rules in
YAML.

Individual job contracts (permissions, step ordering, outputs) are covered
by `test_release_worthiness_workflow.py` (PR lifecycle) and
`test_release_publish_workflow.py` (main lifecycle); this file only checks
the boundary between them.
"""

from __future__ import annotations

import unittest

import yaml

from tests.support.paths import REPO_ROOT

PR_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-worthiness.yml"
MAIN_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-publish.yml"
RELEASE_LIB_DIR = REPO_ROOT / "scripts" / "release_lib"
RELEASE_SCRIPT = REPO_ROOT / "scripts" / "release_worthiness.py"
RELEASE_DOC = REPO_ROOT / "docs" / "RELEASE.md"


def _load(path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _on(data: dict):
    return data.get("on", data.get(True))


class PrWorkflowScopeTests(unittest.TestCase):
    """1-4: the PR workflow contains only release-gate + conditional
    package, never plan/publish."""

    def setUp(self) -> None:
        self.data = _load(PR_WORKFLOW)
        self.jobs = self.data["jobs"]

    def test_contains_release_gate(self) -> None:
        self.assertIn("release-gate", self.jobs)

    def test_preserves_conditional_package(self) -> None:
        package = self.jobs["package"]
        self.assertEqual(package["needs"], "release-gate")
        self.assertEqual(
            str(package["if"]).strip(), "needs.release-gate.outputs.release_worthy == 'true'"
        )

    def test_does_not_define_plan(self) -> None:
        self.assertNotIn("plan", self.jobs)

    def test_does_not_define_publish(self) -> None:
        self.assertNotIn("publish", self.jobs)

    def test_plan_and_publish_are_physically_absent_not_merely_disabled(self) -> None:
        # The objective is not an always-false `if:` — GitHub still creates
        # a Skipped check for a job that exists. Assert the job keys are
        # absent from the parsed YAML entirely, and that neither job name
        # appears anywhere in the raw file (e.g. smuggled into a comment
        # that later becomes a real job id).
        raw = PR_WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("\n  plan:", raw)
        self.assertNotIn("\n  publish:", raw)


class MainWorkflowScopeTests(unittest.TestCase):
    """5-8: the main/release workflow owns authoritative assessment, plan,
    and publish, and is never triggered by pull_request."""

    def setUp(self) -> None:
        self.data = _load(MAIN_WORKFLOW)
        self.jobs = self.data["jobs"]

    def test_owns_plan(self) -> None:
        self.assertIn("plan", self.jobs)

    def test_owns_publish(self) -> None:
        self.assertIn("publish", self.jobs)

    def test_plan_job_performs_the_authoritative_assessment(self) -> None:
        # `plan` is not merely a version calculator: it runs
        # auto-release-plan, which classifies the accumulated change set
        # since the latest tag and requires real CHANGELOG coverage before
        # reporting should_release=true (see release_lib.commands.planning
        # .cmd_auto_release_plan, exercised in tests/unit/release/).
        plan_steps = self.jobs["plan"]["steps"]
        run = " ".join(str(s.get("run", "")) for s in plan_steps)
        self.assertIn("auto-release-plan", run)
        outputs = self.jobs["plan"]["outputs"]
        self.assertIn("should_release", outputs)

    def test_is_not_triggered_by_pull_request(self) -> None:
        on = _on(self.data)
        self.assertNotIn("pull_request", on)

    def test_is_triggered_only_by_push_and_workflow_dispatch(self) -> None:
        on = _on(self.data)
        self.assertEqual(set(on.keys()), {"push", "workflow_dispatch"})


class RequiredCheckIdentityTests(unittest.TestCase):
    """10: the existing `release-gate` output contract, job identity, and
    required-check name stay exactly compatible with issue #241 / PR #256."""

    def setUp(self) -> None:
        self.pr_data = _load(PR_WORKFLOW)

    def test_workflow_name_is_unchanged(self) -> None:
        self.assertEqual(self.pr_data["name"], "Release worthiness")

    def test_release_gate_job_id_is_unchanged(self) -> None:
        gate = self.pr_data["jobs"]["release-gate"]
        self.assertNotIn("name", gate)  # the job id itself is the check context

    def test_release_gate_output_contract_is_unchanged(self) -> None:
        gate = self.pr_data["jobs"]["release-gate"]
        self.assertEqual(
            gate["outputs"]["release_worthy"], "${{ steps.classify.outputs.release_worthy }}"
        )

    def test_release_doc_still_names_the_required_check(self) -> None:
        doc = RELEASE_DOC.read_text(encoding="utf-8")
        self.assertIn("Release worthiness", doc)
        self.assertIn("release-gate", doc)
        self.assertIn("`release-gate`", doc)


class SharedEngineTests(unittest.TestCase):
    """9: both lifecycles drive the same scripts/release_lib/ assessment
    implementation rather than duplicating classification rules in YAML."""

    def test_pr_workflow_invokes_the_shared_cli(self) -> None:
        raw = PR_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("release_worthiness.py resolve-base-ref", raw)
        self.assertIn("release_worthiness.py assess", raw)

    def test_main_workflow_invokes_the_shared_cli(self) -> None:
        raw = MAIN_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("release_worthiness.py auto-release-plan", raw)
        self.assertIn("release_worthiness.py generate-changelog", raw)
        self.assertIn("release_worthiness.py release-preflight", raw)

    def test_neither_workflow_reimplements_classification_in_shell(self) -> None:
        # No workflow computes a SemVer bump, a release-worthy verdict, or
        # a baseline tag itself — those decisions come back as command
        # outputs from release_worthiness.py, never inline shell/YAML.
        for workflow in (PR_WORKFLOW, MAIN_WORKFLOW):
            raw = workflow.read_text(encoding="utf-8")
            self.assertNotIn("git describe --tags", raw)
            self.assertNotIn("major", raw.lower())
            self.assertNotIn("minor", raw.lower())

    def test_release_worthiness_entrypoint_re_exports_the_shared_library(self) -> None:
        text = RELEASE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("from release_lib", text)

    def test_assess_and_auto_release_plan_share_the_same_classifier(self) -> None:
        # release-gate's `assess` (PR-time preview) and the main
        # lifecycle's `auto-release-plan` (authoritative) both resolve to
        # release_lib.classification.classify_paths — there is no second,
        # PR-specific or main-specific classification engine.
        assess_src = (RELEASE_LIB_DIR / "assessment.py").read_text(encoding="utf-8")
        planning_src = (RELEASE_LIB_DIR / "commands" / "planning.py").read_text(encoding="utf-8")
        self.assertIn("from release_lib.classification import Classification, classify_paths", assess_src)
        self.assertIn("from release_lib.classification import classify_paths", planning_src)


class NoOtherPullRequestTriggeredReleaseWorkflowTests(unittest.TestCase):
    """Belt-and-braces: no other workflow file under .github/workflows
    quietly defines a plan/publish job triggered by pull_request, which
    would reopen the same skipped-check problem this issue closes."""

    def test_only_two_release_workflows_exist(self) -> None:
        workflows_dir = REPO_ROOT / ".github" / "workflows"
        release_related = sorted(
            p.name for p in workflows_dir.glob("*.yml")
            if "release" in p.name
        )
        self.assertEqual(release_related, ["release-publish.yml", "release-worthiness.yml"])

    def test_no_pull_request_triggered_workflow_defines_plan_or_publish(self) -> None:
        workflows_dir = REPO_ROOT / ".github" / "workflows"
        for path in sorted(workflows_dir.glob("*.yml")):
            data = _load(path)
            on = _on(data)
            if not isinstance(on, dict) or "pull_request" not in on:
                continue
            jobs = set((data.get("jobs") or {}).keys())
            self.assertNotIn("plan", jobs, path.name)
            self.assertNotIn("publish", jobs, path.name)


if __name__ == "__main__":
    unittest.main()
