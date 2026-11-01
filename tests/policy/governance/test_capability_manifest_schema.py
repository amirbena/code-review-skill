#!/usr/bin/env python3
"""Schema guard for `capabilities/<name>/capability.yaml` (issue #404).

This is additive infrastructure for the capability-architecture
migration (`docs/capability-architecture/capability-architecture-model.md`,
`docs/capability-architecture/capability-manifest-schema.md`). It asserts
each manifest is internally well-formed. It deliberately does not assert
consistency with `scripts/packaging/package-manifest.json` or either
Skill's `metadata/skill.yaml` — reconciling those is a later, separate
step, and no consumer reads these manifests yet.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from tests.support.paths import REPO_ROOT

CAPABILITIES_DIR = REPO_ROOT / "capabilities"

REQUIRED_STRING_FIELDS = ("capability", "summary", "loads", "benchmark")
REQUIRED_LIST_FIELDS = ("adapters", "files", "requires", "never")
VALID_LOADS = {"always", "on-activation"}
VALID_ADAPTERS = {"local", "github"}
EXPECTED_MANIFESTS = {
    "authorization-github",
    "conditional-passes",
    "context-resolution",
    "design-reference",
    "external-contract-context",
    "finding-placement-derivation",
    "parallel-execution",
    "publication-github",
    "reasoning-checkpoint",
    "remediation",
    "rendered-inspection",
    "repository-checkout",
    "reviewer-assist",
    "runtime-execution",
    "scale",
    "specialist-depth",
    "stateful-review",
    "structured-output",
    "workspace-sibling-context",
}
UNMANIFESTED_REQUIRES_TARGETS = {
    "capability-posture",
    "review-router",
    "review-kernel",
    "finding-contract",
    "review-context-core",
}


def _manifest_paths() -> list[Path]:
    return sorted(CAPABILITIES_DIR.glob("*/capability.yaml"))


class TestCapabilityManifestSchema(unittest.TestCase):
    def test_at_least_one_manifest_exists(self) -> None:
        self.assertTrue(
            _manifest_paths(),
            f"expected at least one capabilities/*/capability.yaml under {CAPABILITIES_DIR}",
        )

    def test_manifest_directory_set_is_exact(self) -> None:
        found = {path.parent.name for path in _manifest_paths()}
        self.assertEqual(
            found,
            EXPECTED_MANIFESTS,
            f"manifest set drifted; missing: {sorted(EXPECTED_MANIFESTS - found)}, "
            f"unexpected: {sorted(found - EXPECTED_MANIFESTS)}",
        )

    def test_requires_targets_resolve_to_manifests_or_documented_unmanifested_names(
        self,
    ) -> None:
        for name in UNMANIFESTED_REQUIRES_TARGETS:
            manifest_path = CAPABILITIES_DIR / name / "capability.yaml"
            self.assertFalse(
                manifest_path.exists(),
                f"{name!r} has a manifest; remove it from UNMANIFESTED_REQUIRES_TARGETS",
            )

        valid_targets = EXPECTED_MANIFESTS | UNMANIFESTED_REQUIRES_TARGETS
        for path in _manifest_paths():
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            for dependency in manifest["requires"]:
                with self.subTest(
                    manifest=path.parent.name,
                    dependency=dependency,
                ):
                    self.assertIn(
                        dependency,
                        valid_targets,
                        f"unresolved requires target {dependency!r} in {path}",
                    )

    def test_each_manifest_is_well_formed(self) -> None:
        manifests = _manifest_paths()
        self.assertTrue(manifests)

        for path in manifests:
            with self.subTest(manifest=str(path.relative_to(REPO_ROOT))):
                manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
                self.assertIsInstance(manifest, dict)

                for field in REQUIRED_STRING_FIELDS:
                    self.assertIn(field, manifest, f"missing required field {field!r}")
                    value = manifest[field]
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip(), f"field {field!r} must be non-empty")

                for field in REQUIRED_LIST_FIELDS:
                    self.assertIn(field, manifest, f"missing required field {field!r}")
                    self.assertIsInstance(manifest[field], list, f"field {field!r} must be a list")

                # identity: capability name matches its directory
                self.assertEqual(manifest["capability"], path.parent.name)

                # loads / activation
                self.assertIn(manifest["loads"], VALID_LOADS)
                has_activation = "activation" in manifest
                if manifest["loads"] == "on-activation":
                    self.assertTrue(
                        has_activation,
                        "loads: on-activation requires a non-empty 'activation' list",
                    )
                    self.assertIsInstance(manifest["activation"], list)
                    self.assertTrue(manifest["activation"])
                else:
                    self.assertFalse(
                        has_activation,
                        "loads: always must omit 'activation'",
                    )

                # adapters: non-empty subset of {local, github}
                adapters = manifest["adapters"]
                self.assertTrue(adapters, "'adapters' must be non-empty")
                self.assertTrue(set(adapters) <= VALID_ADAPTERS, f"unknown adapter(s) in {adapters}")

                # files: non-empty, and every path must exist in the repo
                self.assertTrue(manifest["files"], "'files' must be non-empty")
                for rel_path in manifest["files"]:
                    self.assertIsInstance(rel_path, str)
                    self.assertTrue(
                        (REPO_ROOT / rel_path).is_file(),
                        f"declared file does not exist: {rel_path}",
                    )

                # requires: list of strings (empty allowed)
                for dependency in manifest["requires"]:
                    self.assertIsInstance(dependency, str)

                # never: at least one non-empty clause
                self.assertTrue(manifest["never"], "'never' must have at least one clause")
                for clause in manifest["never"]:
                    self.assertIsInstance(clause, str)
                    self.assertTrue(clause.strip())


if __name__ == "__main__":
    unittest.main()
