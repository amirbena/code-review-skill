"""Tests for scripts/packaging/package_domain/tree.py — the deterministic,
self-contained Skill tree, its manifest, and the archive built from it (issue #507)."""

from __future__ import annotations

import contextlib
import io
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

import tests.unit.package_domain._shared  # noqa: F401 - sys.path wiring

from package_domain import main
from package_domain.tree import (
    MANIFEST_NAME,
    SkillTreeError,
    build_archive,
    check_tree_self_contained,
    distribution_frontmatter,
    normalize_tree,
    tree_files,
    tree_hash,
    validate_agent_skill,
    verify_archive,
    write_tree_manifest,
)
from package_domain.version import frontmatter_version

SOURCE = "---\nname: demo-skill\nversion: 1.54.0\ndescription: A demo Skill.\n---\n\n# Demo\n"


class DistributionFrontmatterTests(unittest.TestCase):
    def test_moves_version_under_metadata_and_keeps_field_order(self) -> None:
        self.assertEqual(
            distribution_frontmatter(SOURCE),
            '---\nname: demo-skill\nmetadata:\n  version: "1.54.0"\ndescription: A demo Skill.\n---\n\n# Demo\n',
        )

    def test_the_version_is_still_readable_in_the_built_form(self) -> None:
        self.assertEqual(frontmatter_version(SOURCE), "1.54.0")
        self.assertEqual(frontmatter_version(distribution_frontmatter(SOURCE)), "1.54.0")

    def test_refuses_to_merge_an_existing_metadata_key(self) -> None:
        with self.assertRaises(SkillTreeError):
            distribution_frontmatter("---\nname: x\nmetadata:\n  a: b\nversion: 1.0.0\n---\n")

    def test_refuses_a_skill_md_without_a_version(self) -> None:
        with self.assertRaises(SkillTreeError):
            distribution_frontmatter("---\nname: x\n---\n")


class ValidateAgentSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tree = Path(self._tmp.name) / "demo-skill"
        self.tree.mkdir()

    def write(self, text: str) -> None:
        (self.tree / "SKILL.md").write_text(text, encoding="utf-8")

    def test_the_source_form_is_rejected_for_its_top_level_version(self) -> None:
        self.write(SOURCE)
        with self.assertRaisesRegex(SkillTreeError, "unexpected frontmatter fields: version"):
            validate_agent_skill(self.tree, "demo-skill")

    def test_the_built_form_passes(self) -> None:
        self.write(distribution_frontmatter(SOURCE))
        validate_agent_skill(self.tree, "demo-skill")

    def test_directory_name_must_match_the_skill_name(self) -> None:
        self.write(distribution_frontmatter(SOURCE.replace("demo-skill", "other-skill")))
        with self.assertRaisesRegex(SkillTreeError, "must match skill name"):
            validate_agent_skill(self.tree, "other-skill")

    def test_name_and_description_rules(self) -> None:
        for bad in ("Demo-Skill", "-demo", "demo--skill", "demo_skill"):
            with self.subTest(name=bad):
                self.write(f"---\nname: {bad}\ndescription: ok\n---\n")
                with self.assertRaises(SkillTreeError):
                    validate_agent_skill(self.tree, bad)
        self.write("---\nname: demo-skill\ndescription: " + "x" * 1025 + "\n---\n")
        with self.assertRaisesRegex(SkillTreeError, "1024"):
            validate_agent_skill(self.tree, "demo-skill")


class SelfContainedTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tree = Path(self._tmp.name) / "demo-skill"
        (self.tree / "policies").mkdir(parents=True)
        (self.tree / "SKILL.md").write_text("See [policy](policies/a.md).\n", encoding="utf-8")
        (self.tree / "policies" / "a.md").write_text("Back to [skill](../SKILL.md#top).\n", encoding="utf-8")

    def test_resolving_relative_links_pass(self) -> None:
        check_tree_self_contained(self.tree)

    def test_a_missing_target_fails(self) -> None:
        (self.tree / "policies" / "a.md").write_text("[gone](missing.md)\n", encoding="utf-8")
        with self.assertRaisesRegex(SkillTreeError, "does not resolve"):
            check_tree_self_contained(self.tree)

    def test_a_link_escaping_the_tree_fails(self) -> None:
        (self.tree / "SKILL.md").write_text("[up](../elsewhere.md)\n", encoding="utf-8")
        with self.assertRaisesRegex(SkillTreeError, "escapes"):
            check_tree_self_contained(self.tree)

    def test_an_unadapted_shared_reference_fails(self) -> None:
        (self.tree / "SKILL.md").write_text("[shared](../../shared/policies/x.md)\n", encoding="utf-8")
        with self.assertRaises(SkillTreeError):
            check_tree_self_contained(self.tree)


class DeterminismTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def make_tree(self, name: str = "demo-skill", *, crlf: bool = False, bom: bool = False) -> Path:
        tree = self.root / "dist" / "skills" / name
        (tree / "b").mkdir(parents=True)
        body = "line one\nline two\n"
        text = body.replace("\n", "\r\n") if crlf else body
        data = (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8")
        (tree / "b" / "z.md").write_bytes(data)
        (tree / "a.md").write_bytes(data)
        (tree / "blob.bin").write_bytes(b"\x00\x01\xff")
        return tree

    def test_normalization_yields_lf_no_bom_and_fixed_modes(self) -> None:
        tree = self.make_tree(crlf=True, bom=True)
        normalize_tree(tree)
        self.assertEqual((tree / "a.md").read_bytes(), b"line one\nline two\n")
        self.assertEqual((tree / "blob.bin").read_bytes(), b"\x00\x01\xff")
        self.assertEqual(stat.S_IMODE((tree / "a.md").stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE((tree / "b").stat().st_mode), 0o755)

    def test_differently_authored_trees_hash_identically_after_normalization(self) -> None:
        plain = self.make_tree("plain")
        messy = self.make_tree("messy", crlf=True, bom=True)
        for tree in (plain, messy):
            normalize_tree(tree)
        self.assertEqual(tree_hash(tree_files(plain)), tree_hash(tree_files(messy)))

    def test_tree_hash_depends_on_paths_and_contents(self) -> None:
        self.assertNotEqual(tree_hash({"a": "1" * 64}), tree_hash({"b": "1" * 64}))
        self.assertNotEqual(tree_hash({"a": "1" * 64}), tree_hash({"a": "2" * 64}))

    def test_manifest_is_reproducible_and_sits_outside_the_skill_trees(self) -> None:
        tree = self.make_tree()
        normalize_tree(tree)
        first = write_tree_manifest(self.root / "dist", ["demo-skill"]).read_bytes()
        second = write_tree_manifest(self.root / "dist", ["demo-skill"]).read_bytes()
        self.assertEqual(first, second)
        self.assertEqual(write_tree_manifest(self.root / "dist", ["demo-skill"]), self.root / "dist" / MANIFEST_NAME)
        self.assertFalse((tree / MANIFEST_NAME).exists())

    def test_manifest_lists_only_the_named_trees(self) -> None:
        self.make_tree("built")
        self.make_tree("stale")
        (self.root / "dist" / "skills" / "stray").mkdir()
        path = write_tree_manifest(self.root / "dist", ["built"])
        self.assertEqual(list(json.loads(path.read_text(encoding="utf-8"))["skills"]), ["built"])
        with self.assertRaises(SkillTreeError):
            write_tree_manifest(self.root / "dist", ["missing"])

    def test_archive_is_deterministic_and_equals_the_tree(self) -> None:
        tree = self.make_tree()
        normalize_tree(tree)
        one, two = self.root / "one.zip", self.root / "two.zip"
        build_archive(tree, one)
        (tree / "a.md").touch()  # a new mtime must not change the archive
        build_archive(tree, two)
        self.assertEqual(one.read_bytes(), two.read_bytes())
        verify_archive(tree, one)
        with zipfile.ZipFile(one) as zf:
            self.assertEqual(zf.namelist(), sorted(zf.namelist()))
            self.assertTrue(all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in zf.infolist()))

    def test_verify_archive_reports_drift(self) -> None:
        tree = self.make_tree()
        normalize_tree(tree)
        archive = self.root / "a.zip"
        build_archive(tree, archive)
        (tree / "a.md").write_bytes(b"changed\n")
        with self.assertRaisesRegex(SkillTreeError, "differ"):
            verify_archive(tree, archive)


class FinalizeTreeCliTests(unittest.TestCase):
    def test_finalize_tree_produces_a_spec_valid_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "demo-skill"
            tree.mkdir()
            (tree / "SKILL.md").write_bytes(SOURCE.replace("\n", "\r\n").encode("utf-8"))
            self.assertEqual(main(["finalize-tree", str(tree), "demo-skill"]), 0)
            self.assertEqual(
                (tree / "SKILL.md").read_text(encoding="utf-8"), distribution_frontmatter(SOURCE)
            )

    def test_finalize_tree_fails_closed_on_a_broken_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "demo-skill"
            tree.mkdir()
            (tree / "SKILL.md").write_text(SOURCE + "[x](nope.md)\n", encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(main(["finalize-tree", str(tree), "demo-skill"]), 1)
            self.assertIn("does not resolve", err.getvalue())


if __name__ == "__main__":
    unittest.main()
