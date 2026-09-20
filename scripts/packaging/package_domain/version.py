"""Release-version resolution and SKILL.md frontmatter version stamping.

The version authority is the newest ``## vX.Y.Z`` heading in CHANGELOG.md,
written only by the release flow alongside the ``vX.Y.Z`` tag.
"""

from __future__ import annotations

import re
from pathlib import Path

_STRICT = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
VERSION_RE = re.compile(rf"^{_STRICT}$")
_RELEASE_HEADING = re.compile(rf"^## v({_STRICT})(?=\s|$)", re.MULTILINE)
_VERSION_LINE = re.compile(r"^version:[ \t]*(\S+)[ \t]*$")


class ReleaseVersionError(ValueError):
    """The release authority could not be resolved."""


def newest_release_version(changelog_text: str) -> str | None:
    match = _RELEASE_HEADING.search(changelog_text)
    return match.group(1) if match else None


def resolve_release_version(changelog: Path) -> str:
    try:
        text = Path(changelog).read_bytes().decode("utf-8")
    except OSError as exc:
        raise ReleaseVersionError(f"cannot read the release authority {changelog}: {exc}") from exc
    version = newest_release_version(text)
    if version is None:
        raise ReleaseVersionError(
            f"{changelog} has no '## vX.Y.Z' release heading to derive the packaged Skill version from"
        )
    return version


def _frontmatter_version_index(lines: list[str]) -> int | None:
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return None
    for index in range(1, lines.index("---", 1)):
        if _VERSION_LINE.match(lines[index]):
            return index
    return None


def frontmatter_version(text: str) -> str | None:
    lines = text.split("\n")
    index = _frontmatter_version_index(lines)
    return None if index is None else _VERSION_LINE.match(lines[index]).group(1)


def stamp_frontmatter_version(text: str, version: str) -> str:
    if not VERSION_RE.match(version):
        raise ValueError(f"version must be strict x.y.z (no 'v' prefix, no leading zeros): got {version!r}")
    lines = text.split("\n")
    index = _frontmatter_version_index(lines)
    if index is None:
        raise ValueError("SKILL.md frontmatter has no 'version:' line to stamp")
    lines[index] = f"version: {version}"
    return "\n".join(lines)


def stamp_skill_md_from_authority(skill_md: Path, changelog: Path) -> tuple[str, str | None]:
    """Stamp `skill_md` with the authority's version; return (version, previous value if it changed)."""
    version = resolve_release_version(changelog)
    text = Path(skill_md).read_bytes().decode("utf-8")
    previous = frontmatter_version(text)
    stamped = stamp_frontmatter_version(text, version)
    if stamped == text:
        return version, None
    Path(skill_md).write_bytes(stamped.encode("utf-8"))
    return version, previous
