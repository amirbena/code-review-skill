"""Rebuild, verify, and replace a published release's Skill archives from its tag (issue #497)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable, Sequence

from release_lib.semver_version import validate_semver
from release_lib.skill_version import archive_skill_version, skill_targets, stamp_skill_versions, verify_archive_versions

_PACKAGING = str(Path(__file__).resolve().parents[2] / "packaging")
if _PACKAGING not in sys.path:
    sys.path.insert(0, _PACKAGING)

from package_domain.version import newest_release_version, stamp_frontmatter_version  # noqa: E402

_TAG_RE = re.compile(r"^v((?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*))$")
RECONSTRUCT_FILE = "reconstruct.json"
VERIFY_FILE = "verify.json"
REPLACE_FILE = "replace.json"


class RepairError(RuntimeError):
    """A phase cannot proceed; nothing published was modified."""


def _run(argv: Sequence[str], cwd: Path, *, stdin: bytes | None = None, env: dict[str, str] | None = None) -> bytes:
    result = subprocess.run(list(argv), cwd=cwd, input=stdin, capture_output=True, env=env)
    if result.returncode != 0:
        raise RepairError(f"{' '.join(argv[:3])} failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout


def release_version_from_tag(tag: str) -> str:
    match = _TAG_RE.match(tag)
    if not match:
        raise RepairError(f"{tag!r} is not a vX.Y.Z release tag")
    validate_semver(match.group(1))
    return match.group(1)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare_archives(published: Path, rebuilt: Path, version: str) -> tuple[bool, list[str]]:
    """(inventory matches, differing entries); the only allowed difference is SKILL.md's version line."""
    with zipfile.ZipFile(published) as old, zipfile.ZipFile(rebuilt) as new:
        old_names, new_names = sorted(old.namelist()), sorted(new.namelist())
        if old_names != new_names:
            return False, sorted(set(old_names) ^ set(new_names))
        differing = []
        for name in new_names:
            expected = old.read(name)
            if name == "SKILL.md":
                expected = stamp_frontmatter_version(expected.decode("utf-8"), version).encode("utf-8")
            if expected != new.read(name):
                differing.append(name)
    return True, differing


