#!/usr/bin/env python3
"""Behavioural coverage for the benchmark finding match criteria (Issue #54).

Contract: docs/benchmark/match-criteria.md. Driven through the single
test-only reference matcher (tests/reference/benchmark_match.py); this
module never defines a second one. Expected findings are built with the
bf.ExpectedFinding shape (#50); produced findings with br.ProducedFinding
(#52).

What is proven here:

1. every §8 worked example classifies exactly as the doc's Result column
   (data-driven), and two evaluations agree;
2. each axis (location §3, defect §4) resolves as documented at its
   boundaries;
3. `alternatives`, `any_of`, and `match: optional` resolve into the entry
   outcome per §6.

Turning these results into counts / rates (#55), severity accuracy (#56),
and duplicate noise (#57) is out of scope.
"""

from __future__ import annotations

import unittest

from tests.reference import benchmark_fixture as bf
from tests.reference import benchmark_match as bm
from tests.reference import benchmark_runner as br
from tests.support.paths import REPO_ROOT


def _exp(
    *,
    key: str = "e",
    severity: str = "P1",
    path: str | None = "auth/login.py",
    intent: str = "line",
    symbol: str | None = None,
    anchor: str | None = None,
    lines: tuple[int, int] | None = None,
    claim: str = "a cause leads to a faulty behavior",
    defect_kind: str | None = None,
    required: bool = True,
    alternatives: tuple[dict, ...] = (),
) -> bf.ExpectedFinding:
    location: dict | None = None
    if path is not None or intent == "repository":
        location = {"location_intent": intent}
        if path is not None:
            location["path"] = path
        if symbol is not None:
            location["symbol"] = symbol
        if anchor is not None:
            location["anchor"] = anchor
        if lines is not None:
            location["lines"] = {"start": lines[0], "end": lines[1]}
    return bf.ExpectedFinding(
        key=key,
        severities=(severity,),
        required=required,
        location=location,
        claim=claim,
        defect_kind=defect_kind,
        alternatives=alternatives,
    )


def _any_of(key: str, *members: bf.ExpectedFinding, required: bool = True) -> bf.ExpectedFinding:
    return bf.ExpectedFinding(key=key, severities=(), required=required, members=tuple(members))


def _prod(
    *,
    severity: str = "P1",
    path: str | None = "auth/login.py",
    symbol: str | None = None,
    anchor: str | None = None,
    line: int | None = None,
    lines: tuple[int, int] | None = None,
    claim: str | None = None,
    defect_kind: str | None = None,
) -> br.ProducedFinding:
    location: dict = {}
    if path is not None:
        location["path"] = path
    if symbol is not None:
        location["symbol"] = symbol
    if anchor is not None:
        location["anchor"] = anchor
    if lines is not None:
        location["lines"] = {"start": lines[0], "end": lines[1]}
    elif line is not None:
        location["line"] = line
    extra = {"defect_kind": defect_kind} if defect_kind else {}
    return br.ProducedFinding(severity=severity, location=location, claim=claim, extra=extra)


# ── §8 worked examples, verbatim ─────────────────────────────────────────

_CMD_CLAIM = "unsanitized name reaches a shell true command injection"

WORKED_EXAMPLES = [
    (
        "1 exact match",
        _exp(path="auth/login.py", symbol="authenticate", lines=(40, 40),
             claim=_CMD_CLAIM, defect_kind="command-injection"),
        _prod(path="auth/login.py", symbol="authenticate", line=41,
              defect_kind="command-injection"),
        bm.MatchResult.MATCH,
    ),
    (
        "2 defect_kind absent on produced, claim subset",
        _exp(path="auth/login.py", symbol="authenticate", lines=(40, 40),
             claim=_CMD_CLAIM, defect_kind="command-injection"),
        _prod(path="auth/login.py", line=40,
              claim="unsanitized name reaches a shell true command"),
        bm.MatchResult.MATCH,
    ),
    (
        "3 wrong file",
        _exp(path="auth/login.py", symbol="authenticate", lines=(40, 40),
             claim=_CMD_CLAIM, defect_kind="command-injection"),
        _prod(path="auth/session.py", line=12, defect_kind="command-injection"),
        bm.MatchResult.NO_MATCH,
    ),
    (
        "4 adjacent symbol",
        _exp(path="auth/login.py", symbol="authenticate", lines=(40, 40),
             claim=_CMD_CLAIM, defect_kind="command-injection"),
        _prod(path="auth/login.py", symbol="build_login_command",
              defect_kind="command-injection"),
        bm.MatchResult.NEAR_MISS,
    ),
    (
        "5 contradictory defect_kind",
        _exp(path="report/export.py", lines=(88, 88),
             claim="user controlled export path escapes the export directory path traversal",
             defect_kind="path-traversal"),
        _prod(path="report/export.py", line=88,
              claim="export path argument is not validated",
              defect_kind="missing-input-validation"),
        bm.MatchResult.NO_MATCH,
    ),
    (
        "6 same mechanism, coarser granularity",
        _exp(path="pagination.py", lines=(15, 15),
             claim="slice end off by one page repeats one row from the next page"),
        _prod(path="pagination.py", line=15,
              claim="off by one in pagination page bounds"),
        bm.MatchResult.NEAR_MISS,
    ),
]


