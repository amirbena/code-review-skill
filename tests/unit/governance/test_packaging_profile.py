from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validation import packaging_profile as profile


class SpawnLabelTests(unittest.TestCase):
    def test_script_and_subcommand_group_spawns(self):
        self.assertEqual(profile.spawn_label("/r/scripts/package_adapt.py adapt-shared-links --x /p"), "package_adapt.py adapt-shared-links")

    def test_flag_or_stdin_invocations_do_not_crash(self):
        self.assertEqual(profile.spawn_label(""), "python3 (interactive/stdin)")
        self.assertEqual(profile.spawn_label("-"), "-")

    def test_script_without_subcommand_keeps_the_script_name(self):
        self.assertEqual(profile.spawn_label("/r/validate-skill-metadata.py /skills/x"), "validate-skill-metadata.py")


class SpawnLogTests(unittest.TestCase):
    def test_read_spawns_computes_durations_and_missing_log_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "spawns.tsv"
            self.assertEqual(profile.read_spawns(log), [])
            log.write_text("1.0\t1.5\ta.py sub arg\n2.0\t2.25\tb.py\n", encoding="utf-8")
            spawns = profile.read_spawns(log)
        self.assertEqual([s["seconds"] for s in spawns], [0.5, 0.25])
        self.assertEqual([s["label"] for s in spawns], ["a.py sub", "b.py"])

    def test_render_lists_phases_only_for_cold_runs(self):
        run = {
            "mode": "all", "cold": True, "wall_seconds": 3.0, "cpu_seconds": 2.0, "python_spawns": 2,
            "python_spawn_seconds": 1.0, "shell_other_seconds": 2.0, "manifest_sha256": "ab" * 32,
            "phases": {"a.py sub": {"count": 2, "seconds": 1.0}},
        }
        warm = dict(run, cold=False)
        text = profile.render({"bash": "3.2", "python": "3", "platform": "p", "python_start_seconds": 0.02, "runs": [run, warm]})
        self.assertEqual(text.count("**Phases, all cold**"), 1)
        self.assertIn("| `a.py sub` | 2 | 1.00 |", text)


if __name__ == "__main__":
    unittest.main()
