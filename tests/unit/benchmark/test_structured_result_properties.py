#!/usr/bin/env python3
"""Coverage for the structured-result runtime-property measurement (Issue #529)."""

from __future__ import annotations

import json
import stat
import tempfile
import textwrap
import unittest
from pathlib import Path

from runtime_platform.benchmark.reference import benchmark_runner as br
from runtime_platform.benchmark.reference import benchmark_structured_result as bsr
from runtime_platform.benchmark.scripts import measure_structured_result as msr
from runtime_platform.benchmark.scripts.benchmark_review_adapter import (
    DEFAULT_ALLOWED_TOOLS,
    HASHING_ALLOWED_TOOLS,
    ProductionReviewerAdapter,
    parse_review_output,
)
from tests.reference.review.invocation_options import OPTION_CONCEPTS, normalize
from tests.support.paths import REPO_ROOT

CASE = next(c for c in msr.load_subset() if c.id == "quality-duplicated-branch-logic")
ID_A = "fid_v1_" + "a" * 32
ID_B = "fid_v1_" + "b" * 32

DUPLICATE = {
    "severity": "P2",
    "title": "Duplicated format_message call in the sms branch",
    "location": "app/notify.py:6",
    "evidence": "`msg = format_message(user)` is repeated verbatim from the email branch.",
    "defect_kind": "duplicated-logic",
}
EXTRA_P1 = {
    "severity": "P1",
    "title": "Unknown kinds raise instead of logging",
    "location": "app/notify.py:9",
    "evidence": "`raise ValueError(kind)` aborts the caller.",
    "defect_kind": "unhandled-error",
}


def _report(findings: list[dict], *, stable_ids: list[str] | None = None) -> str:
    """A local report; `stable_ids` given appends a valid structured result."""
    counts = {level: sum(f["severity"] == level.upper() for f in findings) for level in ("p0", "p1", "p2")}
    blocking = counts["p0"] or counts["p1"]
    label = "CHANGES REQUIRED" if blocking else "REVIEW CLEAN"
    blocks = []
    for n, f in enumerate(findings, 1):
        blocks.append(
            f"#### F{n} [{f['severity']}] {f['title']}\n\n"
            f"- **Location:** `{f['location']}` _(unstaged)_\n"
            f"- **Evidence:** {f['evidence']}\n"
            f"- **Defect kind:** `{f['defect_kind']}`\n"
            f"- **Impact:** A later edit to one branch silently diverges.\n"
            f"- **Fix:** Compute the message once before the dispatch.\n"
        )
    text = textwrap.dedent(
        f"""\
        ## Code Review

        **Result: {"⚠️ Changes Requested" if blocking else "✅ Review Clean"}**

        ### What changed
        Adds an sms branch to notify.

        ### Findings

        {{findings}}
        ### Decision
        **{label}**

        ### Review Metadata

        - Base branch: `main`
        - P0: {counts["p0"]}, P1: {counts["p1"]}, P2: {counts["p2"]}
        - Coverage: complete
        """
    ).replace("{findings}", "\n".join(blocks) or "None.\n")
    if stable_ids is None:
        return text
    result = {
        "schema_version": "1.0.0",
        "skill": "local-code-review",
        "reviewed_state": {
            "repository": "workspace",
            "base_branch": "main",
            "base_sha": None,
            "merge_base_sha": None,
            "reviewed_head_sha": None,
            "reviewer_identity": None,
            "completeness": "full",
            "prior_reviewed_sha": None,
        },
        "coverage": "complete",
        "decision": {"derived": "blocking" if blocking else "clean", "outcome": "blocking" if blocking else "clean"},
        "counts": counts,
        "summary": "Adds an sms branch to notify.",
        "findings": [
            {
                "id": f"F{n}",
                "severity": f["severity"],
                "title": f["title"],
                "location": f["location"],
                "fix_location_resolved": True,
                "evidence": f["evidence"],
                "impact": "A later edit to one branch silently diverges.",
                "fix": "Compute the message once before the dispatch.",
                "runtime_validation": "reasoned",
                "confidence": "credible",
                "defect_kind": f["defect_kind"],
                "identity": {"stable_id": stable_id, "matching_eligible": True},
            }
            for n, (f, stable_id) in enumerate(zip(findings, stable_ids), 1)
        ],
    }
    return f"{text}\n### Structured Review Result\n\n```json\n{json.dumps(result, indent=2)}\n```\n"


