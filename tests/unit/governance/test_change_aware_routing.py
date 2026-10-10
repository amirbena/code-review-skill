"""Tests for change-aware DOCS/FAST/FULL classification (#624)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from scripts.validation import ci_test_route as router
from tests.support.paths import REPO_ROOT

ROUTER = REPO_ROOT / "scripts" / "validation" / "ci_test_route.py"
ISSUE_623 = ("docs/rendered-inspection/README.md", "docs/rendered-inspection/rendered-inspection-contract.md")

CONSUMERS = {
    "tests/test_literal.py": 'P = REPO_ROOT / "docs/literal/a.md"\n',
    "tests/test_joined.py": 'P = REPO_ROOT / "docs" / "joined" / "b.md"\n',
    "tests/test_multiline.py": 'P = (\n    REPO_ROOT\n    / "docs"\n    / "multi"\n    / "c.md"\n)\n',
    "tests/test_directory.py": 'D = REPO_ROOT / "docs" / "whole"\ntext = (D / name).read_text()\n',
    "scripts/tool.py": 'CATALOG = "docs/data/catalog"\n',
    "tests/test_dynamic.py": 'name = "x"\nP = f"docs/dyn/{name}.md"\n',
    "tests/test_noise.py": 'assert "docs/" not in text\n',
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


class FixtureRepo(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        _git(self.repo, "init", "-q", "-b", "main")
        _git(self.repo, "config", "user.email", "t@example.com")
        _git(self.repo, "config", "user.name", "t")
        for rel, text in CONSUMERS.items():
            self.write(rel, text)
        for rel in ("docs/pure/x.md", "docs/literal/a.md", "docs/literal/other.md", "docs/dyn/y.md", "docs/data/catalog/c.yaml"):
            self.write(rel, "d\n")
        self.base = self.commit("base")

    def write(self, rel: str, text: str) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> str:
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "--allow-empty", "-m", message)
        return _git(self.repo, "rev-parse", "HEAD")

    def index(self) -> router.ConsumerIndex:
        return router.consumer_index(self.repo)


class ConsumerIndexTests(FixtureRepo):
    def test_pure_docs_have_no_consumer_and_need_no_list_edit(self) -> None:
        index = self.index()
        for path in ("docs/pure/x.md", "docs/brand-new/y.md", "docs/literal/other.md"):
            with self.subTest(path=path):
                self.assertEqual(router.classify([path], index).change_class, router.PURE_DOCS)

    def test_every_reference_form_makes_a_doc_consumed(self) -> None:
        index = self.index()
        for path in (
            "docs/literal/a.md",
            "docs/joined/b.md",
            "docs/multi/c.md",
            "docs/whole/anything.md",
            "docs/whole/deep/er.md",
            "docs/data/catalog/new.md",
            "docs/dyn/y.md",
        ):
            with self.subTest(path=path):
                result = router.classify([path], index)
                self.assertEqual((result.tier, result.change_class), (router.FAST, router.CONSUMED_DOCS))

    def test_adding_a_consumer_reclassifies_the_doc(self) -> None:
        self.assertEqual(router.classify(["docs/pure/x.md"], self.index()).tier, router.DOCS)
        self.write("tests/test_new.py", 'P = REPO_ROOT / "docs" / "pure" / "x.md"\n')
        self.commit("add consumer")
        self.assertEqual(router.classify(["docs/pure/x.md"], self.index()).tier, router.FAST)

    def test_bare_docs_mention_without_enumeration_is_not_a_consumer(self) -> None:
        self.assertEqual(router.classify(["docs/pure/x.md"], self.index()).tier, router.DOCS)

    def test_unregistered_tree_reader_makes_every_doc_unverified(self) -> None:
        self.write("tests/test_walk.py", 'for p in (ROOT / "docs").rglob("*"):\n    pass\n')
        self.commit("tree reader")
        index = self.index()
        self.assertEqual(index.wildcard_files, ("tests/test_walk.py",))
        result = router.classify(["docs/pure/x.md"], index)
        self.assertEqual(result.tier, router.FULL)
        self.assertIn("tests/test_walk.py", result.reason)
        self.assertEqual(router.classify(["README.md"], index).tier, router.FAST)

    def test_router_files_are_not_consumers(self) -> None:
        self.write(router.ROUTER_FILES[1], 'P = "docs/pure/x.md"\n')
        self.commit("router fixture")
        self.assertEqual(router.classify(["docs/pure/x.md"], self.index()).tier, router.DOCS)

    def test_unresolvable_docs_access_forms_are_never_pure(self) -> None:
        forms = {
            "variable component": 'P = REPO_ROOT / "docs" / slug / "README.md"\n',
            "dynamic first component": 'P = REPO_ROOT / f"docs/{area}/README.md"\n',
            "variable root": 'DOCS = REPO_ROOT / "docs"\ntext = (DOCS / "pure" / "x.md").read_text()\n',
            "Path root": 'DOCS = Path("docs")\n',
            "os.path.join": 'p = os.path.join(REPO_ROOT, "docs", name)\n',
            "Path with root arg": 'p = Path(REPO_ROOT, "docs", name)\n',
            "walk": 'for _r, _d, fs in (REPO_ROOT / "docs").walk():\n    pass\n',
            "copytree": 'shutil.copytree(REPO_ROOT / "docs", tmp)\n',
            "name constant": 'DOCS_DIRNAME = "docs"\n',
            "glob pattern": 'list(ROOT.glob("docs/*/x.md"))\n',
        }
        for name, code in forms.items():
            with self.subTest(form=name):
                self.write("tests/test_form.py", code)
                self.commit(name)
                index = self.index()
                self.assertEqual(index.wildcard_files, ("tests/test_form.py",))
                self.assertEqual(router.classify(["docs/pure/x.md"], index).tier, router.FULL)

    def test_resolved_forms_stay_precise(self) -> None:
        self.write("tests/test_ok.py", 'a = os.path.join(ROOT, "docs", "literal", "a.md")\nb = x == "docs"\n')
        self.commit("resolved")
        index = self.index()
        self.assertEqual(index.wildcard_files, ())
        self.assertEqual(router.classify(["docs/pure/x.md"], index).tier, router.DOCS)

    def test_repo_wide_tree_scanners_without_a_docs_token_are_caught(self) -> None:
        scanners = {
            "rglob": 'for md in REPO_ROOT.rglob("*.md"):\n    pass\n',
            "markdown rglob on any root": 'for md in root.rglob("*.md"):\n    pass\n',
            "ls-files": 'out = run(["git", "ls-files"])\n',
            "tracked helper": "files = tracked_markdown_files(root)\n",
            "glob double star": 'list(base.glob("**/*.md"))\n',
            "git grep": 'out = subprocess.run(["git", "grep", "-n", "TODO"])\n',
            "git ls-tree": 'out = run(["git", "ls-tree", "-r", "HEAD"])\n',
            "lowercase root rglob": 'for p in repo_root.rglob("*"):\n    pass\n',
            "parents rglob": 'for p in Path(__file__).parents[2].rglob("*"):\n    pass\n',
            "os.walk": "for d, _, fs in os.walk(root):\n    pass\n",
            "recursive glob.glob": 'glob.glob(str(root / "**" / "*.md"), recursive=True)\n',
            "Path.walk": "for r_, d, f in repo.walk():\n    pass\n",
            "variable glob pattern": "list(base.glob(pattern))\n",
            "iterdir": "for d in ROOT.iterdir():\n    pass\n",
        }
        for name, code in scanners.items():
            with self.subTest(scanner=name):
                self.write("tests/test_scan.py", code)
                self.commit(name)
                index = self.index()
                self.assertEqual(index.wildcard_files, ("tests/test_scan.py",))
                self.assertEqual(router.classify(["docs/pure/x.md"], index).tier, router.FULL)

    def test_enumerations_that_cannot_reach_markdown_are_not_scanners(self) -> None:
        self.write("tests/test_safe.py", 'list(CORPUS.glob("*.yaml"))\nfor n in ast.walk(tree):\n    pass\n')
        self.commit("safe enumerations")
        self.assertEqual(self.index().wildcard_files, ())

    def test_reviewed_enumerators_and_registered_scanners_are_tolerated(self) -> None:
        reviewed = sorted(router.REVIEWED_NON_DOCS_ENUMERATORS)[0]
        scanner = router._module_path(router.DOCS_SCANNER_MODULES[0])
        self.write(reviewed, 'for md in REPO_ROOT.rglob("*.md"):\n    pass\n')
        self.write(scanner, 'for md in REPO_ROOT.rglob("*.md"):\n    pass\nP = REPO_ROOT / "docs"\n')
        self.commit("tolerated")
        self.assertEqual(self.index().wildcard_files, ())

    def test_a_reviewed_enumerator_that_reads_docs_unresolvably_is_still_flagged(self) -> None:
        reviewed = sorted(router.REVIEWED_NON_DOCS_ENUMERATORS)[0]
        self.write(reviewed, 'P = REPO_ROOT / "docs" / slug\n')
        self.commit("reviewed file reads docs")
        self.assertEqual(self.index().wildcard_files, (reviewed,))

    def test_an_unreadable_consumer_file_makes_docs_unverified(self) -> None:
        (self.repo / "tests/test_literal.py").unlink()
        index = self.index()
        self.assertEqual(index.unreadable, ("tests/test_literal.py",))
        result = router.classify(["docs/pure/x.md"], index)
        self.assertEqual(result.tier, router.FULL)
        self.assertIn("could not be read", result.reason)

    def test_markdown_files_are_not_consumers(self) -> None:
        self.write("tests/notes.md", "see docs/pure/x.md\n")
        self.commit("notes")
        self.assertEqual(router.classify(["docs/pure/x.md"], self.index()).tier, router.DOCS)


class ClassifyTests(FixtureRepo):
    def test_pure_docs_never_select_a_suite(self) -> None:
        result = router.classify(["docs/pure/x.md", "docs/pure/y.md"], self.index())
        self.assertEqual((result.tier, result.change_class, result.first_full_path), (router.DOCS, router.PURE_DOCS, None))

    def test_mixed_changes_follow_the_non_doc_paths(self) -> None:
        index = self.index()
        cases = (
            (["docs/pure/x.md", "README.md"], router.FAST, router.MIXED),
            (["docs/pure/x.md", "docs/literal/a.md", "README.md"], router.FAST, router.MIXED),
            (["docs/pure/x.md", "skills/s/SKILL.md"], router.FULL, router.MIXED),
            (["docs/literal/a.md", "scripts/packaging/x.sh"], router.FULL, router.MIXED),
            (["docs/pure/x.md", "tests/unit/test_x.py"], router.FULL, router.MIXED),
        )
        for paths, tier, change_class in cases:
            with self.subTest(paths=paths):
                result = router.classify(paths, index)
                self.assertEqual((result.tier, result.change_class), (tier, change_class))

    def test_the_forcing_path_is_the_first_non_doc_full_path(self) -> None:
        result = router.classify(["docs/pure/x.md", "shared/a.md", "skills/b.md"], self.index())
        self.assertEqual(result.first_full_path, "shared/a.md")

    def test_docs_never_lower_a_tier(self) -> None:
        index = self.index()
        for other in ("shared/a.md", "CHANGELOG.md", ".github/workflows/validate.yml", "requirements-dev.txt"):
            with self.subTest(other=other):
                self.assertEqual(router.classify(["docs/pure/x.md", other], index).tier, router.FULL)

    def test_unknown_and_unnormalized_paths_are_never_pure(self) -> None:
        index = self.index()
        for path in (
            "Docs/pure/x.md",
            "./docs/pure/x.md",
            "docs/pure/x.MD",
            "docs/pure/x.markdown",
            "docs/pure/../../scripts/x.md",
            "docs//pure/x.md",
            "docs\\pure\\x.md",
            "docs/pure/",
            "docs/data/catalog/c.yaml",
            "docs.md",
            "/docs/pure/x.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(router.classify([path], index).tier, router.FULL)

    def test_empty_change_set_is_full(self) -> None:
        self.assertEqual(router.classify([], self.index()).tier, router.FULL)

    def test_a_missing_or_empty_consumer_scan_fails_safe(self) -> None:
        self.assertEqual(router.classify(["docs/pure/x.md"], None).tier, router.FULL)
        empty = router.ConsumerIndex(frozenset(), (), 0)
        result = router.classify(["docs/pure/x.md"], empty)
        self.assertEqual(result.tier, router.FULL)
        self.assertEqual(router.classify(["README.md"], None).tier, router.FAST)


class RouteTests(FixtureRepo):
    def route(self, head: str, tree: Path | None) -> router.Route:
        return router.safe_route("pull_request", self.repo, self.base, head, tree)

    def test_pure_docs_pull_request_routes_docs(self) -> None:
        self.write("docs/pure/x.md", "changed\n")
        result = self.route(self.commit("docs"), self.repo)
        self.assertEqual((result.tier, result.change_class), (router.DOCS, router.PURE_DOCS))

    def test_consumed_docs_pull_request_routes_fast(self) -> None:
        self.write("docs/literal/a.md", "changed\n")
        result = self.route(self.commit("docs"), self.repo)
        self.assertEqual((result.tier, result.change_class), (router.FAST, router.CONSUMED_DOCS))

    def test_missing_tree_unreadable_tree_and_renames_are_full(self) -> None:
        self.write("docs/pure/x.md", "changed\n")
        head = self.commit("docs")
        self.assertEqual(self.route(head, None).tier, router.FULL)
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(self.route(head, Path(empty)).tier, router.FULL)
        _git(self.repo, "checkout", "-q", "--detach", self.base)
        _git(self.repo, "mv", "docs/pure/x.md", "scripts/x.md")
        self.assertEqual(self.route(self.commit("rename out of docs"), self.repo).tier, router.FULL)

    def test_other_events_never_route_docs(self) -> None:
        self.write("docs/pure/x.md", "changed\n")
        head = self.commit("docs")
        for event in ("push", "workflow_dispatch", ""):
            with self.subTest(event=event):
                self.assertEqual(router.safe_route(event, self.repo, self.base, head, self.repo).tier, router.FULL)


class RealRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = router.consumer_index(REPO_ROOT)

    def test_issue_623_paths_are_pure_documentation(self) -> None:
        result = router.classify(list(ISSUE_623), self.index)
        self.assertEqual((result.tier, result.change_class), (router.DOCS, router.PURE_DOCS))

    def test_consumed_docs_are_not_treated_as_pure(self) -> None:
        for path in ("docs/features/rendered-inspection.md", "docs/ARCHITECTURE.md", "docs/RELEASE.md", "docs/findings/README.md"):
            with self.subTest(path=path):
                self.assertEqual(router.classify([path], self.index).change_class, router.CONSUMED_DOCS)

    def test_no_unregistered_docs_reader_or_tree_enumerator_exists(self) -> None:
        # Register a content-agnostic scanner in DOCS_SCANNER_MODULES, list a reviewed non-docs
        # enumerator in REVIEWED_NON_DOCS_ENUMERATORS, or stop reading docs/ in an unresolvable way.
        self.assertEqual(self.index.wildcard_files, ())
        self.assertEqual(self.index.unreadable, ())

    def test_reviewed_enumerators_exist(self) -> None:
        for rel in router.REVIEWED_NON_DOCS_ENUMERATORS:
            with self.subTest(rel=rel):
                self.assertTrue((REPO_ROOT / rel).is_file())

    def test_docs_scanners_exist_and_cover_every_tracked_text_scanner(self) -> None:
        for module in router.DOCS_SCANNER_MODULES:
            with self.subTest(module=module):
                self.assertTrue((REPO_ROOT / router._module_path(module)).is_file())
        self.assertTrue((REPO_ROOT / router.LINK_VALIDATOR).is_file())
        for rel in router.ROUTER_FILES:
            self.assertTrue((REPO_ROOT / rel).is_file(), rel)

    def test_high_risk_paths_are_never_small(self) -> None:
        for path in (
            "tests/support/paths.py",
            "scripts/packaging/package-manifest.json",
            "capabilities/x/capability.yaml",
            "runtime_platform/benchmark/x.py",
            "benchmark/corpus-index.json",
            ".github/workflows/validate.yml",
            "requirements-dev.txt",
            "docs/capability-architecture/capability-loading-baseline.json",
        ):
            with self.subTest(path=path):
                self.assertEqual(router.classify([path], self.index).tier, router.FULL)


class SharedSurfaceTests(unittest.TestCase):
    def test_summary_states_class_tier_reason_and_forcing_path(self) -> None:
        index = router.ConsumerIndex(frozenset({("features",)}), (), 1)
        text = router.summary_markdown(router.classify(["docs/features/a.md"], index))
        for line in ("Tier: **FAST**", "Class: CONSUMED_DOCS", "Reason:", "First path that forced FAST: `docs/features/a.md`"):
            self.assertIn(line, text)
        self.assertNotIn("First path", router.summary_markdown(router.classify(["docs/x/y.md"], router.ConsumerIndex(frozenset(), (), 1))))

    def test_local_classify_matches_the_ci_route_for_the_same_change_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git(repo, "init", "-q", "-b", "main")
            _git(repo, "config", "user.email", "t@example.com")
            _git(repo, "config", "user.name", "t")
            (repo / "tests").mkdir()
            (repo / "tests/test_a.py").write_text("x = 1\n", encoding="utf-8")
            (repo / "docs/area").mkdir(parents=True)
            (repo / "docs/area/a.md").write_text("a\n", encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "base")
            base = _git(repo, "rev-parse", "HEAD")
            (repo / "docs/area/a.md").write_text("b\n", encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "docs")
            head = _git(repo, "rev-parse", "HEAD")
            out = Path(tmp) / "gh-output"
            with redirect_stdout(StringIO()) as ci:
                router.main(["route", "--event-name", "pull_request", "--base", base, "--head", head, "--repo", str(repo),
                             "--tree", str(repo), "--github-output", str(out), "--step-summary", ""])
            with redirect_stdout(StringIO()) as local:
                router.main(["classify", "--base", base, "--head", head, "--repo", str(repo)])
            self.assertEqual(out.read_text(encoding="utf-8"), "tier=docs\nclass=PURE_DOCS\n")
            self.assertTrue(local.getvalue().startswith(ci.getvalue()))
            self.assertIn(router.RUN_COMMANDS[router.DOCS], local.getvalue())

    def test_docs_tier_lists_only_static_validations(self) -> None:
        listed = subprocess.run(
            [router.sys.executable, str(ROUTER), "run-docs", "--list"], capture_output=True, text=True, check=True
        ).stdout.split()
        self.assertEqual(listed, [router.LINK_VALIDATOR, *router.DOCS_SCANNER_MODULES])
        for name in listed:
            self.assertNotIn("integration", name)
            self.assertNotIn("sandbox", name)

    def test_classification_never_touches_opt_in_execution(self) -> None:
        source = ROUTER.read_text(encoding="utf-8")
        for token in ("BENCHMARK_REQUIRE_RUNTIME", "DISTRIBUTION_INSTALL_CHECK", "BENCHMARK_MIGRATION_BASE", "urllib", "socket", "requests", "http.client"):
            with self.subTest(token=token):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()


GENERAL_FILES = {
    "ops/adr/unused.md": "adr\n",
    "ops/read/runbook.md": "r\n",
    "ops/pinned/pinned-name.md": "p\n",
    "ops/enum/a.md": "a\n",
    "ops/cited/adr.md": "c\n",
    "ops/joined/j.md": "j\n",
    "weird_dir/deep/note.md": "n\n",
    "tests/test_runbook.py": 'P = REPO_ROOT / "ops/read/runbook.md"\n',
    "tests/test_pinned.py": 'NAME = "pinned-name.md"\n',
    "scripts/joined.py": 'D = ROOT / "ops" / "joined"\ntext = (D / name).read_text()\n',
    "scripts/named.py": 'D = ROOT / "ops" / "named"\ntext = (D / "x.md").read_text()\n',
    "ops/named/other.md": "o\n",
    "scripts/cited.py": '"""See ops/cited/adr.md."""\n# also ops/cited/adr.md\nX = 1\n',
    ".github/workflows/w.yml": "# ops/cited/adr.md is described here\njobs: {}\n",
}


class GeneralDocumentationTests(FixtureRepo):
    def setUp(self) -> None:
        super().setUp()
        # The docs/ fixture's dynamic consumers would (correctly) route every doc FULL; start clean.
        for rel in ("tests/test_dynamic.py", "tests/test_directory.py", "tests/test_joined.py"):
            (self.repo / rel).unlink()
        for rel, text in GENERAL_FILES.items():
            self.write(rel, text)
        self.commit("general fixtures")

    def tier(self, *paths: str) -> router.Route:
        return router.classify(list(paths), self.index())

    def test_named_sibling_read_does_not_consume_other_documents_in_the_directory(self) -> None:
        self.assertEqual(self.tier("ops/named/other.md").tier, router.DOCS)

    def test_directory_enumeration_is_full_unless_reviewed(self) -> None:
        self.write("scripts/enum.py", 'files = sorted(Path("ops/enum").glob("*.md"))\n')
        self.commit("enumerator")
        self.assertEqual(self.tier("ops/enum/a.md").tier, router.FULL)
        self.assertEqual(self.tier("ops/adr/unused.md").tier, router.FULL)
        with mock.patch.object(router, "REVIEWED_NON_DOCS_ENUMERATORS", router.REVIEWED_NON_DOCS_ENUMERATORS | {"scripts/enum.py"}):
            self.assertEqual(self.tier("ops/enum/a.md").tier, router.FAST)
            self.assertEqual(self.tier("ops/adr/unused.md").tier, router.DOCS)

    def test_new_and_existing_unconsumed_documentation_anywhere_is_docs(self) -> None:
        self.write("brand/new/adr.md", "new\n")
        index = self.index()
        for path in ("brand/new/adr.md", "ops/adr/unused.md", "weird_dir/deep/note.md", "ops/cited/adr.md"):
            with self.subTest(path=path):
                result = router.classify([path], index)
                self.assertEqual((result.tier, result.change_class), (router.DOCS, router.PURE_DOCS))
                self.assertIn("PURE_DOCS", result.reason)

    def test_every_consumer_form_keeps_documentation_out_of_docs(self) -> None:
        for path in ("ops/read/runbook.md", "ops/pinned/pinned-name.md", "ops/joined/j.md"):
            with self.subTest(path=path):
                self.assertEqual(self.tier(path).tier, router.FAST)

    def test_protected_and_format_failures_never_qualify(self) -> None:
        for path in ("ops/SKILL.md", "ops/AGENTS.md", "ops/CLAUDE.md", "skills/x/a.md", "shared/a.md", "distribution/a.md", "ops/x.txt"):
            with self.subTest(path=path):
                self.assertNotEqual(self.tier(path).tier, router.DOCS)

    def test_symlink_executable_and_shebang_documents_do_not_qualify(self) -> None:
        (self.repo / "ops/link.md").symlink_to("adr/unused.md")
        self.write("ops/shebang.md", "#!/bin/sh\n")
        self.write("ops/exec.md", "x\n")
        (self.repo / "ops/exec.md").chmod(0o755)
        self.commit("odd modes")
        index = self.index()
        for path in ("ops/link.md", "ops/shebang.md", "ops/exec.md"):
            with self.subTest(path=path):
                self.assertEqual(router.classify([path], index).tier, router.FULL)

    def test_mixed_sets_take_the_stricter_tier_of_the_non_documentation_path(self) -> None:
        for other in ("scripts/x.py", "ops/manifest.json", "scripts/validation/ci_test_route.py", ".github/workflows/validate.yml"):
            with self.subTest(other=other):
                self.assertEqual(self.tier("ops/adr/unused.md", other).tier, router.FULL)

    def test_new_consumer_reclassifies_documentation_stricter(self) -> None:
        self.assertEqual(self.tier("ops/adr/unused.md").tier, router.DOCS)
        self.write("scripts/late.py", 'DOC = "ops/adr/unused.md"\n')
        self.commit("consumer")
        self.assertEqual(self.tier("ops/adr/unused.md").tier, router.FAST)

    def test_unreviewed_tree_enumeration_and_scan_failures_route_full(self) -> None:
        self.write("tests/test_walk.py", "import os\nlist(os.walk('.'))\n")
        self.commit("walker")
        route = self.tier("ops/adr/unused.md")
        self.assertEqual(route.tier, router.FULL)
        self.assertEqual(router.classify(["ops/adr/unused.md"], None).tier, router.FULL)
        self.assertEqual(router.classify(["ops/adr/unused.md"], router.ConsumerIndex(frozenset(), (), 0, (), True)).tier, router.FULL)

    def test_deleted_unconsumed_documentation_is_docs(self) -> None:
        (self.repo / "ops/adr/unused.md").unlink()
        self.assertEqual(self.tier("ops/adr/unused.md").tier, router.DOCS)

    def test_hand_built_index_keeps_the_docs_only_rule(self) -> None:
        index = router.ConsumerIndex(frozenset(), (), 5)
        self.assertEqual(router.classify(["ops/adr/unused.md"], index).tier, router.FULL)
