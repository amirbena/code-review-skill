#!/usr/bin/env python3
"""Behavioural coverage for the benchmark citation-existence check (Issue #349).

Contract: runtime_platform/benchmark/citation-fidelity.md. Driven through
the reference check (runtime_platform/benchmark/reference/benchmark_citation.py)
over the single reference runner's captured workspace text
(``CaseResult.cited_sources``); this module defines no second runner,
matcher, or location parser.

What is proven here:

1. a genuine citation is ``verified`` and a deliberately fabricated one is
   ``fabricated`` with the documented reason, end to end through the real
   runner path (materialize -> review -> capture -> check);
2. every existing corpus defect case, reviewed by a stub that cites exactly
   what its own fixture expects, produces zero fabricated findings — the
   "no known-good finding is flagged" bar;
3. each §3 reason (missing file, out-of-range line, absent symbol, absent
   snippet) fires alone, and the safe-side rules hold: a locator quote, a
   prose symbol, a pathless location, and an undecidable file are never
   flagged;
4. path escapes (absolute, ``..``, symlink) read as not-a-file-of-the-tree
   without ever being read;
5. the metric is its own category: it is independent of the #54/#55 match
   outcome, and the aggregate/section (§5, §6) are plain sums with one
   exact-rational rate and never touch ``has_regressions``.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import yaml

from runtime_platform.benchmark.reference import benchmark_citation as bc
from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_metrics as bmet
from runtime_platform.benchmark.reference import benchmark_runner as br
from runtime_platform.benchmark.scripts.benchmark_review_adapter import parse_review_output
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus"
PAGINATION = CORPUS_DIR / "correctness-off-by-one-pagination.yaml"


def _load(path: Path) -> bf.BenchmarkCase:
    return bf.parse_case(yaml.safe_load(path.read_text(encoding="utf-8")))


def _pf(location, *, quotes=(), claim="a claim") -> br.ProducedFinding:
    extra = {"evidence_quotes": list(quotes)} if quotes else {}
    return br.ProducedFinding(severity="P1", location=location, claim=claim, extra=extra)


def _run_one(case: bf.BenchmarkCase, *produced: br.ProducedFinding) -> br.CaseResult:
    run = br.run_cases([case], lambda _ws: list(produced))
    (result,) = run.case_results
    return result


def _check(result: br.CaseResult, case: bf.BenchmarkCase) -> bc.CaseCitationFidelity:
    return bc.compute_case_citation_fidelity(case, result)


class EndToEndThroughTheRunnerTests(unittest.TestCase):
    """§2, §3: capture inside the workspace, then check — genuine vs fabricated."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.case = _load(PAGINATION)

    def test_genuine_citation_is_verified(self) -> None:
        genuine = _pf(
            {"path": "app/pagination.py", "lines": {"start": 3, "end": 3}, "symbol": "page"},
            quotes=["offset + page_size + 1"],
        )
        result = _run_one(self.case, genuine)
        self.assertEqual(set(result.cited_sources), {"app/pagination.py"})

        m = _check(result, self.case)
        self.assertEqual((m.verified, m.fabricated, m.unverifiable), (1, 0, 0))
        self.assertEqual(m.fabrication_rate, Fraction(0))

    def test_fabricated_location_and_snippet_is_flagged(self) -> None:
        fabricated = _pf(
            {"path": "app/paginator.py", "line": 400, "symbol": "paginate_all"},
            quotes=["os.system(user_input)"],
        )
        m = _check(_run_one(self.case, fabricated), self.case)
        self.assertEqual((m.verified, m.fabricated), (0, 1))
        self.assertEqual(m.fabricated_findings[0]["reasons"], [bc.FILE_MISSING])
        self.assertEqual(m.fabricated_findings[0]["path"], "app/paginator.py")

    def test_real_file_with_fabricated_line_symbol_and_snippet(self) -> None:
        fabricated = _pf(
            {"path": "app/pagination.py", "lines": {"start": 90, "end": 95}, "symbol": "paginate_all"},
            quotes=["os.system(user_input)"],
        )
        m = _check(_run_one(self.case, fabricated), self.case)
        # line out of range -> the snippet is then checked against the whole file
        self.assertEqual(
            m.fabricated_findings[0]["reasons"],
            [bc.LINE_OUT_OF_RANGE, bc.SYMBOL_ABSENT, bc.SNIPPET_ABSENT],
        )

    def test_genuine_and_fabricated_are_counted_separately(self) -> None:
        genuine = _pf({"path": "app/pagination.py", "line": 3})
        fabricated = _pf({"path": "nope.py", "line": 1})
        m = _check(_run_one(self.case, genuine, fabricated), self.case)
        self.assertEqual((m.produced, m.verified, m.fabricated), (2, 1, 1))
        self.assertEqual(m.fabrication_rate, Fraction(1, 2))
        self.assertEqual(m.fabricated_findings[0]["index"], 1)

    def test_capture_is_not_part_of_the_stable_result_shape(self) -> None:
        result = _run_one(self.case, _pf({"path": "app/pagination.py", "line": 1}))
        self.assertNotIn("cited_sources", result.as_dict())


