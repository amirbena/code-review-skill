"""Tests for the PARTIAL tier of the CI test router (#634): the derived test-impact graph,
the path -> required-surface rules, monotonicity, exhaustiveness, and the fail-upward cases."""

from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.validation import ci_test_route as router
from tests.support.paths import REPO_ROOT

ROUTER = REPO_ROOT / "scripts" / "validation" / "ci_test_route.py"
NO_DOCS_CONSUMERS = router.ConsumerIndex(frozenset(), (), 5)

TEST_BODY = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n"


def _module_path(module: str) -> str:
    return module.replace(".", "/") + ".py"


def _packages(path: str) -> dict[str, str]:
    parts = path.split("/")[:-1]
    return {"/".join(parts[:end] + ["__init__.py"]): "" for end in range(1, len(parts) + 1)}


def synthetic_tree(extra: dict[str, str] | None = None) -> dict[str, str]:
    """A small `tests/` tree that always contains every registered companion module."""
    files: dict[str, str] = {}
    registered = (*router.TREE_GUARD_MODULES, *router.DOCS_SCANNER_MODULES)
    for module in registered:
        files[_module_path(module)] = TEST_BODY
    files.update(
        {
            "tests/support/helper.py": "VALUE = 1\n",
            "tests/support/other.py": "VALUE = 2\n",
            "tests/unit/test_a.py": "from tests.support.helper import VALUE\n" + TEST_BODY,
            "tests/unit/test_b.py": "from tests.support import helper\n" + TEST_BODY,
            "tests/unit/test_c.py": "from pathlib import Path\nS = Path('tests/unit/data/sample.json')\n" + TEST_BODY,
            "tests/unit/test_d.py": "from tests.unit.test_a import T\n",
            "tests/unit/test_e.py": "from tests.support.other import VALUE\n" + TEST_BODY,
            "tests/unit/data/sample.json": "{}\n",
            "tests/integration/test_i.py": "from tests.support.helper import VALUE\n" + TEST_BODY,
            "tests/integration/test_j.py": "from tests.support.other import VALUE\n" + TEST_BODY,
            "tests/unit/test_lonely.py": TEST_BODY,
        }
    )
    files.update(extra or {})
    for path in list(files):
        for init, text in _packages(path).items():
            files.setdefault(init, text)
    return files


def graph_of(head: dict[str, str], base: dict[str, str] | None = None) -> router.ImpactGraph:
    return router.merge_scans(router.scan_tests(base if base is not None else head), router.scan_tests(head))


def modules_of(*paths: str) -> set[str]:
    return {router.module_id(p) or "" for p in paths}


COMPANIONS = set(router.TREE_GUARD_MODULES)


