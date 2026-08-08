#!/usr/bin/env bash
# Package one or both Code Review Agent Skills into self-contained
# distributable archives, using explicit allowlists (never the whole
# repository). Each archive mirrors the repository's shared/ + skills/
# layout for exactly the files that Skill depends on, so its internal
# relative links resolve without requiring the rest of the repository.
#
# Usage:
#   scripts/package-skills.sh [local|github|all]
# Defaults to "all" when no argument is given.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
dist_dir="${repo_root}/dist"

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
)
shared_templates=(
  "finding.md"
)

package_skill() {
  local skill_name="$1"       # e.g. local-code-review
  local archive_stem="$2"     # e.g. local-code-review-skill
  shift 2
  local skill_files=("$@")    # paths relative to skills/<skill_name>/

  local skill_src="${repo_root}/skills/${skill_name}"
  local stage_dir="${dist_dir}/${archive_stem}"
  local archive_path="${dist_dir}/${archive_stem}.zip"

  if [[ ! -d "${skill_src}" ]]; then
    echo "error: required Skill directory missing: skills/${skill_name}" >&2
    exit 1
  fi
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

  # Only ever clean our own controlled staging/output location.
  rm -rf "${stage_dir}"
  mkdir -p "${stage_dir}/shared/policies" "${stage_dir}/shared/templates"
  mkdir -p "${stage_dir}/skills/${skill_name}"

  for f in "${shared_policies[@]}"; do
    cp "${repo_root}/shared/policies/${f}" "${stage_dir}/shared/policies/${f}"
  done
  for f in "${shared_templates[@]}"; do
    cp "${repo_root}/shared/templates/${f}" "${stage_dir}/shared/templates/${f}"
  done

  for f in "${skill_files[@]}"; do
    mkdir -p "${stage_dir}/skills/${skill_name}/$(dirname "${f}")"
    cp "${skill_src}/${f}" "${stage_dir}/skills/${skill_name}/${f}"
  done

  rm -f "${archive_path}"
  (
    cd "${dist_dir}"
    zip -r -q "$(basename "${archive_path}")" "${archive_stem}"
  )

  echo "Package staged at: ${stage_dir}"
  echo "Archive created at: ${archive_path}"
}

echo "Repository root: ${repo_root}"
mkdir -p "${dist_dir}"

if [[ "${target}" == "local" || "${target}" == "all" ]]; then
  package_skill "local-code-review" "local-code-review-skill" \
    "SKILL.md" \
    "metadata/skill.yaml" \
    "runbooks/local-review.md" \
    "templates/local-review-report.md"
fi

if [[ "${target}" == "github" || "${target}" == "all" ]]; then
  package_skill "github-pr-review" "github-pr-review-skill" \
    "SKILL.md" \
    "metadata/skill.yaml" \
    "policies/github-review.md" \
    "runbooks/passive-pr-review.md" \
    "runbooks/active-pr-review.md" \
    "templates/inline-finding.md" \
    "templates/external-review-summary.md"
fi
