"""Argument parsing for the packaging-domain CLI.

Invoked identically by ``scripts/package-skills.sh`` and
``scripts/package-skills.ps1`` (via ``scripts/package_adapt.py``) so both
platform orchestration scripts share one implementation of shared-link
adaptation, metadata-path adaptation, and SKILL.md frontmatter structural
validation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .adaptation import adapt_metadata_paths_file, adapt_shared_links_file
from .validation import SkillFrontmatterError, validate_skill_frontmatter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="package_adapt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    adapt_links = subparsers.add_parser(
        "adapt-shared-links", help="rewrite ../../shared/ and ../../../shared/ links in place"
    )
    adapt_links.add_argument("file", type=Path)

    adapt_metadata = subparsers.add_parser(
        "adapt-metadata-paths", help="rewrite metadata/skill.yaml's shared-resource prefix in place"
    )
    adapt_metadata.add_argument("file", type=Path)

    validate_frontmatter = subparsers.add_parser(
        "validate-frontmatter", help="validate a staged root SKILL.md's frontmatter structure"
    )
    validate_frontmatter.add_argument("file", type=Path)
    validate_frontmatter.add_argument("expected_name")

    args = parser.parse_args(argv)

    try:
        if args.command == "adapt-shared-links":
            adapt_shared_links_file(args.file)
        elif args.command == "adapt-metadata-paths":
            adapt_metadata_paths_file(args.file)
        elif args.command == "validate-frontmatter":
            validate_skill_frontmatter(args.file, args.expected_name)
    except (OSError, SkillFrontmatterError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via scripts/package_adapt.py
    raise SystemExit(main())
