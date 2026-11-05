"""Packaging-boundary guard: the declarative package manifest -- schema,
source/destination path safety, and Windows-path-escape rejection --
exercised through a synthetic manifest, since the real one declares no
Skill until the cutover."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.integration.packaging._shared import PACKAGE_MANIFEST_HELPER, _package_manifest

SKILL = "review-example"


def _base() -> dict:
    return {
        "schema_version": 1,
        "shared_files": [{"source": "LICENSE", "destination": "LICENSE"}],
        "skills": {
            "example": {
                "name": SKILL,
                "archive": "review-example-skill.zip",
                "files": [{"source": f"skills/{SKILL}/SKILL.md", "destination": "SKILL.md"}],
                "required_entries": ["SKILL.md"],
            }
        },
    }


def _run(manifest: dict, query: str = "validate", target: str = "example") -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(PACKAGE_MANIFEST_HELPER), str(path), target, query],
            capture_output=True,
            text=True,
            check=False,
        )


class PackageManifestTests(unittest.TestCase):
    def test_repository_manifest_is_schema_v1(self) -> None:
        manifest = _package_manifest()
        self.assertEqual(manifest["schema_version"], 1)
        self.assertIn("skills", manifest)

    def test_ordinary_posix_relative_paths_are_accepted(self) -> None:
        result = _run(_base())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_targets_query_lists_manifest_targets(self) -> None:
        result = _run(_base(), query="targets", target="-")
        self.assertEqual(result.stdout.split(), ["example"])

    def test_unknown_target_is_rejected(self) -> None:
        self.assertNotEqual(_run(_base(), target="missing").returncode, 0)

    def test_rejects_repository_development_shared_source(self) -> None:
        manifest = _base()
        manifest["shared_files"].append({"source": "AGENTS.md", "destination": "AGENTS.md"})
        result = _run(manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shared package source escapes approved roots", result.stderr)

    def test_rejects_cross_skill_source(self) -> None:
        manifest = _base()
        manifest["skills"]["example"]["files"].append(
            {"source": "skills/review-other/SKILL.md", "destination": "other.md"}
        )
        result = _run(manifest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"Skill package source escapes skills/{SKILL}/", result.stderr)

    def test_rejects_windows_style_path_escapes(self) -> None:
        def entry(manifest: dict, source: str, destination: str) -> None:
            manifest["skills"]["example"]["files"].append({"source": source, "destination": destination})

        mutations = (
            lambda m: m["skills"]["example"].update(archive="..\\outside.zip"),
            lambda m: m["skills"]["example"].update(name="..\\review-other"),
            lambda m: entry(m, f"skills/{SKILL}\\..\\review-other/SKILL.md", "copied.md"),
            lambda m: entry(m, f"skills/{SKILL}/SKILL.md", "..\\outside.md"),
            lambda m: m["skills"]["example"]["required_entries"].append("..\\outside.md"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                manifest = _base()
                mutate(manifest)
                result = _run(manifest)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("safe POSIX-style relative path", result.stderr)

    def test_rejects_windows_drives_roots_and_wildcards(self) -> None:
        def entry(manifest: dict, source: str, destination: str) -> None:
            manifest["skills"]["example"]["files"].append({"source": source, "destination": destination})

        mutations = (
            lambda m: m["skills"]["example"].update(archive="C:outside.zip"),
            lambda m: entry(m, f"skills/{SKILL}/SKILL.md", "C:/outside"),
            lambda m: entry(m, f"skills/{SKILL}/SKILL.md", "//server/share/outside.md"),
            lambda m: entry(m, f"skills/{SKILL}/foo/*.md", "wildcard-star.md"),
            lambda m: entry(m, f"skills/{SKILL}/foo/?ar.txt", "wildcard-question.md"),
            lambda m: entry(m, f"skills/{SKILL}/foo/[ab].txt", "wildcard-brackets.md"),
            lambda m: m["skills"]["example"].update(archive="review-*.zip"),
            lambda m: entry(m, f"skills/{SKILL}/SKILL.md", "templates/[draft].md"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                manifest = _base()
                mutate(manifest)
                self.assertNotEqual(_run(manifest).returncode, 0)

    def test_rejects_duplicate_destinations(self) -> None:
        manifest = _base()
        manifest["skills"]["example"]["files"].append(
            {"source": f"skills/{SKILL}/SKILL.md", "destination": "SKILL.md"}
        )
        self.assertNotEqual(_run(manifest).returncode, 0)


if __name__ == "__main__":
    unittest.main()
