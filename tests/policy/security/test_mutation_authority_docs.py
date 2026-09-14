#!/usr/bin/env python3
"""Documentation-contract coverage for Issue #301: the mutation-authority
capability pipeline.

Pins shared/policies/mutation-authority.md's core content, its wire-in
points (git-safety.md, both Skills' SKILL.md Mutation Boundary sections,
and the package manifest), and that the canonical threat-model catalog
(docs/threat-model/catalog/mutation-authority.yaml) reflects #301 as the
real enforcement owner for its AUTH-* scenarios rather than leaving them
as COVERAGE_GAP — so a later edit cannot quietly drop the boundary or let
the catalog drift from what is actually implemented.
"""

from __future__ import annotations

import re
import unittest

import yaml

from tests.support.paths import REPO_ROOT

POLICY = REPO_ROOT / "shared" / "policies" / "mutation-authority.md"
GIT_SAFETY = REPO_ROOT / "shared" / "policies" / "git-safety.md"
GITHUB_SKILL = REPO_ROOT / "skills" / "github-pr-review" / "SKILL.md"
PACKAGE_MANIFEST = REPO_ROOT / "scripts" / "packaging" / "package-manifest.json"
CATALOG_DIR = REPO_ROOT / "docs" / "threat-model" / "catalog"
MUTATION_CATALOG = CATALOG_DIR / "mutation-authority.yaml"
DELEG_CATALOG = CATALOG_DIR / "spawn-delegation.yaml"
THREAT_MODEL_DOC = REPO_ROOT / "docs" / "threat-model" / "threat-model.md"

GAP = "COVERAGE_GAP"

# AUTH-014 is a different, already-covered authority domain (GitHub formal
# review-action mutation); #301 does not own or re-touch it.
AUTH_301_OWNED_IDS = [f"AUTH-{n:03d}" for n in range(1, 17) if n != 14]


