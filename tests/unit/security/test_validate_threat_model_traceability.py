#!/usr/bin/env python3
"""Tests for scripts/security/validate_threat_model_traceability.py (Issue #310).

Covers `coverage_state` derivation, drift detection (stale scenario ids,
claimed-but-missing benchmark cases, unrationalized high-severity gaps),
and drives it once over the real catalog and real benchmark corpora to
prove the current landed state is drift-free -- mirroring
tests/unit/security/test_validate_threat_model.py's own real-catalog
smoke test.
"""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts" / "security"))

import validate_threat_model as vtm  # noqa: E402
import validate_threat_model_traceability as vtt  # noqa: E402

CATALOG_DIR = REPO_ROOT / "docs" / "threat-model" / "catalog"


def _scenario(**overrides) -> vtm.ThreatScenario:
    base = dict(
        id="AUTH-001",
        title="A read-only agent attempts direct mutation",
        category="AUTH",
        attacker_model="compromised_agent",
        attacker_controlled_inputs=("tool-call arguments",),
        assumed_attacker_capabilities=("arbitrary tool invocation",),
        trusted_inputs=(),
        protected_asset="target repository working tree",
        required_capability_state="no APPLY_PATCH capability granted",
        enforcement_owner="#301",
        enforcement_point="runtime capability gate",
        expected_safe_outcome="the write is refused",
        expected_security_event="DENIED_MUTATION_CAPABILITY_ABSENT",
        benchmark_family=("mutation/#305",),
        benchmark_reference="tests/reference/benchmark/mutation_fixtures.py",
        regression_evidence="tests/unit/security/test_mutation_authority.py",
        threat_severity="CRITICAL",
        notes="",
    )
    base.update(overrides)
    return vtm.ThreatScenario(**base)


def _case(threat_scenario_ids: tuple[str, ...]) -> SimpleNamespace:
    return SimpleNamespace(threat_scenario_ids=threat_scenario_ids)


class CoverageStateTests(unittest.TestCase):
    def test_gap_when_enforcement_owner_is_gap(self) -> None:
        sc = _scenario(enforcement_owner=vtm.GAP, enforcement_point=vtm.GAP)
        self.assertEqual(vtt.coverage_state(sc), "gap")

    def test_covered_when_benchmark_and_regression_are_real(self) -> None:
        sc = _scenario()
        self.assertEqual(vtt.coverage_state(sc), "covered")

    def test_partial_when_benchmark_reference_is_gap(self) -> None:
        sc = _scenario(benchmark_reference=vtm.GAP)
        self.assertEqual(vtt.coverage_state(sc), "partial")

    def test_partial_when_regression_evidence_is_gap(self) -> None:
        sc = _scenario(regression_evidence=vtm.GAP)
        self.assertEqual(vtt.coverage_state(sc), "partial")

    def test_not_applicable_when_family_is_none_and_regression_is_real(self) -> None:
        sc = _scenario(
            benchmark_family=("none",),
            benchmark_reference="reasoning-discipline scenario; no benchmark applies",
        )
        self.assertEqual(vtt.coverage_state(sc), "not-applicable-to-benchmark")

    def test_partial_when_family_is_none_but_regression_is_also_gap(self) -> None:
        sc = _scenario(
            benchmark_family=("none",),
            benchmark_reference="reasoning-discipline scenario; no benchmark applies",
            regression_evidence=vtm.GAP,
        )
        self.assertEqual(vtt.coverage_state(sc), "partial")


class CorpusScenarioIdExtractionTests(unittest.TestCase):
    def test_extracts_real_scenario_ids(self) -> None:
        cases = [_case(("AUTH-001",)), _case(("AUTH-002", "DOS-006"))]
        self.assertEqual(vtt._corpus_scenario_ids(cases), frozenset({"AUTH-001", "AUTH-002", "DOS-006"}))

    def test_ignores_existing_policy_citations(self) -> None:
        cases = [_case(("existing:skills/github-pr-review/policies/review-action-authorization.md",))]
        self.assertEqual(vtt._corpus_scenario_ids(cases), frozenset())

    def test_mixed_case_keeps_only_the_real_id(self) -> None:
        cases = [_case(("AUTH-014", "existing:some/policy.md"))]
        self.assertEqual(vtt._corpus_scenario_ids(cases), frozenset({"AUTH-014"}))


