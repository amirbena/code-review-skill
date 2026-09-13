#!/usr/bin/env python3
"""Pins the security deepening capability contract (Issue #83).

The first domain-specific deepening capability under the composition
contract defined in #82 (`specialist-depth.md`): bounded, evidence-driven
tracing of a trust boundary — authorization placement, alternate paths to
a privileged operation, confused-deputy behavior, validation/sanitization
assumptions, and privilege propagation — once base review (#211) has
already identified a materially implicated "Security / trust boundaries"
dimension. These assertions protect the cross-document invariant, not
merely that each file mentions the feature:

1. one canonical shared policy owns the capability; `review-scope.md`'s
   "Security / trust boundaries" dimension routes to it as an additional
   depth owner, the same way it already routes to "Architectural
   placement and execution-lifecycle fidelity";
2. the capability never decides whether a security concern is considered
   at all — that stays with #211's base pass, unconditionally;
3. activation is evidence-driven, never a file-type/path/keyword router;
4. cascading/alternate-path tracing is bounded by #87's existing
   expansion/stop-condition contract, reused via #82;
5. findings are ordinary findings carrying the optional `capability`
   provenance field, never a new severity/evidence schema;
6. it is not an external SAST integration or a generic vulnerability
   scanner;
7. it is indexed in the shared policy map and packaging manifest.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

POLICY = REPO_ROOT / "shared/policies/security-deepening.md"
SPECIALIST_DEPTH = REPO_ROOT / "shared/policies/specialist-depth.md"
REVIEW_SCOPE = REPO_ROOT / "shared/policies/review-scope.md"
REPOSITORY_EXPANSION = REPO_ROOT / "shared/policies/repository-expansion.md"
REMEDIATION_SCOPE = REPO_ROOT / "shared/policies/remediation-scope-boundary.md"
SEVERITY = REPO_ROOT / "shared/policies/severity.md"
EVIDENCE = REPO_ROOT / "shared/policies/evidence.md"
POLICIES_README = REPO_ROOT / "shared/policies/README.md"
FINDING_TMPL = REPO_ROOT / "shared/templates/finding.md"
FINDING_RENDERING = REPO_ROOT / "shared/templates/finding-rendering.md"
PACKAGE_MANIFEST = REPO_ROOT / "scripts/package-manifest.json"


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class CanonicalOwnerTests(unittest.TestCase):
    def test_policy_file_exists_and_declares_scope(self) -> None:
        t = _norm(POLICY)
        self.assertIn(
            "Applies identically to local-code-review and github-pr-review",
            t,
        )
        self.assertIn(
            "domain-specific deepening capability under "
            "[specialist-depth.md](specialist-depth.md)'s composition "
            "contract",
            t,
        )

    def test_review_scope_routes_without_restating(self) -> None:
        t = _norm(REVIEW_SCOPE)
        raw = REVIEW_SCOPE.read_text(encoding="utf-8")
        self.assertIn(
            "[security-deepening.md](security-deepening.md) per the "
            '"Domain-specific deepening pass" below',
            t,
        )
        # review-scope.md must not restate the capability's worked
        # examples or concern-area catalog
        self.assertNotIn("confused-deputy behavior", t)
        self.assertIn("## Domain-specific deepening pass", raw)

    def test_policy_indexed_in_readme(self) -> None:
        raw = POLICIES_README.read_text(encoding="utf-8")
        self.assertIn("security-deepening.md", raw)

    def test_policy_indexed_in_package_manifest(self) -> None:
        manifest = json.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))
        sources = json.dumps(manifest)
        self.assertIn("shared/policies/security-deepening.md", sources)


class BaseObligationUnconditionalTests(unittest.TestCase):
    """The capability never decides whether a security concern is
    considered at all — #211's base pass owns that, unconditionally."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_never_decides_whether_considered(self) -> None:
        self.assertIn(
            "This capability never decides whether a security concern is "
            "considered at all",
            self.text,
        )

    def test_does_not_redefine_base_detection(self) -> None:
        self.assertIn(
            "that detection does not start existing only once this "
            "capability engages",
            self.text,
        )


