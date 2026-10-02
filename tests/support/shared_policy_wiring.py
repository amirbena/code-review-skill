"""Parametrized wiring-contract mixins shared by the shared-policy doc tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import (
    GITHUB_ACTIVE_RUNBOOK,
    GITHUB_PASSIVE_RUNBOOK,
    GITHUB_REASONING,
    GITHUB_REVIEW_INDEX,
    GITHUB_SKILL_DIR,
    GITHUB_SKILL_MD,
    LOCAL_RUNBOOK,
    LOCAL_SKILL_DIR,
    LOCAL_SKILL_MD,
    PARALLEL_REVIEW,
    REVIEW_SCOPE,
)
from tests.support.policy_docs import extract_section
from tests.support.policy_docs import load_normalized_text as _norm

SHARED_README = REPO_ROOT / "shared/policies/README.md"
PACKAGE_MANIFEST = REPO_ROOT / "scripts/packaging/package-manifest.json"
LOCAL_TEMPLATE = LOCAL_SKILL_DIR / "templates/local-review-report.md"
GITHUB_TEMPLATE = GITHUB_SKILL_DIR / "templates/external-review-summary.md"
FEATURES_INDEX = REPO_ROOT / "docs/features/README.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

RUNBOOKS = (LOCAL_RUNBOOK, GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK)
SKILL_CONSUMERS = (
    LOCAL_SKILL_MD,
    GITHUB_SKILL_MD,
    LOCAL_SKILL_DIR / "metadata/skill.yaml",
    GITHUB_SKILL_DIR / "metadata/skill.yaml",
    *RUNBOOKS,
    LOCAL_TEMPLATE,
    GITHUB_TEMPLATE,
)
DOC_CONSUMERS = (
    REPO_ROOT / "docs/ARCHITECTURE.md",
    REPO_ROOT / "docs/CODE_REVIEW_COMPARISON.md",
    FEATURES_INDEX,
)


@dataclass(frozen=True)
class SharedPolicyWiring:
    basename: str
    issue: str
    runbook_markers: tuple[str, ...]
    local_template_markers: tuple[str, ...]
    github_template_markers: tuple[str, ...]


class SharedPolicyWiringMixin:
    wiring: SharedPolicyWiring

    def test_shared_readme_has_a_policy_map_row(self) -> None:
        self.assertIn(
            self.wiring.basename, SHARED_README.read_text(encoding="utf-8")
        )

    def test_packaged_in_the_one_shared_manifest(self) -> None:
        manifest = json.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))
        destinations = [entry["destination"] for entry in manifest["shared_files"]]
        self.assertIn(f"shared/policies/{self.wiring.basename}", destinations)

    def test_both_skills_load_and_list_the_policy(self) -> None:
        for path in SKILL_CONSUMERS:
            with self.subTest(policy=self.wiring.basename, path=path):
                self.assertIn(
                    self.wiring.basename, path.read_text(encoding="utf-8")
                )

    def test_runbooks_have_a_dedicated_step(self) -> None:
        for path in RUNBOOKS:
            norm = _norm(path)
            for marker in self.wiring.runbook_markers:
                with self.subTest(
                    policy=self.wiring.basename, path=path, marker=marker
                ):
                    self.assertIn(marker, norm)

    def test_local_report_renders_the_policy(self) -> None:
        text = LOCAL_TEMPLATE.read_text(encoding="utf-8")
        for marker in self.wiring.local_template_markers:
            with self.subTest(policy=self.wiring.basename, marker=marker):
                self.assertIn(marker, text)

    def test_github_template_renders_the_policy(self) -> None:
        text = GITHUB_TEMPLATE.read_text(encoding="utf-8")
        for marker in self.wiring.github_template_markers:
            with self.subTest(policy=self.wiring.basename, marker=marker):
                self.assertIn(marker, text)

    def test_architecture_and_comparison_and_feature_index_mention_it(self) -> None:
        for path in DOC_CONSUMERS:
            with self.subTest(policy=self.wiring.basename, path=path):
                self.assertIn(
                    self.wiring.basename, path.read_text(encoding="utf-8")
                )

    def test_feature_index_lists_it_as_not_a_feature_guide(self) -> None:
        text = FEATURES_INDEX.read_text(encoding="utf-8")
        not_a_guide = text.split("## Not a feature guide", 1)[1]
        self.assertIn(self.wiring.basename, not_a_guide)


class ChangelogRecordsPolicyMixin:
    wiring: SharedPolicyWiring

    def test_changelog_records_the_added_shared_policy(self) -> None:
        # Only pins that the changelog records it somewhere under "### Added",
        # not which release heading it currently sits under.
        text = CHANGELOG.read_text(encoding="utf-8")
        self.assertIn("### Added", text)
        self.assertIn(self.wiring.basename, text)
        self.assertIn(f"({self.wiring.issue})", text)


@dataclass(frozen=True)
class SectionForwarding:
    name: str
    reasoning_heading: str
    shared_phrase: str
    index_phrase: str
    runbook_heading: str
    local_window_start: str


class SectionForwardingMixin:
    forwarding: SectionForwarding

    def test_github_review_reasoning_forwards_to_the_shared_section(self) -> None:
        f = self.forwarding
        text = _norm(GITHUB_REASONING)
        self.assertIn(f.reasoning_heading, text, msg=f.name)
        self.assertIn(f.shared_phrase, text, msg=f.name)
        self.assertIn("this PR-specific policy does not restate them", text, msg=f.name)

    def test_github_review_index_lists_the_section(self) -> None:
        self.assertIn(
            self.forwarding.index_phrase,
            _norm(GITHUB_REVIEW_INDEX),
            msg=self.forwarding.name,
        )

    def test_both_github_runbooks_name_the_forwarding_subsection(self) -> None:
        for runbook in (GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK):
            with self.subTest(policy=self.forwarding.name, path=runbook):
                self.assertIn(self.forwarding.runbook_heading, _norm(runbook))

    def test_local_runbook_marks_the_section_signal_triggered(self) -> None:
        window = extract_section(
            _norm(LOCAL_RUNBOOK),
            self.forwarding.local_window_start,
            "Classify findings per",
        )
        for phrase in (
            "signal-triggered per that policy's own gating conditions",
            "not applied",
            "unconditionally to every diff",
        ):
            with self.subTest(policy=self.forwarding.name, phrase=phrase):
                self.assertIn(phrase, window)

    def test_parallel_review_cites_the_shared_section(self) -> None:
        self.assertIn(
            self.forwarding.shared_phrase,
            _norm(PARALLEL_REVIEW),
            msg=self.forwarding.name,
        )
