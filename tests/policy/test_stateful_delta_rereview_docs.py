"""Structural contract checks for the packaged runtime installation of
delta re-review (#65), skills/github-pr-review/policies/stateful-delta-rereview.md.

Mirrors the assertion style of test_delta_re_review_docs.py (#64) but
targets the *packaged* policy this Issue installs, proving the runtime
procedure actually carries the required eligibility, reconciliation,
blast-radius, escalation, and exact-HEAD rules — not merely that the
design-record doc states them.
"""

import unittest

from tests.support.paths import REPO_ROOT

POLICY = (
    REPO_ROOT
    / "skills"
    / "github-pr-review"
    / "policies"
    / "stateful-delta-rereview.md"
)
SKILL = REPO_ROOT / "skills" / "github-pr-review" / "SKILL.md"
INDEX = REPO_ROOT / "skills" / "github-pr-review" / "policies" / "github-review.md"
DELTA_REVIEW = REPO_ROOT / "skills" / "github-pr-review" / "policies" / "reviewer-delta-review.md"
LOCAL_SKILL = REPO_ROOT / "skills" / "local-code-review" / "SKILL.md"
PACKAGE_SH = REPO_ROOT / "scripts" / "package-skills.sh"
PACKAGE_PS1 = REPO_ROOT / "scripts" / "package-skills.ps1"


class StatefulDeltaRereviewPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = POLICY.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_policy_file_exists(self) -> None:
        self.assertTrue(POLICY.is_file())

    def test_reuses_not_redefines_identity_matching_and_lifecycle(self) -> None:
        self.assertIn("## 1. Reuse, do not redefine", self.raw)
        for outcome in ("`MATCH`", "`NO MATCH`", "`AMBIGUOUS`"):
            self.assertIn(outcome, self.raw)
        for event in ("`DETECTED`", "`STILL_PRESENT`", "`RESOLVED`", "`REOPENED`", "`UNCERTAIN`"):
            self.assertIn(event, self.raw)
        self.assertIn("adds no second identity system", self.text)
        self.assertIn("no second matching algorithm", self.text)

    def test_eligibility_lists_five_preconditions_and_fails_closed(self) -> None:
        section = self.raw.split(
            "## 2. Eligibility", 1
        )[1].split("## 3.", 1)[0]
        for precondition in (
            "**Repository identity**",
            "**PR/review scope**",
            "**Same reviewer identity**",
            "**A reliable previously reviewed SHA**",
            "**Trustworthy prior finding/evidence state**",
        ):
            self.assertIn(precondition, section)
        self.assertIn("Fail closed.", section)
        self.assertIn("do not infer, do not guess a boundary", section)

    def test_reconciliation_maps_all_six_change_classes(self) -> None:
        section = self.raw.split(
            "## 3. Reconciliation", 1
        )[1].split("## 4.", 1)[0]
        for change_class in (
            "Unchanged",
            "Fixed",
            "Moved",
            "Reopened",
            "Newly introduced",
            "Ambiguous",
        ):
            self.assertIn(change_class, section)
        self.assertIn("AMBIGUOUS` never becomes a confident transition", section)
        self.assertIn("A resolved prior finding never implies a clean fix", section)
        self.assertIn("File/line movement is never, by itself, a new-finding signal", section)
        self.assertIn(
            "Disappearance from the diff is never, by itself, resolution", section
        )

    def test_blast_radius_is_evidence_based_and_bounded(self) -> None:
        section = self.raw.split("## 4. Blast radius", 1)[1].split("## 5.", 1)[0]
        self.assertIn("Evidence-based attribution only", section)
        self.assertIn("Bounded, not repository-wide", section)

    def test_settled_assumptions_reconsidered_when_basis_invalidated(self) -> None:
        section = self.raw.split(
            "## 5. Previously settled", 1
        )[1].split("## 6.", 1)[0]
        self.assertIn("Remains settled", section)
        self.assertIn("Reconsidered", section)

    def test_escalation_names_four_semantic_triggers_no_numeric_threshold(self) -> None:
        section = self.raw.split(
            "## 6. Escalation", 1
        )[1].split("## 7.", 1)[0]
        for trigger in (
            "**Prior assumptions invalidated**",
            "**Blast radius cannot be bounded**",
            "**Matching is broadly unreliable**",
            "**Reviewed-state preconditions are violated**",
        ):
            self.assertIn(trigger, section)
        self.assertIn("invents no numeric threshold", self.text)
        self.assertIn("When in doubt, escalate.", section)

    @staticmethod
    def _normalize(section: str) -> str:
        return " ".join(section.split())

    def test_exact_head_safety_forbids_stale_publication(self) -> None:
        section = self._normalize(
            self.raw.split("## 7. Exact-HEAD safety", 1)[1].split("## 8.", 1)[0]
        )
        for forbidden in (
            "do not publish findings",
            "REVIEW CLEAN",
            "machine-readable status",
            "GitHub review submission",
        ):
            self.assertIn(forbidden, section)

    def test_normal_severity_and_decision_derivation_unchanged(self) -> None:
        section = self._normalize(
            self.raw.split("## 8. Normal finding semantics", 1)[1].split("## 9.", 1)[0]
        )
        self.assertIn("no separate re-review severity scale", section)
        self.assertIn("a newly introduced P1 remains a P1", section)

    def test_output_reports_per_finding_lifecycle_state(self) -> None:
        section = self._normalize(
            self.raw.split("## 9. Output", 1)[1].split("## 10.", 1)[0]
        )
        self.assertIn(
            "`DETECTED`, `STILL_PRESENT`, `RESOLVED`, `REOPENED`, or `UNCERTAIN`",
            section,
        )

    def test_scope_boundaries_exclude_66_and_defer_identity_lifecycle_owners(self) -> None:
        section = self.raw.split("## 10. Scope boundaries", 1)[1]
        self.assertIn("[#66](https://github.com/amirbena/code-review-skill/issues/66)", section)
        # Owners are cited by Issue number only — never by the
        # unpackaged docs/findings/*.md basename (a packaged resource
        # must not depend on a repository-development doc; see
        # test_reviewed_sha_state_docs.CrossReferenceConsistencyTests).
        for owner_issue in ("| #59 |", "| #60 |", "| #62 |", "| #63 |", "| #64 |"):
            self.assertIn(owner_issue, section)
        self.assertIn("does not load this policy", section)

    def test_does_not_mention_unpackaged_docs_findings_basenames(self) -> None:
        for basename in (
            "reviewed-sha-state-contract",
            "finding-identity-requirements",
            "finding-matching-strategy",
            "finding-stable-identity",
            "finding-lifecycle-contract",
            "delta-re-review-contract",
        ):
            self.assertNotIn(basename, self.raw)

    def test_local_code_review_explicitly_excluded_as_stateless(self) -> None:
        section = self.raw.split("## 10. Scope boundaries", 1)[1]
        self.assertIn("architecturally\nstateless".replace("\n", " "), section.replace("\n", " "))


