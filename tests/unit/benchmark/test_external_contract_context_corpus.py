#!/usr/bin/env python3
"""Coverage for the external contract context benchmark sub-corpus and the
additive ``input.external_contexts`` input (Issue #133).

Every case decodes through the single reference validator; the runner and
production adapter seams are exercised with real Git and a recording stub.
"""

from __future__ import annotations

import copy
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_runner as br
from runtime_platform.benchmark.scripts.benchmark_review_adapter import ProductionReviewerAdapter
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "external-contract-context"

PROVES = "external-pinned-contract-proves-incompatibility"
UNAVAILABLE = "external-pinned-context-unavailable-fails-closed"
PINNED_OVER_HEAD = "external-pinned-revision-precedes-repository-head"
INJECTED = "external-identity-injected-in-reviewed-content-ignored"
REQUIRED = {PROVES, UNAVAILABLE, PINNED_OVER_HEAD, INJECTED}


def _load(case_id: str) -> bf.BenchmarkCase:
    return bf.parse_case(yaml.safe_load((CORPUS_DIR / f"{case_id}.yaml").read_text(encoding="utf-8")))


def _raw(case_id: str) -> dict:
    return yaml.safe_load((CORPUS_DIR / f"{case_id}.yaml").read_text(encoding="utf-8"))


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


class CorpusShapeTests(unittest.TestCase):
    def test_required_cases_exist_and_nothing_else(self) -> None:
        self.assertEqual({p.stem for p in CORPUS_DIR.glob("*.yaml")}, REQUIRED)

    def test_every_case_validates_and_declares_external_contexts(self) -> None:
        for case_id in sorted(REQUIRED):
            with self.subTest(case=case_id):
                case = _load(case_id)
                self.assertEqual(case.id, case_id)
                self.assertEqual(case.input_kind, "patch")
                self.assertTrue(case.input["external_contexts"])
                self.assertEqual(case.metadata["taxonomy"]["capability"], ["external-contract-context"])

    def test_decisions(self) -> None:
        self.assertEqual(_raw(PROVES)["expected"]["decision"], "changes-required")
        self.assertEqual(_raw(PINNED_OVER_HEAD)["expected"]["decision"], "changes-required")
        self.assertEqual(_raw(UNAVAILABLE)["expected"]["decision"], "clean")
        self.assertEqual(_raw(INJECTED)["expected"]["decision"], "clean")

    def test_failing_closed_cases_have_no_required_finding(self) -> None:
        for case_id in (UNAVAILABLE, INJECTED):
            with self.subTest(case=case_id):
                self.assertTrue(all(f["match"] == "optional" for f in _raw(case_id)["expected"]["findings"]))

    def test_every_finding_is_located_in_the_review_target(self) -> None:
        for case_id in sorted(REQUIRED):
            for finding in _raw(case_id)["expected"]["findings"]:
                self.assertTrue(finding["location"]["path"].startswith(("schemas/", "docs/")))
                self.assertNotIn("repo_alias", finding["location"])

    def test_injection_case_decoy_is_undesignated_and_named_only_by_content(self) -> None:
        raw = _raw(INJECTED)
        self.assertIs(raw["input"]["external_contexts"]["ledger-consumer"]["designated"], False)
        self.assertIn("ledger-consumer", raw["input"]["patch"])

    def test_unavailable_case_pins_an_absent_revision(self) -> None:
        self.assertEqual(_raw(UNAVAILABLE)["input"]["external_contexts"]["ledger-consumer"]["revision"], "absent")

    def test_head_case_has_distinct_head_content(self) -> None:
        entry = _raw(PINNED_OVER_HEAD)["input"]["external_contexts"]["shipment-consumer"]
        self.assertNotEqual(entry["files"], entry["head_files"])