class CorpusKnownGoodTests(unittest.TestCase):
    """The 'no known-good finding is flagged' bar: cite exactly what each
    corpus fixture's own expected entries cite, in the reviewed tree."""

    def test_no_corpus_case_flags_its_own_expected_citations(self) -> None:
        checked = 0
        for path in sorted(CORPUS_DIR.glob("*.yaml")):
            case = _load(path)

            def reviewer(workspace: Path, case=case) -> list[br.ProducedFinding]:
                out = []
                for entry in case.findings:
                    loc = entry.location or {}
                    rel, anchor = loc.get("path"), loc.get("anchor")
                    if not rel or not anchor or not (workspace / rel).is_file():
                        continue
                    lines = (workspace / rel).read_text(encoding="utf-8").splitlines()
                    hit = next((i for i, ln in enumerate(lines, 1) if anchor in ln), None)
                    if hit is None:
                        continue
                    location = {"path": rel, "line": hit}
                    if loc.get("symbol"):
                        location["symbol"] = loc["symbol"]
                    out.append(_pf(location, quotes=[anchor]))
                return out

            (result,) = br.run_cases([case], reviewer).case_results
            m = _check(result, case)
            self.assertEqual(m.fabricated, 0, f"{case.id}: {m.fabricated_findings}")
            checked += m.verified
        self.assertGreaterEqual(checked, 3, "expected the defect cases to yield known-good findings")


