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
$packageManifestPath = Join-Path $scriptDir "package-manifest.json"
$packageManifestHelper = Join-Path $scriptDir "package_manifest.py"
$pythonCommand = if (Get-Command "python" -ErrorAction SilentlyContinue) {
  "python"
} elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
  "python3"
} else {
  Write-Error "Python 3 is required but neither 'python' nor 'python3' is available"
  exit 1
}

$packageManifest = Get-Content -Path $packageManifestPath -Raw | ConvertFrom-Json
if ($packageManifest.schema_version -ne 1) {
  Write-Error "unsupported package manifest schema_version"
  exit 1
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
    [string]$PackageTarget
  )

  & $pythonCommand $packageManifestHelper $packageManifestPath $PackageTarget validate
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  $skill = $packageManifest.skills.$PackageTarget
  if ($null -eq $skill) {
    Write-Error "package manifest has no target '$PackageTarget'"
    exit 1
  }
  $skillName = $skill.name
  $archiveName = $skill.archive
  $skillSrc = Join-Path $repoRoot "skills/$SkillName"
  $stageDir = Join-Path $stagingRoot ([System.IO.Path]::GetFileNameWithoutExtension($archiveName))
  $archivePath = Join-Path $distDir $archiveName

  if (-not (Test-Path $skillSrc -PathType Container)) {
    Write-Error "required Skill directory missing: skills/$SkillName"
    exit 1
  }
  & $pythonCommand $metadataValidator $skillSrc --containment-root $repoRoot
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  # Only ever clean our own controlled staging/output location, and only
  # ever write generated content under dist/.
  if (Test-Path $stageDir) {
    Remove-Item -Recurse -Force $stageDir
  }
  New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

  $entries = @($packageManifest.shared_files) + @($skill.files)
  foreach ($entry in $entries) {
    $sourcePath = Join-Path $repoRoot $entry.source
    if (-not (Test-Path $sourcePath -PathType Leaf)) {
      Write-Error "required package source missing: $($entry.source)"
      exit 1
    }
    $destPath = Join-Path $stageDir $entry.destination
    New-Item -ItemType Directory -Path (Split-Path -Parent $destPath) -Force | Out-Null
    Copy-Item -Path $sourcePath -Destination $destPath
  }

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
  foreach ($requiredEntry in $skill.required_entries) {
    if (-not ($entryNames -contains $requiredEntry)) {
      Write-Error "archive missing required runtime asset: $archivePath ($requiredEntry)"
      exit 1
    }
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
  Package-Skill -PackageTarget "local"
}

if ($Skill -eq "github" -or $Skill -eq "all") {
  Package-Skill -PackageTarget "github"
}

# Remove the now-empty staging root if packaging left nothing behind.
if ((Test-Path $stagingRoot) -and ((Get-ChildItem -Path $stagingRoot -Force | Measure-Object).Count -eq 0)) {
  Remove-Item -Force $stagingRoot
}
