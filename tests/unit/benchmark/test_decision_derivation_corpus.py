#!/usr/bin/env python3
"""Contract coverage for the Decision-Derivation benchmark sub-corpus
(Issue #450, regression guard for the closed Issue #449 / PR #452).

The sub-corpus is
``docs/benchmark/corpus/decision-derivation/*.yaml``: a small,
focused set of ``benchmark-case/v2`` fixtures pinning the *reverse*
direction of ``shared/policies/severity.md``'s mechanical severity →
decision derivation — a P2-only, or empty, finding set must always render
`clean`, never `changes-required`. Issue #350 (open) owns the opposite,
forward-direction proof; this sub-corpus never duplicates it.

Like ``test_database_migration_deepening_corpus.py`` and
``test_distributed_systems_deepening_corpus.py``, every fixture decodes
and validates through the *same* single reference validator
(``tests/reference/benchmark/benchmark_fixture.py``) used for every other
corpus — this module never defines a second one.

This module additionally drives every fixture through the real packaged
Skill end-to-end via ``ProductionReviewerAdapter``, gated on the same
``check_runtime_available`` preflight ``test_production_adapter_e2e.py``
uses: the real-runtime path fails loudly with a clear skip reason rather
than being silently skipped without explanation or fabricating a result.
"""

from __future__ import annotations

import unittest

import yaml

from tests.reference.benchmark import benchmark_fixture as bf
from tests.reference.benchmark import benchmark_runner as br
from tests.reference.review import decision_semantics as ds
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus" / "decision-derivation"

MILD_WORDING = "dd-p2-only-mild-wording"
URGENT_WORDING = "dd-p2-only-urgent-wording"
ZERO_FINDINGS = "dd-zero-findings-clean"

REQUIRED_CASE_IDS = {MILD_WORDING, URGENT_WORDING, ZERO_FINDINGS}

# Deliberately alarming/blocking-sounding fragments #449's regression
# shape hinges on. Regenerating this list from the fixture would make the
# assertion vacuous — it must be an independent expectation.
URGENT_WORDING_MARKERS = ("CRITICAL", "must be fixed before merge", "blocking violation")

MIN_CASES = 3
MAX_CASES = 3


def _corpus_files() -> list:
    return sorted(CORPUS_DIR.glob("*.yaml"))


