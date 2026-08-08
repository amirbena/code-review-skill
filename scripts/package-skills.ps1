#!/usr/bin/env pwsh
<#
  Package one or both Code Review Agent Skills into self-contained
  distributable archives, using explicit allowlists (never the whole
  repository). Cross-platform equivalent of scripts/package-skills.sh.

  Usage:
    ./scripts/package-skills.ps1 local
    ./scripts/package-skills.ps1 github
    ./scripts/package-skills.ps1 all      # default
#>

param(
  [ValidateSet("local", "github", "all")]
  [string]$Skill = "all"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$distDir = Join-Path $repoRoot "dist"

# Shared files, by package-relative destination path — kept in sync with
# scripts/package-skills.sh.
$sharedPolicies = @(
  "review-scope.md",
  "severity.md",
  "evidence.md",
  "repository-instructions.md",
  "git-safety.md",
  "review-ownership.md"
)
$sharedTemplates = @(
  "finding.md"
)

function Package-Skill {
  param(
    [string]$SkillName,      # e.g. local-code-review
    [string]$ArchiveStem,    # e.g. local-code-review-skill
    [string[]]$SkillFiles    # paths relative to skills/<SkillName>/
  )

  $skillSrc = Join-Path $repoRoot "skills/$SkillName"
  $stageDir = Join-Path $distDir $ArchiveStem
  $archivePath = Join-Path $distDir "$ArchiveStem.zip"

  if (-not (Test-Path $skillSrc -PathType Container)) {
    Write-Error "required Skill directory missing: skills/$SkillName"
    exit 1
  }
  foreach ($f in $SkillFiles) {
    $path = Join-Path $skillSrc $f
    if (-not (Test-Path $path -PathType Leaf)) {
      Write-Error "required Skill file missing: skills/$SkillName/$f"
      exit 1
    }
  }
  foreach ($f in $sharedPolicies) {
    $path = Join-Path $repoRoot "shared/policies/$f"
    if (-not (Test-Path $path -PathType Leaf)) {
      Write-Error "required shared policy missing: shared/policies/$f"
      exit 1
    }
  }
  foreach ($f in $sharedTemplates) {
    $path = Join-Path $repoRoot "shared/templates/$f"
    if (-not (Test-Path $path -PathType Leaf)) {
      Write-Error "required shared template missing: shared/templates/$f"
      exit 1
    }
  }

  # Only ever clean our own controlled staging/output location.
  if (Test-Path $stageDir) {
    Remove-Item -Recurse -Force $stageDir
  }
  New-Item -ItemType Directory -Path (Join-Path $stageDir "shared/policies") -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $stageDir "shared/templates") -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $stageDir "skills/$SkillName") -Force | Out-Null

  foreach ($f in $sharedPolicies) {
    Copy-Item -Path (Join-Path $repoRoot "shared/policies/$f") -Destination (Join-Path $stageDir "shared/policies/$f")
  }
  foreach ($f in $sharedTemplates) {
    Copy-Item -Path (Join-Path $repoRoot "shared/templates/$f") -Destination (Join-Path $stageDir "shared/templates/$f")
  }

  foreach ($f in $SkillFiles) {
    $destPath = Join-Path $stageDir "skills/$SkillName/$f"
    New-Item -ItemType Directory -Path (Split-Path -Parent $destPath) -Force | Out-Null
    Copy-Item -Path (Join-Path $skillSrc $f) -Destination $destPath
  }

  if (Test-Path $archivePath) {
    Remove-Item -Force $archivePath
  }
  Compress-Archive -Path $stageDir -DestinationPath $archivePath -Force

  Write-Host "Package staged at: $stageDir"
  Write-Host "Archive created at: $archivePath"
}

Write-Host "Repository root: $repoRoot"
New-Item -ItemType Directory -Path $distDir -Force | Out-Null

if ($Skill -eq "local" -or $Skill -eq "all") {
  Package-Skill -SkillName "local-code-review" -ArchiveStem "local-code-review-skill" -SkillFiles @(
    "SKILL.md",
    "metadata/skill.yaml",
    "runbooks/local-review.md",
    "templates/local-review-report.md"
  )
}

if ($Skill -eq "github" -or $Skill -eq "all") {
  Package-Skill -SkillName "github-pr-review" -ArchiveStem "github-pr-review-skill" -SkillFiles @(
    "SKILL.md",
    "metadata/skill.yaml",
    "policies/github-review.md",
    "runbooks/passive-pr-review.md",
    "runbooks/active-pr-review.md",
    "templates/inline-finding.md",
    "templates/external-review-summary.md"
  )
}
