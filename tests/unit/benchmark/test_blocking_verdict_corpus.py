#!/usr/bin/env python3
"""Coverage for the blocking-verdict benchmark fixtures (Issue #350).

The fixtures are ``docs/benchmark/corpus/decision-derivation/dd-blocking-*.yaml``:
unambiguous P0/P1 defects whose real-run rendered Result and Decision must
be the blocking value, never clean. Fixtures decode through the single
reference validator; the rendered-verdict check is
``runtime_platform/benchmark/reference/benchmark_blocking_verdict.py``.
"""

from __future__ import annotations

import stat
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

from runtime_platform.benchmark.reference import benchmark_blocking_verdict as bbv
from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_runner as br
from runtime_platform.benchmark.scripts.benchmark_review_adapter import (
    ProductionReviewerAdapter,
    parse_rendered_outcome,
)
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus" / "decision-derivation"

P0_CASE = "dd-blocking-p0-sql-injection"
P1_CASE = "dd-blocking-p1-inverted-error-rate"
REQUIRED_CASE_IDS = {P0_CASE, P1_CASE}
BLOCKING = {"P0", "P1"}


def _corpus_files() -> list[Path]:
    return sorted(CORPUS_DIR.glob("dd-blocking-*.yaml"))


def _load(path: Path) -> bf.BenchmarkCase:
    return bf.parse_case(yaml.safe_load(path.read_text(encoding="utf-8")))


class BlockingFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: _load(p) for p in _corpus_files()}

    def test_required_cases_are_present(self) -> None:
        self.assertEqual(set(self.by_id), REQUIRED_CASE_IDS)

    def test_filename_stem_matches_case_id(self) -> None:
        for path in _corpus_files():
            with self.subTest(case=path.name):
                self.assertEqual(_load(path).id, path.stem)

    def test_every_case_expects_changes_required(self) -> None:
        for case_id, case in self.by_id.items():
            with self.subTest(case=case_id):
                self.assertEqual(case.decision, "changes-required")
                self.assertEqual(case.derived_decision, "changes-required")

    def test_every_case_has_a_required_blocking_finding(self) -> None:
        for case_id, case in self.by_id.items():
            required = [f for f in case.findings if f.required]
            with self.subTest(case=case_id):
                self.assertEqual(len(required), 1)
                self.assertTrue(set(required[0].severities) <= BLOCKING)

    def test_both_blocking_severities_are_represented(self) -> None:
        self.assertEqual(self.by_id[P0_CASE].findings[0].severities, ("P0",))
        self.assertIn("P1", self.by_id[P1_CASE].findings[0].severities)

    def test_every_case_records_a_rationale_and_tags(self) -> None:
        for case_id, case in self.by_id.items():
            with self.subTest(case=case_id):
                self.assertTrue(str(case.metadata.get("rationale", "")).strip())
                self.assertTrue(case.metadata.get("tags"))

    def test_required_finding_anchors_occur_in_the_patch(self) -> None:
        for case_id, case in self.by_id.items():
            anchor = case.findings[0].location["anchor"]
            with self.subTest(case=case_id):
                self.assertIn(anchor, case.input["patch"])

    def test_patches_apply_in_an_isolated_workspace(self) -> None:
        for case_id, case in self.by_id.items():
            with self.subTest(case=case_id):
                result = br.run_case(case, lambda workspace: [])
                self.assertEqual(result.status, "executed", result.error)


class RenderedLabelClassificationTests(unittest.TestCase):
    def test_local_and_github_wordings_classify(self) -> None:
        expected = {
            "REVIEW CLEAN": bbv.RenderedKind.CLEAN,
            "✅ Review Clean": bbv.RenderedKind.CLEAN,
            "Approve": bbv.RenderedKind.CLEAN,
            "APPROVE": bbv.RenderedKind.CLEAN,
            "CHANGES REQUIRED": bbv.RenderedKind.BLOCKING,
            "⚠️ Changes Requested": bbv.RenderedKind.BLOCKING,
            "Request Changes": bbv.RenderedKind.BLOCKING,
            "REQUEST_CHANGES": bbv.RenderedKind.BLOCKING,
            "REVIEW INCOMPLETE": bbv.RenderedKind.INCOMPLETE,
        }
        for label, kind in expected.items():
            with self.subTest(label=label):
                self.assertEqual(bbv.classify_rendered_label(label), kind)

    def test_absent_empty_or_ambiguous_labels_are_unrecognized(self) -> None:
        for label in (None, "", "COMMENT", "Approve — changes requested"):
            with self.subTest(label=label):
                self.assertEqual(bbv.classify_rendered_label(label), bbv.RenderedKind.UNRECOGNIZED)


