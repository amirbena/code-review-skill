#!/usr/bin/env python3
"""Tests for scripts/sync_issue_labels.py — parsing, mapping, reconciliation.

GitHub's API is out of scope here; only the pure logic the workflow depends on.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sync_issue_labels as sil  # noqa: E402


STANDARD_BODY = """\
### Type

Research

### Area

Review Quality

### Priority

P1 — High

### Problem

Something is unclear.

### Goal

Make it clear.
"""


def _area_form_values() -> list[str]:
    path = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "engineering-task.yml"
    import yaml

    form = yaml.safe_load(path.read_text(encoding="utf-8"))
    area = next(b for b in form["body"] if b.get("id") == "area")
    return list(area["attributes"]["options"])


class ParseTests(unittest.TestCase):
    def test_standard_body(self) -> None:
        self.assertEqual(
            sil.parse_issue_fields(STANDARD_BODY),
            {"Type": "Research", "Area": "Review Quality", "Priority": "P1 — High"},
        )

    def test_unrelated_sections_ignored(self) -> None:
        fields = sil.parse_issue_fields(STANDARD_BODY + "\n### Dependencies\n\nDepends on: none\n")
        self.assertEqual(set(fields), {"Type", "Area", "Priority"})

    def test_tolerates_crlf_and_extra_whitespace(self) -> None:
        body = "###   Type   \r\n\r\n  Feature  \r\n\r\n###  Area\r\n\r\nResearch\r\n\r\n### Priority\r\n\r\nP3 — Low\r\n"
        self.assertEqual(
            sil.parse_issue_fields(body),
            {"Type": "Feature", "Area": "Research", "Priority": "P3 — Low"},
        )

    def test_no_response_is_absent(self) -> None:
        body = "### Type\n\n_No response_\n\n### Area\n\nResearch\n\n### Priority\n\nP2 — Medium\n"
        self.assertEqual(set(sil.parse_issue_fields(body)), {"Area", "Priority"})

    def test_manual_issue_without_fields(self) -> None:
        self.assertEqual(sil.parse_issue_fields("Just a plain issue.\n\nNo headings here."), {})

    def test_empty_body(self) -> None:
        self.assertEqual(sil.parse_issue_fields(""), {})


class MappingTests(unittest.TestCase):
    def test_every_type_value(self) -> None:
        for value, label in {
            "Feature": "type:feature",
            "Refactor": "type:refactor",
            "Quality": "type:quality",
            "Research": "type:research",
            "Documentation": "type:documentation",
            "Infrastructure": "type:infrastructure",
        }.items():
            self.assertEqual(sil.map_labels({"Type": value}), {label})

    def test_every_priority_value_and_dash_variants(self) -> None:
        for token, label in (("P1", "priority:P1"), ("P2", "priority:P2"), ("P3", "priority:P3")):
            word = {"P1": "High", "P2": "Medium", "P3": "Low"}[token]
            for dash in ("-", "–", "—", "−"):
                value = f"{token} {dash} {word}"
                self.assertEqual(sil.map_labels({"Priority": value}), {label}, value)

    def test_every_area_value_matches_form(self) -> None:
        for value in _area_form_values():
            self.assertIn(value, sil.AREA_LABELS, value)
        for value, label in sil.AREA_LABELS.items():
            self.assertEqual(sil.map_labels({"Area": value}), {label})

    def test_form_type_options_match_mapping(self) -> None:
        path = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "engineering-task.yml"
        import yaml

        form = yaml.safe_load(path.read_text(encoding="utf-8"))
        opts = {
            b["id"]: b["attributes"]["options"]
            for b in form["body"]
            if b.get("type") == "dropdown"
        }
        self.assertEqual(set(opts["type"]), set(sil.TYPE_LABELS))
        self.assertEqual(
            {sil._normalize_dashes(o) for o in opts["priority"]}, set(sil.PRIORITY_LABELS)
        )
        self.assertEqual(set(opts["area"]), set(sil.AREA_LABELS))

    def test_unknown_value_raises(self) -> None:
        with self.assertRaises(sil.UnknownFieldValue):
            sil.map_labels({"Type": "Chore"})
        with self.assertRaises(sil.UnknownFieldValue):
            sil.map_labels({"Priority": "P0 — Emergency"})


class ReconcileTests(unittest.TestCase):
    def test_adds_missing_managed_labels(self) -> None:
        add, remove = sil.reconcile(["bug"], {"type:research", "area:review-quality", "priority:P1"})
        self.assertEqual(add, ["area:review-quality", "priority:P1", "type:research"])
        self.assertEqual(remove, [])

    def test_removes_stale_managed_labels_only(self) -> None:
        add, remove = sil.reconcile(
            ["bug", "type:feature", "priority:P2", "area:research", "needs-discussion"],
            {"type:research", "area:research", "priority:P1"},
        )
        self.assertEqual(add, ["priority:P1", "type:research"])
        self.assertEqual(remove, ["priority:P2", "type:feature"])

    def test_unrelated_labels_preserved(self) -> None:
        add, remove = sil.reconcile(
            ["bug", "enhancement", "good first issue", "blocked", "type:research", "area:research", "priority:P1"],
            {"type:research", "area:research", "priority:P1"},
        )
        self.assertEqual((add, remove), ([], []))

    def test_idempotent_when_already_correct(self) -> None:
        desired = {"type:research", "area:review-quality", "priority:P1"}
        add, remove = sil.reconcile(sorted(desired) + ["bug"], desired)
        self.assertEqual((add, remove), ([], []))


class PlanTests(unittest.TestCase):
    def test_apply_from_standard_body(self) -> None:
        result = sil.plan(STANDARD_BODY, ["bug"])
        self.assertEqual(result["action"], "apply")
        self.assertEqual(result["add"], ["area:review-quality", "priority:P1", "type:research"])
        self.assertEqual(result["remove"], [])

    def test_edit_swaps_managed_labels_keeps_others(self) -> None:
        current = ["bug", "type:research", "area:research", "priority:P2"]
        result = sil.plan(
            "### Type\n\nFeature\n\n### Area\n\nReview Quality\n\n### Priority\n\nP1 — High\n",
            current,
        )
        self.assertEqual(result["action"], "apply")
        self.assertEqual(sorted(result["add"]), ["area:review-quality", "priority:P1", "type:feature"])
        self.assertEqual(sorted(result["remove"]), ["area:research", "priority:P2", "type:research"])

    def test_manual_issue_skips(self) -> None:
        self.assertEqual(sil.plan("plain text issue", ["bug"])["action"], "skip")

    def test_incomplete_fields_skip_without_mutation(self) -> None:
        result = sil.plan("### Type\n\nResearch\n", ["bug", "priority:P2"])
        self.assertEqual(result["action"], "skip")
        self.assertNotIn("add", result)

    def test_unknown_value_errors_without_mutation(self) -> None:
        body = "### Type\n\nChore\n\n### Area\n\nResearch\n\n### Priority\n\nP1 — High\n"
        result = sil.plan(body, ["bug"])
        self.assertEqual(result["action"], "error")
        self.assertNotIn("add", result)


class LoadCurrentLabelsTests(unittest.TestCase):
    def test_json_array(self) -> None:
        self.assertEqual(sil._load_current_labels('["bug","type:research"]'), ["bug", "type:research"])

    def test_csv_fallback(self) -> None:
        self.assertEqual(sil._load_current_labels("bug, type:research"), ["bug", "type:research"])

    def test_empty(self) -> None:
        self.assertEqual(sil._load_current_labels(""), [])


class MainOutputContractTests(unittest.TestCase):
    """The exact seam sync-issue-labels.yml consumes: main()'s exit code and the
    action/add/remove lines it writes to $GITHUB_OUTPUT."""

    _ENV_KEYS = ("ISSUE_BODY", "CURRENT_LABELS", "GITHUB_OUTPUT")

    def setUp(self) -> None:
        self._saved = {k: os.environ.get(k) for k in self._ENV_KEYS}
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(self._restore_env)

    def _restore_env(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _run(self, body: str, current_labels: str, *, with_output: bool = True):
        os.environ["ISSUE_BODY"] = body
        os.environ["CURRENT_LABELS"] = current_labels
        out_path = None
        if with_output:
            out_path = os.path.join(self._tmp.name, f"out-{id(body)}.txt")
            os.environ["GITHUB_OUTPUT"] = out_path
        else:
            os.environ.pop("GITHUB_OUTPUT", None)
        with contextlib.redirect_stdout(io.StringIO()):
            rc = sil.main([])
        outputs = None
        if out_path is not None:
            with open(out_path, encoding="utf-8") as handle:
                outputs = dict(line.rstrip("\n").split("=", 1) for line in handle if "=" in line)
        return rc, outputs

    def test_apply_contract(self) -> None:
        rc, outputs = self._run(STANDARD_BODY, '["bug"]')
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["action"], "apply")
        self.assertEqual(outputs["add"], "area:review-quality,priority:P1,type:research")
        self.assertEqual(outputs["remove"], "")

    def test_apply_contract_with_removals(self) -> None:
        rc, outputs = self._run(STANDARD_BODY, '["bug","type:feature","area:research","priority:P1"]')
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["action"], "apply")
        self.assertEqual(outputs["add"], "area:review-quality,type:research")
        self.assertEqual(outputs["remove"], "area:research,type:feature")

    def test_skip_contract(self) -> None:
        rc, outputs = self._run("Just a normal issue.\n\nNo form fields here.", '["bug"]')
        self.assertEqual(rc, 0)
        self.assertEqual(outputs["action"], "skip")
        self.assertEqual(outputs["add"], "")
        self.assertEqual(outputs["remove"], "")

    def test_error_contract_generates_no_label(self) -> None:
        body = "### Type\n\nChore\n\n### Area\n\nResearch\n\n### Priority\n\nP1 — High\n"
        rc, outputs = self._run(body, '["bug"]')
        self.assertEqual(rc, 1)
        self.assertEqual(outputs["action"], "error")
        self.assertEqual(outputs["add"], "")
        self.assertEqual(outputs["remove"], "")

    def test_runs_without_github_output(self) -> None:
        rc, outputs = self._run(STANDARD_BODY, '["bug"]', with_output=False)
        self.assertEqual(rc, 0)
        self.assertIsNone(outputs)
        rc, _ = self._run("plain issue", "[]", with_output=False)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