class DriftDetectionTests(unittest.TestCase):
    def test_no_drift_when_every_claim_is_backed(self) -> None:
        scenarios = [_scenario()]
        family_ids = {"mutation/#305": frozenset({"AUTH-001"})}
        rows, drift = vtt.build_traceability(scenarios, family_corpus_ids=family_ids)
        self.assertEqual(drift, [])
        self.assertEqual(rows[0].coverage_state, "covered")

    def test_stale_scenario_id_referenced_by_a_corpus_is_flagged(self) -> None:
        scenarios = [_scenario()]
        family_ids = {"mutation/#305": frozenset({"AUTH-001", "AUTH-999"})}
        _, drift = vtt.build_traceability(scenarios, family_corpus_ids=family_ids)
        self.assertTrue(any("AUTH-999" in d and "stale" in d for d in drift))

    def test_claimed_benchmark_reference_with_no_backing_case_is_flagged(self) -> None:
        # benchmark_reference is a real (non-GAP) claim, but the family's corpus
        # never actually references this scenario id back.
        scenarios = [_scenario(benchmark_reference="tests/reference/benchmark/mutation_fixtures.py")]
        family_ids = {"mutation/#305": frozenset()}
        _, drift = vtt.build_traceability(scenarios, family_corpus_ids=family_ids)
        self.assertTrue(any("AUTH-001" in d and "no case" in d for d in drift))

    def test_honest_coverage_gap_claim_is_not_flagged_as_drift(self) -> None:
        # benchmark_family names the intended future owner, but
        # benchmark_reference is honestly still COVERAGE_GAP -- not a claim to
        # verify yet, so an empty corpus must not be reported as drift.
        scenarios = [
            _scenario(
                benchmark_family=("sandbox/#306",),
                benchmark_reference=vtm.GAP,
                regression_evidence=vtm.GAP,
                enforcement_owner="#302",
                threat_severity="MEDIUM",
            )
        ]
        family_ids = {"sandbox/#306": frozenset()}
        _, drift = vtt.build_traceability(scenarios, family_corpus_ids=family_ids)
        self.assertEqual(drift, [])

    def test_unknown_benchmark_family_is_flagged(self) -> None:
        scenarios = [_scenario(benchmark_family=("mutation/#305",))]
        _, drift = vtt.build_traceability(scenarios, family_corpus_ids={})
        self.assertTrue(any("does not know how to cross-reference" in d for d in drift))

    def test_high_severity_gap_without_notes_is_flagged(self) -> None:
        scenarios = [
            _scenario(
                enforcement_owner=vtm.GAP,
                enforcement_point=vtm.GAP,
                benchmark_reference=vtm.GAP,
                regression_evidence=vtm.GAP,
                threat_severity="HIGH",
                notes="",
            )
        ]
        _, drift = vtt.build_traceability(scenarios, family_corpus_ids={"mutation/#305": frozenset()})
        self.assertTrue(any("no `notes` rationale" in d for d in drift))

    def test_high_severity_gap_with_notes_is_not_flagged_for_rationale(self) -> None:
        scenarios = [
            _scenario(
                enforcement_owner=vtm.GAP,
                enforcement_point=vtm.GAP,
                benchmark_reference=vtm.GAP,
                regression_evidence=vtm.GAP,
                threat_severity="HIGH",
                notes="Gap: no structural check exists yet for this reasoning-discipline property.",
            )
        ]
        _, drift = vtt.build_traceability(scenarios, family_corpus_ids={"mutation/#305": frozenset()})
        self.assertFalse(any("no `notes` rationale" in d for d in drift))

    def test_medium_severity_gap_without_notes_is_not_flagged(self) -> None:
        # The rationale requirement only applies to CRITICAL/HIGH -- #310
        # asks for high-impact gaps to stay visible, not every gap.
        scenarios = [
            _scenario(
                enforcement_owner=vtm.GAP,
                enforcement_point=vtm.GAP,
                benchmark_reference=vtm.GAP,
                regression_evidence=vtm.GAP,
                threat_severity="MEDIUM",
                notes="",
            )
        ]
        _, drift = vtt.build_traceability(scenarios, family_corpus_ids={"mutation/#305": frozenset()})
        self.assertEqual(drift, [])

    def test_not_applicable_to_benchmark_never_needs_notes(self) -> None:
        # Its rationale already lives in benchmark_reference (required by the
        # catalog schema whenever benchmark_family is "none").
        scenarios = [
            _scenario(
                benchmark_family=("none",),
                benchmark_reference="reasoning-discipline scenario; no benchmark applies",
                threat_severity="CRITICAL",
                notes="",
            )
        ]
        _, drift = vtt.build_traceability(scenarios, family_corpus_ids={})
        self.assertEqual(drift, [])


