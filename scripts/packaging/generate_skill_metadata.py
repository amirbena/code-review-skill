#!/usr/bin/env python3
"""Generate each Skill's `metadata/skill.yaml` `shared:` block from
`capabilities/*/capability.yaml` (issue #406).

`package-manifest.json`'s `shared_files` (itself generated from
`capabilities/*/capability.yaml` — see `generate_package_manifest.py`,
issue #405) is the single authoritative statement of which shared
policies and templates ship with each Skill. `metadata/skill.yaml`'s
`shared: policies:` / `shared: templates:` lists are pure data — no
authored prose — so per
`docs/capability-architecture/capability-architecture-model.md` §J.2 this
step generates them directly rather than adding a validator: this closes
the divergence §A.9 names (17 shared policies shipping in
`local-code-review-skill.zip` undeclared in its own `metadata/skill.yaml`,
and `shared/templates/finding-rendering.md` declared in neither Skill's
metadata).

Every other field in `metadata/skill.yaml` (name, description, version,
capabilities, output, …) stays hand-authored prose; this module only
ever rewrites the trailing `shared:` block, leaving the rest of the file
byte-identical.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.packaging.generate_package_manifest import build_manifest  # noqa: E402

# metadata/skill.yaml lives at skills/<name>/metadata/skill.yaml; shared/
# lives at the repo root, three levels up.
_RELATIVE_PREFIX = "../../../"

_SKILL_METADATA_PATHS = {
    "local": REPO_ROOT / "skills" / "local-code-review" / "metadata" / "skill.yaml",
    "github": REPO_ROOT / "skills" / "github-pr-review" / "metadata" / "skill.yaml",
}

# Matches the trailing `shared:` block (the key and every indented line
# under it) through end of file.
_SHARED_BLOCK_RE = re.compile(r"\nshared:\n(?:[ \t].*\n?)*\Z")


def _shared_block(shared_files: list[dict[str, str]]) -> str:
    policies = [
        f["source"] for f in shared_files if f["source"].startswith("shared/policies/")
    ]
    templates = [
        f["source"] for f in shared_files if f["source"].startswith("shared/templates/")
    ]
    lines = ["shared:", "  policies:"]
    lines += [f"    - {_RELATIVE_PREFIX}{path}" for path in policies]
    lines.append("  templates:")
    lines += [f"    - {_RELATIVE_PREFIX}{path}" for path in templates]
    return "\n".join(lines) + "\n"


def generate_metadata_text(current_text: str, shared_files: list[dict[str, str]]) -> str:
    """Replace `current_text`'s trailing `shared:` block with one
    generated from `shared_files`, leaving everything before it untouched.
    """
    if not _SHARED_BLOCK_RE.search(current_text):
        raise ValueError("metadata/skill.yaml has no trailing `shared:` block to replace")
    return _SHARED_BLOCK_RE.sub("\n" + _shared_block(shared_files), current_text)


def generate() -> dict[str, str]:
    """Return {skill_key: full generated metadata/skill.yaml text}."""
    shared_files = build_manifest()["shared_files"]
    return {
        key: generate_metadata_text(path.read_text(encoding="utf-8"), shared_files)
        for key, path in _SKILL_METADATA_PATHS.items()
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if any metadata/skill.yaml's shared: block is stale",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the generated shared: block into each metadata/skill.yaml",
    )
    args = parser.parse_args()

    generated = generate()

    if args.write:
        for key, path in _SKILL_METADATA_PATHS.items():
            path.write_text(generated[key], encoding="utf-8")
        return 0

    if args.check:
        ok = True
        for key, path in _SKILL_METADATA_PATHS.items():
            current = path.read_text(encoding="utf-8")
            if current != generated[key]:
                print(
                    f"error: {path} shared: block is stale relative to "
                    "capabilities/*/capability.yaml; run "
                    "`python3 scripts/packaging/generate_skill_metadata.py --write`"
                )
                ok = False
        return 0 if ok else 1

    for key, text in generated.items():
        print(f"--- {_SKILL_METADATA_PATHS[key]} ---")
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
