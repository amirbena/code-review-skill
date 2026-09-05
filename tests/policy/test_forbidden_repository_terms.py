#!/usr/bin/env python3
"""Prevent retired product terminology from returning to tracked content."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT


RETIRED_PRODUCT_TERM = re.compile("bill" + r"[ _-]*" + "pay", re.IGNORECASE)


def _tracked_paths() -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return tuple(REPO_ROOT / path.decode("utf-8") for path in result.stdout.split(b"\0") if path)


class ForbiddenRepositoryTermsTests(unittest.TestCase):
    def test_retired_product_term_is_absent_from_tracked_paths_and_text(self) -> None:
        offenders: list[str] = []

        for path in _tracked_paths():
            relative_path = path.relative_to(REPO_ROOT).as_posix()
            if RETIRED_PRODUCT_TERM.search(relative_path):
                offenders.append(relative_path)

            raw = path.read_bytes()
            if b"\0" in raw:
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if RETIRED_PRODUCT_TERM.search(text):
                offenders.append(relative_path)

        self.assertEqual(offenders, [], f"retired product terminology found in: {offenders}")


if __name__ == "__main__":
    unittest.main()