class BlockingVerdictCheckTests(unittest.TestCase):
    def test_blocking_finding_with_blocking_surfaces_is_ok(self) -> None:
        for severities in (["P0"], ["P1"], ["P2", "P1"]):
            for result, decision in (
                ("⚠️ Changes Requested", "CHANGES REQUIRED"),
                ("Request Changes", "REQUEST_CHANGES"),
            ):
                with self.subTest(severities=severities, decision=decision):
                    check = bbv.check_blocking_verdict(
                        severities, result_label=result, decision_label=decision
                    )
                    self.assertTrue(check.blocking_produced)
                    self.assertTrue(check.ok, check.violations)

    def test_blocking_finding_rendered_clean_is_a_violation(self) -> None:
        for severity in ("P0", "P1"):
            for result, decision in (
                ("✅ Review Clean", "REVIEW CLEAN"),
                ("Approve", "APPROVE"),
            ):
                with self.subTest(severity=severity, decision=decision):
                    check = bbv.check_blocking_verdict(
                        [severity], result_label=result, decision_label=decision
                    )
                    self.assertFalse(check.ok)
                    self.assertEqual(len(check.violations), 2)

    def test_each_surface_is_checked_independently(self) -> None:
        clean_result = bbv.check_blocking_verdict(
            ["P1"], result_label="✅ Review Clean", decision_label="CHANGES REQUIRED"
        )
        clean_decision = bbv.check_blocking_verdict(
            ["P1"], result_label="⚠️ Changes Requested", decision_label="REVIEW CLEAN"
        )
        self.assertEqual(len(clean_result.violations), 1)
        self.assertIn("Result", clean_result.violations[0])
        self.assertEqual(len(clean_decision.violations), 1)
        self.assertIn("Decision", clean_decision.violations[0])

    def test_missing_surface_is_a_violation_not_a_pass(self) -> None:
        check = bbv.check_blocking_verdict(["P0"], result_label=None, decision_label=None)
        self.assertFalse(check.ok)
        self.assertEqual(len(check.violations), 2)

    def test_incomplete_is_not_the_blocking_value(self) -> None:
        check = bbv.check_blocking_verdict(
            ["P1"], result_label="REVIEW INCOMPLETE", decision_label="REVIEW INCOMPLETE"
        )
        self.assertFalse(check.ok)

    def test_no_blocking_finding_is_vacuous_and_reports_it(self) -> None:
        for severities in ([], ["P2"]):
            with self.subTest(severities=severities):
                check = bbv.check_blocking_verdict(
                    severities, result_label="✅ Review Clean", decision_label="REVIEW CLEAN"
                )
                self.assertFalse(check.blocking_produced)
                self.assertTrue(check.ok)


def _report(*, severity: str, result: str, decision: str) -> str:
    return textwrap.dedent(
        f"""\
        ## Code Review

        **Result: {result}**

        ### Findings

        #### F1 [{severity}] Unsafe change
        - **Location:** `reports/orders.py:2`
        - **Evidence:** the changed line is defective.

        ### Decision
        **{decision}**
        """
    )


class StubbedEndToEndTests(unittest.TestCase):
    """Drives the real adapter, runner, parser, and check with a stub CLI in
    place of the real runtime, proving a drifted verdict fails the check."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.case = _load(CORPUS_DIR / f"{P0_CASE}.yaml")

    def _run(self, report: str) -> bbv.BlockingVerdictCheck:
        stub = self.tmp_path / "stub-review-cli.py"
        stub.write_text(
            f"#!/usr/bin/env python3\nimport sys\nsys.stdout.write({report!r})\n", encoding="utf-8"
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        adapter = ProductionReviewerAdapter(executable=str(stub))
        result = br.run_case(self.case, adapter)
        self.assertEqual(result.status, "executed", result.error)
        outcome = parse_rendered_outcome(adapter.last_report or "")
        return bbv.check_blocking_verdict(
            [f.severity for f in result.produced_findings],
            result_label=outcome.result_label,
            decision_label=outcome.decision_label,
        )

    def test_blocking_report_with_blocking_verdict_passes(self) -> None:
        check = self._run(_report(severity="P0", result="⚠️ Changes Requested", decision="CHANGES REQUIRED"))
        self.assertTrue(check.blocking_produced)
        self.assertTrue(check.ok, check.violations)

    def test_blocking_report_with_clean_verdict_fails(self) -> None:
        check = self._run(_report(severity="P0", result="✅ Review Clean", decision="REVIEW CLEAN"))
        self.assertTrue(check.blocking_produced)
        self.assertFalse(check.ok)


def _probe_runtime() -> str | None:
    """None when the real review runtime is usable, else the reason it is not."""
    try:
        from runtime_platform.benchmark.scripts.benchmark_review_adapter import check_runtime_available

        check_runtime_available()
    except Exception as exc:  # noqa: BLE001 - surfaced as the skip reason, never swallowed
        return str(exc)
    return None


_SKIP_REASON = _probe_runtime()


@unittest.skipUnless(
    _SKIP_REASON is None,
    f"skipping the live end-to-end path rather than fabricating a result — {_SKIP_REASON}",
)
class LiveBlockingVerdictTests(unittest.TestCase):
    """Real packaged `local-code-review` runs. A case that errors, or that
    produces no P0/P1, fails: the proof was not exercised."""

    def test_real_run_never_renders_a_clean_verdict_for_a_blocking_defect(self) -> None:
        for path in _corpus_files():
            case = _load(path)
            with self.subTest(case=case.id):
                adapter = ProductionReviewerAdapter(timeout=600.0)
                result = br.run_case(case, adapter)

                self.assertEqual(result.status, "executed", result.error)
                outcome = parse_rendered_outcome(adapter.last_report or "")
                check = bbv.check_blocking_verdict(
                    [f.severity for f in result.produced_findings],
                    result_label=outcome.result_label,
                    decision_label=outcome.decision_label,
                )
                self.assertTrue(
                    check.blocking_produced,
                    "the reviewer produced no P0/P1 for an unambiguous blocking defect",
                )
                self.assertTrue(check.ok, check.violations)


class ReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_every_blocking_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_names_the_issue_and_the_check(self) -> None:
        self.assertIn("#350", self.raw)
        self.assertIn("benchmark_blocking_verdict.py", self.raw)


if __name__ == "__main__":
    unittest.main()
