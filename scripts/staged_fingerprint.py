#!/usr/bin/env python3
"""Reference implementation of the local-code-review staged-delta fingerprint.

Mirrors skills/local-code-review/policies/repository-state.md, "Staged
delta fingerprint". Pure hashing logic, plus a thin Git-invoking helper,
so test_staged_fingerprint.py can exercise it deterministically against
real `git diff --cached --raw -M -z` output. Not part of either packaged
Skill archive — the Skills reason from the canonical policy text
directly, not from this script.
"""

from __future__ import annotations

import hashlib
import subprocess
from typing import Optional, Sequence

# The exact, documented command. Do not substitute an equivalent-looking
# command (e.g. without -z, or with a text diff) — see
# repository-state.md, "Staged delta fingerprint," for why each flag is
# load-bearing.
STAGED_FINGERPRINT_COMMAND: Sequence[str] = ("git", "diff", "--cached", "--raw", "-M", "-z")


def compute_staged_fingerprint(raw_diff_bytes: bytes) -> str:
    """Return the SHA-256 hex digest of the exact raw bytes produced by
    STAGED_FINGERPRINT_COMMAND.

    The caller must pass the command's raw stdout bytes unmodified: do
    not decode/re-encode, strip or convert the NUL (`-z`) separators to
    newlines, or otherwise transform the output before hashing. Any such
    transform silently changes what the fingerprint represents.
    """
    if not isinstance(raw_diff_bytes, (bytes, bytearray)):
        raise TypeError(
            "raw_diff_bytes must be the exact raw bytes of "
            "`git diff --cached --raw -M -z` output, not a decoded string"
        )
    return hashlib.sha256(bytes(raw_diff_bytes)).hexdigest()


def run_staged_fingerprint(cwd: Optional[str] = None) -> str:
    """Run STAGED_FINGERPRINT_COMMAND in `cwd` and fingerprint its raw output."""
    result = subprocess.run(
        list(STAGED_FINGERPRINT_COMMAND),
        cwd=cwd,
        capture_output=True,
        check=True,
    )
    return compute_staged_fingerprint(result.stdout)
