#!/usr/bin/env python3
"""Safety contract for the Release worthiness automation: the workflow stays
read-only where it runs contributor content, only the manual release-prep
job holds contents: write, it never uses pull_request_target, it cannot
loop, and the packaging build/integrity gate is wired to the classifier.
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


class WorkflowTriggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _load()
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_exists_and_parses(self) -> None:
        self.assertTrue(WORKFLOW.is_file())
        self.assertIsInstance(self.data, dict)

    def test_triggers_are_pull_request_push_and_manual(self) -> None:
        on = _on(self.data)
        self.assertIn("pull_request", on)
        self.assertIn("push", on)
        self.assertIn("workflow_dispatch", on)

    def test_never_uses_pull_request_target(self) -> None:
        self.assertNotIn("pull_request_target", _on(self.data))
        self.assertNotIn("pull_request_target:", self.raw)


class PermissionsModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _load()
        self.jobs = self.data["jobs"]

    def test_top_level_permissions_are_read_only(self) -> None:
        self.assertEqual(self.data["permissions"], {"contents": "read"})

    def test_assess_job_is_read_only(self) -> None:
        self.assertEqual(self.jobs["assess"]["permissions"], {"contents": "read"})

    def test_only_release_prep_has_contents_write(self) -> None:
        writers = [
            name
            for name, job in self.jobs.items()
            if (job.get("permissions") or {}).get("contents") == "write"
        ]
        self.assertEqual(writers, ["release-prep"])

    def test_assess_does_not_persist_credentials(self) -> None:
        checkout = next(
            step
            for step in self.jobs["assess"]["steps"]
            if isinstance(step.get("uses"), str) and step["uses"].startswith("actions/checkout")
        )
        self.assertEqual(checkout["with"]["persist-credentials"], False)


class JobGatingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = _load()["jobs"]

    def test_assess_skips_manual_dispatch(self) -> None:
        self.assertIn("github.event_name != 'workflow_dispatch'", self.jobs["assess"]["if"])

    def test_release_prep_is_manual_only(self) -> None:
        self.assertIn("github.event_name == 'workflow_dispatch'", self.jobs["release-prep"]["if"])

    def test_release_prep_cannot_loop_the_workflow(self) -> None:
        raw = WORKFLOW.read_text(encoding="utf-8")
        # Pushes a release-prep branch (push trigger is main-only) with a
        # [skip ci] commit — no path back into this workflow.
        self.assertIn("release-prep/v", raw)
        self.assertIn("[skip ci]", raw)
        push = _load()["jobs"]["release-prep"]
        steps_text = yaml.safe_dump(push["steps"])
        self.assertNotIn("git push --set-upstream origin main", steps_text)
        self.assertNotIn("git push origin HEAD:main", steps_text)


class PackagingGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assess_steps = _load()["jobs"]["assess"]["steps"]
        self.text = yaml.safe_dump(self.assess_steps)

    def test_changelog_enforcement_uses_require_flag(self) -> None:
        self.assertIn("--require-changelog", self.text)
        self.assertIn("release_worthiness.py", self.text)

    def test_package_build_is_gated_on_classifier_output(self) -> None:
        build = next(
            s for s in self.assess_steps if s.get("run", "").strip().startswith("./scripts/package-skills.sh")
        )
        self.assertEqual(build["if"], "steps.classify.outputs.release_worthy == 'true'")

    def test_integrity_verification_is_gated_and_present(self) -> None:
        verify = next(s for s in self.assess_steps if s.get("name") == "Verify package integrity")
        self.assertEqual(verify["if"], "steps.classify.outputs.release_worthy == 'true'")
        self.assertIn("unzip -t", verify["run"])
        self.assertIn("test_packaging_runtime_boundary", verify["run"])


class SupportingArtifactsTests(unittest.TestCase):
    def test_classifier_script_present_with_shebang(self) -> None:
        self.assertTrue(SCRIPT.is_file())
        self.assertTrue(SCRIPT.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3"))

    def test_release_doc_present_and_referenced(self) -> None:
        self.assertTrue(RELEASE_DOC.is_file())
        contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("docs/RELEASE.md", contributing)
        pr_template = (REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
        self.assertIn("Changelog:", pr_template)


if __name__ == "__main__":
    unittest.main()
