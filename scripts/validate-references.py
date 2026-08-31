#!/usr/bin/env python3
"""Validate tracked Markdown links and declared shared Skill resources."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode


MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")


@dataclass(frozen=True, order=True)
class UnresolvedReference:
    source: str
    line: int
    target: str


def tracked_files(root: Path, pathspec: str) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", pathspec],
        check=True,
        capture_output=True,
    )
    return [root / path.decode("utf-8") for path in result.stdout.split(b"\0") if path]


def link_destination(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    return target.split(maxsplit=1)[0]


def mask_inline_code(line: str) -> str:
    masked = list(line)
    cursor = 0
    while (start := line.find("`", cursor)) >= 0:
        end_of_run = start
        while end_of_run < len(line) and line[end_of_run] == "`":
            end_of_run += 1
        delimiter = line[start:end_of_run]
        close = line.find(delimiter, end_of_run)
        if close < 0:
            break
        for index in range(start, close + len(delimiter)):
            masked[index] = " "
        cursor = close + len(delimiter)
    return "".join(masked)


def mask_code(text: str) -> str:
    masked_lines: list[str] = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        match = FENCE_RE.match(content)
        if fence is not None:
            masked_lines.append("".join("\n" if char == "\n" else " " for char in line))
            if match:
                marker = match.group(1)
                remainder = content[match.end() :]
                if marker[0] == fence[0] and len(marker) >= fence[1] and not remainder.strip():
                    fence = None
            continue
        if match:
            marker = match.group(1)
            fence = (marker[0], len(marker))
            masked_lines.append("".join("\n" if char == "\n" else " " for char in line))
            continue
        masked_lines.append(mask_inline_code(line))
    return "".join(masked_lines)


def markdown_failures(root: Path) -> list[UnresolvedReference]:
    failures: list[UnresolvedReference] = []
    for source in tracked_files(root, "*.md"):
        text = source.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_RE.finditer(mask_code(text)):
            raw_target = link_destination(match.group(1))
            if (
                not raw_target
                or raw_target.startswith(("#", "/", "//"))
                or SCHEME_RE.match(raw_target)
            ):
                continue
            path_target = unquote(raw_target.split("#", 1)[0].split("?", 1)[0])
            resolved = (source.parent / path_target).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                exists = False
            else:
                exists = resolved.exists()
            if not exists:
                failures.append(
                    UnresolvedReference(
                        str(source.relative_to(root)),
                        text.count("\n", 0, match.start()) + 1,
                        raw_target,
                    )
                )
    return failures


def scalar_nodes(node: Node):
    if isinstance(node, ScalarNode):
        yield node
    elif isinstance(node, MappingNode):
        for _, value in node.value:
            yield from scalar_nodes(value)
    else:
        for child in node.value:
            yield from scalar_nodes(child)


def shared_node(document: Node) -> Node | None:
    if not isinstance(document, MappingNode):
        return None
    for key, value in document.value:
        if isinstance(key, ScalarNode) and key.value == "shared":
            return value
    return None


def metadata_failures(root: Path) -> list[UnresolvedReference]:
    failures: list[UnresolvedReference] = []
    shared_root = (root / "shared").resolve()
    pathspec = ":(glob)skills/*/metadata/skill.yaml"
    for source in tracked_files(root, pathspec):
        document = yaml.compose(source.read_text(encoding="utf-8"))
        if document is None or (shared := shared_node(document)) is None:
            continue
        for node in scalar_nodes(shared):
            target = node.value
            resolved = (source.parent / target).resolve()
            try:
                resolved.relative_to(shared_root)
            except ValueError:
                exists = False
            else:
                exists = resolved.is_file()
            if not exists:
                failures.append(
                    UnresolvedReference(
                        str(source.relative_to(root)), node.start_mark.line + 1, target
                    )
                )
    return failures


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = args.root.resolve()
    failures = markdown_failures(root) + metadata_failures(root)
    if failures:
        print("Unresolved repository references:", file=sys.stderr)
        for failure in sorted(failures):
            print(f"- {failure.source}:{failure.line}: {failure.target}", file=sys.stderr)
        return 1
    print("All repository references resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
