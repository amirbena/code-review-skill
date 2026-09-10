#!/usr/bin/env python3
"""Safety and ordering contract for the Release worthiness automation.

Non-publish jobs stay read-only and never touch the release App
credentials. The read-only `plan` job derives the version with
`auto-release-plan` — there is no workflow version input — and the
`publish` job runs only when `plan` reports `should_release == 'true'`, so
a merge that ships nothing releasable never starts a write-capable job or
the `release` Environment gate. `publish` is the only job with
contents: write and the only one that mints the trusted release App
token; the workflow never uses pull_request_target and cannot recurse.
`publish` runs its steps in the order preflight → changelog →
build/verify → commit(main) → push(main) → verify-main → tag → push-tag →
publish-release → verify-release, with the tag and published assets bound
to the pushed main commit SHA.
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

    def test_parses_and_has_expected_triggers(self) -> None:
        on = _on(self.data)
        self.assertIn("pull_request", on)
        self.assertIn("push", on)
        self.assertIn("workflow_dispatch", on)

    def test_no_pull_request_target(self) -> None:
        self.assertNotIn("pull_request_target", _on(self.data))
        self.assertNotIn("pull_request_target:", self.raw)

    def test_workflow_dispatch_takes_no_version_input(self) -> None:
        dispatch = _on(self.data)["workflow_dispatch"]
        self.assertIn(dispatch, (None, {}))
        self.assertNotIn("inputs.version", self.raw)

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

    def test_plan_is_read_only_and_no_persisted_creds(self) -> None:
        plan = self.jobs["plan"]
        self.assertEqual(plan["permissions"], {"contents": "read"})
        checkout = next(
            s for s in plan["steps"]
            if isinstance(s.get("uses"), str) and s["uses"].startswith("actions/checkout")
        )
        self.assertIs(checkout["with"]["persist-credentials"], False)

    def test_only_publish_job_has_write(self) -> None:
        writers = [
            name for name, job in self.jobs.items()
            if (job.get("permissions") or {}).get("contents") == "write"
        ]
        self.assertEqual(writers, ["publish"])

    def test_only_publish_job_mints_the_app_token(self) -> None:
        minters = [
            name for name, job in self.jobs.items()
            if any(
                isinstance(s.get("uses"), str) and s["uses"].startswith("actions/create-github-app-token")
                for s in job["steps"]
            )
        ]
        self.assertEqual(minters, ["publish"])

    def test_non_publish_jobs_never_reference_app_secrets_or_token(self) -> None:
        for name in ("assess", "plan"):
            blob = yaml.safe_dump(self.jobs[name])
            self.assertNotIn("RELEASE_APP", blob, name)
            self.assertNotIn("app-token", blob, name)

    def test_only_publish_job_is_behind_the_release_environment(self) -> None:
        gated = [name for name, job in self.jobs.items() if job.get("environment")]
        self.assertEqual(gated, ["publish"])


class PlanJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = _load()["jobs"]["plan"]
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_runs_only_on_trusted_main_or_manual_dispatch(self) -> None:
        cond = self.plan["if"]
        self.assertIn("github.event_name == 'workflow_dispatch'", cond)
        self.assertIn("github.event_name == 'push'", cond)
        self.assertIn("github.ref == 'refs/heads/main'", cond)
        self.assertIn("[skip ci]", cond)
        self.assertNotIn("pull_request", cond)

    def test_version_is_planned_not_supplied(self) -> None:
        step = _step(self.plan["steps"], "Plan the release")
        self.assertEqual(step.get("id"), "plan")
        self.assertIn("auto-release-plan", step["run"])
        self.assertNotIn("inputs.version", yaml.safe_dump(self.plan))

    def test_exposes_plan_outputs_for_publish(self) -> None:
        outputs = self.plan["outputs"]
        for key in ("should_release", "version", "impact", "baseline"):
            self.assertIn(key, outputs)
            self.assertIn("steps.plan.outputs.", outputs[key])


class PublishJobGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.jobs = _load()["jobs"]
        self.publish = self.jobs["publish"]
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_runs_only_after_plan_says_release(self) -> None:
        self.assertEqual(self.publish["needs"], "plan")
        self.assertEqual(
            str(self.publish["if"]).strip(),
            "needs.plan.outputs.should_release == 'true'",
        )

    def test_assess_excludes_dispatch_and_skip_ci_commits(self) -> None:
        assess_if = self.jobs["assess"]["if"]
        self.assertIn("github.event_name != 'workflow_dispatch'", assess_if)
        self.assertIn("[skip ci]", assess_if)

    def test_requires_app_credentials_before_doing_anything(self) -> None:
        steps = self.publish["steps"]
        guard = _step_index(steps, "Require trusted release App credentials")
        mint = _step_index(steps, "create-github-app-token")
        self.assertLess(guard, mint)

    def test_release_commit_is_skip_ci(self) -> None:
        self.assertIn(
            "chore(release): v${{ needs.plan.outputs.version }} [skip ci]", self.raw
        )

    def test_serialized_by_a_release_publish_concurrency_group(self) -> None:
        self.assertEqual(self.publish["concurrency"]["group"], "release-publish")
        self.assertIs(self.publish["concurrency"]["cancel-in-progress"], False)

    def test_protected_mutations_use_the_app_token_not_github_token(self) -> None:
        steps = self.publish["steps"]
        checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
        self.assertEqual(checkout["with"]["token"], "${{ steps.app-token.outputs.token }}")
        for name in ("Publish the GitHub Release", "Verify the live tag"):
            step = _step(steps, name)
            self.assertEqual(step["env"]["GH_TOKEN"], "${{ steps.app-token.outputs.token }}")
        self.assertNotIn("GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}", self.raw)

    def test_release_doc_documents_the_bypass_and_automation_model(self) -> None:
        doc = RELEASE_DOC.read_text(encoding="utf-8")
        self.assertIn("ruleset", doc.lower())
        self.assertIn("GitHub App", doc)
        self.assertIn("RELEASE_APP_ID", doc)
        self.assertIn("RELEASE_APP_PRIVATE_KEY", doc)
        self.assertIn("cannot", doc)  # GITHUB_TOKEN cannot be a bypass actor
        self.assertIn("auto-release-plan", doc)
        self.assertIn("migration", doc.lower())


class PublishFlowOrderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.steps = _load()["jobs"]["publish"]["steps"]

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

    def test_preflight_uses_the_planned_version_and_baseline(self) -> None:
        preflight = _step(self.steps, "Preflight")
        self.assertIn("release-preflight", preflight["run"])
        self.assertIn('--version "${{ needs.plan.outputs.version }}"', preflight["run"])
        self.assertIn('--base-ref "${{ needs.plan.outputs.baseline }}"', preflight["run"])

    def test_archives_are_built_from_the_tree_that_gets_committed(self) -> None:
        build = _step_index(self.steps, "Build and verify Skill archives")
        commit = _step_index(self.steps, "Commit release preparation to main")
        self.assertLess(build, commit)

    def test_tag_is_created_at_the_captured_release_sha(self) -> None:
        commit_step = _step(self.steps, "Commit release preparation to main")
        self.assertEqual(commit_step.get("id"), "commit")
        self.assertIn('echo "sha=', commit_step["run"])
        tag_step = _step(self.steps, "Create annotated tag")
        self.assertIn("git tag -a", tag_step["run"])
        self.assertIn("${{ steps.commit.outputs.sha }}", tag_step["run"])

    def test_verify_binds_tag_and_assets_to_the_release_sha(self) -> None:
        verify = _step(self.steps, "Verify the live tag")
        run = verify["run"]
        self.assertIn("release-verify", run)
        self.assertIn("--expected-sha \"${{ steps.commit.outputs.sha }}\"", run)
        self.assertIn("--asset local-code-review-skill.zip", run)
        self.assertIn("--asset github-pr-review-skill.zip", run)

    def test_published_release_targets_the_release_sha_with_both_zips(self) -> None:
        publish = _step(self.steps, "Publish the GitHub Release")
        run = publish["run"]
        self.assertIn("--target \"${{ steps.commit.outputs.sha }}\"", run)
        self.assertIn("dist/local-code-review-skill.zip", run)
        self.assertIn("dist/github-pr-review-skill.zip", run)


class AssessJobSemverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.steps = _load()["jobs"]["assess"]["steps"]

    def test_pr_check_classifies_semver_impact_strictly(self) -> None:
        step = _step(self.steps, "Classify proposed SemVer impact")
        self.assertIn("classify-semver", step["run"])
        self.assertIn("--strict", step["run"])
        self.assertEqual(step.get("id"), "semver")

    def test_semver_classification_runs_after_worthiness_classification(self) -> None:
        classify = _step_index(self.steps, "Classify change set and enforce CHANGELOG coverage")
        semver = _step_index(self.steps, "Classify proposed SemVer impact")
        self.assertLess(classify, semver)


class ReleaseCommitAttributionTests(unittest.TestCase):
    """The release commit is attributed to the GitHub App that authenticated
    the protected push — resolved at run time, never a hard-coded slug.

    The resolution logic itself (``<slug>[bot]`` → GitHub user id → canonical
    noreply email, failing closed on an unresolved slug or non-numeric id)
    lives in ``release_lib.commands.workflow`` and is covered by
    ``tests/unit/test_release_worthiness.py``; here we only pin the workflow
    wiring."""

    def setUp(self) -> None:
        self.steps = _load()["jobs"]["publish"]["steps"]
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_no_hard_coded_release_automation_bot_identity(self) -> None:
        self.assertNotIn("release-automation[bot]", self.raw)
        self.assertNotIn("release-automation", self.raw)

    def test_identity_is_resolved_from_the_minted_app_token(self) -> None:
        step = _step(self.steps, "Resolve the authenticated release App bot identity")
        self.assertEqual(step.get("id"), "bot-identity")
        self.assertEqual(step["env"]["GH_TOKEN"], "${{ steps.app-token.outputs.token }}")
        run = step["run"]
        # Delegates to the tested helper, keyed by the token's own app-slug,
        # and writes login/email back for the commit step to consume.
        self.assertIn("release_worthiness.py resolve-app-identity", run)
        self.assertIn('--app-slug "${{ steps.app-token.outputs.app-slug }}"', run)
        self.assertIn('--github-output "$GITHUB_OUTPUT"', run)

    def test_resolution_runs_after_minting_and_before_the_release_commit(self) -> None:
        mint = _step_index(self.steps, "create-github-app-token")
        resolve = _step_index(self.steps, "Resolve the authenticated release App bot identity")
        commit = _step_index(self.steps, "Commit release preparation to main")
        self.assertLess(mint, resolve)
        self.assertLess(resolve, commit)

    def test_commit_step_configures_git_from_the_resolved_identity(self) -> None:
        commit = _step(self.steps, "Commit release preparation to main")
        run = commit["run"]
        self.assertIn(
            'git config user.name "${{ steps.bot-identity.outputs.login }}"', run
        )
        self.assertIn(
            'git config user.email "${{ steps.bot-identity.outputs.email }}"', run
        )


class ExtractedHelperWiringTests(unittest.TestCase):
    """Reusable shell logic lives in tested helpers; the YAML only wires
    inputs to outputs. The behaviour of each helper is covered by
    ``tests/unit/test_release_worthiness.py`` (the two subcommands) and by
    the helper script's own executable contract."""

    def setUp(self) -> None:
        self.jobs = _load()["jobs"]
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_assess_base_ref_comes_from_the_resolve_base_ref_subcommand(self) -> None:
        step = _step(self.jobs["assess"]["steps"], "Determine base ref")
        self.assertEqual(step.get("id"), "base")
        run = step["run"]
        self.assertIn("release_worthiness.py resolve-base-ref", run)
        self.assertIn('--event-name "${{ github.event_name }}"', run)
        self.assertIn('--pr-base-sha "${{ github.event.pull_request.base.sha }}"', run)
        # No inline `git describe` / branching left in the workflow.
        self.assertNotIn("git describe", self.raw)

    def test_classify_step_passes_the_resolved_base_ref_unconditionally(self) -> None:
        step = _step(self.jobs["assess"]["steps"], "Classify change set and enforce CHANGELOG coverage")
        run = step["run"]
        self.assertIn('--base-ref "${{ steps.base.outputs.ref }}"', run)
        # The old shell arg-accumulation is gone.
        self.assertNotIn('args="', run)

    def test_both_jobs_build_archives_through_the_shared_helper(self) -> None:
        helper = "scripts/release/verify-skill-archives.sh"
        self.assertTrue((REPO_ROOT / helper).is_file())
        for job in ("assess", "publish"):
            steps = self.jobs[job]["steps"]
            build = _step(steps, "Build and verify Skill")
            self.assertIn(helper, build["run"])
        # No job re-implements the "package then unzip -t every zip" loop.
        self.assertNotIn("unzip -t", self.raw)
        self.assertNotIn("scripts/package-skills.sh all", self.raw)

    def test_helper_declares_it_is_ci_only_with_no_powershell_counterpart(self) -> None:
        text = (REPO_ROOT / "scripts" / "release" / "verify-skill-archives.sh").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/usr/bin/env bash"))
        self.assertIn("CI-only", text)
        self.assertIn("PowerShell", text)


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
