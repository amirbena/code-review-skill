"""Shared paths, constants, and manifest helpers for the packaging-boundary
guard tests split across this package — see the package docstring in
tests/integration/packaging/__init__.py for what the guard protects.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.support.paths import REPO_ROOT

PACKAGE_SCRIPT = REPO_ROOT / "scripts" / "package-skills.sh"
PACKAGE_MANIFEST = REPO_ROOT / "scripts" / "package-manifest.json"
PACKAGE_MANIFEST_HELPER = REPO_ROOT / "scripts" / "package_manifest.py"

# The test-only reference modules live in tests/reference/; the PR
# simulation harness lives in tests/support/.
REFERENCE_DIR = REPO_ROOT / "tests" / "reference"
SUPPORT_DIR = REPO_ROOT / "tests" / "support"


def _reference_module_path(name: str) -> Path:
    if name == "pr_simulation.py":
        return SUPPORT_DIR / name
    # tests/reference/*.py now lives under capability sub-packages
    # (issue #217): find the one file matching this bare filename.
    matches = list(REFERENCE_DIR.rglob(name))
    assert len(matches) == 1, f"expected exactly one match for {name}, found {matches}"
    return matches[0]


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
    "context_evidence.py",
    "repository_intelligence.py",
    "pr_checkout.py",
    "pr_simulation.py",
    "parallel_review.py",
    "repository_instructions.py",
    "remediation_guidance.py",
    "finding_contract.py",
    "finding_confidence.py",
    "invocation_options.py",
    "finding_identity.py",
    "runtime_validation.py",
    "delta_re_review.py",
    "benchmark_fixture.py",
    "benchmark_runner.py",
    "benchmark_report.py",
    "benchmark_match.py",
    "benchmark_metrics.py",
    "benchmark_severity.py",
    "benchmark_dupes.py",
)


def _package_manifest() -> dict:
    return json.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))


def _skill_destinations(target: str) -> list[str]:
    return [entry["destination"] for entry in _package_manifest()["skills"][target]["files"]]


def _shared_destinations() -> list[str]:
    return [entry["destination"] for entry in _package_manifest()["shared_files"]]


SH = REPO_ROOT / "scripts" / "package-skills.sh"
PS1 = REPO_ROOT / "scripts" / "package-skills.ps1"
