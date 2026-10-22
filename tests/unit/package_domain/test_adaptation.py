"""Tests for scripts/packaging/package_domain/adaptation.py — the canonical
shared-link and metadata-path rewriting rules shared by both platform
packaging scripts (issue #266)."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import tests.unit.package_domain._shared  # noqa: F401 - sys.path wiring

from package_domain import main
from package_domain.adaptation import adapt_metadata_paths, adapt_shared_links


class AdaptSharedLinksTests(unittest.TestCase):
    def test_source_depth_two_link_becomes_archive_root_relative(self) -> None:
        self.assertEqual(
            adapt_shared_links("See [severity](../../shared/policies/severity.md)."),
            "See [severity](shared/policies/severity.md).",
        )

    def test_source_depth_three_link_becomes_one_level_up(self) -> None:
        self.assertEqual(
            adapt_shared_links("See [severity](../../../shared/policies/severity.md)."),
            "See [severity](../shared/policies/severity.md).",
        )

    def test_replaces_every_occurrence(self) -> None:
        text = "a ../../shared/x.md b ../../shared/y.md"
        self.assertEqual(adapt_shared_links(text), "a shared/x.md b shared/y.md")

    def test_leaves_unrelated_relative_links_untouched(self) -> None:
        text = "See [local](../SKILL.md) and [sibling](runbooks/local-review.md)."
        self.assertEqual(adapt_shared_links(text), text)


class AdaptSharedLinksCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def _write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_single_file_invocation_is_unchanged(self) -> None:
        one = self._write("a.md", b"[x](../../shared/a.md)")
        self.assertEqual(main(["adapt-shared-links", str(one)]), 0)
        self.assertEqual(one.read_bytes(), b"[x](shared/a.md)")

    def test_adapts_every_file_with_unicode_and_spaces_in_names(self) -> None:
        first = self._write("a b.md", "\u05e9 ../../shared/a.md".encode())
        second = self._write("\u05d1.md", "../../../shared/b.md \u2713".encode())
        self.assertEqual(main(["adapt-shared-links", str(first), str(second)]), 0)
        self.assertEqual(first.read_bytes(), "\u05e9 shared/a.md".encode())
        self.assertEqual(second.read_bytes(), "../shared/b.md \u2713".encode())

    def test_undecodable_file_fails_and_leaves_every_file_unmodified(self) -> None:
        good = self._write("good.md", b"../../shared/a.md")
        bad = self._write("bad.md", b"\xff\xfe../../shared/b.md")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["adapt-shared-links", str(good), str(bad)]), 1)
        self.assertIn("error:", err.getvalue())
        self.assertEqual(good.read_bytes(), b"../../shared/a.md")

    def test_missing_file_fails_and_leaves_other_files_unmodified(self) -> None:
        good = self._write("good.md", b"../../shared/a.md")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["adapt-shared-links", str(good), str(self.root / "nope.md")]), 1)
        self.assertEqual(good.read_bytes(), b"../../shared/a.md")

    def test_requires_at_least_one_file(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["adapt-shared-links"])
        self.assertEqual(raised.exception.code, 2)


class AdaptMetadataPathsTests(unittest.TestCase):
    def test_rewrites_list_entry_shared_prefix(self) -> None:
        text = "resources:\n  - ../../../shared/policies/severity.md\n"
        self.assertEqual(
            adapt_metadata_paths(text),
            "resources:\n  - ../shared/policies/severity.md\n",
        )

    def test_leaves_non_list_lines_untouched(self) -> None:
        text = "name: local-code-review\ndescription: ../../../shared/ mentioned in prose\n"
        self.assertEqual(adapt_metadata_paths(text), text)

    def test_leaves_skill_local_list_entries_untouched(self) -> None:
        text = "resources:\n  - policies/pr-context.md\n"
        self.assertEqual(adapt_metadata_paths(text), text)


if __name__ == "__main__":
    unittest.main()
