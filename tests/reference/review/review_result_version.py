"""Test-only reference for the review result consumer version rules.

Contract: docs/review-result/schema-versioning.md, section 3. A consumer
supports one major version and reads up to a highest minor; anything it
cannot interpret fails closed.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

_VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


class VersionDecision(Enum):
    ACCEPT = "accept"
    ACCEPT_KNOWN_FIELDS_ONLY = "accept-known-fields-only"
    REJECT_INVALID = "reject-invalid"
    REJECT_UNSUPPORTED_MAJOR = "reject-unsupported-major"


def parse_version(value: Any) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = _VERSION.fullmatch(value)
    return tuple(int(part) for part in match.groups()) if match else None


def consumer_decision(
    document_version: Any, supported_major: int, supported_minor: int
) -> VersionDecision:
    parsed = parse_version(document_version)
    if parsed is None:
        return VersionDecision.REJECT_INVALID
    major, minor, _patch = parsed
    if major != supported_major:
        return VersionDecision.REJECT_UNSUPPORTED_MAJOR
    if minor > supported_minor:
        return VersionDecision.ACCEPT_KNOWN_FIELDS_ONLY
    return VersionDecision.ACCEPT