class SandboxReadmeParsingTests(unittest.TestCase):
    def test_extracts_only_ids_inside_the_coverage_section(self) -> None:
        with _temp_readme(
            "# Sandbox Adversarial Benchmark\n\n"
            "Mentions SBOX-999 in prose before the table, which must not count.\n\n"
            "## Coverage\n\n"
            "| `SBOX-###` | Threat | Case(s) |\n"
            "| --- | --- | --- |\n"
            "| SBOX-001 | outbound HTTP | `test_sbox_001` |\n"
            "| SBOX-002 | DNS | `test_sbox_002` |\n\n"
            "## Invariant this corpus exists to guard\n\n"
            "SBOX-888 mentioned after the table must not count either.\n"
        ) as path:
            ids = vtt.sandbox_readme_scenario_ids(path)
        self.assertEqual(ids, frozenset({"SBOX-001", "SBOX-002"}))

    def test_missing_coverage_section_raises(self) -> None:
        with _temp_readme("# No coverage section here\n") as path:
            with self.assertRaises(vtt.TraceabilityError):
                vtt.sandbox_readme_scenario_ids(path)

    def test_real_sandbox_readme_parses(self) -> None:
        ids = vtt.sandbox_readme_scenario_ids()
        self.assertGreaterEqual(len(ids), 10)
        self.assertTrue(all(vtt._SCENARIO_ID_RE.match(i) for i in ids))


@contextlib.contextmanager
def _temp_readme(text: str):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "README.md"
        path.write_text(text, encoding="utf-8")
        yield path


class RealCatalogAndCorporaTests(unittest.TestCase):
    """Drive the validator over the real, landed catalog and corpora -- the
    same smoke-test discipline test_validate_threat_model.py applies to the
    schema validator itself."""

    def setUp(self) -> None:
        self.scenarios = vtm.load_catalog(CATALOG_DIR)

    def test_real_catalog_and_corpora_have_no_traceability_drift(self) -> None:
        rows, drift = vtt.build_traceability(self.scenarios)
        self.assertEqual(drift, [], f"unexpected traceability drift: {drift}")
        self.assertEqual(len(rows), len(self.scenarios))

    def test_every_row_has_a_valid_coverage_state(self) -> None:
        rows, _ = vtt.build_traceability(self.scenarios)
        for row in rows:
            self.assertIn(row.coverage_state, vtt.COVERAGE_STATES)

    def test_seeding_a_stale_id_is_caught(self) -> None:
        # Prove the validator actually reports a seeded gap/drift, not just
        # that the real catalog happens to be clean (#310's own validation
        # bullet: "seed one missing mapping and prove validation reports it").
        family_ids = {
            "mutation/#305": frozenset({"AUTH-NOTREAL-999"}),
            "delegation/#307": frozenset(),
            "security-event/#308": frozenset(),
            "sandbox/#306": frozenset(),
        }
        _, drift = vtt.build_traceability(self.scenarios, family_corpus_ids=family_ids)
        self.assertTrue(any("AUTH-NOTREAL-999" in d for d in drift))

    def test_seeding_an_overclaimed_benchmark_reference_is_caught(self) -> None:
        scenarios = list(self.scenarios)
        victim = next(sc for sc in scenarios if sc.category == "AUTH" and sc.benchmark_reference != vtm.GAP)
        seeded = replace(victim, benchmark_family=("delegation/#307",))
        scenarios[scenarios.index(victim)] = seeded
        _, drift = vtt.build_traceability(scenarios)
        self.assertTrue(any(seeded.id in d for d in drift))


class MainCliTests(unittest.TestCase):
    def test_main_exits_zero_and_prints_a_summary_for_the_real_catalog(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vtt.main(["--catalog-dir", str(CATALOG_DIR)])
        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("OK:", output)
        self.assertIn("covered:", output)

    def test_main_filters_to_one_scenario(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = vtt.main(["--catalog-dir", str(CATALOG_DIR), "--scenario", "AUTH-001"])
        self.assertEqual(rc, 0)
        output = buf.getvalue()
        self.assertIn("AUTH-001", output)
        self.assertNotIn("AUTH-002", output)

    def test_main_exits_nonzero_for_unknown_scenario(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = vtt.main(["--catalog-dir", str(CATALOG_DIR), "--scenario", "NOPE-000"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
