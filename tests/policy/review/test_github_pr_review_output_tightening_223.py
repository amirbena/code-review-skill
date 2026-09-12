#!/usr/bin/env python3
"""Structural/semantic regression coverage for Issue #223.

Tightens `github-pr-review`'s final human-facing output contract: a stable
`## Review Summary` heading, a reader-visible compact severity legend on
every finding heading, explicit non-numeric density/de-duplication
guidance for both output modes, tightened senior-mode voice, reinforced
inline-finding compactness, and a prohibition on agent/model/tool
disclosure in the published review surface.

These are structural/semantic assertions against the canonical
policy/template markdown (this repository's established test pattern —
see e.g. `test_human_review_output_docs.py`), not exact-prose or
word-count checks, and not an execution of a live reviewer.

Cross-Skill boundary (also under test): none of this tightening may leak
into `local-code-review`'s own report format, heading, or voice — its
templates/runbook/policies are pinned by content hash captured before this
change.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

SHARED_SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
SHARED_FINDING = REPO_ROOT / "shared/templates/finding.md"
SHARED_FINDING_RENDERING = REPO_ROOT / "shared/templates/finding-rendering.md"
SHARED_SEVERITY = REPO_ROOT / "shared/policies/severity.md"

GH_OUTPUT = REPO_ROOT / "skills/github-pr-review/policies/review-output.md"
GH_SUMMARY = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
GH_INLINE = REPO_ROOT / "skills/github-pr-review/templates/inline-finding.md"
GH_DIR = REPO_ROOT / "skills/github-pr-review"

LOCAL_REPORT = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
LOCAL_RUNBOOK = REPO_ROOT / "skills/local-code-review/runbooks/local-review.md"
LOCAL_SKILL = REPO_ROOT / "skills/local-code-review/SKILL.md"
LOCAL_POLICY_DIR = REPO_ROOT / "skills/local-code-review/policies"

SEVERITY_LEGEND = {
    "P0": "P0 (Critical)",
    "P1": "P1 (Blocking)",
    "P2": "P2 (Non-Blocking)",
}

# Content hashes captured from the working tree *before* Issue #223 touched
# anything, via `git hash-object`. Issue #223 must not modify any of these
# files — this is the "local-code-review is provably unaffected" guard the
# Issue's cross-Skill boundary and acceptance criteria require.
#
# LOCAL_REPORT's, LOCAL_RUNBOOK's, and LOCAL_SKILL's hashes were re-captured
# after Issue #89 (review-stopping-criteria.md) made deliberate,
# separately-owned changes to local-review-report.md (the always-on Coverage
# metadata field and the REVIEW INCOMPLETE decision variant),
# local-review.md (the new "Evaluate review coverage" step), and SKILL.md
# (the required-policy link) — unrelated to #223's github-pr-review
# tightening, which this guard exists to catch. LOCAL_REPORT and
# LOCAL_RUNBOOK were re-captured again after Issue #237 (thin-pointer trim
# of the family-of-four subordinate-metadata prose in the "Rules" section
# and steps 8b-8d/10b) — also deliberate and unrelated to #223. The other
# files in this map are untouched by #89/#237 and keep their original
# #223-era hashes.
LOCAL_BASELINE_HASHES = {
    LOCAL_REPORT: "1abf7c6a28f6d6b73a845aa8c8f9e06e7d062a82",
    LOCAL_RUNBOOK: "1a48a4e0d21322fcb6a4e4ec71cdf0023640c42b",
    LOCAL_SKILL: "44b6e6953d2847f6c999d5824d41d235b6fd9435",
    LOCAL_POLICY_DIR / "invocation-approval.md": "3fad248e86f655af57a06a99624a226d56238e0d",
    LOCAL_POLICY_DIR / "pr-context.md": "1b5238723eab4308407c137c554fa3a169e8b482",
    LOCAL_POLICY_DIR / "repository-state.md": "6792d7e3f7ae1ad0214fff2e85db5e28ac6fb108",
    LOCAL_POLICY_DIR / "review-context.md": "ea16e2e8425e8c85f83ba5588d0e8aee94bd495e",
}


def _git_blob_sha1(path) -> str:
    """Reimplements `git hash-object` so the baseline check needs no
    subprocess/git dependency at test time — a pure content hash of the
    exact bytes on disk, using git's own blob framing."""
    import hashlib

    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def _norm(path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


def _md_or_text_blocks(path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"```(?:markdown|text)\n(.*?)\n```", text, re.S)


class LocalCodeReviewIsProvablyUnaffected(unittest.TestCase):
    """Acceptance criterion: a regression test asserts local-code-review's
    own report template/policy/runbook is unchanged by this work."""

    def test_local_resources_match_pre_223_content_hash(self) -> None:
        for path, expected_hash in LOCAL_BASELINE_HASHES.items():
            self.assertTrue(path.is_file(), f"missing: {path}")
            actual = _git_blob_sha1(path)
            self.assertEqual(
                actual,
                expected_hash,
                f"{path.relative_to(REPO_ROOT)} changed during Issue #223 "
                "work — local-code-review's own report format/voice/heading "
                "must stay byte-for-byte unchanged",
            )

    def test_local_report_heading_is_unchanged(self) -> None:
        text = LOCAL_REPORT.read_text(encoding="utf-8")
        self.assertIn("## Code Review", text)
        self.assertNotIn("## Review Summary", text)

    def test_local_report_has_no_severity_legend_leak(self) -> None:
        text = LOCAL_REPORT.read_text(encoding="utf-8")
        for legend in SEVERITY_LEGEND.values():
            self.assertNotIn(legend, text)

    def test_local_report_has_no_github_density_subsection_leak(self) -> None:
        text = LOCAL_REPORT.read_text(encoding="utf-8")
        self.assertNotIn("github-pr-review only", text)
        self.assertNotIn("Density, de-duplication, and voice tightening", text)


class StableReviewSummaryHeading(unittest.TestCase):
    """Both github-pr-review output modes render a body starting
    `## Review Summary` — clean, findings, fallback, and self-review
    COMMENT cases, structured and human_review_output alike."""

    def test_shared_template_documents_the_override_point(self) -> None:
        raw = SHARED_SUMMARY.read_text(encoding="utf-8")
        self.assertIn("### Heading is a per-Skill override point", raw)
        t = _norm(SHARED_SUMMARY)
        self.assertIn("default heading", t)
        self.assertIn("github-pr-review overrides it to ## Review Summary", t)
        # The default heading itself (consumed by local-code-review) is
        # unchanged in the canonical shape.
        canonical_shape = re.search(
            r"## Canonical shape\n\n```markdown\n(.*?)\n```", raw, re.S
        )
        self.assertIsNotNone(canonical_shape)
        self.assertIn("## Code Review", canonical_shape.group(1))

    def test_review_output_policy_states_the_stable_heading_rule(self) -> None:
        t = _norm(GH_OUTPUT)
        self.assertIn("## Review Summary", GH_OUTPUT.read_text(encoding="utf-8"))
        self.assertIn("never changes with mode, verdict, or reviewed", t)
        self.assertIn("replaces the previously used", t)

    def test_every_rendered_example_case_uses_the_new_heading(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        # Clean, findings-with-inline-anchors, self-review COMMENT, and the
        # concise human_review_output body all render examples in this
        # file; none may use the retired heading.
        self.assertNotIn("## Code Review", raw)
        headings = re.findall(r"^## (Review Summary|Code Review)$", raw, re.M)
        self.assertGreaterEqual(len(headings), 4, "expected >=4 rendered example headings")
        self.assertTrue(all(h == "Review Summary" for h in headings))

    def test_readme_example_also_uses_the_new_heading(self) -> None:
        readme = (GH_DIR / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Review Summary", readme)
        self.assertNotIn("## Code Review", readme)


class ReaderVisibleSeverityLegend(unittest.TestCase):
    """Each rendered finding heading exposes a compact, canonical
    human-readable severity meaning, once, with no repeated explanatory
    paragraph — aligned with shared/policies/severity.md."""

    def test_legend_defined_once_and_aligned_with_severity_policy(self) -> None:
        raw = GH_OUTPUT.read_text(encoding="utf-8")
        self.assertIn("## Reader-visible severity legend", raw)
        for code, legend in SEVERITY_LEGEND.items():
            self.assertIn(legend, raw)
        t = _norm(GH_OUTPUT)
        self.assertIn("never changes severity, identity", t)
        # Alignment: severity.md's own blocking semantics are named, not
        # contradicted (both P0 and P1 block).
        severity_text = _norm(SHARED_SEVERITY)
        self.assertIn("Critical / Blocking", severity_text)
        self.assertIn("Significant / Blocking", severity_text)
        self.assertIn("Non-Blocking", severity_text)

    def test_finding_list_summary_pointer_uses_the_legend(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        self.assertIn("P1 (Blocking) —", raw)
        self.assertIn("P2 (Non-Blocking) —", raw)

    def test_fallback_full_rendering_uses_the_legend(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        self.assertIn("[P1 (Blocking)]", raw)
        self.assertIn("[P2 (Non-Blocking)]", raw)

    def test_inline_structured_form_uses_the_legend(self) -> None:
        raw = GH_INLINE.read_text(encoding="utf-8")
        self.assertIn("[<severity> (<compact meaning>)]", raw)
        self.assertIn("[P1 (Blocking)]", raw)

    def test_human_inline_voice_carries_the_same_compact_meaning(self) -> None:
        raw = GH_INLINE.read_text(encoding="utf-8")
        self.assertIn("P2 (Non-Blocking):", raw)
        self.assertNotIn("P2: Retry eligibility", raw)

    def test_no_repeated_explanatory_paragraph_per_finding(self) -> None:
        # The legend is a heading-only parenthetical; assert no finding
        # example additionally spells out "means" / "which means" prose
        # explaining the severity a second time.
        for path in (GH_SUMMARY, GH_INLINE):
            for block in _md_or_text_blocks(path):
                self.assertNotIn("which means", block.lower())
                self.assertNotIn("this means", block.lower())

    def test_shared_templates_document_the_override_as_optional(self) -> None:
        finding_t = _norm(SHARED_FINDING)
        self.assertIn("per-Skill rendering override point", finding_t)
        rendering_t = _norm(SHARED_FINDING_RENDERING)
        self.assertIn("substitutes", rendering_t)
        self.assertIn("local-code-review does not, and its renderings below stay exactly the bare-code form", rendering_t.replace(" .", "."))


class DensityAndDeduplicationGuidance(unittest.TestCase):
    """Explicit, testable density/de-dup guidance for both modes, without a
    rigid global word/line limit."""

    NUMERIC_CAP_PATTERN = re.compile(r"\b\d+[\s-]?(words?|lines?)\b", re.I)

    def test_shared_summary_carries_the_scoped_subsection(self) -> None:
        # Issue #231: this guidance describes the voice itself, not a
        # GitHub-specific mechanism, so it moved into the single shared
        # "Senior voice contract" owner and is no longer scoped
        # "github-pr-review only" — local-code-review now inherits it too
        # through the same existing link. review-summary.md keeps only a
        # pointer to the new owner.
        raw = SHARED_SUMMARY.read_text(encoding="utf-8")
        self.assertIn("### Density, de-duplication, and voice tightening", raw)
        self.assertNotIn(
            "### Density, de-duplication, and voice tightening (`github-pr-review` only)",
            raw,
        )
        t = _norm(SHARED_SUMMARY)
        self.assertIn("Senior voice contract", t)
        self.assertIn("local-code-review inherits it", t)

        rendering_t = _norm(SHARED_FINDING_RENDERING)
        self.assertIn("## Senior voice contract", SHARED_FINDING_RENDERING.read_text(encoding="utf-8"))
        for rule in (
            "never restate the diff",
            "never repeat the same evidence",
            "no numeric word or line cap",
            "scale with the number and complexity of",
        ):
            self.assertIn(rule, rendering_t)

    def test_review_output_wires_the_guidance_in(self) -> None:
        raw = GH_OUTPUT.read_text(encoding="utf-8")
        self.assertIn("### Density and de-duplication", raw)
        t = _norm(GH_OUTPUT)
        self.assertIn("no numeric word or line cap", t)

    def test_no_numeric_cap_introduced_anywhere_in_the_density_guidance(self) -> None:
        for path in (SHARED_SUMMARY, GH_OUTPUT, GH_SUMMARY):
            section_matches = re.findall(
                r"(?:Density[^\n]*\n(?:.*?\n)*?)(?=\n##|\Z)",
                path.read_text(encoding="utf-8"),
            )
            for section in section_matches:
                # "no numeric ... cap" sentences legitimately contain the
                # word "numeric"/"cap"; only flag an actual "<N> words/lines"
                # style limit being introduced.
                self.assertNotRegex(section, self.NUMERIC_CAP_PATTERN)


class SeniorModeVoiceTightening(unittest.TestCase):
    """Senior-mode guidance reduces headings/meta-commentary/repeated
    evidence while every existing evidence/rigor field stays required."""

    def test_scoped_subsection_names_the_voice_rules(self) -> None:
        # Issue #231: these voice rules now live once, in the shared
        # "Senior voice contract" in finding-rendering.md, rather than
        # restated in review-summary.md's own subsection.
        t = _norm(SHARED_FINDING_RENDERING)
        self.assertIn("natural short paragraphs, minimal", t.replace("\n", " "))
        self.assertIn("no meta-commentary", t)

    def test_evidence_rigor_guarantees_still_independently_required(self) -> None:
        # The tightening subsection must not remove/weaken the mandatory
        # core; the finding contract's quality gate is untouched.
        finding_t = _norm(SHARED_FINDING)
        self.assertIn("What? Where? Evidence? Impact? Fix?", finding_t)
        self.assertIn("never reduced to hit a length target", finding_t)

    def test_human_inline_rendering_gets_the_no_meta_commentary_rule(self) -> None:
        t = _norm(SHARED_FINDING_RENDERING)
        self.assertIn("no meta-commentary about the review process", t)


class CompactInlineFindingsReinforced(unittest.TestCase):
    """Inline comment stays the minimum self-contained unit; a fallback
    body finding is never a near-duplicate of its inline comment."""

    def test_inline_template_states_the_rule_explicitly(self) -> None:
        raw = GH_INLINE.read_text(encoding="utf-8")
        self.assertIn("one authoritative representation, minimum self-contained unit", raw)
        t = _norm(GH_INLINE)
        self.assertIn("never a near", t.replace("\n", " "))

    def test_body_template_never_repeats_inline_detail(self) -> None:
        t = _norm(GH_SUMMARY)
        self.assertIn(
            "Do not repeat Evidence / Impact / Fix / Details / multi-paragraph reasoning in the body for a finding that was published inline",
            t,
        )


class NoToolOrModelDisclosure(unittest.TestCase):
    """No packaged github-pr-review resource discloses/advertises the
    underlying agent/model/tool in published review content, and an
    explicit rule prohibits it going forward."""

    DISCLOSURE_PATTERN = re.compile(
        r"generated (with|by)|powered by|anthropic|claude", re.I
    )

    def test_explicit_rule_exists(self) -> None:
        raw = GH_OUTPUT.read_text(encoding="utf-8")
        self.assertIn("## No agent/model/tool disclosure", raw)
        t = _norm(GH_OUTPUT)
        self.assertIn("never disclose or advertise the underlying agent", t)
        self.assertIn(
            "No packaged github-pr-review template, runbook, or policy resource may introduce such a signature",
            t,
        )

    def test_rule_does_not_touch_the_pr_authoring_disclosure_convention(self) -> None:
        # The repo's own contributed-PR AI-assistance disclosure line is a
        # separate, unrelated concern owned outside this packaged Skill.
        raw = GH_OUTPUT.read_text(encoding="utf-8")
        self.assertNotIn("policies/github-issue-pr-authoring.md", raw)

    def test_no_disclosure_signature_in_any_rendered_example(self) -> None:
        for path in GH_DIR.rglob("*.md"):
            for block in _md_or_text_blocks(path):
                cleaned = re.sub(r"claude\.md", "", block, flags=re.I)
                self.assertNotRegex(
                    cleaned,
                    self.DISCLOSURE_PATTERN,
                    f"disclosure-like signature found in a rendered example in {path}",
                )


class GoldenScenarios(unittest.TestCase):
    """Golden/structural scenarios named in the Issue's acceptance
    criteria, built from the documented contract rather than by executing
    a live reviewer (matching this repository's doc-assertion test
    convention)."""

    def test_clean_normal_review_scenario(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        clean_block = re.search(
            r"## Clean review\n\n```markdown\n(.*?)\n```", raw, re.S
        ).group(1)
        self.assertTrue(clean_block.startswith("## Review Summary"))
        self.assertIn("REVIEW CLEAN", clean_block)
        self.assertNotIn("### Findings", clean_block)

    def test_clean_senior_review_scenario(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        senior_block = re.search(
            r"## Concise human-style body \(opt-in\)\n\n.*?```markdown\n(.*?)\n```",
            raw,
            re.S,
        ).group(1)
        self.assertTrue(senior_block.startswith("## Review Summary"))
        # Senior mode omits the structured Findings heading in favor of
        # prose, and never emits review-process/machine language.
        self.assertNotIn("### Findings", senior_block)
        self.assertNotIn("review_mode", senior_block)

    def test_normal_review_with_p0_p1_p2_findings_scenario(self) -> None:
        # Synthesized per the documented finding-list contract (severity
        # legend + summary-pointer form), since no single packaged example
        # currently carries all three severities together.
        synthetic = "\n".join(
            [
                "### Findings",
                "",
                "- **P0 (Critical) — Destructive migration drops data with no backup**",
                "  `db/migrate.py:12`",
                "- **P1 (Blocking) — Authorization provenance can bypass the trusted boundary**",
                "  `src/review/authz.py:142`",
                "- **P2 (Non-Blocking) — Validation output hides the failing check name**",
                "  `scripts/validate.py:117`",
            ]
        )
        for code, legend in SEVERITY_LEGEND.items():
            self.assertIn(legend, synthetic)
        # Structural shape: severity+title on one line, location indented
        # below it — matches the documented summary-pointer rendering.
        for line in ("P0 (Critical) —", "P1 (Blocking) —", "P2 (Non-Blocking) —"):
            self.assertIn(line, synthetic)

    def test_senior_review_with_multiple_findings_scenario(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        senior_block = re.search(
            r"## Concise human-style body \(opt-in\)\n\n.*?```markdown\n(.*?)\n```",
            raw,
            re.S,
        ).group(1)
        legend_mentions = sum(
            senior_block.count(legend) for legend in SEVERITY_LEGEND.values()
        )
        self.assertGreaterEqual(legend_mentions, 2, "expected multiple findings referenced")

    def test_one_finding_published_inline_plus_summary_pointer_scenario(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        fallback_section = re.search(
            r"## Fallback: a finding with no valid inline anchor\n(.*?)\n## ",
            raw,
            re.S,
        ).group(1)
        # The inline-eligible finding appears as a bare summary-pointer
        # line in the body (no Evidence/Impact/Fix block for it) while the
        # no-anchor finding gets its full block.
        self.assertIn("P1 (Blocking) — Authorization provenance", fallback_section)
        self.assertNotIn(
            "F1", fallback_section
        )  # the inline-published finding has no body-side id/full block
        self.assertIn("#### F2 [P2 (Non-Blocking)]", fallback_section)

    def test_both_modes_render_review_summary_heading(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        structured_headings = re.findall(r"^## Review Summary$", raw, re.M)
        self.assertGreaterEqual(len(structured_headings), 4)

    def test_severity_headings_expose_compact_meaning_everywhere(self) -> None:
        for path, needles in (
            (GH_SUMMARY, ["P1 (Blocking)", "P2 (Non-Blocking)"]),
            (GH_INLINE, ["P1 (Blocking)", "P2 (Non-Blocking)"]),
        ):
            raw = path.read_text(encoding="utf-8")
            for needle in needles:
                self.assertIn(needle, raw)

    def test_senior_output_omits_low_value_empty_sections(self) -> None:
        raw = GH_SUMMARY.read_text(encoding="utf-8")
        clean_block = re.search(
            r"## Clean review\n\n```markdown\n(.*?)\n```", raw, re.S
        ).group(1)
        for absent in ("What was done well", "Areas inspected", "no issues"):
            self.assertNotIn(absent, clean_block)


if __name__ == "__main__":
    unittest.main()
