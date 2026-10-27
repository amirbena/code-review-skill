#!/usr/bin/env python3
"""Report the mandatory review-context size of each packaged Skill.

The unconditional set is derived from each SKILL.md "Required Policy Loading"
section, so the report cannot drift from the files the Skill tells a reviewer
to open. Output depends only on file contents; token figures are estimates.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS = ("local-code-review", "github-pr-review")
BYTES_PER_TOKEN = 4

SECTION_RE = re.compile(r"^## 2\.[^\n]*\n(.*?)(?=^## \d+\.)", re.M | re.S)
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
UNCONDITIONAL_CUE_RE = re.compile(r"^(?:shared,\s*)?always\b|^this skill's own\b", re.I)
CONDITIONAL_CUE_RE = re.compile(r"^conditionally\b", re.I)
# Links after this phrase belong to a context-specific member, not the default set.
CONTEXT_MEMBER_RE = re.compile(r"\bin\s+[^.]*?contexts?,\s*also\b|—\s*with [a-z ]+ workers\s*—", re.I)
# A "see [x](y)" cross-reference points at a file; it never declares it.
SEE_LINK_RE = re.compile(r"\bsee\s+\[[^\]]+\]\([^)]+\)", re.I)


class ReportError(Exception):
    """A required input could not be resolved."""


@dataclass(frozen=True)
class FileSize:
    path: str
    lines: int
    bytes: int

    @property
    def est_tokens(self) -> int:
        return -(-self.bytes // BYTES_PER_TOKEN)


@dataclass
class SkillReport:
    skill: str
    entry: FileSize
    unconditional: list[FileSize] = field(default_factory=list)
    context_conditional: list[FileSize] = field(default_factory=list)
    conditional: list[FileSize] = field(default_factory=list)
    procedure: list[FileSize] = field(default_factory=list)
    output_templates: list[FileSize] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)


def measure(repo: Path, rel: str) -> FileSize:
    data = (repo / rel).read_bytes()
    return FileSize(rel, data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1), len(data))


def section_two(text: str) -> str:
    match = SECTION_RE.search(text)
    if not match:
        raise ReportError("SKILL.md has no '## 2.' section")
    return match.group(1)


def resolve_link(repo: Path, skill_md: Path, target: str) -> str | None:
    """Repo-relative path of a local Markdown link, or None for anchors and URLs."""
    path = target.split("#", 1)[0]
    if not path or "://" in path or not path.endswith(".md"):
        return None
    resolved = (skill_md.parent / path).resolve()
    try:
        rel = resolved.relative_to(repo.resolve()).as_posix()
    except ValueError:
        raise ReportError(f"link escapes the repository: {target}") from None
    if not resolved.is_file():
        raise ReportError(f"link does not resolve to a file: {target} -> {rel}")
    return rel


def section_targets(section: str) -> tuple[list[str], list[str], list[str]]:
    """The one derivation of a Skill's load inventory: raw (unconditional, context-conditional, conditional)
    link targets of a section 2 body, in document order.

    Shared by this report, the policy-read checker and the inventory test, so none keeps its own list.
    """
    unconditional: list[str] = []
    context: list[str] = []
    conditional: list[str] = []
    for paragraph in re.split(r"\n\s*\n", section.strip()):
        if UNCONDITIONAL_CUE_RE.search(paragraph):
            marker = CONTEXT_MEMBER_RE.search(paragraph)
            split = marker.start() if marker else len(paragraph)
            targets = ((paragraph[:split], unconditional), (paragraph[split:], context))
        elif CONDITIONAL_CUE_RE.search(paragraph):
            targets = ((paragraph, conditional),)
        else:
            continue
        for chunk, bucket in targets:
            for link in LINK_RE.findall(SEE_LINK_RE.sub("", chunk)):
                if link not in bucket:
                    bucket.append(link)
    return unconditional, context, conditional


def classify_section(repo: Path, skill_md: Path, section: str) -> tuple[list[str], list[str], list[str]]:
    """Return (unconditional, context-conditional, conditional) repo-relative paths in document order."""
    buckets: list[list[str]] = []
    for raw in section_targets(section):
        bucket: list[str] = []
        for link in raw:
            rel = resolve_link(repo, skill_md, link)
            if rel and rel not in bucket:
                bucket.append(rel)
        buckets.append(bucket)
    unconditional, context, conditional = buckets
    context = [p for p in context if p not in unconditional]
    conditional = [p for p in conditional if p not in unconditional and p not in context]
    return unconditional, context, conditional


def skill_links(repo: Path, skill_md: Path, text: str, subdir: str) -> list[str]:
    """Links in SKILL.md outside section 2 that point into this Skill's own `subdir`."""
    outside = SECTION_RE.sub("", text)
    own = (skill_md.parent.relative_to(repo.resolve()) / subdir).as_posix() + "/"
    found: list[str] = []
    for link in LINK_RE.findall(outside):
        rel = resolve_link(repo, skill_md, link)
        if rel and rel.startswith(own) and rel not in found:
            found.append(rel)
    return found


