#!/usr/bin/env python3
"""Test-only reference for stable finding identity (Issue #60).

Mirrors docs/findings/finding-stable-identity.md: the canonical construction of the
descriptor primitives and the minted stable identity digest.
Not runtime logic, not packaged — the packaged Skills are Markdown/YAML only.

Matching (#59) and lifecycle (#62) are deliberately not modelled here; the
only #59 touch-point is ``effective_identity``'s hand-off argument.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union

IDENTITY_SCHEME = "v1"
CONTEXT_TOKEN_CAP = 64

# Cause -> faulty-behavior connectives, tried left to right (§3.2 cause_key).
CAUSE_BEHAVIOR_CONNECTIVES = (
    " so ",
    " causing ",
    " resulting in ",
    " leads to ",
    " which causes ",
    " therefore ",
    " -> ",
    " → ",
)

LOCATION_INTENTS = ("line", "symbol", "file", "cross_file", "repository")
CONSTRUCT_KINDS = (
    "statement",
    "declaration",
    "call",
    "expression",
    "config_key",
    "section",
    "block",
)

# The descriptor fields hashed into the minted identity, in order (§6.1).
# `cause_key` / `behavior_key` are included: a reworded claim that changes
# their normalized tokens re-mints (a false split, the safe direction per
# #58 §6), and a definite #59 MATCH re-propagates. `defect_kind` is a
# free-form slug of reviewer wording and is *not* a stable hash discriminator,
# so it is excluded here (still built for #59).
DISCRIMINATING_FIELDS = (
    "repository",
    "location_intent",
    "path",
    "symbol",
    "construct",
    "anchor_tokens",
    "mechanism_key",
    "cause_key",
    "behavior_key",
)

# Classified semantic fields that distinguish two findings beyond
# repository / path / anchor. A descriptor with none of these is not
# eligible for automatic matching (§7).
STRONG_SEMANTIC_FIELDS = ("symbol", "mechanism_key", "cause_key", "behavior_key")


class Sentinel(Enum):
    """§4: absent vs. unclassifiable — distinct, never wildcards."""

    ABSENT = "absent"
    UNCLASSIFIABLE = "unclassifiable"


ABSENT = Sentinel.ABSENT
UNCLASSIFIABLE = Sentinel.UNCLASSIFIABLE

Tokens = tuple[str, ...]
MaybeStr = Union[str, Sentinel]
MaybeTokens = Union[Tokens, Sentinel]

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_TOKEN = re.compile(
    r"""
    [A-Za-z_][A-Za-z0-9_]*        # identifier / keyword
    | \d+(?:\.\d+)?               # numeric literal
    | "[^"]*" | '[^']*'           # quoted string literal, verbatim
    | [-+*/%=!<>&|^~.]+           # operator run
    | [()\[\]{}]                  # single bracket
    """,
    re.X,
)


def _strip_comments(text: str) -> str:
    """Remove ``/* */`` and ``#``-to-end-of-line comments that are *outside*
    string literals. `//` is left intact — it is ambiguous with floor
    division and other operator runs, and an anchor fragment (the smallest
    defect-demonstrating snippet) rarely carries a trailing line comment.
    An unterminated quote consumes the rest of the fragment (conservative)."""
    out: list[str] = []
    i, n, quote = 0, len(text), ""
    while i < n:
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
        elif ch == "#":
            while i < n and text[i] != "\n":
                i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            out.append(" ")
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def normalize_tokens(fragment: Optional[str]) -> Tokens:
    """§3.1: the one tokenizer shared by every token-valued primitive."""
    if not fragment:
        return ()
    text = _CONTROL.sub(" ", _strip_comments(fragment))
    return tuple(_TOKEN.findall(text))


def location_intent(raw: Optional[str], explicit: Optional[str] = None) -> MaybeStr:
    """§3.2: an explicit keyword wins; otherwise infer from the location shape."""
    if explicit is not None:
        value = explicit.strip().lower()
        return value if value in LOCATION_INTENTS else UNCLASSIFIABLE
    value = (raw or "").strip()
    if value.lower() in LOCATION_INTENTS:
        return value.lower()
    if re.search(r"[^\s:]:\d+(?:-\d+)?$", value):
        return "line"
    if "/" in value or re.search(r"\.[A-Za-z0-9]{1,6}$", value):
        return "file"
    if re.fullmatch(r"[A-Za-z_][\w.]*", value) and "." in value:
        return "symbol"
    return UNCLASSIFIABLE


# Stable alias so build_descriptor can reach this after its own parameter of
# the same name shadows the module binding.
_resolve_location_intent = location_intent


def path_key(raw: Optional[str], intent: MaybeStr) -> MaybeStr:
    if intent in ("cross_file", "repository"):
        return ABSENT
    if not raw or not raw.strip():
        return ABSENT
    value = raw.strip().replace("\\", "/")
    value = re.sub(r"^\./", "", value)
    value = re.sub(r"^(?:[A-Za-z]:)?/+", "", value)  # strip absolute / drive prefix
    value = re.sub(r":\d+(?:-\d+)?$", "", value)  # strip a trailing :line or :start-end
    segments = [s for s in value.split("/") if s]
    if not segments or any(s in (".", "..") for s in segments):
        return ABSENT
    return "/".join(segments)


def symbol_key(raw: Optional[str]) -> MaybeStr:
    """Portable lexical qualified name only; a parser guess is not this field."""
    if not raw or not raw.strip():
        return ABSENT
    return re.sub(r"\s+", " ", raw.strip())


def construct_key(raw: Optional[str]) -> MaybeStr:
    value = (raw or "").strip().lower()
    return value if value in CONSTRUCT_KINDS else UNCLASSIFIABLE


def behavioral_claim(raw: Optional[str]) -> MaybeStr:
    if not raw or not raw.strip():
        return ABSENT
    return re.sub(r"\s+", " ", raw.strip()).casefold()


# A prose clause is trimmed of *trailing* whitespace and sentence
# punctuation so "twice." does not re-mint an identity (§6.1). The trim is
# trailing-only: a *leading* "!" is negation and must survive (a leading
# strip would merge a defect with its opposite — matching-strategy.md §2).
_CLAUSE_TRAIL = " \t\n\r.,;:!?"


def _trim_clause(clause: str) -> str:
    return clause.rstrip(_CLAUSE_TRAIL).lstrip(" \t\n\r")


def _split_claim(claim: MaybeStr) -> Optional[tuple[str, str]]:
    if isinstance(claim, Sentinel):
        return None
    for connective in CAUSE_BEHAVIOR_CONNECTIVES:
        idx = claim.find(connective)
        if idx != -1:
            head = _trim_clause(claim[:idx])
            tail = _trim_clause(claim[idx + len(connective) :])
            return head, tail
    return None


def cause_key(claim: MaybeStr) -> MaybeTokens:
    parts = _split_claim(claim)
    if parts is None or not parts[0]:
        return UNCLASSIFIABLE
    tokens = normalize_tokens(parts[0])
    return tokens or UNCLASSIFIABLE


def behavior_key(claim: MaybeStr) -> MaybeTokens:
    parts = _split_claim(claim)
    if parts is None or not parts[1]:
        return UNCLASSIFIABLE
    tokens = normalize_tokens(parts[1])
    return tokens or UNCLASSIFIABLE


def mechanism_key(fragment: Optional[str]) -> MaybeTokens:
    """§3.2: #60 only normalizes a reviewer-supplied fragment; no extraction."""
    tokens = normalize_tokens(fragment)
    return tokens or UNCLASSIFIABLE