class ScanTests(unittest.TestCase):
    def deps(self, files: dict[str, str], rel: str) -> set[str]:
        return {d for d in router.scan_tests(files).deps[rel] if not d.endswith("__init__.py")}

    def test_import_forms_resolve_to_files(self) -> None:
        files = synthetic_tree(
            {
                "tests/unit/test_forms.py": (
                    "import tests.support.helper\n"
                    "from tests.support import other\n"
                    "from ..support import helper as h\n"
                    "from . import test_lonely\n"
                    "def late():\n    from tests.support.other import VALUE\n"
                )
            }
        )
        self.assertEqual(
            self.deps(files, "tests/unit/test_forms.py"),
            {"tests/support/helper.py", "tests/support/other.py", "tests/unit/test_lonely.py"},
        )

    def test_literal_directory_and_path_reads_resolve(self) -> None:
        files = synthetic_tree(
            {
                "tests/unit/test_reads.py": (
                    "from pathlib import Path\n"
                    "from tests.support.paths import REPO_ROOT\n"
                    "A = REPO_ROOT / 'tests' / 'support'\n"
                    "B = (REPO_ROOT / 'tests' / 'unit' / 'data' / 'sample.json').read_text()\n"
                    "C = Path(__file__).resolve().parent / 'data'\n"
                    "D = str(Path('tests', 'unit', 'test_lonely.py'))\n"
                    "E = 'see tests/unit/test_e.py for details'\n"
                    "assert REPO_ROOT.joinpath('tests', 'unit', 'test_a.py').exists()\n"
                ),
                "tests/support/paths.py": "REPO_ROOT = None\n",
            }
        )
        deps = self.deps(files, "tests/unit/test_reads.py")
        self.assertLessEqual(
            {
                "tests/support/helper.py",
                "tests/support/other.py",
                "tests/unit/data/sample.json",
                "tests/unit/test_lonely.py",
                "tests/unit/test_e.py",
                "tests/unit/test_a.py",
            },
            deps,
        )
        self.assertNotIn("tests/unit/test_b.py", deps)

    def test_docstrings_and_bare_tests_argument_are_not_reads(self) -> None:
        files = synthetic_tree(
            {"tests/unit/test_prose.py": '"""Shared by the ``tests/unit/`` modules."""\nCMD = ("pytest", "tests/")\n'}
        )
        self.assertEqual(self.deps(files, "tests/unit/test_prose.py"), set())

    def test_directory_strings_are_reads_only_as_filesystem_call_arguments(self) -> None:
        files = synthetic_tree(
            {
                "tests/unit/test_cli.py": "CMD = ('pytest', 'tests/support')\nLINK = '](../../tests/support/)'\n",
                "tests/unit/test_fs.py": "import os\nos.listdir('tests/support')\n",
            }
        )
        self.assertEqual(self.deps(files, "tests/unit/test_cli.py"), set())
        self.assertEqual(self.deps(files, "tests/unit/test_fs.py"), {"tests/support/helper.py", "tests/support/other.py"})
        files["tests/unit/test_exact.py"] = "S = 'tests/support/helper.py'\n"
        self.assertEqual(self.deps(files, "tests/unit/test_exact.py"), {"tests/support/helper.py"})

    def test_stalled_git_read_routes_full(self) -> None:
        graph_error = subprocess.TimeoutExpired("git", 1)
        with mock.patch.object(router, "build_impact_graph", side_effect=graph_error):
            self.assertIsNone(router._graph_or_none(["tests/unit/test_a.py"], REPO_ROOT, "a", "b", REPO_ROOT))

    def test_non_tests_loaders_are_resolved_and_unknown_ones_are_dynamic(self) -> None:
        safe = (
            "import sys\nfrom tests.support.paths import REPO_ROOT\n"
            "sys.path.insert(0, str(REPO_ROOT / 'scripts' / 'release'))\n"
            "p = REPO_ROOT / 'scripts' / 'security' / 'x.py'\n"
            "import importlib.util\nspec = importlib.util.spec_from_file_location('x', p)\n"
            "import importlib\nm = importlib.import_module('json')\n"
        )
        unsafe = {
            "variable path": "import sys\nsys.path.insert(0, sys.argv[1])\n",
            "computed module": "import importlib\nimportlib.import_module(NAME)\n",
            "loads from tests": "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).parent))\n",
            "f-string tests path": "import subprocess\nsubprocess.run(['ls', f'tests/{NAME}/x'])\n",
            "bare tests argument": "import os\nos.listdir('tests')\n",
        }
        files = synthetic_tree({"tests/unit/test_safe.py": safe, **{f"tests/unit/test_dyn_{i}.py": b for i, b in enumerate(unsafe.values())}})
        scan = router.scan_tests(files)
        self.assertNotIn("tests/unit/test_safe.py", scan.dynamic)
        for index, label in enumerate(unsafe):
            with self.subTest(label=label):
                self.assertIn(f"tests/unit/test_dyn_{index}.py", scan.dynamic)
                self.assertRegex(scan.dynamic[f"tests/unit/test_dyn_{index}.py"], r"^line \d+: ")

    def test_unparseable_and_unreadable_files_are_problems(self) -> None:
        scan = router.scan_tests(synthetic_tree({"tests/unit/test_bad.py": "def (:\n", "tests/unit/test_gone.py": None}))  # type: ignore[dict-item]
        self.assertEqual(len(scan.problems), 2)
        self.assertTrue(any("test_bad.py" in p and "parsed" in p for p in scan.problems))
        self.assertTrue(any("test_gone.py" in p and "read" in p for p in scan.problems))

    def test_module_ids(self) -> None:
        self.assertEqual(router.module_id("tests/unit/test_a.py"), "tests.unit.test_a")
        for bad in ("tests/unit/test-a.py", "tests/unit/data/s.json", "scripts/x.py", "tests/9x/test_a.py", "tests/x y/test_a.py"):
            with self.subTest(path=bad):
                self.assertIsNone(router.module_id(bad))
        self.assertTrue(router.is_test_module("tests/unit/test_a.py"))
        self.assertFalse(router.is_test_module("tests/support/helper.py"))
        self.assertFalse(router.is_test_module("tests/unit/__init__.py"))


class PartialRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = synthetic_tree()
        self.graph = graph_of(self.files)

    def route(self, *paths: str, graph: router.ImpactGraph | None = None, index=NO_DOCS_CONSUMERS) -> router.Route:
        return router.classify(list(paths), index, self.graph if graph is None else graph)

    def test_docs_only_is_docs(self) -> None:
        result = self.route("docs/new/x.md")
        self.assertEqual((result.tier, result.change_class, result.modules), (router.DOCS, router.PURE_DOCS, ()))

    def test_one_test_module_selects_it_importers_readers_and_companions_only(self) -> None:
        result = self.route("tests/unit/test_a.py")
        self.assertEqual((result.tier, result.change_class), (router.PARTIAL, router.PARTIAL_TESTS))
        self.assertEqual(set(result.modules), {"tests.unit.test_a", "tests.unit.test_d"} | COMPANIONS)
        self.assertEqual(list(result.modules), sorted(result.modules))
        self.assertIsNone(result.first_full_path)

    def test_literal_reader_of_a_non_python_input_is_selected(self) -> None:
        result = self.route("tests/unit/data/sample.json")
        self.assertEqual((result.tier, set(result.modules)), (router.PARTIAL, {"tests.unit.test_c"} | COMPANIONS))

    def test_non_python_input_with_no_reader_is_full(self) -> None:
        graph = graph_of(synthetic_tree({"tests/unit/data/unread.json": "{}\n"}))
        result = self.route("tests/unit/data/unread.json", graph=graph)
        self.assertEqual(result.tier, router.FULL)
        self.assertIn("no test module imports or reads it", result.reason)

    def test_shared_helper_selects_every_known_consumer_not_full(self) -> None:
        result = self.route("tests/support/helper.py")
        self.assertEqual(result.tier, router.PARTIAL)
        self.assertEqual(
            set(result.modules),
            {"tests.unit.test_a", "tests.unit.test_b", "tests.unit.test_d", "tests.integration.test_i"} | COMPANIONS,
        )

    def test_near_universal_helper_keeps_every_consumer(self) -> None:
        many = {f"tests/unit/test_many_{i}.py": "from tests.support.helper import VALUE\n" + TEST_BODY for i in range(60)}
        graph = graph_of(synthetic_tree(many))
        result = self.route("tests/support/helper.py", graph=graph)
        self.assertEqual(result.tier, router.PARTIAL)
        self.assertLessEqual({f"tests.unit.test_many_{i}" for i in range(60)}, set(result.modules))
        self.assertNotIn("tests.unit.test_lonely", result.modules)

    def test_whole_suite_closure_is_full(self) -> None:
        result = self.route("tests/__init__.py")
        self.assertEqual(result.tier, router.FULL)
        self.assertEqual(result.reason, "the affected test modules are the whole suite")

    def test_two_bounded_families_union(self) -> None:
        one, two = self.route("tests/support/helper.py"), self.route("tests/support/other.py")
        both = self.route("tests/support/helper.py", "tests/support/other.py")
        self.assertEqual(both.tier, router.PARTIAL)
        self.assertEqual(set(both.modules), set(one.modules) | set(two.modules))

    def test_production_and_shared_paths_are_full(self) -> None:
        for path in ("skills/x/SKILL.md", "shared/policies/x.md", "scripts/x.py", "runtime_platform/x.py", "CHANGELOG.md", "requirements-dev.txt"):
            with self.subTest(path=path):
                result = self.route("tests/unit/test_a.py", path)
                self.assertEqual((result.tier, result.first_full_path), (router.FULL, path))

    def test_pure_docs_with_a_test_change_adds_docs_scanners_and_link_validation(self) -> None:
        result = self.route("tests/unit/test_a.py", "docs/new/x.md")
        self.assertEqual(result.tier, router.PARTIAL)
        self.assertTrue(result.docs_links)
        self.assertLessEqual(set(router.DOCS_SCANNER_MODULES), set(result.modules))
        self.assertEqual(result.change_class, router.MIXED)

    def test_allowlisted_fast_path_with_integration_consumer_is_fast_plus_those_modules(self) -> None:
        result = self.route("README.md", "tests/support/helper.py")
        self.assertEqual(result.tier, router.FAST)
        self.assertEqual(result.modules, ("tests.integration.test_i",))
        self.assertEqual(self.route("README.md", "tests/unit/test_e.py").modules, ())

    def test_consumed_docs_with_a_test_change_is_fast(self) -> None:
        index = router.ConsumerIndex(frozenset({("new",)}), (), 5)
        result = self.route("docs/new/x.md", "tests/unit/test_lonely.py", index=index)
        self.assertEqual((result.tier, result.modules), (router.FAST, ()))

    def test_fail_upward_cases_are_full(self) -> None:
        dynamic = graph_of(synthetic_tree({"tests/unit/test_dyn.py": "from tests.support.helper import VALUE\nimport importlib\nimportlib.import_module(NAME)\n"}))
        unparseable = graph_of(synthetic_tree({"tests/unit/test_bad.py": "def (:\n"}))
        new_dir = graph_of(synthetic_tree({"tests/newkind/test_x.py": TEST_BODY}), base=synthetic_tree())
        no_companion = {p: t for p, t in synthetic_tree().items() if p != _module_path(router.TREE_GUARD_MODULES[0])}
        empty = router.merge_scans(router.scan_tests({}), router.scan_tests({}))
        cases = {
            "unknown path": (("weird/new.xyz",), self.graph),
            "unknown tests path": (("tests/unit/nonexistent.py",), self.graph),
            "new tests/ top-level dir": (("tests/newkind/test_x.py",), new_dir),
            "unparseable file": (("tests/unit/test_e.py",), unparseable),
            "dynamically loaded consumer": (("tests/support/helper.py",), dynamic),
            "missing graph": (("tests/unit/test_a.py",), None),
            "empty graph": (("tests/unit/test_a.py",), empty),
            "no consumer at all": (("tests/support/orphan.py",), graph_of(synthetic_tree({"tests/support/orphan.py": "X = 1\n"}))),
            "missing companion": (("tests/unit/test_a.py",), graph_of(no_companion)),
            "empty change set": ((), self.graph),
        }
        for label, (paths, graph) in cases.items():
            with self.subTest(label=label):
                self.assertEqual(router.classify(list(paths), NO_DOCS_CONSUMERS, graph).tier, router.FULL)

    def test_router_registries_and_workflow_are_full_even_with_a_graph(self) -> None:
        for path in (*router.ROUTER_FILES, ".github/workflows/validate.yml"):
            with self.subTest(path=path):
                self.assertEqual(self.route(path).tier, router.FULL)

    def test_a_router_test_is_a_companion_but_never_replaces_full(self) -> None:
        self.assertTrue(set(router.ROUTER_FILES[1:]) <= {_module_path(m) for m in router.TREE_GUARD_MODULES})
        result = self.route("tests/unit/test_a.py", "scripts/validation/ci_test_route.py")
        self.assertEqual(result.tier, router.FULL)

    def test_rename_or_delete_of_a_helper_includes_its_former_consumers(self) -> None:
        base = synthetic_tree()
        head = {p: t for p, t in base.items() if p != "tests/support/helper.py"}
        head["tests/support/helper2.py"] = base["tests/support/helper.py"]
        head["tests/unit/test_new.py"] = "from tests.support.helper2 import VALUE\n" + TEST_BODY
        graph = graph_of(head, base=base)
        deleted = self.route("tests/support/helper.py", "tests/support/helper2.py", "tests/unit/test_new.py", graph=graph)
        self.assertEqual(deleted.tier, router.PARTIAL)
        self.assertLessEqual(
            {"tests.unit.test_a", "tests.unit.test_b", "tests.integration.test_i", "tests.unit.test_new"}, set(deleted.modules)
        )
        self.assertNotIn("tests.support.helper", deleted.modules)
        # A consumer that still imports the deleted helper is selected from the base graph alone.
        only_delete = self.route("tests/support/helper.py", graph=graph)
        self.assertLessEqual({"tests.unit.test_a", "tests.unit.test_b"}, set(only_delete.modules))

    def test_removed_and_added_edges_are_both_covered(self) -> None:
        base = synthetic_tree({"tests/unit/test_x.py": "from tests.support.other import VALUE\n" + TEST_BODY})
        head = synthetic_tree({"tests/unit/test_x.py": "from tests.support.helper import VALUE\n" + TEST_BODY})
        graph = graph_of(head, base=base)
        for helper in ("tests/support/helper.py", "tests/support/other.py"):
            with self.subTest(helper=helper):
                self.assertIn("tests.unit.test_x", self.route(helper, graph=graph).modules)

    def test_summary_and_run_command_show_the_module_list(self) -> None:
        result = self.route("tests/unit/test_a.py", "docs/new/x.md")
        text = router.summary_markdown(result)
        self.assertIn("Tier: **PARTIAL**", text)
        self.assertIn(f"Modules ({len(result.modules)}): ", text)
        command = router.run_command(result)
        self.assertTrue(command.startswith("python3 scripts/validation/ci_test_route.py run-partial --with-docs-links --modules "))
        self.assertTrue(command.endswith(" ".join(result.modules)))
        fast = self.route("README.md", "tests/support/helper.py")
        self.assertEqual(
            router.run_command(fast), "python3 scripts/validation/ci_test_route.py run-fast --modules tests.integration.test_i"
        )
        self.assertEqual(router.run_command(self.route("README.md")), "python3 scripts/validation/ci_test_route.py run-fast")


