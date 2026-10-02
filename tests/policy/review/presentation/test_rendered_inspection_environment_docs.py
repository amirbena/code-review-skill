#!/usr/bin/env python3
"""Contract: shared/policies/rendered-inspection-environment.md owns browser
capability detection, the acquisition question, install authorization, and the
durable opt-out for rendered inspection (Issue #618, Epic #614).

Prose checks over the shared policy and its consumers, plus behavior checks over
the test-only reference model.
"""

from __future__ import annotations

import itertools
import re
import unittest

from tests.reference.review import rendered_inspection_environment as env
from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _text


def _plain(phrase: str) -> str:
    return phrase.replace("**", "").replace("`", "")


POLICY = REPO_ROOT / "shared/policies/rendered-inspection-environment.md"
PARENT = REPO_ROOT / "shared/policies/rendered-inspection.md"
TRUSTED_HOST = REPO_ROOT / "shared/policies/trusted-host-execution.md"
BRIEF_POLICY = REPO_ROOT / "skills/github-pr-review/policies/reviewer-brief.md"
BRIEF_TEMPLATE = REPO_ROOT / "skills/github-pr-review/templates/reviewer-brief.md"
LOCAL_TEMPLATE = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
CAPABILITY = REPO_ROOT / "capabilities/rendered-inspection/capability.yaml"
MANIFEST = REPO_ROOT / "scripts/packaging/package-manifest.json"
SKILL_YAMLS = (
    REPO_ROOT / "skills/github-pr-review/metadata/skill.yaml",
    REPO_ROOT / "skills/local-code-review/metadata/skill.yaml",
)
NAME = "rendered-inspection-environment.md"


class DetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def test_detection_order_is_stated_in_order(self) -> None:
        positions = [
            self.text.index(marker)
            for marker in (
                "Runtime-supplied browser capability",
                "The project's own Playwright",
                "A previously installed user-level Playwright",
                "None.",
            )
        ]
        self.assertEqual(positions, sorted(positions))

    def test_detection_is_read_only_and_playwright_not_required(self) -> None:
        for phrase in (
            "Detection (read-only)",
            "never installs, downloads",
            "Playwright is not required",
            "the repository is never modified",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_model_prefers_earlier_usable_source(self) -> None:
        ok, bad = env.Candidate(True), env.ABSENT
        self.assertEqual(env.detect(ok, ok, ok), env.Source.RUNTIME)
        self.assertEqual(env.detect(bad, ok, ok), env.Source.PROJECT)
        self.assertEqual(env.detect(bad, bad, ok), env.Source.USER_LEVEL)
        self.assertEqual(env.detect(bad, bad, bad), env.Source.NONE)

    def test_unusable_candidates_fall_through(self) -> None:
        no_binary = env.Candidate(True, browser_binary_present=False)
        shared_profile = env.Candidate(True, shares_user_profile=True)
        weak = env.Candidate(True, meets_capability=False)
        user_level = env.Candidate(True)
        for unusable in (no_binary, shared_profile, weak):
            with self.subTest(unusable=unusable):
                self.assertEqual(
                    env.detect(unusable, unusable, user_level), env.Source.USER_LEVEL
                )


class LocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def test_location_rules(self) -> None:
        for phrase in (
            "Package and browser binaries are treated separately",
            "Chromium only",
            "Nothing is installed into it and its manifest and lockfile are never altered",
            "standard user-level browser cache",
            "pinned, version-recorded user-level tools directory",
            "global `npm -g`, `sudo`, any system package, and Playwright's `--with-deps`",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_pinned_version_matches_model(self) -> None:
        self.assertIn(f"playwright@{env.PINNED_VERSION}", self.text)
        self.assertIn(f"playwright {env.PINNED_VERSION}", self.text)

    def test_command_has_no_forbidden_forms(self) -> None:
        for line in env.install_command("<tools-dir>"):
            for forbidden in ("npm -g", "--global", "sudo", "--with-deps"):
                self.assertNotIn(forbidden, line)
        self.assertIn("--prefix", env.install_command("<tools-dir>")[0])


class QuestionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def test_four_gates_are_stated(self) -> None:
        for phrase in (
            "Emitted only when **all four** gates hold, and never otherwise",
            "materially UI-impacting",
            "would add meaningful evidence",
            "no usable browser capability exists",
            "no durable opt-out is present",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_each_gate_independently_silences_the_question(self) -> None:
        self.assertTrue(env.should_ask(env.Gates(True, True, False, False)))
        for gates in (
            env.Gates(False, True, False, False),
            env.Gates(True, False, False, False),
            env.Gates(True, True, True, False),
            env.Gates(True, True, False, True),
        ):
            with self.subTest(gates=gates):
                self.assertFalse(env.should_ask(gates))

    def test_only_the_all_clear_combination_asks(self) -> None:
        asked = [
            combo
            for combo in itertools.product((False, True), repeat=4)
            if env.should_ask(env.Gates(*combo))
        ]
        self.assertEqual(asked, [(True, True, False, False)])

    def test_question_content_requirements(self) -> None:
        for phrase in (
            "approval enables rendered verification now and in future reviews",
            "location",
            "size",
            "pinned version",
            "exact command",
            "supply the authorization signal",
            "set `rendered_inspection_opt_out`",
            "never blocks the review",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_surface_is_operator_only_per_skill(self) -> None:
        self.assertIn("never a PR comment", self.text)
        self.assertEqual(env.surface_for("github-pr-review"), env.Surface.REVIEWER_BRIEF)
        self.assertEqual(env.surface_for("local-code-review"), env.Surface.LOCAL_FINAL_REPORT)
        self.assertIn("rendered-inspection-environment.md", _text(BRIEF_POLICY))
        self.assertIn("Open questions / assumptions", _text(BRIEF_TEMPLATE))
        self.assertIn(NAME, _text(BRIEF_TEMPLATE))
        self.assertIn(NAME, _text(LOCAL_TEMPLATE))


class AuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def test_authorization_provenance_matches_trusted_host(self) -> None:
        for phrase in (
            "trusted, out-of-band, invocation-scoped channel",
            "`allow_browser_tooling_install` (default `false`)",
            "A natural-language phrasing is **not** recognized",
            "The Skill never performs the install and ships no installer",
            "the next invocation re-detects from scratch",
        ):
            self.assertIn(_plain(phrase), self.text)
        self.assertIn("trusted-host-execution.md", self.text)

    def test_excluded_sources_are_enumerated(self) -> None:
        for phrase in (
            "PR/issue/commit text",
            "repository instruction files, manifests, scripts, or configuration",
            "a prior review's outcome",
            "nested-agent or spawned-child state",
            "rendered page or console text",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_only_trusted_runtime_channel_authorizes(self) -> None:
        self.assertTrue(env.install_authorized(env.Signal(True, env.Channel.TRUSTED_RUNTIME)))
        for channel in env.Channel:
            if channel is env.Channel.TRUSTED_RUNTIME:
                continue
            with self.subTest(channel=channel):
                self.assertFalse(env.install_authorized(env.Signal(True, channel)))
        self.assertFalse(env.install_authorized(None))
        self.assertFalse(
            env.install_authorized(env.Signal(True, env.Channel.TRUSTED_RUNTIME, ambiguous=True))
        )

    def test_trusted_host_flag_does_not_cover_installation(self) -> None:
        self.assertIn(NAME, _text(TRUSTED_HOST))
        self.assertIn("never covers installing a browser", _text(TRUSTED_HOST))

    def test_nothing_is_ever_installed_by_the_skill(self) -> None:
        gates = env.Gates(True, True, False, False)
        trusted = env.Signal(True, env.Channel.TRUSTED_RUNTIME)
        for auth, opt in itertools.product((None, trusted), (None, trusted)):
            action = env.decide(gates, auth, opt)
            self.assertFalse(action.performed_install)
            self.assertTrue(action.review_completes)

    def test_authorized_request_requires_the_question_to_fire(self) -> None:
        trusted = env.Signal(True, env.Channel.TRUSTED_RUNTIME)
        gates = env.Gates(True, True, False, False)
        self.assertTrue(env.decide(gates, trusted, None).emit_authorized_install_request)
        self.assertFalse(env.decide(gates, None, None).emit_authorized_install_request)
        self.assertFalse(env.decide(gates, trusted, trusted).emit_authorized_install_request)
        usable = env.Gates(True, True, True, False)
        self.assertFalse(env.decide(usable, trusted, None).emit_authorized_install_request)


class OptOutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def test_opt_out_is_a_local_trusted_signal_only(self) -> None:
        for phrase in (
            "`rendered_inspection_opt_out` (default `false`)",
            "never conversational memory",
            "A repository-resident file, PR text, a prior review, or an inferred preference cannot establish it",
            "A one-off \"no\" in conversation is **not** durable",
            "treated as absent for the question",
            "silences the *question* only",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_opt_out_honored_or_ignored_by_source(self) -> None:
        gates = env.Gates(True, True, False, False)
        honored = env.decide(gates, None, env.Signal(True, env.Channel.TRUSTED_RUNTIME))
        self.assertFalse(honored.asked)
        for channel in env.Channel:
            if channel is env.Channel.TRUSTED_RUNTIME:
                continue
            with self.subTest(channel=channel):
                self.assertTrue(env.decide(gates, None, env.Signal(True, channel)).asked)
        ambiguous = env.Signal(True, env.Channel.TRUSTED_RUNTIME, ambiguous=True)
        self.assertTrue(env.decide(gates, None, ambiguous).asked)


class DeniedPathTests(unittest.TestCase):
    def test_denied_path_continues_with_one_limitation(self) -> None:
        text = _text(POLICY)
        for phrase in (
            "the review completes in full with no rendered evidence",
            "the **one** limitation statement",
            "nothing makes the review `REVIEW INCOMPLETE`",
        ):
            self.assertIn(_plain(phrase), text)
        action = env.decide(env.Gates(True, True, False, False), None, None)
        self.assertTrue(action.review_completes)

    def test_design_tool_access_is_excluded(self) -> None:
        text = _text(POLICY)
        self.assertIn("Design-reference access is never requested through this question", text)


class WiringTests(unittest.TestCase):
    def test_parent_policy_points_here_and_does_not_restate(self) -> None:
        parent = _text(PARENT)
        self.assertIn(NAME, parent)
        self.assertNotIn("allow_browser_tooling_install", parent)
        self.assertNotIn("rendered_inspection_opt_out", parent)

    def test_packaging_and_manifests_include_the_policy(self) -> None:
        self.assertIn(NAME, _text(MANIFEST))
        self.assertIn(NAME, _text(CAPABILITY))
        for path in SKILL_YAMLS:
            self.assertIn(NAME, _text(path))

    def test_policy_has_no_link_into_skills_or_repo_docs(self) -> None:
        raw = POLICY.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\]\([^)]*(skills/|docs/)", raw))


if __name__ == "__main__":
    unittest.main()
