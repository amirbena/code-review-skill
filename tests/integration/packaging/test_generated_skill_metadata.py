"""Packaging-boundary guard: each Skill's `metadata/skill.yaml` `shared:`
block must match what `scripts/packaging/generate_skill_metadata.py`
generates from `capabilities/*/capability.yaml` (issue #406).

This is the second projection of the same capability manifest
`test_generated_package_manifest.py` guards for `package-manifest.json`
(issue #405): `metadata/skill.yaml`'s `shared: policies:` / `shared:
templates:` lists are pure data, so they are generated rather than
hand-maintained, closing the divergence
`docs/capability-architecture/capability-architecture-model.md` §A.9
names — 17 shared policies shipping in `local-code-review-skill.zip`
undeclared in its own metadata, and `shared/templates/finding-rendering.md`
declared in neither Skill's metadata.
"""

from __future__ import annotations

import unittest

from scripts.packaging import generate_package_manifest, generate_skill_metadata


class GeneratedSkillMetadataTests(unittest.TestCase):
    def test_generated_shared_block_is_byte_identical_to_committed_files(self) -> None:
        generated = generate_skill_metadata.generate()
        for key, path in generate_skill_metadata._SKILL_METADATA_PATHS.items():
            committed = path.read_text(encoding="utf-8")
            self.assertEqual(
                generated[key],
                committed,
                f"{path} shared: block has diverged from "
                "capabilities/*/capability.yaml — regenerate it with "
                "`python3 scripts/packaging/generate_skill_metadata.py --write`",
            )

    def test_every_shared_file_appears_in_the_generated_block(self) -> None:
        generated = generate_skill_metadata.generate()
        shared_files = [
            entry["source"]
            for entry in generate_package_manifest.build_manifest()["shared_files"]
            if entry["source"].startswith("shared/")
        ]
        for key, text in generated.items():
            for source in shared_files:
                self.assertIn(
                    source,
                    text,
                    f"metadata for {key!r} is missing shared file {source!r}",
                )

    def test_generator_replaces_only_the_trailing_shared_block(self) -> None:
        original = (
            "name: example\n"
            "description: >-\n"
            "  Example.\n"
            "\n"
            "shared:\n"
            "  policies:\n"
            "    - ../../../shared/policies/old.md\n"
            "  templates:\n"
            "    - ../../../shared/templates/old.md\n"
        )
        shared_files = [
            {"source": "shared/policies/new.md", "destination": "shared/policies/new.md"},
            {"source": "shared/templates/new.md", "destination": "shared/templates/new.md"},
        ]
        regenerated = generate_skill_metadata.generate_metadata_text(original, shared_files)
        self.assertIn("name: example\n", regenerated)
        self.assertIn("../../../shared/policies/new.md", regenerated)
        self.assertIn("../../../shared/templates/new.md", regenerated)
        self.assertNotIn("old.md", regenerated)

    def test_generator_rejects_metadata_with_no_shared_block(self) -> None:
        with self.assertRaises(ValueError):
            generate_skill_metadata.generate_metadata_text("name: example\n", [])

    def test_generator_tolerates_a_blank_line_inside_the_shared_block(self) -> None:
        # A wholly blank separator line (no leading whitespace) between
        # `policies:` and `templates:` must not break the trailing
        # `shared:` block match — the same visual-separator style already
        # used between other top-level sections in these files.
        original = (
            "name: example\n"
            "description: >-\n"
            "  Example.\n"
            "\n"
            "shared:\n"
            "  policies:\n"
            "    - ../../../shared/policies/old.md\n"
            "\n"
            "  templates:\n"
            "    - ../../../shared/templates/old.md\n"
        )
        shared_files = [
            {"source": "shared/policies/new.md", "destination": "shared/policies/new.md"},
            {"source": "shared/templates/new.md", "destination": "shared/templates/new.md"},
        ]
        regenerated = generate_skill_metadata.generate_metadata_text(original, shared_files)
        self.assertIn("name: example\n", regenerated)
        self.assertIn("../../../shared/policies/new.md", regenerated)
        self.assertIn("../../../shared/templates/new.md", regenerated)
        self.assertNotIn("old.md", regenerated)


if __name__ == "__main__":
    unittest.main()