class MonotonicityTests(unittest.TestCase):
    POOL = (
        "docs/new/x.md",
        "docs/other/y.md",
        "README.md",
        "policies/a.md",
        "skills/x/SKILL.md",
        "scripts/x.py",
        "weird/new.xyz",
        "tests/support/helper.py",
        "tests/support/other.py",
        "tests/unit/test_a.py",
        "tests/unit/test_c.py",
        "tests/unit/test_e.py",
        "tests/unit/test_lonely.py",
        "tests/unit/data/sample.json",
        "tests/integration/test_i.py",
        "tests/__init__.py",
        "tests/unit/nonexistent.py",
    )

    @staticmethod
    def covers(big: router.Route, small: router.Route) -> bool:
        rank = router.TIER_ORDER.index
        if rank(big.tier) < rank(small.tier):
            return False
        if big.tier == router.FULL:
            return True
        if big.tier == small.tier:
            return set(big.modules) >= set(small.modules)
        if big.tier == router.FAST and small.tier == router.PARTIAL:
            # FAST already runs every non-integration module; it must also carry the integration ones.
            return {m for m in small.modules if m.startswith(router.INTEGRATION_PREFIX)} <= set(big.modules)
        return True

    def assert_monotone(self, graph: router.ImpactGraph, pool: tuple[str, ...], seed: int, rounds: int) -> None:
        rng = random.Random(seed)
        for _ in range(rounds):
            a = rng.sample(pool, rng.randint(1, 4))
            b = rng.sample(pool, rng.randint(1, 4))
            union = sorted(set(a) | set(b))
            ra, rb = router.classify(a, NO_DOCS_CONSUMERS, graph), router.classify(b, NO_DOCS_CONSUMERS, graph)
            rab = router.classify(union, NO_DOCS_CONSUMERS, graph)
            for small in (ra, rb):
                self.assertTrue(self.covers(rab, small), (a, b, rab, small))
            self.assertEqual(rab, router.classify(list(reversed(union)), NO_DOCS_CONSUMERS, graph) if rab.first_full_path is None else rab)

    def test_union_never_lowers_the_tier_or_drops_a_module_synthetic(self) -> None:
        self.assert_monotone(graph_of(synthetic_tree()), self.POOL, 634, 400)

    def test_union_never_lowers_the_tier_or_drops_a_module_on_the_real_tree(self) -> None:
        head = router.scan_tests(router.read_tests_from_tree(REPO_ROOT))
        graph = router.merge_scans(head, head)
        tracked = sorted(p for p in graph.head_files if p.endswith(".py"))
        pool = (*self.POOL[:7], *random.Random(1).sample(tracked, 25), "tests/support/paths.py", "tests/__init__.py")
        index = router.ConsumerIndex(frozenset(), (), 5)
        rng = random.Random(634)
        for _ in range(60):
            a, b = rng.sample(pool, 2), rng.sample(pool, 3)
            rab = router.classify(sorted({*a, *b}), index, graph)
            for small in (router.classify(a, index, graph), router.classify(b, index, graph)):
                self.assertTrue(self.covers(rab, small), (a, b))