def defect_kind(raw: Optional[str]) -> MaybeStr:
    slug = re.sub(r"[^a-z0-9]+", "_", (raw or "").casefold()).strip("_")
    return slug or UNCLASSIFIABLE


def _strip_anchor(context: Tokens, anchor: Tokens) -> Tokens:
    """Remove the longest contiguous run of ``context`` equal to ``anchor``."""
    if not anchor:
        return context
    for start in range(len(context) - len(anchor) + 1):
        if context[start : start + len(anchor)] == anchor:
            return context[:start] + context[start + len(anchor) :]
    return context


def context_tokens(sibling_source: Optional[str], anchor: Tokens) -> MaybeTokens:
    if not sibling_source or not sibling_source.strip():
        return ABSENT
    trimmed = _strip_anchor(normalize_tokens(sibling_source), anchor)
    return trimmed[:CONTEXT_TOKEN_CAP]


def neighboring_syntax(
    predecessor: Optional[str], successor: Optional[str]
) -> tuple[MaybeTokens, MaybeTokens]:
    pred = normalize_tokens(predecessor) if predecessor and predecessor.strip() else ABSENT
    succ = normalize_tokens(successor) if successor and successor.strip() else ABSENT
    return pred, succ


@dataclass(frozen=True)
class FindingDescriptor:
    repository: str
    location_intent: MaybeStr
    path: MaybeStr
    symbol: MaybeStr
    construct: MaybeStr
    anchor_tokens: Tokens
    mechanism_key: MaybeTokens
    cause_key: MaybeTokens
    behavior_key: MaybeTokens
    defect_kind: MaybeStr
    # Matching-only evidence — excluded from the minted identity (§6.1).
    context_tokens: MaybeTokens = ABSENT
    neighboring_syntax: tuple[MaybeTokens, MaybeTokens] = (ABSENT, ABSENT)
    behavioral_claim: MaybeStr = ABSENT
    # Optional parser refinement — diagnostics only, never hashed (§5).
    diagnostic_symbol: Optional[str] = field(default=None, compare=False)
    diagnostic_construct: Optional[str] = field(default=None, compare=False)


