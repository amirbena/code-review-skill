#!/usr/bin/env python3
"""Coverage for the workspace sibling context benchmark sub-corpus, the additive
``input.workspace_siblings`` input, the adapter grant seam, and the
pre-registered gate rules (Issue #664).
"""

from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_runner as br
from runtime_platform.benchmark.reference import benchmark_workspace_sibling as bws
from runtime_platform.benchmark.scripts import measure_workspace_sibling as mws
from runtime_platform.benchmark.scripts.benchmark_review_adapter import _workspace_grant_block
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "workspace-sibling-context"
RESOLVES = "wsib-resolves-from-relevant-sibling"
MIRROR = "wsib-gh-pr-repository-excluded-by-identity"
PUBLISHED = "wsib-gh-published-output-reference-only"


def _raw(case_id: str) -> dict:
    return yaml.safe_load((CORPUS_DIR / f"{case_id}.yaml").read_text(encoding="utf-8"))


def _load(case_id: str) -> bf.BenchmarkCase:
    return bf.parse_case(_raw(case_id))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


class CorpusShapeTests(unittest.TestCase):
    def test_cases_match_the_role_table_exactly(self) -> None:
        self.assertEqual({p.stem for p in CORPUS_DIR.glob("*.yaml")}, set(bws.CASE_ROLES))

    def test_every_case_validates_and_declares_siblings(self) -> None:
        for case_id in sorted(bws.CASE_ROLES):
            with self.subTest(case=case_id):
                case = _load(case_id)
                self.assertTrue(case.input["workspace_siblings"])
                self.assertEqual(case.metadata["taxonomy"]["capability"], ["workspace-sibling-context"])

    def test_six_shared_and_three_github_only_cases(self) -> None:
        local = [c for c in bws.CASE_ROLES if bws.applies_to(c, bws.LOCAL)]
        github = [c for c in bws.CASE_ROLES if bws.applies_to(c, bws.GITHUB)]
        self.assertEqual(len(local), 6)
        self.assertEqual(len(github), 9)
        self.assertTrue(set(local) < set(github))

    def test_every_finding_is_located_in_the_review_target(self) -> None:
        for case_id in sorted(bws.CASE_ROLES):
            for finding in _raw(case_id)["expected"]["findings"]:
                self.assertNotIn("repo_alias", finding["location"])
                self.assertTrue(finding["location"]["path"].startswith("schemas/"))

    def test_only_the_resolving_cases_require_a_finding(self) -> None:
        for case_id, role in bws.CASE_ROLES.items():
            required = [f for f in _raw(case_id)["expected"]["findings"] if f.get("match", "required") == "required"]
            with self.subTest(case=case_id):
                self.assertEqual(bool(required), role in (bws.RESOLVING, bws.PUBLISHED))

    def test_published_case_plants_the_leak_marker_in_the_sibling(self) -> None:
        files = _raw(PUBLISHED)["input"]["workspace_siblings"]["ledger-consumer"]["files"]
        self.assertTrue(any(bws.LEAK_MARKER in text for text in files.values()))
        for case_id in bws.CASE_ROLES:
            if case_id != PUBLISHED:
                self.assertNotIn(bws.LEAK_MARKER, (CORPUS_DIR / f"{case_id}.yaml").read_text(encoding="utf-8"))


