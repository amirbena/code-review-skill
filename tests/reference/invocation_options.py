#!/usr/bin/env python3
"""Test-only model for shared invocation-option normalization.

Mirrors shared/policies/invocation-options.md; not runtime logic, not packaged.
"""

from __future__ import annotations

import re
from typing import Mapping


OPTION_CONCEPTS = {
    "include_fix_prompt": "fix prompt",
    "include_fix_guidance": "fix guidance",
    "include_finding_details": "finding details",
}


def _canonical_values(text: str, option: str) -> set[bool]:
    pattern = rf"(?<![\w]){re.escape(option)}\s*=\s*(true|false)(?![\w])"
    return {match == "true" for match in re.findall(pattern, text.lower())}


def _natural_values(text: str, option: str) -> set[bool]:
    lowered = text.lower()
    concept = OPTION_CONCEPTS[option]
    spaced = option.replace("_", " ")
    hyphenated = option.replace("_", "-")
    question = re.compile(
        rf"\b(?:what|how|why|does|is)\b[^?]*\b(?:{re.escape(option)}|"
        rf"{re.escape(spaced)}|{re.escape(hyphenated)})\b[^?]*\?"
    )
    lowered = question.sub("", lowered)
    values: set[bool] = set()
    positive = (
        rf"(?<![\w]){re.escape(option)}(?![\w=])",
        rf"(?<![\w]){re.escape(spaced)}(?![\w])",
        rf"(?<![\w]){re.escape(hyphenated)}(?![\w])",
        rf"\b(?:include|show|give me)(?: a| the)? {re.escape(concept)}\b",
    )
    negative = (
        rf"\bdo not (?:include|show|give me)(?: a| the)? {re.escape(concept)}\b",
        rf"\b(?:no|hide) {re.escape(concept)}\b",
    )
    negative_match = any(re.search(p, lowered) for p in negative)
    if negative_match:
        values.add(False)
    without_negative = lowered
    for pattern in negative:
        without_negative = re.sub(pattern, "", without_negative)
    if any(re.search(p, without_negative) for p in positive):
        values.add(True)
    return values


def normalize(text: str, *, defaults: Mapping[str, bool]) -> dict[str, bool]:
    """Normalize one invocation independently with canonical precedence."""
    result = dict(defaults)
    for option in OPTION_CONCEPTS:
        canonical = _canonical_values(text, option)
        if False in canonical:
            result[option] = False
        elif True in canonical:
            result[option] = True
        else:
            natural = _natural_values(text, option)
            if len(natural) == 1:
                result[option] = natural.pop()
    return result
