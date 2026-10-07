#!/usr/bin/env python3
"""Security: authorization channel and member/alias rejection for
skills/local-code-review/policies/external-contract-context.md (Issue #133).
"""

from __future__ import annotations

import unittest

from tests.reference.review import external_contract_context as ecc
from tests.unit.review.test_external_contract_context import _RepoCase, git


class AuthorizationChannelTests(unittest.TestCase):
    def test_only_the_invocation_channel_supplies_the_pair(self) -> None:
        invocation = ecc.Candidate(ecc.Channel.INVOCATION, "/repos/contracts", "a" * 40)
        self.assertEqual(ecc.accepted_input([invocation]), ("/repos/contracts", "a" * 40))

    def test_repository_content_cannot_supply_or_change_the_pair(self) -> None:
        injected = [
            ecc.Candidate(channel, "/repos/evil", "b" * 40)
            for channel in ecc.Channel
            if channel is not ecc.Channel.INVOCATION
        ]
        self.assertIsNone(ecc.accepted_input(injected))

    def test_injected_candidate_never_overrides_the_invocation_pair(self) -> None:
        invocation = ecc.Candidate(ecc.Channel.INVOCATION, "/repos/contracts", "a" * 40)
        injected = ecc.Candidate(ecc.Channel.REPOSITORY_FILE, "/repos/evil", "b" * 40)
        self.assertEqual(ecc.accepted_input([injected, invocation]), ("/repos/contracts", "a" * 40))

    def test_half_a_pair_is_not_an_input(self) -> None:
        self.assertIsNone(ecc.accepted_input([ecc.Candidate(ecc.Channel.INVOCATION, "/repos/x", None)]))
        self.assertIsNone(ecc.accepted_input([ecc.Candidate(ecc.Channel.INVOCATION, None, "a" * 40)]))


class ActivationTests(unittest.TestCase):
    def test_loads_only_when_all_three_conditions_hold(self) -> None:
        full = dict(contract_change=True, surface_unresolved_in_target=True, supplied=True)
        self.assertTrue(ecc.should_load(**full))
        for missing in full:
            with self.subTest(missing=missing):
                self.assertFalse(ecc.should_load(**{**full, missing: False}))

    def test_ambiguity_resolves_to_load_only_with_caller_input(self) -> None:
        self.assertTrue(
            ecc.should_load(
                contract_change=False, surface_unresolved_in_target=False, supplied=True, ambiguous=True
            )
        )
        self.assertFalse(
            ecc.should_load(
                contract_change=True, surface_unresolved_in_target=True, supplied=False, ambiguous=True
            )
        )


class MemberAliasRejectionTests(_RepoCase):
    def test_the_member_itself_is_rejected(self) -> None:
        problem, root = ecc.validate_path(self.target, [self.target])
        self.assertEqual((problem, root), (ecc.Outcome.CONFIGURATION_ERROR, None))

    def test_a_symlink_to_a_member_is_rejected(self) -> None:
        link = self.tmp / "alias-link"
        link.symlink_to(self.target, target_is_directory=True)
        problem, _ = ecc.validate_path(link, [self.target])
        self.assertEqual(problem, ecc.Outcome.CONFIGURATION_ERROR)

    def test_a_worktree_sharing_a_common_dir_is_rejected(self) -> None:
        wt = self.tmp / "target-wt"
        git(self.target, "worktree", "add", "-q", "-b", "side", str(wt))
        problem, _ = ecc.validate_path(wt, [self.target])
        self.assertEqual(problem, ecc.Outcome.CONFIGURATION_ERROR)

    def test_member_is_rejected_for_any_member_of_a_multi_repo_target(self) -> None:
        other = self._init("other-member")
        problem, _ = ecc.validate_path(other, [self.target, other])
        self.assertEqual(problem, ecc.Outcome.CONFIGURATION_ERROR)

    def test_an_unrelated_repository_is_accepted(self) -> None:
        problem, root = ecc.validate_path(self.ext, [self.target])
        self.assertIsNone(problem)
        self.assertEqual(root, self.ext)

    def test_member_alias_yields_no_claims_and_no_provenance(self) -> None:
        result = ecc.assess(
            target_members=[self.target],
            path=self.target,
            revision="HEAD",
            contract_paths=["a.txt"],
            expectation_violated=True,
        )
        self.assertEqual(result.outcome, ecc.Outcome.CONFIGURATION_ERROR)
        self.assertFalse(result.breakage_claim_allowed)
        self.assertIsNone(result.provenance)


class ReadHardeningTests(_RepoCase):
    def test_repository_hooks_and_config_cannot_execute(self) -> None:
        marker = self.tmp / "ran"
        hook = self.ext / ".git" / "hooks" / "post-checkout"
        hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
        hook.chmod(0o755)
        git(self.ext, "config", "core.fsmonitor", f"touch {marker}")
        ecc.resolve_revision(self.ext, self.pinned)
        ecc.read_contract_files(self.ext, self.pinned, ["schema.json"])
        self.assertFalse(marker.exists())

    def test_reads_do_not_modify_the_repository(self) -> None:
        before = git(self.ext, "status", "--porcelain=v1", "--ignored")
        head = git(self.ext, "rev-parse", "HEAD")
        ecc.read_contract_files(self.ext, self.pinned, ["schema.json"])
        self.assertEqual(git(self.ext, "status", "--porcelain=v1", "--ignored"), before)
        self.assertEqual(git(self.ext, "rev-parse", "HEAD"), head)


if __name__ == "__main__":
    unittest.main()