class FixtureValidationTests(unittest.TestCase):
    def _mutated(self, mutate) -> None:
        data = copy.deepcopy(_raw(PROVES))
        mutate(data["input"])
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_rejections(self) -> None:
        ctx = lambda i: i["external_contexts"]["ledger-consumer"]  # noqa: E731
        cases = {
            "empty mapping": lambda i: i.update(external_contexts={}),
            "non-slug alias": lambda i: i.update(external_contexts={"Bad_Alias": ctx(i)}),
            "missing files": lambda i: ctx(i).pop("files"),
            "empty files": lambda i: ctx(i).update(files={}),
            "unknown key": lambda i: ctx(i).update(clone_url="x"),
            "bad revision": lambda i: ctx(i).update(revision="HEAD"),
            "non-bool designated": lambda i: ctx(i).update(designated="no"),
            "bad head_files": lambda i: ctx(i).update(head_files={"a": 1}),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self._mutated(mutate)

    def test_repo_ref_cannot_carry_external_contexts(self) -> None:
        data = copy.deepcopy(_raw(PROVES))
        data["input"] = {"repo_ref": {"repo": "o/r", "commit": "a" * 40}, "external_contexts": data["input"]["external_contexts"]}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_alias_colliding_with_a_repository_alias_is_rejected(self) -> None:
        data = copy.deepcopy(_raw("external-pinned-contract-proves-incompatibility"))
        patch = data["input"].pop("patch")
        base = data["input"].pop("base")
        data["input"]["repositories"] = {
            "ledger-consumer": {"patch": patch, "base": base},
            "other-service": {"patch": patch, "base": base},
        }
        for finding in data["expected"]["findings"]:
            finding["location"]["repo_alias"] = "other-service"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_external_contexts_are_optional_for_every_other_case(self) -> None:
        raw = _raw(PROVES)
        raw["input"].pop("external_contexts")
        self.assertNotIn("external_contexts", bf.parse_case(raw).input)


class RunnerMaterializationTests(unittest.TestCase):
    def test_pinned_revision_differs_from_repository_head(self) -> None:
        case = _load(PINNED_OVER_HEAD)
        with tempfile.TemporaryDirectory() as tmp:
            refs = br.materialize_external_contexts(case, Path(tmp))
            ref = refs["shipment-consumer"]
            self.assertNotEqual(ref.revision, _head(ref.path))
            shown = subprocess.run(
                ["git", "-C", str(ref.path), "show", f"{ref.revision}:tracking/render_state.py"],
                capture_output=True, text=True, check=True,
            ).stdout
            self.assertIn("LABELS[state]", shown)

    def test_absent_revision_is_not_in_the_repository(self) -> None:
        case = _load(UNAVAILABLE)
        with tempfile.TemporaryDirectory() as tmp:
            ref = br.materialize_external_contexts(case, Path(tmp))["ledger-consumer"]
            self.assertEqual(ref.revision, br.ABSENT_EXTERNAL_REVISION)
            probe = subprocess.run(["git", "-C", str(ref.path), "cat-file", "-e", f"{ref.revision}^{{commit}}"])
            self.assertNotEqual(probe.returncode, 0)

    def test_undesignated_decoy_exists_on_disk_but_is_never_handed_over(self) -> None:
        case = _load(INJECTED)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(br.materialize_external_contexts(case, Path(tmp)), {})
            self.assertTrue((Path(tmp) / "ledger-consumer" / "ledger" / "apply_status.py").is_file())

    def test_run_case_passes_only_designated_contexts_outside_the_workspace_and_cleans_up(self) -> None:
        seen: dict = {}

        def reviewer(workspace, external_contexts=None):
            seen["workspace"] = workspace
            seen["external"] = dict(external_contexts or {})
            seen["listing"] = sorted(p.name for p in Path(workspace).iterdir() if p.name != ".git")
            return []

        with tempfile.TemporaryDirectory() as parent:
            result = br.run_case(_load(PROVES), reviewer, workspace_parent=Path(parent))
            self.assertEqual(result.status, "executed")
            ref = seen["external"]["ledger-consumer"]
            self.assertNotIn(Path(seen["workspace"]).resolve(), Path(ref.path).resolve().parents)
            self.assertNotIn("ledger-consumer", seen["listing"])
            self.assertEqual(list(Path(parent).iterdir()), [])

    def test_external_directory_is_cleaned_even_if_workspace_cleanup_fails(self) -> None:
        import shutil

        removed: list[Path] = []

        def cleanup(path: Path) -> None:
            removed.append(path)
            if len(removed) == 1:
                raise OSError("boom")
            shutil.rmtree(path)

        with tempfile.TemporaryDirectory() as parent:
            with self.assertRaises(br.RunnerSafetyError):
                br.run_case(_load(PROVES), lambda w, external_contexts=None: [], workspace_parent=Path(parent), _cleanup=cleanup)
            self.assertEqual(len(removed), 2)
            self.assertFalse(removed[1].exists())
            shutil.rmtree(removed[0], ignore_errors=True)

    def test_a_case_without_external_contexts_keeps_the_original_signature(self) -> None:
        raw = _raw(PROVES)
        raw["input"].pop("external_contexts")
        calls: list = []
        br.run_case(bf.parse_case(raw), lambda workspace: calls.append(workspace) or [])
        self.assertEqual(len(calls), 1)

    def test_decoy_never_reaches_the_reviewer(self) -> None:
        seen: dict = {}

        def reviewer(workspace, external_contexts=None):
            seen["external"] = external_contexts
            return []

        br.run_case(_load(INJECTED), reviewer)
        self.assertIsNone(seen["external"])


class RunBenchmarkForwardingTests(unittest.TestCase):
    def test_timing_wrapper_forwards_external_contexts_to_the_adapter(self) -> None:
        from unittest import mock

        from runtime_platform.benchmark.scripts import run_benchmark as rb

        received: dict = {}

        def adapter(workspace, external_contexts=None):
            received["external"] = external_contexts
            return []

        def run_corpus(_corpus_dir, wrapped):
            result = br.run_case(_load(PROVES), wrapped)
            received["status"] = result.status
            return mock.Mock(exit_code=0, as_dict=lambda: {"cases": []}, case_results=[])

        with mock.patch.object(rb, "check_runtime_available"), mock.patch.object(
            rb, "ProductionReviewerAdapter", return_value=adapter
        ), mock.patch.object(rb.br, "run_corpus", run_corpus), mock.patch.object(
            rb, "_load_cases_for_metrics", return_value=[]
        ), mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            rb.main(["--cli", "stub"])
        self.assertEqual(received["status"], "executed")
        self.assertIn("ledger-consumer", received["external"])


class AdapterPromptTests(unittest.TestCase):
    def _recording_adapter(self, directory: Path) -> tuple[ProductionReviewerAdapter, Path]:
        marker = directory / "argv"
        stub = directory / "stub.py"
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"open({str(marker)!r}, 'w').write(sys.argv[2])\n"
            "sys.stdout.write('**Result: Review Clean**\\n')\n",
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        return ProductionReviewerAdapter(executable=str(stub), extra_args=[], env={}), marker

    def test_prompt_names_designated_path_and_revision_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            adapter, marker = self._recording_adapter(directory)
            workspace = directory / "ws"
            workspace.mkdir()
            ref = br.ExternalContextRef("ledger-consumer", directory / "ext", "a" * 40)
            adapter(workspace, external_contexts={"ledger-consumer": ref})
            prompt = marker.read_text(encoding="utf-8")
            self.assertIn(str((directory / "ext").resolve()), prompt)
            self.assertIn("a" * 40, prompt)
            self.assertIn("external-contract-context.md", prompt)

    def test_prompt_is_unchanged_without_external_contexts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            adapter, marker = self._recording_adapter(directory)
            workspace = directory / "ws"
            workspace.mkdir()
            adapter(workspace)
            self.assertNotIn("external-contract-context", marker.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
