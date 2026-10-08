#!/usr/bin/env python3
"""Per-run evidence, skill-isolation verification and capability-activation
classification for the on-demand workspace sibling measurement (Issue #664).

Repository-development benchmark tooling only; nothing here is packaged and
nothing here changes a Skill, a fixture, a threshold, or the gate.

Three jobs, each a small pure function over the review CLI's
``--output-format stream-json --verbose`` event stream:

- :func:`parse_stream` reads the stream the CLI wrote, whether or not the run
  succeeded.
- :func:`verify_isolation` fails closed unless the stream's ``init`` event shows
  that exactly the skill under test was available and that every skill call
  went to it. A prompt asking for ``local-code-review`` is never the binding.
- :func:`classify_activation` separates "a workspace root was supplied" from
  "a sibling was inspected" from "sibling content was read" using the tool calls
  the reviewer actually made.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

SKILL_NAME = "local-code-review"
INLINE_SOURCE_SUFFIX = "@inline"
BUILTIN_SOURCE_SUFFIX = "@builtin"
MAX_TRACE_INPUT_CHARS = 400


class IsolationError(RuntimeError):
    """The harness cannot establish that the skill under test, and only it, ran."""


class StreamParseError(ValueError):
    """The CLI output was not a usable stream-json event stream."""


@dataclass(frozen=True)
class SkillIdentity:
    skill: str
    plugin_name: str
    plugin_path: str
    plugin_source: str
    plugin_version: str | None
    git_head: str | None
    git_dirty: bool | None
    claude_code_version: str | None
    model: str | None


@dataclass(frozen=True)
class StreamSummary:
    init: Mapping[str, Any] | None
    result: Mapping[str, Any] | None
    tool_calls: tuple[tuple[str, Mapping[str, Any]], ...]
    event_count: int


def parse_stream(stdout: str) -> StreamSummary:
    """Parse stream-json lines. Lines that are not JSON objects are ignored; a
    stream with no events at all is an error."""
    init: Mapping[str, Any] | None = None
    result: Mapping[str, Any] | None = None
    calls: list[tuple[str, Mapping[str, Any]]] = []
    count = 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        count += 1
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init" and init is None:
            init = event
        elif kind == "result":
            result = event
        elif kind == "assistant":
            content = (event.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    calls.append((str(block.get("name")), block.get("input") or {}))
    if count == 0:
        raise StreamParseError("no stream-json events in the review CLI output")
    return StreamSummary(init, result, tuple(calls), count)


def _git(root: Path, *args: str) -> str | None:
    completed = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else None


def verify_isolation(summary: StreamSummary, *, expected_root: Path) -> SkillIdentity:
    """Return the identity of the one skill that ran, or raise :class:`IsolationError`.

    Fails closed when: there is no init event; the number of skills named
    ``local-code-review`` is not exactly one; the plugin providing it is not the
    inline plugin loaded from ``expected_root``; any other non-builtin plugin is
    loaded; no skill call was made; or a skill call went anywhere else.
    """
    init = summary.init
    if init is None:
        raise IsolationError("no init event: cannot establish which skill was available")
    expected = Path(expected_root).resolve()
    candidates = [s for s in init.get("skills") or [] if s == SKILL_NAME or str(s).endswith(f":{SKILL_NAME}")]
    if len(candidates) != 1:
        raise IsolationError(f"expected exactly one {SKILL_NAME} skill, found {sorted(candidates)}")
    qualified = candidates[0]
    plugins = list(init.get("plugins") or [])
    foreign = [
        p.get("source") or p.get("name")
        for p in plugins
        if not str(p.get("source", "")).endswith(BUILTIN_SOURCE_SUFFIX)
        and not (str(p.get("source", "")).endswith(INLINE_SOURCE_SUFFIX) and Path(str(p.get("path"))).resolve() == expected)
    ]
    if foreign:
        raise IsolationError(f"plugins other than the skill under test are loaded: {sorted(map(str, foreign))}")
    owner = qualified.rpartition(":")[0]
    matching = [p for p in plugins if p.get("name") == owner and Path(str(p.get("path"))).resolve() == expected]
    if len(matching) != 1:
        raise IsolationError(f"{qualified} does not come from the plugin loaded from {expected}")
    plugin = matching[0]
    skill_calls = [str(i.get("skill")) for n, i in summary.tool_calls if n == "Skill"]
    if not skill_calls:
        raise IsolationError("the reviewer never invoked a skill: cannot establish which skill produced the report")
    stray = sorted({c for c in skill_calls if c not in (qualified, SKILL_NAME)})
    if stray:
        raise IsolationError(f"the reviewer invoked a skill other than {qualified}: {stray}")
    dirty = _git(expected, "status", "--porcelain")
    return SkillIdentity(
        skill=qualified,
        plugin_name=str(plugin.get("name")),
        plugin_path=str(expected),
        plugin_source=str(plugin.get("source")),
        plugin_version=plugin.get("version"),
        git_head=_git(expected, "rev-parse", "HEAD"),
        git_dirty=None if dirty is None else bool(dirty),
        claude_code_version=init.get("claude_code_version"),
        model=init.get("model"),
    )


def usage_totals(result: Mapping[str, Any] | None) -> dict[str, int] | None:
    """Token usage the CLI reported, or None. Never estimated.

    ``input_tokens`` is the whole prompt context: fresh input plus cache creation
    plus cache reads. The CLI reports those separately and the fresh part alone
    is a few tokens, which would hide the real context cost.
    """
    usage = (result or {}).get("usage")
    if not isinstance(usage, Mapping):
        return None
    try:
        fresh = int(usage["input_tokens"])
        out = int(usage["output_tokens"])
    except (KeyError, TypeError, ValueError):
        return None
    cache_create = int(usage.get("cache_creation_input_tokens") or 0)
    cache_read = int(usage.get("cache_read_input_tokens") or 0)
    return {
        "input_tokens": fresh + cache_create + cache_read,
        "output_tokens": out,
        "fresh_input_tokens": fresh,
        "cache_creation_input_tokens": cache_create,
        "cache_read_input_tokens": cache_read,
    }


# --- capability activation -------------------------------------------------

_CONTENT_VERBS = re.compile(
    r"(?<![\w-])(cat|head|tail|sed|awk|grep|rg|less|more)\b"
    r"|\bgit\b[^|;&]*\b(show|cat-file|grep|diff|blame)\b|\bgit\b[^|;&]*\blog\b[^|;&]*\s-p\b"
)


def _variants(path: Path) -> set[str]:
    raw = str(path)
    resolved = str(path.resolve())
    forms = {raw, resolved}
    for form in list(forms):
        if form.startswith("/private/"):
            forms.add(form[len("/private") :])
        else:
            forms.add("/private" + form)
    return forms


def classify_activation(
    tool_calls: Sequence[tuple[str, Mapping[str, Any]]],
    *,
    workspace_root: Path | None,
    sibling_names: Sequence[str],
) -> dict[str, Any]:
    """Distinguish the four activation levels from the reviewer's own tool calls.

    - ``supplied``: the harness handed a workspace root (not evidence of use).
    - ``discovered``: some call touched the root itself, outside any sibling.
    - ``siblings_inspected``: some call referenced a path inside a sibling.
    - ``sibling_content_read``: a call read file content inside a sibling
      (``Read``/``Grep`` on a sibling path, or a content verb such as ``cat`` or
      ``git show`` against it). Listing a directory or ``git ls-tree`` is not a
      content read.

    The relevance of what was read is not judged here; it is a fixture-specific
    question for whoever reads the evidence. Classification is by inspection of
    call inputs, so a command built indirectly can be misclassified; the call
    trace is retained so the result can be checked.
    """
    if workspace_root is None:
        return {"supplied": False, "discovered": False, "siblings_inspected": [], "sibling_content_read": []}
    forms = _variants(Path(workspace_root))
    discovered = False
    inspected: set[str] = set()
    read: dict[str, set[str]] = {}
    for name, tool_input in tool_calls:
        text = json.dumps(tool_input)
        if not any(form in text for form in forms):
            continue
        in_sibling = False
        for sibling in sibling_names:
            if any(f"{form}/{sibling}" in text for form in forms):
                in_sibling = True
                inspected.add(sibling)
                if _reads_content(name, text):
                    read.setdefault(sibling, set()).add(_first_path(text, forms, sibling))
        if not in_sibling:
            discovered = True
    return {
        "supplied": True,
        "discovered": discovered or bool(inspected),
        "siblings_inspected": sorted(inspected),
        "sibling_content_read": {k: sorted(v) for k, v in sorted(read.items())},
    }


def _reads_content(tool: str, text: str) -> bool:
    if tool in ("Read", "Grep"):
        return True
    if tool == "Bash":
        return bool(_CONTENT_VERBS.search(text))
    return False


def _first_path(text: str, forms: set[str], sibling: str) -> str:
    for form in forms:
        match = re.search(re.escape(f"{form}/{sibling}") + r"[^\s\"'\\]*", text)
        if match:
            return match.group(0)[len(form) + 1 :]
    return sibling


# --- evidence record ---------------------------------------------------------


@dataclass
class RunEvidence:
    """Everything retained about one reviewer invocation, success or failure."""

    argv_redacted: list[str] = field(default_factory=list)
    prompt_sha256: str | None = None
    cwd: str | None = None
    isolation: str = "none"
    exit_code: int | None = None
    error_category: str | None = None
    error_message: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    seconds: float | None = None
    skill: dict[str, Any] | None = None
    usage: dict[str, int] | None = None
    activation: dict[str, Any] | None = None
    tool_trace: list[dict[str, str]] = field(default_factory=list)
    result_is_error: bool | None = None
    session_id: str | None = None

    def metadata(self) -> dict[str, Any]:
        """The record minus the (large) raw streams."""
        data = asdict(self)
        data.pop("stdout")
        data.pop("stderr")
        return data


def redact_argv(command: Sequence[str], prompt: str) -> tuple[list[str], str]:
    """The command with the prompt replaced by its hash, plus that hash."""
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return [f"<prompt sha256:{digest[:16]}>" if arg == prompt or prompt in arg else arg for arg in command], digest


def trace_of(calls: Sequence[tuple[str, Mapping[str, Any]]]) -> list[dict[str, str]]:
    return [{"tool": n, "input": json.dumps(i)[:MAX_TRACE_INPUT_CHARS]} for n, i in calls]


def write_run_evidence(directory: Path, run_id: str, evidence: RunEvidence) -> str:
    """Write ``<run_id>.json`` (metadata) plus raw ``.stdout``/``.stderr`` files.
    Refuses to overwrite. Returns the metadata file name."""
    directory.mkdir(parents=True, exist_ok=True)
    meta = directory / f"{run_id}.json"
    if meta.exists():
        raise FileExistsError(f"refusing to overwrite evidence {meta}")
    for suffix, content in (("stdout", evidence.stdout), ("stderr", evidence.stderr)):
        if content is not None:
            with open(directory / f"{run_id}.{suffix}", "x", encoding="utf-8") as handle:
                handle.write(content)
    with open(meta, "x", encoding="utf-8") as handle:
        json.dump(evidence.metadata() | {"raw_streams_retained": [s for s, c in (("stdout", evidence.stdout), ("stderr", evidence.stderr)) if c is not None]}, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return meta.name


def sibling_names_of(root: Path) -> list[str]:
    """Immediate child directories of the root, as the harness materialized them."""
    return sorted(p.name for p in Path(root).iterdir() if p.is_dir()) if Path(root).is_dir() else []

