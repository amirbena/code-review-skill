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
_VERSION_LINE = re.compile(r"^version:[ \t]*(\S+)[ \t]*\r?$")


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
    # Lines keep any trailing "\r" so CRLF files are read and rewritten unchanged.
    stripped = [line.rstrip("\r") for line in lines]
    if not stripped or stripped[0] != "---" or "---" not in stripped[1:]:
        return None
    for index in range(1, stripped.index("---", 1)):
        if _VERSION_LINE.match(lines[index]):
            return index
    return None


_METADATA_VERSION_LINE = re.compile(r"^[ \t]+version:[ \t]*\"?([^\s\"]+)\"?[ \t]*\r?$")


def frontmatter_version(text: str) -> str | None:
    """The Skill version: top-level `version:` (source form), else `metadata.version` (built form, #507)."""
    lines = text.split("\n")
    index = _frontmatter_version_index(lines)
    if index is not None:
        return _VERSION_LINE.match(lines[index]).group(1)
    stripped = [line.rstrip("\r") for line in lines]
    if not stripped or stripped[0] != "---" or "---" not in stripped[1:]:
        return None
    closing = stripped.index("---", 1)
    for at in range(1, closing - 1):
        if stripped[at] == "metadata:":
            match = _METADATA_VERSION_LINE.match(lines[at + 1])
            return match.group(1) if match else None
    return None


def stamp_frontmatter_version(text: str, version: str, *, insert_missing: bool = False) -> str:
    """Write `version` into the frontmatter's top-level `version:` line.

    A v3 Skill carries no `version:` line before its first release (ADR §11).
    Only the release run's stamp step passes ``insert_missing=True``, which
    adds the line after ``description:``; any other caller fails on a missing line.
    """
    if not VERSION_RE.match(version):
        raise ValueError(f"version must be strict x.y.z (no 'v' prefix, no leading zeros): got {version!r}")
    lines = text.split("\n")
    index = _frontmatter_version_index(lines)
    if index is None:
        if not insert_missing:
            raise ValueError("SKILL.md frontmatter has no 'version:' line to stamp")
        return _insert_version_line(lines, version)
    lines[index] = f"version: {version}" + ("\r" if lines[index].endswith("\r") else "")
    return "\n".join(lines)


def _insert_version_line(lines: list[str], version: str) -> str:
    plain = [line.rstrip("\r") for line in lines]
    if not plain or plain[0] != "---" or "---" not in plain[1:]:
        raise ValueError("SKILL.md has no frontmatter to insert a 'version:' line into")
    closing = plain.index("---", 1)
    # `description:` must stay the last frontmatter line (packaging validation), so the
    # version goes before it, as in v2.
    at = next((i for i in range(1, closing) if plain[i].startswith("description:")), closing)
    eol = "\r" if lines[0].endswith("\r") else ""
    lines.insert(at, f"version: {version}{eol}")
    return "\n".join(lines)


def stamp_skill_md_from_authority(skill_md: Path, changelog: Path) -> tuple[str | None, str | None]:
    """Stamp `skill_md` with the authority's version; return (version, previous value if it changed).

    A Skill with no `version:` line has never been released (ADR §11): it is
    left unstamped and ``(None, None)`` is returned, so a non-release build
    never labels it with an older release's version.
    """
    text = Path(skill_md).read_bytes().decode("utf-8")
    if frontmatter_version(text) is None:
        return None, None
    version = resolve_release_version(changelog)
    previous = frontmatter_version(text)
    stamped = stamp_frontmatter_version(text, version)
    if stamped == text:
        return version, None
    Path(skill_md).write_bytes(stamped.encode("utf-8"))
    return version, previous
