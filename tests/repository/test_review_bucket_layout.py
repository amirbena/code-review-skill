#!/usr/bin/env python3
"""`tests/policy/review/` and `tests/unit/review/` stay decomposed (Issue #293).

#293 split these two buckets' flat 30+-module catch-alls into ownership
sub-packages once real evidence supported a cluster, while deliberately
leaving modules with no second clustering member directly under the
bucket (a single-module "cluster" is not a cluster). This is a soft
regression guard, not a topology whitelist: it does not enumerate the
current sub-packages or cap their size, so a legitimate new cluster
needs no update here. It only flags the two symptoms #293 fixed —
the flat level re-growing past a generous threshold, and a sub-package
created for just one module.
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT

# Generous: #293 left roughly a dozen genuinely unclustered modules flat in
# each bucket. This is a trip-wire for the bucket re-growing into another
# 30+-module catch-all, not a target to keep tightening.
MAX_FLAT_MODULES = 20

REVIEW_BUCKETS = (
    REPO_ROOT / "tests" / "policy" / "review",
    REPO_ROOT / "tests" / "unit" / "review",
)


class ReviewBucketLayoutTests(unittest.TestCase):
    def test_flat_module_count_stays_below_the_sprawl_threshold(self) -> None:
        for bucket in REVIEW_BUCKETS:
            flat_modules = sorted(
                p.name
                for p in bucket.glob("test_*.py")
                if p.is_file()
            )
            with self.subTest(bucket=str(bucket.relative_to(REPO_ROOT))):
                self.assertLess(
                    len(flat_modules),
                    MAX_FLAT_MODULES,
                    f"{bucket} has {len(flat_modules)} flat modules (>= "
                    f"{MAX_FLAT_MODULES}) with no further ownership split: "
                    f"{flat_modules}. Group the new/overlapping ones into an "
                    "ownership sub-package the way Issue #293 did.",
                )

    def test_no_subpackage_holds_only_a_single_module(self) -> None:
        for bucket in REVIEW_BUCKETS:
            for entry in sorted(bucket.iterdir()):
                if not entry.is_dir() or entry.name == "__pycache__":
                    continue
                modules = sorted(
                    p.name for p in entry.glob("test_*.py") if p.is_file()
                )
                with self.subTest(subpackage=str(entry.relative_to(REPO_ROOT))):
                    self.assertGreater(
                        len(modules),
                        1,
                        f"{entry} contains only {modules or 'no'} test module(s); "
                        "a cluster of one belongs flat in the parent bucket instead "
                        "(see Issue #293's non-goals).",
                    )


if __name__ == "__main__":
    unittest.main()