class FixtureValidationTests(unittest.TestCase):
    def _rejected(self, mutate) -> None:
        data = copy.deepcopy(_raw(RESOLVES))
        mutate(data["input"])
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_rejections(self) -> None:
        sibling = lambda i: i["workspace_siblings"]["ledger-consumer"]  # noqa: E731
        cases = {
            "empty mapping": lambda i: i.update(workspace_siblings={}),
            "non-slug alias": lambda i: i.update(workspace_siblings={"Bad_Alias": sibling(i)}),
            "missing files": lambda i: sibling(i).pop("files"),
            "empty files": lambda i: sibling(i).update(files={}),
            "unknown key": lambda i: sibling(i).update(path="/tmp/x"),
            "non-bool mirror": lambda i: sibling(i).update(mirrors_review_target="yes"),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._rejected(mutate)

    def test_requires_patch_input(self) -> None:
        data = copy.deepcopy(_raw(RESOLVES))
        data["input"] = {
            "repo_ref": {"repo": "o/r", "commit": "a" * 40},
            "workspace_siblings": data["input"]["workspace_siblings"],
        }
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_input_is_optional_for_every_other_case(self) -> None:
        data = _raw(RESOLVES)
        data["input"].pop("workspace_siblings")
        self.assertNotIn("workspace_siblings", bf.parse_case(data).input)


class RunnerMaterializationTests(unittest.TestCase):
    def test_siblings_are_immediate_child_git_repositories_at_head(self) -> None:
        case = _load(RESOLVES)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            target = Path(tmp) / "target"
            root.mkdir()
            target.mkdir()
            subprocess.run(["git", "-C", str(target), "init", "-q"], check=True)
            self.assertEqual(br.materialize_workspace_siblings(case, root, target), root)
            self.assertEqual({p.name for p in root.iterdir()}, {"ledger-consumer", "docs-site"})
            shown = _git(root / "ledger-consumer", "show", "HEAD:ledger/apply_status.py")
            self.assertIn("unknown payment status", shown)

    def test_mirror_shares_the_review_workspace_identity(self) -> None:
        case = _load(MIRROR)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            target = Path(tmp) / "target"
            root.mkdir()
            target.mkdir()
            subprocess.run(["git", "-C", str(target), "init", "-q"], check=True)
            br.materialize_workspace_siblings(case, root, target)
            mirror = _git(root / "payment-service-checkout", "remote", "get-url", "origin")
            self.assertEqual(mirror, br.WORKSPACE_MIRROR_ORIGIN)
            self.assertEqual(_git(target, "remote", "get-url", "origin"), mirror)
            with self.assertRaises(subprocess.CalledProcessError):
                _git(root / "docs-site", "remote", "get-url", "origin")

    def test_runner_hands_the_root_only_when_siblings_are_declared(self) -> None:
        seen: list[dict] = []

        def reviewer(workspace, **kwargs):
            seen.append(kwargs)
            self.assertTrue((Path(kwargs["workspace_root"]) / "ledger-consumer" / ".git").exists())
            return []

        result = br.run_case(_load(RESOLVES), reviewer)
        self.assertEqual(result.status, "executed")
        self.assertEqual(list(seen[0]), ["workspace_root"])

        plain = copy.deepcopy(_raw(RESOLVES))
        plain["input"].pop("workspace_siblings")
        calls: list[tuple] = []
        br.run_case(bf.parse_case(plain), lambda workspace, **kw: calls.append(tuple(kw)) or [])
        self.assertEqual(calls, [()])

    def test_the_workspace_root_is_removed_after_the_run(self) -> None:
        roots: list[Path] = []
        br.run_case(_load(RESOLVES), lambda workspace, **kw: roots.append(Path(kw["workspace_root"])) or [])
        self.assertFalse(roots[0].exists())

    def test_off_arm_withholds_the_grant_and_on_arm_forwards_it(self) -> None:
        seen: dict[str, bool] = {}
        for arm, grant in (("on", True), ("off", False)):
            inner = lambda workspace, **kw: seen.update({arm: "workspace_root" in kw}) or []  # noqa: E731
            br.run_case(_load(RESOLVES), mws.ArmAdapter(inner, grant=grant))
        self.assertEqual(seen, {"on": True, "off": False})


class AdapterGrantTests(unittest.TestCase):
    def test_block_names_the_root_and_nothing_else(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            block = _workspace_grant_block(Path(tmp))
        self.assertIn("workspace root:", block)
        self.assertIn("workspace-sibling-context.md", block)
        self.assertIn("No other location is authorized", block)


def _obs(case_id: str, arm: str, **kw) -> bws.RunObservation:
    base = dict(required=0, found=0, wrong=0, escalated=False, absence_claim=False, leaked=False, seconds=10.0, tokens=None)
    base.update(kw)
    return bws.RunObservation(case_id, arm, "executed", **base)


def _runs(per_arm: int, overrides: dict | None = None) -> list[bws.RunObservation]:
    """A passing baseline over the local case set, with per-(case, arm) overrides."""
    overrides = overrides or {}
    runs = []
    for case_id, role in bws.CASE_ROLES.items():
        if not bws.applies_to(case_id, bws.LOCAL):
            continue
        for arm in ("off", "on"):
            kw: dict = {}
            if role == bws.RESOLVING:
                kw = {"required": 1, "found": 1 if arm == "on" else 0}
            if role == bws.ESCALATION:
                kw = {"escalated": True}
            kw.update(overrides.get((case_id, arm), {}))
            runs.extend(_obs(case_id, arm, **kw) for _ in range(per_arm))
    return runs


LOCAL_IDS = [c for c in bws.CASE_ROLES if bws.applies_to(c, bws.LOCAL)]
FALLBACK = "wsib-no-relevant-sibling-fallback"
ABSENCE = "wsib-absence-in-inspected-sibling-no-claim"


class GateRuleTests(unittest.TestCase):
    def outcome(self, runs, ids=LOCAL_IDS) -> dict:
        return bws.evaluate_adapter(runs, ids)

    def test_clean_gain_passes_with_cost_unevaluated_by_tokens(self) -> None:
        result = self.outcome(_runs(3))
        self.assertEqual(result["outcome"], bws.PASS, result)
        self.assertFalse(result["criteria"]["acceptable_cost"]["tokens_reported"])

    def test_no_gain_fails(self) -> None:
        runs = _runs(3, {(RESOLVES, "on"): {"found": 0}})
        self.assertIn("quality_gain", self.outcome(runs)["failed"])

    def test_false_positive_growth_fails(self) -> None:
        runs = _runs(3, {(FALLBACK, "on"): {"wrong": 1}})
        self.assertIn("false_positive_growth", self.outcome(runs)["failed"])

    def test_equal_wrong_counts_do_not_fail(self) -> None:
        runs = _runs(3, {(FALLBACK, "on"): {"wrong": 1}, (FALLBACK, "off"): {"wrong": 1}})
        self.assertNotIn("false_positive_growth", self.outcome(runs)["failed"])

    def test_lost_escalation_fails(self) -> None:
        runs = _runs(3, {("wsib-insufficient-evidence-question-preserved", "on"): {"escalated": False}})
        self.assertIn("preserved_escalation", self.outcome(runs)["failed"])

    def test_absence_claim_fails(self) -> None:
        runs = _runs(3, {(ABSENCE, "on"): {"absence_claim": True}})
        self.assertIn("no_absence_claim", self.outcome(runs)["failed"])

    def test_leak_fails_only_where_the_published_case_applies(self) -> None:
        github_ids = [c for c in bws.CASE_ROLES if bws.applies_to(c, bws.GITHUB)]
        runs = []
        for case_id in github_ids:
            for arm in ("off", "on"):
                role = bws.CASE_ROLES[case_id]
                kw: dict = {}
                if role in (bws.RESOLVING, bws.PUBLISHED):
                    kw = {"required": 1, "found": 1 if arm == "on" else 0}
                if role == bws.ESCALATION:
                    kw = {"escalated": True}
                if role == bws.PUBLISHED and arm == "on":
                    kw["leaked"] = True
                runs.extend(_obs(case_id, arm, **kw) for _ in range(3))
        result = self.outcome(runs, github_ids)
        self.assertEqual(result["failed"], ["no_published_sibling_content"])

    def test_cost_over_the_ratio_fails(self) -> None:
        runs = [
            _obs(r.case_id, r.arm, required=r.required, found=r.found, escalated=r.escalated,
                 seconds=30.0 if r.arm == "on" else 10.0)
            for r in _runs(3)
        ]
        self.assertIn("acceptable_cost", self.outcome(runs)["failed"])

    def test_token_ratio_over_the_limit_fails(self) -> None:
        runs = [
            _obs(r.case_id, r.arm, required=r.required, found=r.found, escalated=r.escalated,
                 tokens=300 if r.arm == "on" else 100)
            for r in _runs(3)
        ]
        self.assertIn("acceptable_cost", self.outcome(runs)["failed"])

    def test_too_few_executed_runs_is_not_evaluated(self) -> None:
        self.assertEqual(self.outcome(_runs(1))["outcome"], bws.NOT_EVALUATED)

    def test_adapters_are_never_merged(self) -> None:
        record = bws.measurement_record(
            {bws.LOCAL: _runs(3), bws.GITHUB: None},
            {bws.LOCAL: LOCAL_IDS, bws.GITHUB: []},
            runs_per_arm=3,
            metadata={},
        )
        self.assertEqual(record["summary"], {bws.LOCAL: bws.PASS, bws.GITHUB: "not-run"})


class ReportHeuristicTests(unittest.TestCase):
    def test_escalation_sections_only(self) -> None:
        report = "## Findings\n\nrefunded here\n\n### Context gaps\n\n- refunded consumers unknown\n\n### Decision\n\nclean\n"
        text = bws.escalation_sections(report)
        self.assertIn("refunded consumers unknown", text)
        self.assertNotIn("refunded here", text)

    def test_absence_phrases(self) -> None:
        self.assertTrue(bws.ABSENCE_CLAIM_RE.search("There are no other consumers of this event."))
        self.assertTrue(bws.ABSENCE_CLAIM_RE.search("Nothing else depends on it."))
        for phrase in ("No downstream callers exist.", "It is safe to add this event.", "Nothing reads this topic.", "The topic is orphaned."):
            self.assertTrue(bws.ABSENCE_CLAIM_RE.search(phrase), phrase)
        self.assertFalse(bws.ABSENCE_CLAIM_RE.search("ledger-consumer@abc1234 does not subscribe to it."))


class AbsenceClaimScopeTests(unittest.TestCase):
    def test_scoped_search_statements_are_not_claims(self) -> None:
        for text in (
            "ledger-consumer@abc1234 has no subscribers for payment.refunded.v1.",
            "Found no callers in ledger-consumer@abc1234:ledger/x.py",
            "Searched ledger-consumer@abc1234; no subscribers there.",
        ):
            self.assertFalse(bws.has_absence_claim(text), text)

    def test_unscoped_claims_are_detected_even_beside_a_scoped_sentence(self) -> None:
        self.assertTrue(bws.has_absence_claim("There are no consumers of this event."))
        self.assertTrue(
            bws.has_absence_claim("ledger-consumer@abc1234 subscribes to completed only. Nothing else depends on it.")
        )

    def test_observe_run_uses_the_scoped_check(self) -> None:
        case = _load("wsib-absence-in-inspected-sibling-no-claim")
        ok = br.CaseResult(case.id, "patch", "executed", produced_findings=())
        scoped = bws.observe_run(case, ok, "ledger-consumer@abc1234 has no subscribers for it.", arm="on")
        unscoped = bws.observe_run(case, ok, "There are no consumers of this event.", arm="on")
        self.assertFalse(scoped.absence_claim)
        self.assertTrue(unscoped.absence_claim)


if __name__ == "__main__":
    unittest.main()
