#!/usr/bin/env python3
"""Safety and ordering contract for the Release worthiness automation.

Non-release jobs stay read-only; only the manual `release` job holds
contents: write and only it can mint the trusted release App token; the
workflow never uses pull_request_target and cannot recurse; and the
direct-to-main release job runs its steps in the order
preflight → changelog → build/verify → commit(main) → push(main) →
verify-main → tag → push-tag → publish-release → verify-release, with the
tag and the published assets both bound to the pushed main commit SHA.
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


class TriggerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _load()
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_parses_and_has_expected_triggers(self) -> None:
        on = _on(self.data)
        self.assertIn("pull_request", on)
        self.assertIn("push", on)
        self.assertIn("workflow_dispatch", on)

    def test_no_pull_request_target(self) -> None:
        self.assertNotIn("pull_request_target", _on(self.data))
        self.assertNotIn("pull_request_target:", self.raw)

    def test_cannot_recurse_on_tags_or_releases(self) -> None:
        on = _on(self.data)
        # No release event, and push is branch-scoped only (no tags:).
        self.assertNotIn("release", on)
        self.assertEqual(list(on["push"].keys()), ["branches"])
        self.assertEqual(on["push"]["branches"], ["main"])


class PermissionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = _load()
        self.jobs = self.data["jobs"]

    def test_top_level_read_only(self) -> None:
        self.assertEqual(self.data["permissions"], {"contents": "read"})

    def test_assess_is_read_only_and_no_persisted_creds(self) -> None:
        assess = self.jobs["assess"]
        self.assertEqual(assess["permissions"], {"contents": "read"})
        checkout = next(
            s for s in assess["steps"]
            if isinstance(s.get("uses"), str) and s["uses"].startswith("actions/checkout")
        )
        self.assertIs(checkout["with"]["persist-credentials"], False)

    def test_only_release_job_has_write(self) -> None:
        writers = [
            name for name, job in self.jobs.items()
            if (job.get("permissions") or {}).get("contents") == "write"
        ]
        self.assertEqual(writers, ["release"])

    def test_only_release_job_mints_the_app_token(self) -> None:
        minters = [
            name for name, job in self.jobs.items()
            if any(
                isinstance(s.get("uses"), str) and s["uses"].startswith("actions/create-github-app-token")
                for s in job["steps"]
            )
        ]
        self.assertEqual(minters, ["release"])

    def test_assess_never_references_app_secrets_or_token(self) -> None:
        assess_blob = yaml.safe_dump(self.jobs["assess"])
        self.assertNotIn("RELEASE_APP", assess_blob)
        self.assertNotIn("app-token", assess_blob)


class ReleaseJobGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.release = _load()["jobs"]["release"]
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_dispatch_only(self) -> None:
        self.assertIn("github.event_name == 'workflow_dispatch'", self.release["if"])

    def test_assess_excludes_dispatch_and_skip_ci_commits(self) -> None:
        assess_if = _load()["jobs"]["assess"]["if"]
        self.assertIn("github.event_name != 'workflow_dispatch'", assess_if)
        self.assertIn("[skip ci]", assess_if)

    def test_requires_app_credentials_before_doing_anything(self) -> None:
        steps = self.release["steps"]
        guard = _step_index(steps, "Require trusted release App credentials")
        mint = _step_index(steps, "create-github-app-token")
        self.assertLess(guard, mint)

    def test_release_commit_is_skip_ci(self) -> None:
        self.assertIn("chore(release): v${{ inputs.version }} [skip ci]", self.raw)

    def test_protected_mutations_use_the_app_token_not_github_token(self) -> None:
        steps = self.release["steps"]
        checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
        self.assertEqual(checkout["with"]["token"], "${{ steps.app-token.outputs.token }}")
        for name in ("Publish the GitHub Release", "Verify the live tag"):
            step = steps[_step_index(steps, name)]
            self.assertEqual(step["env"]["GH_TOKEN"], "${{ steps.app-token.outputs.token }}")
        self.assertNotIn("GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}", self.raw)

    def test_release_doc_documents_the_bypass_model(self) -> None:
        doc = RELEASE_DOC.read_text(encoding="utf-8")
        self.assertIn("ruleset", doc.lower())
        self.assertIn("GitHub App", doc)
        self.assertIn("RELEASE_APP_ID", doc)
        self.assertIn("RELEASE_APP_PRIVATE_KEY", doc)
        self.assertIn("cannot", doc)  # GITHUB_TOKEN cannot be a bypass actor


class ReleaseFlowOrderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.steps = _load()["jobs"]["release"]["steps"]

    def test_direct_to_main_then_tag_then_release(self) -> None:
        order = [
            "Preflight",
            "Roll CHANGELOG Unreleased",
            "Build and verify Skill archives",
            "Commit release preparation to main",
            "Push to main",
            "Verify main advanced",
            "Create annotated tag",
            "Push the tag",
            "Publish the GitHub Release",
            "Verify the live tag",
        ]
        indices = [_step_index(self.steps, needle) for needle in order]
        self.assertEqual(indices, sorted(indices), f"steps out of order: {indices}")

    def test_archives_are_built_from_the_tree_that_gets_committed(self) -> None:
        build = _step_index(self.steps, "Build and verify Skill archives")
        commit = _step_index(self.steps, "Commit release preparation to main")
        self.assertLess(build, commit)

    def test_tag_is_created_at_the_captured_release_sha(self) -> None:
        commit_step = self.steps[_step_index(self.steps, "Commit release preparation to main")]
        self.assertEqual(commit_step.get("id"), "commit")
        self.assertIn('echo "sha=', commit_step["run"])
        tag_step = self.steps[_step_index(self.steps, "Create annotated tag")]
        self.assertIn("git tag -a", tag_step["run"])
        self.assertIn("${{ steps.commit.outputs.sha }}", tag_step["run"])

    def test_verify_binds_tag_and_assets_to_the_release_sha(self) -> None:
        verify = self.steps[_step_index(self.steps, "Verify the live tag")]
        run = verify["run"]
        self.assertIn("release-verify", run)
        self.assertIn("--expected-sha \"${{ steps.commit.outputs.sha }}\"", run)
        self.assertIn("--asset local-code-review-skill.zip", run)
        self.assertIn("--asset github-pr-review-skill.zip", run)

    def test_published_release_targets_the_release_sha_with_both_zips(self) -> None:
        publish = self.steps[_step_index(self.steps, "Publish the GitHub Release")]
        run = publish["run"]
        self.assertIn("--target \"${{ steps.commit.outputs.sha }}\"", run)
        self.assertIn("dist/local-code-review-skill.zip", run)
        self.assertIn("dist/github-pr-review-skill.zip", run)


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
