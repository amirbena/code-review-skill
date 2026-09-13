#!/usr/bin/env python3
"""Safety and ordering contract for the PR-lifecycle release-worthiness
automation (issue #168 lifecycle split).

`release-worthiness.yml` is triggered only by `pull_request` and owns only
two jobs: `release-gate` (the required, always-created, read-only PR
check) and the conditional, non-required `package` job. It never mutates
the repository, never touches the release App credentials, and — most
importantly — never defines `plan` or `publish`: the authoritative
main/release lifecycle lives entirely in the separate
`release-publish.yml` (see `test_release_publish_workflow.py`), so GitHub
never creates a `plan` or `publish` check run (not even `Skipped`) from a
pull request.

This preserves the behavior shipped by issue #241 / PR #256: `release-gate`
always resolves, `package` stays conditional on
`release-gate.outputs.release_worthy`, and the required check identity
stays exactly `Release worthiness / release-gate`.
"""

from __future__ import annotations

import unittest

import yaml

from tests.support.paths import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-worthiness.yml"
SCRIPT = REPO_ROOT / "scripts" / "release_worthiness.py"
RELEASE_DOC = REPO_ROOT / "docs" / "RELEASE.md"


def _load() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _on(data: dict):
    # PyYAML parses the bare key `on` as the boolean True.
    return data.get("on", data.get(True))


def _step_index(steps: list[dict], needle: str) -> int:
    for i, step in enumerate(steps):
        blob = " ".join(str(v) for v in (step.get("name", ""), step.get("run", ""), step.get("uses", "")))
        if needle in blob:
            return i
    raise AssertionError(f"no step matching {needle!r}")


def _step(steps: list[dict], needle: str) -> dict:
    return steps[_step_index(steps, needle)]


class TriggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _load()
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_triggered_only_by_pull_request(self) -> None:
        on = _on(self.data)
        self.assertEqual(list(on.keys()), ["pull_request"])

    def test_no_push_or_workflow_dispatch_trigger(self) -> None:
        on = _on(self.data)
        self.assertNotIn("push", on)
        self.assertNotIn("workflow_dispatch", on)

    def test_no_pull_request_target(self) -> None:
        self.assertNotIn("pull_request_target", _on(self.data))
        self.assertNotIn("pull_request_target:", self.raw)

    def test_runs_for_every_pull_request_event_type(self) -> None:
        types = _on(self.data)["pull_request"]["types"]
        for event in ("opened", "synchronize", "reopened", "edited"):
            self.assertIn(event, types)


class JobTopologyTests(unittest.TestCase):
    """The PR workflow owns exactly `release-gate` and `package` — nothing
    else, and specifically never `plan` or `publish`."""

    def setUp(self) -> None:
        self.data = _load()
        self.jobs = self.data["jobs"]

    def test_defines_exactly_release_gate_and_package(self) -> None:
        self.assertEqual(set(self.jobs.keys()), {"release-gate", "package"})

    def test_does_not_define_plan(self) -> None:
        self.assertNotIn("plan", self.jobs)

    def test_does_not_define_publish(self) -> None:
        self.assertNotIn("publish", self.jobs)

    def test_never_mints_the_release_app_token(self) -> None:
        self.assertNotIn("create-github-app-token", WORKFLOW.read_text(encoding="utf-8"))

    def test_never_checks_out_main_by_ref(self) -> None:
        # release-gate/package operate on the PR head; only the authoritative
        # main-lifecycle workflow checks out `main` explicitly.
        for job in self.jobs.values():
            for step in job["steps"]:
                if isinstance(step.get("uses"), str) and step["uses"].startswith("actions/checkout"):
                    self.assertNotEqual((step.get("with") or {}).get("ref"), "main")


class PermissionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _load()
        self.jobs = self.data["jobs"]

    def test_top_level_read_only(self) -> None:
        self.assertEqual(self.data["permissions"], {"contents": "read"})

    def test_release_gate_is_read_only_and_no_persisted_creds(self) -> None:
        gate = self.jobs["release-gate"]
        self.assertEqual(gate["permissions"], {"contents": "read"})
        checkout = next(
            s for s in gate["steps"]
            if isinstance(s.get("uses"), str) and s["uses"].startswith("actions/checkout")
        )
        self.assertIs(checkout["with"]["persist-credentials"], False)

    def test_package_is_read_only_and_no_persisted_creds(self) -> None:
        package = self.jobs["package"]
        self.assertEqual(package["permissions"], {"contents": "read"})
        checkout = next(
            s for s in package["steps"]
            if isinstance(s.get("uses"), str) and s["uses"].startswith("actions/checkout")
        )
        self.assertIs(checkout["with"]["persist-credentials"], False)

    def test_no_job_has_write_permissions(self) -> None:
        for name, job in self.jobs.items():
            for scope, level in (job.get("permissions") or {}).items():
                self.assertEqual(level, "read", f"{name}: {scope}")

    def test_no_job_mints_the_app_token(self) -> None:
        minters = [
            name for name, job in self.jobs.items()
            if any(
                isinstance(s.get("uses"), str) and s["uses"].startswith("actions/create-github-app-token")
                for s in job["steps"]
            )
        ]
        self.assertEqual(minters, [])

    def test_no_job_references_app_secrets_or_token(self) -> None:
        for name in ("release-gate", "package"):
            blob = yaml.safe_dump(self.jobs[name])
            self.assertNotIn("RELEASE_APP", blob, name)
            self.assertNotIn("app-token", blob, name)

    def test_no_job_is_behind_the_release_environment(self) -> None:
        gated = [name for name, job in self.jobs.items() if job.get("environment")]
        self.assertEqual(gated, [])


class AssessJobReleaseIntentTests(unittest.TestCase):
    """The required `release-gate` check takes CHANGELOG coverage from the
    PR description's release intent; contributor text reaches the script
    through env only."""

    CONTRIBUTOR_TEXT = (
        "github.event.pull_request.body",
        "github.event.pull_request.title",
        "github.event.pull_request.head.ref",
        "github.head_ref",
    )

    def setUp(self) -> None:
        self.data = _load()
        self.steps = self.data["jobs"]["release-gate"]["steps"]
        self.step = _step(self.steps, "Classify change set and enforce release intent")

    def test_description_edits_rerun_the_check(self) -> None:
        types = _on(self.data)["pull_request"]["types"]
        for event in ("opened", "synchronize", "reopened", "edited"):
            self.assertIn(event, types)

    def test_pr_body_reaches_the_script_through_env_only(self) -> None:
        self.assertEqual(self.step["env"]["PR_BODY"], "${{ github.event.pull_request.body }}")
        run = self.step["run"]
        self.assertIn("--pr-body-env PR_BODY", run)
        self.assertIn("--require-release-intent", run)
        self.assertIn('--step-summary "$GITHUB_STEP_SUMMARY"', run)

    def test_intent_is_enforced_on_pull_requests_only(self) -> None:
        self.assertEqual(self.step["env"]["EVENT_NAME"], "${{ github.event_name }}")
        self.assertIn('if [ "${EVENT_NAME}" = "pull_request" ]', self.step["run"])

    def test_no_run_step_interpolates_contributor_text(self) -> None:
        for name, job in self.data["jobs"].items():
            for step in job["steps"]:
                run = str(step.get("run", ""))
                for expr in self.CONTRIBUTOR_TEXT:
                    self.assertNotIn(expr, run, f"{name}: {step.get('name')}")

    def test_coverage_no_longer_comes_from_a_changelog_edit(self) -> None:
        blob = yaml.safe_dump(self.data["jobs"]["release-gate"])
        self.assertNotIn("classify-semver", blob)
        self.assertNotIn("--require-changelog", blob)


