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
# A paragraph opened this way is required for coverage but loaded at the phase that first uses it.
PHASED_CUE_RE = re.compile(r"^always,\s*by phase\b", re.I)
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
    phased: list[FileSize] = field(default_factory=list)
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


def phased_targets(section: str) -> list[str]:
    """Raw link targets of the "Always, by phase" paragraphs of a section 2 body."""
    found: list[str] = []
    for paragraph in re.split(r"\n\s*\n", section.strip()):
        if PHASED_CUE_RE.search(paragraph):
            for link in LINK_RE.findall(SEE_LINK_RE.sub("", paragraph)):
                if link not in found:
                    found.append(link)
    return found


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
    section = section_two(text)
    phased = {rel for rel in (resolve_link(repo, skill_md, link) for link in phased_targets(section)) if rel}
    report.unconditional = [measure(repo, p) for p in unconditional if p not in phased]
    report.phased = [measure(repo, p) for p in unconditional if p in phased]
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
    whole = [*headline, *report.phased]
    full = [*whole, *report.procedure, *report.output_templates]
    group = lambda files: {"total": total(files), "files": [vars(f) | {"est_tokens": f.est_tokens} for f in files]}  # noqa: E731
    return {
        "skill": report.skill,
        "headline_entry_plus_unconditional": total(headline),
        "before_step_1": total(headline),
        "whole_review_default": total(whole),
        "phased": group(report.phased),
        "upper_bound_with_all_procedure_and_templates": total(full),
        "entry": group([report.entry]),
        "unconditional": group(report.unconditional),
        "context_conditional": group(report.context_conditional),
        "conditional": group(report.conditional),
        "procedure": group(report.procedure),
        "output_templates": group(report.output_templates),
        "unmeasured": report.unmeasured,
    }


def savings(before: dict, after: dict) -> dict[str, int]:
    """Bytes moved out of the before-step-1 checkpoint, split into what no review loads any more
    (genuine) and what a review still loads later (deferral)."""
    checkpoint = before["before_step_1"]["bytes"] - after["before_step_1"]["bytes"]
    genuine = before["whole_review_default"]["bytes"] - after["whole_review_default"]["bytes"]
    return {"before_step_1_bytes": checkpoint, "genuine_bytes": genuine, "deferral_bytes": checkpoint - genuine}


def build(repo: Path = REPO_ROOT, baseline: Path | None = None) -> dict:
    skills = [report_dict(build_skill_report(repo, s)) for s in SKILLS]
    if baseline is not None:
        for current in skills:
            prior = report_dict(build_skill_report(baseline, current["skill"]))
            current["savings_vs_baseline"] = savings(prior, current)
    return {
        "schema": "context-size-report/v1",
        "bytes_per_token_estimate": BYTES_PER_TOKEN,
        "skills": skills,
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
            _row("**Before step 1** (SKILL.md + section 2 unconditional)", skill["before_step_1"]),
            _row("Loaded by phase (required for coverage)", skill["phased"]["total"]),
            _row("**Whole review default** (before step 1 + by phase)", skill["whole_review_default"]),
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
        files = [*skill["entry"]["files"], *skill["unconditional"]["files"], *skill["phased"]["files"]]
        for f in sorted(files, key=lambda f: (-f["bytes"], f["path"])):
            out.append(f"| `{f['path']}` | {f['lines']:,} | {f['bytes']:,} |")
        if "savings_vs_baseline" in skill:
            s = skill["savings_vs_baseline"]
            out += [
                "",
                f"Versus baseline: before step 1 {s['before_step_1_bytes']:+,} bytes fewer, "
                f"genuine (no longer loaded) {s['genuine_bytes']:,}, deferral (loaded later) {s['deferral_bytes']:,}.",
            ]
        for note in skill["unmeasured"]:
            out += ["", f"Not measured: {note}."]
        out.append("")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of Markdown")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT, help="repository root to measure")
    parser.add_argument("--baseline", type=Path, help="earlier checkout to report genuine savings against")
    args = parser.parse_args(argv)
    try:
        data = build(args.repo.resolve(), args.baseline.resolve() if args.baseline else None)
    except (ReportError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, indent=2, sort_keys=True) if args.json else render_markdown(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
