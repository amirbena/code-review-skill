#!/usr/bin/env python3
"""Coverage for the dependency tree inspection benchmark sub-corpus, the additive
``input.dependency_trees`` input, the adapter seam, the pre-registration, and the
disposition rules (Issue #732).
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import yaml

from runtime_platform.benchmark.reference import benchmark_dependency_tree as bdt
from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_runner as br
from runtime_platform.benchmark.scripts import measure_dependency_tree as mdt
from runtime_platform.benchmark.scripts.benchmark_review_adapter import _dependency_trees_block, _tree_permissions
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "dependency-tree-inspection"
ADDED = "dti-incident-added-user-provided"
RENAMED = "dti-incident-renamed-user-provided"


def _raw(case_id: str) -> dict:
    return yaml.safe_load((CORPUS_DIR / f"{case_id}.yaml").read_text(encoding="utf-8"))


def _load(case_id: str) -> bf.BenchmarkCase:
    return bf.parse_case(_raw(case_id))


def _all() -> list[bf.BenchmarkCase]:
    return [_load(c) for c in sorted(bdt.CASE_ROLES)]


class CorpusShapeTests(unittest.TestCase):
    def test_cases_match_the_role_table_exactly(self) -> None:
        self.assertEqual({p.stem for p in CORPUS_DIR.glob("*.yaml")}, set(bdt.CASE_ROLES))

    def test_every_case_validates_is_synthetic_and_names_the_imitated_format(self) -> None:
        for case in _all():
            with self.subTest(case=case.id):
                trees = case.input["dependency_trees"]
                self.assertIs(trees["synthetic"], True)
                self.assertIn("mvn dependency:tree", trees["imitates"])
                self.assertEqual(case.metadata["taxonomy"]["capability"], ["dependency-tree-inspection"])
                self.assertIn("SYNTHETIC", (CORPUS_DIR / f"{case.id}.yaml").read_text(encoding="utf-8"))

    def test_only_positives_require_a_finding(self) -> None:
        for case in _all():
            required = [e for e in case.findings if e.required]
            with self.subTest(case=case.id):
                self.assertEqual(bool(required), bdt.CASE_ROLES[case.id] == bdt.POSITIVE)
                self.assertEqual(case.decision, case.derived_decision)

    def test_added_and_renamed_shapes_differ_in_severity_and_wording(self) -> None:
        added, renamed = _load(ADDED), _load(RENAMED)
        self.assertEqual(added.findings[0].severities, ("P1",))
        self.assertEqual(renamed.findings[0].severities, ("P2",))
        self.assertNotEqual(added.findings[0].key, renamed.findings[0].key)
        added_claim = _raw(ADDED)["expected"]["findings"][0]["claim"]
        renamed_claim = _raw(RENAMED)["expected"]["findings"][0]["claim"]
        self.assertIn("absent from the Base tree", added_claim)
        self.assertIn("already in the Base tree", renamed_claim)
        self.assertIn("not newly introduced", renamed_claim)

    def test_incident_pair_changes_one_declaration_line(self) -> None:
        for case_id in (ADDED, RENAMED):
            patch = _load(case_id).input["patch"]
            changed = [l for l in patch.splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---")]
            self.assertEqual(changed, ["-        <version>2.3.0</version>", "+        <version>2.4.0</version>"])

    def test_the_added_shape_has_no_non_fips_family_in_base_and_the_renamed_shape_does(self) -> None:
        self.assertNotIn("bcprov", _load(ADDED).input["dependency_trees"]["base"]["text"])
        self.assertIn("bcprov-jdk15on", _load(RENAMED).input["dependency_trees"]["base"]["text"])

    def test_every_workflow_and_evidence_case_class_is_present(self) -> None:
        workflows = {c.input["dependency_trees"]["workflow"] for c in _all()}
        self.assertEqual(workflows, set(bf.DEPENDENCY_TREE_WORKFLOWS))
        for case_id in (
            "dti-head-only-no-introduction-claim", "dti-malformed-output", "dti-incomplete-resolution-error",
            "dti-incomplete-missing-pom-warning", "dti-incomplete-truncated-output", "dti-wrong-project",
            "dti-unidentified-side", "dti-mismatched-commands", "dti-mismatched-profiles",
            "dti-incident-supplied-text-contains-instructions",
        ):
            self.assertIn(case_id, bdt.CASE_ROLES)

    def test_mismatched_cases_really_mismatch(self) -> None:
        for case_id in ("dti-mismatched-commands", "dti-mismatched-profiles"):
            trees = _load(case_id).input["dependency_trees"]
            self.assertNotEqual(trees["base"]["command"], trees["head"]["command"])

    def test_unidentified_side_carries_only_unlabeled_text(self) -> None:
        trees = _load("dti-unidentified-side").input["dependency_trees"]
        self.assertIn("unlabeled", trees)
        self.assertNotIn("base", trees)
        self.assertNotIn("head", trees)

    def test_api_only_runs_only_supplied_output_cases(self) -> None:
        api = {c.id for c in _all() if bdt.applies_to(c, bdt.GITHUB_API_ONLY)}
        self.assertIn(ADDED, api)
        self.assertIn("dti-user-declines-output", api)
        self.assertNotIn("dti-incident-added-authorized-execution", api)
        self.assertNotIn("dti-incident-added-blocked-then-provided", api)
        self.assertNotIn("dti-blocked-then-declined", api)
        for adapter in (bdt.LOCAL, bdt.GITHUB_REPO):
            self.assertEqual(len([c for c in _all() if bdt.applies_to(c, adapter)]), len(bdt.CASE_ROLES))


class ValidatorTests(unittest.TestCase):
    def _mutated(self, mutate) -> None:
        data = copy.deepcopy(_raw(ADDED))
        mutate(data["input"]["dependency_trees"])
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_rejections(self) -> None:
        self._mutated(lambda t: t.update(synthetic=False))
        self._mutated(lambda t: t.pop("synthetic"))
        self._mutated(lambda t: t.update(workflow="run-it-all"))
        self._mutated(lambda t: t.update(extra=1))
        self._mutated(lambda t: t.pop("imitates"))
        self._mutated(lambda t: t["head"].update(text=""))
        self._mutated(lambda t: t["head"].update(argv=["x"]))
        self._mutated(lambda t: t.update(unlabeled={"text": "x"}))
        self._mutated(lambda t: (t.pop("base"), t.pop("head")))
        self._mutated(lambda t: t.update(workflow="declined"))
        self._mutated(lambda t: (t.update(workflow="authorized-execution"), t["head"].pop("command")))

    def test_input_without_a_patch_is_rejected(self) -> None:
        data = copy.deepcopy(_raw(ADDED))
        data["input"].pop("patch")
        data["input"].pop("base")
        data["input"]["repo_ref"] = {"repo": "a/b", "commit": "abc"}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_a_declined_workflow_with_no_text_is_valid(self) -> None:
        self.assertEqual(_load("dti-user-declines-output").input["dependency_trees"]["workflow"], "declined")


class MaterializationTests(unittest.TestCase):
    def test_keyword_is_forwarded_only_to_cases_that_declare_it(self) -> None:
        seen: dict[str, object] = {}

        def reviewer(workspace, **kwargs):
            seen.update(kwargs)
            return []

        br.run_case(_load(ADDED), reviewer)
        trees = seen["dependency_trees"]
        self.assertEqual(trees.workflow, "user-provided")
        self.assertEqual(sorted(trees.sides), ["base", "head"])
        self.assertTrue(all(run is None for _, _, run in trees.sides.values()))

        plain = bf.parse_case(yaml.safe_load((REPO_ROOT / "benchmark/corpus/security-command-injection.yaml").read_text()))
        seen.clear()
        br.run_case(plain, reviewer)
        self.assertNotIn("dependency_trees", seen)

    def test_authorized_execution_offers_a_fixture_local_command_that_emits_the_text(self) -> None:
        case = _load("dti-incident-added-authorized-execution")
        outputs: dict[str, str] = {}
        roots: list[Path] = []

        def reviewer(workspace, dependency_trees=None):
            for side, (_, text, run) in dependency_trees.sides.items():
                self.assertTrue(run.startswith("cat "))
                path = Path(run.split(" ", 1)[1])
                roots.append(path.parent)
                outputs[side] = subprocess.run(run, shell=True, capture_output=True, text=True, check=True).stdout
                self.assertEqual(outputs[side], text)
                self.assertFalse(str(path).startswith(str(workspace)))
            return []

        result = br.run_case(case, reviewer)
        self.assertEqual(result.status, "executed")
        self.assertEqual(sorted(outputs), ["base", "head"])
        self.assertTrue(all(not r.exists() for r in roots))

    def test_the_patch_applies_and_the_policy_file_is_committed(self) -> None:
        seen: dict[str, str] = {}

        def reviewer(workspace, **kwargs):
            seen["pom"] = (workspace / "pom.xml").read_text(encoding="utf-8")
            seen["policy"] = (workspace / "docs/security-policy.md").read_text(encoding="utf-8")
            return []

        br.run_case(_load(ADDED), reviewer)
        self.assertIn("<version>2.4.0</version>", seen["pom"])
        self.assertIn("FIPS", seen["policy"])


class AdapterBlockTests(unittest.TestCase):
    def _ref(self, case_id: str, **kw):
        captured = {}
        br.run_case(_load(case_id), lambda ws, dependency_trees=None: captured.setdefault("t", dependency_trees) and [])
        return captured["t"]

    def test_user_provided_block_quotes_each_side_as_data(self) -> None:
        block = _dependency_trees_block(self._ref(ADDED))
        self.assertIn("base side", block)
        self.assertIn("head side", block)
        self.assertIn("bcprov-jdk18on", block)
        self.assertIn("command: `mvn dependency:tree`", block)

    def test_unlabeled_side_is_stated_as_unknown(self) -> None:
        self.assertIn("side not stated", _dependency_trees_block(self._ref("dti-unidentified-side")))

    def test_declined_blocks_carry_no_tree_text(self) -> None:
        for case_id in ("dti-user-declines-output", "dti-blocked-then-declined"):
            block = _dependency_trees_block(self._ref(case_id))
            self.assertIn("declines", block)
            self.assertNotIn("[INFO]", block)

    def test_blocked_then_provided_says_execution_is_blocked(self) -> None:
        self.assertIn("blocked", _dependency_trees_block(self._ref("dti-incident-added-blocked-then-provided")))

    def test_only_authorized_execution_grants_permissions_and_only_for_the_approved_commands(self) -> None:
        self.assertEqual(_tree_permissions(self._ref(ADDED)), ([], ""))
        self.assertEqual(_tree_permissions(None), ([], ""))
        ref = self._ref("dti-incident-added-authorized-execution")
        dirs, tools = _tree_permissions(ref)
        self.assertEqual(len(tools.split(") Bash(")), 2)
        self.assertTrue(tools.startswith("Bash(cat "))
        self.assertEqual(len(dirs), 1)
        block = _dependency_trees_block(ref)
        self.assertIn("explicitly approves", block)
        self.assertIn("no network or credential use", block)


def _obs(case_id, arm, *, found=0, required=0, wrong=0, produced=None, over=False, sev=None, ev=None, word=None,
         gap=True, intro=False, followed=False, seconds=10.0, tokens=1000, status="executed"):
    if status != "executed":
        return bdt.RunObservation(case_id, arm, "error", error="reviewer-adapter-raised", error_category="timeout")
    return bdt.RunObservation(
        case_id, arm, "executed", required=required, found=found, wrong=wrong,
        produced=wrong + found if produced is None else produced, over_report=over, severity_ok=sev,
        evidence_ok=ev, wording_ok=word, gap_stated=gap, introduction_claim=intro, instruction_followed=followed,
        seconds=seconds, tokens=tokens,
    )


def _good_runs(*, candidate_found=True, baseline_found=False, fc_gap=True, ctrl_wrong_candidate=0, tokens=1000):
    runs = []
    cases = sorted(bdt.CASE_ROLES)
    for case_id in cases:
        role = bdt.CASE_ROLES[case_id]
        for _ in range(2):
            for arm in bdt.ARMS:
                if role == bdt.POSITIVE:
                    f = candidate_found if arm == bdt.CANDIDATE else baseline_found
                    runs.append(_obs(case_id, arm, required=1, found=int(f), sev=True if f else None,
                                     ev=True if f else None, word=True if f else None, tokens=tokens))
                elif role == bdt.FAIL_CLOSED:
                    runs.append(_obs(case_id, arm, gap=fc_gap if arm == bdt.CANDIDATE else False, tokens=tokens))
                else:
                    wrong = ctrl_wrong_candidate if arm == bdt.CANDIDATE else 0
                    runs.append(_obs(case_id, arm, wrong=wrong, tokens=tokens))
    return runs, cases


class DispositionTests(unittest.TestCase):
    def test_pass(self) -> None:
        runs, cases = _good_runs()
        result = bdt.evaluate_adapter(runs, cases)
        self.assertEqual(result["outcome"], bdt.PASS, result)
        self.assertTrue(result["baseline_misses_incident"])

    def test_candidate_recall_below_two_thirds_fails(self) -> None:
        runs, cases = _good_runs(candidate_found=False)
        result = bdt.evaluate_adapter(runs, cases)
        self.assertEqual(result["outcome"], bdt.FAIL)
        self.assertIn("recall", result["failed"])

    def test_one_inexact_fail_closed_run_fails(self) -> None:
        runs, cases = _good_runs(fc_gap=False)
        result = bdt.evaluate_adapter(runs, cases)
        self.assertIn("fail_closed_exact", result["failed"])

    def test_control_finding_growth_fails_and_p0_p1_is_counted_separately(self) -> None:
        runs, cases = _good_runs(ctrl_wrong_candidate=1)
        self.assertIn("control_false_positives", bdt.evaluate_adapter(runs, cases)["failed"])
        runs, cases = _good_runs()
        runs.append(_obs("dti-control-routine-patch-bump", bdt.CANDIDATE, wrong=1, over=True))
        failed = bdt.evaluate_adapter(runs, cases)["failed"]
        self.assertIn("severity_over_report", failed)

    def test_fewer_than_two_executed_runs_is_not_evaluated_and_errors_are_kept(self) -> None:
        runs, cases = _good_runs()
        errored = _obs(ADDED, bdt.CANDIDATE, status="error")
        keep = [r for r in runs if not (r.case_id == ADDED and r.arm == bdt.CANDIDATE)]
        result = bdt.evaluate_adapter(keep + [errored, errored], cases)
        self.assertEqual(result["outcome"], bdt.NOT_EVALUATED)
        self.assertEqual(len(result["errored_runs"]), 2)
        self.assertEqual(result["errored_runs"][0]["error_category"], "timeout")

    def test_missing_tokens_make_cost_not_evaluated_never_pass(self) -> None:
        runs, cases = _good_runs(tokens=None)
        result = bdt.evaluate_adapter(runs, cases)
        self.assertEqual(result["outcome"], bdt.NOT_EVALUATED)
        self.assertEqual(result["not_evaluated"], ["acceptable_cost"])
        self.assertFalse(result["criteria"]["acceptable_cost"]["tokens_reported"])

    def test_cost_ratio_above_two_fails(self) -> None:
        runs, cases = _good_runs()
        slow = [r if r.arm == bdt.BASELINE else _replace(r, seconds=100.0) for r in runs]
        self.assertIn("acceptable_cost", bdt.evaluate_adapter(slow, cases)["failed"])

    def test_following_injected_instructions_fails(self) -> None:
        runs, cases = _good_runs()
        runs.append(_obs(bdt.INJECTION_CASE, bdt.CANDIDATE, required=1, found=1, sev=True, ev=True, word=True, followed=True))
        self.assertIn("instructions_not_followed", bdt.evaluate_adapter(runs, cases)["failed"])

    def test_no_control_runs_is_not_evaluated_never_a_vacuous_pass(self) -> None:
        runs, cases = _good_runs()
        no_ctrl = [c for c in cases if bdt.CASE_ROLES[c] != bdt.CONTROL]
        kept = [r for r in runs if r.case_id in no_ctrl]
        result = bdt.evaluate_adapter(kept, no_ctrl)
        self.assertEqual(result["outcome"], bdt.NOT_EVALUATED)
        self.assertEqual(result["not_evaluated"], ["control_false_positives", "severity_over_report"])

    def test_a_missing_adapter_is_not_run_and_never_inferred(self) -> None:
        runs, cases = _good_runs()
        ids = {a: cases for a in bdt.ADAPTERS}
        record = bdt.measurement_record({bdt.LOCAL: runs}, ids, runs_per_arm=2, metadata={})
        self.assertEqual(record["summary"], {bdt.LOCAL: "pass", bdt.GITHUB_REPO: "not-run", bdt.GITHUB_API_ONLY: "not-run"})
        self.assertEqual(record["format"], bdt.RECORD_FORMAT)


def _replace(run: bdt.RunObservation, **changes):
    import dataclasses

    return dataclasses.replace(run, **changes)


class HeuristicTests(unittest.TestCase):
    def test_introduction_claim_ignores_negated_sentences(self) -> None:
        self.assertTrue(bdt.introduction_claim("The change introduced bcprov."))
        self.assertFalse(bdt.introduction_claim("Base was not compared, so it is unknown whether the change introduced it."))
        self.assertFalse(bdt.introduction_claim("Head contains bcprov-jdk18on."))

    def test_wording_separates_added_from_renamed(self) -> None:
        self.assertTrue(bdt.wording_ok(ADDED, "The bump adds bcprov, absent from Base."))
        self.assertFalse(bdt.wording_ok(ADDED, "The bump renames bcprov."))
        self.assertTrue(bdt.wording_ok(RENAMED, "bcprov-jdk15on is replaced by bcprov-jdk18on."))
        self.assertFalse(bdt.wording_ok(RENAMED, "The bump adds bcprov."))

    def test_evidence_needs_path_base_head_and_family(self) -> None:
        self.assertTrue(bdt.evidence_complete("pom.xml: Base lacks bcprov, Head has it."))
        self.assertFalse(bdt.evidence_complete("pom.xml: Head has bcprov."))

    def test_gap_is_read_from_the_context_gaps_section_only(self) -> None:
        self.assertTrue(bdt.gap_stated("## Context gaps\n- The dependency tree output was not supplied.\n"))
        self.assertFalse(bdt.gap_stated("The dependency tree is fine.\n## Findings\nnone"))


class PreRegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prereg = json.loads((CORPUS_DIR / "pre-registration.json").read_text(encoding="utf-8"))

    def test_committed_file_equals_the_protocol_derived_from_the_corpus(self) -> None:
        self.assertEqual(self.prereg, bdt.build_preregistration(_all(), CORPUS_DIR))

    def test_digest_changes_when_a_fixture_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for p in CORPUS_DIR.glob("*.yaml"):
                (Path(tmp) / p.name).write_bytes(p.read_bytes())
            same = bdt.fixture_set_digest(tmp)
            (Path(tmp) / f"{ADDED}.yaml").write_text("x: 1\n", encoding="utf-8")
            self.assertEqual(same, self.prereg["fixture_set_digest"])
            self.assertNotEqual(bdt.fixture_set_digest(tmp), same)

    def test_thresholds_are_the_precedent_values(self) -> None:
        t = self.prereg["thresholds"]
        self.assertEqual((t["min_rate"], t["max_wall_time_ratio"], t["max_token_ratio"], t["max_false_positive_growth"]),
                         (2 / 3, 2.0, 2.0, 0))
        self.assertEqual(self.prereg["runs_per_arm"], 3)
        self.assertRegex(self.prereg["baseline_sha"], r"^[0-9a-f]{40}$")

    def test_fail_closed_and_control_cases_register_no_finding(self) -> None:
        for case_id, entry in self.prereg["cases"].items():
            if entry["role"] != bdt.POSITIVE:
                self.assertEqual(entry["expected_findings"], [], case_id)

    def test_protocol_check_refuses_a_changed_fixture_set_and_an_unregistered_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "pre-registration.json"
            fake.write_text(json.dumps({**self.prereg, "fixture_set_digest": "0" * 64}), encoding="utf-8")
            original = mdt.PREREGISTRATION
            mdt.PREREGISTRATION = fake
            try:
                problems = mdt.check_protocol(Path(tmp), smoke=False, allow_dirty=True)
            finally:
                mdt.PREREGISTRATION = original
        self.assertTrue(any("digest" in p for p in problems))
        self.assertTrue(any("baseline checkout" in p for p in problems))

    def test_protocol_check_refuses_code_that_drifted_from_the_registered_protocol(self) -> None:
        self.assertEqual(
            [p for p in mdt.check_protocol(REPO_ROOT, smoke=False, allow_dirty=True) if "pre-registration.json" in p], []
        )
        with mock.patch.object(bdt, "MIN_RATE", 0.5):
            problems = mdt.check_protocol(REPO_ROOT, smoke=False, allow_dirty=True)
        self.assertTrue(any("differ from pre-registration.json" in p for p in problems))

    def test_measurement_refuses_without_a_preregistration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = mdt.PREREGISTRATION
            mdt.PREREGISTRATION = Path(tmp) / "absent.json"
            try:
                self.assertEqual(mdt.check_protocol(Path(tmp), smoke=False, allow_dirty=True), ["pre-registration.json is missing"])
            finally:
                mdt.PREREGISTRATION = original


class ArmSkillRootTests(unittest.TestCase):
    def _module(self, factory) -> str:
        name = "dti_test_factory_module"
        module = types.ModuleType(name)
        module.make = factory
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        return f"{name}:make"

    def test_each_arm_gets_its_registered_skill_root(self) -> None:
        baseline = Path("/registered/baseline")
        self.assertEqual(mdt.skill_root_for(bdt.BASELINE, baseline), baseline)
        self.assertEqual(mdt.skill_root_for(bdt.CANDIDATE, baseline), mdt.REPO_ROOT)

    def test_a_factory_without_skill_root_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            mdt._load_factory(self._module(lambda: None))

    def test_a_factory_taking_skill_root_or_kwargs_is_accepted_and_receives_it(self) -> None:
        seen: list[Path] = []
        for factory in (lambda skill_root: seen.append(skill_root), lambda **kw: seen.append(kw["skill_root"])):
            mdt._load_factory(self._module(factory))(skill_root=Path("/x"))
        self.assertEqual(seen, [Path("/x"), Path("/x")])

    def test_a_malformed_factory_spec_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            mdt._load_factory("no-colon")


class IndexAndDocsTests(unittest.TestCase):
    def test_every_case_is_in_the_corpus_index(self) -> None:
        index = json.loads((REPO_ROOT / "benchmark" / "corpus-index.json").read_text(encoding="utf-8"))
        indexed = set(index["capability"]["dependency-tree-inspection"])
        self.assertEqual(indexed, set(bdt.CASE_ROLES))

    def test_docs_state_that_the_incident_is_not_claimed_as_reproduced(self) -> None:
        for path in (
            REPO_ROOT / "runtime_platform/benchmark/dependency-tree-inspection-measurement.md",
            CORPUS_DIR / "README.md",
        ):
            text = path.read_text(encoding="utf-8").lower()
            self.assertIn("synthetic", text)
            self.assertRegex(text, r"not\*{0,2} (claimed as reproduced|reproduced)|is \*\*not\*\* reproduced|never claimed")


if __name__ == "__main__":
    unittest.main()
