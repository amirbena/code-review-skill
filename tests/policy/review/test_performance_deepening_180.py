#!/usr/bin/env python3
"""Pins the performance deepening capability contract (Issue #180).

A domain-specific deepening capability under the composition contract
defined in #82 (`specialist-depth.md`): bounded, evidence-driven tracing of
a performance/scale concern — cardinality analysis, call-path behavior,
batching, hot-path placement, query/network amplification, and
memory/concurrency implications — once base review (#211) has already
identified a materially implicated "Performance / scale" dimension. These
assertions protect the cross-document invariant, not merely that each file
mentions the feature:

1. one canonical shared policy owns the capability; `review-scope.md`'s
   "Performance / scale" dimension routes to it as an additional depth
   owner, the same way it already routes to "Change-risk signals and
   review depth" and `repository-expansion.md`;
2. the capability never decides whether a performance/scale concern is
   considered at all — that stays with #211's base pass, unconditionally,
   and ordinary performance findings remain part of every review whether
   or not this capability engages;
3. activation is evidence-driven, never a file-type/path/framework router
   — superficial filenames, framework names, or "performance-looking" code
   are not by themselves activation evidence;
4. cascading/call-path tracing is bounded by #87's existing
   expansion/stop-condition contract, reused via #82;
5. findings are ordinary findings carrying the optional `capability`
   provenance field, never a new severity/evidence schema;
6. missing call-graph/data-size context fails safe with no invented
   findings;
7. it does not re-trace concurrent-interleaving correctness, which stays
   owned by `distributed-systems-deepening.md`;
8. it is indexed in the shared policy map and packaging manifest.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

POLICY = REPO_ROOT / "shared/policies/performance-deepening.md"
SPECIALIST_DEPTH = REPO_ROOT / "shared/policies/specialist-depth.md"
REVIEW_SCOPE = REPO_ROOT / "shared/policies/review-scope.md"
REPOSITORY_EXPANSION = REPO_ROOT / "shared/policies/repository-expansion.md"
REMEDIATION_SCOPE = REPO_ROOT / "shared/policies/remediation-scope-boundary.md"
DISTRIBUTED_DEEPENING = REPO_ROOT / "shared/policies/distributed-systems-deepening.md"
SEVERITY = REPO_ROOT / "shared/policies/severity.md"
EVIDENCE = REPO_ROOT / "shared/policies/evidence.md"
POLICIES_README = REPO_ROOT / "shared/policies/README.md"
FINDING_TMPL = REPO_ROOT / "shared/templates/finding.md"
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
            "[performance-deepening.md](performance-deepening.md) per the "
            '"Domain-specific deepening pass" below',
            t,
        )
        # review-scope.md must not restate the capability's worked
        # examples or concern-area catalog
        self.assertNotIn("Query/network amplification", raw)
        self.assertNotIn("PerformanceUtils.java", raw)
        self.assertIn("## Domain-specific deepening pass", raw)

    def test_policy_indexed_in_readme(self) -> None:
        raw = POLICIES_README.read_text(encoding="utf-8")
        self.assertIn("performance-deepening.md", raw)

    def test_policy_indexed_in_package_manifest(self) -> None:
        manifest = json.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))
        sources = json.dumps(manifest)
        self.assertIn("shared/policies/performance-deepening.md", sources)


class BaseObligationUnconditionalTests(unittest.TestCase):
    """The capability never decides whether a performance/scale concern is
    considered at all — #211's base pass owns that, unconditionally, and
    ordinary performance findings remain part of every review."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_never_decides_whether_considered(self) -> None:
        self.assertIn(
            "This capability never decides whether a performance/scale "
            "concern is considered at all",
            self.text,
        )

    def test_ordinary_reasoning_visible_regardless_of_engagement(self) -> None:
        self.assertIn(
            "An obvious N+1, unbounded work, blocking I/O in a hot path, "
            "or accidental complexity amplification is base reasoning's "
            "job on every review, whether or not this capability engages",
            self.text,
        )

    def test_does_not_redefine_base_detection(self) -> None:
        self.assertIn(
            "that detection does not start existing only once this "
            "capability engages",
            self.text,
        )