def _stub_adapter(tmp: Path, off: str, on_outputs: list[str]) -> msr.AdapterFactory:
    """A stub CLI that prints `off`, or the next of `on_outputs` when the option is on."""
    outputs = tmp / "on-outputs.json"
    outputs.write_text(json.dumps(on_outputs), encoding="utf-8")
    counter = tmp / "counter"
    counter.write_text("0", encoding="utf-8")
    stub = tmp / "stub-review-cli.py"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "prompt = sys.argv[sys.argv.index('-p') + 1]\n"
        "if 'structured_review_result=true' not in prompt:\n"
        f"    sys.stdout.write({off!r}); sys.exit(0)\n"
        f"n = int(open({str(counter)!r}).read())\n"
        f"open({str(counter)!r}, 'w').write(str(n + 1))\n"
        f"sys.stdout.write(json.load(open({str(outputs)!r}))[n])\n",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return lambda structured: ProductionReviewerAdapter(
        executable=str(stub), structured_review_result=structured, allowed_tools=HASHING_ALLOWED_TOOLS
    )


def _observe(report: str, *, structured: bool) -> bsr.RunObservation:
    result = br.run_case(CASE, lambda workspace: parse_review_output(report))
    return bsr.observe_run(CASE, result, report, structured=structured)


class AdapterArmTests(unittest.TestCase):
    def _argv(self, **kwargs) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "argv.json"
            stub = Path(tmp) / "argv-stub.py"
            stub.write_text(
                "#!/usr/bin/env python3\nimport json, sys\n"
                f"json.dump(sys.argv[1:], open({str(marker)!r}, 'w'))\n"
                "print('**Result: ✅ Review Clean**')\n",
                encoding="utf-8",
            )
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
            ProductionReviewerAdapter(executable=str(stub), extra_args=[], **kwargs)(Path(tmp))
            return json.loads(marker.read_text(encoding="utf-8"))

    def _resolved(self, argv: list[str]) -> bool:
        prompt = argv[argv.index("-p") + 1]
        return normalize(prompt, defaults=dict.fromkeys(OPTION_CONCEPTS, False))["structured_review_result"]

    def test_default_invocation_is_unchanged(self) -> None:
        argv = self._argv()
        self.assertIs(self._resolved(argv), False)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], DEFAULT_ALLOWED_TOOLS)

    def test_structured_arm_turns_the_option_on(self) -> None:
        self.assertIs(self._resolved(self._argv(structured_review_result=True)), True)

    def test_hashing_allowlist_adds_only_hashing_commands(self) -> None:
        argv = self._argv(allowed_tools=HASHING_ALLOWED_TOOLS)
        allowed = argv[argv.index("--allowedTools") + 1]
        self.assertTrue(allowed.startswith(DEFAULT_ALLOWED_TOOLS))
        self.assertIn("Bash(shasum *)", allowed)


class ObserveRunTests(unittest.TestCase):
    def test_agreeing_on_run_attributes_the_stable_id_to_the_matched_entry(self) -> None:
        run = _observe(_report([DUPLICATE], stable_ids=[ID_A]), structured=True)
        self.assertEqual(run.contract_errors, ())
        self.assertEqual(run.paired, (("duplicated-format-message-call", "P2"),))
        self.assertEqual(run.stable_ids, {"duplicated-format-message-call": ID_A})
        self.assertEqual(run.decision, "clean")

    def test_off_run_carries_no_result(self) -> None:
        run = _observe(_report([DUPLICATE]), structured=False)
        self.assertEqual(run.stable_ids, {})
        self.assertNotIn("contract_errors", run.as_dict())

    def test_on_run_without_a_result_is_a_contract_error_and_attributes_nothing(self) -> None:
        run = _observe(_report([DUPLICATE]), structured=True)
        self.assertEqual(run.contract_errors, ("no structured result block and no not-emitted statement",))
        self.assertEqual(run.stable_ids, {})

    def test_failed_run_is_recorded_as_an_error(self) -> None:
        result = br.CaseResult(CASE.id, "patch", "error", error="reviewer-adapter-raised")
        run = bsr.observe_run(CASE, result, None, structured=True)
        self.assertFalse(run.executed)
        self.assertEqual(run.as_dict(), {"structured": True, "status": "error", "error": "reviewer-adapter-raised"})


