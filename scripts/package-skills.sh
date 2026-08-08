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

target="${1:-all}"
case "${target}" in
  local|github|all) ;;
  *)
    echo "error: unknown target '${target}' (expected local|github|all)" >&2
    exit 1
    ;;
esac

# Shared files, by package-relative destination path.
shared_policies=(
  "review-scope.md"
  "severity.md"
  "evidence.md"
  "repository-instructions.md"
  "git-safety.md"
  "review-ownership.md"
  "file-reviewability.md"
)
shared_templates=(
  "finding.md"
  "review-summary.md"
)

# Runtime assets that must be present in the packaged github-pr-review
# archive, verified independently of the general skill_files allowlist
# passed to package_skill below — so a future edit that drops an entry
# from that allowlist still fails packaging instead of silently shipping
# an incomplete archive. external-review-summary.md is a required
# runtime dependency (referenced by SKILL.md and both runbooks), not
# repository-only documentation.
github_required_runtime_templates=(
  "templates/external-review-summary.md"
)

require_source_file() {
  local skill_name="$1"
  local skill_src="$2"
  local rel_path="$3"
  if [[ ! -f "${skill_src}/${rel_path}" ]]; then
    echo "error: required runtime template missing for ${skill_name}: skills/${skill_name}/${rel_path}" >&2
    exit 1
  fi
}

require_archive_entry() {
  local archive_path="$1"
  local rel_path="$2"
  if ! unzip -l "${archive_path}" | awk '{print $4}' | grep -qx "${rel_path}"; then
    echo "error: archive missing required runtime asset: ${archive_path} (${rel_path})" >&2
    exit 1
  fi
}

# Rewrite relative links into shared/ so they resolve from the archive
# root instead of from skills/<name>/. Packaging strips exactly the two
# path segments ("skills/<name>/"), so every "../../shared/" (used by
# SKILL.md, at source depth 2) becomes "shared/", and every
# "../../../shared/" (used by files one level under the Skill, at source
# depth 3: runbooks/, templates/, policies/) becomes "../shared/". This
# is a narrow, deterministic substitution scoped to the exact link
# prefixes that point into shared/ — it never touches any other text.
# Guard against a regression stripping/corrupting the Agent Skills
# YAML frontmatter of a packaged root SKILL.md. This is a narrow
# structural check (line 1 is the opening delimiter, a closing
# delimiter exists, and the required name/description fields are
# present with the expected name) — not a full YAML validator. Prefers
# python3's YAML support when available for a real parse; otherwise
# falls back to the same structural check without attempting to
# reimplement YAML.
validate_skill_frontmatter() {
  local skill_md="$1"
  local expected_name="$2"

  local first_line
  first_line="$(head -n 1 "${skill_md}")"
  if [[ "${first_line}" != "---" ]]; then
    echo "error: ${skill_md} does not start with '---' frontmatter delimiter on line 1" >&2
    exit 1
  fi

  local closing_line
  closing_line="$(awk 'NR>1 && /^---$/ {print NR; exit}' "${skill_md}")"
  if [[ -z "${closing_line}" ]]; then
    echo "error: ${skill_md} frontmatter has no closing '---' delimiter" >&2
    exit 1
  fi

  if command -v python3 >/dev/null 2>&1 && python3 -c "import yaml" >/dev/null 2>&1; then
    python3 - "${skill_md}" "${expected_name}" <<'PYEOF'
import sys, yaml
skill_md, expected_name = sys.argv[1], sys.argv[2]
with open(skill_md, encoding="utf-8") as f:
    lines = f.read().split("\n")
end = lines[1:].index("---") + 1
data = yaml.safe_load("\n".join(lines[1:end])) or {}
name = data.get("name")
description = data.get("description")
if not name:
    sys.exit(f"error: {skill_md} frontmatter missing required 'name'")
if not description:
    sys.exit(f"error: {skill_md} frontmatter missing required 'description'")
if name != expected_name:
    sys.exit(f"error: {skill_md} frontmatter name '{name}' does not match expected '{expected_name}'")
PYEOF
    if [[ $? -ne 0 ]]; then
      exit 1
    fi
  else
    local fm_body
    fm_body="$(sed -n "2,${closing_line}p" "${skill_md}")"
    if ! grep -qE '^name:[[:space:]]*'"${expected_name}"'[[:space:]]*$' <<<"${fm_body}"; then
      echo "error: ${skill_md} frontmatter missing 'name: ${expected_name}'" >&2
      exit 1
    fi
    if ! grep -qE '^description:' <<<"${fm_body}"; then
      echo "error: ${skill_md} frontmatter missing required 'description'" >&2
      exit 1
    fi
    echo "note: python3 yaml module unavailable — used structural fallback validation for ${skill_md}" >&2
  fi
}

