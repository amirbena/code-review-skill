"""Argument parsing for the packaging-domain CLI.

Invoked identically by ``scripts/packaging/package-skills.sh`` and
``scripts/packaging/package-skills.ps1`` (via ``scripts/packaging/package_adapt.py``) so both
platform orchestration scripts share one implementation of shared-link
adaptation, metadata-path adaptation, release-version stamping, and SKILL.md
frontmatter structural validation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .adaptation import adapt_metadata_paths_file, adapt_shared_links_file
from .tree import (
    build_archive,
    check_tree_self_contained,
    distribute_skill_md,
    normalize_tree,
    validate_agent_skill,
    verify_archive,
    write_tree_manifest,
)
from .validation import SkillFrontmatterError, validate_skill_frontmatter
from .version import stamp_skill_md_from_authority


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

    stamp_version = subparsers.add_parser(
        "stamp-release-version",
        help="stamp a staged root SKILL.md with the version from CHANGELOG.md's newest release heading",
    )
    stamp_version.add_argument("file", type=Path)
    stamp_version.add_argument("changelog", type=Path)

    finalize = subparsers.add_parser(
        "finalize-tree",
        help="normalize a staged tree, apply the distribution frontmatter form, and validate it (#507)",
    )
    finalize.add_argument("tree", type=Path)
    finalize.add_argument("expected_name")

    manifest = subparsers.add_parser(
        "write-tree-manifest", help="write dist/skills-manifest.json for every built dist/skills/<name>/ tree"
    )
    manifest.add_argument("dist_dir", type=Path)

    archive = subparsers.add_parser("build-archive", help="zip a built tree deterministically")
    archive.add_argument("tree", type=Path)
    archive.add_argument("archive", type=Path)

    verify = subparsers.add_parser("verify-archive", help="fail unless the archive equals the tree byte for byte")
    verify.add_argument("tree", type=Path)
    verify.add_argument("archive", type=Path)

    args = parser.parse_args(argv)

    try:
        if args.command == "adapt-shared-links":
            adapt_shared_links_file(args.file)
        elif args.command == "adapt-metadata-paths":
            adapt_metadata_paths_file(args.file)
        elif args.command == "validate-frontmatter":
            validate_skill_frontmatter(args.file, args.expected_name)
        elif args.command == "stamp-release-version":
            version, previous = stamp_skill_md_from_authority(args.file, args.changelog)
            if previous is None:
                print(f"packaged Skill version {version} (release authority: {args.changelog})")
            else:
                print(
                    f"note: committed SKILL.md version {previous} differs from the release "
                    f"authority {version}; packaged with {version}"
                )
        elif args.command == "finalize-tree":
            normalize_tree(args.tree)
            distribute_skill_md(args.tree / "SKILL.md")
            validate_agent_skill(args.tree, args.expected_name)
            check_tree_self_contained(args.tree)
        elif args.command == "write-tree-manifest":
            print(f"tree manifest written to: {write_tree_manifest(args.dist_dir)}")
        elif args.command == "build-archive":
            build_archive(args.tree, args.archive)
        elif args.command == "verify-archive":
            verify_archive(args.tree, args.archive)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via scripts/packaging/package_adapt.py
    raise SystemExit(main())
