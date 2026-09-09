#!/usr/bin/env python3
"""Validate and query the declarative Skill package manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any


def _relative_path(value: str, label: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must stay repository/package relative: {value}")
    return path


def load_target(manifest_path: Path, target: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported package manifest schema_version")
    try:
        skill = manifest["skills"][target]
    except KeyError as exc:
        raise ValueError(f"package manifest has no target {target!r}") from exc

    skill_name = skill["name"]
    if PurePosixPath(skill_name).name != skill_name:
        raise ValueError("package Skill name must be one path segment")
    archive = _relative_path(skill["archive"], "package archive")
    if archive.name != skill["archive"] or archive.suffix != ".zip":
        raise ValueError("package archive must be a relative .zip filename")

    shared_entries = manifest["shared_files"]
    skill_entries = skill["files"]
    allowed_shared_roots = ("shared/policies/", "shared/templates/")
    for entry in shared_entries:
        source = entry["source"]
        _relative_path(source, "package source")
        if source != "LICENSE" and not source.startswith(allowed_shared_roots):
            raise ValueError(f"shared package source escapes approved roots: {source}")
    skill_root = f"skills/{skill_name}/"
    for entry in skill_entries:
        source = entry["source"]
        _relative_path(source, "package source")
        if not source.startswith(skill_root):
            raise ValueError(f"Skill package source escapes {skill_root}: {source}")

    entries = [*shared_entries, *skill_entries]
    destinations: set[str] = set()
    for entry in entries:
        destination = entry["destination"]
        _relative_path(destination, "package destination")
        if destination in destinations:
            raise ValueError(f"duplicate package destination: {destination}")
        destinations.add(destination)
    for required in skill["required_entries"]:
        _relative_path(required, "required package entry")
        if required not in destinations:
            raise ValueError(f"invalid required package entry: {required}")
    return skill, entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("target")
    parser.add_argument("query", choices=("validate", "name", "archive", "files", "required_entries"))
    args = parser.parse_args()
    try:
        skill, entries = load_target(args.manifest, args.target)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.query in ("name", "archive"):
        print(skill[args.query])
    elif args.query == "files":
        for entry in entries:
            print(f"{entry['source']}\t{entry['destination']}")
    elif args.query == "required_entries":
        print("\n".join(skill["required_entries"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
