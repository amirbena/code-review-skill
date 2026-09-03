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
    "human_review_output": "human review output",
}

# Small, fixed phrase vocabularies for options that are normally requested
# conversationally rather than by name. Mirrors
# shared/policies/invocation-options.md, "`human_review_output` phrasings" —
# keep the two in exact sync.
OPTION_EXTRA_AFFIRMATIVE: dict[str, tuple[str, ...]] = {
    "human_review_output": (
        "shorter and more human",
        "more human and shorter",
        "like a senior engineer",
        "as a senior engineer",
        "concise review comments",
        "concise review comment",
    ),
}
OPTION_EXTRA_NEGATIVE: dict[str, tuple[str, ...]] = {
    "human_review_output": (
        "keep the full summary",
        "keep the default summary",
        "do not shorten the review",
        "don't shorten the review",
    ),
}


def _phrase_regex(phrase: str) -> str:
    """A whitespace-flexible, word-bounded matcher for a fixed phrase."""
    return r"(?<![\w])" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"(?![\w])"


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
    ) + tuple(_phrase_regex(p) for p in OPTION_EXTRA_AFFIRMATIVE.get(option, ()))
    negative = (
        rf"\bdo not (?:include|show|give me)(?: a| the)? {re.escape(concept)}\b",
        rf"\b(?:no|hide) {re.escape(concept)}\b",
    ) + tuple(_phrase_regex(p) for p in OPTION_EXTRA_NEGATIVE.get(option, ()))
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