class ExtractedHelperWiringTests(unittest.TestCase):
    """Reusable shell logic lives in tested helpers; the YAML only wires
    inputs to outputs."""

    def setUp(self) -> None:
        self.jobs = _load()["jobs"]
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_subcommand_step_runs_after_checkout_and_python_setup(self) -> None:
        steps = self.jobs["release-gate"]["steps"]
        call = _step_index(steps, "Determine base ref")
        checkout = _step_index(steps, "actions/checkout")
        setup_python = _step_index(steps, "actions/setup-python")
        self.assertLess(checkout, call)
        self.assertLess(setup_python, call)

    def test_release_gate_base_ref_comes_from_the_resolve_base_ref_subcommand(self) -> None:
        step = _step(self.jobs["release-gate"]["steps"], "Determine base ref")
        self.assertEqual(step.get("id"), "base")
        run = step["run"]
        self.assertIn("release_worthiness.py resolve-base-ref", run)
        self.assertIn('--event-name "${{ github.event_name }}"', run)
        self.assertIn('--pr-base-ref "${{ github.event.pull_request.base.ref }}"', run)
        self.assertIn('--pr-base-sha "${{ github.event.pull_request.base.sha }}"', run)
        self.assertNotIn("git describe", self.raw)

    def test_release_gate_fetches_the_pr_base_branch_before_resolving_the_base_ref(self) -> None:
        steps = self.jobs["release-gate"]["steps"]
        fetch = _step(steps, "Fetch the PR base branch")
        self.assertEqual(fetch["if"], "github.event_name == 'pull_request'")
        self.assertIn("git fetch", fetch["run"])
        self.assertIn("refs/remotes/origin/${{ github.event.pull_request.base.ref }}", fetch["run"])
        checkout = _step_index(steps, "actions/checkout")
        self.assertLess(checkout, _step_index(steps, "Fetch the PR base branch"))
        self.assertLess(_step_index(steps, "Fetch the PR base branch"), _step_index(steps, "Determine base ref"))

    def test_classify_step_passes_the_resolved_base_ref_unconditionally(self) -> None:
        step = _step(self.jobs["release-gate"]["steps"], "Classify change set and enforce release intent")
        run = step["run"]
        self.assertIn('--base-ref "${{ steps.base.outputs.ref }}"', run)
        self.assertNotIn('args="', run)

    def test_package_builds_archives_through_the_shared_helper(self) -> None:
        helper = "scripts/release/verify-skill-archives.sh"
        self.assertTrue((REPO_ROOT / helper).is_file())
        build = _step(self.jobs["package"]["steps"], "Build and verify Skill")
        self.assertIn(helper, build["run"])
        self.assertNotIn("unzip -t", self.raw)
        self.assertNotIn("scripts/package-skills.sh all", self.raw)


class RequiredReleaseGateTests(unittest.TestCase):
    """The required, always-created PR check (issue #241): `release-gate`
    is a stable job identity, decoupled from the conditional `package`
    (archive build/verify/upload) work, and always resolves — release-worthy
    or not."""

    def setUp(self) -> None:
        self.data = _load()
        self.jobs = self.data["jobs"]
        self.gate = self.jobs["release-gate"]
        self.package = self.jobs["package"]

    def test_release_gate_job_exists_with_a_stable_name(self) -> None:
        self.assertIn("release-gate", self.jobs)
        self.assertNotIn("name", self.gate)  # job id is the check context

    def test_release_gate_never_builds_or_uploads_packaging_artifacts(self) -> None:
        blob = yaml.safe_dump(self.gate)
        self.assertNotIn("verify-skill-archives.sh", blob)
        self.assertNotIn("upload-artifact", blob)
        self.assertNotIn("packaging", blob)

    def test_release_gate_exposes_release_worthy_for_downstream_jobs(self) -> None:
        self.assertEqual(
            self.gate["outputs"]["release_worthy"], "${{ steps.classify.outputs.release_worthy }}"
        )

    def test_package_job_only_runs_when_release_gate_says_release_worthy(self) -> None:
        self.assertEqual(self.package["needs"], "release-gate")
        self.assertEqual(
            str(self.package["if"]).strip(), "needs.release-gate.outputs.release_worthy == 'true'"
        )

    def test_package_job_is_not_named_in_the_required_status_checks_doc_contract(self) -> None:
        self.assertNotIn("paths:", WORKFLOW.read_text(encoding="utf-8"))


class SupportingArtifactsTests(unittest.TestCase):
    def test_classifier_script_present_with_shebang(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(SCRIPT.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3"))

    def test_release_doc_referenced_from_contributing_and_pr_template(self) -> None:
        self.assertTrue(RELEASE_DOC.is_file())
        contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("docs/RELEASE.md", contributing)
        pr_template = (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
        self.assertIn("Changelog:", pr_template)


if __name__ == "__main__":
    unittest.main()
