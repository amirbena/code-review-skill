"""Rewrite relative links and metadata paths for a staged, standalone
packaged Skill.

Packaging strips exactly two path segments (``skills/<name>/``) when
staging a Skill at the archive root, so:

- every ``../../shared/`` (used at source depth 2, e.g. by ``SKILL.md``)
  becomes ``shared/``;
- every ``../../../shared/`` (used one level deeper, e.g. by
  ``runbooks/``, ``templates/``, ``policies/`` files) becomes
  ``../shared/``.

This is a narrow, deterministic substitution scoped to the exact link
prefixes that point into ``shared/`` — it never touches any other text.

``metadata/skill.yaml`` stays source-relative in the repository; only its
known shared-resource list-entry prefix is adapted in the staged copy,
where ``metadata/`` sits one level below the standalone package root.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

_METADATA_SHARED_PREFIX = re.compile(r"^([ \t]*- [ \t]*)\.\./\.\./\.\./shared/", re.MULTILINE)


def adapt_shared_links(text: str) -> str:
    text = text.replace("../../../shared/", "../shared/")
    text = text.replace("../../shared/", "shared/")
    return text


def adapt_metadata_paths(text: str) -> str:
    return _METADATA_SHARED_PREFIX.sub(r"\1../shared/", text)


def _write_atomic(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via write-to-temp-then-replace, so a
    reader never observes a partially written file."""
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        os.unlink(tmp_name)
        raise


def adapt_shared_links_file(path: Path) -> None:
    _write_atomic(path, adapt_shared_links(path.read_text(encoding="utf-8")))


def adapt_metadata_paths_file(path: Path) -> None:
    _write_atomic(path, adapt_metadata_paths(path.read_text(encoding="utf-8")))
