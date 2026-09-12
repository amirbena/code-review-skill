#!/usr/bin/env python3
"""Test-only reference for the staged-delta fingerprint, plus a thin
git-invoking helper.

Mirrors skills/local-code-review/policies/repository-state.md,
"Staged delta fingerprint". Not runtime logic, not packaged.
"""

from __future__ import annotations

import hashlib
import subprocess
from typing import Optional, Sequence

# Exact command — every flag is load-bearing (see repository-state.md,
# "Staged delta fingerprint"). Do not substitute an equivalent.
STAGED_FINGERPRINT_COMMAND: Sequence[str] = ("git", "diff", "--cached", "--raw", "-M", "-z")


def compute_staged_fingerprint(raw_diff_bytes: bytes) -> str:
    """SHA-256 of the command's exact raw stdout bytes.

    Pass the bytes unmodified — no decode/re-encode, no NUL→newline
    conversion; any transform changes what the fingerprint represents.
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