class StableIdStabilityTests(unittest.TestCase):
    KEY = "duplicated-format-message-call"

    def _on(self, stable_id: str) -> bsr.RunObservation:
        return bsr.RunObservation(CASE.id, True, "executed", stable_ids={self.KEY: stable_id}, all_stable_ids=(stable_id,))

    def test_same_id_across_runs_is_stable(self) -> None:
        verdict = bsr.stable_id_stability([self._on(ID_A)] * 3)
        self.assertEqual(verdict["entries"][self.KEY]["status"], bsr.STABLE)
        self.assertEqual(verdict["flags"], [])

    def test_changing_id_is_flagged_unstable(self) -> None:
        verdict = bsr.stable_id_stability([self._on(ID_A), self._on(ID_B), self._on(ID_A)])
        self.assertEqual(verdict["entries"][self.KEY]["status"], bsr.UNSTABLE)
        self.assertEqual(len(verdict["flags"]), 1)
        self.assertTrue(verdict["flags"][0].startswith("unstable:"))

    def test_one_matched_run_is_insufficient_not_stable(self) -> None:
        verdict = bsr.stable_id_stability([self._on(ID_A)])
        self.assertEqual(verdict["entries"][self.KEY]["status"], bsr.INSUFFICIENT)

    def test_one_id_on_distinct_entries_is_a_collision(self) -> None:
        run = bsr.RunObservation(CASE.id, True, "executed", stable_ids={"a": ID_A, "b": ID_A}, all_stable_ids=(ID_A, ID_A))
        flags = bsr.stable_id_stability([run, run])["flags"]
        self.assertEqual(sum(f.startswith("collision:") for f in flags), 2)

    def test_the_policy_example_id_is_flagged_as_copied(self) -> None:
        flags = bsr.stable_id_stability([self._on(bsr.POLICY_EXAMPLE_STABLE_ID)] * 2)["flags"]
        self.assertEqual([f.split(":")[0] for f in flags], ["example-copy", "example-copy"])

    def test_policy_example_constant_tracks_the_policy(self) -> None:
        policy = (REPO_ROOT / "shared" / "policies" / "structured-output.md").read_text(encoding="utf-8")
        self.assertIn(f'"stable_id": "{bsr.POLICY_EXAMPLE_STABLE_ID}"', policy)


class OptionInvarianceTests(unittest.TestCase):
    def _run(self, structured: bool, decision: str, paired=(("k", "P2"),), unpaired=()) -> bsr.RunObservation:
        return bsr.RunObservation(CASE.id, structured, "executed", decision=decision, paired=paired, unpaired=unpaired)

    def test_identical_arms_are_consistent(self) -> None:
        verdict = bsr.option_invariance([self._run(True, "clean")] * 3, [self._run(False, "clean")] * 3)
        self.assertEqual(verdict["verdict"], bsr.CONSISTENT)

    def test_a_steady_difference_is_divergent(self) -> None:
        verdict = bsr.option_invariance([self._run(True, "blocking")] * 3, [self._run(False, "clean")] * 3)
        self.assertEqual(verdict["verdict"], bsr.DIVERGENT)
        self.assertEqual(verdict["components"]["decision"]["verdict"], bsr.DIVERGENT)
        self.assertEqual(verdict["components"]["finding_set"]["verdict"], bsr.CONSISTENT)

    def test_variance_inside_an_arm_is_inconclusive_not_divergent(self) -> None:
        on = [self._run(True, "blocking"), self._run(True, "incomplete")]
        verdict = bsr.option_invariance(on, [self._run(False, "clean")] * 2)
        self.assertEqual(verdict["components"]["decision"]["verdict"], bsr.INCONCLUSIVE)

    def test_partial_overlap_is_inconclusive(self) -> None:
        on = [self._run(True, "clean"), self._run(True, "blocking")]
        verdict = bsr.option_invariance(on, [self._run(False, "clean")] * 2)
        self.assertEqual(verdict["verdict"], bsr.INCONCLUSIVE)

    def test_severity_and_extra_findings_are_compared(self) -> None:
        on = [self._run(True, "clean", paired=(("k", "P1"),), unpaired=("P2",))] * 2
        verdict = bsr.option_invariance(on, [self._run(False, "clean")] * 2)
        self.assertEqual(verdict["components"]["severities"]["verdict"], bsr.DIVERGENT)
        self.assertEqual(verdict["components"]["unpaired"]["verdict"], bsr.DIVERGENT)

    def test_an_arm_with_no_executed_run_is_not_evaluated(self) -> None:
        failed = bsr.RunObservation(CASE.id, True, "error", error="reviewer-adapter-raised")
        verdict = bsr.option_invariance([failed], [self._run(False, "clean")])
        self.assertEqual(verdict["verdict"], bsr.NOT_EVALUATED)