class WiringTests(unittest.TestCase):
    """The policy must actually be loaded, not merely exist on disk."""

    def test_skill_required_policy_loading_references_it(self) -> None:
        text = " ".join(SKILL.read_text(encoding="utf-8").split())
        self.assertIn("policies/stateful-delta-rereview.md", text)

    def test_canonical_index_lists_it_after_reviewer_delta_review(self) -> None:
        raw = INDEX.read_text(encoding="utf-8")
        self.assertIn("stateful-delta-rereview.md", raw)
        pos_delta = raw.index("reviewer-delta-review.md")
        pos_stateful = raw.index("stateful-delta-rereview.md")
        self.assertLess(pos_delta, pos_stateful)

    def test_reviewer_delta_review_links_forward_to_it(self) -> None:
        raw = DELTA_REVIEW.read_text(encoding="utf-8")
        self.assertIn("stateful-delta-rereview.md", raw)
        self.assertNotIn("delta-re-review-contract", raw)

    def test_local_code_review_skill_is_not_modified_to_load_it(self) -> None:
        text = LOCAL_SKILL.read_text(encoding="utf-8")
        self.assertNotIn("stateful-delta-rereview.md", text)

    def test_packaging_scripts_declare_the_new_policy_file(self) -> None:
        for script in (PACKAGE_SH, PACKAGE_PS1):
            self.assertIn(
                "policies/stateful-delta-rereview.md",
                script.read_text(encoding="utf-8"),
                script.name,
            )


if __name__ == "__main__":
    unittest.main()
