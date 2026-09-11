"""Tests for repository-wide Markdown link validation."""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from skill_metadata import links  # noqa: E402


class ValidateMarkdownLinksTests(unittest.TestCase):
    def test_valid_links_and_fragment_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "policies" / "example.md"
            target.parent.mkdir()
            target.write_text("# Example\n", encoding="utf-8")
            source = root / "README.md"
            source.write_text(
                "[policy](policies/example.md) [fragment](policies/example.md#section)\n"
                "[external](https://example.test/doc)\n"
                "inline `policies/missing.md` is ignored\n",
                encoding="utf-8",
            )
            broken = links.find_broken_markdown_links([source], root)
            self.assertEqual(broken, [])

    def test_broken_link_reports_source_line_and_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "docs" / "guide.md"
            source.parent.mkdir()
            source.write_text(
                "See [missing](../policies/nope.md) for details.\n",
                encoding="utf-8",
            )
            broken = links.find_broken_markdown_links([source], root)
            self.assertEqual(len(broken), 1)
            self.assertEqual(broken[0].source, source)
            self.assertEqual(broken[0].line, 1)
            self.assertEqual(broken[0].target, "../policies/nope.md")

    def test_check_repository_markdown_links_exits_with_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "AGENTS.md"
            source.write_text("[broken](policies/missing.md)\n", encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as ctx:
                    links.check_repository_markdown_links(root, [source])
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("AGENTS.md:1: broken link 'policies/missing.md'", stderr.getvalue())

    def test_repository_passes_validation(self) -> None:
        links.check_repository_markdown_links(REPO_ROOT, links.tracked_markdown_files(REPO_ROOT))

    def test_cli_passes_on_repository(self) -> None:
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "validate-markdown-links.py")],
            cwd=REPO_ROOT,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
