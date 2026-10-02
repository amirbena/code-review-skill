"""Shared composition-contract skeleton for domain-specific deepening policies.

Every ``shared/policies/*-deepening.md`` capability instantiates the same
contract from ``specialist-depth.md``. A test module declares one
``DeepeningDomain`` and subclasses ``DeepeningContractMixin`` alongside
``unittest.TestCase``; each domain keeps its own TestCase class, so a failure
names the domain module and policy file. Domain-specific worked examples and
concern-area content stay in the owning module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _norm

SPECIALIST_DEPTH = REPO_ROOT / "shared/policies/specialist-depth.md"
REVIEW_SCOPE = REPO_ROOT / "shared/policies/review-scope.md"
REMEDIATION_SCOPE = REPO_ROOT / "shared/policies/remediation-scope-boundary.md"
SEVERITY = REPO_ROOT / "shared/policies/severity.md"
EVIDENCE = REPO_ROOT / "shared/policies/evidence.md"
POLICIES_README = REPO_ROOT / "shared/policies/README.md"
FINDING_TMPL = REPO_ROOT / "shared/templates/finding.md"
PACKAGE_MANIFEST = REPO_ROOT / "scripts/packaging/package-manifest.json"


@dataclass(frozen=True)
class DeepeningDomain:
    policy: Path
    dimension: str
    never_decides: str
    implication_without_file: str
    concern_areas: tuple[str, ...]
    no_unbounded_audit: str
    no_second_schema: str
    generic_advice_rejected: str
    review_scope_absent: tuple[str, ...]

    @property
    def basename(self) -> str:
        return self.policy.name

    @property
    def capability_value(self) -> str:
        return self.policy.stem


class DeepeningContractMixin:
    domain: DeepeningDomain

    def setUp(self) -> None:
        self.text = _norm(self.domain.policy)

    def test_policy_declares_scope(self) -> None:
        self.assertIn(
            "Applies identically to local-code-review and github-pr-review",
            self.text,
        )
        self.assertIn(
            "domain-specific deepening capability under "
            "[specialist-depth.md](specialist-depth.md)'s composition "
            "contract",
            self.text,
        )

    def test_review_scope_routes_without_restating(self) -> None:
        name = self.domain.basename
        raw = REVIEW_SCOPE.read_text(encoding="utf-8")
        t = _norm(REVIEW_SCOPE)
        self.assertIn(
            f"[{name}]({name}) per the "
            '"Domain-specific deepening pass" below',
            t,
        )
        for phrase in self.domain.review_scope_absent:
            self.assertNotIn(phrase, t)
            self.assertNotIn(phrase, raw)
        self.assertIn("## Domain-specific deepening pass", raw)

    def test_policy_indexed_in_readme(self) -> None:
        raw = POLICIES_README.read_text(encoding="utf-8")
        self.assertIn(self.domain.basename, raw)

    def test_policy_indexed_in_package_manifest(self) -> None:
        manifest = json.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))
        self.assertIn(
            f"shared/policies/{self.domain.basename}", json.dumps(manifest)
        )

    def test_never_decides_whether_considered(self) -> None:
        self.assertIn(self.domain.never_decides, self.text)

    def test_does_not_redefine_base_detection(self) -> None:
        self.assertIn(
            "that detection does not start existing only once this "
            "capability engages",
            self.text,
        )

    def test_two_part_activation_condition(self) -> None:
        self.assertIn(
            "[review-scope.md](review-scope.md)'s base pass has already "
            f"identified a materially implicated {self.domain.dimension} "
            "dimension",
            self.text,
        )
        self.assertIn("the evidence gathered by that base pass", self.text)

    def test_signals_never_independently_sufficient(self) -> None:
        self.assertIn("does not by itself satisfy condition 2", self.text)

    def test_implication_without_expected_file_present(self) -> None:
        self.assertIn(self.domain.implication_without_file, self.text)

    def test_concern_areas_present(self) -> None:
        for phrase in self.domain.concern_areas:
            with self.subTest(concern_area=phrase):
                self.assertIn(phrase, self.text)

    def test_not_an_exhaustive_unconditional_checklist(self) -> None:
        self.assertIn(
            "not an exhaustive checklist run unconditionally on every "
            "activation",
            self.text,
        )

    def test_reuses_specialist_depth_and_repository_expansion(self) -> None:
        self.assertIn(
            "reuses [specialist-depth.md](specialist-depth.md)'s "
            "cascading-activation model, which in turn reuses "
            "[repository-expansion.md](repository-expansion.md)'s fixed "
            "trigger/ring/ ceiling procedure",
            self.text,
        )

    def test_no_unbounded_audit(self) -> None:
        self.assertIn(self.domain.no_unbounded_audit, self.text)

    def test_insufficient_evidence_remains_valid_terminal_outcome(self) -> None:
        self.assertIn(
            'Insufficient evidence" remains a valid terminal outcome',
            self.text,
        )

    def test_ordinary_finding_language(self) -> None:
        self.assertIn(
            "A finding this capability contributes is an ordinary finding",
            self.text,
        )

    def test_capability_provenance_field_named(self) -> None:
        self.assertIn(
            "the optional capability provenance field, valued "
            f"{self.domain.capability_value}",
            self.text,
        )

    def test_no_second_schema(self) -> None:
        self.assertIn(self.domain.no_second_schema, self.text)

    def test_generic_advice_rejected(self) -> None:
        self.assertIn(self.domain.generic_advice_rejected, self.text)

    def test_does_not_redefine_composition_or_remediation_scope(self) -> None:
        self.assertIn(
            "Does not redefine composition, cascading, or "
            "remediation-scope semantics",
            self.text,
        )

    def test_shared_worked_example_cases_present(self) -> None:
        for phrase in (
            "Does not engage — bounded base reasoning already suffices",
            "Misleading superficial signal",
            "Implication without the expected file/path",
            "Depth vs. remediation scope",
        ):
            with self.subTest(case=phrase):
                self.assertIn(phrase, self.text)

    def test_capability_field_documented_in_finding_template(self) -> None:
        raw = FINDING_TMPL.read_text(encoding="utf-8")
        self.assertIn("**capability** — optional", raw)
        self.assertIn("## Capability provenance", raw)

    def test_specialist_depth_owns_generic_labeling_rule(self) -> None:
        self.assertIn(
            "Capability-contributed findings are labeled, not re-schemed",
            _norm(SPECIALIST_DEPTH),
        )

    def test_defers_severity_and_evidence(self) -> None:
        policy_raw = self.domain.policy.read_text(encoding="utf-8")
        self.assertTrue(SEVERITY.read_text(encoding="utf-8").strip())
        self.assertTrue(EVIDENCE.read_text(encoding="utf-8").strip())
        self.assertNotIn("## Decision derivation", policy_raw)

    def test_defers_remediation_scope(self) -> None:
        remediation_raw = REMEDIATION_SCOPE.read_text(encoding="utf-8")
        policy_raw = self.domain.policy.read_text(encoding="utf-8")
        self.assertIn(
            "## Three-part reasoning (mandatory, per material finding)",
            remediation_raw,
        )
        self.assertNotIn("## Three-part reasoning", policy_raw)

    def test_every_consumer_names_the_policy(self) -> None:
        for path in (REVIEW_SCOPE, POLICIES_README):
            with self.subTest(consumer=path.name):
                raw = path.read_text(encoding="utf-8")
                self.assertIn(
                    self.domain.basename,
                    raw,
                    msg=f"{path} does not reference {self.domain.basename}",
                )

    def test_manifest_names_the_policy_file_exactly(self) -> None:
        manifest_raw = PACKAGE_MANIFEST.read_text(encoding="utf-8")
        self.assertIn(f"shared/policies/{self.domain.basename}", manifest_raw)
