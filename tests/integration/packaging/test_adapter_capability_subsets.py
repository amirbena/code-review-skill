"""Packaging-boundary guard: each adapter's derived capability subset must
match what its archive actually ships (issue #407).

`capabilities/*/capability.yaml` already declares `adapters:` (issue
#404's schema). This asserts that declaration is not just internally
well-formed (`tests/policy/governance/test_capability_manifest_schema.py`)
but actually reconciles with `package-manifest.json`: for every
capability-owned file, the set of adapters
`generate_package_manifest.derive_adapter_subsets()` derives from
`adapters:` must equal the set of adapters whose archive the file is
actually present in today. No archive contents change here (see the
capability-manifest-schema doc, "What this step does not do") — this
only makes the boundary an asserted invariant instead of an implicit one,
so a future capability addition that omits or misstates adapter
applicability fails CI instead of silently shipping a file to an adapter
its manifest doesn't claim (or omitting it from one it does).
"""

from __future__ import annotations

import unittest

from scripts.packaging import generate_package_manifest


class AdapterCapabilitySubsetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.capability_files = generate_package_manifest._load_capability_files()
        self.manifest = generate_package_manifest.build_manifest()
        self.owned_files = {
            source for files in self.capability_files.values() for source in files
        }

    def _actual_capability_owned(self, adapter: str) -> set[str]:
        shared_sources = {entry["source"] for entry in self.manifest["shared_files"]}
        skill_sources = {
            entry["source"] for entry in self.manifest["skills"][adapter]["files"]
        }
        return (shared_sources | skill_sources) & self.owned_files

    def test_derived_local_subset_matches_the_local_archive(self) -> None:
        derived = generate_package_manifest.derive_adapter_subsets()
        self.assertEqual(derived["local"], self._actual_capability_owned("local"))

    def test_derived_github_subset_matches_the_github_archive(self) -> None:
        derived = generate_package_manifest.derive_adapter_subsets()
        self.assertEqual(derived["github"], self._actual_capability_owned("github"))

    def test_every_capability_owned_shared_file_declares_both_adapters(self) -> None:
        # Neither archive special-cases shared/ files by adapter today (no
        # lazy loading yet — see the schema doc's "next child" note), so a
        # capability that owns a shared/ file but doesn't declare both
        # adapters would make the two tests above fail. Assert the
        # precondition directly for a clearer failure message.
        manifests = generate_package_manifest._load_capability_manifests()
        for capability, manifest in manifests.items():
            shared_files = [f for f in manifest["files"] if f.startswith("shared/")]
            if shared_files:
                with self.subTest(capability=capability):
                    self.assertEqual(
                        set(manifest["adapters"]),
                        {"local", "github"},
                        f"{capability!r} owns shared/ file(s) {shared_files} but "
                        f"declares adapters {manifest['adapters']!r} — both "
                        "archives still ship every shared/ file, so a "
                        "shared-owning capability must declare both adapters "
                        "until per-adapter shared packaging exists",
                    )

    def test_a_local_file_owned_by_a_github_only_capability_is_rejected(self) -> None:
        manifests = generate_package_manifest._load_capability_manifests()
        manifests["scale"]["files"].append("skills/local-code-review/SKILL.md")
        manifests["scale"]["adapters"] = ["github"]
        with self.assertRaises(ValueError):
            generate_package_manifest.derive_adapter_subsets(manifests)

    def test_a_github_file_owned_by_a_local_only_capability_is_rejected(self) -> None:
        manifests = generate_package_manifest._load_capability_manifests()
        manifests["scale"]["files"].append("skills/github-pr-review/SKILL.md")
        manifests["scale"]["adapters"] = ["local"]
        with self.assertRaises(ValueError):
            generate_package_manifest.derive_adapter_subsets(manifests)

    def test_a_shared_file_owned_by_a_single_adapter_capability_diverges_from_the_archive(
        self,
    ) -> None:
        # Simulates the exact regression this guard exists to catch: a
        # future capability declares a narrower `adapters:` than the
        # archives actually ship its shared/ file to. `derive_adapter_subsets`
        # itself doesn't raise for this case (a shared/ file legitimately
        # can be single-adapter once per-adapter packaging exists) — the
        # divergence must surface as a mismatch against the archive, which
        # is what CI actually checks.
        manifests = generate_package_manifest._load_capability_manifests()
        manifests["scale"]["adapters"] = ["github"]
        derived = generate_package_manifest.derive_adapter_subsets(manifests)
        self.assertNotEqual(derived["local"], self._actual_capability_owned("local"))


if __name__ == "__main__":
    unittest.main()
