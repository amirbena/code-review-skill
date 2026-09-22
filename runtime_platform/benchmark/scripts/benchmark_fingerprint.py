"""Drift fingerprint (Issue #339), a stdlib-only leaf so the publisher can check it without importing drift classification.

Contract: `runtime_platform/benchmark/drift-detection-and-regression-lifecycle.md` §3.
"""

from __future__ import annotations

import hashlib
import json


def fingerprint(case_id: str, drift_type: str, expected_finding_key: str) -> str:
    """Stable identity for a regression (contract §3): sha256 of the
    canonical `{case_id, drift_type, expected_finding_key}` triple, built
    from the fields directly so a caller's key ordering/whitespace never
    changes the result."""
    canonical = json.dumps(
        {
            "case_id": case_id,
            "drift_type": drift_type,
            "expected_finding_key": expected_finding_key,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
