#!/usr/bin/env python3
"""Validate internal Markdown links across tracked repository files.

Usage:
    python3 scripts/validation/validate-markdown-links.py [--repo-root <root>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skill_metadata.links import check_repository_markdown_links, tracked_markdown_files  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="repository root (default: current directory)",
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    check_repository_markdown_links(root, tracked_markdown_files(root))


if __name__ == "__main__":
    main()
