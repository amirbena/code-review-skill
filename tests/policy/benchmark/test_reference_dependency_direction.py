#!/usr/bin/env python3
"""Benchmark dependency direction guard (Issues #792, #849): the platform
(`runtime_platform/`) is repository tooling and must not import from `tests/`."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

PLATFORM_ROOT = REPO_ROOT / "runtime_platform"


def package_of(path: Path) -> str:
    return ".".join(path.parent.relative_to(REPO_ROOT).parts)


def imported_targets(source: str, package: str) -> list[tuple[int, str]]:
    """Absolute dotted import targets; `from M import n` yields `M.n`."""
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


def platform_violations(path: Path, targets) -> list[str]:
    return [f"{path}:{line} imports {module}" for line, module in targets if is_under(module, "tests")]


class DependencyDirectionTests(unittest.TestCase):
    def test_platform_imports_nothing_from_tests(self) -> None:
        violations = []
        for path in sorted(PLATFORM_ROOT.rglob("*.py")):
            targets = imported_targets(path.read_text(encoding="utf-8"), package_of(path))
            violations.extend(platform_violations(path.relative_to(REPO_ROOT), targets))
        self.assertEqual(violations, [])


class ImportClassificationTests(unittest.TestCase):
    PKG = "runtime_platform.benchmark.reference"

    def platform(self, source: str, package: str = PKG) -> list[str]:
        return platform_violations(Path("x.py"), imported_targets(source, package))

    def test_every_tests_import_form_is_rejected(self) -> None:
        for source in (
            "import tests",
            "import tests.support.paths",
            "from tests import support",
            "from tests.support import paths",
            "def f():\n    from tests.policy import y",
        ):
            with self.subTest(source=source):
                self.assertEqual(len(self.platform(source)), 1)

    def test_non_tests_imports_are_ignored(self) -> None:
        self.assertEqual(self.platform("import os\nfrom testsuite import x"), [])

    def test_relative_imports_resolve_to_absolute_targets(self) -> None:
        self.assertEqual(len(self.platform("from tests import x", "runtime_platform.benchmark")), 1)
        self.assertEqual(self.platform("from . import x", "runtime_platform.benchmark"), [])


if __name__ == "__main__":
    unittest.main()
