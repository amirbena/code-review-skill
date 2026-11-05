"""Validate a document against the JSON Schema subset the review-core result schema uses.

Supported keywords: type, const, enum, required, properties,
additionalProperties (false only), items, minItems, minLength, minimum,
pattern and local $ref. Any other keyword fails loudly, so the schema
cannot rely on one this validator ignores.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

SUPPORTED = frozenset(
    {
        "$schema", "$comment", "title", "description", "definitions", "$ref", "type", "const", "enum",
        "required", "properties", "additionalProperties", "items", "minItems", "minLength", "minimum", "pattern",
    }
)


def _is_type(value: Any, json_type: str) -> bool:
    checks = {
        "null": lambda v: v is None,
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "array": lambda v: isinstance(v, list),
        "object": lambda v: isinstance(v, dict),
    }
    if json_type not in checks:
        raise ValueError(f"unsupported JSON type: {json_type}")
    return checks[json_type](value)


def _resolve(ref: str, root: Mapping) -> Mapping:
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref is supported: {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _validate(value: Any, node: Mapping, root: Mapping, path: str, errors: list[str]) -> None:
    unknown = set(node) - SUPPORTED
    if unknown:
        raise ValueError(f"{path}: unsupported schema keywords {sorted(unknown)}")
    if "$ref" in node:
        _validate(value, _resolve(node["$ref"], root), root, path, errors)
        return
    if "type" in node:
        allowed = [node["type"]] if isinstance(node["type"], str) else list(node["type"])
        if not any(_is_type(value, t) for t in allowed):
            errors.append(f"{path}: expected {allowed}, got {value!r}")
            return
    if "const" in node and value != node["const"]:
        errors.append(f"{path}: expected {node['const']!r}, got {value!r}")
    if "enum" in node and value not in node["enum"]:
        errors.append(f"{path}: {value!r} not in {node['enum']}")
    if isinstance(value, str):
        if len(value) < node.get("minLength", 0):
            errors.append(f"{path}: shorter than {node['minLength']}")
        if "pattern" in node and not re.search(re.sub(r"(?<!\\)\$$", r"\\Z", node["pattern"]), value):
            errors.append(f"{path}: {value!r} does not match {node['pattern']}")
    if isinstance(value, int) and not isinstance(value, bool) and value < node.get("minimum", value):
        errors.append(f"{path}: {value} below {node['minimum']}")
    if isinstance(value, list):
        if len(value) < node.get("minItems", 0):
            errors.append(f"{path}: fewer than {node['minItems']} items")
        for index, item in enumerate(value):
            if "items" in node:
                _validate(item, node["items"], root, f"{path}[{index}]", errors)
    if isinstance(value, dict):
        properties = node.get("properties", {})
        for name in node.get("required", ()):
            if name not in value:
                errors.append(f"{path}: missing {name!r}")
        for name, sub in value.items():
            if name in properties:
                _validate(sub, properties[name], root, f"{path}.{name}", errors)
            elif node.get("additionalProperties", True) is False:
                errors.append(f"{path}: unexpected {name!r}")


def validate(document: Any, schema: Mapping) -> tuple[str, ...]:
    """Shape errors; empty when the document matches."""
    errors: list[str] = []
    _validate(document, schema, schema, "$", errors)
    return tuple(errors)