def build_descriptor(
    *,
    repository: str,
    location: Optional[str],
    location_intent: Optional[str] = None,
    path: Optional[str] = None,
    behavioral_claim_text: Optional[str] = None,
    anchor_fragment: Optional[str] = None,
    mechanism_fragment: Optional[str] = None,
    defect_kind_text: Optional[str] = None,
    symbol: Optional[str] = None,
    construct: Optional[str] = None,
    sibling_source: Optional[str] = None,
    predecessor_source: Optional[str] = None,
    successor_source: Optional[str] = None,
    diagnostic_symbol: Optional[str] = None,
    diagnostic_construct: Optional[str] = None,
    **_ignored: object,
) -> FindingDescriptor:
    """§3: deterministic descriptor construction.

    ``_ignored`` absorbs severity, display id, HEAD SHA, discovery order,
    etc. — accepted alongside real inputs and dropped (§5).
    """
    intent = _resolve_location_intent(location, explicit=location_intent)
    anchor = normalize_tokens(anchor_fragment)
    claim = behavioral_claim(behavioral_claim_text)
    # Explicit path wins; otherwise parse it from a line/file location string.
    path_source = path if path is not None else (location if intent in ("line", "file") else None)
    return FindingDescriptor(
        repository=(repository or "").strip(),
        location_intent=intent,
        path=path_key(path_source, intent),
        symbol=symbol_key(symbol),
        construct=construct_key(construct),
        anchor_tokens=anchor,
        mechanism_key=mechanism_key(mechanism_fragment),
        cause_key=cause_key(claim),
        behavior_key=behavior_key(claim),
        defect_kind=defect_kind(defect_kind_text),
        context_tokens=context_tokens(sibling_source, anchor),
        neighboring_syntax=neighboring_syntax(predecessor_source, successor_source),
        behavioral_claim=claim,
        diagnostic_symbol=diagnostic_symbol,
        diagnostic_construct=diagnostic_construct,
    )


def _encode(value: object) -> str:
    if value is ABSENT:
        return "\x00A"
    if value is UNCLASSIFIABLE:
        return "\x00U"
    if isinstance(value, tuple):
        return "\x1f".join([str(len(value)), *value])
    text = str(value)
    return f"{len(text)}\x1f{text}"


def canonical_serialization(descriptor: FindingDescriptor) -> str:
    """§6.2: unambiguous, length-delimited encoding of the hashed subset."""
    parts = [IDENTITY_SCHEME]
    for name in DISCRIMINATING_FIELDS:
        parts.append(f"{name}\x1d{_encode(getattr(descriptor, name))}")
    return "\x1e".join(parts)


def mint_identity(descriptor: FindingDescriptor) -> str:
    """§6.3: content-addressed identity for a finding with no known predecessor."""
    digest = hashlib.sha256(canonical_serialization(descriptor).encode("utf-8")).hexdigest()
    return f"fid_{IDENTITY_SCHEME}_{digest[:32]}"


def _has_strong_semantic_field(descriptor: FindingDescriptor) -> bool:
    """True when at least one classified field distinguishes this finding
    beyond repository / path / anchor (§7)."""
    return any(
        getattr(descriptor, name) not in (ABSENT, UNCLASSIFIABLE)
        for name in STRONG_SEMANTIC_FIELDS
    )


def is_matchable(descriptor: FindingDescriptor) -> bool:
    """§7: fail closed. A finding is not eligible for automatic matching when
    the repository is unresolvable, the location intent is unclassifiable,
    there is no source-backed discriminator, or its discrimination reduces to
    repository / path / ``anchor_tokens`` (and at most ``construct``) — no
    classified ``symbol`` / ``mechanism_key`` / ``cause_key`` / ``behavior_key``.
    A non-matchable finding still gets a deterministic minted identity."""
    if not descriptor.repository:
        return False
    if descriptor.location_intent is UNCLASSIFIABLE:
        return False
    if not descriptor.anchor_tokens and descriptor.mechanism_key is UNCLASSIFIABLE:
        return False
    if not _has_strong_semantic_field(descriptor):
        return False
    return True


def effective_identity(
    descriptor: FindingDescriptor,
    *,
    matched_prior_identity: Optional[str] = None,
) -> str:
    """§6.4: the #59 -> #60 hand-off.

    ``matched_prior_identity`` is set only for a definite #59 ``MATCH``;
    ``NO MATCH`` and ``AMBIGUOUS`` pass ``None`` and mint fresh. A prior
    identity is propagated only for a descriptor that is eligible for
    automatic matching (§7) — a non-matchable descriptor always mints fresh,
    so a caller cannot bypass fail-closed at the hand-off.
    """
    if matched_prior_identity is not None and is_matchable(descriptor):
        return matched_prior_identity
    return mint_identity(descriptor)
