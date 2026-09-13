#!/usr/bin/env bash
# Package one or both Code Review Agent Skills into self-contained,
# standalone distributable archives, using explicit allowlists (never the
# whole repository). Each archive has its own SKILL.md at the archive
# ROOT (not nested under skills/<name>/), so a consumer never needs to
# know this repository's source layout. All generated output (staging
# and final zips) stays strictly under dist/.
#
# Usage:
#   scripts/package-skills.sh [local|github|all]
# Defaults to "all" when no argument is given.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
dist_dir="${repo_root}/dist"
staging_root="${dist_dir}/.staging"
metadata_validator="${script_dir}/validate-skill-metadata.py"
package_manifest="${script_dir}/package-manifest.json"
package_manifest_helper="${script_dir}/package_manifest.py"
package_adapt="${script_dir}/package_adapt.py"

target="${1:-all}"
case "${target}" in
  local|github|all) ;;
  *)
    echo "error: unknown target '${target}' (expected local|github|all)" >&2
    exit 1
    ;;
esac

manifest_query() {
  local package_target="$1"
  local query="$2"
  python3 "${package_manifest_helper}" "${package_manifest}" "${package_target}" "${query}"
}

require_archive_entry() {
  local archive_path="$1"
  local rel_path="$2"
  if ! unzip -l "${archive_path}" | awk '{print $4}' | grep -qx "${rel_path}"; then
    echo "error: archive missing required runtime asset: ${archive_path} (${rel_path})" >&2
    exit 1
  fi
}

# Shared-link adaptation, metadata-path adaptation, and SKILL.md
# frontmatter structural validation are packaging-domain rules shared
# with scripts/package-skills.ps1; both platform scripts delegate to the
# single canonical Python implementation in scripts/package_domain/ (see
# scripts/package_adapt.py) instead of restating the rules here.
validate_skill_frontmatter() {
  local skill_md="$1"
  local expected_name="$2"
  python3 "${package_adapt}" validate-frontmatter "${skill_md}" "${expected_name}"
}

adapt_shared_links() {
  local file="$1"
  python3 "${package_adapt}" adapt-shared-links "${file}"
}

adapt_metadata_paths() {
  local metadata_file="$1"
  python3 "${package_adapt}" adapt-metadata-paths "${metadata_file}"
}

package_skill() {
  local package_target="$1"
  local skill_name
  local archive_name
  skill_name="$(manifest_query "${package_target}" name)"
  archive_name="$(manifest_query "${package_target}" archive)"
  local skill_src="${repo_root}/skills/${skill_name}"
  local stage_dir="${staging_root}/${archive_name%.zip}"
  local archive_path="${dist_dir}/${archive_name}"

  if [[ ! -d "${skill_src}" ]]; then
    echo "error: required Skill directory missing: skills/${skill_name}" >&2
    exit 1
  fi
  python3 "${metadata_validator}" "${skill_src}" --containment-root "${repo_root}"

  # Only ever clean our own controlled staging/output location, and only
  # ever write generated content under dist/.
  rm -rf "${stage_dir}"
  mkdir -p "${stage_dir}"

  local manifest_files
  manifest_files="$(mktemp)"
  if ! manifest_query "${package_target}" files > "${manifest_files}"; then
    rm -f "${manifest_files}"
    exit 1
  fi
  while IFS=$'\t' read -r source destination; do
    if [[ ! -f "${repo_root}/${source}" ]]; then
      rm -f "${manifest_files}"
      echo "error: required package source missing: ${source}" >&2
      exit 1
    fi
    mkdir -p "$(dirname "${stage_dir}/${destination}")"
    cp "${repo_root}/${source}" "${stage_dir}/${destination}"
  done < "${manifest_files}"
  rm -f "${manifest_files}"

  # Adapt relative links into shared/ across every packaged Markdown
  # file (skill-local links like ../SKILL.md or runbooks/... need no
  # change, since skill-internal relative depth is unchanged).
  while IFS= read -r -d '' md_file; do
    adapt_shared_links "${md_file}"
  done < <(find "${stage_dir}" -name '*.md' -print0)
  adapt_metadata_paths "${stage_dir}/metadata/skill.yaml"

  # --- Validate staged package structure before archiving ---
  if [[ ! -f "${stage_dir}/SKILL.md" ]]; then
    echo "error: staged package missing root SKILL.md: ${stage_dir}/SKILL.md" >&2
    exit 1
  fi
  if [[ -d "${stage_dir}/skills" ]]; then
    echo "error: staged package must not contain a nested skills/ directory: ${stage_dir}/skills" >&2
    exit 1
  fi
  if ! grep -q "${skill_name}" "${stage_dir}/SKILL.md"; then
    echo "error: staged root SKILL.md does not identify as '${skill_name}'" >&2
    exit 1
  fi
  validate_skill_frontmatter "${stage_dir}/SKILL.md" "${skill_name}"
  python3 "${metadata_validator}" "${stage_dir}" --containment-root "${stage_dir}"

  rm -f "${archive_path}"
  (
    cd "${stage_dir}"
    zip -r -q "${archive_path}" .
  )

  # --- Verify archive contents ---
  local required_entries
  required_entries="$(mktemp)"
  if ! manifest_query "${package_target}" required_entries > "${required_entries}"; then
    rm -f "${required_entries}"
    exit 1
  fi
  while IFS= read -r required_entry; do
    require_archive_entry "${archive_path}" "${required_entry}"
  done < "${required_entries}"
  rm -f "${required_entries}"
  if unzip -l "${archive_path}" | awk '{print $4}' | grep -q '^skills/'; then
    echo "error: archive must not contain a nested skills/ directory: ${archive_path}" >&2
    exit 1
  fi

  rm -rf "${stage_dir}"

  echo "Archive created at: ${archive_path}"
}

echo "Repository root: ${repo_root}"
mkdir -p "${dist_dir}"

if [[ "${target}" == "local" || "${target}" == "all" ]]; then
  package_skill "local"
fi

if [[ "${target}" == "github" || "${target}" == "all" ]]; then
  package_skill "github"
fi

# Remove the now-empty staging root if packaging left nothing behind.
rmdir "${staging_root}" 2>/dev/null || true
