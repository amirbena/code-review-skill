"""End-to-end reference-model fixtures for risk-based review depth and
large-PR handling (Issue #90).

Issues #86-#89 each pin their own reference model in isolation
(``tests/unit/review/test_change_risk_signals.py``,
``tests/unit/review/test_repository_expansion.py``,
``tests/unit/review/test_large_pr_partitioning.py``,
``tests/unit/review/test_review_stopping_criteria.py``). This module does not
repeat that per-model coverage; it exercises them **chained together**,
the way a real review actually uses them: change-risk depth first, then
repository-expansion capped by that depth, then large-PR partitioning
when the change is big enough, then coverage/completeness rolled up over
whatever passes and partitions that depth required.

Representative scenarios, not an exhaustive matrix:

1. each catalog risk signal alone, and the depth-only conservative
   tie-break escalating two independent ``elevated`` occurrences to
   ``deep`` (change-risk-signals.md);
2. repository-expansion's ring ceiling actually tracking the depth a
   scenario's signals produced, not a hardcoded ring (repository-
   expansion.md);
3. a large multi-area change activating partitioning, with a partition
   that stays capped because coherence is never broken for size (large-
   pr-partitioning.md);
4. coverage/completeness rolling up per-pass and per-partition results
   into a single ``complete``/``incomplete`` label that overrides the
   mechanical clean/changes-required decision — ``REVIEW INCOMPLETE``
   never renders as clean (review-stopping-criteria.md).
"""

from __future__ import annotations

import unittest

from tests.reference.review import change_risk_signals as crs
from tests.reference.review import large_pr_partitioning as lpp
from tests.reference.review import repository_expansion as repo_exp
from tests.reference.review import review_stopping_criteria as rsc
from tests.reference.review.change_risk_signals import Depth
from tests.reference.review.large_pr_partitioning import ChangedFile
from tests.reference.review.repository_expansion import FiredTrigger, Ring
from tests.reference.review.review_stopping_criteria import PartitionCompletion, PassResult


def fact(fact_id: str, *labels: str, evidence: str = "") -> crs.ObservedFact:
    return crs.ObservedFact(
        fact_id=fact_id, labels=frozenset(labels), evidence=evidence or fact_id
    )


def large_multi_area_files() -> list[ChangedFile]:
    """Three areas, each big enough on its own to be unambiguous, summing
    well past the >=1200-line / >=60-file partitioning activation
    threshold."""
    api_files = [ChangedFile(f"api/endpoint_{i}.py", "api", 25) for i in range(20)]
    worker_files = [ChangedFile(f"worker/task_{i}.py", "worker", 20) for i in range(20)]
    infra_files = [ChangedFile(f"infra/module_{i}.tf", "infra", 15) for i in range(20)]
    return api_files + worker_files + infra_files


class RiskSignalDepthScenarioTests(unittest.TestCase):
    """One scenario per way a real review would arrive at each depth."""

    def test_auth_change_alone_selects_deep(self) -> None:
        classification = crs.classify(
            [fact("login-handler", "auth", evidence="new auth bypass branch")]
        )
        self.assertEqual(classification.depth, Depth.DEEP)

    def test_concurrency_change_alone_selects_deep(self) -> None:
        classification = crs.classify(
            [fact("worker-pool", "concurrency", evidence="new shared-state write")]
        )
        self.assertEqual(classification.depth, Depth.DEEP)

    def test_two_independent_elevated_signals_escalate_to_deep(self) -> None:
        # sensitive_path (secrets-adjacent file) and infra_config (CI
        # workflow) are two DISTINCT observed facts -> two elevated
        # occurrences -> escalation, per change-risk-signals.md's
        # "Classification ordering".
        classification = crs.classify(
            [
                fact("env-example", "sensitive_path", evidence=".env.example touched"),
                fact("ci-workflow", "infra_config", evidence="CI workflow touched"),
            ]
        )
        self.assertEqual(classification.depth, Depth.DEEP)
        self.assertEqual(len(classification.occurrences), 2)

    def test_diff_size_alone_selects_elevated_without_any_catalog_signal(self) -> None:
        classification = crs.classify(
            [fact("refactor")],
            diff_size=crs.DiffSize(changed_lines=180, changed_files=4),
        )
        self.assertEqual(classification.depth, Depth.ELEVATED)
        self.assertEqual(classification.occurrences[0].source, "diff-size")

    def test_no_signal_and_small_diff_stays_standard(self) -> None:
        classification = crs.classify(
            [fact("typo-fix")],
            diff_size=crs.DiffSize(changed_lines=6, changed_files=1),
        )
        self.assertEqual(classification.depth, Depth.STANDARD)