class ExhaustivenessTests(unittest.TestCase):
    def test_every_tracked_path_classifies_deterministically(self) -> None:
        head = router.scan_tests(router.read_tests_from_tree(REPO_ROOT))
        graph = router.merge_scans(head, head)
        index = router.consumer_index(REPO_ROOT)
        tracked = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "-z"], capture_output=True, check=True
        ).stdout.decode("utf-8", "surrogateescape").split("\0")
        paths = [p for p in tracked if p]
        self.assertGreater(len(paths), 500)
        for path in paths:
            first = router.classify([path], index, graph)
            self.assertIn(first.tier, router.TIER_ORDER, path)
            self.assertEqual(first, router.classify([path], index, graph), path)
            if first.tier == router.PARTIAL:
                self.assertTrue(path.startswith("tests/") or first.docs_links, path)
                self.assertTrue(first.modules, path)

    def test_a_synthetic_path_with_no_rule_is_full(self) -> None:
        graph = graph_of(synthetic_tree())
        for path in ("unclassified/new.dat", "Tests/unit/test_a.py", "tests", "tests/../scripts/x.py", "tests//unit/test_a.py", ".hidden"):
            with self.subTest(path=path):
                self.assertEqual(router.classify([path], NO_DOCS_CONSUMERS, graph).tier, router.FULL)


