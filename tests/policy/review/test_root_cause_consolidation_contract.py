"""Cross-contract consistency checks for root-cause finding consolidation
(Issue #177) and its re-review reconciliation (review F1).

These assertions protect the *invariant that spans documents*, not merely
that each file mentions the feature:

1. ordinary ambiguous many-to-one matching still preserves prior identities
   and state in every owner (matching #59, lifecycle #62, delta re-review
   #64, and the packaged #65 policy);
2. a positively established shared root cause is the one narrow exception —
   the ``CONSOLIDATED`` lifecycle disposition — and it is defined in every
   owner, gated on the ``review-scope.md`` root-cause evidence bar, never on
   ``N->1`` topology or wording similarity;
3. ``CONSOLIDATED`` resolves nothing (a folded prior identity stays
   ``OPEN``) and never reuses ``SUPERSEDED``;
4. ``review-scope.md`` routes to that model rather than defining a second,
   competing one (no ``supersede`` verb, no lifecycle rules restated);
5. the #185 benchmark corpus is reused: the low-confidence fixture does not
   enter the consolidation path, and the re-review fixture pins exactly one
   authoritative finding whose prose reflects the ``CONSOLIDATED`` semantics.
"""

from __future__ import annotations

import re
import unittest

import yaml

from tests.support.paths import REPO_ROOT

REVIEW_SCOPE = REPO_ROOT / "shared/policies/review-scope.md"
# The root-cause / model-completeness consolidation sub-domain was extracted
# from review-scope.md into its own canonical shared policy (Issue #198);
# review-scope.md keeps a linking overview.
ROOT_CAUSE = REPO_ROOT / "shared/policies/root-cause-consolidation.md"
FINDING_TMPL = REPO_ROOT / "shared/templates/finding.md"
IDENTITY = REPO_ROOT / "docs/findings/finding-identity-requirements.md"
LIFECYCLE = REPO_ROOT / "docs/findings/finding-lifecycle-contract.md"
MATCHING = REPO_ROOT / "docs/findings/finding-matching-strategy.md"
DELTA = REPO_ROOT / "docs/findings/delta-re-review-contract.md"
STATEFUL = REPO_ROOT / "skills/github-pr-review/policies/stateful-delta-rereview.md"
CORPUS = REPO_ROOT / "docs/benchmark/corpus/consolidation"

ALL_OWNERS = (REVIEW_SCOPE, IDENTITY, LIFECYCLE, MATCHING, DELTA, STATEFUL)


