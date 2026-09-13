#!/usr/bin/env python3
"""Structural/semantic regression coverage for Issue #275.

Adds `include_severity_description` — a natural-language, opt-in
canonical invocation option that expands `github-pr-review`'s severity
code (`P0` / `P1` / `P2`) into its reader-visible legend parenthetical
(`P0 (Critical)` / `P1 (Blocking)` / `P2 (Non-Blocking)`) on every
finding-headline surface that Skill owns. Compact (no parenthetical) is
now the default everywhere the legend used to always render (Issue
#223); the option only toggles the parenthetical, never severity itself,
never the headline emphasis, and never anything owned by
`shared/policies/severity.md`.

These are structural/semantic assertions against the canonical
policy/template markdown (this repository's established test pattern —
see `test_github_pr_review_output_tightening_223.py`), not exact-prose or
word-count checks, and not an execution of a live reviewer.

Cross-Skill boundary (also under test): none of this may leak into
`local-code-review`'s own report format, heading, or voice — it defines
no severity legend and is unaffected regardless of this option's value.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

SHARED_INVOCATION_OPTIONS = REPO_ROOT / "shared/policies/invocation-options.md"
SHARED_FINDING = REPO_ROOT / "shared/templates/finding.md"
SHARED_FINDING_RENDERING = REPO_ROOT / "shared/templates/finding-rendering.md"
SHARED_SEVERITY = REPO_ROOT / "shared/policies/severity.md"

GH_OUTPUT = REPO_ROOT / "skills/github-pr-review/policies/review-output.md"
GH_SUMMARY = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
GH_INLINE = REPO_ROOT / "skills/github-pr-review/templates/inline-finding.md"
GH_README = REPO_ROOT / "skills/github-pr-review/README.md"

LOCAL_REPORT = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
LOCAL_RUNBOOK = REPO_ROOT / "skills/local-code-review/runbooks/local-review.md"
LOCAL_SKILL = REPO_ROOT / "skills/local-code-review/SKILL.md"
LOCAL_POLICY_DIR = REPO_ROOT / "skills/local-code-review/policies"

DOCS_FEATURE = REPO_ROOT / "docs/features/severity-description.md"
ARCHITECTURE = REPO_ROOT / "docs/ARCHITECTURE.md"

SEVERITY_LEGEND = {
    "P0": "P0 (Critical)",
    "P1": "P1 (Blocking)",
    "P2": "P2 (Non-Blocking)",
}


def _norm(path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class OptionDefinedInSharedInvocationOptions(unittest.TestCase):
    """`include_severity_description` is one more canonical option in the
    existing invocation-options machinery — no parallel parser."""

    def test_option_is_listed_with_default_false(self) -> None:
        raw = SHARED_INVOCATION_OPTIONS.read_text(encoding="utf-8")
        self.assertIn("`include_severity_description`", raw)
        t = _norm(SHARED_INVOCATION_OPTIONS)
        self.assertIn("include_severity_description — default false for both Skills", t)

    def test_option_is_presentation_only(self) -> None:
        t = _norm(SHARED_INVOCATION_OPTIONS)
        self.assertIn(
            "it never affects whether severity itself is shown, whether the finding headline is emphasized, severity.md's definitions, the blocking rule, or the mechanical decision derivation",
            t,
        )

    def test_local_code_review_is_explicitly_unaffected(self) -> None:
        t = _norm(SHARED_INVOCATION_OPTIONS)
        self.assertIn("local-code-review defines no severity legend at all", t)
        self.assertIn("is unaffected by this option regardless of its value", t)

    def test_phrasings_subsection_exists_with_exhaustive_vocabulary(self) -> None:
        raw = SHARED_INVOCATION_OPTIONS.read_text(encoding="utf-8")
        self.assertIn("### `include_severity_description` phrasings", raw)
        t = _norm(SHARED_INVOCATION_OPTIONS)
        for phrase in (
            "include severity descriptions",
            "show severity descriptions",
            "show blocking/non-blocking labels",
            "keep severity compact",
            "do not include severity descriptions",
            "don't include severity descriptions",
            "show only p0/p1/p2",
        ):
            self.assertIn(phrase, t.lower())
        self.assertIn("this phrase set is exhaustive", t.lower())

    def test_finite_vocabulary_sentence_names_the_new_concept(self) -> None:
        t = _norm(SHARED_INVOCATION_OPTIONS)
        self.assertIn("five canonical option concepts", t)
        self.assertIn("severity description", t)

    def test_precedence_rule_is_not_duplicated_for_this_option(self) -> None:
        # The option reuses the one shared precedence ladder; no
        # option-specific override is introduced.
        raw = SHARED_INVOCATION_OPTIONS.read_text(encoding="utf-8")
        self.assertEqual(
            raw.count("explicit canonical false\n> explicit canonical true"),
            1,
        )


class DefaultRenderingIsCompact(unittest.TestCase):
    """Issue #275 acceptance criteria 1-2: every finding-headline surface
    `github-pr-review` owns defaults to the bare `P0`/`P1`/`P2` code."""

    def _default_examples(self, path) -> str:
        raw = path.read_text(encoding="utf-8")
        # Exclude the dedicated opt-in section(s) so this class asserts
        # only on default-mode content.
        raw = re.split(r"\n## Severity description \(opt-in\)\n", raw)[0]
        return raw

    def test_summary_pointer_default_examples_are_compact(self) -> None:
        default_text = self._default_examples(GH_SUMMARY)
        self.assertIn("P1 — Authorization provenance", default_text)
        self.assertIn("P1 — Stale HEAD", default_text)
        self.assertIn("P2 — Validation output hides", default_text)
        for legend in SEVERITY_LEGEND.values():
            self.assertNotIn(legend, default_text)

    def test_fallback_full_rendering_default_examples_are_compact(self) -> None:
        default_text = self._default_examples(GH_SUMMARY)
        self.assertIn("#### F2 [P2] Config schema drift", default_text)
        self.assertIn("#### F3 [P1] `sanitize_path` bypass", default_text)

    def test_human_full_rendering_default_example_is_compact(self) -> None:
        default_text = self._default_examples(GH_SUMMARY)
        self.assertIn("#### F2 P2: Config schema drift", default_text)

    def test_readme_worked_example_is_compact(self) -> None:
        raw = GH_README.read_text(encoding="utf-8")
        self.assertIn("**P0 — Endpoint skips the ownership check", raw)
        self.assertIn("**P1 — Pagination can stop after page one", raw)
        self.assertIn("**P2 — Validation output hides", raw)
        for legend in SEVERITY_LEGEND.values():
            self.assertNotIn(legend, raw)

    def test_inline_structured_default_example_is_compact(self) -> None:
        raw = GH_INLINE.read_text(encoding="utf-8")
        example = re.search(r"## Example\n\n```text\n(.*?)\n```", raw, re.S).group(1)
        self.assertIn("[P1] Incomplete pagination", example)
        for legend in SEVERITY_LEGEND.values():
            self.assertNotIn(legend, example)

    def test_human_inline_default_examples_are_compact(self) -> None:
        raw = GH_INLINE.read_text(encoding="utf-8")
        section = re.search(
            r"## Human-rendered inline finding \(opt-in\)\n(.*)\Z",
            raw,
            re.S,
        ).group(1)
        self.assertIn("P1: Paginated file listing stops after page 1", section)
        self.assertIn(
            "P2: Sync and async retry paths decide eligibility", section
        )


class OptInExpandedRenderingIsPinned(unittest.TestCase):
    """Issue #275 acceptance criteria 3, 5-6, 10: enabling
    `include_severity_description` expands every surface's headline
    consistently, inside the same emphasized unit, never as a trailing
    unemphasized addition."""

    def _opt_in_section(self, path, heading_pattern: str) -> str:
        raw = path.read_text(encoding="utf-8")
        match = re.search(
            heading_pattern + r"\n(.*?)(?:\n## |\Z)", raw, re.S
        )
        self.assertIsNotNone(match, f"missing opt-in section in {path}")
        return match.group(1)

    def test_summary_external_review_opt_in_section_exists_and_is_pinned(self) -> None:
        section = self._opt_in_section(
            GH_SUMMARY, r"## Severity description \(opt-in\)"
        )
        # Summary-pointer form: severity + description + title inside one
        # bold unit, never the title bolded alone.
        self.assertIn(
            "**P1 (Blocking) — Authorization provenance can bypass the trusted boundary**",
            section,
        )
        self.assertNotRegex(section, r"P1 \(Blocking\) — \*\*Authorization")
        # Full fallback rendering: parenthetical inside the heading line.
        self.assertIn(
            "#### F2 [P2 (Non-Blocking)] Config schema drift spans three unlinked files",
            section,
        )
        # Human full rendering composes with human_review_output.
        self.assertIn(
            "#### F2 P2 (Non-Blocking): Config schema drift spans three unlinked files",
            section,
        )

    def test_inline_finding_opt_in_section_exists_and_is_pinned(self) -> None:
        section = self._opt_in_section(
            GH_INLINE, r"## Severity description \(opt-in\)"
        )
        self.assertIn(
            "[P1 (Blocking)] Incomplete pagination can produce a false clean review",
            section,
        )

    def test_human_inline_composes_with_the_option(self) -> None:
        raw = GH_INLINE.read_text(encoding="utf-8")
        self.assertIn(
            "P1 (Blocking): Paginated file listing stops after page 1", raw
        )
        self.assertIn(
            "P2 (Non-Blocking): Sync and async retry paths decide eligibility",
            raw,
        )

    def test_generic_structured_inline_placeholder_documents_both_forms(self) -> None:
        raw = GH_INLINE.read_text(encoding="utf-8")
        self.assertIn("[<severity>]", raw)
        self.assertIn("[<severity> (<compact meaning>)]", raw)


class EmphasizedHeadlineContract(unittest.TestCase):
    """Issue #275's second gap: an explicit, surface-by-surface contract
    that the complete headline is emphasized as one unit."""

    def test_review_output_states_the_contract_explicitly(self) -> None:
        raw = GH_OUTPUT.read_text(encoding="utf-8")
        self.assertIn("### Emphasized-headline contract, by surface", raw)
        t = _norm(GH_OUTPUT)
        self.assertIn("Never P1 — Title", t.replace("**", ""))
        self.assertIn("one emphasized unit", t)

    def test_contract_names_all_four_surfaces(self) -> None:
        t = _norm(GH_OUTPUT)
        for marker in (
            "Summary-pointer",
            "Full finding heading",
            "Structured inline finding",
            "Human-review rendering",
        ):
            self.assertIn(marker, t)

    def test_shared_finding_rendering_notes_the_option_gates_the_override(self) -> None:
        t = _norm(SHARED_FINDING_RENDERING)
        self.assertIn("only when that skill's own gating invocation option resolves true", t.lower())


class SeverityModelUnchanged(unittest.TestCase):
    """Non-goals: shared/policies/severity.md is untouched; blocking rule
    and decision derivation are unaffected by this presentation option."""

    def test_severity_policy_never_mentions_the_new_option(self) -> None:
        raw = SHARED_SEVERITY.read_text(encoding="utf-8")
        self.assertNotIn("include_severity_description", raw)

    def test_severity_policy_blocking_rule_language_intact(self) -> None:
        t = _norm(SHARED_SEVERITY)
        self.assertIn("Critical / Blocking", t)
        self.assertIn("Significant / Blocking", t)
        self.assertIn("Non-Blocking", t)

    def test_finding_field_contract_documents_the_gate(self) -> None:
        t = _norm(SHARED_FINDING)
        self.assertIn("per-skill rendering override point".lower(), t.lower())
        self.assertIn(
            "the bare [p0] / [p1] / [p2] form is this skill's own default too".lower(),
            t.lower(),
        )


class LocalCodeReviewIsProvablyUnaffected(unittest.TestCase):
    """Acceptance criterion 11: no local-code-review regression."""

    def _git_blob_sha1(self, path) -> str:
        import hashlib

        data = path.read_bytes()
        header = f"blob {len(data)}\0".encode()
        return hashlib.sha1(header + data).hexdigest()

    def test_local_report_has_no_severity_legend_or_new_option_leak(self) -> None:
        text = LOCAL_REPORT.read_text(encoding="utf-8")
        for legend in SEVERITY_LEGEND.values():
            self.assertNotIn(legend, text)
        self.assertNotIn("include_severity_description", text)

    def test_local_policy_and_runbook_have_no_new_option_leak(self) -> None:
        for path in (LOCAL_RUNBOOK, LOCAL_SKILL):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("include_severity_description", text)
        for path in LOCAL_POLICY_DIR.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("include_severity_description", text)


class OptionalFeatureGuideExists(unittest.TestCase):
    """Documentation for the new capability follows the repo's existing
    docs/features/ guide convention (see human-review-output.md)."""

    def test_guide_file_exists_and_states_the_default(self) -> None:
        self.assertTrue(DOCS_FEATURE.is_file())
        t = _norm(DOCS_FEATURE)
        self.assertIn("compact", t.lower())
        self.assertIn("default", t.lower())

    def test_guide_is_indexed_in_features_readme(self) -> None:
        raw = (REPO_ROOT / "docs/features/README.md").read_text(encoding="utf-8")
        self.assertIn("severity-description.md", raw)
        self.assertIn("include_severity_description", raw)


class ArchitectureSystemMapIsUpToDate(unittest.TestCase):
    """The concise system map in docs/ARCHITECTURE.md enumerates every
    presentation-only invocation option by name; this new option must be
    included in both its capability-list bullet and its per-option
    "presentation-only" bullet in section 9, alongside its siblings."""

    def test_capability_list_names_the_new_option(self) -> None:
        raw = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn("`include_severity_description`", raw)

    def test_reasoning_vs_delivery_section_has_its_own_bullet(self) -> None:
        t = _norm(ARCHITECTURE)
        self.assertIn(
            "the severity-legend parenthetical is presentation-only".lower(),
            t.lower(),
        )
        self.assertIn("include_severity_description", t)


if __name__ == "__main__":
    unittest.main()