def _load(path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class SubCorpusPresenceTests(unittest.TestCase):
    def test_directory_exists_with_a_readme(self) -> None:
        self.assertTrue(CORPUS_DIR.is_dir(), f"missing {CORPUS_DIR}")
        self.assertTrue((CORPUS_DIR / "README.md").is_file())

    def test_sub_corpus_is_small(self) -> None:
        n = len(_corpus_files())
        self.assertGreaterEqual(n, MIN_CASES, "a required case went missing")
        self.assertLessEqual(n, MAX_CASES, "sub-corpus is growing beyond #450's three named outcome shapes")


class SubCorpusCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no decision-derivation fixtures found")

    def test_every_file_parses_and_validates(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertEqual(case.format, "benchmark-case/v2")

    def test_filename_stem_matches_case_id(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertEqual(case.id, path.stem)

    def test_case_ids_are_unique(self) -> None:
        ids = [bf.parse_case(_load(p)).id for p in self.files]
        self.assertEqual(len(ids), len(set(ids)), "duplicate case id in sub-corpus")

    def test_every_case_records_a_rationale_and_tags(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                rationale = case.metadata.get("rationale", "")
                self.assertTrue(
                    isinstance(rationale, str) and rationale.strip(),
                    "case-selection rationale must be recorded in metadata",
                )
                self.assertTrue(
                    case.metadata.get("tags"), "case must carry >=1 category tag"
                )

    def test_patch_case_anchors_occur_in_the_diff_or_base(self) -> None:
        for path in self.files:
            case = bf.parse_case(_load(path))
            if case.input_kind != "patch":
                continue
            patch = case.input["patch"]
            base = case.input.get("base") or {}
            base_text = "\n".join(base.values())
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    locs = [spec.location, *(a.get("location") for a in spec.alternatives)]
                    for loc in locs:
                        anchor = (loc or {}).get("anchor")
                        if anchor:
                            with self.subTest(case=path.name, anchor=anchor):
                                self.assertIn(anchor, patch + base_text)

    def test_every_case_pins_an_explicit_consistent_decision(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertIsNotNone(
                    case.decision, "cases state `decision` as a cross-check"
                )
                self.assertEqual(case.decision, case.derived_decision)


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(_load(p)) for p in _corpus_files()}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_every_case_expects_clean(self) -> None:
        # The entire point of #450: severity, never wording or finding
        # count, is what may move the decision -- every case here must
        # land on `clean`.
        for case_id, case in self.by_id.items():
            with self.subTest(case=case_id):
                self.assertEqual(case.decision, "clean")

    def test_no_case_carries_a_required_p0_or_p1_finding(self) -> None:
        # This corpus is the reverse-polarity proof; a P0/P1 anywhere here
        # would be #350's (opposite-direction) concern, not this one's.
        for case_id, case in self.by_id.items():
            for finding in case.findings:
                if not finding.required:
                    continue
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    with self.subTest(case=case_id, finding=finding.key):
                        for severity in spec.severities:
                            self.assertEqual(severity, "P2")

    def test_zero_findings_case_carries_no_finding_at_all(self) -> None:
        case = self.by_id[ZERO_FINDINGS]
        self.assertEqual(list(case.findings), [])

    def test_p2_only_cases_each_carry_exactly_one_required_finding(self) -> None:
        for case_id in (MILD_WORDING, URGENT_WORDING):
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(len(required), 1)
                self.assertEqual(required[0].severities, ("P2",))

    def test_urgent_wording_case_actually_reads_as_urgent(self) -> None:
        # Guards against the fixture silently regressing into unremarkable
        # wording, which would make it indistinguishable from the mild
        # control case and defeat the point of pinning #449's shape.
        case = self.by_id[URGENT_WORDING]
        finding = case.findings[0]
        claim = finding.claim or ""
        for marker in URGENT_WORDING_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, claim)

    def test_mild_wording_case_does_not_read_as_urgent(self) -> None:
        case = self.by_id[MILD_WORDING]
        finding = case.findings[0]
        claim = finding.claim or ""
        for marker in URGENT_WORDING_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, claim)

    def test_every_case_is_tagged_quality_or_no_op(self) -> None:
        for case in self.by_id.values():
            tags = case.metadata.get("tags", [])
            self.assertTrue(set(tags) & {"quality", "no-op"})


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_every_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_cross_references(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("#450", text)
        self.assertIn("#350", text)
        self.assertIn("#449", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../tests/reference/benchmark/benchmark_fixture.py)", self.raw
        )


def _probe_runtime() -> str | None:
    """Return None if the real review runtime is actually usable, else a
    human-readable reason it is not (used as the skip reason). Delegates
    to the same ``check_runtime_available`` preflight
    ``test_production_adapter_e2e.py`` and the production entrypoint use,
    so this sub-corpus exercises the identical binding/probe path rather
    than a second, hand-rolled one."""
    try:
        from scripts.benchmark.benchmark_review_adapter import check_runtime_available

        check_runtime_available()
    except Exception as exc:  # noqa: BLE001 - re-raised as a skip reason, never swallowed
        return str(exc)
    return None


_SKIP_REASON = _probe_runtime()


@unittest.skipUnless(
    _SKIP_REASON is None,
    f"skipping the live end-to-end path rather than fabricating a result — {_SKIP_REASON}",
)
class SubCorpusEndToEndTests(unittest.TestCase):
    """Drives every fixture through the real packaged Skill and asserts
    the decision mechanically derived from the *produced* findings is
    `Decision.CLEAN` — the actual acceptance criterion #450 asks for, not
    merely that the fixtures' own declared expectations are internally
    consistent (that is ``SubCorpusCaseTests`` above)."""

    def test_real_run_derives_clean_for_every_case(self) -> None:
        from scripts.benchmark.benchmark_review_adapter import ProductionReviewerAdapter

        cases = [bf.parse_case(_load(p)) for p in _corpus_files()]
        adapter = ProductionReviewerAdapter(timeout=600.0)
        run_result = br.run_cases(cases, adapter)

        self.assertTrue(run_result.ok, run_result.error)
        self.assertEqual(len(run_result.case_results), len(cases))
        for case_result in run_result.case_results:
            with self.subTest(case=case_result.id):
                self.assertEqual(case_result.status, "executed")
                findings = tuple(
                    ds.Finding(id=str(i), severity=ds.Severity(f.severity))
                    for i, f in enumerate(case_result.produced_findings)
                )
                self.assertEqual(ds.derive_decision(findings), ds.Decision.CLEAN)


if __name__ == "__main__":
    unittest.main()