def _norm(path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class OrdinaryManyToOneStillAmbiguousTests(unittest.TestCase):
    """Invariant 1 — the false-merge safeguard for a raw N->1 topology is
    unchanged in every owner."""

    def test_matching_strategy_keeps_collapse_a_disqualifier(self) -> None:
        raw = MATCHING.read_text(encoding="utf-8")
        self.assertIn("a split or collapse (one-to-many or many-to-one)", raw)
        # worked case 14 still resolves to Ambiguous
        self.assertRegex(
            raw, r"two findings collapse into one path.*\*\*Ambiguous\*\*"
        )
        n = _norm(MATCHING)
        self.assertIn(
            "A many-to-one (collapse) relationship stays `AMBIGUOUS` here "
            "regardless of how confident anyone is", n
        )
        self.assertIn("this matcher transfers nothing", n)

    def test_lifecycle_scenario_12_is_unchanged(self) -> None:
        raw = LIFECYCLE.read_text(encoding="utf-8")
        self.assertIn(
            "| 12 | Two prior findings collapse into one candidate | `OPEN` for "
            "both | `AMBIGUOUS` | Many-to-one cannot transfer either identity | "
            "`UNCERTAIN` each | both `OPEN` preserved |",
            raw,
        )

    def test_delta_and_stateful_keep_ambiguous_as_the_default(self) -> None:
        d = _norm(DELTA)
        # consolidation is explicitly NOT a seventh #64 change class; the
        # collapse still classifies as Ambiguous
        self.assertIn("### Consolidation is not a change class", d)
        self.assertIn("does **not** add a seventh change class", d)
        self.assertIn(
            "this contract's classifier still calls that **`Ambiguous`**", d
        )
        self.assertIn("The classifier is unchanged", d)
        self.assertNotIn("**Consolidated**", d)  # no peer change-class row
        s = _norm(STATEFUL)
        self.assertIn("`AMBIGUOUS` for the relationship under consideration | "
                      "Ambiguous | `UNCERTAIN`, prior state preserved", s)
        self.assertIn("`AMBIGUOUS` never becomes a confident transition", s)
        # §1 still says six change classes and §3 stays consistent with it
        self.assertIn("the six change classes", s)
        self.assertIn(
            "Ambiguous (still — collapse is a #59 disqualifier)", s
        )


class ConsolidatedDispositionDefinedInEveryOwnerTests(unittest.TestCase):
    """Invariants 2 + 3 — one shared definition, reviewer-gated, resolves
    nothing, no SUPERSEDED reuse."""

    def test_every_owner_names_the_disposition(self) -> None:
        for path in (IDENTITY, LIFECYCLE, MATCHING, DELTA, STATEFUL):
            self.assertIn("CONSOLIDATED", path.read_text(encoding="utf-8"), path.name)

    def test_gate_is_positive_root_cause_evidence_not_topology(self) -> None:
        for path in (LIFECYCLE, IDENTITY, DELTA, STATEFUL):
            n = _norm(path)
            self.assertIn("review-scope.md", n, path.name)
            self.assertIn("root-cause evidence", n, path.name)
            names_the_shape = (
                "N→1" in n or "N->1" in n or "many-to-one" in n or "collapse" in n
            )
            says_shape_is_insufficient = (
                "topology" in n
                or "shape of the prior finding set" in n
                or "never trigger it" in n
                or "never suffice" in n
                or "each insufficient on their own" in n
            )
            self.assertTrue(
                names_the_shape and says_shape_is_insufficient,
                f"{path.name}: must say the N→1 shape alone never triggers it",
            )

    def test_consolidation_resolves_nothing(self) -> None:
        self.assertIn("consolidation resolves nothing", _norm(LIFECYCLE))
        self.assertIn("each still `OPEN` — consolidation resolves nothing", _norm(DELTA))
        self.assertIn("each folded prior identity stays `OPEN`", _norm(STATEFUL))
        self.assertIn("nothing resolved", _norm(STATEFUL))
        self.assertIn(
            "A folded identity resolves only later, if and when the "
            "consolidated finding itself meets the full resolution bar",
            _norm(IDENTITY),
        )

    def test_superseded_is_not_reused(self) -> None:
        self.assertIn("Consolidation never uses `SUPERSEDED`", _norm(LIFECYCLE))
        self.assertIn("not resolved, not `SUPERSEDED`", _norm(IDENTITY))

    def test_consolidated_finding_gets_a_fresh_identity(self) -> None:
        n = _norm(IDENTITY)
        self.assertIn("the consolidated finding is minted a\n**fresh** identity, "
                      "never one reused from a prior per-site finding".replace(
                          "\n", " "), n)
        self.assertIn("fresh identity via `DETECTED` → `OPEN`", _norm(LIFECYCLE))

    def test_lifecycle_event_and_scenario_row_exist(self) -> None:
        raw = LIFECYCLE.read_text(encoding="utf-8")
        self.assertIn("| `CONSOLIDATED` |", raw)
        self.assertRegex(raw, r"\| 16 \| Prior per-site findings positively "
                              r"established as one shared root cause \|")
        self.assertIn("### Reviewer-established root-cause consolidation "
                      "(`CONSOLIDATED`)", raw)


class ReviewScopeRoutesRatherThanRedefinesTests(unittest.TestCase):
    """Invariant 4 — no second competing definition; the consolidation
    routing/default/exception prose lives in the extracted canonical home
    (root-cause-consolidation.md), review-scope.md only links to it."""

    def setUp(self) -> None:
        self.n = _norm(ROOT_CAUSE)

    def test_no_supersede_verb(self) -> None:
        self.assertNotIn("supersede", self.n.lower())

    def test_routes_identity_handling_to_the_owner_model(self) -> None:
        self.assertIn(
            "How the prior per-site finding identities are then handled is owned "
            "by the repository's finding-identity and lifecycle model, not "
            "restated here",
            self.n,
        )

    def test_states_the_default_and_the_exception_and_the_fail_open(self) -> None:
        self.assertIn("ordinary many-to-one matching", self.n)
        self.assertIn("stays ambiguous", self.n)
        self.assertIn(
            "consolidation is never inferred from that topology or from wording "
            "similarity",
            self.n,
        )
        self.assertIn("the lifecycle model's `CONSOLIDATED` disposition", self.n)
        self.assertIn("nothing is treated as resolved", self.n)
        self.assertIn(
            "when the shared cause is not positively established, keep the "
            "findings separate",
            self.n,
        )

    def test_does_not_restate_lifecycle_state_machine(self) -> None:
        # neither review-scope.md nor its extracted consolidation home grows
        # its own OPEN/RESOLVED state table
        for path in (REVIEW_SCOPE, ROOT_CAUSE):
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("OPEN → RESOLVED", raw)
            self.assertNotIn("| `RESOLVED` |", raw)


class AffectedLocationsCardinalityTests(unittest.TestCase):
    """Invariant / F2 — consolidation needs >= 2 sites and the field is
    conditionally required, exhaustive, and not simultaneously optional."""

    def test_review_scope_requires_at_least_two_sites(self) -> None:
        self.assertIn(
            "Consolidation applies only when the shared cause reaches **at "
            "least two**\nmanifestation sites".replace("\n", " "),
            _norm(ROOT_CAUSE),
        )

    def test_finding_template_marks_it_conditionally_required_and_exhaustive(self) -> None:
        n = _norm(FINDING_TMPL)
        self.assertIn("**conditionally required**", n)
        self.assertIn(
            "a consolidated finding rendered without it, or with fewer than two "
            "entries, is not publishable",
            n,
        )
        self.assertIn(
            "it is **exhaustive for the manifestation sites the review found**", n
        )
        # not simultaneously optional + required
        self.assertIn("It is **not optional**", n)


class Benchmark185CorpusReuseTests(unittest.TestCase):
    """Invariant 5 — reuse the #185 fixtures rather than re-encoding cases."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = {
            p.stem: yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in CORPUS.glob("*.yaml")
        }

    def test_low_confidence_fixture_stays_separate_no_consolidation(self) -> None:
        case = self.cases["consolidation-shared-cause-low-confidence-fallback"]
        findings = case["expected"]["findings"]
        required = [f for f in findings if f.get("match") == "required"]
        self.assertEqual(
            len(required), 2,
            "the low-confidence case must yield two separate required findings, "
            "never a consolidated one",
        )
        rationale = case["metadata"]["rationale"].lower()
        self.assertIn("fail-open", rationale)

    def test_shared_validator_fixture_is_one_consolidated_finding(self) -> None:
        case = self.cases["consolidation-shared-validator-many-call-paths"]
        required = [
            f for f in case["expected"]["findings"] if f.get("match") == "required"
        ]
        self.assertEqual(len(required), 1)
        # the one authoritative finding names the multiple inheriting sites
        self.assertIn("caller", required[0]["claim"])

    def test_rereview_fixture_pins_one_finding_with_consolidated_semantics(self) -> None:
        case = self.cases["consolidation-rereview-reconciles-to-authoritative"]
        required = [
            f for f in case["expected"]["findings"] if f.get("match") == "required"
        ]
        self.assertEqual(len(required), 1, "one authoritative finding, not two, not three")
        claim = required[0]["claim"].lower()
        # the fixture prose must reflect the lifecycle semantics, not "supersede"
        self.assertIn("consolidat", claim)
        self.assertIn("open", claim)
        self.assertNotIn("supersede", claim)
        blob = (case.get("metadata", {}).get("rationale", "") + " "
                + case.get("title", "")).lower()
        self.assertNotIn("supersede", blob)

    def test_corpus_readme_points_at_the_lifecycle_owner(self) -> None:
        readme = (CORPUS / "README.md").read_text(encoding="utf-8")
        self.assertIn("finding-lifecycle-contract.md", readme)
        self.assertIn("stateful-delta-rereview.md", readme)
        self.assertIn("CONSOLIDATED", readme)


if __name__ == "__main__":
    unittest.main()
