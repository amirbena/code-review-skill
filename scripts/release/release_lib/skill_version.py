"""Skill ``SKILL.md`` frontmatter version: release-time stamping and archive verification."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from release_lib.semver_version import validate_semver

_PACKAGING = str(Path(__file__).resolve().parents[2] / "packaging")
if _PACKAGING not in sys.path:
    sys.path.insert(0, _PACKAGING)

from package_domain.version import frontmatter_version, stamp_frontmatter_version  # noqa: E402

PACKAGE_MANIFEST = Path("scripts") / "packaging" / "package-manifest.json"


def _parse_targets(manifest_text: str) -> list[tuple[str, str]]:
    manifest = json.loads(manifest_text)
    return [(skill["name"], skill["archive"]) for skill in manifest["skills"].values()]


def skill_targets(repo_root: Path) -> list[tuple[str, str]]:
    """(skill name, archive filename) for every packaged Skill, from the package manifest."""
    return _parse_targets((repo_root / PACKAGE_MANIFEST).read_text(encoding="utf-8"))


def skill_targets_at(repo_root: Path, ref: str) -> list[tuple[str, str]] | None:
    """The packaged Skills as declared by the package manifest committed at `ref` (a release tag).

    A release is judged by the archive set it was published with, which can differ
    from the current manifest (v2 shipped two Skills, v3 ships eleven). `None` when
    the manifest at `ref` cannot be read, so callers fail closed.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{PACKAGE_MANIFEST.as_posix()}"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        )
        return _parse_targets(result.stdout)
    except (subprocess.CalledProcessError, OSError, ValueError, KeyError, TypeError):
        return None


def stamp_skill_versions(repo_root: Path, version: str) -> list[Path]:
    """Write `version` into every packaged Skill's SKILL.md (inserting the line where a never-released
    v3 Skill has none, ADR §11); return the files that changed."""
    validate_semver(version)
    changed: list[Path] = []
    for name, _archive in skill_targets(repo_root):
        path = repo_root / "skills" / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        stamped = stamp_frontmatter_version(text, version, insert_missing=True)
        if stamped != text:
            path.write_text(stamped, encoding="utf-8")
            changed.append(path)
    return changed


def archive_skill_version(archive: Path) -> str | None:
    """The frontmatter `version` of the archive's root SKILL.md, or None if absent."""
    with zipfile.ZipFile(archive) as zf:
        if "SKILL.md" not in zf.namelist():
            return None
        return frontmatter_version(zf.read("SKILL.md").decode("utf-8"))


def verify_archive_versions(repo_root: Path, dist_dir: Path, version: str) -> list[str]:
    """Problems (empty when clean) for any Skill archive not reporting exactly `version`."""
    problems: list[str] = []
    for _name, archive in skill_targets(repo_root):
        path = dist_dir / archive
        if not path.is_file():
            problems.append(f"{archive}: archive is missing from {dist_dir}")
            continue
        found = archive_skill_version(path)
        if found != version:
            problems.append(
                f"{archive}: SKILL.md frontmatter version is {found!r}, expected release version {version!r}"
            )
    return problems
