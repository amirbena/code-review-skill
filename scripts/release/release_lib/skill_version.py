"""Skill ``SKILL.md`` frontmatter version: release-time stamping and archive verification."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from release_lib.semver_version import validate_semver

_PACKAGING = str(Path(__file__).resolve().parents[2] / "packaging")
if _PACKAGING not in sys.path:
    sys.path.insert(0, _PACKAGING)

from package_domain.version import frontmatter_version, stamp_frontmatter_version  # noqa: E402

PACKAGE_MANIFEST = Path("scripts") / "packaging" / "package-manifest.json"


def skill_targets(repo_root: Path) -> list[tuple[str, str]]:
    """(skill name, archive filename) for every packaged Skill, from the package manifest."""
    manifest = json.loads((repo_root / PACKAGE_MANIFEST).read_text(encoding="utf-8"))
    return [(skill["name"], skill["archive"]) for skill in manifest["skills"].values()]


def stamp_skill_versions(repo_root: Path, version: str) -> list[Path]:
    """Write `version` into every packaged Skill's SKILL.md; return the files that changed."""
    validate_semver(version)
    changed: list[Path] = []
    for name, _archive in skill_targets(repo_root):
        path = repo_root / "skills" / name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        stamped = stamp_frontmatter_version(text, version)
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
