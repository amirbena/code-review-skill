#!/usr/bin/env python3
"""Root-cause and model-completeness pass.

Contract: shared/policies/root-cause-consolidation.md — extracted from
review-scope.md (Issue #198); review-scope.md keeps a linking overview
under its own "Root-cause and model-completeness pass" heading (see
test_review_scope_core_wiring.py for the reachability/routing checks that
span every extracted pass).
Prose checks only — there is deliberately no second implementation of the
rules (see policies/skill-development-policy.md, "Runbook Design").
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import extract_section as _section
from tests.support.policy_docs import load_normalized_text as _text

ROOT_CAUSE = REPO_ROOT / "shared/policies/root-cause-consolidation.md"


class RootCauseAndModelCompletenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.section = _section(
            _text(ROOT_CAUSE),
            "## Root-cause and model-completeness pass",
        )

    def test_multiple_symptoms_trigger_a_structural_pass_without_fixed_threshold(self) -> None:
        for signal in (
            "related defects with the same failure shape",
            "individually correct helpers whose composition remains unsafe",
            "same invariant bypassed through multiple paths",
            "several special cases accumulating around one abstraction",
        ):
            self.assertIn(signal, self.section)
        self.assertIn("strong signal, not a mandatory numeric threshold", self.section)

    def test_model_completeness_requires_evidenced_missing_dimension(self) -> None:
        self.assertIn("an author without the authority kind being established", self.section)
        self.assertIn("Do not invent dimensions speculatively", self.section)
        self.assertIn("cannot represent a distinction required", self.section)

    def test_one_structural_finding_does_not_collapse_distinct_causes(self) -> None:
        self.assertIn("Prefer one structural finding", self.section)
        self.assertIn("Keep findings separate when causes or fixes are materially different", self.section)
        self.assertIn("semantic deduplication, not under-reporting", self.section)

    def test_canonical_repository_owner_is_preferred(self) -> None:
        self.assertIn("recommend fixing or consuming that owner", self.section)
        self.assertIn("instead of adding more local copies", self.section)

    def test_evidenced_upstream_fix_prefers_package_upgrade(self) -> None:
        self.assertIn("Upstream defect with an evidenced maintained fix", self.section)
        self.assertIn("prefer upgrading the same package to the fixed version", self.section)
        for evidence in ("release notes", "changelog", "advisory", "upstream issue"):
            self.assertIn(evidence, self.section)

    def test_unknown_fixed_version_is_never_invented(self) -> None:
        self.assertIn("Upstream defect without a verified fixed version", self.section)
        self.assertIn("do not invent a version", self.section)
        self.assertIn("state the limitation rather than guessing", self.section)

    def test_local_misuse_is_fixed_locally_not_upgraded_automatically(self) -> None:
        self.assertIn("Local misuse or unsupported configuration", self.section)
        self.assertIn("correct the local call, configuration, or ordering", self.section)
        self.assertIn("Package upgrades are not a blanket dependency rule", self.section)

    def test_breaking_upgrade_requires_migration_evidence(self) -> None:
        self.assertIn("Breaking or major-version upgrade", self.section)
        self.assertIn("account for migration and compatibility implications", self.section)
        self.assertIn("never present it as a trivial remediation", self.section)

    def test_rereview_verifies_invariant_across_related_paths(self) -> None:
        self.assertIn("verify on re-review that the corrected invariant covers the related paths", self.section)
        self.assertIn("same unfixed mechanism reconciles to the same finding", self.section)

    def test_shared_root_cause_versus_independent_findings_is_defined_with_examples(self) -> None:
        self.assertIn("A shared root cause is a single defect-bearing element", self.section)
        self.assertIn(
            "one correction at that element resolves every manifestation", self.section
        )
        self.assertIn("A common theme is not a common cause.", self.section)
        # worked contrast: one symbol many callers -> consolidate; unrelated
        # look-alikes -> separate
        self.assertIn("one authoritative finding on is_valid_email", self.section)
        self.assertIn("emits two findings and does not merge them", self.section)

    def test_authoritative_consolidated_finding_shape_lists_affected_locations(self) -> None:
        self.assertIn("emit one finding with a single identity", self.section)
        # F2: at least two sites, exhaustive, required / not publishable without it
        self.assertIn(
            "Consolidation applies only when the shared cause reaches at least "
            "two manifestation sites.",
            self.section,
        )
        self.assertIn(
            "plus an affected-locations list that names every known manifestation site",
            self.section,
        )
        self.assertIn("so the list is exhaustive for the sites the review found", self.section)
        self.assertIn(
            "the affected-locations list is required — a consolidated finding "
            "without it is not publishable",
            self.section,
        )
        self.assertIn("rendered on every delivery surface", self.section)
        self.assertIn("Affected locations on a consolidated finding", self.section)
        self.assertIn("An ordinary single-site finding never carries the field.", self.section)

    def test_consolidation_fails_open_to_separate_findings(self) -> None:
        self.assertIn(
            "Consolidation requires the shared cause to be positively established",
            self.section,
        )
        self.assertIn("emit separate findings rather than over-merging", self.section)
        self.assertIn(
            "A false split is visible duplicate noise a reader can reconcile; "
            "an over-merge silently drops a distinct defect.",
            self.section,
        )
        self.assertIn("When confidence is not there, split.", self.section)

    def test_rereview_routes_identity_handling_to_the_lifecycle_model(self) -> None:
        # F1: no "supersede"; route to the finding-identity / lifecycle model;
        # ordinary many-to-one stays ambiguous; only positive root-cause
        # evidence folds (CONSOLIDATED); nothing resolved.
        self.assertNotIn("supersede", self.section.lower())
        self.assertIn(
            "Consolidation also reconciles in the other direction on re-review.",
            self.section,
        )
        self.assertIn("emit the single authoritative consolidated finding (a new finding identity)", self.section)
        self.assertIn(
            "How the prior per-site finding identities are then handled is owned "
            "by the repository's finding-identity and lifecycle model, not "
            "restated here",
            self.section,
        )
        self.assertIn(
            "ordinary many-to-one matching (several prior identities that merely "
            "appear to map to one candidate) stays ambiguous",
            self.section,
        )
        self.assertIn(
            "consolidation is never inferred from that topology or from wording similarity",
            self.section,
        )
        self.assertIn(
            "only a positively established shared cause folds the prior identities "
            "into the consolidated finding (the lifecycle model's CONSOLIDATED disposition)",
            self.section,
        )
        self.assertIn("nothing is treated as resolved", self.section)
        self.assertIn(
            "when the shared cause is not positively established, keep the findings separate",
            self.section,
        )

    def test_existing_review_evidence_triggers_but_does_not_prove_root_cause(self) -> None:
        self.assertIn("may trigger this pass as Existing Review Evidence", self.section)
        self.assertIn("never widen the current Review Target", self.section)
        self.assertIn("never prove the root cause by themselves", self.section)

    def test_policy_stays_a_bounded_reasoning_rule(self) -> None:
        for excluded in (
            "finding graph",
            "clustering/similarity system",
            "dependency scanner",
            "automatic package resolver",
        ):
            self.assertIn(excluded, self.section)


if __name__ == "__main__":
    unittest.main()