class StubbedMeasurementTests(unittest.TestCase):
    """Drives the real adapter, runner, matcher, and #71 comparator with a stub CLI."""

    def _measure(self, off: str, on_outputs: list[str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            case = msr.measure_case(CASE, len(on_outputs), _stub_adapter(Path(tmp), off, on_outputs))
        return bsr.measurement_record([case], runs_per_arm=len(on_outputs))

    def test_stable_and_invariant_runs_raise_no_flag(self) -> None:
        record = self._measure(_report([DUPLICATE]), [_report([DUPLICATE], stable_ids=[ID_A])] * 2)
        case = record["cases"][0]
        self.assertEqual(case["stable_id"]["entries"]["duplicated-format-message-call"]["status"], bsr.STABLE)
        self.assertEqual(case["invariance"]["verdict"], bsr.CONSISTENT)
        self.assertEqual(
            record["summary"],
            {"stable_id_flags": [], "option_dependent": [], "inconclusive": [], "not_evaluated": [], "contract_errors": []},
        )

    def test_an_unstable_stable_id_is_visible_in_the_record(self) -> None:
        on = [_report([DUPLICATE], stable_ids=[ID_A]), _report([DUPLICATE], stable_ids=[ID_B])]
        record = self._measure(_report([DUPLICATE]), on)
        self.assertEqual(len(record["summary"]["stable_id_flags"]), 1)
        self.assertIn("unstable", record["summary"]["stable_id_flags"][0])

    def test_a_review_that_changes_with_the_option_is_visible_in_the_record(self) -> None:
        on = [_report([DUPLICATE, EXTRA_P1], stable_ids=[ID_A, ID_B])] * 2
        record = self._measure(_report([DUPLICATE]), on)
        self.assertEqual(record["summary"]["option_dependent"], [CASE.id])
        components = record["cases"][0]["invariance"]["components"]
        self.assertEqual(components["decision"]["verdict"], bsr.DIVERGENT)
        self.assertEqual(components["unpaired"]["on"], [["P1"]])

    def test_record_is_json_serializable_and_tagged(self) -> None:
        record = self._measure(_report([DUPLICATE]), [_report([DUPLICATE], stable_ids=[ID_A])] * 2)
        self.assertEqual(json.loads(json.dumps(record))["format"], bsr.RECORD_FORMAT)


class SubsetTests(unittest.TestCase):
    def test_subset_mixes_blocking_non_blocking_and_clean_cases(self) -> None:
        cases = msr.load_subset()
        self.assertEqual(len(cases), len(msr.FIXTURE_SUBSET))
        severities = {s for c in cases for f in c.findings if f.required for s in f.severities}
        self.assertTrue({"P0", "P1", "P2"} <= severities)
        self.assertTrue(any(not c.findings for c in cases))

    def test_unknown_case_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            msr.load_subset(case_ids=["correctness-off-by-one-pagination"])

    def test_decision_record_names_every_subset_fixture(self) -> None:
        doc = (REPO_ROOT / "runtime_platform" / "benchmark" / "structured-result-runtime-properties.md").read_text(
            encoding="utf-8"
        )
        for case in msr.load_subset():
            self.assertIn(f"`{case.id}`", doc)
        self.assertIn(f"`{msr.DEFAULT_RUNS}`", doc)

    def test_single_run_per_arm_is_refused(self) -> None:
        self.assertEqual(msr.main(["--runs", "1"]), 2)


if __name__ == "__main__":
    unittest.main()
