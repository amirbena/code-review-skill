#!/usr/bin/env pwsh
<#
  Package the portable Code Review Agent Skill into a distributable
  archive, using an explicit allowlist (never the whole repository).
  Cross-platform equivalent of scripts/package-skill.sh.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

$packageName = "github-code-review-skill"
$distDir = Join-Path $repoRoot "dist"
$stageDir = Join-Path $distDir $packageName
$archivePath = Join-Path $distDir "$packageName.zip"

# Explicit allowlist of package contents — kept in sync with
# scripts/package-skill.sh. Pack by allowlist, never by copy-then-delete.
$files = @(
  "SKILL.md",
  "review-config.yaml"
)
$dirs = @(
  "metadata",
  "policies",
  "runbooks",
  "templates"
)

Write-Host "Repository root: $repoRoot"

foreach ($f in $files) {
  $path = Join-Path $repoRoot $f
  if (-not (Test-Path $path -PathType Leaf)) {
    Write-Error "required Skill file missing: $f"
    exit 1
  }
}

foreach ($d in $dirs) {
  $path = Join-Path $repoRoot $d
  if (-not (Test-Path $path -PathType Container)) {
    Write-Error "required Skill directory missing: $d"
    exit 1
  }
}

# Only ever clean our own controlled staging/output location, never
# anything outside dist/.
if (Test-Path $stageDir) {
  Remove-Item -Recurse -Force $stageDir
}
New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

foreach ($f in $files) {
  Copy-Item -Path (Join-Path $repoRoot $f) -Destination (Join-Path $stageDir $f)
}

foreach ($d in $dirs) {
  $destDir = Join-Path $stageDir $d
  New-Item -ItemType Directory -Path $destDir -Force | Out-Null
  Copy-Item -Path (Join-Path $repoRoot $d "*") -Destination $destDir -Recurse -Force
}

if (Test-Path $archivePath) {
  Remove-Item -Force $archivePath
}

Compress-Archive -Path $stageDir -DestinationPath $archivePath -Force

Write-Host "Package staged at: $stageDir"
Write-Host "Archive created at: $archivePath"
