#!/usr/bin/env python3
"""Documentation-contract checks for the contextual-evidence model (Issue #118).

Pins docs/review-context/contextual-evidence-model.md, its navigational
README, the optional `contextual evidence` finding field, and the wiring
into the architecture map and the feature guide. Structural prose checks in
the same style as test_shared_review_context.py — semantic structure and
whitespace-normalized prose, not brittle exact whitespace.

Run with:
    python3 -m unittest tests.policy.test_context_evidence_docs
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

DOCDIR = REPO_ROOT / "docs" / "review-context"
MODEL = DOCDIR / "contextual-evidence-model.md"
DIR_README = DOCDIR / "README.md"
FINDING = REPO_ROOT / "shared" / "templates" / "finding.md"
FINDING_RENDERING = REPO_ROOT / "shared" / "templates" / "finding-rendering.md"
SHARED_CONTEXT = REPO_ROOT / "shared" / "policies" / "review-context.md"
SHARED_EVIDENCE = REPO_ROOT / "shared" / "policies" / "review-evidence.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
FEATURE = REPO_ROOT / "docs" / "features" / "review-context.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "context_evidence.py"
BOUNDARY = REPO_ROOT / "tests" / "integration" / "test_packaging_runtime_boundary.py"
EXPECTATIONS = REPO_ROOT / "scripts" / "skill_metadata" / "expectations.py"

EVIDENCE_TYPES = (
    "requirement",
    "acceptance_criteria",
    "accepted_decision",
    "repository_policy",
    "implementation_feedback",
    "historical_context",
    "pre_existing_risk_note",
    "informal_discussion",
)
RESOLUTION_OUTCOMES = (
    "USE_AUTHORITATIVE",
    "REPORT_CONFLICT",
    "REPORT_AMBIGUITY",
    "TREAT_AS_INFORMATIONAL_ONLY",
    "DISREGARD_STALE",
)


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class DesignRecordExistsAndIsTypedTests(unittest.TestCase):
    def test_docs_exist(self) -> None:
        self.assertTrue(MODEL.is_file())
        self.assertTrue(DIR_README.is_file())

    def test_every_evidence_type_appears_and_is_marked(self) -> None:
        t = _norm(MODEL)
        for name in EVIDENCE_TYPES:
            self.assertIn(name, t, f"evidence type {name} missing from the model")
        self.assertIn("authoritative", t)
        self.assertIn("informational", t)
        # the table names both markings against concrete types
        self.assertRegex(t, r"requirement \| authoritative")
        self.assertRegex(t, r"informal_discussion \| informational")

    def test_non_override_rule_is_explicit(self) -> None:
        t = _norm(MODEL)
        self.assertIn("An informational source can never override an authoritative one", t)
        self.assertIn(
            "informal discussion must not silently override an explicit requirement "
            "or an approved design decision",
            t,
        )

    def test_feedback_is_informational_until_ratified(self) -> None:
        t = _norm(MODEL)
        self.assertIn("is informational unless ratified", t)
        self.assertIn("the accepted artifact or decision is the authoritative evidence", t)

    def test_repository_policy_vs_requirement_is_deterministic(self) -> None:
        t = _norm(MODEL)
        self.assertIn("If an existing repository contract already defines the precedence", t)
        self.assertIn("Otherwise, report the conflict", t)
        self.assertIn("does not silently pick whichever source is ranked higher", t)

    def test_all_five_resolution_outcomes_are_named(self) -> None:
        t = _norm(MODEL)
        for outcome in RESOLUTION_OUTCOMES:
            self.assertIn(outcome, t)

    def test_provenance_severity_distinction_is_explicit(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Severity and provenance are distinct", t)
        self.assertIn(
            "The provenance metadata itself never moves severity", t
        )
        self.assertIn("Evidence can justify a severity; the provenance annotation cannot move one", t)

    def test_scope_intent_and_attribution_sections_have_worked_examples(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Using authoritative context for scope / intent validation", t)
        self.assertIn("Introduced-versus-pre-existing attribution", t)
        # every worked example the reference corpus mirrors — covering all
        # five resolution outcomes
        for n in range(1, 9):
            self.assertIn(f"Worked example {n}", t)

    def test_precision_preservation_analysis_exists(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Preventing precision loss", t)
        self.assertIn("Context focuses attention and supplies provenance; it never lowers the evidence bar", t)
        self.assertIn("Informational sources cannot create findings", t)
        self.assertIn("Severity is never imported from a source's wording", t)

    def test_smallest_useful_first_implementation_is_scoped(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Smallest useful first implementation", t)
        for deferred in (
            "source adapters",
            "automatic PR↔Issue discovery",
            "machine-readable provenance block",
        ):
            self.assertIn(deferred, t)

    def test_runtime_boundary_is_stated(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Runtime boundary", t)
        self.assertIn(
            "introduces no automatic context retrieval, resolution, inference, or attachment",
            t,
        )
        self.assertIn("grants no new capability", t)


class NotPackagedTests(unittest.TestCase):
    def test_model_declares_itself_not_packaged(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Not packaged", MODEL.read_text(encoding="utf-8"))
        self.assertIn("no packaged Skill resource depends on them", _norm(DIR_README))

    def test_reference_module_is_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:600]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_reference_module_registered_in_packaging_boundary(self) -> None:
        self.assertIn('"context_evidence.py"', BOUNDARY.read_text(encoding="utf-8"))


class FindingProvenanceFieldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = FINDING.read_text(encoding="utf-8")
        self.norm = _norm(FINDING)

    def test_finding_template_has_the_provenance_section(self) -> None:
        self.assertIn("## Contextual evidence and provenance", self.text)

    def test_contextual_evidence_is_an_optional_field(self) -> None:
        self.assertIn("contextual evidence", self.norm)
        # named in the Optional and surface-specific fields section
        opt = re.search(
            r"## Optional and surface-specific fields\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(opt)
        self.assertIn("contextual evidence", _norm_str(opt.group(1)))

    def test_provenance_never_moves_severity_or_identity(self) -> None:
        section = re.search(
            r"## Contextual evidence and provenance\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(section)
        body = _norm_str(section.group(1))
        self.assertIn("never calculates, raises, lowers, or overrides severity", body)
        self.assertIn("never changes the finding's identity", body)
        self.assertIn("on the GitHub inline surface it folds into evidence prose", body)

    def test_rendering_exemplar_shows_the_optional_line(self) -> None:
        self.assertIn("**Contextual evidence:**", FINDING_RENDERING.read_text(encoding="utf-8"))

    def test_expectations_marker_is_registered(self) -> None:
        self.assertIn(
            '"## Contextual evidence and provenance"',
            EXPECTATIONS.read_text(encoding="utf-8"),
        )


class SharedPolicyReferencesAreLinkLevelTests(unittest.TestCase):
    def test_review_context_names_the_model_without_duplicating_it(self) -> None:
        t = _norm(SHARED_CONTEXT)
        self.assertIn("contextual-evidence model", t.lower())
        self.assertIn("Contextual evidence and provenance", t)
        # no authority matrix / resolution table copied into packaged policy
        self.assertNotIn("USE_AUTHORITATIVE", t)
        self.assertNotIn("DISREGARD_STALE", t)

    def test_review_evidence_names_the_model_without_duplicating_it(self) -> None:
        t = _norm(SHARED_EVIDENCE)
        self.assertIn("contextual-evidence model", t.lower())
        self.assertNotIn("USE_AUTHORITATIVE", t)

    def test_shared_files_do_not_markdown_link_into_docs(self) -> None:
        for path in (SHARED_CONTEXT, SHARED_EVIDENCE, FINDING):
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("](../../docs/", raw, path.name)
            self.assertNotIn("](../../../docs/", raw, path.name)


class WiringTests(unittest.TestCase):
    def test_architecture_references_the_new_directory(self) -> None:
        t = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn("review-context/contextual-evidence-model.md", t)
        self.assertIn("review-context/README.md", t)
        norm = _norm(ARCHITECTURE)
        self.assertIn("contextual-evidence model", norm.lower())

    def test_feature_guide_mentions_typed_authority_and_provenance(self) -> None:
        t = _norm(FEATURE)
        self.assertIn("authoritative", t)
        self.assertIn("informational", t)
        self.assertIn("provenance", t.lower())
        self.assertIn("contextual-evidence-model.md", FEATURE.read_text(encoding="utf-8"))


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


def _norm_str(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.replace("**", "").replace("`", ""))


if __name__ == "__main__":
    unittest.main()
