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


# Immutable archive of the v2 benchmark corpus (Issue #848): its READMEs keep the
# links they had when the evidence was frozen, some to files since removed.
FROZEN_ARCHIVE = "benchmark/corpus-v2"


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
    archive = root / FROZEN_ARCHIVE
    files = [path for path in tracked_markdown_files(root) if archive not in path.parents]
    check_repository_markdown_links(root, files)


if __name__ == "__main__":
    main()
