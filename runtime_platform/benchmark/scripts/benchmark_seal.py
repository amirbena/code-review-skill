#!/usr/bin/env python3
"""The seal: the execution side's only GitHub-adjacent operation.

Contract: `runtime_platform/benchmark/scheduled-operations/execution-publication-boundary.md` §4.
Pushes one orphan commit to a `claude/` ref through the checkout's own git remote, so the
provider mediates the write; no GitHub API, `gh`, or token is used here.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

CONFINED_REF_PREFIX = "claude/"
STAGING_REF_PREFIX = "claude/benchmark-result-"
HANDOFF_CHECK_REF_PREFIX = "claude/benchmark-handoff-check-"
RECORD_FILE = "benchmark-result.json"
RAW_FILE = "raw-bundle.json"
HANDOFF_CHECK_FILE = "handoff-check.json"

GIT_TIMEOUT_S = 120

_COMMIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "benchmark-execution",
    "GIT_AUTHOR_EMAIL": "benchmark-execution@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "benchmark-execution",
    "GIT_COMMITTER_EMAIL": "benchmark-execution@users.noreply.github.com",
}


class SealError(RuntimeError):
    """The handoff was not written; the run stays unsealed and leaves no record."""


def staging_ref(run_id: str) -> str:
    return f"{STAGING_REF_PREFIX}{run_id}"


def encode_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _git(repo_root: Path, *args: str, stdin: bytes | None = None, env: Mapping[str, str] | None = None) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            input=stdin,
            capture_output=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})},
            timeout=GIT_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise SealError(f"git {' '.join(args)} timed out after {GIT_TIMEOUT_S}s") from exc
    if proc.returncode != 0:
        raise SealError(f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout.decode("utf-8").strip()


def seal_to_ref(repo_root: Path, remote: str, ref: str, files: Mapping[str, bytes], message: str) -> str:
    """Create `refs/heads/<ref>` on `remote` as an orphan commit of `files`; return its sha.

    A plain push (never forced) and a read-back of the remote ref: an existing ref or an
    unconfirmed push leaves the run unsealed.
    """
    if not ref.startswith(CONFINED_REF_PREFIX):
        raise SealError(f"refusing to write {ref!r}: the seal is confined to {CONFINED_REF_PREFIX} refs")
    entries = []
    for name, content in sorted(files.items()):
        blob = _git(repo_root, "hash-object", "-w", "--stdin", stdin=content)
        entries.append(f"100644 blob {blob}\t{name}\n")
    tree = _git(repo_root, "mktree", stdin="".join(entries).encode("utf-8"))
    commit = _git(repo_root, "commit-tree", tree, "-m", message, env=_COMMIT_IDENTITY)
    _git(repo_root, "push", remote, f"{commit}:refs/heads/{ref}")
    remote_tip = _git(repo_root, "ls-remote", remote, f"refs/heads/{ref}").split()
    if not remote_tip or remote_tip[0] != commit:
        raise SealError(f"{remote} does not hold {ref} at {commit} after the push")
    return commit


def seal_to_directory(directory: Path, files: Mapping[str, bytes], commit_file: str) -> Path:
    """Local dry-run seal: write `files` with `commit_file` last, as it is the commit point."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in sorted(files, key=lambda n: n == commit_file):
        (directory / name).write_bytes(files[name])
    return directory