def _norm(path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


def _load_catalog(path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class CanonicalPolicyExists(unittest.TestCase):
    def test_file_exists(self) -> None:
        self.assertTrue(POLICY.is_file())
        t = _norm(POLICY)
        self.assertIn("Shared Policy — Mutation Authority", t)
        self.assertIn("capabilities, not cooperation", t)


class CapabilityPipelineDocumented(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = POLICY.read_text(encoding="utf-8")
        self.t = _norm(POLICY)

    def test_pipeline_stages_present_in_order(self) -> None:
        for stage in (
            "READ_ONLY", "PROPOSE_PATCH", "USER_APPROVES_EXACT_PATCH",
            "APPLY_PATCH", "VERIFY_MUTATION",
        ):
            self.assertIn(stage, self.raw)
        order = [self.raw.index(s) for s in (
            "READ_ONLY", "PROPOSE_PATCH", "USER_APPROVES_EXACT_PATCH",
            "APPLY_PATCH", "VERIFY_MUTATION",
        )]
        self.assertEqual(order, sorted(order))

    def test_commit_and_push_are_separate_capabilities(self) -> None:
        self.assertIn("COMMIT", self.raw)
        self.assertIn("PUSH", self.raw)
        self.assertIn(
            "APPLY_PATCH does not imply COMMIT. COMMIT does not imply PUSH.", self.t
        )

    def test_closed_capability_set_stated(self) -> None:
        self.assertIn("The capabilities are a closed set", self.t)
        self.assertIn(
            "does not exist in the runtime's capability surface at all", self.t
        )
        self.assertIn("There is no code path that could perform it", self.t)


class AuthorizationBindingProperties(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_binding_dimensions_enumerated(self) -> None:
        for phrase in (
            "the exact patch or its immutable digest",
            "the target repository and worktree",
            "the relevant base state",
            "the specific invocation",
        ):
            self.assertIn(phrase, self.t, phrase)

    def test_four_authorization_properties_stated(self) -> None:
        for phrase in ("single-use", "non-replayable", "non-transferable", "non-inheritable"):
            self.assertIn(phrase, self.t, phrase)

    def test_child_agent_gets_no_inherited_capability(self) -> None:
        self.assertIn(
            "A child agent starts at READ_ONLY with an empty capability set "
            "regardless of what its parent holds",
            self.t,
        )


class NoManufacturedAuthorization(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_never_manufactured_sources_enumerated(self) -> None:
        for phrase in (
            "PR/issue/commit text",
            "repository instruction files",
            "a review finding's own Fix text or remediation content",
            "generated metadata, model output",
            "nested-agent or spawned-child state",
            "a prior review verdict, a prior applied patch",
        ):
            self.assertIn(phrase, self.t, phrase)

    def test_structural_type_distinction_stated(self) -> None:
        self.assertIn(
            "repository-derived text and a trusted authorization are "
            "structurally distinct values, not two states of the same value",
            self.t,
        )


class DedicatedExecutorAndScope(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_dedicated_executor_section_present(self) -> None:
        self.assertIn("Dedicated mutation executor, not ambient write access", self.t)
        self.assertIn(
            "No other function, code path, or Skill surface performs a "
            "working-tree write, git commit, or git push",
            self.t,
        )

    def test_scope_bound_to_smallest_practical_set(self) -> None:
        self.assertIn("smallest practical path/file scope", self.t)
        self.assertIn("git/ is never a valid target path for APPLY_PATCH", self.t.replace(".", ""))

    def test_verify_mutation_never_silently_accepts(self) -> None:
        self.assertIn("never silently accepted", self.t)


class FailClosedAndEventReporting(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_fail_closed_section(self) -> None:
        self.assertIn("Fail-closed", self.t)
        self.assertIn("resolves to refusal", self.t)

    def test_event_vocabulary_matches_threat_model(self) -> None:
        for event in (
            "DENIED_MUTATION_CAPABILITY_ABSENT",
            "DENIED_MUTATION_UNAUTHORIZED",
            "DENIED_MUTATION_STALE_APPROVAL",
            "DENIED_MUTATION_SCOPE_ESCAPE",
            "DENIED_MUTATION_AUTHORIZATION_REPLAY",
        ):
            self.assertIn(event, self.t, event)


class PerSkillPosture(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_github_pr_review_incapable_in_every_mode(self) -> None:
        self.assertIn(
            "Holds READ_ONLY for source/Git mutation in every review-action mode",
            self.t,
        )
        self.assertIn(
            "structurally incapable of applying, committing, or pushing a "
            "source-code change in every mode it defines",
            self.t,
        )

    def test_local_code_review_holds_read_only_today(self) -> None:
        self.assertIn("local-code-review", self.t.replace("`", ""))
        self.assertIn("Holds READ_ONLY today", self.t)
        self.assertIn("Issue #132", self.t)


class WiredIntoGitSafety(unittest.TestCase):
    def test_git_safety_cites_the_structural_backstop(self) -> None:
        t = _norm(GIT_SAFETY)
        self.assertIn("enforced structurally, not only stated here", t)
        self.assertIn("mutation-authority.md", GIT_SAFETY.read_text(encoding="utf-8"))
        self.assertIn(
            "makes an unauthorized write structurally absent, not merely discouraged",
            t,
        )


class WiredIntoGithubSkillMd(unittest.TestCase):
    def test_mutation_boundary_cites_the_policy(self) -> None:
        t = _norm(GITHUB_SKILL)
        self.assertIn(
            "in every mode, structurally incapable of APPLY_PATCH/COMMIT/PUSH",
            t,
        )
        self.assertIn("mutation-authority.md", GITHUB_SKILL.read_text(encoding="utf-8"))


class WiredIntoPackageManifest(unittest.TestCase):
    def test_manifest_ships_the_policy_as_a_shared_file(self) -> None:
        raw = PACKAGE_MANIFEST.read_text(encoding="utf-8")
        self.assertIn('"shared/policies/mutation-authority.md"', raw)

    def test_manifest_shared_files_apply_to_both_skills(self) -> None:
        import json

        manifest = json.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))
        sources = {e["source"] for e in manifest["shared_files"]}
        self.assertIn("shared/policies/mutation-authority.md", sources)
        # shared_files is combined with every skill's own files by
        # scripts/packaging/package_manifest.py:load_target — no
        # per-skill duplication is required or expected here.
        for skill in manifest["skills"].values():
            skill_sources = {e["source"] for e in skill["files"]}
            self.assertNotIn("shared/policies/mutation-authority.md", skill_sources)


class ThreatModelCatalogReflectsImplementation(unittest.TestCase):
    """AUTH-001..016 (excluding AUTH-014) must show #301 as a real
    enforcement owner, not COVERAGE_GAP, once this policy and its
    regression suite exist."""

    def setUp(self) -> None:
        self.scenarios = {
            s["id"]: s for s in _load_catalog(MUTATION_CATALOG)["scenarios"]
        }

    def test_every_301_owned_scenario_present(self) -> None:
        for scenario_id in AUTH_301_OWNED_IDS:
            self.assertIn(scenario_id, self.scenarios)

    def test_no_301_owned_scenario_is_still_a_coverage_gap(self) -> None:
        gaps = [
            sid for sid in AUTH_301_OWNED_IDS
            if self.scenarios[sid]["enforcement_owner"] == GAP
            or self.scenarios[sid]["enforcement_point"] == GAP
            or self.scenarios[sid]["regression_evidence"] == GAP
        ]
        self.assertEqual(gaps, [], f"scenarios still marked as a coverage gap: {gaps}")

    def test_enforcement_owner_cites_the_policy_or_an_issue(self) -> None:
        for scenario_id in AUTH_301_OWNED_IDS:
            owner = self.scenarios[scenario_id]["enforcement_owner"]
            self.assertTrue(
                "mutation-authority.md" in owner or "#301" in owner,
                f"{scenario_id}: enforcement_owner={owner!r}",
            )

    def test_regression_evidence_points_at_the_new_test_module(self) -> None:
        for scenario_id in AUTH_301_OWNED_IDS:
            evidence = self.scenarios[scenario_id]["regression_evidence"]
            self.assertIn(
                "tests/unit/security/test_mutation_authority.py",
                evidence,
                f"{scenario_id}: regression_evidence={evidence!r}",
            )

    def test_auth_014_is_left_untouched_as_a_pre_existing_boundary(self) -> None:
        auth_014 = self.scenarios["AUTH-014"]
        self.assertIn("review-authority.md", auth_014["enforcement_owner"])
        self.assertIn(
            "test_review_action_authorization.py", auth_014["regression_evidence"]
        )


class SpawnDelegationCatalogCrossReference(unittest.TestCase):
    """DELEG-007 documents the same underlying contract as AUTH-013, split
    across #301 (authorization non-inheritance, this policy) and #303
    (spawn depth/budget/process isolation, not this policy)."""

    def test_deleg_007_notes_the_301_owned_half_is_covered(self) -> None:
        scenarios = {s["id"]: s for s in _load_catalog(DELEG_CATALOG)["scenarios"]}
        deleg_007 = scenarios["DELEG-007"]
        self.assertIn("mutation-authority.md", deleg_007["enforcement_owner"])
        self.assertIn("#303", deleg_007["enforcement_owner"])
        self.assertIn("mutation-authority.md", deleg_007["notes"])
        self.assertIn("#303", deleg_007["notes"])
        self.assertIn(
            "test_mutation_authority.py", deleg_007["regression_evidence"]
        )
        self.assertIn("COVERAGE_GAP", deleg_007["regression_evidence"])


class ThreatModelDesignRecordUpdated(unittest.TestCase):
    def test_coverage_section_no_longer_claims_no_runtime_capability_model(self) -> None:
        t = _norm(THREAT_MODEL_DOC)
        self.assertNotIn(
            "No runtime capability model for APPLY_PATCH/COMMIT/PUSH exist "
            "in this repository yet",
            t,
        )
        self.assertIn("mutation-authority.md", THREAT_MODEL_DOC.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