def build_skill_report(repo: Path, skill: str) -> SkillReport:
    repo = repo.resolve()
    skill_md = repo / "skills" / skill / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    unconditional, context, conditional = classify_section(repo, skill_md, section_two(text))
    report = SkillReport(skill=skill, entry=measure(repo, skill_md.relative_to(repo).as_posix()))
    report.unconditional = [measure(repo, p) for p in unconditional]
    report.context_conditional = [measure(repo, p) for p in context]
    report.conditional = [measure(repo, p) for p in conditional]
    report.procedure = [measure(repo, p) for p in skill_links(repo, skill_md, text, "runbooks")]
    report.output_templates = [measure(repo, p) for p in skill_links(repo, skill_md, text, "templates")]
    return report


def total(files: Sequence[FileSize]) -> dict[str, int]:
    return {
        "files": len(files),
        "lines": sum(f.lines for f in files),
        "bytes": sum(f.bytes for f in files),
        "est_tokens": sum(f.est_tokens for f in files),
    }


def report_dict(report: SkillReport) -> dict:
    headline = [report.entry, *report.unconditional]
    full = [*headline, *report.procedure, *report.output_templates]
    group = lambda files: {"total": total(files), "files": [vars(f) | {"est_tokens": f.est_tokens} for f in files]}  # noqa: E731
    return {
        "skill": report.skill,
        "headline_entry_plus_unconditional": total(headline),
        "upper_bound_with_all_procedure_and_templates": total(full),
        "entry": group([report.entry]),
        "unconditional": group(report.unconditional),
        "context_conditional": group(report.context_conditional),
        "conditional": group(report.conditional),
        "procedure": group(report.procedure),
        "output_templates": group(report.output_templates),
        "unmeasured": report.unmeasured,
    }


def build(repo: Path = REPO_ROOT) -> dict:
    return {
        "schema": "context-size-report/v1",
        "bytes_per_token_estimate": BYTES_PER_TOKEN,
        "skills": [report_dict(build_skill_report(repo, s)) for s in SKILLS],
    }


def _row(label: str, t: dict[str, int]) -> str:
    return f"| {label} | {t['files']} | {t['lines']:,} | {t['bytes']:,} | ~{t['est_tokens']:,} |"


def render_markdown(data: dict) -> str:
    out = [
        f"Token figures are estimates (bytes / {data['bytes_per_token_estimate']}).",
        "",
    ]
    for skill in data["skills"]:
        out += [
            f"### {skill['skill']}",
            "",
            "| Group | Files | Lines | Bytes | Est. tokens |",
            "| --- | ---: | ---: | ---: | ---: |",
            _row("**Default set** (SKILL.md + section 2 unconditional)", skill["headline_entry_plus_unconditional"]),
            _row("Procedure files (all runbooks; modes are alternatives)", skill["procedure"]["total"]),
            _row("Output templates linked from SKILL.md", skill["output_templates"]["total"]),
            _row("Upper bound (default + all procedure + templates)", skill["upper_bound_with_all_procedure_and_templates"]),
            _row("Context-specific members (not in default set)", skill["context_conditional"]["total"]),
            _row("Conditional files (not loaded by default)", skill["conditional"]["total"]),
            "",
            "Default set, largest first:",
            "",
            "| File | Lines | Bytes |",
            "| --- | ---: | ---: |",
        ]
        files = [*skill["entry"]["files"], *skill["unconditional"]["files"]]
        for f in sorted(files, key=lambda f: (-f["bytes"], f["path"])):
            out.append(f"| `{f['path']}` | {f['lines']:,} | {f['bytes']:,} |")
        for note in skill["unmeasured"]:
            out += ["", f"Not measured: {note}."]
        out.append("")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of Markdown")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT, help="repository root to measure")
    args = parser.parse_args(argv)
    try:
        data = build(args.repo.resolve())
    except (ReportError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, indent=2, sort_keys=True) if args.json else render_markdown(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
