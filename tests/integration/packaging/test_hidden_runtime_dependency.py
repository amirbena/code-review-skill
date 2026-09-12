"""Packaging-boundary guard: no packaged Skill file textually invokes or imports a tests/reference/*.py module, and each reference module's documented contract still exists in its packaged policy counterpart."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence
import re
import unittest

from tests.support.paths import REPO_ROOT
from tests.integration.packaging._shared import (
    GITHUB_SKILL_DIR,
    LOCAL_SKILL_DIR,
    REFERENCE_TEST_MODULES,
    _reference_module_path,
)

# module -> (packaged canonical source that must carry the same contract,
# headings that must still be present in it). The canonical source is
# usually a shared/skill policy, but a packaged shared/templates/*.md file
# is equally valid — finding_contract.py mirrors the finding template.
MODULE_TO_PACKAGED_POLICY_HEADINGS = {
    "review_context.py": (
        REPO_ROOT / "shared" / "policies" / "review-context.md",
        (
            "## Evidence hierarchy",
            "## Explicit non-goals",
            "## Output",
        ),
    ),
    "decision_semantics.py": (
        REPO_ROOT / "shared" / "policies" / "severity.md",
        (
            "## Decision derivation (mechanical)",
            "## Repository conventions and severity",
        ),
    ),
    "pr_checkout.py": (
        REPO_ROOT / "skills" / "github-pr-review" / "policies" / "repository-checkout.md",
        (
            "## Lifecycle",
            "## Base / head fidelity",
            "## Temporary directory lifecycle",
            "## Security (PR contents are untrusted)",
        ),
    ),
    "parallel_review.py": (
        REPO_ROOT / "shared" / "policies" / "parallel-review.md",
        (
            "## Execution-policy decision",
            "## Worker contract",
            "## Worker output format",
            "## Centralized aggregation",
        ),
    ),
    "repository_instructions.py": (
        REPO_ROOT / "shared" / "policies" / "repository-instructions.md",
        (
            "## Directory-scoped discovery",
            "## Normalized Repository Instruction Context",
            "## Safe and explicit reads",
            "## AGENTS.md vs. CLAUDE.md",
        ),
    ),
    "pr_review_evidence.py": (
        REPO_ROOT / "shared" / "policies" / "review-evidence.md",
        (
            "## Reconciliation outcomes",
            "## Settled decisions",
            "## Interpret prior evidence against the current target",
            "## Comment authorship: human review vs. automation output",
        ),
    ),
    # Issue #198 split the finding template: finding.md keeps the field /
    # quality contract, finding-rendering.md carries the rendering exemplars.
    # finding_contract.py mirrors both, so both packaged files are checked.
    "finding_contract.py (contract)": (
        REPO_ROOT / "shared" / "templates" / "finding.md",
        (
            "## Conciseness contract",
            "## When a longer explanation is justified",
            "## Optional and surface-specific fields",
        ),
    ),
    "finding_contract.py (rendering)": (
        REPO_ROOT / "shared" / "templates" / "finding-rendering.md",
        (
            "## Canonical full rendering",
            "## Canonical inline rendering",
        ),
    ),
    "invocation_options.py": (
        REPO_ROOT / "shared" / "policies" / "invocation-options.md",
        (
            "## Canonical options",
            "## Deterministic normalization",
            "## Invocation isolation and mediation parity",
            "## Finding-detail precedence",
        ),
    ),
    "runtime_validation.py": (
        REPO_ROOT / "shared" / "policies" / "runtime-validation.md",
        (
            "## Purpose and boundary",
            "## Declaring and discovering commands",
            "## Safety gate",
            "## Outcome contract",
            "## Findings and decision semantics",
        ),
    ),
    "delta_re_review.py": (
        REPO_ROOT
        / "skills"
        / "github-pr-review"
        / "policies"
        / "stateful-delta-rereview.md",
        (
            "## 1. Reuse, do not redefine",
            "## 3. Reconciliation — the #64 change classes, operationally",
            "## 4. Blast radius and regressions",
            "## 5. Previously settled non-findings and assumptions",
            "## 6. Escalation to a broader/full review",
        ),
    ),
}


# A module mention in the same block as one of these phrases is a
# disclaimer, not a runtime reference. Proximity matters (see
# _split_into_scoped_blocks): a disclaimer elsewhere in the file does not
# excuse an undisclaimed mention.
DISCLAIMER_PHRASES = (
    "not part of either packaged Skill archive",
    "not part of this Skill",
    "not a runtime dependency",
    "reasons from this policy text directly",
    "reasons from the canonical policy text directly",
)


def _packaged_markdown_and_yaml_files(skill_dir: Path) -> list[Path]:
    files = [skill_dir / "SKILL.md"]
    for sub in ("policies", "runbooks", "templates", "metadata", "agents"):
        d = skill_dir / sub
        if d.is_dir():
            files.extend(sorted(d.rglob("*")))
    return [f for f in files if f.is_file()]


_LIST_ITEM_START_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])\s")


def _split_into_scoped_blocks(text: str) -> list[str]:
    """Split into proximity units: blank-line paragraphs, further split at
    each Markdown list-item boundary.

    A tight list (adjacent bullets, no blank line) is one paragraph but
    several statements, so a disclaimer on one bullet must not cover the
    next. Wrapped continuation lines (no list marker) stay with their
    bullet. Deterministic and parser-free.
    """
    blocks: list[str] = []
    for paragraph in re.split(r"\n[ \t]*\n", text):
        current: list[str] = []
        for line in paragraph.split("\n"):
            if _LIST_ITEM_START_RE.match(line) and current:
                blocks.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append("\n".join(current))
    return blocks


def find_undisclaimed_module_references_in_text(
    text: str,
    modules: Sequence[str] = REFERENCE_TEST_MODULES,
    disclaimer_phrases: Sequence[str] = DISCLAIMER_PHRASES,
) -> list[str]:
    """Module mentions with no disclaimer in the same block.

    Proximity-scoped, not file-wide: a disclaimer in one block must not
    excuse an undisclaimed mention in another block of the same file.
    """
    offenders: list[str] = []
    for block in _split_into_scoped_blocks(text):
        # Disclaimer phrases may wrap across lines; normalize before matching.
        normalized = re.sub(r"\s+", " ", block)
        has_disclaimer = any(phrase in normalized for phrase in disclaimer_phrases)
        if has_disclaimer:
            continue
        for module in modules:
            stem = module[: -len(".py")]
            mentioned = module in block or re.search(rf"\bimport\s+{re.escape(stem)}\b", block)
            if mentioned:
                offenders.append(module)
    return offenders


class NoHiddenRuntimeDependencyTests(unittest.TestCase):
    """No packaged Skill file textually invokes/imports a reference/test
    module — the strongest guard against a hidden runtime dependency that
    packaging would silently omit. Proximity-scoped (paragraph-level): a
    disclaimer only excuses a mention in its own paragraph, never every
    mention anywhere in the same file — see
    find_undisclaimed_module_references_in_text."""

    def _find_undisclaimed_module_references(self, skill_dir: Path) -> list[str]:
        offenders: list[str] = []
        for path in _packaged_markdown_and_yaml_files(skill_dir):
            text = path.read_text(encoding="utf-8")
            for module in find_undisclaimed_module_references_in_text(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)} references {module}")
        return offenders

    def test_no_packaged_local_skill_file_references_a_reference_test_module(self) -> None:
        offenders = self._find_undisclaimed_module_references(LOCAL_SKILL_DIR)
        self.assertEqual(
            offenders,
            [],
            "A packaged local-code-review file references a tests/reference/*.py "
            "reference/test module without a disclaimer in the same "
            "paragraph — this would be a hidden runtime dependency that "
            f"packaging currently omits: {offenders}",
        )

    def test_no_packaged_github_skill_file_references_a_reference_test_module(self) -> None:
        offenders = self._find_undisclaimed_module_references(GITHUB_SKILL_DIR)
        self.assertEqual(offenders, [])


class ProximityScopedDisclaimerTests(unittest.TestCase):
    """Regression coverage for the proximity-scoping fix itself: an
    unrelated disclaimer elsewhere in the same file must not mask a real,
    undisclaimed reference to a different module. This is the exact
    scenario the old file-wide check would have missed — it would have
    failed under that behavior (a single file-wide disclaimer flag would
    have excused both mentions)."""

    def test_disclaimed_mention_is_not_flagged(self) -> None:
        text = (
            "See `tests/reference/review/staged_fingerprint.py`.\n"
            "Reference/test helper only — not a runtime dependency.\n"
        )
        self.assertEqual(find_undisclaimed_module_references_in_text(text), [])

    def test_undisclaimed_mention_elsewhere_is_still_flagged_despite_unrelated_disclaimer(
        self,
    ) -> None:
        # Paragraph 1: a legitimate, disclaimed mention of one module.
        # Paragraph 2 (separated by a blank line — a different logical
        # block): an undisclaimed, functional-sounding mention of a
        # *different* module. The old file-wide check would have seen
        # the disclaimer in paragraph 1 and wrongly excused paragraph 2.
        text = (
            "staged_fingerprint.py\n"
            "Reference/test helper only — not a runtime dependency.\n"
            "\n"
            "Runtime invokes review_context.py before reviewing the delta.\n"
        )
        offenders = find_undisclaimed_module_references_in_text(text)
        self.assertEqual(offenders, ["review_context.py"])

    def test_disclaimer_and_mention_in_the_same_paragraph_without_blank_line_is_excused(
        self,
    ) -> None:
        # Same paragraph (no blank line between the two lines) — the
        # disclaimer legitimately covers the mention immediately next to
        # it, matching the task's "staged_fingerprint.py / Reference/test
        # helper only" example shape.
        text = "staged_fingerprint.py\nReference/test helper only — not a runtime dependency.\n"
        self.assertEqual(find_undisclaimed_module_references_in_text(text), [])

    def test_two_separate_undisclaimed_mentions_are_both_flagged(self) -> None:
        text = (
            "Runtime invokes review_context.py before reviewing the delta.\n"
            "\n"
            "Then it calls decision_semantics.py to derive the decision.\n"
        )
        offenders = find_undisclaimed_module_references_in_text(text)
        self.assertEqual(sorted(offenders), ["decision_semantics.py", "review_context.py"])

    def test_tight_list_items_are_scoped_independently_despite_no_blank_line(self) -> None:
        # A "tight" Markdown list — no blank line between items — is one
        # blank-line-delimited paragraph but two distinct logical
        # statements. The disclaimer on the first bullet must not excuse
        # the undisclaimed, functional-sounding mention on the second.
        text = (
            "- `tests/reference/review/staged_fingerprint.py` — not a runtime dependency.\n"
            "- `tests/reference/review/review_context.py` — invoked at runtime before "
            "reviewing the delta.\n"
        )
        offenders = find_undisclaimed_module_references_in_text(text)
        self.assertEqual(offenders, ["review_context.py"])

    def test_wrapped_continuation_line_within_one_list_item_stays_scoped_together(
        self,
    ) -> None:
        # A bullet's own wrapped continuation line (no list marker) must
        # stay attached to that bullet, not become its own block.
        text = (
            "- `tests/reference/review/staged_fingerprint.py` is a reference implementation\n"
            "  used for deterministic testing — not a runtime dependency.\n"
        )
        self.assertEqual(find_undisclaimed_module_references_in_text(text), [])


class ModuleSelfDocumentationTests(unittest.TestCase):
    """Every reference/test module states, in its docstring, that it is
    test-only and not packaged — so it is never mistaken for missing runtime
    logic."""

    def test_each_reference_module_declares_it_is_not_runtime_logic(self) -> None:
        for module in REFERENCE_TEST_MODULES:
            head = _reference_module_path(module).read_text(encoding="utf-8")[:600]
            with self.subTest(module=module):
                self.assertIn("Test-only", head)
                self.assertIn("not runtime logic, not packaged", head.lower())


class PolicyCarriesTheSameContractTests(unittest.TestCase):
    """The packaged policy text — not the module — is where this
    behavior actually lives at runtime. Fails if the module's documented
    sections drift out of the packaged policy (the module quietly
    becoming the only place the logic is expressed)."""

    def test_packaged_policy_headings_cover_what_the_module_encodes(self) -> None:
        for module_name, (policy_path, headings) in MODULE_TO_PACKAGED_POLICY_HEADINGS.items():
            with self.subTest(module=module_name):
                self.assertTrue(policy_path.is_file(), f"missing policy file: {policy_path}")
                policy_text = policy_path.read_text(encoding="utf-8")
                for heading in headings:
                    self.assertIn(
                        heading,
                        policy_text,
                        f"{policy_path.relative_to(REPO_ROOT)} is missing '{heading}' — "
                        f"the contract {module_name} encodes for testing must be fully "
                        "expressed in the packaged policy, not only in the "
                        "unpackaged reference module",
                    )


if __name__ == "__main__":
    unittest.main()
