"""Test doubles for the evidence-destination contract (#688): hermetic, never a real remote."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest import mock

from runtime_platform.benchmark.scripts import benchmark_evidence_destination as ed
from runtime_platform.benchmark.scripts.benchmark_schedule_manifest import MANIFEST_PATH, load_manifest

SOURCE = "amirbena/code-review-skill"
EVIDENCE = "amirbena/code-review-skill-evidence"
NAMESPACES = tuple(load_manifest(MANIFEST_PATH)["evidence"]["namespaces"])


def evidence_block(phase: str = ed.PHASE_PRE_CUTOVER, repository: str | None = None) -> dict[str, Any]:
    return {
        "phase": phase,
        "repository": repository or (SOURCE if phase == ed.PHASE_PRE_CUTOVER else EVIDENCE),
        "namespaces": list(NAMESPACES),
        "history_branch": "benchmark-history",
    }


def manifest_with(phase: str = ed.PHASE_PRE_CUTOVER, repository: str | None = None) -> dict[str, Any]:
    manifest = load_manifest(MANIFEST_PATH)
    manifest["evidence"] = evidence_block(phase, repository)
    return manifest


@dataclass(frozen=True)
class OfflineDestination(ed.Destination):
    """A resolved destination whose store is never contacted: preflight passes, the stop-condition read is scripted."""

    prior_refs: tuple[str, ...] = ()

    def preflight(self) -> None:
        return None

    def list_refs(self, prefix: str) -> list[str]:
        self.check_namespace(prefix + "x")
        return [r for r in self.prior_refs if r.startswith(prefix)]


def offline_destination(repo_root: Path | None = None, *, prior_refs: tuple[str, ...] = (), repository: str = SOURCE,
                        phase: str = ed.PHASE_PRE_CUTOVER) -> OfflineDestination:
    return OfflineDestination(
        repository=repository, phase=phase, remote="offline-evidence-remote", namespaces=NAMESPACES,
        history_branch="benchmark-history", repo_root=repo_root or Path("."), prior_refs=prior_refs,
    )


def real_destination(repo_root: Path | None = None, *, remote: str = "offline-evidence-remote") -> ed.Destination:
    """The production class with no network step: for tests that fake `subprocess.run` themselves."""
    return ed.Destination(
        repository=SOURCE, phase=ed.PHASE_PRE_CUTOVER, remote=remote, namespaces=NAMESPACES,
        history_branch="benchmark-history", repo_root=repo_root or Path("."),
    )


def patch_resolution(case: unittest.TestCase, module: Any, destination: ed.Destination | None = None) -> mock.MagicMock:
    """Make `module.resolve_destination` return a fixed destination instead of proving a real remote."""
    patcher = mock.patch.object(module, "resolve_destination", return_value=destination or offline_destination())
    started = patcher.start()
    case.addCleanup(patcher.stop)
    return started
