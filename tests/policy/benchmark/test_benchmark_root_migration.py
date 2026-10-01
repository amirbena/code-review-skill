#!/usr/bin/env python3
"""Benchmark-root migration guard (Issue #579, parent #577)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

import yaml

from runtime_platform.benchmark.reference import benchmark_result_reference as brr
from runtime_platform.benchmark.scripts import (
    benchmark_corpus_membership as membership,
    benchmark_lane_run as lane_run,
    build_benchmark_index as build_index,
    measure_structured_result as measure,
    run_benchmark,
    select_benchmark_cases as select_cases,
)
from tests.policy.governance import test_instruction_architecture as instruction_arch
from tests.support.paths import REPO_ROOT

NEW_ROOT = REPO_ROOT / "benchmark"
OLD_TREE = "docs/benchmark"
SELF = "tests/policy/benchmark/test_benchmark_root_migration.py"

REQUIRED_FILES = (
    "README.md",
    "corpus/README.md",
    "corpus-index.json",
    "examples/example-case.yaml",
    "cloud-routine-integration.md",
    "corpus/correctness-off-by-one-pagination.yaml",
    "corpus/no-op-comment-and-rename.yaml",
    "corpus/quality-duplicated-branch-logic.yaml",
    "corpus/security-command-injection.yaml",
)
SENTINEL_FIXTURES = REQUIRED_FILES[-4:]
BYTE_IDENTICAL_PREFIXES = ("corpus/", "corpus-index.json", "examples/")
# Corpus READMEs are rewired by the move; only fixtures stay byte-identical.
BYTE_IDENTICAL_SKIP_SUFFIXES = (".md",)

# Old-tree literal followed by neither a word char nor `-`, so the sibling
# `docs/benchmark-measurement-architecture/` never matches.
OLD_LITERAL_RE = re.compile(r"docs/benchmark(?![\w-])")
OLD_JOINED_RE = re.compile(r"""["']docs["']\s*/\s*["']benchmark["']""")
LINK_RE = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_RE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)