adapt_shared_links() {
  local file="$1"
  local tmp
  tmp="$(mktemp)"
  sed -e 's#\.\./\.\./\.\./shared/#../shared/#g' \
      -e 's#\.\./\.\./shared/#shared/#g' \
      "${file}" > "${tmp}"
  mv "${tmp}" "${file}"
}

# metadata/skill.yaml remains source-relative in the repository. Adapt only
# its known shared-resource prefix in the staged copy, where metadata/ is one
# level below the standalone package root.
adapt_metadata_paths() {
  local metadata_file="$1"
  local tmp
  tmp="$(mktemp)"
  sed -e 's#^\([[:space:]]*- [[:space:]]*\)\.\./\.\./\.\./shared/#\1../shared/#' \
      "${metadata_file}" > "${tmp}"
  mv "${tmp}" "${metadata_file}"
}

package_skill() {
  local skill_name="$1"       # e.g. local-code-review
  local archive_stem="$2"     # e.g. local-code-review-skill
  shift 2
  local skill_files=("$@")    # paths relative to skills/<skill_name>/

  local skill_src="${repo_root}/skills/${skill_name}"
  local stage_dir="${staging_root}/${archive_stem}"
  local archive_path="${dist_dir}/${archive_stem}.zip"

  if [[ ! -d "${skill_src}" ]]; then
    echo "error: required Skill directory missing: skills/${skill_name}" >&2
    exit 1
  fi
  if [[ ! -f "${skill_src}/SKILL.md" ]]; then
    echo "error: required Skill entry point missing: skills/${skill_name}/SKILL.md" >&2
    exit 1
  fi
  python3 "${metadata_validator}" "${skill_src}" --containment-root "${repo_root}"
  for f in "${skill_files[@]}"; do
    if [[ ! -f "${skill_src}/${f}" ]]; then
      echo "error: required Skill file missing: skills/${skill_name}/${f}" >&2
      exit 1
    fi
  done
  for f in "${shared_policies[@]}"; do
    if [[ ! -f "${repo_root}/shared/policies/${f}" ]]; then
      echo "error: required shared policy missing: shared/policies/${f}" >&2
      exit 1
    fi
  done
  for f in "${shared_templates[@]}"; do
    if [[ ! -f "${repo_root}/shared/templates/${f}" ]]; then
      echo "error: required shared template missing: shared/templates/${f}" >&2
      exit 1
    fi
  done

  # Only ever clean our own controlled staging/output location, and only
  # ever write generated content under dist/.
  rm -rf "${stage_dir}"
  mkdir -p "${stage_dir}/shared/policies" "${stage_dir}/shared/templates"

  for f in "${shared_policies[@]}"; do
    cp "${repo_root}/shared/policies/${f}" "${stage_dir}/shared/policies/${f}"
  done
  for f in "${shared_templates[@]}"; do
    cp "${repo_root}/shared/templates/${f}" "${stage_dir}/shared/templates/${f}"
  done

  # Copy SKILL.md to the archive root, and every other Skill-specific
  # file to its package-root-relative location (dropping the
  # skills/<skill_name>/ source prefix).
  for f in "SKILL.md" "${skill_files[@]}"; do
    dest="${stage_dir}/${f}"
    mkdir -p "$(dirname "${dest}")"
    cp "${skill_src}/${f}" "${dest}"
  done

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
  if ! unzip -l "${archive_path}" | awk '{print $4}' | grep -qx "SKILL.md"; then
    echo "error: archive missing root SKILL.md: ${archive_path}" >&2
    exit 1
  fi
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
  package_skill "local-code-review" "local-code-review-skill" \
    "agents/openai.yaml" \
    "metadata/skill.yaml" \
    "policies/invocation-approval.md" \
    "runbooks/local-review.md" \
    "templates/local-review-report.md"
fi

if [[ "${target}" == "github" || "${target}" == "all" ]]; then
  for f in "${github_required_runtime_templates[@]}"; do
    require_source_file "github-pr-review" "${repo_root}/skills/github-pr-review" "${f}"
  done
  package_skill "github-pr-review" "github-pr-review-skill" \
    "agents/openai.yaml" \
    "metadata/skill.yaml" \
    "policies/github-review.md" \
    "policies/review-authority.md" \
    "policies/reviewer-delta-review.md" \
    "policies/pr-scope.md" \
    "policies/review-reasoning.md" \
    "policies/finding-placement.md" \
    "policies/review-output.md" \
    "runbooks/passive-pr-review.md" \
    "runbooks/active-pr-review.md" \
    "templates/inline-finding.md" \
    "templates/external-review-summary.md"
  for f in "${github_required_runtime_templates[@]}"; do
    require_archive_entry "${dist_dir}/github-pr-review-skill.zip" "${f}"
  done
fi

# Remove the now-empty staging root if packaging left nothing behind.
rmdir "${staging_root}" 2>/dev/null || true
