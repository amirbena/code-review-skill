"""Tests for scripts/packaging/adaptation.py — the canonical shared-link
and metadata-path rewriting rules shared by both platform packaging
scripts (issue #266)."""

from __future__ import annotations

import unittest

import tests.unit.packaging._shared  # noqa: F401 - sys.path wiring

from packaging.adaptation import adapt_metadata_paths, adapt_shared_links


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
