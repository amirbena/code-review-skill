"""Repository-owned test suite and its test-only reference models."""

import faulthandler
import os
import sys

if os.environ.get("CI"):
    # Every 5 minutes the stack of every thread goes to stderr, so a hung run shows the stuck test.
    faulthandler.dump_traceback_later(300, repeat=True, file=sys.stderr)
