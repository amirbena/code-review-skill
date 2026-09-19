#!/usr/bin/env python3
"""Conformance coverage for the `benchmark-result/v1` schema and validator (Issue #468).

Contract: runtime_platform/benchmark/benchmark-result-schema.md.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Iterator

from runtime_platform.benchmark.reference import benchmark_result_reference as ref
from runtime_platform.benchmark.scripts import benchmark_drift as bd
from runtime_platform.benchmark.scripts import benchmark_result as res
from tests.support.paths import REPO_ROOT

EXAMPLES = REPO_ROOT / "runtime_platform" / "benchmark" / "schemas" / "examples"
SHA = "a" * 40


def _load(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _resealed(record: dict[str, Any]) -> dict[str, Any]:
    return res.seal_record({k: v for k, v in record.items() if k != "content_sha256"})


def _required_paths(schema: dict[str, Any], node: dict[str, Any], prefix: tuple[str, ...] = ()) -> Iterator[tuple[str, ...]]:
    """Every required-field path in the result schema, walking objects and `cases` items."""
    if "$ref" in node:
        node = res._resolve(node["$ref"], schema)
    for name in node.get("required", ()):
        yield prefix + (name,)
    for name, child in node.get("properties", {}).items():
        if name == "cases":
            yield from _required_paths(schema, child["items"], prefix + (name, "0"))
        elif name != "unconfirmed":
            yield from _required_paths(schema, child, prefix + (name,))


def _delete(record: dict[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    mutated = copy.deepcopy(record)
    node: Any = mutated
    for part in path[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    del node[path[-1]]
    return mutated


class CanonicalHashingTests(unittest.TestCase):
    def test_canonical_json_matches_fingerprint_canonicalization(self) -> None:
        triple = {"case_id": "case-a", "drift_type": "decision-flip", "expected_finding_key": "-"}
        self.assertEqual(res.sha256_hex(res.canonical_json(triple)), bd.fingerprint(**triple))

    def test_canonical_json_ignores_key_order_and_whitespace(self) -> None:
        self.assertEqual(res.canonical_json({"b": 1, "a": [2, {"d": 1, "c": 2}]}), '{"a":[2,{"c":2,"d":1}],"b":1}')

    def test_content_sha256_excludes_itself_and_is_key_order_independent(self) -> None:
        record = _load("sentinel-bootstrap.record.json")
        reordered = dict(reversed(list(record.items())))
        self.assertEqual(res.content_sha256(record), record["content_sha256"])
        self.assertEqual(res.content_sha256(reordered), record["content_sha256"])

    def test_editing_a_sealed_record_is_detected(self) -> None:
        record = _load("sentinel-bootstrap.record.json")
        record["trigger"] = "manual"
        self.assertIn("content_sha256 does not match", "\n".join(res.validate_record(record)))


class RunIdTests(unittest.TestCase):
    def test_two_runs_of_one_lane_on_one_sha_and_day_are_distinct(self) -> None:
        first = res.make_run_id("sentinel", "2026-09-19T01:00:00Z", SHA)
        second = res.make_run_id("sentinel", "2026-09-19T13:30:05Z", SHA)
        self.assertNotEqual(first, second)
        self.assertEqual(first, "sentinel-20260919T010000Z-" + SHA[:12])

    def test_run_id_round_trips(self) -> None:
        run_id = res.make_run_id("comprehensive", "2026-09-19T01:00:00Z", SHA)
        self.assertEqual(res.parse_run_id(run_id), ("comprehensive", "20260919T010000Z", SHA[:12]))
        self.assertIsNone(res.parse_run_id("2026-09-19-" + SHA[:12]))

    def test_run_id_must_match_lane_start_and_sha(self) -> None:
        record = _load("sentinel-bootstrap.record.json")
        record["run_id"] = res.make_run_id("sentinel", "2026-09-17T01:00:00Z", record["provenance"]["repo_sha"])
        self.assertIn("run_id does not match", "\n".join(res.validate_record(_resealed(record))))


class ReferenceFixtureTests(unittest.TestCase):
    def test_reference_records_conform(self) -> None:
        for name in ("sentinel-bootstrap.record.json", "sentinel-compared-drift.record.json"):
            with self.subTest(name):
                self.assertEqual(res.validate_record(_load(name)), [])

    def test_reference_receipt_conforms_and_links_the_record(self) -> None:
        receipt = _load("sentinel-compared-drift.receipt.json")
        record = _load("sentinel-compared-drift.record.json")
        self.assertEqual(res.validate_receipt(receipt), [])
        self.assertEqual((receipt["run_id"], receipt["record_sha256"]), (record["run_id"], record["content_sha256"]))

    def test_compared_record_references_the_bootstrap_baseline(self) -> None:
        baseline, candidate = _load("sentinel-bootstrap.record.json"), _load("sentinel-compared-drift.record.json")
        self.assertEqual(candidate["baseline"]["run_id"], baseline["run_id"])
        self.assertEqual(candidate["baseline"]["record_sha256"], baseline["content_sha256"])

    def test_confirmed_drift_records_are_classify_drift_shaped(self) -> None:
        for item in _load("sentinel-compared-drift.record.json")["drift"]["confirmed"]:
            self.assertEqual(item["fingerprint"], bd.fingerprint(item["case_id"], item["drift_type"], item["expected_finding_key"]))


class RequiredFieldTests(unittest.TestCase):
    def test_every_required_field_is_enforced(self) -> None:
        schema = res.load_schema(res.RESULT_SCHEMA_PATH)
        record = _load("sentinel-compared-drift.record.json")
        paths = list(_required_paths(schema, schema))
        self.assertGreater(len(paths), 60)
        for path in paths:
            with self.subTest(".".join(path)):
                errors = res.validate_record(_delete(record, path))
                self.assertTrue(any(f"missing required field '{path[-1]}'" in e for e in errors), errors)

    def test_field_table_groups_are_all_present(self) -> None:
        required = set(res.load_schema(res.RESULT_SCHEMA_PATH)["required"])
        for field in ("run_id", "trigger", "started_at", "sealed_at", "lane", "mode", "corpus", "provenance",
                      "runtime", "aggregate", "cases", "verification", "baseline", "drift", "execution",
                      "reproduction", "raw", "content_sha256"):
            self.assertIn(field, required)

    def test_unexpected_fields_and_bad_values_are_rejected(self) -> None:
        record = _load("sentinel-bootstrap.record.json")
        cases = [
            (lambda r: r.update(extra=1), "unexpected field"),
            (lambda r: r.update(trigger="cron"), "not one of"),
            (lambda r: r["corpus"].update(corpus_id="xyz"), "does not match"),
            (lambda r: r["cases"][0].update(fixture_digest="short"), "does not match"),
            (lambda r: r.update(schema="benchmark-result/v2"), "expected 'benchmark-result/v1'"),
            (lambda r: r["cases"].clear(), "fewer than 1"),
        ]
        for mutate, expected in cases:
            with self.subTest(expected):
                mutated = copy.deepcopy(record)
                mutate(mutated)
                self.assertIn(expected, "\n".join(res.validate_record(mutated)))

    def test_trailing_newline_in_an_anchored_pattern_is_rejected(self) -> None:
        record = _load("sentinel-bootstrap.record.json")
        record["cases"][0]["fixture_digest"] += "\n"
        record["raw"]["bundle_sha256"] += "\n"
        errors = "\n".join(res.validate_record(_resealed(record)))
        self.assertIn("$.cases[0].fixture_digest: does not match", errors)
        self.assertIn("$.raw.bundle_sha256: does not match", errors)

    def test_unanchored_prefix_pattern_still_matches(self) -> None:
        self.assertTrue(res._pattern_matches("^https://", "https://example.test/x"))
        self.assertFalse(res._pattern_matches("^https://", "http://example.test/x"))

    def test_non_finite_numbers_are_rejected(self) -> None:
        record = _load("sentinel-bootstrap.record.json")
        for value in (float("nan"), float("inf")):
            with self.subTest(value):
                record["execution"]["duration_s"] = value
                errors = "\n".join(res.validate_record(_resealed(record)))
                self.assertIn("$.execution.duration_s: expected type ['number'], got a non-finite number", errors)

    def test_drift_records_are_closed_to_unknown_fields(self) -> None:
        for group in ("observations", "confirmed", "unconfirmed"):
            with self.subTest(group):
                record = _load("sentinel-compared-drift.record.json")
                record["drift"][group][0]["extra"] = 1
                errors = "\n".join(res.validate_record(_resealed(record)))
                self.assertIn(f"$.drift.{group}[0].extra: unexpected field", errors)

    def test_receipt_missing_field_is_rejected(self) -> None:
        receipt = _load("sentinel-compared-drift.receipt.json")
        for field in list(receipt):
            with self.subTest(field):
                mutated = {k: v for k, v in receipt.items() if k != field}
                self.assertTrue(res.validate_receipt(mutated))


class FixtureDigestComparabilityTests(unittest.TestCase):
    def _cases(self) -> list[dict[str, Any]]:
        return [{"id": f"case-{n}", "fixture_digest": f"{n}" * 64} for n in "123"]

    def test_fixture_change_downgrades_only_the_affected_case(self) -> None:
        baseline = self._cases()
        candidate = copy.deepcopy(baseline)
        candidate[1]["fixture_digest"] = "f" * 64
        part = res.partition_case_comparability(candidate, baseline)
        self.assertEqual(part["comparable_case_ids"], ["case-1", "case-3"])
        self.assertEqual([c["id"] for c in part["incomparable_cases"]], ["case-2"])
        self.assertEqual(part["incomparable_cases"][0]["reason"], res.FIXTURE_DIGEST_MISMATCH)

    def test_added_and_removed_cases_never_make_others_incomparable(self) -> None:
        baseline = self._cases()
        candidate = baseline[:2] + [{"id": "case-9", "fixture_digest": "9" * 64}]
        part = res.partition_case_comparability(candidate, baseline)
        self.assertEqual(part["comparable_case_ids"], ["case-1", "case-2"])
        self.assertEqual((part["added_case_ids"], part["removed_case_ids"]), (["case-9"], ["case-3"]))
        self.assertEqual(part["incomparable_cases"], [])

    def test_reference_record_partition_matches_a_recomputation(self) -> None:
        baseline, candidate = _load("sentinel-bootstrap.record.json"), _load("sentinel-compared-drift.record.json")
        part = res.partition_case_comparability(candidate["cases"], baseline["cases"])
        self.assertEqual(part["comparable_case_ids"], candidate["baseline"]["comparable_case_ids"])
        self.assertEqual(part["incomparable_cases"], candidate["baseline"]["incomparable_cases"])

    def test_fixture_digest_is_the_sha256_of_file_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fx.yaml"
            path.write_text("id: x\n", encoding="utf-8")
            first = res.fixture_digest(path)
            path.write_text("id: y\n", encoding="utf-8")
            self.assertNotEqual(first, res.fixture_digest(path))


class SemanticRuleTests(unittest.TestCase):
    def _errors(self, name: str, mutate: Any) -> str:
        record = _load(name)
        mutate(record)
        return "\n".join(res.validate_record(_resealed(record)))

    def test_lane_must_be_the_canonical_lane_of_mode(self) -> None:
        self.assertEqual(res.validate_record(_resealed({**_load("sentinel-bootstrap.record.json"), "mode": "full"})), [])
        errors = self._errors("sentinel-bootstrap.record.json", lambda r: r.update(mode="comprehensive"))
        self.assertIn("canonical lane", errors)

    def test_only_verified_runs_are_sealed(self) -> None:
        errors = self._errors("sentinel-bootstrap.record.json", lambda r: r["verification"].update(overall_verified=False))
        self.assertIn("only verified runs are sealed", errors)

    def test_timestamps_must_be_ordered(self) -> None:
        errors = self._errors("sentinel-bootstrap.record.json", lambda r: r.update(sealed_at="2026-09-01T00:00:00Z"))
        self.assertIn("timestamps must satisfy", errors)

    def test_case_count_and_membership_must_match_cases(self) -> None:
        errors = self._errors("sentinel-bootstrap.record.json", lambda r: r["corpus"].update(case_count=99))
        self.assertIn("corpus.case_count", errors)
        errors = self._errors("sentinel-bootstrap.record.json", lambda r: r["cases"][0].update(id="renamed"))
        self.assertIn("membership_digest", errors)

    def test_duplicate_case_ids_are_rejected(self) -> None:
        errors = self._errors("sentinel-bootstrap.record.json", lambda r: r["cases"][1].update(id=r["cases"][0]["id"]))
        self.assertIn("must be unique", errors)

    def test_bootstrap_baseline_cannot_reference_a_baseline_or_evaluate_drift(self) -> None:
        errors = self._errors("sentinel-bootstrap.record.json", lambda r: r["baseline"].update(run_id="sentinel-20260101T000000Z-" + "0" * 12))
        self.assertIn("must carry no baseline reference", errors)
        errors = self._errors("sentinel-bootstrap.record.json", lambda r: r["drift"]["outcome"].update(status="none", reason=None))
        self.assertIn("requires drift.outcome.status 'not-evaluated'", errors)

    def test_compared_baseline_requires_a_reference(self) -> None:
        errors = self._errors("sentinel-compared-drift.record.json", lambda r: r["baseline"].update(record_sha256=None))
        self.assertIn("requires baseline.run_id and baseline.record_sha256", errors)

    def test_not_evaluated_requires_a_reason(self) -> None:
        errors = self._errors("sentinel-bootstrap.record.json", lambda r: r["drift"]["outcome"].update(reason=None))
        self.assertIn("reason is required", errors)

    def test_drift_outcome_must_agree_with_confirmed_drift(self) -> None:
        errors = self._errors("sentinel-compared-drift.record.json", lambda r: r["drift"]["outcome"].update(status="none"))
        self.assertIn("contradicts confirmed drift", errors)
        errors = self._errors("sentinel-compared-drift.record.json", lambda r: r["drift"].update(confirmed=[]))
        self.assertIn("partition drift.observations", errors)

    def test_fingerprint_must_match_its_identity_triple(self) -> None:
        errors = self._errors("sentinel-compared-drift.record.json", lambda r: r["drift"]["confirmed"][0].update(expected_finding_key="tampered-key"))
        self.assertIn("fingerprint of", errors)

    def test_drift_must_stay_inside_the_evaluated_comparable_scope(self) -> None:
        errors = self._errors("sentinel-compared-drift.record.json", lambda r: r["drift"]["evaluated_scope"].append("security-command-injection"))
        self.assertIn("within baseline.comparable_case_ids", errors)

    def test_evidence_is_bounded_and_limited_to_confirmed_cases(self) -> None:
        case_id = "correctness-off-by-one-pagination"
        errors = self._errors("sentinel-compared-drift.record.json", lambda r: r["drift"]["evidence"].update({case_id: "é" * 20000}))
        self.assertIn("exceeds 32768 bytes", errors)
        errors = self._errors("sentinel-compared-drift.record.json", lambda r: r["drift"]["evidence"].update({"quality-duplicated-branch-logic": "x"}))
        self.assertIn("not a confirmed-drift case", errors)

    def test_unconfirmed_drift_needs_a_documented_reason(self) -> None:
        errors = self._errors("sentinel-compared-drift.record.json", lambda r: r["drift"]["unconfirmed"][0].update(reason="flaky"))
        self.assertIn("not one of", errors)


class RealCorpusMeasurementTests(unittest.TestCase):
    """Growth-trigger assumptions of canonical-result-and-persistence.md §4, on the real corpus."""

    def test_records_over_the_real_corpus_conform_and_stay_inside_the_trigger(self) -> None:
        for lane in ("sentinel", "comprehensive"):
            with self.subTest(lane):
                stats = ref.measure(lane, ref.DEFAULT_CORPUS_ROOT)
                self.assertLess(stats["pretty_bytes"], 10 * 1024 * 1024)
                self.assertLess(stats["largest_case_bytes"], 2 * 1024)

    def test_a_year_of_records_stays_far_below_the_repository_trigger(self) -> None:
        sentinel = ref.measure("sentinel", ref.DEFAULT_CORPUS_ROOT)["pretty_bytes"]
        comprehensive = ref.measure("comprehensive", ref.DEFAULT_CORPUS_ROOT)["pretty_bytes"]
        per_year = 130 * sentinel + 52 * comprehensive
        self.assertLess(per_year, 100 * 1024 * 1024)


class CliTests(unittest.TestCase):
    def _run(self, *args: str) -> tuple[int, str]:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = res.main(list(args))
        return code, err.getvalue()

    def test_valid_record_and_receipt_exit_zero(self) -> None:
        self.assertEqual(self._run("validate", str(EXAMPLES / "sentinel-bootstrap.record.json"))[0], 0)
        self.assertEqual(self._run("validate", "--receipt", str(EXAMPLES / "sentinel-compared-drift.receipt.json"))[0], 0)

    def test_invalid_and_unreadable_inputs_exit_non_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{}", encoding="utf-8")
            code, err = self._run("validate", str(bad))
            self.assertEqual(code, 1)
            self.assertIn("missing required field", err)
            code, err = self._run("validate", str(Path(tmp) / "absent.json"))
            self.assertEqual(code, 1)
            self.assertIn("unreadable", err)


if __name__ == "__main__":
    unittest.main()