class ActivationTests(unittest.TestCase):
    """Activation requires both a base-identified concern and evidence
    that deeper tracing is warranted — never a file-type/path/framework
    router."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_two_part_activation_condition(self) -> None:
        self.assertIn(
            "[review-scope.md](review-scope.md)'s base pass has already "
            "identified a materially implicated Performance / scale "
            "dimension",
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
            "Conversely, a change with no file conventionally associated "
            "with performance can still satisfy both",
            self.text,
        )


class ConcernAreaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_all_six_concern_areas_present(self) -> None:
        for phrase in (
            "Cardinality analysis",
            "Call-path behavior",
            "Batching",
            "Hot-path placement",
            "Query/network amplification",
            "Memory/concurrency implications",
        ):
            self.assertIn(phrase, self.text)

    def test_not_an_exhaustive_unconditional_checklist(self) -> None:
        self.assertIn(
            "not an exhaustive checklist run unconditionally on every "
            "activation",
            self.text,
        )

    def test_memory_concurrency_bounded_away_from_interleaving_correctness(
        self,
    ) -> None:
        self.assertIn(
            "not the correctness of a concurrent interleaving", self.text
        )


class FailSafeTests(unittest.TestCase):
    """Missing call-graph/data-size context must not produce invented
    findings, and superficial signals alone must never force deep
    analysis."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_missing_context_section_present(self) -> None:
        self.assertIn("Missing call-graph or data-size context", self.text)

    def test_no_speculation_language(self) -> None:
        self.assertIn(
            "this capability does not speculate about that volume, "
            "invocation count, or downstream behavior",
            self.text,
        )

    def test_superficial_signals_alone_not_sufficient(self) -> None:
        self.assertIn(
            'Superficial filenames, framework names, and "performance-'
            'looking" code are not activation evidence',
            self.text,
        )
        self.assertIn(
            "does not by itself trigger deep analysis", self.text
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
            "never a separate, unbounded audit of every call site or loop "
            "in the repository",
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
            "performance-deepening",
            self.text,
        )

    def test_no_second_schema(self) -> None:
        self.assertIn("never a second schema", self.text)

    def test_generic_advice_rejected(self) -> None:
        self.assertIn(
            'generic "this could be slow" advice with no traced cost '
            "concern in this change does not meet the evidence bar",
            self.text,
        )


class NonGoalsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_no_benchmarking_or_profiling(self) -> None:
        self.assertIn("No benchmarking or profiling", self.text)

    def test_not_a_generic_optimization_advisor(self) -> None:
        self.assertIn("Not a generic optimization advisor", self.text)

    def test_does_not_redefine_composition_or_remediation_scope(self) -> None:
        self.assertIn(
            "Does not redefine composition, cascading, or "
            "remediation-scope semantics",
            self.text,
        )

    def test_defers_interleaving_correctness_to_distributed_deepening(
        self,
    ) -> None:
        self.assertIn(
            "Does not re-trace concurrent-interleaving correctness",
            self.text,
        )
        self.assertIn(
            "[distributed-systems-deepening.md](distributed-systems-"
            "deepening.md)'s question",
            self.text,
        )


class WorkedExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_engagement_and_non_engagement_cases_present(self) -> None:
        self.assertIn("Engages — N+1 call path", self.text)
        self.assertIn("Engages — hot-path placement", self.text)
        self.assertIn(
            "Does not engage — bounded base reasoning already suffices",
            self.text,
        )
        self.assertIn("Misleading superficial signal", self.text)
        self.assertIn("Implication without the expected file/path", self.text)
        self.assertIn("Missing call-graph context — fails safe", self.text)
        self.assertIn("Depth vs. remediation scope", self.text)


class FindingContractCapabilityFieldReusedTests(unittest.TestCase):
    """The generic `capability` provenance field (introduced by #83) is
    reused as-is — this capability adds no new finding schema."""

    def test_field_documented_in_fields_list(self) -> None:
        raw = FINDING_TMPL.read_text(encoding="utf-8")
        self.assertIn("**capability** — optional", raw)

    def test_capability_provenance_section_present(self) -> None:
        raw = FINDING_TMPL.read_text(encoding="utf-8")
        self.assertIn("## Capability provenance", raw)

    def test_specialist_depth_owns_generic_labeling_rule(self) -> None:
        t = _norm(SPECIALIST_DEPTH)
        self.assertIn(
            "Capability-contributed findings are labeled, not re-schemed",
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

    def test_defers_interleaving_correctness_mechanics(self) -> None:
        distributed_raw = DISTRIBUTED_DEEPENING.read_text(encoding="utf-8")
        policy_raw = POLICY.read_text(encoding="utf-8")
        self.assertIn("Concurrent interleavings", distributed_raw)
        self.assertNotIn("## Concurrent interleavings", policy_raw)


class NoLexicalDriftTests(unittest.TestCase):
    ALL_CONSUMERS = (
        REVIEW_SCOPE,
        POLICIES_README,
    )

    def test_every_consumer_names_the_policy(self) -> None:
        for path in self.ALL_CONSUMERS:
            raw = path.read_text(encoding="utf-8")
            self.assertIn(
                "performance-deepening.md",
                raw,
                msg=f"{path} does not reference performance-deepening.md",
            )

    def test_manifest_names_the_policy_file_exactly(self) -> None:
        manifest_raw = PACKAGE_MANIFEST.read_text(encoding="utf-8")
        self.assertIn(
            "shared/policies/performance-deepening.md",
            manifest_raw,
        )


if __name__ == "__main__":
    unittest.main()
