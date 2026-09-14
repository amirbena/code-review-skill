#!/usr/bin/env python3
"""Tests for scripts/security/validate_threat_model.py (Issue #300).

Covers the threat-scenario-catalog/v1 parser/validator itself (malformed
input is rejected, well-formed input is accepted, cross-file invariants
hold) and drives it once over the real catalog under
docs/threat-model/catalog/ to prove the canonical scenario set is valid.
"""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

import yaml

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts" / "security"))

import validate_threat_model as vtm  # noqa: E402

CATALOG_DIR = REPO_ROOT / "docs" / "threat-model" / "catalog"


def _minimal_scenario(**overrides) -> dict:
    base = {
        "id": "AUTH-001",
        "title": "A read-only agent attempts direct mutation",
        "category": "AUTH",
        "attacker_model": "compromised_agent",
        "attacker_controlled_inputs": ["tool-call arguments"],
        "assumed_attacker_capabilities": ["arbitrary tool invocation"],
        "trusted_inputs": [],
        "protected_asset": "target repository working tree",
        "required_capability_state": "no APPLY_PATCH capability granted",
        "enforcement_owner": "#301",
        "enforcement_point": "runtime capability gate",
        "expected_safe_outcome": "the write is refused",
        "expected_security_event": "DENIED_MUTATION_CAPABILITY_ABSENT",
        "benchmark_family": "mutation/#305",
        "benchmark_reference": vtm.GAP,
        "regression_evidence": vtm.GAP,
        "threat_severity": "CRITICAL",
    }
    base.update(overrides)
    return base


class ParseScenarioAcceptsWellFormedInputTests(unittest.TestCase):
    def test_minimal_well_formed_scenario_parses(self) -> None:
        scenario = vtm.parse_scenario(_minimal_scenario())
        self.assertEqual(scenario.id, "AUTH-001")
        self.assertEqual(scenario.category, "AUTH")
        self.assertTrue(scenario.is_enforcement_gap is False)
        self.assertTrue(scenario.is_benchmark_gap)
        self.assertTrue(scenario.is_regression_gap)

    def test_notes_field_is_optional(self) -> None:
        scenario = vtm.parse_scenario(_minimal_scenario(notes="extra context"))
        self.assertEqual(scenario.notes, "extra context")
        scenario_no_notes = vtm.parse_scenario(_minimal_scenario())
        self.assertEqual(scenario_no_notes.notes, "")

    def test_full_coverage_gap_scenario_parses(self) -> None:
        scenario = vtm.parse_scenario(
            _minimal_scenario(
                enforcement_owner=vtm.GAP,
                enforcement_point=vtm.GAP,
                expected_security_event="NOT_APPLICABLE",
            )
        )
        self.assertEqual(scenario.enforcement_owner, vtm.GAP)
        self.assertEqual(scenario.expected_security_event, "NOT_APPLICABLE")

    def test_existing_owner_citation_is_accepted(self) -> None:
        scenario = vtm.parse_scenario(
            _minimal_scenario(
                enforcement_owner="existing: tests/reference/review/pr_checkout.py",
                enforcement_point="core.hooksPath=/dev/null on every git call",
                regression_evidence="tests/integration/github/test_pr_checkout.py",
            )
        )
        self.assertTrue(scenario.enforcement_owner.startswith("existing:"))

    def test_benchmark_family_none_with_justification_is_accepted(self) -> None:
        scenario = vtm.parse_scenario(
            _minimal_scenario(
                benchmark_family="none",
                benchmark_reference="reasoning-discipline scenario, not a runtime capability boundary",
            )
        )
        self.assertEqual(scenario.benchmark_family, ("none",))

    def test_combined_benchmark_family_is_accepted(self) -> None:
        scenario = vtm.parse_scenario(
            _minimal_scenario(benchmark_family="mutation/#305, delegation/#307")
        )
        self.assertEqual(scenario.benchmark_family, ("mutation/#305", "delegation/#307"))