# Frozen fixture header comments: bytes derive corpus_id / fixture_digest, so
# they keep the stale path. Exactly one occurrence each.
FROZEN_FIXTURE_HEADERS = (
    "benchmark/corpus/analogue-placement-pattern/analogue-placement-distinct-boundaries-not-consolidated.yaml",
    "benchmark/corpus/analogue-placement-pattern/analogue-placement-status-label-duplication-consolidated.yaml",
    "benchmark/corpus/analogue-placement-pattern/analogue-placement-status-label-duplication-missing-key.yaml",
    "benchmark/corpus/analogue-placement-pattern/analogue-placement-test-file-split-clean.yaml",
    "benchmark/corpus/candidate-finding-validation/cfv-disconfirmed-severe-candidate-dropped.yaml",
    "benchmark/corpus/candidate-finding-validation/cfv-disconfirming-precedent-reevaluated.yaml",
    "benchmark/corpus/candidate-finding-validation/cfv-invariant-violation-no-requirement-still-valid.yaml",
    "benchmark/corpus/candidate-finding-validation/cfv-narrowed-blast-radius-bounded-evidence.yaml",
    "benchmark/corpus/candidate-finding-validation/cfv-no-jira-toctou-still-blocking.yaml",
    "benchmark/corpus/candidate-finding-validation/cfv-requirement-ambiguity-not-invented.yaml",
    "benchmark/corpus/candidate-finding-validation/cfv-semantic-role-no-inference.yaml",
    "benchmark/corpus/candidate-finding-validation/cfv-structural-inconsistency-non-blocking.yaml",
    "benchmark/corpus/candidate-finding-validation/cfv-unproven-regression-not-asserted.yaml",
    "benchmark/corpus/candidate-finding-validation/cfv-valid-defect-severity-downgrade.yaml",
    "benchmark/corpus/candidate-finding-validation/real-world-semantic-consistency-trap-pr-390.yaml",
    "benchmark/corpus/consolidation/consolidation-rereview-reconciles-to-authoritative.yaml",
    "benchmark/corpus/consolidation/consolidation-shared-cause-low-confidence-fallback.yaml",
    "benchmark/corpus/consolidation/consolidation-shared-validator-many-call-paths.yaml",
    "benchmark/corpus/consolidation/consolidation-similar-but-independent-defects.yaml",
    "benchmark/corpus/correctness-off-by-one-pagination.yaml",
    "benchmark/corpus/decision-derivation/dd-blocking-p0-sql-injection.yaml",
    "benchmark/corpus/decision-derivation/dd-blocking-p1-inverted-error-rate.yaml",
    "benchmark/corpus/decision-derivation/dd-p2-only-mild-wording.yaml",
    "benchmark/corpus/decision-derivation/dd-p2-only-urgent-wording.yaml",
    "benchmark/corpus/decision-derivation/dd-zero-findings-clean.yaml",
    "benchmark/corpus/no-op-comment-and-rename.yaml",
    "benchmark/corpus/quality-duplicated-branch-logic.yaml",
    "benchmark/corpus/repository-intelligence/repo-intel-python-call-site-caller-null-deref.yaml",
    "benchmark/corpus/repository-intelligence/repo-intel-python-config-consumer-stale-import.yaml",
    "benchmark/corpus/repository-intelligence/repo-intel-python-control-compatible-caller-no-finding.yaml",
    "benchmark/corpus/repository-intelligence/repo-intel-python-dynamic-dispatch-safe-failure.yaml",
    "benchmark/corpus/repository-intelligence/repo-intel-typescript-interface-contract-implementer-break.yaml",
    "benchmark/corpus/security-command-injection.yaml",
)
# Named historical records that describe the old path by design.
HISTORICAL_RECORDS = {
    "docs/capability-architecture/benchmark-ownership-boundary-checkpoint.md": 21,
    "docs/capability-architecture/benchmark-root-ownership-decision.md": 5,
    "runtime_platform/benchmark/scheduled-operations/decision-record.md": 1,
}
OLD_PATH_ALLOWLIST = {
    **{p: 1 for p in FROZEN_FIXTURE_HEADERS},
    "benchmark/examples/example-case.yaml": 1,
    **HISTORICAL_RECORDS,
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout


def _tracked() -> list[str]:
    return [p for p in _git("ls-files").splitlines() if (REPO_ROOT / p).is_file()]


def _text(rel: str) -> str | None:
    try:
        return (REPO_ROOT / rel).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _link_targets(text: str) -> list[str]:
    targets = []
    for raw in LINK_RE.findall(FENCE_RE.sub("", text)):
        target = raw.split("#", 1)[0]
        if target and not re.match(r"^[a-z][a-z0-9+.-]*:", target):
            targets.append(target)
    return targets


def _resolve(rel: str, target: str) -> Path:
    base = REPO_ROOT if target.startswith("/") else (REPO_ROOT / rel).parent
    return Path(os.path.normpath(base / target.lstrip("/")))


def _under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


class PermanentLayoutTests(unittest.TestCase):
    def test_benchmark_root_has_its_required_files(self) -> None:
        missing = [f for f in REQUIRED_FILES if not (NEW_ROOT / f).is_file()]
        self.assertEqual(missing, [], f"benchmark/ is missing required files: {missing}")

    def test_old_tree_has_no_tracked_files_while_architecture_dir_remains(self) -> None:
        leftover = [p for p in _tracked() if p.startswith(OLD_TREE + "/")]
        self.assertEqual(leftover, [], f"docs/benchmark/ still has tracked files: {leftover[:5]}")
        self.assertTrue((REPO_ROOT / "docs" / "benchmark-measurement-architecture").is_dir())


class OldPathReferenceTests(unittest.TestCase):
    def test_no_unallowlisted_reference_to_the_old_tree(self) -> None:
        counts: Counter[str] = Counter()
        relative_links: list[str] = []
        for rel in _tracked():
            if rel == SELF:
                continue
            text = _text(rel)
            if text is None:
                continue
            n = len(OLD_LITERAL_RE.findall(text)) + len(OLD_JOINED_RE.findall(text))
            if n:
                counts[rel] = n
            if rel.endswith(".md"):
                for target in _link_targets(text):
                    if OLD_LITERAL_RE.search(target):
                        continue
                    if _under(_resolve(rel, target), REPO_ROOT / OLD_TREE):
                        relative_links.append(f"{rel} -> {target}")
        unexpected = {p: n for p, n in sorted(counts.items()) if OLD_PATH_ALLOWLIST.get(p) != n}
        stale = sorted(p for p in OLD_PATH_ALLOWLIST if p not in counts)
        self.assertEqual(relative_links, [], "relative links into docs/benchmark/")
        self.assertEqual(unexpected, {}, "old-tree references outside the exact allowlist")
        self.assertEqual(stale, [], "allowlist entries with no remaining old-tree reference")

    def test_measurement_architecture_name_is_not_an_old_path_reference(self) -> None:
        sibling = "docs/benchmark-measurement-architecture/model.md"
        self.assertIsNone(OLD_LITERAL_RE.search(sibling))
        self.assertIsNotNone(OLD_LITERAL_RE.search("docs/benchmark/README.md"))
        self.assertIsNotNone(OLD_LITERAL_RE.search("see docs/benchmark"))
        self.assertIsNotNone(OLD_JOINED_RE.search('REPO_ROOT / "docs" / "benchmark" / "corpus"'))
        self.assertIsNone(OLD_JOINED_RE.search('"docs" / "benchmark-measurement-architecture"'))


class ResolvedPathTests(unittest.TestCase):
    def test_path_constants_resolve_under_benchmark_root(self) -> None:
        constants = {
            "build_benchmark_index.DEFAULT_CORPUS_DIR": build_index.DEFAULT_CORPUS_DIR,
            "build_benchmark_index.DEFAULT_INDEX_PATH": build_index.DEFAULT_INDEX_PATH,
            "select_benchmark_cases.DEFAULT_INDEX_PATH": select_cases.DEFAULT_INDEX_PATH,
            "measure_structured_result.CORPUS_DIR": measure.CORPUS_DIR,
            "run_benchmark.DEFAULT_CORPUS_DIR": run_benchmark.DEFAULT_CORPUS_DIR,
            "benchmark_lane_run.ROUTINE_DOC": lane_run.ROUTINE_DOC,
            "benchmark_result_reference.DEFAULT_CORPUS_ROOT": brr.DEFAULT_CORPUS_ROOT,
        }
        outside = {k: str(v) for k, v in constants.items() if not _under(Path(v), NEW_ROOT)}
        self.assertEqual(outside, {}, "path constants not under benchmark/")

    def test_routine_prompt_block_resolves_through_prompt_template(self) -> None:
        self.assertTrue(lane_run.ROUTINE_DOC.is_file(), f"missing {lane_run.ROUTINE_DOC}")
        self.assertTrue(lane_run._prompt_template().strip())

    def test_sentinel_sees_exactly_the_four_root_fixtures(self) -> None:
        corpus = run_benchmark.DEFAULT_CORPUS_DIR
        self.assertEqual(
            sorted(corpus.glob("*.yaml")), sorted(NEW_ROOT / f for f in SENTINEL_FIXTURES)
        )

    def test_comprehensive_discovers_each_fixture_once(self) -> None:
        corpus = run_benchmark.DEFAULT_CORPUS_DIR
        fixtures = membership.discover_comprehensive_fixtures(corpus)
        paths = [fx.fixture_path for fx in fixtures]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(len({fx.case_id for fx in fixtures}), len(fixtures))
        self.assertTrue(all(_under(p, NEW_ROOT / "corpus") for p in paths))
        self.assertTrue({(NEW_ROOT / f) for f in SENTINEL_FIXTURES} <= set(paths))

    def test_capability_benchmark_paths_exist(self) -> None:
        missing = []
        for manifest in sorted((REPO_ROOT / "capabilities").glob("*/capability.yaml")):
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            raw = data.get("benchmark", "")
            entries = raw if isinstance(raw, list) else str(raw).split(",")
            for entry in (e.strip() for e in entries):
                if entry and not (REPO_ROOT / entry).exists():
                    missing.append(f"{manifest.parent.name}: {entry}")
        self.assertEqual(missing, [], "capability benchmark: paths that do not exist")

    def test_benchmark_root_is_a_user_facing_guidance_dir(self) -> None:
        self.assertIn(NEW_ROOT, instruction_arch.USER_FACING_GUIDANCE_DIRS)


class LinkResolutionTests(unittest.TestCase):
    def test_links_inside_and_into_benchmark_root_resolve(self) -> None:
        broken = []
        for rel in _tracked():
            if not rel.endswith(".md"):
                continue
            text = _text(rel)
            if text is None:
                continue
            inside = rel.startswith("benchmark/")
            for target in _link_targets(text):
                resolved = _resolve(rel, target)
                if (inside or _under(resolved, NEW_ROOT)) and not resolved.exists():
                    broken.append(f"{rel} -> {target}")
        self.assertEqual(broken, [], "unresolved links inside or into benchmark/")


@unittest.skipUnless(
    os.environ.get("BENCHMARK_MIGRATION_BASE"),
    "one-off mode: set BENCHMARK_MIGRATION_BASE=<pre-move sha>",
)
class OneOffByteIdentityTests(unittest.TestCase):
    """Not a permanent assertion: valid only around the relocation commit."""

    def test_moved_blobs_are_byte_identical_to_the_pre_move_base(self) -> None:
        base = os.environ["BENCHMARK_MIGRATION_BASE"]
        old = {}
        for line in _git("ls-tree", "-r", base, OLD_TREE).splitlines():
            meta, path = line.split("\t", 1)
            old[path[len(OLD_TREE) + 1 :]] = meta.split()[2]
        new = {}
        for line in _git("ls-files", "-s", "benchmark").splitlines():
            meta, path = line.split("\t", 1)
            new[path[len("benchmark/") :]] = meta.split()[1]
        scoped = {
            p
            for p in old
            if p.startswith(BYTE_IDENTICAL_PREFIXES) and not p.endswith(BYTE_IDENTICAL_SKIP_SUFFIXES)
        }
        self.assertTrue(scoped, f"no fixtures/index/examples under {OLD_TREE} at {base}")
        missing = sorted(p for p in scoped if p not in new)
        changed = sorted(p for p in scoped if p in new and new[p] != old[p])
        self.assertEqual(missing, [], "files not present under benchmark/")
        self.assertEqual(changed, [], "files whose blob SHA changed in the move")


def main() -> int:
    result = unittest.main(module=__name__, exit=False, verbosity=1).result
    if result.wasSuccessful():
        print("benchmark root migration: OK")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
