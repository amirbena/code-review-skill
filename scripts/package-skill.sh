#!/usr/bin/env bash
# Package the portable Code Review Agent Skill into a distributable
# archive, using an explicit allowlist (never the whole repository).
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

package_name="github-code-review-skill"
dist_dir="${repo_root}/dist"
stage_dir="${dist_dir}/${package_name}"
archive_path="${dist_dir}/${package_name}.zip"

# Explicit allowlist of package contents. See policies/ section 28 of the
# task history / README "Packaging" for rationale: pack by allowlist,
# never by copy-then-delete.
files=(
  "SKILL.md"
  "review-config.yaml"
)
dirs=(
  "metadata"
  "policies"
  "runbooks"
  "templates"
)

echo "Repository root: ${repo_root}"

for f in "${files[@]}"; do
  if [[ ! -f "${repo_root}/${f}" ]]; then
    echo "error: required Skill file missing: ${f}" >&2
    exit 1
  fi
done

for d in "${dirs[@]}"; do
  if [[ ! -d "${repo_root}/${d}" ]]; then
    echo "error: required Skill directory missing: ${d}" >&2
    exit 1
  fi
done

# Only ever clean our own controlled staging/output location, never
# anything outside dist/.
rm -rf "${stage_dir}"
mkdir -p "${stage_dir}"

for f in "${files[@]}"; do
  cp "${repo_root}/${f}" "${stage_dir}/${f}"
done

for d in "${dirs[@]}"; do
  mkdir -p "${stage_dir}/${d}"
  cp -R "${repo_root}/${d}/." "${stage_dir}/${d}/"
done

rm -f "${archive_path}"
(
  cd "${dist_dir}"
  zip -r -q "$(basename "${archive_path}")" "${package_name}"
)

echo "Package staged at: ${stage_dir}"
echo "Archive created at: ${archive_path}"