class WorkedExampleTests(unittest.TestCase):
    def test_every_worked_example_classifies_as_documented(self) -> None:
        for name, expected, produced, want in WORKED_EXAMPLES:
            with self.subTest(row=name):
                got = bm.match_pair(expected, produced)
                self.assertEqual(got.result, want, f"{name}: {got.as_dict()}")

    def test_worked_examples_are_deterministic(self) -> None:
        first = [bm.match_pair(e, p).as_dict() for _, e, p, _ in WORKED_EXAMPLES]
        second = [bm.match_pair(e, p).as_dict() for _, e, p, _ in WORKED_EXAMPLES]
        self.assertEqual(first, second)

    def test_row5_entry_outcome_is_match_via_the_any_of_member(self) -> None:
        # §8 note: same produced finding is NO_MATCH vs the path-traversal
        # member but MATCH vs the missing-input-validation member; the
        # entry (an any_of group) therefore resolves to MATCH.
        _, _, produced, _ = WORKED_EXAMPLES[4]
        group = _any_of(
            "export-path",
            _exp(key="pt", path="report/export.py", lines=(88, 88),
                 claim="user controlled export path escapes the export directory path traversal",
                 defect_kind="path-traversal"),
            _exp(key="miv", path="report/export.py", lines=(88, 88),
                 claim="export path argument is not validated",
                 defect_kind="missing-input-validation"),
        )
        outcome = bm.evaluate_entry(group, [produced])
        self.assertEqual(outcome.result, bm.MatchResult.MATCH)
        self.assertEqual(outcome.via, "any_of:miv")
        self.assertEqual(outcome.member_results["pt"], bm.MatchResult.NO_MATCH)
        self.assertEqual(outcome.member_results["miv"], bm.MatchResult.MATCH)


class LocationAxisTests(unittest.TestCase):
    def test_different_path_is_none(self) -> None:
        r = bm.location_match(
            bm.Descriptor.from_expected(_exp(path="a/x.py")),
            bm.Descriptor.from_produced(_prod(path="a/y.py", line=1)),
        )
        self.assertEqual(r, bm.LocationMatch.NONE)

    def test_unplaceable_produced_finding_is_none(self) -> None:
        r = bm.location_match(
            bm.Descriptor.from_expected(_exp(path="a/x.py")),
            bm.Descriptor.from_produced(br.ProducedFinding(severity="P1", location={}, claim="x")),
        )
        self.assertEqual(r, bm.LocationMatch.NONE)

    def test_line_drift_within_window_stays_exact(self) -> None:
        r = bm.location_match(
            bm.Descriptor.from_expected(_exp(path="a/x.py", lines=(40, 40))),
            bm.Descriptor.from_produced(_prod(path="a/x.py", line=43)),
        )
        self.assertEqual(r, bm.LocationMatch.EXACT)

    def test_line_drift_outside_window_is_near(self) -> None:
        r = bm.location_match(
            bm.Descriptor.from_expected(_exp(path="a/x.py", lines=(40, 40))),
            bm.Descriptor.from_produced(_prod(path="a/x.py", line=44)),
        )
        self.assertEqual(r, bm.LocationMatch.NEAR)

    def test_symbol_mismatch_is_near_even_on_the_same_line(self) -> None:
        r = bm.location_match(
            bm.Descriptor.from_expected(_exp(path="a/x.py", symbol="f", lines=(10, 10))),
            bm.Descriptor.from_produced(_prod(path="a/x.py", symbol="g", line=10)),
        )
        self.assertEqual(r, bm.LocationMatch.NEAR)

    def test_repository_intent_matches_a_pathless_finding(self) -> None:
        exp = _exp(path=None, intent="repository", claim="no CI config anywhere")
        r = bm.location_match(
            bm.Descriptor.from_expected(exp),
            bm.Descriptor.from_produced(br.ProducedFinding(severity="P2", location={}, claim="no CI config anywhere")),
        )
        self.assertEqual(r, bm.LocationMatch.EXACT)

    def test_anchor_off_the_reported_line_is_near(self) -> None:
        post_image = "\n".join(f"line {i}" for i in range(1, 30))  # 'unsafe(' nowhere
        exp = _exp(path="a/x.py", anchor="unsafe(", lines=(5, 5), claim="c")
        r = bm.location_match(
            bm.Descriptor.from_expected(exp),
            bm.Descriptor.from_produced(_prod(path="a/x.py", line=5)),
            post_image=post_image,
        )
        self.assertEqual(r, bm.LocationMatch.NEAR)


