#!/usr/bin/env python3
"""Documentation-contract coverage for issue #303: the agent-spawn /
delegation capability boundary.

Pins the canonical policy (shared/policies/agent-delegation.md) and its
wire-in points (the shared policy index, parallel-review.md — shared and
github-pr-review's PR application — github-review.md, both Skills'
SKILL.md, and the packaging manifest) so a later edit cannot quietly drop
the capability boundary or widen the default topology.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

SHARED = REPO_ROOT / "shared" / "policies"
POLICY = SHARED / "agent-delegation.md"
SHARED_README = SHARED / "README.md"
SHARED_PARALLEL = SHARED / "parallel-review.md"
GITHUB = REPO_ROOT / "skills" / "github-pr-review"
GITHUB_INDEX = GITHUB / "policies" / "github-review.md"
GITHUB_PARALLEL = GITHUB / "policies" / "parallel-review.md"
GITHUB_SKILL = GITHUB / "SKILL.md"
LOCAL_SKILL = REPO_ROOT / "skills" / "local-code-review" / "SKILL.md"
PACKAGE_MANIFEST = REPO_ROOT / "scripts" / "packaging" / "package-manifest.json"
CATALOG = REPO_ROOT / "docs" / "threat-model" / "catalog" / "spawn-delegation.yaml"
REFERENCE_MODEL = REPO_ROOT / "tests" / "reference" / "review" / "agent_delegation.py"
REGRESSION_TESTS = REPO_ROOT / "tests" / "unit" / "review" / "delegation" / "test_agent_delegation_authorization.py"


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class CanonicalPolicyExists(unittest.TestCase):
    def test_file_exists(self) -> None:
        self.assertTrue(POLICY.is_file())

    def test_scopes_out_mutation_and_sandbox_execution(self) -> None:
        t = _norm(POLICY)
        self.assertIn("does not implement mutation execution", t)
        self.assertIn("runtime sandboxing (issue #302)", t)


class CoreInvariantStated(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_invariant_formula_present(self) -> None:
        self.assertIn("child_authority", self.t)
        self.assertIn("parent_authority", self.t)
        self.assertIn("explicit_delegation", self.t)

    def test_invariant_prose_present(self) -> None:
        self.assertIn(
            "A childs effective capability set is always a subset of what its "
            "parent actually holds".replace("childs", "child's"),
            self.t,
        )


class SpawnAgentIsExplicitCapability(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_absent_by_default(self) -> None:
        self.assertIn("spawn_agent = absent", self.t)
        self.assertIn(
            "there is no ambient or default-on spawn capability", self.t
        )

    def test_default_topology_is_shallow(self) -> None:
        self.assertIn("review owner", self.t)
        self.assertIn("read-only worker", self.t)
        self.assertIn("explicitly justified path", self.t)


class HardBudgets(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_both_limits_named(self) -> None:
        self.assertIn("max_agents_per_invocation", self.t)
        self.assertIn("max_spawn_depth", self.t)

    def test_one_canonical_tree_wide_accounting_model(self) -> None:
        self.assertIn("One canonical accounting model, tree-wide", self.t)
        self.assertIn(
            "one shared pool for the entire\ninvocation".replace("\n", " "), self.t
        )
        self.assertIn(
            "not a fresh independent allowance handed to each parent", self.t
        )

    def test_budget_exhaustion_fails_closed(self) -> None:
        self.assertIn("Budget exhaustion fails closed", self.t)
        self.assertIn("never resolved by increasing the configured limit", self.t)
        self.assertIn("REVIEW INCOMPLETE", self.t)


class DelegationRule(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_intersection_formula_present(self) -> None:
        self.assertIn("effective_child_capabilities", self.t)
        self.assertIn("parent_capabilities", self.t)
        self.assertIn("explicitly_delegated_capabilities", self.t)
        self.assertIn("runtime_policy", self.t)

    def test_parent_cannot_delegate_what_it_lacks(self) -> None:
        self.assertIn(
            "A parent cannot delegate a\ncapability it does not itself hold".replace(
                "\n", " "
            ),
            self.t,
        )

    def test_copying_state_is_not_delegation(self) -> None:
        self.assertIn(
            "Copying the\nparent's state, token, or orchestration metadata onto a child is never\n"
            "equivalent to, or a substitute for, an explicit delegation grant".replace(
                "\n", " "
            ),
            self.t,
        )

    def test_mutation_and_formal_review_action_are_non_transferable(self) -> None:
        self.assertIn(
            "Mutation and formal review-action authorization are non-transferable",
            self.t,
        )
        self.assertIn(
            "never delegated by default", self.t
        )
        self.assertIn("single-use, narrowly-scoped authorization model", self.t)
        self.assertIn(
            "must not be inherited, copied, forwarded, replayed,\nreconstructed "
            "from orchestration state, or shared between siblings".replace(
                "\n", " "
            ),
            self.t,
        )


class ConfusedDeputyProtection(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_section_exists(self) -> None:
        self.assertIn("Confused-deputy protection", self.t)
        self.assertIn(
            "Capability checks bind to the acting agent's own granted identity",
            self.t,
        )

    def test_siblings_cannot_combine_capabilities(self) -> None:
        self.assertIn(
            "Sibling agents cannot combine their individually-granted capabilities",
            self.t,
        )

    def test_alternate_surfaces_enumerated(self) -> None:
        for phrase in ("a bot", "an\nalternate account".replace("\n", " "), "a subprocess", "a different tool"):
            self.assertIn(phrase, self.t)


class ReadOnlyWorkerCapabilitySet(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_section_exists_and_enumerates_denied_capabilities(self) -> None:
        self.assertIn("Read-only worker capability set", self.t)
        for phrase in (
            "publication",
            "runtime validation execution",
            "code mutation",
            "formal review-action authorization",
            "further",
        ):
            self.assertIn(phrase, self.t)

    def test_denied_action_does_not_discard_valid_findings(self) -> None:
        self.assertIn(
            "a denied action on\none capability does not discard the worker's "
            "otherwise-valid findings".replace("\n", " "),
            self.t,
        )


class WiredIntoSharedIndex(unittest.TestCase):
    def test_readme_lists_it(self) -> None:
        raw = SHARED_README.read_text(encoding="utf-8")
        self.assertIn("agent-delegation.md", raw)
        self.assertIn("parallel-review.md", raw)

    def test_parallel_review_references_it_in_worker_contract_and_boundaries(self) -> None:
        raw = SHARED_PARALLEL.read_text(encoding="utf-8")
        self.assertIn("agent-delegation.md", raw)
        t = _norm(SHARED_PARALLEL)
        self.assertIn("Worker contract", t)
        self.assertIn("No new mutation.", t)


class WiredIntoGithubReviewIndex(unittest.TestCase):
    def test_index_references_the_capability_gate(self) -> None:
        raw = GITHUB_INDEX.read_text(encoding="utf-8")
        self.assertIn("agent-delegation.md", raw)


class WiredIntoGithubParallelReviewApplication(unittest.TestCase):
    def test_boundary_section_references_capability_gate(self) -> None:
        raw = GITHUB_PARALLEL.read_text(encoding="utf-8")
        self.assertIn("agent-delegation.md", raw)
        t = _norm(GITHUB_PARALLEL)
        self.assertIn("hold no", t)
        self.assertIn("max_agents_per_invocation", t)
        self.assertIn("max_spawn_depth", t)


class WiredIntoGithubSkillMd(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = GITHUB_SKILL.read_text(encoding="utf-8")
        self.t = _norm(GITHUB_SKILL)

    def test_safety_boundaries_bullet_present(self) -> None:
        self.assertIn("Agent-spawn capability is absent by default", self.t)

    def test_policy_loading_lists_it(self) -> None:
        self.assertIn("agent-delegation.md", self.raw)

    def test_mutation_boundary_section_references_non_transferability(self) -> None:
        self.assertIn(
            "never transfers\nformal authority".replace("\n", " "), self.t
        )
        self.assertIn(
            "never inherited, copied, forwarded, or replayed\nacross an agent-spawn boundary".replace(
                "\n", " "
            ),
            self.t,
        )


class WiredIntoLocalSkillMd(unittest.TestCase):
    def test_states_no_spawn_agent_capability(self) -> None:
        t = _norm(LOCAL_SKILL)
        self.assertIn("This Skill holds no spawn_agent capability of its own", t)
        self.assertIn("agent-delegation.md", LOCAL_SKILL.read_text(encoding="utf-8"))


class WiredIntoPackageManifest(unittest.TestCase):
    def test_manifest_ships_the_shared_policy(self) -> None:
        raw = PACKAGE_MANIFEST.read_text(encoding="utf-8")
        self.assertIn(
            '"source": "shared/policies/agent-delegation.md"', raw
        )


class ThreatModelCatalogUpdated(unittest.TestCase):
    def test_scenarios_point_at_real_enforcement_and_regression_evidence(self) -> None:
        raw = CATALOG.read_text(encoding="utf-8")
        self.assertIn("shared/policies/agent-delegation.md", raw)
        self.assertIn(str(REGRESSION_TESTS.relative_to(REPO_ROOT)), raw)
        # Every DELEG scenario keeps enforcement_owner '#303'; none regress
        # to COVERAGE_GAP for enforcement_point now that #303 has landed.
        self.assertNotIn("enforcement_point: COVERAGE_GAP", raw)

    def test_reference_model_and_regression_tests_exist(self) -> None:
        self.assertTrue(REFERENCE_MODEL.is_file())
        self.assertTrue(REGRESSION_TESTS.is_file())


if __name__ == "__main__":
    unittest.main()
