"""Canonical-home registry checks (issue #80).

``canonical_homes.json`` declares each registered normative anchor and the
one file that owns it. ``violations`` reports every drift; the contract and
the reason vocabulary live in ``docs/canonical-homes/canonical-homes-model.md``.
"""

from __future__ import annotations

import fnmatch
import importlib
import json
import os
import re
from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).resolve().with_name("canonical_homes.json")
GROUPS = ("routed-policy", "github-index-owned", "exact-string")
# Directories and the registry itself are never scanned for restatements.
SKIPPED_DIRS = {".git", "dist", "node_modules", "__pycache__", ".claude"}
SKIPPED_TOP_LEVEL = {"tests"}
SKIPPED_FILES = {"scripts/governance/canonical_homes.json"}


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text: str) -> str:
    """Strip blockquote markers, emphasis and code ticks; collapse whitespace."""
    lines = (re.sub(r"^\s*>\s?", "", line) for line in text.splitlines())
    return re.sub(r"\s+", " ", "\n".join(lines).replace("**", "").replace("`", ""))


def anchors_in_group(registry: dict, group: str) -> list[dict]:
    return [a for a in registry["anchors"] if a["group"] == group]


def _text_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        if rel_dir == Path("."):
            dirnames[:] = [d for d in dirnames if d not in SKIPPED_TOP_LEVEL]
        dirnames[:] = [d for d in dirnames if d not in SKIPPED_DIRS]
        for name in filenames:
            rel = (rel_dir / name).as_posix()
            if rel in SKIPPED_FILES:
                continue
            yield rel


def _read(root: Path, rel: str) -> str | None:
    try:
        return normalize((root / rel).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def _in_scope(rel: str, scope: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(rel, pattern) for pattern in scope)


def violations(registry: dict, root: Path) -> list[str]:
    problems: list[str] = []
    reasons = set(registry["reasons"])
    seen_ids: set[str] = set()
    corpus: dict[str, str] | None = None
    for anchor in registry["anchors"]:
        aid, text, owner = anchor["id"], normalize(anchor["text"]), anchor["owner"]
        if aid in seen_ids:
            problems.append(f"{aid}: duplicate anchor id")
        seen_ids.add(aid)
        if anchor["group"] not in GROUPS:
            problems.append(f"{aid}: unknown group {anchor['group']!r}")
        owner_text = _read(root, owner)
        if owner_text is None or text not in owner_text:
            problems.append(f"{aid}: owner {owner} does not contain the anchor")
        allowed = {entry["path"]: entry["reason"] for entry in anchor["allow"]}
        for path, reason in allowed.items():
            if reason not in reasons:
                problems.append(f"{aid}: allowlist entry {path} uses unknown reason {reason!r}")
            if path == owner:
                problems.append(f"{aid}: the owner {owner} must not be allowlisted")
            body = _read(root, path)
            if body is None or text not in body:
                problems.append(f"{aid}: stale allowlist entry {path} no longer contains the anchor")
        if corpus is None:
            corpus = {rel: body for rel in _text_files(root) if (body := _read(root, rel)) is not None}
        for rel, body in corpus.items():
            if rel == owner or rel in allowed or not _in_scope(rel, anchor["scope"]):
                continue
            if text in body:
                problems.append(f"{aid}: restated outside its owner {owner}: {rel}")
    return problems


def capability_double_claims(root: Path) -> dict[str, list[str]]:
    claims: dict[str, list[str]] = {}
    for manifest in sorted((root / "capabilities").glob("*/capability.yaml")):
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        for path in data.get("files", []):
            claims.setdefault(path, []).append(manifest.parent.name)
    return {path: owners for path, owners in claims.items() if len(owners) > 1}


def parity_violations(registry: dict) -> list[str]:
    """Check each anchor's optional code-constant mirror, which the text scan cannot see."""
    problems: list[str] = []
    for anchor in registry["anchors"]:
        parity = anchor.get("parity")
        if not parity:
            continue
        value = getattr(importlib.import_module(parity["module"]), parity["constant"], None)
        if not isinstance(value, str) or normalize(value) != normalize(anchor["text"]):
            problems.append(f"{anchor['id']}: {parity['module']}.{parity['constant']} drifted from the anchor")
    return problems
