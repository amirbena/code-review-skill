#!/usr/bin/env python3
"""Pins conditional (fail-closed) loading for `scale` (Issue #447).

Issue #412's continuation checkpoint named `scale` as the second
capability to prove the #408->#410->#411 declarative-manifest +
hand-authored-predicate + conditional-load pattern generalizes beyond
`specialist-depth`. #447 is the step that makes `scale`'s loading
actually conditional on its already-declared activation predicate, and —
because a capability boundary a failed or ambiguous predicate evaluation
can silently bypass would be the one catastrophic-if-wrong outcome in
this migration (per `capability-architecture-model.md` SS C.4, the same
concern #410 already proved for `specialist-depth`) — provably
fail-closed: ambiguity or evaluation failure must load the capability,
never skip it.

`scale` bundles two policy files with different activation postures:
`repository-expansion.md` ("always active") and `large-pr-partitioning.md`
("conditional"). This module pins that both reconcile "always active" /
"conditional" *pass evaluation* against `on-activation` *file loading*
the same way, rather than leaving one silently contradicting the
manifest.

These assertions protect the cross-document invariant, not merely that a
file mentions the word "fail-closed":

1. both `repository-expansion.md` and `large-pr-partitioning.md` state
   that their own text loads only once their own predicate has already
   been decided — never as a precondition to deciding it;
2. `large-pr-partitioning.md`'s predicate, and three of
   `repository-expansion.md`'s four trigger predicates (interface/
   contract, migration/schema, config-consumer), are decidable entirely
   from `review-scope.md`'s own resident base-pass evidence, so
   evaluating them never requires opening either file; only
   `repository-expansion.md`'s call-site trigger can require its own
   ring-1 investigation to confirm firing, which is exactly the
   ambiguous case fail-closed loading exists to cover;
3. ambiguous or failed predicate evaluation loads the capability rather
   than skipping it (fail-closed), consistent with the repository's
   existing fail-closed convention (`specialist-depth.md`, #410);
4. `repository-expansion.md`'s "always active" framing describes the
   trigger-evaluation predicate, not whether the file itself is opened —
   it is not silently contradicted by `on-activation` loading;
5. the conditional-loading contract is scoped to `scale` alone — it is
   not a general router and does not change any other capability's
   manifest or loading behavior, including `specialist-depth`'s
   `requires: [... scale]` dependency;
6. `capability.yaml` records the same fail-closed clause machine-readably.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

from tests.support.paths import REPO_ROOT

REPOSITORY_EXPANSION = REPO_ROOT / "shared/policies/repository-expansion.md"
LARGE_PR_PARTITIONING = REPO_ROOT / "shared/policies/large-pr-partitioning.md"
REVIEW_SCOPE = REPO_ROOT / "shared/policies/review-scope.md"
SCALE_MANIFEST = REPO_ROOT / "capabilities/scale/capability.yaml"
SPECIALIST_DEPTH_MANIFEST = REPO_ROOT / "capabilities/specialist-depth/capability.yaml"
MANIFEST_SCHEMA_DOC = REPO_ROOT / "docs/capability-architecture/capability-manifest-schema.md"
CAPABILITIES_DIR = REPO_ROOT / "capabilities"


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class RepositoryExpansionConditionalLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = REPOSITORY_EXPANSION.read_text(encoding="utf-8")
        self.text = _norm(REPOSITORY_EXPANSION)

    def test_section_exists(self) -> None:
        self.assertIn("## Conditional loading: fail-closed", self.raw)

    def test_always_active_reconciled_not_contradicted(self) -> None:
        self.assertIn(
            "describes the trigger-evaluation predicate above, not "
            "whether this file itself is opened",
            self.text,
        )

    def test_loads_only_once_predicate_decided(self) -> None:
        self.assertIn(
            "This file loads only once a trigger has already been "
            "decided to have fired, or its firing cannot yet be "
            "confidently ruled out",
            self.text,
        )

    def test_trigger_type_recognition_decidable_without_opening_this_file(self) -> None:
        self.assertIn(
            "since that recognition is decidable from the diff alone",
            self.text,
        )

    def test_three_of_four_triggers_firing_is_resident_too(self) -> None:
        # The second soundness fix: only the call-site trigger's firing
        # hinges on an evidenced consumer (per "Signal detection is
        # evidence-based, not name-based"); the other three fire on a
        # fact the diff itself already shows, so confirming them is just
        # as resident as recognizing their type -- unlike the first
        # (overcorrected) fix, this no longer implies all four triggers
        # need investigation to confirm firing.
        self.assertIn(
            "interface/contract, migration/schema, and config-consumer "
            "triggers each fire on a fact the diff itself already shows",
            self.text,
        )

    def test_call_site_firing_may_require_ring_1_investigation(self) -> None:
        self.assertIn(
            "fired can require this file's own ring-1 investigation to "
            "resolve",
            self.text,
        )
        self.assertIn(
            "never to silently treating the call-site trigger as unfired "
            "for lack of a visible consumer in the diff",
            self.text,
        )

    def test_fail_closed_ambiguity_loads_never_skips(self) -> None:
        self.assertIn(
            "Ambiguity resolves to load, never to skip",
            self.text,
        )

    def test_fail_closed_covers_not_yet_investigated_determination(self) -> None:
        self.assertIn(
            "including because a call-site trigger's evidenced-consumer "
            "determination has not yet been investigated",
            self.text,
        )

    def test_scoped_to_scale_alone(self) -> None:
        self.assertIn(
            "This conditional-loading contract is scoped to scale alone",
            self.text,
        )
        self.assertIn(
            "does not define, and must not be read as defining, a "
            "general loading/routing mechanism for any other capability "
            "in this repository",
            self.text,
        )


class LargePrPartitioningConditionalLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = LARGE_PR_PARTITIONING.read_text(encoding="utf-8")
        self.text = _norm(LARGE_PR_PARTITIONING)

    def test_section_exists(self) -> None:
        self.assertIn("## Conditional loading: fail-closed", self.raw)

    def test_loads_only_once_measurement_decided(self) -> None:
        self.assertIn(
            "This file loads only once the diff-size measurement below "
            "has already been decided to reach the partitioning "
            "threshold; it is never opened as a precondition to "
            "deciding that",
            self.text,
        )

    def test_predicate_decidable_without_opening_this_file(self) -> None:
        self.assertIn(
            "so evaluating it never requires opening this file",
            self.text,
        )

    def test_fail_closed_ambiguity_loads_never_skips(self) -> None:
        self.assertIn(
            "Ambiguity resolves to load, never to skip",
            self.text,
        )

    def test_scoped_to_scale_alone(self) -> None:
        self.assertIn(
            "This conditional-loading contract is scoped to scale alone",
            self.text,
        )


class ReviewScopeReferencesFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(REVIEW_SCOPE)

    def test_repository_expansion_predicate_decidable_from_resident_evidence(self) -> None:
        self.assertIn(
            "Recognizing which trigger type a change plausibly implicates",
            self.text,
        )
        self.assertIn(
            "are all decidable entirely from this base pass's own "
            "resident trigger catalog above",
            self.text,
        )
        self.assertIn(
            "only confirming whether the call-site trigger fires can "
            "require repository-expansion.md's own ring-1 investigation",
            self.text,
        )

    def test_repository_expansion_fails_closed_reference(self) -> None:
        self.assertIn(
            "not-yet-investigated call-site firing determination fails "
            "closed: it loads the capability rather than skipping it, "
            "per repository-expansion.md's",
            self.text,
        )

    def test_large_pr_partitioning_predicate_decidable_from_resident_evidence(self) -> None:
        self.assertIn(
            "That threshold measurement is decidable entirely from this "
            "base pass's own resident diff-size count above",
            self.text,
        )
        self.assertIn(
            "evaluating it never requires opening large-pr-partitioning.md",
            self.text,
        )

    def test_large_pr_partitioning_fails_closed_reference(self) -> None:
        self.assertIn(
            "fails closed: ambiguity or evaluation failure loads the "
            "capability rather than skipping it, per "
            "large-pr-partitioning.md's",
            self.text,
        )


class ManifestFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = yaml.safe_load(SCALE_MANIFEST.read_text(encoding="utf-8"))

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
        # #447 makes the predicate enforced, not the manifest's own
        # loads/activation shape, which already declared on-activation.
        self.assertEqual(self.manifest["loads"], "on-activation")


class ScopeBoundaryTests(unittest.TestCase):
    """No capability other than `scale`/`specialist-depth` changes."""

    KNOWN_FAIL_CLOSED_CAPABILITIES = {"specialist-depth", "scale"}

    def test_only_known_manifests_mention_fail_closed(self) -> None:
        for path in sorted(CAPABILITIES_DIR.glob("*/capability.yaml")):
            if path.parent.name in self.KNOWN_FAIL_CLOSED_CAPABILITIES:
                continue
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "fail-closed",
                raw,
                msg=f"{path} unexpectedly declares a fail-closed clause",
            )

    def test_specialist_depth_requires_scale_unchanged(self) -> None:
        manifest = yaml.safe_load(SPECIALIST_DEPTH_MANIFEST.read_text(encoding="utf-8"))
        self.assertIn("scale", manifest["requires"])


class ManifestSchemaDocRecordsIssueTests(unittest.TestCase):
    def test_issue_447_note_present(self) -> None:
        raw = MANIFEST_SCHEMA_DOC.read_text(encoding="utf-8")
        self.assertIn("Issue #447:", raw)
        t = _norm(MANIFEST_SCHEMA_DOC)
        self.assertIn(
            "scale's activation predicate is now enforced the same way",
            t,
        )


if __name__ == "__main__":
    unittest.main()