class ParseScenarioRejectsMalformedInputTests(unittest.TestCase):
    def test_rejects_unknown_category(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(_minimal_scenario(id="ZZZZ-001", category="ZZZZ"))

    def test_rejects_id_category_mismatch(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(_minimal_scenario(id="AUTH-001", category="SBOX"))

    def test_rejects_malformed_id_shape(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(_minimal_scenario(id="AUTH-1"))

    def test_rejects_unknown_attacker_model(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(_minimal_scenario(attacker_model="evil_hacker"))

    def test_rejects_unknown_threat_severity(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(_minimal_scenario(threat_severity="SEV1"))

    def test_rejects_review_finding_severity_collision(self) -> None:
        for token in ("P0", "P1", "P2"):
            with self.subTest(token=token):
                with self.assertRaises(vtm.ThreatModelFormatError):
                    vtm.parse_scenario(_minimal_scenario(threat_severity=token))

    def test_rejects_unknown_security_event(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(_minimal_scenario(expected_security_event="MADE_UP_EVENT"))

    def test_rejects_unknown_benchmark_family(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(_minimal_scenario(benchmark_family="made-up-family"))

    def test_rejects_benchmark_family_none_combined_with_real_family(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(_minimal_scenario(benchmark_family="none, mutation/#305"))

    def test_rejects_benchmark_family_none_with_coverage_gap_reference(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(
                _minimal_scenario(benchmark_family="none", benchmark_reference=vtm.GAP)
            )

    def test_rejects_missing_required_field(self) -> None:
        scenario = _minimal_scenario()
        del scenario["protected_asset"]
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(scenario)

    def test_rejects_unknown_field(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(_minimal_scenario(unexpected_field="surprise"))

    def test_rejects_empty_attacker_controlled_inputs(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(_minimal_scenario(attacker_controlled_inputs=[]))

    def test_rejects_invented_looking_reference(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(
                _minimal_scenario(regression_evidence="probably somewhere in the codebase")
            )

    def test_accepts_issue_reference_as_regression_evidence(self) -> None:
        scenario = vtm.parse_scenario(_minimal_scenario(regression_evidence="tracked by #305"))
        self.assertIn("#305", scenario.regression_evidence)

    def test_rejects_enforcement_owner_point_disagreement(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(
                _minimal_scenario(enforcement_owner=vtm.GAP, enforcement_point="a real check")
            )

    def test_rejects_review_verdict_language_leaking_in(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_scenario(
                _minimal_scenario(expected_safe_outcome="the result becomes REVIEW CLEAN")
            )


class CatalogFileParsingTests(unittest.TestCase):
    def test_rejects_unsupported_format(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_catalog_file({"format": "threat-scenario-catalog/v2", "category": "AUTH", "scenarios": [_minimal_scenario()]})

    def test_rejects_category_mismatch_between_file_and_scenario(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_catalog_file(
                {
                    "format": "threat-scenario-catalog/v1",
                    "category": "SBOX",
                    "scenarios": [_minimal_scenario()],
                }
            )

    def test_rejects_empty_scenarios_list(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.parse_catalog_file({"format": "threat-scenario-catalog/v1", "category": "AUTH", "scenarios": []})

    def test_well_formed_file_parses(self) -> None:
        scenarios = vtm.parse_catalog_file(
            {"format": "threat-scenario-catalog/v1", "category": "AUTH", "scenarios": [_minimal_scenario()]}
        )
        self.assertEqual(len(scenarios), 1)


class LoadCatalogCrossFileInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = self.enterContext(_temp_dir())

    def _write(self, name: str, doc: dict) -> None:
        with open(self.tmpdir / name, "w", encoding="utf-8") as fh:
            yaml.safe_dump(doc, fh)

    def test_rejects_duplicate_ids_across_files(self) -> None:
        doc = {"format": "threat-scenario-catalog/v1", "category": "AUTH", "scenarios": [_minimal_scenario()]}
        self._write("a.yaml", doc)
        self._write("b.yaml", doc)
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.load_catalog(self.tmpdir)

    def test_rejects_missing_category_coverage(self) -> None:
        doc = {"format": "threat-scenario-catalog/v1", "category": "AUTH", "scenarios": [_minimal_scenario()]}
        self._write("a.yaml", doc)
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.load_catalog(self.tmpdir)

    def test_rejects_empty_catalog_directory(self) -> None:
        with self.assertRaises(vtm.ThreatModelFormatError):
            vtm.load_catalog(self.tmpdir)


@contextlib.contextmanager
def _temp_dir():
    import tempfile

    with tempfile.TemporaryDirectory() as raw:
        yield Path(raw)


class RealCatalogTests(unittest.TestCase):
    """Drives the validator over the real, canonical catalog."""

    def setUp(self) -> None:
        self.assertTrue(CATALOG_DIR.is_dir(), f"missing {CATALOG_DIR}")
        self.scenarios = vtm.load_catalog(CATALOG_DIR)

    def test_catalog_loads_and_validates(self) -> None:
        self.assertGreaterEqual(len(self.scenarios), 60)

    def test_every_category_is_present(self) -> None:
        present = {sc.category for sc in self.scenarios}
        self.assertEqual(present, vtm.CATEGORIES)

    def test_all_ids_are_unique(self) -> None:
        ids = [sc.id for sc in self.scenarios]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_scenario_uses_review_finding_severity(self) -> None:
        for sc in self.scenarios:
            self.assertNotIn(sc.threat_severity, vtm.REVIEW_FINDING_SEVERITIES)

    def test_gap_and_real_scenarios_both_exist(self) -> None:
        # The catalog must document real existing coverage (not everything is a
        # gap) and honestly track genuine gaps (not everything is claimed done).
        self.assertTrue(any(sc.is_enforcement_gap for sc in self.scenarios))
        self.assertTrue(any(not sc.is_enforcement_gap for sc in self.scenarios))

    def test_auth_scenarios_are_owned_by_301_or_existing(self) -> None:
        auth = [sc for sc in self.scenarios if sc.category == "AUTH"]
        self.assertGreaterEqual(len(auth), 10)
        for sc in auth:
            self.assertTrue(
                "#301" in sc.enforcement_owner
                or sc.enforcement_owner.startswith("existing:")
                or "#303" in sc.enforcement_owner,
                f"{sc.id} has unexpected enforcement_owner {sc.enforcement_owner!r}",
            )

    def test_sbox_scenarios_are_owned_by_302(self) -> None:
        sbox = [sc for sc in self.scenarios if sc.category == "SBOX"]
        self.assertGreaterEqual(len(sbox), 10)
        for sc in sbox:
            self.assertIn("#302", sc.enforcement_owner)

    def test_deleg_scenarios_are_owned_by_303(self) -> None:
        deleg = [sc for sc in self.scenarios if sc.category == "DELEG"]
        self.assertGreaterEqual(len(deleg), 8)
        for sc in deleg:
            self.assertIn("#303", sc.enforcement_owner)

    def test_git_checkout_hooks_scenario_cites_real_evidence(self) -> None:
        by_id = {sc.id: sc for sc in self.scenarios}
        self.assertIn("GIT-001", by_id)
        git_001 = by_id["GIT-001"]
        self.assertNotEqual(git_001.regression_evidence, vtm.GAP)
        self.assertIn("pr_checkout", git_001.regression_evidence)

    def test_self_review_scenario_cites_real_evidence_not_301(self) -> None:
        by_id = {sc.id: sc for sc in self.scenarios}
        self.assertIn("AUTH-014", by_id)
        auth_014 = by_id["AUTH-014"]
        self.assertNotEqual(auth_014.regression_evidence, vtm.GAP)
        self.assertTrue(auth_014.enforcement_owner.startswith("existing:"))


class MainCliTests(unittest.TestCase):
    def test_main_exits_zero_and_prints_a_summary_for_the_real_catalog(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vtm.main(["--catalog-dir", str(CATALOG_DIR)])
        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("OK:", output)
        self.assertIn("coverage gaps", output)

    def test_main_exits_nonzero_on_invalid_catalog(self) -> None:
        with _temp_dir() as tmp:
            with open(tmp / "bad.yaml", "w", encoding="utf-8") as fh:
                yaml.safe_dump({"format": "not-a-real-format"}, fh)
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                rc = vtm.main(["--catalog-dir", str(tmp)])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
