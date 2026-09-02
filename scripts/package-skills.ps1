#!/usr/bin/env pwsh
<#
  Package one or both Code Review Agent Skills into self-contained,
  standalone distributable archives, using explicit allowlists (never the
  whole repository). Each archive has its own SKILL.md at the archive
  ROOT (not nested under skills/<name>/), so a consumer never needs to
  know this repository's source layout. All generated output (staging
  and final zips) stays strictly under dist/. Cross-platform equivalent
  of scripts/package-skills.sh.

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
$stagingRoot = Join-Path $distDir ".staging"
$metadataValidator = Join-Path $scriptDir "validate-skill-metadata.py"
$pythonCommand = if (Get-Command "python" -ErrorAction SilentlyContinue) {
  "python"
} elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
  "python3"
} else {
  Write-Error "Python 3 is required but neither 'python' nor 'python3' is available"
  exit 1
}

# Shared files, by package-relative destination path — kept in sync with
# scripts/package-skills.sh.
$sharedPolicies = @(
  "review-scope.md",
  "severity.md",
  "evidence.md",
  "repository-instructions.md",
  "runtime-validation.md",
  "git-safety.md",
  "review-ownership.md",
  "file-reviewability.md",
  "review-context.md",
  "review-evidence.md",
  "parallel-review.md",
  "invocation-options.md",
  "remediation-guidance.md"
)
$sharedTemplates = @(
  "finding.md",
  "review-summary.md"
)

# Runtime assets that must be present in the packaged github-pr-review
# archive, verified independently of the general -SkillFiles allowlist
# passed to Package-Skill below — so a future edit that drops an entry
# from that allowlist still fails packaging instead of silently shipping
# an incomplete archive. external-review-summary.md is a required
# runtime dependency (referenced by SKILL.md and both runbooks), not
# repository-only documentation. Kept in sync with the equivalent guard
# in scripts/package-skills.sh.
$githubRequiredRuntimeTemplates = @(
  "templates/external-review-summary.md"
)

function Require-SourceFile {
  param(
    [string]$SkillName,
    [string]$SkillSrc,
    [string]$RelPath
  )
  $path = Join-Path $SkillSrc $RelPath
  if (-not (Test-Path $path -PathType Leaf)) {
    Write-Error "required runtime template missing for $SkillName`: skills/$SkillName/$RelPath"
    exit 1
  }
}

function Require-ArchiveEntry {
  param(
    [string]$ArchivePath,
    [string]$RelPath
  )
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [System.IO.Compression.ZipFile]::OpenRead($ArchivePath)
  try {
    $entryNames = $zip.Entries | ForEach-Object { $_.FullName }
  } finally {
    $zip.Dispose()
  }
  if (-not ($entryNames -contains $RelPath)) {
    Write-Error "archive missing required runtime asset: $ArchivePath ($RelPath)"
    exit 1
  }
}

# Rewrite relative links into shared/ so they resolve from the archive
# root instead of from skills/<name>/. Packaging strips exactly the two
# path segments ("skills/<name>/"), so every "../../shared/" (used by
# SKILL.md, at source depth 2) becomes "shared/", and every
# "../../../shared/" (used by files one level under the Skill, at source
# depth 3: runbooks/, templates/, policies/) becomes "../shared/". This
# is a narrow, deterministic substitution scoped to the exact link
# prefixes that point into shared/ — it never touches any other text.
# Guard against a regression stripping/corrupting the Agent Skills YAML
# frontmatter of a packaged root SKILL.md. Narrow structural check (line
# 1 is the opening delimiter, a closing delimiter exists, required
# name/description fields are present with the expected name) — not a
# full YAML validator; kept in sync with the equivalent guard in
# scripts/package-skills.sh.
function Test-SkillFrontmatter {
  param(
    [string]$SkillMdPath,
    [string]$ExpectedName
  )

  $lines = Get-Content -Path $SkillMdPath
  if ($lines.Count -eq 0 -or $lines[0] -ne "---") {
    Write-Error "$SkillMdPath does not start with '---' frontmatter delimiter on line 1"
    exit 1
  }

  $closingIndex = -1
  for ($i = 1; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -eq "---") {
      $closingIndex = $i
      break
    }
  }
  if ($closingIndex -eq -1) {
    Write-Error "$SkillMdPath frontmatter has no closing '---' delimiter"
    exit 1
  }

  $fmBody = $lines[1..($closingIndex - 1)] -join "`n"
  if ($fmBody -notmatch "(?m)^name:\s*$([regex]::Escape($ExpectedName))\s*$") {
    Write-Error "$SkillMdPath frontmatter missing 'name: $ExpectedName'"
    exit 1
  }
  if ($fmBody -notmatch "(?m)^description:") {
    Write-Error "$SkillMdPath frontmatter missing required 'description'"
    exit 1
  }
}

