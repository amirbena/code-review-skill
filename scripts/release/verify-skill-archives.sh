#!/usr/bin/env bash
#
# Build (optionally) and verify the Skill distribution archives.
#
# Shared by the `package` and `publish` jobs of
# .github/workflows/release-worthiness.yml so the "package, unzip -t every
# archive, confirm both expected zips exist" sequence has one
# implementation instead of two drifting inline `run: |` copies.
#
# CI-only: release automation runs exclusively on Linux GitHub Actions
# runners, so there is deliberately no PowerShell counterpart under
# scripts/. The local packaging entrypoint for developers on any platform
# stays scripts/packaging/package-skills.sh / scripts/packaging/package-skills.ps1.
#
# Usage:
#   scripts/release/verify-skill-archives.sh [--build] [--expect-version X.Y.Z]
#
#   --build                 Run `scripts/packaging/package-skills.sh all` first.
#                           Without it the script only verifies archives
#                           already present under dist/.
#   --expect-version X.Y.Z  Also fail unless every archive's SKILL.md
#                           frontmatter version is exactly X.Y.Z (the release
#                           version being published).

set -euo pipefail

build=0
expect_version=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --build) build=1; shift ;;
    --expect-version)
      if [[ $# -lt 2 || -z "$2" ]]; then
        echo "error: --expect-version requires a value" >&2; exit 2
      fi
      expect_version="$2"; shift 2 ;;
    *) echo "error: unknown argument: $1" >&2; exit 2 ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_root}"

manifest="scripts/packaging/package-manifest.json"
expected_archives=()
for target in local github; do
  expected_archives+=("$(python3 scripts/packaging/package_manifest.py "${manifest}" "${target}" archive)")
done

if [[ "${build}" -eq 1 ]]; then
  ./scripts/packaging/package-skills.sh all
fi

shopt -s nullglob
archives=(dist/*.zip)
shopt -u nullglob
if [[ "${#archives[@]}" -eq 0 ]]; then
  echo "::error::no archives found under dist/ (run with --build, or package first)" >&2
  exit 1
fi

for archive in "${archives[@]}"; do
  echo "== ${archive} =="
  unzip -t "${archive}"
done

for name in "${expected_archives[@]}"; do
  if [[ ! -f "dist/${name}" ]]; then
    echo "::error::expected release archive dist/${name} is missing" >&2
    exit 1
  fi
done

if [[ -n "${expect_version}" ]]; then
  python3 scripts/release/release_worthiness.py verify-archive-versions --version "${expect_version}"
fi

echo "Verified $(printf '%s ' "${expected_archives[@]}")under dist/"
