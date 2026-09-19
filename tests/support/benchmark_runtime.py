"""Shared gate for tests that drive the real benchmark review runtime."""

from __future__ import annotations

import functools
import os
import unittest

REQUIRE_RUNTIME_ENV_VAR = "BENCHMARK_REQUIRE_RUNTIME"


@functools.lru_cache(maxsize=1)
def runtime_unavailable_reason() -> str | None:
    """None when the real review runtime is usable, else why it is not."""
    from runtime_platform.benchmark.scripts.benchmark_review_adapter import check_runtime_available

    try:
        check_runtime_available()
    except Exception as exc:  # noqa: BLE001 - surfaced as the skip/failure reason
        return str(exc)
    return None


class LiveRuntimeTestCase(unittest.TestCase):
    """Skips with the reason when the runtime is unavailable; errors instead
    when ``BENCHMARK_REQUIRE_RUNTIME`` is set, so a missing runtime is never
    read as a pass."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        reason = runtime_unavailable_reason()
        if reason is None:
            return
        if os.environ.get(REQUIRE_RUNTIME_ENV_VAR):
            raise AssertionError(f"{REQUIRE_RUNTIME_ENV_VAR} is set but the runtime is unavailable — {reason}")
        raise unittest.SkipTest(f"skipping the live end-to-end path rather than fabricating a result — {reason}")