class UnderReportingGuardTests(unittest.TestCase):
    """The static graph must be a superset of what the test modules actually import and read."""

    def test_graph_covers_the_imports_test_modules_actually_perform(self) -> None:
        script = r"""
import builtins, json, sys, unittest
edges = set()
real = builtins.__import__
def hook(name, globals=None, locals=None, fromlist=(), level=0):
    importer = (globals or {}).get("__name__", "")
    if importer.startswith("tests"):
        if level:
            package = (globals or {}).get("__package__") or ""
            base = package.rsplit(".", level - 1)[0] if level > 1 else package
            target = f"{base}.{name}" if name else base
        else:
            target = name
        if target.startswith("tests"):
            edges.add((importer, target))
            for item in fromlist or ():
                edges.add((importer, f"{target}.{item}"))
    return real(name, globals, locals, fromlist, level)
builtins.__import__ = hook
unittest.defaultTestLoader.discover("tests", top_level_dir=".")
print(json.dumps(sorted(edges)))
"""
        done = subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, check=True)
        runtime = json.loads(done.stdout.strip().splitlines()[-1])
        head = router.scan_tests(router.read_tests_from_tree(REPO_ROOT))
        self.assertGreater(len(runtime), 300)
        missing = []
        for importer, target in runtime:
            source = router._file_for_module(importer, head.files)
            wanted = router._file_for_module(target, head.files)
            if source is None or wanted is None or source == wanted:
                continue
            if wanted not in head.deps.get(source, ()):
                missing.append(f"{source} -> {wanted}")
        self.assertEqual(missing, [], "the static graph under-reports these imports")

    def test_real_tree_has_no_unresolved_access_forms_or_scan_problems(self) -> None:
        head = router.scan_tests(router.read_tests_from_tree(REPO_ROOT))
        self.assertEqual(head.problems, ())
        self.assertEqual(
            dict(head.dynamic), {}, "an unrecognized tests/ access form was added; teach the scan or register it"
        )

    def test_a_new_unrecognized_access_form_fails_with_file_and_line(self) -> None:
        files = synthetic_tree({"tests/unit/test_new_form.py": "import os\n\nroot = '.'\nos.listdir(f'tests/{root}/x')\n"})
        scan = router.scan_tests(files)
        self.assertEqual(scan.dynamic, {"tests/unit/test_new_form.py": scan.dynamic["tests/unit/test_new_form.py"]})
        self.assertTrue(scan.dynamic["tests/unit/test_new_form.py"].startswith("line 4: "))
        result = router.classify(["tests/unit/test_new_form.py"], NO_DOCS_CONSUMERS, graph_of(files))
        self.assertEqual(result.tier, router.FULL)
        self.assertIn("test_new_form.py, line 4", result.reason)

    def test_helper_fan_out_matches_an_independent_closure(self) -> None:
        head = router.scan_tests(router.read_tests_from_tree(REPO_ROOT))
        graph = router.merge_scans(head, head)
        seeds = {"tests/support/paths.py"}
        seen = set(seeds)
        changed = True
        while changed:  # brute-force fixed point, independent of the BFS used by the router
            changed = False
            for consumer, deps in graph.deps.items():
                if consumer not in seen and seen & deps:
                    seen.add(consumer)
                    changed = True
        expected = {router.module_id(f) for f in seen if router.is_test_module(f)}
        modules, _ = router.surface_of_test_path("tests/support/paths.py", graph)
        self.assertEqual(modules, expected)
        self.assertGreater(len(expected), 100)


class GitSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        for rel, text in synthetic_tree().items():
            self.write(rel, text)
        self.write("README.md", "r\n")
        self.base = self.commit("base")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=True).stdout.strip()

    def write(self, rel: str, text: str) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def route(self, head: str) -> router.Route:
        return router.safe_route("pull_request", self.repo, self.base, head, self.repo)

    def test_rev_and_tree_sources_agree(self) -> None:
        self.assertEqual(router.read_tests_from_rev(self.repo, self.base), router.read_tests_from_tree(self.repo))

    def test_test_only_change_routes_partial_end_to_end(self) -> None:
        self.write("tests/support/helper.py", "VALUE = 3\n")
        result = self.route(self.commit("edit helper"))
        self.assertEqual(result.tier, router.PARTIAL)
        self.assertLessEqual({"tests.unit.test_a", "tests.integration.test_i"}, set(result.modules))

    def test_deleted_helper_selects_its_former_consumers_from_the_base_commit(self) -> None:
        self.git("rm", "-q", "tests/support/helper.py")
        self.git("rm", "-q", "tests/unit/test_a.py")
        result = self.route(self.commit("delete"))
        self.assertEqual(result.tier, router.PARTIAL)
        self.assertLessEqual({"tests.unit.test_b", "tests.unit.test_d", "tests.integration.test_i"}, set(result.modules))
        self.assertNotIn("tests.unit.test_a", result.modules)

    def test_unreadable_base_fails_upward(self) -> None:
        self.write("tests/support/helper.py", "VALUE = 3\n")
        head = self.commit("edit helper")
        with mock.patch.object(router, "read_tests_from_rev", side_effect=subprocess.CalledProcessError(1, "git")):
            self.assertEqual(self.route(head).tier, router.FULL)

    def test_graph_is_built_only_when_a_test_path_changed(self) -> None:
        self.write("README.md", "changed\n")
        head = self.commit("readme")
        with mock.patch.object(router, "build_impact_graph", side_effect=AssertionError("must not build")):
            self.assertEqual(self.route(head).tier, router.FAST)

    def test_route_and_classify_print_the_same_summary(self) -> None:
        self.write("tests/unit/test_e.py", TEST_BODY + "\n")
        head = self.commit("edit test")
        result = self.route(head)
        with tempfile.TemporaryDirectory() as tmp:
            out, summary = Path(tmp) / "out", Path(tmp) / "summary"
            captured = _capture(
                lambda: router.main(
                    ["route", "--event-name", "pull_request", "--base", self.base, "--head", head, "--repo", str(self.repo),
                     "--tree", str(self.repo), "--github-output", str(out), "--step-summary", str(summary)]
                )
            )
            outputs = out.read_text(encoding="utf-8")
        classified = _capture(lambda: router.main(["classify", "--base", self.base, "--head", head, "--repo", str(self.repo)]))
        self.assertEqual(result.tier, router.PARTIAL)
        self.assertTrue(classified.startswith(captured))
        self.assertIn(f"- Modules ({len(result.modules)}): {' '.join(result.modules)}", captured)
        self.assertIn("tier=partial\nclass=PARTIAL_TESTS\nmodules=", outputs)
        self.assertIn(f"- Run: `{router.run_command(result)}`", classified)


def _capture(call) -> str:
    from contextlib import redirect_stdout
    from io import StringIO

    buffer = StringIO()
    with redirect_stdout(buffer):
        call()
    return buffer.getvalue()


class RunPartialTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for package in ("tests", "tests/unit"):
            (self.root / package).mkdir(parents=True, exist_ok=True)
            (self.root / package / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests/unit/test_ok.py").write_text(TEST_BODY, encoding="utf-8")
        (self.root / "tests/unit/test_fail.py").write_text(TEST_BODY.replace("pass", "self.fail('x')"), encoding="utf-8")
        (self.root / "tests/unit/test_none.py").write_text("import unittest\n", encoding="utf-8")

    def run_partial(self, *modules: str, extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROUTER), "run-partial", *extra, "--repo", str(self.root), "--modules", *modules],
            cwd=self.root, capture_output=True, text=True,
        )

    def test_runs_exactly_the_named_modules(self) -> None:
        listed = self.run_partial("tests.unit.test_ok", extra=("--list",))
        self.assertEqual((listed.returncode, listed.stdout.split()), (0, ["tests.unit.test_ok"]))
        self.assertEqual(self.run_partial("tests.unit.test_ok").returncode, 0)
        self.assertEqual(self.run_partial("tests.unit.test_fail").returncode, 1)

    def test_zero_tests_unresolvable_and_malformed_ids_fail(self) -> None:
        self.assertEqual(self.run_partial("tests.unit.test_none").returncode, 1)
        self.assertEqual(self.run_partial("tests.unit.test_missing").returncode, 1)
        for bad in ("tests", "scripts.x", "tests.unit.test_ok; rm -rf x", "../tests.unit.test_ok", "tests.unit.-x"):
            with self.subTest(module=bad):
                done = self.run_partial(bad)
                self.assertEqual(done.returncode, 1)
                self.assertIn("run-partial:", done.stderr)

    def test_validate_module_ids(self) -> None:
        self.assertIsNone(router.validate_module_ids(["tests.unit.test_ok"]))
        self.assertIsNotNone(router.validate_module_ids([]))
        self.assertIsNotNone(router.validate_module_ids(["tests.unit.test_ok", "bad id"]))

    def test_fast_with_extra_modules_adds_them_to_the_fast_set(self) -> None:
        (self.root / "tests/integration").mkdir()
        (self.root / "tests/integration/__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests/integration/test_int.py").write_text(TEST_BODY, encoding="utf-8")

        def listed(*extra: str) -> list[str]:
            done = subprocess.run(
                [sys.executable, str(ROUTER), "run-fast", "--list", *extra], cwd=self.root, capture_output=True, text=True
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            return done.stdout.split()

        self.assertNotIn("tests.integration.test_int.T.test_a", listed())
        self.assertIn("tests.integration.test_int.T.test_a", listed("--modules", "tests.integration.test_int"))
        bad = subprocess.run(
            [sys.executable, str(ROUTER), "run-fast", "--modules", "bad id"], cwd=self.root, capture_output=True, text=True
        )
        self.assertEqual(bad.returncode, 1)


class InvariantTests(unittest.TestCase):
    SOURCE = ROUTER.read_text(encoding="utf-8")

    def test_selection_never_runs_live_work_or_touches_the_network(self) -> None:
        imports = set(re.findall(r"^(?:import|from) ([A-Za-z_][\w.]*)", self.SOURCE, re.MULTILINE))
        self.assertEqual(
            imports,
            {"__future__", "argparse", "ast", "importlib.util", "os", "re", "subprocess", "sys", "unittest", "collections", "dataclasses", "pathlib", "typing"},
        )
        invocations = re.findall(r"subprocess\.run\(\s*(\[[^\]]*\])", self.SOURCE)
        for argv in invocations:
            self.assertTrue(argv.startswith('["git"') or "sys.executable" in argv, argv)
        for gate in ("BENCHMARK_REQUIRE_RUNTIME", "DISTRIBUTION_INSTALL_CHECK", "BENCHMARK_MIGRATION_BASE"):
            self.assertNotIn(gate, self.SOURCE)

    def test_no_label_flag_or_environment_input_selects_a_tier(self) -> None:
        self.assertEqual(sorted(set(re.findall(r"os\.environ(?:\.get)?\(?\[?[\"'](\w+)", self.SOURCE))), ["GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY"])
        self.assertEqual(
            sorted(a for a in re.findall(r'add_argument\("(--[\w-]+)"', self.SOURCE) if "tier" in a or "label" in a or "force" in a), []
        )
        paths = ["tests/unit/test_a.py"]
        graph = graph_of(synthetic_tree())
        baseline = router.classify(paths, NO_DOCS_CONSUMERS, graph)
        hostile = {"TIER": "docs", "ROUTE_TIER": "fast", "FORCE_TIER": "docs", "LABELS": "skip-ci", "GITHUB_OUTPUT": ""}
        with mock.patch.dict(os.environ, hostile):
            self.assertEqual(router.classify(paths, NO_DOCS_CONSUMERS, graph), baseline)

    def test_tier_order_places_partial_between_docs_and_fast(self) -> None:
        self.assertEqual(router.TIER_ORDER, (router.DOCS, router.PARTIAL, router.FAST, router.FULL))


if __name__ == "__main__":
    unittest.main()
