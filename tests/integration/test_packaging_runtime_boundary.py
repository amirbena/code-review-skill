#!/usr/bin/env python3
"""Guards the packaging boundary: the tests/reference/*.py reference modules
stay test-only and out of both Skill archives.

Fails if a refactor adds one to a package file list, makes a packaged file
import/invoke one, or lets a module's contract drift out of its packaged
policy. Archive-content checks need zip/unzip and skip explicitly otherwise.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
import zipfile
from pathlib import Path
from typing import Sequence

from tests.support.paths import REPO_ROOT

PACKAGE_SCRIPT = REPO_ROOT / "scripts" / "package-skills.sh"

# The test-only reference modules live in tests/reference/; the PR
# simulation harness lives in tests/support/.
REFERENCE_DIR = REPO_ROOT / "tests" / "reference"
SUPPORT_DIR = REPO_ROOT / "tests" / "support"


def _reference_module_path(name: str) -> Path:
    return (SUPPORT_DIR if name == "pr_simulation.py" else REFERENCE_DIR) / name
LOCAL_SKILL_DIR = REPO_ROOT / "skills" / "local-code-review"
GITHUB_SKILL_DIR = REPO_ROOT / "skills" / "github-pr-review"
DIST_DIR = REPO_ROOT / "dist"

# The reference modules this test guards — none is a runtime dependency.
REFERENCE_TEST_MODULES = (
    "current_evidence.py",
    "review_context.py",
    "decision_semantics.py",
    "pr_context_reconciliation.py",
    "pr_review_evidence.py",
    "reviewer_ownership.py",
    "staged_fingerprint.py",
    "jira_context.py",
    "pr_checkout.py",
    "pr_simulation.py",
    "parallel_review.py",
    "repository_instructions.py",
    "remediation_guidance.py",
)

# module -> (packaged policy that must carry the same contract, headings that
# must still be present in it).
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
}


def _extract_local_skill_file_list(script_text: str) -> list[str]:
    # The local-code-review package_skill invocation looks like:
    #   package_skill "local-code-review" "local-code-review-skill" \
    #     "agents/openai.yaml" \
    #     ...
    match = re.search(
        r'package_skill "local-code-review" "local-code-review-skill" \\\n(.*?)\nfi',
        script_text,
        re.S,
    )
    if not match:
        raise AssertionError("could not locate local-code-review package_skill invocation")
    return re.findall(r'"([^"]+)"', match.group(1))


SH = REPO_ROOT / "scripts" / "package-skills.sh"
PS1 = REPO_ROOT / "scripts" / "package-skills.ps1"


def _sh_array(text: str, name: str) -> list[str]:
    m = re.search(rf'{re.escape(name)}=\((.*?)\)', text, re.S)
    if not m:
        raise AssertionError(f"array {name} not found in package-skills.sh")
    return re.findall(r'"([^"]+)"', m.group(1))


def _ps1_array(text: str, name: str) -> list[str]:
    m = re.search(rf'\${re.escape(name)}\s*=\s*@\((.*?)\)', text, re.S)
    if not m:
        raise AssertionError(f"array ${name} not found in package-skills.ps1")
    return re.findall(r'"([^"]+)"', m.group(1))


def _sh_skill_files(text: str, skill: str) -> list[str]:
    m = re.search(rf'package_skill "{re.escape(skill)}" "[^"]+" \\\n(.*?)\n(?:\s*for |\}}|fi)', text, re.S)
    if not m:
        raise AssertionError(f"package_skill {skill} not found in package-skills.sh")
    return re.findall(r'"([^"]+)"', m.group(1))


def _ps1_skill_files(text: str, skill: str) -> list[str]:
    m = re.search(rf'-SkillName "{re.escape(skill)}"[^@]*-SkillFiles @\((.*?)\)', text, re.S)
    if not m:
        raise AssertionError(f"Package-Skill {skill} not found in package-skills.ps1")
    return re.findall(r'"([^"]+)"', m.group(1))


class PackagingScriptParityTests(unittest.TestCase):
    """The shell and PowerShell packaging scripts must ship the same files.
    pwsh may be unavailable to execute; this compares the declared lists
    statically so a drift still fails CI."""

    def setUp(self) -> None:
        self.sh = SH.read_text(encoding="utf-8")
        self.ps1 = PS1.read_text(encoding="utf-8")

    def test_shared_policy_lists_match(self) -> None:
        self.assertEqual(
            _sh_array(self.sh, "shared_policies"),
            _ps1_array(self.ps1, "sharedPolicies"),
        )

    def test_shared_template_lists_match(self) -> None:
        self.assertEqual(
            _sh_array(self.sh, "shared_templates"),
            _ps1_array(self.ps1, "sharedTemplates"),
        )

    def test_local_skill_file_lists_match(self) -> None:
        self.assertEqual(
            _sh_skill_files(self.sh, "local-code-review"),
            _ps1_skill_files(self.ps1, "local-code-review"),
        )

    def test_github_skill_file_lists_match(self) -> None:
        self.assertEqual(
            _sh_skill_files(self.sh, "github-pr-review"),
            _ps1_skill_files(self.ps1, "github-pr-review"),
        )

    def test_new_shared_policies_are_in_both(self) -> None:
        for name in ("review-context.md", "review-evidence.md", "parallel-review.md"):
            self.assertIn(name, _sh_array(self.sh, "shared_policies"))
            self.assertIn(name, _ps1_array(self.ps1, "sharedPolicies"))

    def test_new_github_policies_are_in_both(self) -> None:
        for name in (
            "policies/review-context.md",
            "policies/review-evidence.md",
            "policies/repository-checkout.md",
            "policies/parallel-review.md",
        ):
            self.assertIn(name, _sh_skill_files(self.sh, "github-pr-review"))
            self.assertIn(name, _ps1_skill_files(self.ps1, "github-pr-review"))


class DeclaredPackageFileListTests(unittest.TestCase):
    """Structural check on scripts/package-skills.sh itself — no build
    required, so this always runs."""

    def setUp(self) -> None:
        self.script_text = PACKAGE_SCRIPT.read_text(encoding="utf-8")
        self.local_files = _extract_local_skill_file_list(self.script_text)

    def test_local_file_list_is_non_empty_and_sane(self) -> None:
        self.assertIn("SKILL.md", self.local_files + ["SKILL.md"])  # always copied separately
        self.assertIn("policies/review-context.md", self.local_files)
        self.assertIn("policies/pr-context.md", self.local_files)

    def test_declared_file_list_contains_no_python_files(self) -> None:
        python_entries = [f for f in self.local_files if f.endswith(".py")]
        self.assertEqual(
            python_entries,
            [],
            "package-skills.sh declares a .py file for local-code-review — "
            "this is a Markdown/YAML-only Skill package; a .py entry here "
            "means a reference/test module was mistakenly wired into "
            "packaging without becoming a genuine, reviewed runtime "
            f"dependency: {python_entries}",
        )

    def test_none_of_the_reference_test_modules_are_declared(self) -> None:
        for module in REFERENCE_TEST_MODULES:
            with self.subTest(module=module):
                self.assertNotIn(
                    module,
                    self.local_files,
                    f"{module} must not be declared in package-skills.sh's "
                    "local-code-review file list unless it has genuinely "
                    "become a runtime dependency (Contract B) — see "
                    "tests/integration/test_packaging_runtime_boundary.py module "
                    "docstring",
                )


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
            "See `tests/reference/staged_fingerprint.py`.\n"
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
            "- `tests/reference/staged_fingerprint.py` — not a runtime dependency.\n"
            "- `tests/reference/review_context.py` — invoked at runtime before "
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
            "- `tests/reference/staged_fingerprint.py` is a reference implementation\n"
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


@unittest.skipUnless(
    shutil.which("zip") and shutil.which("unzip"),
    "zip/unzip not available on PATH — cannot build/inspect the archive",
)
class BuiltArchiveContentTests(unittest.TestCase):
    """End-to-end confirmation: build the real local-code-review archive
    and inspect its actual contents, not just the declared file list."""

    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [str(PACKAGE_SCRIPT), "local"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"package-skills.sh local failed:\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        archive_path = DIST_DIR / "local-code-review-skill.zip"
        if not archive_path.is_file():
            raise AssertionError(f"expected archive not found: {archive_path}")
        with zipfile.ZipFile(archive_path) as zf:
            cls.archive_names = set(zf.namelist())
            cls.review_scope_text = zf.read(
                "shared/policies/review-scope.md"
            ).decode("utf-8")
            cls.remediation_text = zf.read(
                "shared/policies/remediation-guidance.md"
            ).decode("utf-8")

    def test_archive_contains_no_python_files(self) -> None:
        python_files = {n for n in self.archive_names if n.endswith(".py")}
        self.assertEqual(
            python_files,
            set(),
            f"packaged local-code-review archive must contain no .py files, found: {python_files}",
        )

    def test_archive_contains_the_review_context_policy(self) -> None:
        self.assertIn("policies/review-context.md", self.archive_names)

    def test_archive_contains_every_context_related_runtime_file(self) -> None:
        # The complete, minimal set of context-related files this Skill
        # actually depends on at runtime — policy + template + runbook +
        # entry point, all Markdown, all consumed by the LLM reading them.
        required = {
            "SKILL.md",
            "policies/review-context.md",
            "policies/pr-context.md",
            "runbooks/local-review.md",
            "templates/local-review-report.md",
            "shared/policies/severity.md",
            "shared/policies/review-scope.md",
            "shared/policies/review-context.md",
            "shared/policies/review-evidence.md",
        }
        missing = required - self.archive_names
        self.assertEqual(missing, set(), f"archive missing required runtime file(s): {missing}")

    def test_archive_contains_root_cause_model_completeness_policy(self) -> None:
        self.assertIn(
            "## Root-cause and model-completeness pass", self.review_scope_text
        )

    def test_archive_contains_shared_remediation_policy(self) -> None:
        self.assertIn("## Evidence-grounded direction", self.remediation_text)
        self.assertIn("include_fix_prompt", self.remediation_text)

    def test_archive_does_not_contain_reference_test_modules(self) -> None:
        for module in REFERENCE_TEST_MODULES:
            with self.subTest(module=module):
                matches = {n for n in self.archive_names if n.endswith(module)}
                self.assertEqual(matches, set())


@unittest.skipUnless(
    shutil.which("zip") and shutil.which("unzip"),
    "zip/unzip not available on PATH — cannot build/inspect the archive",
)
class GitHubArchiveContentTests(unittest.TestCase):
    """The packaged github-pr-review archive carries every policy needed to
    instruct repository-backed review and portable concurrency, and no
    Python."""

    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [str(PACKAGE_SCRIPT), "github"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"package-skills.sh github failed:\n{result.stdout}\n{result.stderr}"
            )
        with zipfile.ZipFile(DIST_DIR / "github-pr-review-skill.zip") as zf:
            cls.names = set(zf.namelist())
            cls.review_scope_text = zf.read(
                "shared/policies/review-scope.md"
            ).decode("utf-8")
            cls.remediation_text = zf.read(
                "shared/policies/remediation-guidance.md"
            ).decode("utf-8")

    def test_no_python_and_no_reference_modules(self) -> None:
        self.assertEqual({n for n in self.names if n.endswith(".py")}, set())
        for module in REFERENCE_TEST_MODULES:
            self.assertEqual({n for n in self.names if n.endswith(module)}, set())

    def test_repository_backed_and_parallel_policies_are_packaged(self) -> None:
        required = {
            "SKILL.md",
            "policies/github-review.md",
            "policies/repository-checkout.md",
            "policies/parallel-review.md",
            "runbooks/active-pr-review.md",
            "runbooks/passive-pr-review.md",
            "shared/policies/parallel-review.md",
            "shared/policies/review-scope.md",
        }
        self.assertEqual(required - self.names, set())

    def test_root_cause_model_completeness_policy_is_packaged(self) -> None:
        self.assertIn(
            "## Root-cause and model-completeness pass", self.review_scope_text
        )

    def test_shared_remediation_policy_is_packaged(self) -> None:
        self.assertIn("## Skill-specific detail", self.remediation_text)
        self.assertIn("github-pr-review", self.remediation_text)

    def test_repo_dev_docs_are_not_packaged(self) -> None:
        for n in self.names:
            self.assertNotIn("runtime-parallelism.md", n)
            self.assertNotIn("ARCHITECTURE.md", n)


if __name__ == "__main__":
    unittest.main()