class ReasonRuleTests(unittest.TestCase):
    """§3/§4 rules, driven directly over captured text."""

    TEXT = "\n".join(f"line {n}" for n in range(1, 41)) + "\ndef target(x):\n    return x + 1\n"

    def _check(self, finding, sources=None):
        return bc.check_finding(finding, {"a.py": self.TEXT} if sources is None else sources)

    def test_each_reason_fires_alone(self) -> None:
        cases = [
            (_pf({"path": "a.py", "line": 500}), (bc.LINE_OUT_OF_RANGE,)),
            (_pf({"path": "a.py", "lines": {"start": 5, "end": 3}}), (bc.LINE_OUT_OF_RANGE,)),
            (_pf({"path": "a.py", "line": 0}), (bc.LINE_OUT_OF_RANGE,)),
            (_pf({"path": "a.py", "symbol": "missing_fn"}), (bc.SYMBOL_ABSENT,)),
            (_pf({"path": "a.py", "line": 41}, quotes=["os.system(cmd)"]), (bc.SNIPPET_ABSENT,)),
        ]
        for finding, reasons in cases:
            with self.subTest(reasons=reasons):
                self.assertEqual(self._check(finding), (bc.FABRICATED, reasons))

    def test_last_line_is_in_range_and_one_past_is_not(self) -> None:
        last = len(self.TEXT.splitlines())
        self.assertEqual(self._check(_pf({"path": "a.py", "line": last}))[0], bc.VERIFIED)
        self.assertEqual(self._check(_pf({"path": "a.py", "line": last + 1}))[0], bc.FABRICATED)

    def test_qualified_and_called_symbols_resolve_to_their_leaf(self) -> None:
        for symbol in ("target", "target()", "Module.target", "mod::target", "Cls#target"):
            with self.subTest(symbol=symbol):
                self.assertEqual(self._check(_pf({"path": "a.py", "symbol": symbol}))[0], bc.VERIFIED)

    def test_prose_section_symbol_is_never_checked(self) -> None:
        finding = _pf({"path": "a.py", "symbol": "the setup section"})
        self.assertEqual(self._check(finding), (bc.VERIFIED, ()))

    def test_snippet_matches_whitespace_insensitively_and_by_token_coverage(self) -> None:
        for quote in ("return x+1", "return   x + 1", "def target( x ):", "return x + 1  # note"):
            with self.subTest(quote=quote):
                finding = _pf({"path": "a.py", "line": 42}, quotes=[quote])
                self.assertEqual(self._check(finding)[0], bc.VERIFIED)

    def test_reordered_or_scattered_tokens_do_not_count_as_present(self) -> None:
        for quote in ("x + return 1", "1 x return", "target(return x)", "x = target + 1 + line"):
            with self.subTest(quote=quote):
                finding = _pf({"path": "a.py", "line": 42}, quotes=[quote])
                self.assertEqual(self._check(finding), (bc.FABRICATED, (bc.SNIPPET_ABSENT,)))

    def test_in_order_match_is_line_local_and_multi_line_quotes_span_lines(self) -> None:
        # `def target(x): return x + 1` is on two consecutive lines (41-42)
        two_lines = _pf({"path": "a.py", "line": 42}, quotes=["def target(x):\n    return x + 2"])
        self.assertEqual(self._check(two_lines)[0], bc.VERIFIED)  # 5/6 tokens, in order
        # tokens spread over two lines do not satisfy a single-line quote
        spread = _pf({"path": "a.py", "line": 42}, quotes=["target x return 1"])
        self.assertEqual(self._check(spread), (bc.FABRICATED, (bc.SNIPPET_ABSENT,)))

    def test_unparsed_path_with_colon_is_unverifiable(self) -> None:
        finding = _pf({"path": "a.py:L42-L43"})
        self.assertIsNone(br.cited_path(finding.location))
        self.assertEqual(self._check(finding), (bc.UNVERIFIABLE, ()))

    def test_any_one_present_quote_is_enough(self) -> None:
        finding = _pf({"path": "a.py", "line": 42}, quotes=["os.system(cmd)", "return x + 1"])
        self.assertEqual(self._check(finding)[0], bc.VERIFIED)

    def test_locator_and_trivial_quotes_are_ignored(self) -> None:
        finding = _pf({"path": "a.py", "line": 42}, quotes=["a.py:42", "a.py:3-9", "None", "False", "x"])
        self.assertEqual(self._check(finding), (bc.VERIFIED, ()))

    def test_snippet_window_is_bounded_around_the_cited_line(self) -> None:
        # "return x + 1" is on line 42; the window is +/- SNIPPET_WINDOW_LINES.
        edge = 42 - bc.SNIPPET_WINDOW_LINES
        inside = _pf({"path": "a.py", "line": edge}, quotes=["return x + 1"])
        outside = _pf({"path": "a.py", "line": edge - 1}, quotes=["return x + 1"])
        self.assertEqual(self._check(inside)[0], bc.VERIFIED)
        self.assertEqual(self._check(outside), (bc.FABRICATED, (bc.SNIPPET_ABSENT,)))

    def test_path_only_citation_searches_the_whole_file(self) -> None:
        finding = _pf({"path": "a.py"}, quotes=["return x + 1"])
        self.assertEqual(self._check(finding)[0], bc.VERIFIED)

    def test_missing_file_short_circuits_other_reasons(self) -> None:
        finding = _pf({"path": "gone.py", "line": 999, "symbol": "nope"}, quotes=["zzz zzz"])
        self.assertEqual(self._check(finding, {"gone.py": None}), (bc.FABRICATED, (bc.FILE_MISSING,)))

    def test_undecidable_and_pathless_citations_are_unverifiable_not_fabricated(self) -> None:
        for location in (
            {"location_intent": "repository"},
            {"path": "big.py", "line": 1},  # runner could not decide (absent from sources)
            "not-a-mapping",
        ):
            with self.subTest(location=location):
                self.assertEqual(self._check(_pf(location), {}), (bc.UNVERIFIABLE, ()))

    def test_path_normalization_matches_the_runner_key(self) -> None:
        self.assertEqual(br.cited_path({"path": "./a\\b.py"}), "a/b.py")
        finding = _pf({"path": "./a.py", "line": 1})
        self.assertEqual(self._check(finding)[0], bc.VERIFIED)


