"""Argument parsing for the Skill metadata validator."""

from __future__ import annotations

import argparse
from pathlib import Path

from .orchestrator import validate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_root", type=Path)
    parser.add_argument("--containment-root", type=Path)
    args = parser.parse_args()
    root = args.skill_root.resolve()
    containment = (args.containment_root or root).resolve()
    validate(root, containment)


if __name__ == "__main__":
    main()
