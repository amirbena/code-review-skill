#!/usr/bin/env python3
"""Publication CLI entrypoint; contract: runtime_platform/benchmark/publication-cli.md.

Usage::

    python3 runtime_platform/benchmark/scripts/publish_benchmark.py sweep --once --dry-run
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.publisher.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