class WorkedExampleTests(unittest.TestCase):
    """citation-fidelity.md §7, verbatim: the two-reader conformance bar."""

    TEXT = ReasonRuleTests.TEXT
    SOURCES = {"a.py": TEXT, "gone.py": None}  # big.py deliberately absent (row 10)

    ROWS = (
        (1, _pf({"path": "a.py", "line": 42}, quotes=["return x + 1"]), bc.VERIFIED, ()),
        (2, _pf({"path": "gone.py", "line": 1}), bc.FABRICATED, (bc.FILE_MISSING,)),
        (3, _pf({"path": "a.py", "line": 500}), bc.FABRICATED, (bc.LINE_OUT_OF_RANGE,)),
        (4, _pf({"path": "a.py", "symbol": "missing_fn"}), bc.FABRICATED, (bc.SYMBOL_ABSENT,)),
        (5, _pf({"path": "a.py", "line": 42}, quotes=["os.system(cmd)"]), bc.FABRICATED, (bc.SNIPPET_ABSENT,)),
        (6, _pf({"path": "a.py", "line": 1}, quotes=["return x + 1"]), bc.FABRICATED, (bc.SNIPPET_ABSENT,)),
        (7, _pf({"path": "a.py", "line": 42}, quotes=["a.py:42"]), bc.VERIFIED, ()),
        (8, _pf({"path": "a.py", "symbol": "the setup section"}), bc.VERIFIED, ()),
        (9, _pf({"location_intent": "repository"}), bc.UNVERIFIABLE, ()),
        (10, _pf({"path": "big.py", "line": 1}), bc.UNVERIFIABLE, ()),
        (
            11,
            _pf({"path": "a.py", "line": 500, "symbol": "missing_fn"}, quotes=["os.system(cmd)"]),
            bc.FABRICATED,
            (bc.LINE_OUT_OF_RANGE, bc.SYMBOL_ABSENT, bc.SNIPPET_ABSENT),
        ),
        (12, _pf({"path": "a.py", "line": 42}, quotes=["x + return 1"]), bc.FABRICATED, (bc.SNIPPET_ABSENT,)),
        (13, _pf({"path": "a.py:L42-L43"}), bc.UNVERIFIABLE, ()),
    )

    def test_every_documented_row(self) -> None:
        for number, finding, status, reasons in self.ROWS:
            with self.subTest(row=number):
                self.assertEqual(bc.check_finding(finding, self.SOURCES), (status, reasons))
                # two runs agree (§6 determinism)
                self.assertEqual(
                    bc.check_finding(finding, self.SOURCES), bc.check_finding(finding, self.SOURCES)
                )

    def test_documented_file_shape(self) -> None:
        self.assertEqual(len(self.TEXT.splitlines()), 42)
        self.assertEqual(self.TEXT.splitlines()[40:], ["def target(x):", "    return x + 1"])


