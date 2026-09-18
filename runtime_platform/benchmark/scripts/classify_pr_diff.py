#!/usr/bin/env python3
"""PR-diff taxonomy classification (Issue #333). Contract:
runtime_platform/benchmark/taxonomy.md §4.

The one bounded, schema-constrained model call in the taxonomy/indexing
design: classify a PR's changed paths (and optionally a diff excerpt) into
``capability`` / ``policy_contract`` / ``risk_mode``. ``affected_surface``
is never asked of the model — it is derived deterministically from the
changed paths via ``benchmark_taxonomy.classify_affected_surfaces``.

This module owns the deterministic parts of that call: building a prompt
that states the closed enum (so the model is never asked to invent a
value), and turning its raw response into a taxonomy mapping via
``benchmark_taxonomy.sanitize_taxonomy_response`` — off-taxonomy output
never survives, it resolves to ``unclassified`` for that dimension. It
does *not* own how the model is actually invoked: that is a Class 2
(maintainer-controlled) runtime/credential concern owned by
runtime_platform/benchmark/runtime-execution-contract.md (#330), reused rather than
reimplemented here. ``classify_pr_diff`` takes the invocation as an
injected callable so this module has no subprocess/credential dependency
of its own and no automatic-trigger path.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Iterable

from runtime_platform.benchmark.reference import benchmark_taxonomy as tax

# The three dimensions the model is asked about. affected_surface is
# deliberately excluded (§2.4 — fully deterministic, never a model
# question).
_MODEL_DIMENSIONS: tuple[str, ...] = ("capability", "policy_contract", "risk_mode")


def build_classification_prompt(
    changed_paths: Iterable[str], diff_excerpt: str | None = None
) -> str:
    """A deterministic prompt naming the closed enum for each model
    dimension, so the model is structurally steered away from inventing a
    key or value it was never offered."""
    paths = sorted(set(changed_paths))
    lines = [
        "Classify this pull request's changed paths into the following "
        "closed taxonomy dimensions. For each dimension, respond with a "
        "JSON array containing ONLY values from that dimension's listed "
        "set below. Never invent a value. If you are not confident for a "
        "dimension, respond with [\"unclassified\"] for it.",
        "",
        "Changed paths:",
    ]
    lines.extend(f"- {p}" for p in paths)
    if diff_excerpt:
        lines += ["", "Diff excerpt:", diff_excerpt]
    lines.append("")
    lines.append("Dimensions and their closed value sets:")
    for dim in _MODEL_DIMENSIONS:
        values = sorted(tax.DIMENSIONS[dim])
        lines.append(f"- {dim}: {values}")
    lines.append("")
    lines.append(
        'Respond with a single JSON object with exactly the keys '
        f"{list(_MODEL_DIMENSIONS)}, each mapped to a non-empty JSON array "
        "of strings drawn only from that dimension's set above."
    )
    return "\n".join(lines)


def parse_classification_response(raw_text: str) -> dict[str, tuple[str, ...]]:
    """Turn the model's raw text response into a sanitized taxonomy
    mapping for the three model dimensions. Never raises: malformed JSON,
    an invented key, an invented value, or a missing dimension all resolve
    to ``(unclassified,)`` for the affected dimension(s) rather than
    propagating an exception into the PR path."""
    try:
        parsed: Any = json.loads(raw_text)
    except (ValueError, TypeError):
        parsed = {}
    sanitized = tax.sanitize_taxonomy_response(parsed)
    return {dim: sanitized[dim] for dim in _MODEL_DIMENSIONS}


def classify_pr_diff(
    changed_paths: Iterable[str],
    diff_excerpt: str | None = None,
    *,
    invoke: Callable[[str], str] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Classify a PR diff into all four taxonomy dimensions.

    ``affected_surface`` is always computed deterministically from
    ``changed_paths``. The other three dimensions come from ``invoke`` — a
    Class 2 runtime/credential-path callable (docs/benchmark/
    runtime-execution-contract.md) that takes the built prompt and returns
    the model's raw text response. When ``invoke`` is ``None`` (runtime
    unavailable — a distinct, explicit outcome per the runtime contract,
    never silently guessed), every model dimension resolves to
    ``unclassified`` rather than the call being skipped/hidden.
    """
    paths = list(changed_paths)
    affected_surface = tax.classify_affected_surfaces(paths)

    if invoke is None:
        model_result = {dim: (tax.UNCLASSIFIED,) for dim in _MODEL_DIMENSIONS}
    else:
        prompt = build_classification_prompt(paths, diff_excerpt)
        raw_text = invoke(prompt)
        model_result = parse_classification_response(raw_text)

    return {**model_result, "affected_surface": affected_surface}