class RepositoryExpansionTracksDepthTests(unittest.TestCase):
    """The expansion ceiling must track whatever depth the scenario's own
    signals produced -- never a value hardcoded independently of it."""

    def test_standard_depth_caps_expansion_at_ring_one(self) -> None:
        depth = crs.classify([fact("docs-only")]).depth
        self.assertEqual(depth, Depth.STANDARD)
        result = repo_exp.resolve(
            [
                FiredTrigger(
                    "call_site", "helper.py", Ring.RING_3, locations=("caller.py",)
                )
            ],
            depth,
        )
        self.assertEqual(result.fired[0].resolved_at_ring, Ring.RING_1)

    def test_deep_auth_signal_lets_expansion_reach_ring_three(self) -> None:
        depth = crs.classify([fact("auth-check", "auth")]).depth
        result = repo_exp.resolve(
            [
                FiredTrigger(
                    "interface_contract",
                    "AuthProvider",
                    Ring.RING_3,
                    locations=("impl_a.py", "impl_b.py"),
                )
            ],
            depth,
        )
        self.assertEqual(result.fired[0].resolved_at_ring, Ring.RING_3)

    def test_ceiling_never_pushes_out_a_trigger_resolved_earlier(self) -> None:
        depth = crs.classify([fact("auth-check", "auth")]).depth
        result = repo_exp.resolve(
            [FiredTrigger("config_consumer", "settings.py", Ring.RING_1)], depth
        )
        self.assertEqual(result.fired[0].resolved_at_ring, Ring.RING_1)


class LargePrPartitioningScenarioTests(unittest.TestCase):
    """A large, genuinely multi-area change."""

    def test_large_multi_area_change_activates_partitioning_by_directory(self) -> None:
        files = large_multi_area_files()
        result = lpp.build_partitions(files)
        self.assertTrue(result.activated)
        directories = {p.files[0].directory for p in result.partitions}
        self.assertEqual(directories, {"api", "worker", "infra"})

    def test_a_partition_that_still_exceeds_the_cap_is_flagged_capped(self) -> None:
        # One directory alone is big enough to exceed the per-partition cap
        # after grouping; coherence (same directory) is never broken to
        # shrink it back under the cap.
        files = [
            ChangedFile(f"api/endpoint_{i}.py", "api", 25) for i in range(50)
        ] + [ChangedFile("worker/task_0.py", "worker", 5)]
        result = lpp.build_partitions(files)
        self.assertTrue(result.activated)
        api_partition = next(p for p in result.partitions if p.files[0].directory == "api")
        self.assertTrue(api_partition.capped)

    def test_small_multi_directory_change_does_not_activate(self) -> None:
        files = [
            ChangedFile("api/endpoint_0.py", "api", 10),
            ChangedFile("worker/task_0.py", "worker", 5),
        ]
        result = lpp.build_partitions(files)
        self.assertFalse(result.activated)


class StoppingCriteriaCompletenessScenarioTests(unittest.TestCase):
    """Coverage rolled up over the passes a scenario's own depth required
    and, for a partitioned change, over per-partition completion -- and
    the resulting label overriding the mechanical decision."""

    def test_deep_scenario_with_every_required_pass_complete_is_complete(self) -> None:
        depth = crs.classify([fact("auth-check", "auth")]).depth
        result = rsc.evaluate_coverage(
            depth,
            passes=(
                PassResult("review-scope", True),
                PassResult("affected-test-analysis", True),
            ),
        )
        self.assertEqual(result.coverage, "complete")
        self.assertEqual(rsc.decision_label(result, "CHANGES REQUIRED"), "CHANGES REQUIRED")

    def test_large_partitioned_scenario_with_an_incomplete_partition_is_incomplete(
        self,
    ) -> None:
        files = large_multi_area_files()
        partitioning = lpp.build_partitions(files)
        self.assertTrue(partitioning.activated)
        partition_completion = tuple(
            PartitionCompletion(p.partition_id, completed=(p.partition_id != "P1"))
            for p in partitioning.partitions
        )
        depth = crs.classify(
            [], diff_size=crs.DiffSize(changed_lines=1200, changed_files=60)
        ).depth
        self.assertEqual(depth, Depth.DEEP)
        result = rsc.evaluate_coverage(depth, passes=(), partitions=partition_completion)
        self.assertEqual(result.coverage, "incomplete")
        self.assertEqual(
            result.reasons[0].trigger, rsc.IncompleteTrigger.PARTITION_NOT_COMPLETED
        )
        # Incomplete must never render as clean, no matter what severity.md's
        # mechanical derivation would otherwise have said.
        self.assertEqual(rsc.decision_label(result, "REVIEW CLEAN"), "REVIEW INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