class ParsedReviewOutputTests(unittest.TestCase):
    """Real reviewer-report locations, through the production parser, the
    runner capture, and the check (issue #349 review F1): a genuine citation
    is never flagged whichever coordinate spelling the reviewer used."""

    REPORT = (
        "**Result: ⚠️ Changes Requested**\n\n"
        "#### F1 [P1] Off-by-one page end\n\n"
        "- **Location:** `{loc}`\n"
        "- **Evidence:** `end = offset + page_size + 1` returns one extra row.\n"
        "- **Impact:** rows repeat.\n"
        "- **Fix:** drop the +1.\n"
    )

    def test_genuine_finding_is_never_flagged_for_any_location_spelling(self) -> None:
        case = _load(PAGINATION)
        for loc in (
            "app/pagination.py:3",
            "app/pagination.py:3-3",
            "app/pagination.py:L3",
            "app/pagination.py:L3-L4",
            "app/pagination.py:3 - 4",
            "app/pagination.py:3,4",
            "app/pagination.py:page",
        ):
            with self.subTest(loc=loc):
                findings = parse_review_output(self.REPORT.format(loc=loc))
                (result,) = br.run_cases([case], lambda _ws, f=findings: f).case_results
                self.assertEqual(_check(result, case).fabricated, 0)

    def test_genuinely_fabricated_report_is_still_flagged(self) -> None:
        case = _load(PAGINATION)
        for loc in ("app/ghost.py:3", "app/ghost.py:L3-L4"):
            with self.subTest(loc=loc):
                findings = parse_review_output(self.REPORT.format(loc=loc))
                (result,) = br.run_cases([case], lambda _ws, f=findings: f).case_results
                self.assertEqual(_check(result, case).fabricated_findings[0]["reasons"], [bc.FILE_MISSING])

    def test_still_unparsed_spelling_is_undecidable_not_fabricated(self) -> None:
        case = _load(PAGINATION)
        findings = parse_review_output(self.REPORT.format(loc="app/ghost.py:a-b"))
        (result,) = br.run_cases([case], lambda _ws: findings).case_results
        self.assertEqual(_check(result, case).unverifiable, 1)


class PathContainmentTests(unittest.TestCase):
    """§2: only files of the reviewed tree are ever read."""

    def test_escapes_are_not_files_of_the_tree_and_are_never_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws = root / "ws"
            ws.mkdir()
            (ws / "ok.py").write_text("x = 1\n", encoding="utf-8")
            outside = root / "secret.txt"
            outside.write_text("TOP SECRET\n", encoding="utf-8")
            os.symlink(outside, ws / "link.txt")
            (ws / "adir").mkdir()

            def f(path: str) -> br.ProducedFinding:
                return _pf({"path": path, "line": 1})

            sources = br._capture_cited_sources(
                [f("ok.py"), f("../secret.txt"), f(str(outside)), f("link.txt"), f("adir"), f("absent.py")],
                ws,
            )
        self.assertEqual(sources["ok.py"], "x = 1\n")
        for escaped in ("../secret.txt", str(outside), "link.txt", "adir", "absent.py"):
            self.assertIsNone(sources[escaped], escaped)

    def test_oversized_and_binary_files_are_undecidable_not_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "big.txt").write_bytes(b"a" * (br.MAX_CITED_FILE_BYTES + 1))
            (ws / "bin.dat").write_bytes(b"\xff\xfe\x00\x81")
            sources = br._capture_cited_sources(
                [_pf({"path": "big.txt"}), _pf({"path": "bin.dat"})], ws
            )
        self.assertEqual(sources, {})

    def test_distinct_path_cap_bounds_the_capture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            produced = [_pf({"path": f"f{i}.py"}) for i in range(br.MAX_CITED_PATHS + 5)]
            sources = br._capture_cited_sources(produced, ws)
        self.assertEqual(len(sources), br.MAX_CITED_PATHS)


