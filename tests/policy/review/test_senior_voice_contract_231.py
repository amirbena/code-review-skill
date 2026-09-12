#!/usr/bin/env python3
"""Documentation-contract coverage for Issue #231.

Implements the senior/human voice-quality contract validated in #229:
consolidates the previously-triplicated senior voice rules (inline
rendering, full-body rendering, review-summary prose) under one owning
"Senior voice contract" in `shared/templates/finding-rendering.md`, fixes
the stale `finding.md` -> "Canonical human inline rendering" anchors, and
rewrites the canonical examples to remove first-person hedging on
required fixes and the bold `**What's good:**` / `**What's concerning:**`
summary labels.

These are structural/semantic assertions against the canonical
policy/template markdown (this repository's established test pattern),
not exact-prose or word-count checks.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

FINDING_RENDERING = REPO_ROOT / "shared/templates/finding-rendering.md"
REVIEW_SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
INVOCATION = REPO_ROOT / "shared/policies/invocation-options.md"
GH_OUTPUT = REPO_ROOT / "skills/github-pr-review/policies/review-output.md"
GH_SUMMARY = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
GH_INLINE = REPO_ROOT / "skills/github-pr-review/templates/inline-finding.md"
FEATURE_DOC = REPO_ROOT / "docs/features/human-review-output.md"

# Every canonical resource that can render or reference a senior-voice
# example, scanned for banned boilerplate/first-person phrasing.
ALL_SENIOR_VOICE_DOCS = (
    FINDING_RENDERING,
    REVIEW_SUMMARY,
    GH_OUTPUT,
    GH_SUMMARY,
    GH_INLINE,
    FEATURE_DOC,
)

BANNED_BOILERPLATE = (
    "The evidence shows",
    "The impact of this is",
    "Consider changing",
)

BANNED_FIRST_PERSON = ("I'd ", "I would ")


def _norm(path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


def _md_or_text_blocks(path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"```(?:markdown|text)\n(.*?)\n```", text, re.S)


class SingleOwnerExists(unittest.TestCase):
    """One "Senior voice contract" section owns the voice; it is not a
    second copy of an existing rule set."""

    def test_contract_section_exists_in_finding_rendering(self) -> None:
        raw = FINDING_RENDERING.read_text(encoding="utf-8")
        self.assertIn("## Senior voice contract", raw)
        t = _norm(FINDING_RENDERING)
        self.assertIn("single owner", t)
        self.assertIn("presentation only", t)

    def test_contract_names_the_eight_principles_and_two_decisions(self) -> None:
        t = _norm(FINDING_RENDERING)
        raw = FINDING_RENDERING.read_text(encoding="utf-8")
        self.assertIn("Lead with the defect or failure mode", t)
        self.assertIn("Say why it matters in the repo", t)
        self.assertIn("State each fact once", t)
        self.assertIn("Separate required from optional", t)
        self.assertIn("Tone follows severity", t)
        self.assertIn("Length follows complexity", t)
        self.assertIn("No boilerplate", t)
        self.assertIn("Same rigor as structured mode", t)
        self.assertIn("No dedicated praise slot", raw)
        self.assertIn(
            "Required fixes are stated directly, not as first-person suggestions",
            raw,
        )

    def test_contract_states_semantic_not_lexical_restatement(self) -> None:
        t = _norm(FINDING_RENDERING)
        self.assertIn("Semantic restatement, not lexical", t)
        self.assertIn("not by whether it repeats a noun phrase", t)
        self.assertIn(
            "do not build or apply a mechanical noun-phrase-repetition check",
            t.lower(),
        )


class OtherSitesLinkInsteadOfRestate(unittest.TestCase):
    """The three consuming sites keep only surface-specific shape and link
    to the single owner instead of restating the voice rules."""

    def test_finding_rendering_inline_and_full_link_to_the_contract(self) -> None:
        raw = FINDING_RENDERING.read_text(encoding="utf-8")
        inline_section = raw.split("## Canonical human inline rendering", 1)[1]
        inline_section = inline_section.split("## Canonical human full rendering", 1)[0]
        self.assertIn("Senior voice contract", inline_section)

        full_section = raw.split("## Canonical human full rendering", 1)[1]
        self.assertIn("Senior voice contract", full_section)

    def test_review_summary_links_instead_of_restating(self) -> None:
        raw = REVIEW_SUMMARY.read_text(encoding="utf-8")
        opt_in = raw.split("## Concise human-style summary (opt-in)", 1)[1]
        opt_in = opt_in.split("## Machine metadata is subordinate", 1)[0]
        self.assertIn(
            "[`finding-rendering.md`](finding-rendering.md), \"Senior voice contract\"",
            opt_in,
        )
        # The density/de-dup/voice-tightening rules are no longer
        # restated here in full; they are a pointer to the shared owner.
        self.assertNotIn("never narrate file-by-file inspection", opt_in)

    def test_review_output_policy_links_instead_of_restating(self) -> None:
        t = _norm(GH_OUTPUT)
        self.assertIn("Senior voice contract", t)

    def test_inline_finding_template_links_instead_of_restating(self) -> None:
        t = _norm(GH_INLINE)
        self.assertIn("Senior voice contract", t)


class NoStaleAnchorsRemain(unittest.TestCase):
    """`finding.md` no longer owns "Canonical human inline/full
    rendering" (moved to `finding-rendering.md` by #198); no packaged or
    shared resource may still point readers there."""

    SCAN_ROOTS = (
        REPO_ROOT / "shared",
        REPO_ROOT / "skills",
        REPO_ROOT / "docs",
    )

    STALE_PATTERN = re.compile(
        r"\[`finding\.md`\]\(finding\.md\)|\[`\.\./\.\./\.\./shared/templates/finding\.md`\]"
        r"\(\.\./\.\./\.\./shared/templates/finding\.md\)|"
        r"\[`\.\./templates/finding\.md`\]\(\.\./templates/finding\.md\)",
    )

    def test_no_link_to_finding_md_names_the_canonical_human_sections(self) -> None:
        for root in self.SCAN_ROOTS:
            for path in root.rglob("*.md"):
                text = path.read_text(encoding="utf-8")
                for match in self.STALE_PATTERN.finditer(text):
                    # Only a problem if that same link's nearby text still
                    # claims to point at a "Canonical human ..." section
                    # (those sections live in finding-rendering.md, not
                    # finding.md, since #198).
                    window = text[match.end(): match.end() + 80]
                    self.assertNotIn(
                        "Canonical human",
                        window,
                        f"stale finding.md anchor to a Canonical human section in {path}",
                    )


class BannedBoilerplateAbsent(unittest.TestCase):
    """No senior-voice example anywhere uses the named boilerplate
    openers or generic filler."""

    def test_no_banned_boilerplate_in_any_rendered_example(self) -> None:
        for path in ALL_SENIOR_VOICE_DOCS:
            for block in _md_or_text_blocks(path):
                for phrase in BANNED_BOILERPLATE:
                    self.assertNotIn(
                        phrase, block, f"{phrase!r} found in an example in {path}"
                    )

    def test_no_first_person_hedging_anywhere_in_a_rendered_example(self) -> None:
        for path in ALL_SENIOR_VOICE_DOCS:
            for block in _md_or_text_blocks(path):
                for phrase in BANNED_FIRST_PERSON:
                    self.assertNotIn(
                        phrase, block, f"{phrase!r} found in an example in {path}"
                    )

    def test_no_bold_whats_good_whats_concerning_labels_remain(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        self.assertNotIn("**What's good:**", raw)
        self.assertNotIn("**What's concerning:**", raw)


class P0P1ExamplesHaveNoHedgingOnTheRequiredFix(unittest.TestCase):
    """Every P0/P1 senior example states its required fix directly."""

    def test_finding_rendering_p1_examples_are_decisive(self) -> None:
        raw = FINDING_RENDERING.read_text(encoding="utf-8")
        for block in _md_or_text_blocks(FINDING_RENDERING):
            if re.match(r"(### \S+ )?P1[:\s]", block):
                for phrase in BANNED_FIRST_PERSON:
                    self.assertNotIn(phrase, block)
        self.assertIn("P1: Paginated file listing stops after page 1", raw)
        self.assertIn("F3 P1: Paginated file listing stops after page 1", raw)

    def test_inline_finding_p1_example_is_decisive(self) -> None:
        raw = GH_INLINE.read_text(encoding="utf-8")
        self.assertIn("P1 (Blocking): Paginated file listing stops after page 1", raw)
        for block in _md_or_text_blocks(GH_INLINE):
            if "P1 (Blocking):" in block:
                for phrase in BANNED_FIRST_PERSON:
                    self.assertNotIn(phrase, block)

    def test_summary_p1_findings_are_decisive(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        senior_block = re.search(
            r"## Concise human-style body \(opt-in\)\n\n.*?```markdown\n(.*?)\n```",
            raw,
            re.S,
        ).group(1)
        self.assertIn("P1 (Blocking)", senior_block)
        for phrase in BANNED_FIRST_PERSON:
            self.assertNotIn(phrase, senior_block)


class PresentationOnlyInvariantRestated(unittest.TestCase):
    def test_contract_states_presentation_only_boundary(self) -> None:
        t = _norm(FINDING_RENDERING)
        self.assertIn(
            "changes no finding's detection, severity, identity, "
            "deduplication, evidence/remediation requirement, verdict "
            "derivation, placement/anchor, or publication authorization",
            t,
        )


if __name__ == "__main__":
    unittest.main()
