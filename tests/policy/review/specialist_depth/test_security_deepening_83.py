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

import unittest

from tests.support.deepening_contract import (
    FINDING_TMPL,
    SPECIALIST_DEPTH,
    DeepeningContractMixin,
    DeepeningDomain,
)
from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _norm

POLICY = REPO_ROOT / "shared/policies/security-deepening.md"
FINDING_RENDERING = REPO_ROOT / "shared/templates/finding-rendering.md"

DOMAIN = DeepeningDomain(
    policy=POLICY,
    dimension="Security / trust boundaries",
    never_decides=(
        "This capability never decides whether a security concern is "
        "considered at all"
    ),
    implication_without_file=(
        'no file conventionally associated with "security" or "auth" '
        "is touched"
    ),
    concern_areas=(
        "Authorization placement",
        "Alternate paths to a privileged operation",
        "Confused-deputy behavior",
        "Validation/sanitization assumptions",
        "Privilege propagation",
    ),
    no_unbounded_audit=(
        "never a separate, unbounded audit of every caller in the "
        "repository"
    ),
    no_second_schema="No new finding/severity/evidence schema",
    generic_advice_rejected=(
        "generic vulnerability-class advice with no traced flow in "
        "this change does not meet the evidence bar"
    ),
    review_scope_absent=("confused-deputy behavior",),
)


class SecurityDeepeningContractTests(DeepeningContractMixin, unittest.TestCase):
    domain = DOMAIN


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


class WorkedExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_engagement_cases_present(self) -> None:
        self.assertIn("Engages — alternate path to a privileged operation", self.text)
        self.assertIn("Engages — confused-deputy behavior", self.text)


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

    def test_specialist_depth_labeling_rule_forbids_proof_of_run_findings(
        self,
    ) -> None:
        t = _norm(SPECIALIST_DEPTH)
        self.assertIn(
            "A capability that finds nothing beyond what base reasoning "
            "already established contributes no additional finding "
            "merely to prove it ran",
            t,
        )


if __name__ == "__main__":
    unittest.main()