class SeparateCategoryTests(unittest.TestCase):
    """§7: the signal is independent of the match/near-miss/no-match outcome."""

    def test_verified_citation_can_still_be_an_incorrect_finding(self) -> None:
        case = _load(PAGINATION)
        # Real location, unrelated claim: #55 scores it a false positive,
        # this check scores its citation as genuine.
        unrelated = _pf({"path": "app/pagination.py", "line": 1}, claim="tokens rotate hourly")
        result = _run_one(case, unrelated)

        self.assertEqual(_check(result, case).verified, 1)
        self.assertEqual(bmet.compute_case_metrics(case, result).false_positives, 1)

    def test_ledger_never_reads_expected_or_match_state(self) -> None:
        case = _load(PAGINATION)
        stripped = bf.BenchmarkCase(
            format=case.format,
            id=case.id,
            title=case.title,
            input=case.input,
            decision=None,
            findings_completeness="at-least",
            findings=(),
        )
        finding = _pf({"path": "app/pagination.py", "line": 3})
        result = _run_one(case, finding)
        self.assertEqual(_check(result, case).as_dict(), _check(result, stripped).as_dict())


class RunAggregateAndSectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = _load(PAGINATION)
        self.other = bf.BenchmarkCase(
            format=self.case.format,
            id="zz-other",
            title="t",
            input={"patch": "--- a\n+++ b\n"},
            decision=None,
            findings_completeness="exhaustive",
            findings=(),
        )

    def _run(self, *produced: br.ProducedFinding) -> bc.RunCitationFidelity:
        result = _run_one(self.case, *produced)
        errored = br.CaseResult(self.other.id, "patch", "error", error="reviewer-adapter-raised")
        return bc.compute_run_citation_fidelity([self.case, self.other], [result, errored])

    def test_errored_case_is_all_zero_and_flagged(self) -> None:
        run = self._run(_pf({"path": "nope.py"}))
        errored = run.by_id()["zz-other"]
        self.assertEqual((errored.status, errored.produced, errored.fabricated), ("errored", 0, 0))
        self.assertIsNone(errored.fabrication_rate)

    def test_case_with_no_result_is_treated_as_errored(self) -> None:
        run = bc.compute_run_citation_fidelity([self.other], [])
        self.assertEqual(run.per_case[0].status, "errored")

    def test_aggregate_is_plain_sums_with_one_rational_rate(self) -> None:
        run = self._run(_pf({"path": "app/pagination.py", "line": 1}), _pf({"path": "nope.py"}))
        agg = run.aggregate
        self.assertEqual(
            (agg.total_produced, agg.total_verified, agg.total_fabricated, agg.total_unverifiable),
            (2, 1, 1, 0),
        )
        self.assertEqual(agg.cases_with_fabricated_citations, 1)
        self.assertEqual(agg.fabrication_rate, Fraction(1, 2))
        self.assertEqual(agg.as_dict()["fabrication_rate"], "1/2")

    def test_rate_is_none_when_nothing_is_checkable(self) -> None:
        run = self._run(_pf({"location_intent": "repository"}))
        self.assertIsNone(run.aggregate.fabrication_rate)
        self.assertIsNone(run.aggregate.as_dict()["fabrication_rate"])

    def test_output_is_deterministic_and_ordered_by_id(self) -> None:
        a = self._run(_pf({"path": "nope.py"})).as_dict()
        b = self._run(_pf({"path": "nope.py"})).as_dict()
        self.assertEqual(a, b)
        self.assertEqual([c["id"] for c in a["cases"]], sorted(c["id"] for c in a["cases"]))

    def test_section_renders_candidate_alone_and_against_a_baseline(self) -> None:
        base = self._run(_pf({"path": "app/pagination.py", "line": 1}))
        cand = self._run(_pf({"path": "nope.py"}), _pf({"path": "nope2.py"}))

        self.assertEqual(set(bc.citation_fidelity_section(cand)), {"candidate"})
        section = bc.citation_fidelity_section(cand, baseline=base)
        self.assertEqual(
            section["aggregate"]["total_fabricated"], {"baseline": 0, "candidate": 2, "delta": 2}
        )
        self.assertEqual(section["aggregate"]["fabrication_rate"], {"baseline": "0", "candidate": "1"})
        self.assertNotIn("has_regressions", section)


if __name__ == "__main__":
    unittest.main()
