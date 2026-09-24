"""The canonical, deterministic, self-contained Skill tree (issue #507).

``dist/skills/<name>/`` is the one build output every distribution channel
derives from; the release zip is built *from* that tree, never re-derived.
Both platform scripts delegate here, so the shell and PowerShell builds
produce byte-identical trees, manifests, and archives.

- ``normalize_tree``       — LF endings, no BOM, normalized modes and mtimes
- ``distribution_frontmatter`` — built-tree-only ``version`` -> ``metadata.version``
- ``validate_agent_skill`` — offline equivalent of ``skills-ref validate``
- ``check_tree_self_contained`` — links and metadata paths resolve inside the tree
- ``write_tree_manifest``  — per-file SHA-256 plus an aggregate tree hash
- ``build_archive`` / ``verify_archive`` — the zip is the tree, byte for byte
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import unicodedata
import zipfile
from pathlib import Path

MANIFEST_NAME = "skills-manifest.json"
MANIFEST_SCHEMA_VERSION = 1
# Fixed ZIP timestamp (the format's epoch), so an archive carries no build time.
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_FILE_MODE = 0o644
_DIR_MODE = 0o755

_VERSION_LINE = re.compile(r"^version:[ \t]*(\S+)[ \t]*$")
_MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_SHARED_ESCAPE = re.compile(r"\.\./\.\./(?:\.\./)?shared/")


class SkillTreeError(ValueError):
    """A built Skill tree, manifest, or archive failed a distribution check."""


def _files(root: Path) -> list[Path]:
    return sorted(
        (p for p in root.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix(),
    )


def _is_text(data: bytes) -> bool:
    if b"\0" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def normalize_tree(root: Path) -> None:
    """Make the tree byte-stable: LF text, no BOM, fixed modes, no timestamps in content."""
    root = Path(root)
    for path in _files(root):
        data = path.read_bytes()
        if _is_text(data):
            normalized = data.removeprefix(b"\xef\xbb\xbf").replace(b"\r\n", b"\n")
            if normalized != data:
                path.write_bytes(normalized)
        path.chmod(_FILE_MODE)
    for directory in [root, *(p for p in root.rglob("*") if p.is_dir())]:
        directory.chmod(_DIR_MODE)


def distribution_frontmatter(text: str) -> str:
    """Move the frontmatter's top-level ``version`` to ``metadata.version`` (built tree only).

    ``skills-ref validate`` (Agent Skills spec) allows only ``name``,
    ``description``, ``license``, ``compatibility``, ``metadata`` and
    ``allowed-tools`` at the top level (#507: recorded result). The source
    ``SKILL.md`` contract from #439 is unchanged; only the distributed tree
    carries the spec-conformant form.
    """
    lines = text.split("\n")
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise SkillTreeError("SKILL.md has no frontmatter to normalize")
    closing = lines.index("---", 1)
    if any(line.startswith("metadata:") for line in lines[1:closing]):
        raise SkillTreeError("SKILL.md frontmatter already has a 'metadata' key; refusing to merge")
    for index in range(1, closing):
        match = _VERSION_LINE.match(lines[index])
        if match:
            lines[index : index + 1] = ["metadata:", f'  version: "{match.group(1)}"']
            return "\n".join(lines)
    raise SkillTreeError("SKILL.md frontmatter has no top-level 'version:' line to normalize")


def distribute_skill_md(skill_md: Path) -> None:
    skill_md = Path(skill_md)
    skill_md.write_bytes(distribution_frontmatter(skill_md.read_bytes().decode("utf-8")).encode("utf-8"))


def _frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SkillTreeError(f"{skill_md} must start with YAML frontmatter (---)")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise SkillTreeError(f"{skill_md} frontmatter not properly closed with ---")
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - PyYAML is a dev requirement
        raise SkillTreeError("PyYAML is required to validate the built Skill tree") from exc
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise SkillTreeError(f"{skill_md} has invalid YAML frontmatter: {exc}") from exc
    if not isinstance(data, dict):
        raise SkillTreeError(f"{skill_md} frontmatter must be a YAML mapping")
    return data


_ALLOWED_FIELDS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def validate_agent_skill(tree: Path, expected_name: str) -> None:
    """Offline equivalent of ``skills-ref validate`` (Agent Skills spec, skills-ref 0.1.1).

    CI additionally runs the real ``skills-ref`` against every built tree, so
    this in-build check can never be the only line of defense against drift.
    """
    tree = Path(tree)
    skill_md = tree / "SKILL.md"
    if not skill_md.is_file():
        raise SkillTreeError(f"{tree}: missing required file SKILL.md")
    data = _frontmatter(skill_md)
    errors: list[str] = []
    extra = set(data) - _ALLOWED_FIELDS
    if extra:
        errors.append(
            f"unexpected frontmatter fields: {', '.join(sorted(extra))} "
            f"(allowed: {sorted(_ALLOWED_FIELDS)})"
        )
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("field 'name' must be a non-empty string")
    else:
        name = unicodedata.normalize("NFKC", name.strip())
        if len(name) > 64:
            errors.append(f"name {name!r} exceeds 64 characters")
        if name != name.lower():
            errors.append(f"name {name!r} must be lowercase")
        if name.startswith("-") or name.endswith("-") or "--" in name:
            errors.append("name cannot start/end with a hyphen or contain consecutive hyphens")
        if not all(c.isalnum() or c == "-" for c in name):
            errors.append(f"name {name!r} may contain only letters, digits, and hyphens")
        if unicodedata.normalize("NFKC", tree.name) != name:
            errors.append(f"directory name {tree.name!r} must match skill name {name!r}")
        if name != expected_name:
            errors.append(f"name {name!r} does not match the expected Skill {expected_name!r}")
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("field 'description' must be a non-empty string")
    elif len(description) > 1024:
        errors.append(f"description exceeds 1024 characters ({len(description)})")
    compatibility = data.get("compatibility")
    if "compatibility" in data and (not isinstance(compatibility, str) or len(compatibility) > 500):
        errors.append("field 'compatibility' must be a string of at most 500 characters")
    metadata = data.get("metadata")
    if "metadata" in data and (
        not isinstance(metadata, dict) or not all(isinstance(v, str) for v in metadata.values())
    ):
        errors.append("field 'metadata' must be a mapping of string values")
    if errors:
        raise SkillTreeError(f"{tree} fails Agent Skills validation: " + "; ".join(errors))


def check_tree_self_contained(tree: Path) -> None:
    """Every relative Markdown link resolves inside the tree; nothing reaches for ``../../shared``."""
    tree = Path(tree).resolve()
    problems: list[str] = []
    for md_file in sorted(tree.rglob("*.md")):
        rel = md_file.relative_to(tree).as_posix()
        for line_no, line in enumerate(md_file.read_text(encoding="utf-8").splitlines(), start=1):
            if _SHARED_ESCAPE.search(line):
                problems.append(f"{rel}:{line_no}: unadapted ../../shared reference")
            for link in _MARKDOWN_LINK.findall(line):
                if link.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = link.split("#", 1)[0]
                if not target:
                    continue
                resolved = (md_file.parent / target).resolve()
                try:
                    resolved.relative_to(tree)
                except ValueError:
                    problems.append(f"{rel}:{line_no}: link {link!r} escapes the Skill tree")
                    continue
                if not resolved.exists():
                    problems.append(f"{rel}:{line_no}: link {link!r} does not resolve inside the tree")
    if problems:
        raise SkillTreeError(f"{tree.name} is not self-contained:\n  " + "\n  ".join(problems))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(files: dict[str, str]) -> str:
    """Aggregate hash: SHA-256 over sorted ``<sha256>  <path>\\n`` lines (sha256sum layout)."""
    lines = "".join(f"{digest}  {path}\n" for path, digest in sorted(files.items()))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def tree_files(tree: Path) -> dict[str, str]:
    tree = Path(tree)
    return {p.relative_to(tree).as_posix(): _sha256(p) for p in _files(tree)}


def write_tree_manifest(dist_dir: Path, names: list[str]) -> Path:
    """Write ``dist/skills-manifest.json`` covering exactly the named ``dist/skills/<name>/`` trees.

    The caller names the Skills built in this run, so a stale tree from an
    earlier build (or a stray directory) is never described.
    """
    dist_dir = Path(dist_dir)
    skills: dict[str, dict] = {}
    for name in sorted(set(names)):
        tree = dist_dir / "skills" / name
        if not tree.is_dir():
            raise SkillTreeError(f"cannot write the manifest: no built tree at {tree}")
        files = tree_files(tree)
        skills[name] = {"tree_hash": tree_hash(files), "files": files}
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "algorithm": "sha256",
        "tree_hash": "sha256 over sorted '<file sha256>  <relative path>\\n' lines",
        "skills": skills,
    }
    path = dist_dir / MANIFEST_NAME
    path.write_bytes((json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return path


def build_archive(tree: Path, archive: Path) -> None:
    """Zip the tree's contents at the archive root: sorted, fixed timestamps, normalized modes."""
    tree, archive = Path(tree), Path(archive)
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in _files(tree):
            info = zipfile.ZipInfo(path.relative_to(tree).as_posix(), date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # Unix, whichever platform builds it
            info.external_attr = (stat.S_IFREG | _FILE_MODE) << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def verify_archive(tree: Path, archive: Path) -> None:
    """The archive's extracted contents equal the tree byte for byte (same paths, same bytes)."""
    tree, archive = Path(tree), Path(archive)
    expected = {p.relative_to(tree).as_posix(): p.read_bytes() for p in _files(tree)}
    with zipfile.ZipFile(archive) as zf:
        found = {i.filename: zf.read(i) for i in zf.infolist() if not i.is_dir()}
        bad = zf.testzip()
    if bad is not None:
        raise SkillTreeError(f"{archive}: corrupt member {bad}")
    if found != expected:
        missing = sorted(set(expected) - set(found))
        extra = sorted(set(found) - set(expected))
        differ = sorted(k for k in set(expected) & set(found) if expected[k] != found[k])
        raise SkillTreeError(
            f"{archive} does not equal {tree}: missing={missing} extra={extra} differ={differ}"
        )
