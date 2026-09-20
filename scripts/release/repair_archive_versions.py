#!/usr/bin/env python3
"""Maintainer tool to repair stale SKILL.md versions in published Skill archives (issue #497).

Three separate phases: `reconstruct` and `verify` never modify a Release;
`replace` is the explicit, opt-in publish step. See docs/RELEASE.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

from release_lib import archive_repair as repair


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="repository root holding the release tags (default: cwd)")
    parser.add_argument("--work-dir", required=True, help="directory for rebuilt archives and evidence (outside the repo)")
    sub = parser.add_subparsers(dest="phase", required=True)
    for name, help_text in (
        ("reconstruct", "rebuild both archives from each tag with only the release version stamped"),
        ("verify", "compare each rebuilt archive with its published asset (read-only)"),
        ("replace", "upload verified archives over the published assets, then re-check them"),
    ):
        phase = sub.add_parser(name, help=help_text)
        phase.add_argument("tags", nargs="+", metavar="vX.Y.Z")
        if name == "replace":
            phase.add_argument("--confirm-replace", action="store_true", help="required to modify a published Release")
    return parser


def _run_phase(phase: str, repo_root: Path, work_dir: Path, tag: str) -> dict:
    if phase == "reconstruct":
        record = repair.reconstruct(repo_root, tag, work_dir)
        return {archive: {"passed": True, "sha256": sha} for archive, sha in record["archives"].items()}
    if phase == "verify":
        return repair.verify(repo_root, tag, work_dir)
    return repair.replace(repo_root, tag, work_dir)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root, work_dir = Path(args.repo_root).resolve(), Path(args.work_dir).resolve()
    if args.phase == "replace" and not args.confirm_replace:
        print("::error::replace modifies published Release assets; re-run with --confirm-replace")
        return 2
    failed = False
    for tag in args.tags:
        try:
            results = _run_phase(args.phase, repo_root, work_dir, tag)
        except (repair.RepairError, ValueError, OSError, zipfile.BadZipFile) as exc:
            print(f"::error::{tag}: {exc}")
            failed = True
            continue
        print(json.dumps({tag: results}, indent=2))
        failed = failed or not repair.phase_ok(results)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