function Adapt-SharedLinks {
  param([string]$FilePath)
  $content = Get-Content -Path $FilePath -Raw
  $content = $content -replace [regex]::Escape("../../../shared/"), "../shared/"
  $content = $content -replace [regex]::Escape("../../shared/"), "shared/"
  Set-Content -Path $FilePath -Value $content -NoNewline
}

# Keep source metadata repository-relative, but adapt the exact known shared
# resource prefix in the staged standalone package copy.
function Adapt-MetadataPaths {
  param([string]$MetadataPath)
  $content = Get-Content -Path $MetadataPath -Raw
  $content = $content -replace '(?m)^(\s*-\s*)\.\./\.\./\.\./shared/', '$1../shared/'
  Set-Content -Path $MetadataPath -Value $content -NoNewline
}

function Package-Skill {
  param(
    [string]$SkillName,      # e.g. local-code-review
    [string]$ArchiveStem,    # e.g. local-code-review-skill
    [string[]]$SkillFiles    # paths relative to skills/<SkillName>/
  )

  $skillSrc = Join-Path $repoRoot "skills/$SkillName"
  $stageDir = Join-Path $stagingRoot $ArchiveStem
  $archivePath = Join-Path $distDir "$ArchiveStem.zip"

  if (-not (Test-Path $skillSrc -PathType Container)) {
    Write-Error "required Skill directory missing: skills/$SkillName"
    exit 1
  }
  if (-not (Test-Path (Join-Path $skillSrc "SKILL.md") -PathType Leaf)) {
    Write-Error "required Skill entry point missing: skills/$SkillName/SKILL.md"
    exit 1
  }
  if (-not (Test-Path (Join-Path $repoRoot "LICENSE") -PathType Leaf)) {
    Write-Error "required repository license missing: LICENSE"
    exit 1
  }
  & $pythonCommand $metadataValidator $skillSrc --containment-root $repoRoot
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
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

  # Only ever clean our own controlled staging/output location, and only
  # ever write generated content under dist/.
  if (Test-Path $stageDir) {
    Remove-Item -Recurse -Force $stageDir
  }
  New-Item -ItemType Directory -Path (Join-Path $stageDir "shared/policies") -Force | Out-Null
  New-Item -ItemType Directory -Path (Join-Path $stageDir "shared/templates") -Force | Out-Null

  foreach ($f in $sharedPolicies) {
    Copy-Item -Path (Join-Path $repoRoot "shared/policies/$f") -Destination (Join-Path $stageDir "shared/policies/$f")
  }
  foreach ($f in $sharedTemplates) {
    Copy-Item -Path (Join-Path $repoRoot "shared/templates/$f") -Destination (Join-Path $stageDir "shared/templates/$f")
  }

  # Copy SKILL.md to the archive root, and every other Skill-specific
  # file to its package-root-relative location (dropping the
  # skills/<SkillName>/ source prefix).
  $allFiles = @("SKILL.md") + $SkillFiles
  foreach ($f in $allFiles) {
    $destPath = Join-Path $stageDir $f
    New-Item -ItemType Directory -Path (Split-Path -Parent $destPath) -Force | Out-Null
    Copy-Item -Path (Join-Path $skillSrc $f) -Destination $destPath
  }
  Copy-Item -Path (Join-Path $repoRoot "LICENSE") -Destination (Join-Path $stageDir "LICENSE")

  # Adapt relative links into shared/ across every packaged Markdown
  # file (skill-local links like ../SKILL.md or runbooks/... need no
  # change, since skill-internal relative depth is unchanged).
  Get-ChildItem -Path $stageDir -Filter "*.md" -Recurse | ForEach-Object {
    Adapt-SharedLinks -FilePath $_.FullName
  }
  Adapt-MetadataPaths -MetadataPath (Join-Path $stageDir "metadata/skill.yaml")

  # --- Validate staged package structure before archiving ---
  if (-not (Test-Path (Join-Path $stageDir "SKILL.md") -PathType Leaf)) {
    Write-Error "staged package missing root SKILL.md: $stageDir/SKILL.md"
    exit 1
  }
  if (Test-Path (Join-Path $stageDir "skills")) {
    Write-Error "staged package must not contain a nested skills/ directory: $stageDir/skills"
    exit 1
  }
  $rootSkillMdContent = Get-Content -Path (Join-Path $stageDir "SKILL.md") -Raw
  if ($rootSkillMdContent -notmatch [regex]::Escape($SkillName)) {
    Write-Error "staged root SKILL.md does not identify as '$SkillName'"
    exit 1
  }
  Test-SkillFrontmatter -SkillMdPath (Join-Path $stageDir "SKILL.md") -ExpectedName $SkillName
  & $pythonCommand $metadataValidator $stageDir --containment-root $stageDir
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  if (Test-Path $archivePath) {
    Remove-Item -Force $archivePath
  }
  # Compress the staged package's *contents* (not the staging folder
  # itself) so SKILL.md lands at the archive root.
  Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $archivePath -Force

  # --- Verify archive contents ---
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [System.IO.Compression.ZipFile]::OpenRead($archivePath)
  try {
    $entryNames = $zip.Entries | ForEach-Object { $_.FullName }
  } finally {
    $zip.Dispose()
  }
  if (-not ($entryNames -contains "SKILL.md")) {
    Write-Error "archive missing root SKILL.md: $archivePath"
    exit 1
  }
  if (-not ($entryNames -contains "LICENSE")) {
    Write-Error "archive missing root LICENSE: $archivePath"
    exit 1
  }
  if ($entryNames | Where-Object { $_ -like "skills/*" }) {
    Write-Error "archive must not contain a nested skills/ directory: $archivePath"
    exit 1
  }

  Remove-Item -Recurse -Force $stageDir

  Write-Host "Archive created at: $archivePath"
}