class ActivationTests(unittest.TestCase):
    """Activation requires both a base-identified boundary and evidence
    that deeper tracing is warranted — never a file-type/path router."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_two_part_activation_condition(self) -> None:
        self.assertIn(
            "[review-scope.md](review-scope.md)'s base pass has already "
            "identified a materially implicated Security / trust "
            "boundaries dimension",
            self.text,
        )
        self.assertIn(
            "the evidence gathered by that base pass", self.text
        )

    def test_signals_never_independently_sufficient(self) -> None:
        self.assertIn(
            "does not by itself satisfy condition 2", self.text
        )

    def test_implication_without_expected_file_present(self) -> None:
        self.assertIn(
            'no file conventionally associated with "security" or "auth" '
            "is touched",
            self.text,
        )


class ConcernAreaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_all_five_concern_areas_present(self) -> None:
        for phrase in (
            "Authorization placement",
            "Alternate paths to a privileged operation",
            "Confused-deputy behavior",
            "Validation/sanitization assumptions",
            "Privilege propagation",
        ):
            self.assertIn(phrase, self.text)

    def test_not_an_exhaustive_unconditional_checklist(self) -> None:
        self.assertIn(
            "not an exhaustive checklist run unconditionally on every "
            "activation",
            self.text,
        )


class CascadingBoundedByExpansionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_reuses_specialist_depth_and_repository_expansion(self) -> None:
        self.assertIn(
            "reuses [specialist-depth.md](specialist-depth.md)'s "
            "cascading-activation model, which in turn reuses "
            "[repository-expansion.md](repository-expansion.md)'s fixed "
            "trigger/ring/ ceiling procedure",
            self.text,
        )

    def test_no_unbounded_audit(self) -> None:
        self.assertIn(
            "never a separate, unbounded audit of every caller in the "
            "repository",
            self.text,
        )

    def test_insufficient_evidence_remains_valid_terminal_outcome(self) -> None:
        self.assertIn(
            'Insufficient evidence" remains a valid terminal outcome',
            self.text,
        )


class FindingsAreOrdinaryAndLabeledTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_ordinary_finding_language(self) -> None:
        self.assertIn(
            "A finding this capability contributes is an ordinary finding",
            self.text,
        )

    def test_capability_provenance_field_named(self) -> None:
        self.assertIn(
            "the optional capability provenance field, valued "
            "security-deepening",
            self.text,
        )

    def test_no_second_schema(self) -> None:
        self.assertIn("No new finding/severity/evidence schema", self.text)

    def test_generic_vulnerability_advice_rejected(self) -> None:
        self.assertIn(
            "generic vulnerability-class advice with no traced flow in "
            "this change does not meet the evidence bar",
            self.text,
        )


class NonGoalsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_no_external_sast(self) -> None:
        self.assertIn("No external SAST integration", self.text)

    def test_not_a_generic_scanner(self) -> None:
        self.assertIn(
            "Not a generic security audit or vulnerability scanner",
            self.text,
        )

    def test_does_not_redefine_composition_or_remediation_scope(self) -> None:
        self.assertIn(
            "Does not redefine composition, cascading, or "
            "remediation-scope semantics",
            self.text,
        )


class WorkedExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_engagement_and_non_engagement_cases_present(self) -> None:
        self.assertIn("Engages — alternate path to a privileged operation", self.text)
        self.assertIn("Engages — confused-deputy behavior", self.text)
        self.assertIn(
            "Does not engage — bounded base reasoning already suffices",
            self.text,
        )
        self.assertIn("Misleading superficial signal", self.text)
        self.assertIn("Implication without the expected file/path", self.text)
        self.assertIn("Depth vs. remediation scope", self.text)


class FindingContractCapabilityFieldTests(unittest.TestCase):
    """The `capability` field is optional, evidence-only provenance —
    never a severity input, never a new schema."""

    def test_field_documented_in_fields_list(self) -> None:
        raw = FINDING_TMPL.read_text(encoding="utf-8")
        self.assertIn("**capability** — optional", raw)
        t = _norm(FINDING_TMPL)
        self.assertIn(
            "it never calculates or changes severity, identity, "
            "deduplication, or the decision derivation (see \"Capability "
            "provenance\")",
            t,
        )

    def test_capability_provenance_section_present(self) -> None:
        raw = FINDING_TMPL.read_text(encoding="utf-8")
        self.assertIn("## Capability provenance", raw)
        idx = raw.find("## Capability provenance")
        self.assertNotEqual(idx, -1)
        self.assertIn("specialist-depth.md", raw[idx : idx + 2500])

    def test_rendering_example_present(self) -> None:
        raw = FINDING_RENDERING.read_text(encoding="utf-8")
        self.assertIn("**Capability:** security-deepening", raw)
        t = _norm(FINDING_RENDERING)
        self.assertIn(
            "there is no separate Capability: line on this surface", t
        )

    def test_capability_listed_in_optional_and_surface_specific_fields(self) -> None:
        # regression guard: this master enumeration section lists every
        # other provenance field (contextual evidence, runtime validation,
        # confidence) individually — `capability` must not be the one
        # left out when a future edit touches this section again.
        raw = FINDING_TMPL.read_text(encoding="utf-8")
        idx = raw.find("## Optional and surface-specific fields")
        self.assertNotEqual(idx, -1)
        section = raw[idx : idx + 4000]
        self.assertIn("**capability**", section)

    def test_capability_listed_in_finding_rules_section(self) -> None:
        # same regression guard for finding.md's own "## Rules" section.
        raw = FINDING_TMPL.read_text(encoding="utf-8")
        idx = raw.rfind("## Rules")
        self.assertNotEqual(idx, -1)
        section = raw[idx:]
        self.assertIn("**capability**", section)

    def test_specialist_depth_owns_generic_labeling_rule(self) -> None:
        t = _norm(SPECIALIST_DEPTH)
        self.assertIn(
            "Capability-contributed findings are labeled, not re-schemed",
            t,
        )
        self.assertIn(
            "A capability that finds nothing beyond what base reasoning "
            "already established contributes no additional finding "
            "merely to prove it ran",
            t,
        )


class NoDuplicationTests(unittest.TestCase):
    """The policy defers severity/evidence/remediation-scope mechanics to
    their existing owners rather than restating them."""

    def test_defers_severity_and_evidence(self) -> None:
        severity_raw = SEVERITY.read_text(encoding="utf-8")
        evidence_raw = EVIDENCE.read_text(encoding="utf-8")
        policy_raw = POLICY.read_text(encoding="utf-8")
        self.assertTrue(severity_raw.strip())
        self.assertTrue(evidence_raw.strip())
        self.assertNotIn("## Decision derivation", policy_raw)

    def test_defers_remediation_scope(self) -> None:
        remediation_raw = REMEDIATION_SCOPE.read_text(encoding="utf-8")
        policy_raw = POLICY.read_text(encoding="utf-8")
        self.assertIn(
            "## Three-part reasoning (mandatory, per material finding)",
            remediation_raw,
        )
        self.assertNotIn("## Three-part reasoning", policy_raw)


class NoLexicalDriftTests(unittest.TestCase):
    ALL_CONSUMERS = (
        REVIEW_SCOPE,
        POLICIES_README,
    )

    def test_every_consumer_names_the_policy(self) -> None:
        for path in self.ALL_CONSUMERS:
            raw = path.read_text(encoding="utf-8")
            self.assertIn(
                "security-deepening.md",
                raw,
                msg=f"{path} does not reference security-deepening.md",
            )

    def test_manifest_names_the_policy_file_exactly(self) -> None:
        manifest_raw = PACKAGE_MANIFEST.read_text(encoding="utf-8")
        self.assertIn("shared/policies/security-deepening.md", manifest_raw)


if __name__ == "__main__":
    unittest.main()
