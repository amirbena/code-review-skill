#!/usr/bin/env python3
"""Regression coverage for the workspace sibling measurement harness (Issue #664).

Covers the defects the first C3 run exposed: a user-installed plugin shadowing
the skill under test, no raw evidence for failed runs, "workspace root supplied"
mistaken for "capability used", absence-claim false positives, and missing token
telemetry. The review CLI is replaced by a stub executable; nothing here calls a
model.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
import textwrap
import unittest
from pathlib import Path

from runtime_platform.benchmark.reference import benchmark_workspace_sibling as bws
from runtime_platform.benchmark.scripts import benchmark_run_evidence as bre
from runtime_platform.benchmark.scripts import measure_workspace_sibling as mws
from runtime_platform.benchmark.scripts.benchmark_review_adapter import (
    SKILL_PLUGIN_DIR,
    ProductionReviewerAdapter,
    ReviewCliExitError,
    failure_category,
)

QUALIFIED = "tree-under-test:local-code-review"
REPORT = "## Code Review\n\n**Result: ✅ Review Clean**\n\n### Decision\n**REVIEW CLEAN**\n"


def init_event(*, skills=None, plugins=None) -> dict:
    return {
        "type": "system",
        "subtype": "init",
        "session_id": "s1",
        "claude_code_version": "9.9.9",
        "model": "stub-model",
        "skills": skills if skills is not None else [QUALIFIED, "code-review"],
        "plugins": plugins
        if plugins is not None
        else [
            {"name": "tree-under-test", "path": str(SKILL_PLUGIN_DIR), "source": "tree-under-test@inline"},
            {"name": "telemetry", "path": "builtin", "source": "telemetry@builtin"},
        ],
    }


def skill_call(name: str = QUALIFIED) -> dict:
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": name}}]}}


def tool_call(name: str, **tool_input) -> dict:
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": tool_input}]}}


def result_event(text: str = REPORT, *, is_error: bool = False, usage: dict | None = None) -> dict:
    return {
        "type": "result",
        "is_error": is_error,
        "result": text,
        "session_id": "s1",
        "usage": usage
        if usage is not None
        else {"input_tokens": 3, "output_tokens": 7, "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 200},
    }


def stream(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events) + "\n"


class AbsenceClassificationTests(unittest.TestCase):
    # Sentences taken from the C3 run's reviewer output: statements about the
    # reviewed repository or a named document, not about a sibling.
    SCOPED = [
        "No consumer implementation exists inside this repository to confirm whether it handles the new event type.",
        "The repository contains no consumer implementation to inspect.",
        "No consumer source is present here, and nothing in this change touches it.",
        "`docs/consumers.md` states only that it owns the schema; it names no consumers, no version policy.",
        "No consumer code, client, or test referencing this schema exists anywhere in this repository.",
        "ledger-consumer@1a2b3c4 has no other consumers of this field.",
        "Searched the full repository (`events/catalog.json`); no consumer code present to inspect.",
        "caller_consumer is unresolved (no consumer code in repository; see Context gaps).",
    ]
    # Genuinely unsupported: global or unnamed-sibling absence, or a safety conclusion.
    UNSCOPED = [
        "There are no consumers.",
        "No downstream consumers exist for this event.",
        "Nothing else depends on this schema.",
        "The sibling has no consumers of this field.",
        "No consumers exist in this repository, so it is safe to ship.",
        "It is harmless to remove because nothing else uses it.",
        "This field is unused.",
    ]

    def test_scoped_statements_are_not_claims(self) -> None:
        for sentence in self.SCOPED:
            with self.subTest(sentence=sentence):
                self.assertFalse(bws.has_absence_claim(sentence))

    def test_unscoped_statements_still_are(self) -> None:
        for sentence in self.UNSCOPED:
            with self.subTest(sentence=sentence):
                self.assertTrue(bws.has_absence_claim(sentence))

    def test_inspected_sibling_scope_needs_evidence_of_inspection(self) -> None:
        text = "No consumers were found in the ledger-consumer sibling."
        self.assertTrue(bws.has_absence_claim(text))
        self.assertTrue(bws.has_absence_claim(text, ["docs-site"]))
        self.assertFalse(bws.has_absence_claim(text, ["ledger-consumer"]))

    def test_inspected_sibling_does_not_license_a_conclusion(self) -> None:
        text = "Nothing was found in ledger-consumer, so it is safe to ship."
        self.assertTrue(bws.has_absence_claim(text, ["ledger-consumer"]))

    def test_revision_scoped_sentence_is_exempt_as_before(self) -> None:
        self.assertFalse(bws.has_absence_claim("No consumers in ledger-consumer@abcdef1."))

    def test_the_recorded_false_positives_no_longer_match(self) -> None:
        report = (
            "- Repository expansion: searched the repository; the repository contains only "
            "`docs/consumers.md` and `events/catalog.json`, so no consumer code exists to inspect."
        )
        self.assertFalse(bws.has_absence_claim(report))


class StreamAndIsolationTests(unittest.TestCase):
    def verify(self, *events: dict) -> bre.SkillIdentity:
        return bre.verify_isolation(bre.parse_stream(stream(*events)), expected_root=SKILL_PLUGIN_DIR)

    def test_identity_is_established_from_the_stream(self) -> None:
        identity = self.verify(init_event(), skill_call(), result_event())
        self.assertEqual(identity.skill, QUALIFIED)
        self.assertEqual(identity.plugin_path, str(SKILL_PLUGIN_DIR.resolve()))
        self.assertEqual(identity.claude_code_version, "9.9.9")
        self.assertIsNotNone(identity.git_head)

    def test_a_shadowing_installed_plugin_fails_closed(self) -> None:
        shadow = init_event(
            skills=[QUALIFIED, "code-review-skills:local-code-review"],
            plugins=init_event()["plugins"]
            + [{"name": "code-review-skills", "path": "/x/1.71.0", "source": "code-review-skills@code-review-skills", "version": "1.71.0"}],
        )
        with self.assertRaisesRegex(bre.IsolationError, "exactly one"):
            self.verify(shadow, skill_call(), result_event())

    def test_a_foreign_plugin_fails_closed_even_without_a_duplicate_skill(self) -> None:
        other = init_event(
            plugins=init_event()["plugins"] + [{"name": "engineering", "path": "/x", "source": "engineering@synced"}]
        )
        with self.assertRaisesRegex(bre.IsolationError, "other than the skill under test"):
            self.verify(other, skill_call(), result_event())

    def test_the_skill_must_come_from_this_checkout(self) -> None:
        elsewhere = init_event(
            plugins=[{"name": "tree-under-test", "path": "/somewhere/else", "source": "tree-under-test@inline"}]
        )
        with self.assertRaises(bre.IsolationError):
            self.verify(elsewhere, skill_call(), result_event())

    def test_no_skill_call_cannot_establish_what_ran(self) -> None:
        with self.assertRaisesRegex(bre.IsolationError, "never invoked"):
            self.verify(init_event(), result_event())

    def test_a_call_to_another_skill_fails_closed(self) -> None:
        with self.assertRaisesRegex(bre.IsolationError, "other than"):
            self.verify(init_event(), skill_call("code-review-skills:local-code-review"), result_event())

    def test_no_init_event_fails_closed(self) -> None:
        with self.assertRaisesRegex(bre.IsolationError, "no init"):
            self.verify(skill_call(), result_event())

    def test_empty_output_is_a_parse_error(self) -> None:
        with self.assertRaises(bre.StreamParseError):
            bre.parse_stream("not json\n")

    def test_usage_is_the_reported_context_not_an_estimate(self) -> None:
        totals = bre.usage_totals(result_event())
        self.assertEqual(totals["input_tokens"], 3 + 1000 + 200)
        self.assertEqual(totals["output_tokens"], 7)
        self.assertEqual(totals["fresh_input_tokens"], 3)

    def test_missing_usage_is_none_never_zero(self) -> None:
        self.assertIsNone(bre.usage_totals({"type": "result"}))
        self.assertIsNone(bre.usage_totals({"usage": {"output_tokens": 4}}))


class ActivationTests(unittest.TestCase):
    ROOT = Path("/tmp/wsib-root")

    def classify(self, *calls):
        return bre.classify_activation(calls, workspace_root=self.ROOT, sibling_names=["ledger-consumer", "docs-site"])

    def test_no_root_means_not_supplied(self) -> None:
        result = bre.classify_activation([], workspace_root=None, sibling_names=[])
        self.assertFalse(result["supplied"])

    def test_supplying_a_root_is_not_use(self) -> None:
        result = self.classify()
        self.assertTrue(result["supplied"])
        self.assertFalse(result["discovered"])
        self.assertEqual(result["siblings_inspected"], [])
        self.assertEqual(result["sibling_content_read"], {})

    def test_listing_the_root_is_discovery_only(self) -> None:
        result = self.classify(("Glob", {"pattern": "*", "path": str(self.ROOT)}))
        self.assertTrue(result["discovered"])
        self.assertEqual(result["siblings_inspected"], [])

    def test_listing_a_sibling_is_inspection_not_a_content_read(self) -> None:
        for call in (
            ("Bash", {"command": f"git -C {self.ROOT}/ledger-consumer ls-tree -r HEAD"}),
            ("Bash", {"command": f"ls {self.ROOT}/ledger-consumer"}),
            ("Glob", {"pattern": "**/*.py", "path": f"{self.ROOT}/ledger-consumer"}),
        ):
            with self.subTest(call=call):
                result = self.classify(call)
                self.assertEqual(result["siblings_inspected"], ["ledger-consumer"])
                self.assertEqual(result["sibling_content_read"], {})

    def test_reading_a_sibling_file_is_a_content_read(self) -> None:
        for call in (
            ("Read", {"file_path": f"{self.ROOT}/ledger-consumer/ledger/apply_status.py"}),
            ("Bash", {"command": f"git -C {self.ROOT}/ledger-consumer show HEAD:ledger/apply_status.py"}),
            ("Bash", {"command": f"cat {self.ROOT}/ledger-consumer/ledger/apply_status.py"}),
            ("Grep", {"pattern": "refunded", "path": f"{self.ROOT}/ledger-consumer"}),
        ):
            with self.subTest(call=call):
                result = self.classify(call)
                self.assertIn("ledger-consumer", result["sibling_content_read"])

    def test_the_private_prefix_spelling_is_the_same_path(self) -> None:
        result = bre.classify_activation(
            [("Read", {"file_path": "/private/tmp/wsib-root/docs-site/README.md"})],
            workspace_root=Path("/tmp/wsib-root"),
            sibling_names=["docs-site"],
        )
        self.assertIn("docs-site", result["sibling_content_read"])

    def test_calls_outside_the_root_are_ignored(self) -> None:
        result = self.classify(("Read", {"file_path": "/elsewhere/ledger-consumer/x.py"}))
        self.assertFalse(result["discovered"])


class StubAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.workspace = self.dir / "ws"
        self.workspace.mkdir()
        self.root = self.dir / "root"
        (self.root / "ledger-consumer").mkdir(parents=True)

    def stub(self, stdout: str, *, exit_code: int = 0, stderr: str = "") -> str:
        out, err = self.dir / "out.txt", self.dir / "err.txt"
        out.write_text(stdout, encoding="utf-8")
        err.write_text(stderr, encoding="utf-8")
        script = self.dir / "cli"
        script.write_text(
            textwrap.dedent(
                f"""\
                #!/bin/sh
                echo "$@" > "{self.dir}/argv.txt"
                cat "{out}"
                cat "{err}" 1>&2
                exit {exit_code}
                """
            )
        )
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        return str(script)

    def adapter(self, stdout: str, **kw) -> ProductionReviewerAdapter:
        return ProductionReviewerAdapter(executable=self.stub(stdout, **kw), verified_isolation=True, env=dict(os.environ), timeout=30)

    def test_isolated_invocation_flags(self) -> None:
        adapter = self.adapter(stream(init_event(), skill_call(), result_event()))
        adapter(self.workspace, workspace_root=self.root)
        argv = (self.dir / "argv.txt").read_text()
        self.assertIn("--setting-sources project,local", argv)
        self.assertIn("--output-format stream-json", argv)
        self.assertIn("--verbose", argv)
        self.assertIn(f"--add-dir {self.root.resolve()}", argv)

    def test_no_grant_means_no_extra_directory(self) -> None:
        adapter = self.adapter(stream(init_event(), skill_call(), result_event()))
        adapter(self.workspace)
        self.assertNotIn("--add-dir", (self.dir / "argv.txt").read_text())

    def test_success_keeps_identity_usage_and_activation(self) -> None:
        events = (
            init_event(),
            skill_call(),
            tool_call("Glob", pattern="*", path=str(self.root)),
            tool_call("Read", file_path=f"{self.root}/ledger-consumer/a.py"),
            result_event(),
        )
        adapter = self.adapter(stream(*events))
        adapter(self.workspace, workspace_root=self.root)
        evidence = adapter.last_evidence
        self.assertIsNone(evidence.error_category)
        self.assertEqual(evidence.exit_code, 0)
        self.assertEqual(evidence.skill["skill"], QUALIFIED)
        self.assertEqual(adapter.last_usage, {"input_tokens": 1203, "output_tokens": 7})
        self.assertTrue(evidence.activation["discovered"])
        self.assertIn("ledger-consumer", evidence.activation["sibling_content_read"])
        self.assertIn("<prompt sha256:", " ".join(evidence.argv_redacted))
        self.assertNotIn("Invoke the local-code-review", " ".join(evidence.argv_redacted))
        self.assertEqual(adapter.last_report, REPORT)

    def test_a_shadowed_run_fails_closed_and_keeps_its_evidence(self) -> None:
        shadow = init_event(skills=[QUALIFIED, "code-review-skills:local-code-review"])
        raw = stream(shadow, skill_call("code-review-skills:local-code-review"), result_event())
        adapter = self.adapter(raw, stderr="warn")
        with self.assertRaises(bre.IsolationError):
            adapter(self.workspace)
        evidence = adapter.last_evidence
        self.assertEqual(evidence.error_category, "isolation-failed")
        self.assertEqual(evidence.stdout, raw)
        self.assertEqual(evidence.stderr, "warn")
        self.assertEqual(failure_category(bre.IsolationError("x")), "isolation-failed")

    def test_a_clarifying_question_run_is_isolation_failure_not_a_review(self) -> None:
        # The first C3 run's three errors: the reviewer asked which skill to use and never called one.
        raw = stream(init_event(), result_event("Which skill do you mean?"))
        adapter = self.adapter(raw)
        with self.assertRaisesRegex(bre.IsolationError, "never invoked"):
            adapter(self.workspace)
        self.assertEqual(adapter.last_evidence.error_category, "isolation-failed")

    def test_nonzero_exit_keeps_streams_exit_code_and_category(self) -> None:
        adapter = self.adapter(stream(init_event(), skill_call()), exit_code=3, stderr="boom")
        with self.assertRaises(ReviewCliExitError):
            adapter(self.workspace)
        evidence = adapter.last_evidence
        self.assertEqual((evidence.exit_code, evidence.error_category, evidence.stderr), (3, "cli-exit-3", "boom"))
        self.assertIsNotNone(evidence.stdout)

    def test_an_error_result_is_a_runtime_error(self) -> None:
        adapter = self.adapter(stream(init_event(), skill_call(), result_event("limit", is_error=True)))
        with self.assertRaises(Exception) as caught:
            adapter(self.workspace)
        self.assertEqual(failure_category(caught.exception), "runtime-reported-error")

    def test_default_mode_is_unchanged(self) -> None:
        adapter = ProductionReviewerAdapter(executable=self.stub(REPORT), env=dict(os.environ), timeout=30)
        adapter(self.workspace, workspace_root=self.root)
        argv = (self.dir / "argv.txt").read_text()
        self.assertIn("--output-format text", argv)
        self.assertNotIn("--setting-sources", argv)
        self.assertNotIn("--add-dir", argv)
        self.assertIsNone(adapter.last_usage)
        self.assertEqual(adapter.last_evidence.isolation, "none")


class EvidenceFilesTests(unittest.TestCase):
    def test_raw_streams_and_metadata_are_written_and_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence = bre.RunEvidence(exit_code=1, error_category="cli-exit-1", stdout="out", stderr="err", argv_redacted=["x"])
            name = bre.write_run_evidence(Path(tmp), "local-case-on-1", evidence)
            meta = json.loads((Path(tmp) / name).read_text())
            self.assertEqual(meta["error_category"], "cli-exit-1")
            self.assertEqual(meta["raw_streams_retained"], ["stdout", "stderr"])
            self.assertNotIn("stdout", meta)
            self.assertEqual((Path(tmp) / "local-case-on-1.stdout").read_text(), "out")
            with self.assertRaises(FileExistsError):
                bre.write_run_evidence(Path(tmp), "local-case-on-1", evidence)

    def test_a_timeout_with_no_streams_still_leaves_a_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            evidence = bre.RunEvidence(error_category="timeout")
            name = bre.write_run_evidence(Path(tmp), "r", evidence)
            self.assertEqual(json.loads((Path(tmp) / name).read_text())["raw_streams_retained"], [])


class MeasureScriptGuardTests(unittest.TestCase):
    def args(self, **kw):
        ns = mws.build_arg_parser().parse_args([])
        for key, value in kw.items():
            setattr(ns, key, value)
        return ns

    def test_an_existing_record_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / "c3.json"
            record.write_text("{}")
            with self.assertRaises(FileExistsError):
                mws._prepare_outputs(self.args(out=str(record)))
            self.assertEqual(record.read_text(), "{}")

    def test_a_non_empty_evidence_directory_is_never_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "old.json").write_text("{}")
            with self.assertRaises(FileExistsError):
                mws._prepare_outputs(self.args(evidence_dir=tmp))

    def test_default_evidence_dir_sits_beside_the_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out, evidence = mws._prepare_outputs(self.args(out=str(Path(tmp) / "new.json")))
            self.assertEqual(evidence, Path(tmp) / "new.json.evidence")

    def test_smoke_requires_a_case(self) -> None:
        self.assertEqual(mws.main(["--smoke"]), 2)

    def test_a_measurement_refuses_a_dirty_checkout(self) -> None:
        from unittest import mock

        with mock.patch.object(mws, "tree_is_dirty", return_value=True):
            self.assertEqual(mws.main([]), 2)
        with mock.patch.object(mws, "tree_is_dirty", return_value=None):
            self.assertEqual(mws.main([]), 2)

    def test_tree_is_dirty_reads_tracked_changes_only(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            run = lambda *a: subprocess.run(["git", "-C", tmp, *a], check=True, capture_output=True)
            run("init", "-q")
            run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-qm", "x")
            self.assertFalse(mws.tree_is_dirty(Path(tmp)))
            (Path(tmp) / "untracked.txt").write_text("x")
            self.assertFalse(mws.tree_is_dirty(Path(tmp)))
            (Path(tmp) / "f.txt").write_text("a")
            run("add", "f.txt")
            self.assertTrue(mws.tree_is_dirty(Path(tmp)))
            self.assertIsNone(mws.tree_is_dirty(Path(tmp) / "missing"))

    def test_stream_failures_stop_the_run(self) -> None:
        self.assertIn("isolation-failed", mws.HARNESS_INVALID_CATEGORIES)
        self.assertIn("stream-parse-failure", mws.HARNESS_INVALID_CATEGORIES)


class ObservationRecordTests(unittest.TestCase):
    def test_provenance_is_additive(self) -> None:
        plain = bws.RunObservation("c", "on", "executed", seconds=1.0)
        self.assertNotIn("activation", plain.as_dict())
        rich = bws.RunObservation(
            "c", "on", "error", error="reviewer-adapter-raised", error_category="isolation-failed",
            evidence_file="e.json", skill={"skill": "s"}, activation={"supplied": True},
        )
        self.assertEqual(rich.as_dict()["error_category"], "isolation-failed")
        self.assertEqual(rich.as_dict()["evidence_file"], "e.json")

    def test_activation_summary_separates_supplied_from_read(self) -> None:
        runs = [
            bws.RunObservation("c", "on", "executed", activation={"supplied": True, "discovered": False, "siblings_inspected": [], "sibling_content_read": {}}),
            bws.RunObservation("c", "on", "executed", activation={"supplied": True, "discovered": True, "siblings_inspected": ["a"], "sibling_content_read": {"a": ["x"]}}),
            bws.RunObservation("c", "off", "executed"),
        ]
        summary = bws.activation_summary(runs)
        self.assertEqual(
            (summary["on_runs"], summary["root_supplied"], summary["root_discovered"], summary["sibling_inspected"], summary["sibling_content_read"]),
            (2, 2, 1, 1, 1),
        )

    def test_the_gate_is_unchanged(self) -> None:
        self.assertEqual(bws.RESOLUTION_MIN_ON_RATE, 2 / 3)
        self.assertEqual((bws.MAX_WRONG_GROWTH, bws.MAX_WALL_TIME_RATIO, bws.MAX_TOKEN_RATIO, bws.MIN_RUNS_PER_ARM), (0, 2.0, 2.0, 2))


if __name__ == "__main__":
    unittest.main()
