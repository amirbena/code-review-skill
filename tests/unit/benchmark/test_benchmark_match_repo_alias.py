#!/usr/bin/env python3
"""Behavioural coverage for the ``repo_alias`` axis the multi-repository
Review Target benchmark extension (Issue #558) added to the matcher's
``Descriptor``/``location_match`` (``runtime_platform/benchmark/reference/benchmark_match.py``).

Driven through the single reference matcher module every other match test
uses; this module never defines a second one. Constructs ``Descriptor``
values directly (rather than through ``test_benchmark_match.py``'s
``_exp``/``_prod`` helpers, which predate this field and have no
``repo_alias`` parameter) so the pre-existing helpers stay untouched.
"""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_match as bm
from runtime_platform.benchmark.reference import benchmark_runner as br


def _expected_descriptor(*, path: str, repo_alias: str | None) -> bm.Descriptor:
    entry = bf.ExpectedFinding(
        key="k",
        severities=("P1",),
        required=True,
        location={"location_intent": "line", "path": path, "repo_alias": repo_alias}
        if repo_alias is not None
        else {"location_intent": "line", "path": path},
        claim="c",
    )
    return bm.Descriptor.from_expected(entry)


def _produced_descriptor(*, path: str, line: int, repo_alias: str | None) -> bm.Descriptor:
    location = {"path": path, "line": line}
    if repo_alias is not None:
        location["repo_alias"] = repo_alias
    return bm.Descriptor.from_produced(br.ProducedFinding(severity="P1", location=location, claim="c"))


class RepoAliasAxisTests(unittest.TestCase):
    def test_same_path_and_alias_is_exact(self) -> None:
        expected = _expected_descriptor(path="src/client.py", repo_alias="repo-a")
        produced = _produced_descriptor(path="src/client.py", line=1, repo_alias="repo-a")
        self.assertEqual(bm.location_match(expected, produced), bm.LocationMatch.EXACT)

    def test_identical_relative_path_in_a_different_member_is_none(self) -> None:
        """Two members can legitimately share a relative path (both have
        ``src/client.py``); a produced finding in the wrong member must
        never be treated as matching, however identical the path/line."""
        expected = _expected_descriptor(path="src/client.py", repo_alias="repo-a")
        produced = _produced_descriptor(path="src/client.py", line=1, repo_alias="repo-b")
        self.assertEqual(bm.location_match(expected, produced), bm.LocationMatch.NONE)

    def test_expected_alias_with_no_produced_alias_falls_back_to_path_comparison(self) -> None:
        """A produced finding that never rendered a repo-qualified location
        (e.g. an adapter/prompt regression) is not automatically a phantom
        mismatch — the axis only narrows when *both* sides carry an alias,
        matching this module's own docstring."""
        expected = _expected_descriptor(path="src/client.py", repo_alias="repo-a")
        produced = _produced_descriptor(path="src/client.py", line=1, repo_alias=None)
        self.assertEqual(bm.location_match(expected, produced), bm.LocationMatch.EXACT)

    def test_single_repository_descriptors_never_carry_an_alias(self) -> None:
        expected = _expected_descriptor(path="src/client.py", repo_alias=None)
        produced = _produced_descriptor(path="src/client.py", line=1, repo_alias=None)
        self.assertIsNone(expected.repo_alias)
        self.assertIsNone(produced.repo_alias)
        self.assertEqual(bm.location_match(expected, produced), bm.LocationMatch.EXACT)


if __name__ == "__main__":
    unittest.main()
