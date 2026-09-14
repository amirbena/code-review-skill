"""Disposable, symlink-sanitized copy of the reviewed work copy.

The sandboxed process never opens ``source_dir`` directly; it only ever
sees this ephemeral copy, so "reviewed source unchanged" is true by
construction and re-verified defensively after teardown.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

_IGNORED_DIR_NAMES = {".git"}


def fingerprint(directory: Path) -> str:
    """Cheap recursive content/metadata digest used as a tamper check."""
    digest = hashlib.sha256()
    for root, dirs, files in os.walk(directory):
        dirs.sort()
        dirs[:] = [d for d in dirs if d not in _IGNORED_DIR_NAMES]
        for name in sorted(files):
            path = Path(root) / name
            rel = path.relative_to(directory)
            digest.update(str(rel).encode("utf-8", "surrogateescape"))
            try:
                st = path.lstat()
            except OSError:
                continue
            digest.update(str(st.st_size).encode())
            digest.update(str(int(st.st_mtime)).encode())
    return digest.hexdigest()


def _copy_tree_sanitized(src: Path, dst: Path) -> None:
    """Copy ``src`` into ``dst``, refusing any symlink that escapes ``src``."""
    src = src.resolve()
    dst.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src, topdown=True, followlinks=False):
        dirs[:] = [d for d in dirs if d not in _IGNORED_DIR_NAMES]
        rel_root = Path(root).relative_to(src)
        dst_root = dst / rel_root
        dst_root.mkdir(parents=True, exist_ok=True)
        for name in dirs:
            entry = Path(root) / name
            if entry.is_symlink():
                _copy_symlink_if_contained(entry, src, dst_root / name)
                dirs.remove(name)
        for name in files:
            entry = Path(root) / name
            dst_entry = dst_root / name
            if entry.is_symlink():
                _copy_symlink_if_contained(entry, src, dst_entry)
                continue
            try:
                shutil.copy2(entry, dst_entry, follow_symlinks=False)
            except OSError:
                continue


def _copy_symlink_if_contained(entry: Path, boundary: Path, dst_entry: Path) -> None:
    """Preserve a symlink only if its resolved target stays inside ``boundary``.

    An escaping symlink (absolute, or ``..``-relative outside the tree) is
    replaced with an inert placeholder rather than followed or copied —
    it must never become a route to host content outside the work copy.
    """
    target_real = os.path.realpath(entry)
    try:
        contained = os.path.commonpath([boundary, target_real]) == str(boundary)
    except ValueError:
        contained = False
    if contained and os.path.exists(target_real):
        link_target = os.readlink(entry)
        os.symlink(link_target, dst_entry)
    else:
        dst_entry.write_text("")


@dataclass
class SandboxWorkspace:
    root: Path
    work_copy: Path
    source_fingerprint: str

    def teardown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def prepare_workspace(source_dir: Path) -> SandboxWorkspace:
    source_dir = Path(source_dir).resolve()
    root = Path(tempfile.mkdtemp(prefix="crs-sandbox-"))
    work_copy = root / "workcopy"
    fp = fingerprint(source_dir)
    _copy_tree_sanitized(source_dir, work_copy)
    # Ephemeral, writable fake HOME: tools that consult $HOME find nothing.
    (root / "home").mkdir(parents=True, exist_ok=True)
    os.chmod(root, stat.S_IRWXU)
    return SandboxWorkspace(root=root, work_copy=work_copy, source_fingerprint=fp)


def verify_source_unchanged(source_dir: Path, fingerprint_before: str) -> bool:
    return fingerprint(Path(source_dir).resolve()) == fingerprint_before
