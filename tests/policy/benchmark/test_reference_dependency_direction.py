#!/usr/bin/env python3
"""Benchmark reference-model dependency direction guard (Issue #792)."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

PLATFORM_ROOT = REPO_ROOT / "runtime_platform"
LIBRARY_ROOT = REPO_ROOT / "tests" / "reference" / "review"
SANCTIONED = "tests.reference.review"
PLATFORM = "runtime_platform"


def package_of(path: Path) -> str:
    return ".".join(path.parent.relative_to(REPO_ROOT).parts)


def imported_targets(source: str, package: str) -> list[tuple[int, str]]:
    """Absolute dotted import targets; `from M import n` yields `M.n` so that
    `from tests.reference import review` equals `import tests.reference.review`."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, a.name) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                parts = parts[: len(parts) - (node.level - 1)]
                base = ".".join(parts + ([node.module] if node.module else []))
            found.extend((node.lineno, f"{base}.{a.name}") for a in node.names)
    return found


def is_under(module: str, package: str) -> bool:
    return module == package or module.startswith(package + ".")


def platform_violations(path: Path, targets):
    """Platform imports of `tests` must stay inside the sanctioned library."""
    return [
        f"{path}:{line} imports {module}"
        for line, module in targets
        if is_under(module, "tests") and not is_under(module, SANCTIONED)
    ]


def library_violations(path: Path, targets):
    """The reference-model library must not depend on the platform."""
    return [
        f"{path}:{line} imports {module}"
        for line, module in targets
        if is_under(module, PLATFORM)
    ]


def scan(root: Path, check) -> list[str]:
    violations = []
    for path in sorted(root.rglob("*.py")):
        targets = imported_targets(path.read_text(encoding="utf-8"), package_of(path))
        violations.extend(check(path.relative_to(REPO_ROOT), targets))
    return violations


class ReferenceDependencyDirectionTests(unittest.TestCase):
    def test_platform_imports_only_the_sanctioned_library(self):
        self.assertEqual(scan(PLATFORM_ROOT, platform_violations), [])

    def test_library_does_not_import_the_platform(self):
        self.assertEqual(scan(LIBRARY_ROOT, library_violations), [])

    def test_scan_sees_the_known_dependency(self):
        seen = [
            m
            for p in PLATFORM_ROOT.rglob("*.py")
            for _, m in imported_targets(p.read_text(encoding="utf-8"), package_of(p))
        ]
        self.assertTrue(any(is_under(m, SANCTIONED) for m in seen))


class ImportClassificationTests(unittest.TestCase):
    PKG = "runtime_platform.benchmark.reference"

    def platform(self, source, package=PKG):
        return platform_violations(Path("x.py"), imported_targets(source, package))

    def library(self, source, package="tests.reference.review"):
        return library_violations(Path("x.py"), imported_targets(source, package))

    def test_equivalent_sanctioned_forms_are_accepted(self):
        for source in (
            "import tests.reference.review",
            "import tests.reference.review as review",
            "import tests.reference.review.decision_semantics as ds",
            "from tests.reference import review",
            "from tests.reference.review import decision_semantics",
            "from tests.reference.review import *",
            "def f():\n    from tests.reference.review import x",
        ):
            with self.subTest(source=source):
                self.assertEqual(self.platform(source), [])

    def test_forbidden_platform_imports_are_rejected(self):
        for source in (
            "import tests",
            "import tests.support.paths",
            "from tests import reference",
            "from tests.support import paths",
            "from tests.unit.review import test_x",
            "from tests.reference import benchmark",
            "from tests.reference.benchmark import x",
            "import tests.reference.benchmark.x as x",
            "def f():\n    from tests.policy import y",
        ):
            with self.subTest(source=source):
                self.assertEqual(len(self.platform(source)), 1)

    def test_non_tests_imports_are_ignored(self):
        self.assertEqual(self.platform("import os\nfrom testsuite import x"), [])

    def test_library_rejects_platform_imports_in_every_form(self):
        for source in (
            "import runtime_platform",
            "import runtime_platform.benchmark.reference as r",
            "from runtime_platform import benchmark",
            "from runtime_platform.benchmark.reference import x",
        ):
            with self.subTest(source=source):
                self.assertEqual(len(self.library(source)), 1)

    def test_library_accepts_itself_and_unrelated_modules(self):
        self.assertEqual(
            self.library("import json\nfrom tests.reference.review import a\nfrom . import b"),
            [],
        )

    def test_relative_imports_resolve_to_absolute_targets(self):
        self.assertEqual(
            self.library("from ... import runtime_platform", "tests.reference.review"),
            [],  # resolves to `tests.runtime_platform`, not the platform package
        )
        self.assertEqual(
            len(self.platform("from ... import support", "tests.reference.review")), 1
        )
        self.assertEqual(
            len(self.library("from . import x", "runtime_platform.benchmark")), 1
        )
        self.assertEqual(
            len(self.platform("from tests import x", "runtime_platform.benchmark")), 1
        )


if __name__ == "__main__":
    unittest.main()
