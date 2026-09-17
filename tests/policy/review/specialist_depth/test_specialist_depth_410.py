#!/usr/bin/env python3
"""Pins conditional (fail-closed) loading for `specialist-depth` (Issue #410).

Issue #409 declared `capabilities/specialist-depth/capability.yaml` as a
capability boundary without changing load behavior. #410 is the step that
makes loading actually conditional on the already-declared activation
predicate, and — because a capability boundary a failed or ambiguous
predicate evaluation can silently bypass would be the one
catastrophic-if-wrong outcome in this migration (per
`capability-architecture-model.md` §C.4) — provably fail-closed: ambiguity
or evaluation failure must load the capability, never skip it.

These assertions protect the cross-document invariant, not merely that a
file mentions the word "fail-closed":

1. `specialist-depth.md` states that its own text, and the four
   `*-deepening.md` files it composes, load only once the activation
   predicate has already been decided — never as a precondition to
   deciding it;
2. that predicate is decidable entirely from `review-scope.md`'s own
   resident base-pass evidence, so evaluating it never requires opening
   `specialist-depth.md`;
3. ambiguous or failed predicate evaluation loads the capability rather
   than skipping it (fail-closed), consistent with the repository's
   existing fail-closed convention;
4. not loading this capability never gates the unconditional base
   per-dimension obligation `review-scope.md` already owns;
5. the conditional-loading contract is scoped to `specialist-depth`
   alone — it is not a general router and does not change any other
   capability's manifest or loading behavior;
6. `capability.yaml` records the same fail-closed clause machine-readably.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

from tests.support.paths import REPO_ROOT

POLICY = REPO_ROOT / "shared/policies/specialist-depth.md"
REVIEW_SCOPE = REPO_ROOT / "shared/policies/review-scope.md"
MANIFEST = REPO_ROOT / "capabilities/specialist-depth/capability.yaml"
MANIFEST_SCHEMA_DOC = REPO_ROOT / "docs/capability-architecture/capability-manifest-schema.md"
CAPABILITIES_DIR = REPO_ROOT / "capabilities"


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class ConditionalLoadingSectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = POLICY.read_text(encoding="utf-8")
        self.text = _norm(POLICY)

    def test_section_exists(self) -> None:
        self.assertIn("## Conditional loading: fail-closed", self.raw)

    def test_loads_only_once_predicate_decided(self) -> None:
        self.assertIn(
            "loads only once the activation predicate above has already "
            "been decided; it is never opened as a precondition to "
            "deciding it",
            self.text,
        )

    def test_predicate_decidable_without_opening_this_file(self) -> None:
        self.assertIn(
            "so evaluating it never requires opening this file or any of "
            "the four deepening policies",
            self.text,
        )

    def test_fail_closed_ambiguity_loads_never_skips(self) -> None:
        self.assertIn(
            "Ambiguity resolves to load, never to skip",
            self.text,
        )

    def test_catastrophic_bypass_framing_present(self) -> None:
        self.assertIn(
            "A capability boundary that a failed or ambiguous predicate "
            "evaluation could silently bypass is the one "
            "catastrophic-if-wrong outcome this contract exists to "
            "prevent",
            self.text,
        )

    def test_base_pass_still_unconditional_under_no_load(self) -> None:
        self.assertIn(
            "Not loading this capability never gates, narrows, or "
            "substitutes for the base per-dimension obligation",
            self.text,
        )
        self.assertIn(
            "that pass always runs regardless of whether this file is "
            "ever opened",
            self.text,
        )

    def test_scoped_to_this_capability_alone(self) -> None:
        self.assertIn(
            "This conditional-loading contract is scoped to this "
            "capability alone",
            self.text,
        )
        self.assertIn(
            "does not define, and must not be read as defining, a "
            "general loading/routing mechanism for any other capability "
            "in this repository",
            self.text,
        )


class ReviewScopeReferencesFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(REVIEW_SCOPE)

    def test_predicate_decidable_from_resident_evidence(self) -> None:
        self.assertIn(
            "That activation predicate is decidable entirely from this "
            "base pass's own resident evidence above",
            self.text,
        )
        self.assertIn(
            "evaluating it never requires opening specialist-depth.md",
            self.text,
        )

    def test_fails_closed_reference(self) -> None:
        self.assertIn(
            "fails closed: ambiguity or evaluation failure loads the "
            "capability rather than skipping it",
            self.text,
        )

    def test_still_does_not_restate_composition_contract(self) -> None:
        # Issue #82's guard: review-scope.md routes without restating the
        # composition contract's own worked examples.
        self.assertNotIn("misleading superficial signal", self.text)
        self.assertNotIn("is outside this section's scope", self.text)


class ManifestFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))

    def test_activation_declares_fail_closed_clause(self) -> None:
        activation = self.manifest["activation"]
        self.assertTrue(
            any("fail-closed" in item for item in activation),
            f"expected a fail-closed activation clause, got {activation!r}",
        )
        self.assertTrue(
            any("loads this capability rather than skipping it" in item for item in activation),
        )

    def test_never_declares_no_skip_on_ambiguity(self) -> None:
        never = self.manifest["never"]
        self.assertTrue(
            any("ambiguous or failed predicate evaluation" in item for item in never),
            f"expected a fail-closed 'never' clause, got {never!r}",
        )

    def test_loads_still_on_activation(self) -> None:
        # #410 makes the predicate enforced, not the manifest's own
        # loads/activation shape, which #409 already declared correctly.
        self.assertEqual(self.manifest["loads"], "on-activation")


class ScopeBoundaryTests(unittest.TestCase):
    """No other capability's manifest changes as part of this issue.

    `scale` is excluded from this "no other manifest" check: issue #447
    gave it its own, independently-declared fail-closed clause as the
    second capability to prove the pattern (see
    `tests/policy/review/scale/test_scale_447.py`), not a change to
    `specialist-depth`'s own scope.
    """

    KNOWN_FAIL_CLOSED_CAPABILITIES = {"specialist-depth", "scale"}

    def test_only_specialist_depth_manifest_mentions_fail_closed(self) -> None:
        for path in sorted(CAPABILITIES_DIR.glob("*/capability.yaml")):
            if path.parent.name in self.KNOWN_FAIL_CLOSED_CAPABILITIES:
                continue
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "fail-closed",
                raw,
                msg=f"{path} unexpectedly declares a fail-closed clause",
            )


class ManifestSchemaDocRecordsIssueTests(unittest.TestCase):
    def test_issue_410_note_present(self) -> None:
        raw = MANIFEST_SCHEMA_DOC.read_text(encoding="utf-8")
        self.assertIn("Issue #410:", raw)
        t = _norm(MANIFEST_SCHEMA_DOC)
        self.assertIn(
            "activation predicate is now enforced, not merely declared",
            t,
        )


if __name__ == "__main__":
    unittest.main()
