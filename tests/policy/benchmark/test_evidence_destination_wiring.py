"""Every evidence path resolves through the shared destination contract (#688; F8, F10, no implicit `origin`)."""

from __future__ import annotations

import re
import unittest

from runtime_platform.benchmark.scripts import benchmark_evidence_destination as ed
from runtime_platform.benchmark.scripts import benchmark_schedule_manifest as sm
from tests.support.paths import REPO_ROOT

BENCHMARK = REPO_ROOT / "runtime_platform" / "benchmark"
EXECUTION_ENTRYPOINTS = ("run_benchmark_routine.py", "run_severity_observation.py", "run_concurrency_experiment.py")
REF_LITERAL = re.compile(r"claude/[a-z][a-z0-9-]*-")


class NamespaceRegistryTests(unittest.TestCase):
    def test_every_claude_ref_prefix_in_benchmark_code_is_registered(self) -> None:
        registry = tuple(sm.load_manifest()["evidence"]["namespaces"])
        found: set[str] = set()
        for path in sorted(BENCHMARK.rglob("*")):
            if path.suffix in {".py", ".json"} and "__pycache__" not in path.parts and path.name != "benchmark_evidence_config.py":
                found |= {m for m in REF_LITERAL.findall(path.read_text(encoding="utf-8")) if m != "claude/<name>-"}
        for workflow in (REPO_ROOT / ".github" / "workflows").glob("*.y*ml"):
            found |= set(REF_LITERAL.findall(workflow.read_text(encoding="utf-8")))
        unregistered = {p for p in found if not any(p.startswith(ns) for ns in registry)}
        self.assertEqual(unregistered, set(), "add the namespace to evidence.namespaces and to the ADR's retention table")

    def test_the_registry_has_no_unused_namespace(self) -> None:
        text = "\n".join(
            p.read_text(encoding="utf-8") for p in BENCHMARK.rglob("*.py") if "__pycache__" not in p.parts and "evidence" not in p.name
        )
        for ns in sm.load_manifest()["evidence"]["namespaces"]:
            self.assertIn(ns, text, ns)


class NoImplicitOriginTests(unittest.TestCase):
    def test_no_entrypoint_defaults_a_remote_or_names_origin(self) -> None:
        for name in EXECUTION_ENTRYPOINTS:
            source = (BENCHMARK / "scripts" / name).read_text(encoding="utf-8")
            self.assertNotRegex(source, r"""["']origin["']""", name)
            self.assertIn("resolve_destination", source, name)
            self.assertIn("add_remote_argument", source, name)

    def test_the_only_origin_literal_is_the_proven_pre_cutover_checkout_remote(self) -> None:
        offenders = []
        for path in sorted((BENCHMARK / "scripts").glob("*.py")) + sorted((BENCHMARK / "publisher").glob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if re.search(r"""["']origin["']""", line) and path.name not in ("benchmark_evidence_destination.py", "validation.py"):  # validation.py: the `origin` gate name
                    offenders.append(f"{path.name}:{number}")
        self.assertEqual(offenders, [])
        self.assertEqual(ed.CHECKOUT_REMOTE, "origin")

    def test_no_remote_default_remains_on_the_history_reader(self) -> None:
        source = (BENCHMARK / "scripts" / "benchmark_baseline.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"remote: str = ")

    def test_every_producer_and_consumer_goes_through_the_destination(self) -> None:
        for name in EXECUTION_ENTRYPOINTS:
            source = (BENCHMARK / "scripts" / name).read_text(encoding="utf-8")
            self.assertNotIn("seal.seal_to_ref", source, name)  # writes go through Destination.seal
            self.assertNotIn('"ls-remote"', source, name)  # stop-condition reads go through Destination.list_refs
            self.assertNotIn("GitRefHistory(", source, name)  # baseline reads go through Destination.history

    def test_the_publisher_target_is_the_evidence_repository(self) -> None:
        source = (BENCHMARK / "publisher" / "cli.py").read_text(encoding="utf-8")
        self.assertIn('manifest["evidence"]["repository"]', source)
        self.assertIn("repository = evidence_repository(manifest)", source)


class ManifestEvidenceBlockTests(unittest.TestCase):
    def test_the_committed_block_is_pre_cutover_and_names_the_source(self) -> None:
        manifest = sm.load_manifest()
        self.assertEqual(sm.validate_manifest(manifest), [])
        self.assertEqual(manifest["evidence"]["phase"], "pre_cutover")
        self.assertEqual(manifest["evidence"]["repository"], manifest["repository"])

    def test_the_manifest_validator_rejects_the_matrix_rows_statically(self) -> None:
        def errors(**block) -> list[str]:
            manifest = sm.load_manifest()
            manifest["evidence"] = {**manifest["evidence"], **block}
            return sm.validate_manifest(manifest)

        self.assertTrue(errors(repository="amirbena/other"))  # V2
        self.assertTrue(errors(phase="private"))  # V4
        self.assertTrue(errors(phase="public"))  # V7
        self.assertEqual(errors(phase="private", repository="amirbena/code-review-skill-evidence"), [])
        manifest = sm.load_manifest()
        del manifest["evidence"]["repository"]  # V5
        self.assertTrue(sm.validate_manifest(manifest))
        self.assertTrue(errors(namespaces=["main"]))
        self.assertTrue(errors(namespaces=["claude/severity-observation-"]))  # drops the staging prefix: F2
        self.assertTrue(errors(history_branch="claude/x-"))


if __name__ == "__main__":
    unittest.main()