class DefectAxisTests(unittest.TestCase):
    def test_equal_defect_kind_corresponds(self) -> None:
        self.assertEqual(
            bm.defect_match(
                bm.Descriptor.from_expected(_exp(defect_kind="sql-injection")),
                bm.Descriptor.from_produced(_prod(defect_kind="sql-injection")),
            ),
            bm.DefectMatch.CORRESPONDS,
        )

    def test_different_defect_kind_is_unrelated(self) -> None:
        self.assertEqual(
            bm.defect_match(
                bm.Descriptor.from_expected(_exp(defect_kind="sql-injection")),
                bm.Descriptor.from_produced(_prod(defect_kind="xss")),
            ),
            bm.DefectMatch.UNRELATED,
        )

    def test_claim_subset_corresponds_when_no_defect_kind(self) -> None:
        self.assertEqual(
            bm.defect_match(
                bm.Descriptor.from_expected(_exp(claim="tainted user input reaches the sql query")),
                bm.Descriptor.from_produced(_prod(claim="user input reaches the sql query")),
            ),
            bm.DefectMatch.CORRESPONDS,
        )

    def test_partial_overlap_is_related_then_unrelated(self) -> None:
        related = bm.defect_match(
            bm.Descriptor.from_expected(_exp(claim="slice end off by one page repeats one row from the next page")),
            bm.Descriptor.from_produced(_prod(claim="off by one in pagination page bounds")),
        )
        self.assertEqual(related, bm.DefectMatch.RELATED)
        unrelated = bm.defect_match(
            bm.Descriptor.from_expected(_exp(claim="race condition on the shared counter")),
            bm.Descriptor.from_produced(_prod(claim="missing docstring on the helper")),
        )
        self.assertEqual(unrelated, bm.DefectMatch.UNRELATED)

    def test_no_assessable_defect_is_unrelated(self) -> None:
        self.assertEqual(
            bm.defect_match(
                bm.Descriptor.from_expected(_exp(claim="something is wrong")),
                bm.Descriptor.from_produced(_prod(claim=None)),
            ),
            bm.DefectMatch.UNRELATED,
        )


class EntryResolutionTests(unittest.TestCase):
    def test_alternative_location_makes_the_entry_match(self) -> None:
        entry = _exp(
            key="dup",
            path="a/primary.py",
            lines=(3, 3),
            claim="duplicated branch logic",
            defect_kind="duplication",
            alternatives=({"location": {"location_intent": "line", "path": "a/other.py"}},),
        )
        produced = _prod(path="a/other.py", line=3, defect_kind="duplication")
        outcome = bm.evaluate_entry(entry, [produced])
        self.assertEqual(outcome.result, bm.MatchResult.MATCH)
        self.assertEqual(outcome.via, "alternative:0")

    def test_optional_entry_with_no_match_is_not_a_missed_required(self) -> None:
        entry = _exp(required=False, path="a/x.py", lines=(1, 1), claim="optional smell")
        outcome = bm.evaluate_entry(entry, [_prod(path="b/y.py", line=99, claim="unrelated")])
        self.assertEqual(outcome.result, bm.MatchResult.NO_MATCH)
        self.assertFalse(outcome.is_missed_required)

    def test_required_entry_with_no_match_is_a_missed_required(self) -> None:
        entry = _exp(required=True, path="a/x.py", lines=(1, 1), claim="the real bug", defect_kind="bug")
        outcome = bm.evaluate_entry(entry, [_prod(path="b/y.py", line=99, defect_kind="other")])
        self.assertTrue(outcome.is_missed_required)
        self.assertIsNone(outcome.produced_index)
        self.assertIsNone(outcome.via)

    def test_best_of_several_produced_findings_wins_lowest_index_on_a_tie(self) -> None:
        entry = _exp(path="a/x.py", symbol="f", lines=(10, 10), claim="c", defect_kind="bug")
        near = _prod(path="a/x.py", symbol="g", line=10, defect_kind="bug")   # NEAR_MISS
        exact = _prod(path="a/x.py", symbol="f", line=10, defect_kind="bug")  # MATCH
        self.assertEqual(bm.evaluate_entry(entry, [near, exact]).produced_index, 1)
        # two equal MATCHes -> lower index wins
        self.assertEqual(bm.evaluate_entry(entry, [exact, exact]).produced_index, 0)


class ReferenceModuleTests(unittest.TestCase):
    def test_module_is_declared_test_only(self) -> None:
        head = (REPO_ROOT / "tests" / "reference" / "benchmark_match.py").read_text(encoding="utf-8")[:600]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_matcher_consumes_the_shared_reference_models(self) -> None:
        raw = (REPO_ROOT / "tests" / "reference" / "benchmark_match.py").read_text(encoding="utf-8")
        self.assertIn("from tests.reference import benchmark_fixture as bf", raw)
        self.assertIn("from tests.reference import benchmark_runner as br", raw)


if __name__ == "__main__":
    unittest.main()
