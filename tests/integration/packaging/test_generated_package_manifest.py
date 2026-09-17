"""Packaging-boundary guard: `package-manifest.json` must match what
`scripts/packaging/generate_package_manifest.py` generates from
`capabilities/*/capability.yaml` (issue #405).

This is the CI check that makes the manifest's `shared_files` and
`skills.*.files` sections a generated projection of the capability
manifests rather than a fifth hand-maintained copy: any edit to a
capability's `files:` list without a matching edit to
`generate_package_manifest.py`'s `_ORDER`/`_CORE_*` tables — or a stray
hand-edit to `package-manifest.json` itself — fails this test.
"""

from __future__ import annotations

import unittest

from tests.integration.packaging._shared import PACKAGE_MANIFEST
from scripts.packaging import generate_package_manifest


class GeneratedPackageManifestTests(unittest.TestCase):
    def test_generated_manifest_is_byte_identical_to_committed_file(self) -> None:
        generated = generate_package_manifest.generate()
        committed = PACKAGE_MANIFEST.read_text(encoding="utf-8")
        self.assertEqual(
            generated,
            committed,
            "package-manifest.json has diverged from capabilities/*/capability.yaml — "
            "regenerate it with `python3 scripts/packaging/generate_package_manifest.py --write`",
        )

    def test_generator_rejects_a_capability_file_missing_from_the_order_table(self) -> None:
        capability_files = generate_package_manifest._load_capability_files()
        capability_files["scale"].append("shared/policies/not-yet-in-the-order-table.md")
        with self.assertRaises(ValueError):
            generate_package_manifest._resolve_section(
                generate_package_manifest._SHARED_ORDER,
                generate_package_manifest._CORE_SHARED,
                capability_files,
                prefix="shared/",
            )

    def test_generator_rejects_an_order_entry_no_longer_owned_by_its_capability(self) -> None:
        capability_files = generate_package_manifest._load_capability_files()
        capability_files["scale"].remove("shared/policies/large-pr-partitioning.md")
        with self.assertRaises(ValueError):
            generate_package_manifest._resolve_section(
                generate_package_manifest._SHARED_ORDER,
                generate_package_manifest._CORE_SHARED,
                capability_files,
                prefix="shared/",
            )

    def test_generator_rejects_a_file_owned_by_two_capabilities(self) -> None:
        capability_files = generate_package_manifest._load_capability_files()
        capability_files["conditional-passes"].append(
            "shared/policies/large-pr-partitioning.md"
        )
        with self.assertRaises(ValueError):
            generate_package_manifest._resolve_section(
                generate_package_manifest._SHARED_ORDER,
                generate_package_manifest._CORE_SHARED,
                capability_files,
                prefix="shared/",
            )

    def test_generator_rejects_a_core_file_also_claimed_by_a_capability(self) -> None:
        capability_files = generate_package_manifest._load_capability_files()
        capability_files["scale"].append("shared/policies/severity.md")
        with self.assertRaises(ValueError):
            generate_package_manifest._resolve_section(
                generate_package_manifest._SHARED_ORDER,
                generate_package_manifest._CORE_SHARED,
                capability_files,
                prefix="shared/",
            )


if __name__ == "__main__":
    unittest.main()
