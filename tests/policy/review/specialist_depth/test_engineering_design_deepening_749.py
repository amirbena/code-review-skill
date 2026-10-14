#!/usr/bin/env python3
"""Pins the engineering design deepening capability contract (Issue #749).

Design content the reviewed change adds or modifies is reviewed through the
existing specialist-depth activation, with no new engine, severity model,
evidence label, gate, or execution permission. These assertions protect the
cross-document invariants:

1. one canonical shared policy owns the capability and is wired through
   review-scope, the capability manifest, both Skill manifests, and packaging;
2. activation is semantic, never path/extension/title routing;
3. the reviewed change cannot accept its own design; acceptance is per
   statement;
4. a design claim is a claim, never evidence; unverified claims ground nothing;
5. absence is not a finding and never a Context gap;
6. severity, evidence, Context gaps, Reasoning check, and change-risk signals
   are unchanged.
"""

from __future__ import annotations

import json
import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _norm

POLICY = REPO_ROOT / "shared/policies/engineering-design-deepening.md"
NAME = POLICY.name


class EngineeringDesignDeepeningContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_semantic_activation_and_path_negative(self) -> None:
        self.assertIn("defined by what the text does, never by where it lives", self.text)
        self.assertIn("is a signal only — never required, never sufficient", self.text)
        self.assertIn("does not activate this capability", self.text)

    def test_reuses_specialist_depth_activation(self) -> None:
        self.assertIn("reusing [specialist-depth.md](specialist-depth.md)", self.text)
        self.assertIn("explicit user focus", self.text.lower())

    def test_change_cannot_accept_itself(self) -> None:
        self.assertIn("the reviewed change cannot accept its own design", self.text)
        self.assertIn("Acceptance is decided per statement or section, not per file", self.text)
        self.assertIn("A conventional directory name alone does not make a statement accepted", self.text)

    def test_claim_never_evidence_and_unverified_outcome(self) -> None:
        self.assertIn("claim, never evidence", self.text)
        self.assertIn("No finding grounded on the claim", self.text)
        self.assertIn("never states or implies it was verified", self.text)

    def test_missing_information_rule(self) -> None:
        self.assertIn("Absence is not a finding", self.text)
        self.assertIn("Missing information never produces a Context gap", self.text)
        self.assertIn("An acknowledged trade-off is not a defect", self.text)

    def test_api_only_boundary(self) -> None:
        self.assertIn("Reads are limited to changed paths", self.text)
        self.assertIn("a claim about an unchanged file is unverified", self.text)
        self.assertIn("never assumed accepted", self.text)

    def test_no_new_schema_gate_or_severity_text(self) -> None:
        raw = POLICY.read_text(encoding="utf-8")
        self.assertNotIn("## Decision derivation", raw)
        self.assertIn("No new finding/severity/evidence schema", self.text)
        self.assertIn("It adds no design-specific severity guidance", self.text)
        self.assertIn("design review is not design approval", self.text.lower())

    def test_design_only_change_may_block_without_severity_cap(self) -> None:
        self.assertIn("never caps severity by document type", self.text)
        self.assertIn("a design-only change can receive a blocking (P0/P1) finding", self.text)
        self.assertIn(
            "An unsupported assumption, an architectural preference, or a "
            "missing detail is never a blocking finding",
            self.text,
        )

    def test_context_gaps_reasoning_check_change_risk_unchanged(self) -> None:
        self.assertIn(
            "No change to Context gaps, the Reasoning check "
            "([reasoning-checkpoint.md](reasoning-checkpoint.md)), change-risk "
            "signals ([change-risk-signals.md](change-risk-signals.md))",
            self.text,
        )

    def test_capability_provenance_value(self) -> None:
        self.assertIn("valued engineering-design-deepening", self.text)

    def test_worked_examples_design_only_and_mixed(self) -> None:
        for phrase in ("Engages — design-only", "Engages — mixed", "typo-only edit", "unverified claim"):
            with self.subTest(case=phrase):
                self.assertIn(phrase, self.text)

    def test_review_scope_wiring(self) -> None:
        raw = (REPO_ROOT / "shared/policies/review-scope.md").read_text(encoding="utf-8")
        self.assertIn("### Proposed behavior in design content", raw)
        self.assertIn("## Engineering design review", raw)
        self.assertIn(f"[`{NAME[:-3]}.md`]({NAME})", raw)
        self.assertIn("never gates the base obligation", _norm(REPO_ROOT / "shared/policies/review-scope.md"))

    def test_review_context_clarifies_changed_design_is_target(self) -> None:
        t = _norm(REPO_ROOT / "shared/policies/review-context.md")
        self.assertIn("design content (an ADR, HLD, or design doc) that the delta itself changes is part of the review target", t)

    def test_wiring(self) -> None:
        rel = f"shared/policies/{NAME}"
        for path in (
            "shared/policies/README.md",
            "capabilities/specialist-depth/capability.yaml",
            "skills/local-code-review/metadata/skill.yaml",
            "skills/github-pr-review/metadata/skill.yaml",
            "scripts/packaging/generate_package_manifest.py",
        ):
            with self.subTest(path=path):
                self.assertIn(NAME, (REPO_ROOT / path).read_text(encoding="utf-8"))
        manifest = json.loads((REPO_ROOT / "scripts/packaging/package-manifest.json").read_text(encoding="utf-8"))
        self.assertIn(rel, json.dumps(manifest))

    def test_domain_policy_count_updated(self) -> None:
        t = _norm(REPO_ROOT / "shared/policies/specialist-depth.md")
        self.assertIn("the five domain deepening policies", t)
        self.assertNotIn("four domain deepening policies", t)


if __name__ == "__main__":
    unittest.main()