Write-Host "Repository root: $repoRoot"
New-Item -ItemType Directory -Path $distDir -Force | Out-Null

if ($Skill -eq "local" -or $Skill -eq "all") {
  Package-Skill -SkillName "local-code-review" -ArchiveStem "local-code-review-skill" -SkillFiles @(
    "agents/openai.yaml",
    "metadata/skill.yaml",
    "policies/invocation-approval.md",
    "policies/repository-state.md",
    "policies/review-context.md",
    "policies/pr-context.md",
    "runbooks/local-review.md",
    "templates/local-review-report.md"
  )
}

if ($Skill -eq "github" -or $Skill -eq "all") {
  $githubSkillSrc = Join-Path $repoRoot "skills/github-pr-review"
  foreach ($f in $githubRequiredRuntimeTemplates) {
    Require-SourceFile -SkillName "github-pr-review" -SkillSrc $githubSkillSrc -RelPath $f
  }
  Package-Skill -SkillName "github-pr-review" -ArchiveStem "github-pr-review-skill" -SkillFiles @(
    "agents/openai.yaml",
    "metadata/skill.yaml",
    "policies/github-review.md",
    "policies/review-authority.md",
    "policies/review-action-authorization.md",
    "policies/reviewer-delta-review.md",
    "policies/pr-scope.md",
    "policies/repository-checkout.md",
    "policies/review-context.md",
    "policies/review-evidence.md",
    "policies/review-reasoning.md",
    "policies/parallel-review.md",
    "policies/finding-placement.md",
    "policies/review-output.md",
    "policies/review-status-enforcement.md",
    "runbooks/passive-pr-review.md",
    "runbooks/active-pr-review.md",
    "templates/inline-finding.md",
    "templates/external-review-summary.md"
  )
  $githubArchivePath = Join-Path $distDir "github-pr-review-skill.zip"
  foreach ($f in $githubRequiredRuntimeTemplates) {
    Require-ArchiveEntry -ArchivePath $githubArchivePath -RelPath $f
  }
}

# Remove the now-empty staging root if packaging left nothing behind.
if ((Test-Path $stagingRoot) -and ((Get-ChildItem -Path $stagingRoot -Force | Measure-Object).Count -eq 0)) {
  Remove-Item -Force $stagingRoot
}