def reconstruct(repo_root: Path, tag: str, work_dir: Path) -> dict:
    """Build both archives from the exact tag with only the release version stamped; never touches a Release."""
    version = release_version_from_tag(tag)
    commit = _run(["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"], repo_root).decode().strip()
    tag_dir = work_dir / tag
    tree = tag_dir / "tree"
    if tag_dir.exists():
        shutil.rmtree(tag_dir)
    tree.mkdir(parents=True)
    _run(["tar", "-x", "-C", str(tree)], repo_root, stdin=_run(["git", "archive", "--format=tar", commit], repo_root))

    changelog_version = newest_release_version((tree / "CHANGELOG.md").read_text(encoding="utf-8"))
    if changelog_version != version:
        raise RepairError(f"{tag}: CHANGELOG.md's newest release heading is {changelog_version!r}, expected {version!r}")
    stamp_skill_versions(tree, version)
    _run(["bash", str(tree / "scripts" / "packaging" / "package-skills.sh"), "all"], tree,
         env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    problems = verify_archive_versions(tree, tree / "dist", version)
    if problems:
        raise RepairError(f"{tag}: " + "; ".join(problems))

    rebuilt = tag_dir / "rebuilt"
    rebuilt.mkdir()
    for _name, archive in skill_targets(tree):
        shutil.copy2(tree / "dist" / archive, rebuilt / archive)
    record = {
        "tag": tag,
        "commit": commit,
        "expected_version": version,
        "archives": {archive: sha256_of(rebuilt / archive) for _name, archive in skill_targets(tree)},
    }
    (tag_dir / RECONSTRUCT_FILE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(tree)
    return record


def _load(work_dir: Path, tag: str, name: str) -> dict:
    path = work_dir / tag / name
    if not path.is_file():
        raise RepairError(f"{path} is missing; run the previous phase for {tag} first")
    return json.loads(path.read_text(encoding="utf-8"))


def published_digests(repo_root: Path, tag: str) -> dict[str, str]:
    out = _run(["gh", "release", "view", tag, "--json", "assets"], repo_root)
    return {asset["name"]: str(asset.get("digest") or "").removeprefix("sha256:") for asset in json.loads(out)["assets"]}


def download_published(repo_root: Path, tag: str, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    _run(["gh", "release", "download", tag, "--pattern", "*.zip", "--dir", str(dest)], repo_root)


def _check_published_copy(archive: Path, rebuilt: Path, version: str) -> dict:
    inventory_ok, differing = compare_archives(archive, rebuilt, version)
    return {"version": archive_skill_version(archive), "inventory_match": inventory_ok, "differences": differing}


def verify(repo_root: Path, tag: str, work_dir: Path) -> dict:
    """Compare each rebuilt archive with its published asset, independently per Skill; read-only."""
    record = _load(work_dir, tag, RECONSTRUCT_FILE)
    version = record["expected_version"]
    published_dir = work_dir / tag / "published"
    download_published(repo_root, tag, published_dir)
    digests = published_digests(repo_root, tag)
    results = {}
    for archive, rebuilt_sha in record["archives"].items():
        rebuilt = work_dir / tag / "rebuilt" / archive
        published = published_dir / archive
        problems: list[str] = []
        entry = {
            "tag": tag,
            "commit": record["commit"],
            "expected_version": version,
            "rebuilt_sha256": rebuilt_sha,
            "rebuilt_version": archive_skill_version(rebuilt),
        }
        if sha256_of(rebuilt) != rebuilt_sha:
            problems.append("rebuilt archive changed since reconstruction")
        if entry["rebuilt_version"] != version:
            problems.append(f"rebuilt SKILL.md version is {entry['rebuilt_version']!r}")
        if not published.is_file():
            problems.append("published asset is missing")
        else:
            entry["published_sha256"] = sha256_of(published)
            entry["published_size"] = published.stat().st_size
            if digests.get(archive) and digests[archive] != entry["published_sha256"]:
                problems.append("downloaded asset does not match the digest GitHub reports")
            copy = _check_published_copy(published, rebuilt, version)
            entry.update(published_version=copy["version"], inventory_match=copy["inventory_match"],
                         content_differences=copy["differences"])
            if not copy["inventory_match"]:
                problems.append(f"file inventory differs from the published package: {copy['differences']}")
            elif copy["differences"]:
                problems.append(f"content differs beyond the version line: {copy['differences']}")
        entry.update(problems=problems, passed=not problems)
        results[archive] = entry
    (work_dir / tag / VERIFY_FILE).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


def replace(
    repo_root: Path,
    tag: str,
    work_dir: Path,
    *,
    upload: Callable[[Path, str, Path], None] | None = None,
) -> dict:
    """Upload each archive that passed `verify` over its published asset, then re-check the published copy."""
    upload = upload or _upload_asset
    verified = _load(work_dir, tag, VERIFY_FILE)
    digests = published_digests(repo_root, tag)
    results = {}
    for archive, entry in verified.items():
        outcome = {"archive": archive, "replaced_sha256": entry.get("published_sha256"), "replaced": False}
        results[archive] = outcome
        if not entry["passed"]:
            outcome["skipped"] = "verification failed; published asset left untouched"
        elif digests.get(archive) != entry["published_sha256"]:
            outcome["skipped"] = "published asset changed since verification; re-run verify"
        else:
            upload(repo_root, tag, work_dir / tag / "rebuilt" / archive)
            outcome["replaced"] = True
    if any(outcome["replaced"] for outcome in results.values()):
        after_dir = work_dir / tag / "replaced"
        download_published(repo_root, tag, after_dir)
        for archive, outcome in results.items():
            if not outcome["replaced"]:
                continue
            rebuilt = work_dir / tag / "rebuilt" / archive
            copy = _check_published_copy(after_dir / archive, rebuilt, verified[archive]["expected_version"])
            outcome.update(published_version=copy["version"], inventory_match=copy["inventory_match"],
                           published_sha256=sha256_of(after_dir / archive))
            outcome["post_replace_ok"] = (
                copy["version"] == verified[archive]["expected_version"]
                and copy["inventory_match"]
                and outcome["published_sha256"] == verified[archive]["rebuilt_sha256"]
            )
    (work_dir / tag / REPLACE_FILE).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return results


def _upload_asset(repo_root: Path, tag: str, archive: Path) -> None:
    _run(["gh", "release", "upload", tag, str(archive), "--clobber"], repo_root)


def phase_ok(results: dict) -> bool:
    return all(
        entry.get("passed", entry.get("post_replace_ok", False)) for entry in results.values()
    )
