#!/usr/bin/env python3
"""Documentation-contract checks for the candidate-finding validation model
(Issue #382).

Pins docs/candidate-finding-validation/candidate-finding-validation-model.md,
its navigational README, and its light cross-link wiring into
shared/policies/review-scope.md, evidence.md, severity.md,
repository-expansion.md, architectural-placement.md, and
docs/ARCHITECTURE.md. Structural prose checks in the same style as
test_context_evidence_docs.py -- semantic structure and
whitespace-normalized prose, not brittle exact whitespace.

Run with:
    python3 -m unittest tests.policy.review.root_cause.test_candidate_finding_validation_docs
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

DOCDIR = REPO_ROOT / "docs" / "candidate-finding-validation"
MODEL = DOCDIR / "candidate-finding-validation-model.md"
DIR_README = DOCDIR / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "review" / "candidate_finding_validation.py"
BOUNDARY = REPO_ROOT / "tests" / "integration" / "packaging" / "_shared.py"

REVIEW_SCOPE = REPO_ROOT / "shared" / "policies" / "review-scope.md"
EVIDENCE = REPO_ROOT / "shared" / "policies" / "evidence.md"
SEVERITY = REPO_ROOT / "shared" / "policies" / "severity.md"
REPO_EXPANSION = REPO_ROOT / "shared" / "policies" / "repository-expansion.md"
ARCH_PLACEMENT = REPO_ROOT / "shared" / "policies" / "architectural-placement.md"

GROUNDING_SOURCES = (
    "Explicit requirement",
    "Tests encoding intent",
    "Established production behavior",
    "Technical invariant",
    "Nearby precedent",
    "Local docs",
    "Reviewer inference alone",
)
CLASSIFICATIONS = (
    "proven correctness defect",
    "requirement ambiguity",
    "test-coverage gap",
    "maintainability concern",
)
DISCONFIRMATION_OUTCOMES = ("SURVIVES", "DROPPED", "DOWNGRADED", "RECLASSIFIED")


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class DesignRecordExistsAndCoversScopeTests(unittest.TestCase):
    def test_docs_exist(self) -> None:
        self.assertTrue(MODEL.is_file())
        self.assertTrue(DIR_README.is_file())

    def test_pipeline_stages_are_named(self) -> None:
        t = _norm(MODEL)
        self.assertIn(
            "observation → candidate claim → validated finding → severity", t
        )

    def test_every_grounding_source_appears_in_order(self) -> None:
        t = MODEL.read_text(encoding="utf-8")
        positions = [t.find(name) for name in GROUNDING_SOURCES]
        self.assertNotIn(-1, positions, "a grounding source is missing from the model")
        self.assertEqual(positions, sorted(positions), "grounding hierarchy out of order")

    def test_reviewer_inference_alone_never_establishes_blocking_premise(self) -> None:
        t = _norm(MODEL)
        self.assertIn(
            "reviewer inference alone", t.lower()
        )
        self.assertIn("never alone establishes a blocking premise", t)

    def test_no_ticket_required_for_technical_invariant(self) -> None:
        t = _norm(MODEL)
        self.assertIn("No source in the hierarchy requires a tracker ticket", t)
        self.assertIn("Jira is sufficient, never necessary", t)

    def test_semantic_role_validation_is_conditional_not_universal(self) -> None:
        # #382 follow-up: semantic-role validation gates a candidate only
        # when its own reasoning depends on comparing usages -- it must not
        # read as a universal prerequisite for every candidate.
        t = _norm(MODEL)
        self.assertIn("This gate applies only when", t)
        self.assertIn(
            "depends on comparing two or more usages, paths, or implementations", t
        )
        self.assertIn(
            "does not apply, and is not a prerequisite, for a candidate with", t
        )
        self.assertIn(
            "not a universal prerequisite every candidate must clear", t
        )

    def test_worked_example_1_is_explicitly_not_gated_by_semantic_role(self) -> None:
        t = _norm(MODEL)
        self.assertIn(
            "Semantic-role validation: not applicable", t
        )

    def test_causal_validation_chain_four_links_named(self) -> None:
        t = _norm(MODEL)
        for link in (
            "Reviewed change",
            "Changed state/control-flow/assumption",
            "Concrete failure condition",
            "Observable incorrect result",
        ):
            self.assertIn(link, t)

    def test_regression_proof_discipline_four_part_evidence(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Regression-proof discipline", t)
        self.assertIn("prior behavior", t)
        self.assertIn("failure scenario", t)

    def test_disconfirmation_outcomes_are_named(self) -> None:
        t = MODEL.read_text(encoding="utf-8")
        for outcome in DISCONFIRMATION_OUTCOMES:
            self.assertIn(outcome, t)

    def test_classification_categories_are_named(self) -> None:
        t = _norm(MODEL)
        for category in CLASSIFICATIONS:
            self.assertIn(category, t)
        self.assertIn("Only a proven correctness defect is normally blocking", t)

    def test_claim_valid_vs_blocking_justification_valid_is_explicit(self) -> None:
        t = _norm(MODEL)
        self.assertIn("claim_valid", t)
        self.assertIn("blocking_justification_valid", t)
        self.assertIn("finding is kept", t)
        self.assertIn("never suppressed", t)

    def test_blast_radius_reuse_is_explicit(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Bounded blast-radius reuse", t)
        self.assertIn("no second expansion or blast-radius procedure", t)

    def test_worked_examples_present(self) -> None:
        t = _norm(MODEL)
        for n in range(1, 7):
            self.assertIn(f"Worked example {n}", t)

    def test_classification_and_blocking_are_orthogonal_dimensions(self) -> None:
        # #382 follow-up 2: a proven correctness defect with insufficient
        # material impact must stay classified as a proven correctness
        # defect -- the design record must say this unmistakably, and must
        # not imply that non-blocking means ambiguity/coverage/
        # maintainability, nor that only blocking defects are "proven".
        t = _norm(MODEL)
        self.assertIn("Classification and blocking justification are orthogonal dimensions", t)
        self.assertIn("the second is never allowed to change the answer to the first", t)
        self.assertIn(
            "stays classified as a proven correctness defect", t
        )
        self.assertIn(
            "It never consults material impact", t
        )
        self.assertIn(
            "including proven correctness defect itself, when every gate cleared except material impact",
            t,
        )

    def test_worked_example_6_shows_proven_defect_non_blocking_impact(self) -> None:
        t = _norm(MODEL)
        self.assertIn(
            "Worked example 6 — proven defect, impact does not clear the blocking bar", t
        )
        self.assertIn("blocking_justification_valid = false", t)
        self.assertIn(
            "Only the blocking eligibility differs from worked example 1; the classification does not",
            t,
        )

    def test_non_goals_cover_chain_of_thought_and_no_new_enum(self) -> None:
        t = _norm(MODEL)
        self.assertIn("No chain-of-thought exposure", t)
        self.assertIn("No new runtime enum on the finding contract", t)
        self.assertIn("Jira is never made mandatory", t)
        self.assertIn("No suppression of a code-provable P1", t)


class NotPackagedTests(unittest.TestCase):
    def test_model_declares_itself_not_packaged(self) -> None:
        self.assertIn("Not packaged", MODEL.read_text(encoding="utf-8"))
        self.assertIn("no packaged Skill resource depends on it", _norm(DIR_README))

    def test_reference_module_is_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:800]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_reference_module_registered_in_packaging_boundary(self) -> None:
        self.assertIn('"candidate_finding_validation.py"', BOUNDARY.read_text(encoding="utf-8"))


class SharedPolicyReferencesAreLinkLevelTests(unittest.TestCase):
    def test_review_scope_names_the_model_without_duplicating_it(self) -> None:
        t = _norm(REVIEW_SCOPE)
        self.assertIn("candidate-finding validation model", t)
        # no grounding hierarchy or disconfirmation table copied in
        self.assertNotIn("RECLASSIFIED", t)
        self.assertNotIn("Reviewer inference alone", t)

    def test_review_scope_does_not_state_a_universal_comparison_requirement(self) -> None:
        # #382 follow-up: the packaged wording must not read as though every
        # candidate must compare two usages before it can become valid.
        t = _norm(REVIEW_SCOPE)
        self.assertNotIn(
            "requires establishing that two compared usages serve the same semantic",
            t,
        )
        self.assertIn(
            "When the candidate's own reasoning depends on comparing two", t
        )
        self.assertIn("no such comparison", t)

    def test_evidence_names_the_model_without_duplicating_it(self) -> None:
        t = _norm(EVIDENCE)
        self.assertIn("candidate-finding validation model", t)
        self.assertNotIn("RECLASSIFIED", t)

    def test_severity_names_the_model_without_duplicating_it(self) -> None:
        t = _norm(SEVERITY)
        self.assertIn("candidate-finding validation model", t)
        self.assertIn("Relationship to candidate-finding validation", t)

    def test_repository_expansion_and_architectural_placement_cross_link(self) -> None:
        self.assertIn(
            "candidate-finding validation model", _norm(REPO_EXPANSION)
        )
        self.assertIn(
            "candidate-finding validation model", _norm(ARCH_PLACEMENT)
        )

    def test_shared_files_do_not_markdown_link_into_docs(self) -> None:
        for path in (REVIEW_SCOPE, EVIDENCE, SEVERITY, REPO_EXPANSION, ARCH_PLACEMENT):
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("](../../docs/", raw, path.name)
            self.assertNotIn("](../../../docs/", raw, path.name)

    def test_shared_policies_do_not_redefine_evidence_or_severity(self) -> None:
        t = _norm(EVIDENCE)
        self.assertIn("confirmed defect", t)
        self.assertIn("credible engineering risk", t)
        t2 = _norm(SEVERITY)
        self.assertIn("P0", t2)
        self.assertIn("P1", t2)
        self.assertIn("P2", t2)


class WiringTests(unittest.TestCase):
    def test_architecture_references_the_new_directory(self) -> None:
        t = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn(
            "candidate-finding-validation/candidate-finding-validation-model.md", t
        )
        self.assertIn("candidate-finding-validation/README.md", t)
        norm = _norm(ARCHITECTURE)
        self.assertIn("candidate-finding validation model", norm.lower())


class LinksResolveTests(unittest.TestCase):
    def test_every_relative_markdown_link_in_the_new_docs_resolves(self) -> None:
        link_re = re.compile(r"\]\((?!https?://|#)([^)]+)\)")
        broken: list[str] = []
        for md in (MODEL, DIR_README):
            base = md.parent
            for target in link_re.findall(md.read_text(encoding="utf-8")):
                path_part = target.split("#", 1)[0]
                if not path_part:
                    continue
                if not (base / path_part).resolve().exists():
                    broken.append(f"{md.name} -> {target}")
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
