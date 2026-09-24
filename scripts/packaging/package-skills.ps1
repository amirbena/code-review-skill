#!/usr/bin/env pwsh
<#
  Package one or both Code Review Agent Skills into self-contained,
  standalone distributable archives, using explicit allowlists (never the
  whole repository). Each archive has its own SKILL.md at the archive
  ROOT (not nested under skills/<name>/), so a consumer never needs to
  know this repository's source layout. All generated output stays
  strictly under dist/: the canonical, deterministic, validated
  self-contained Skill trees at dist/skills/<name>/ (with a content
  manifest at dist/skills-manifest.json), and the release zips built from
  exactly those trees. dist/ is gitignored and is never published from
  this repository. Cross-platform equivalent of
  scripts/packaging/package-skills.sh.

  Usage:
    ./scripts/packaging/package-skills.ps1 local
    ./scripts/packaging/package-skills.ps1 github
    ./scripts/packaging/package-skills.ps1 all      # default
#>

param(
  [ValidateSet("local", "github", "all")]
  [string]$Skill = "all"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "../..")
$distDir = Join-Path $repoRoot "dist"
$treesRoot = Join-Path $distDir "skills"
$metadataValidator = Join-Path $repoRoot "scripts/validation/validate-skill-metadata.py"
$packageManifestPath = Join-Path $scriptDir "package-manifest.json"
$packageManifestHelper = Join-Path $scriptDir "package_manifest.py"
$packageAdapt = Join-Path $scriptDir "package_adapt.py"
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

# Shared-link adaptation, metadata-path adaptation, release-version
# stamping, and SKILL.md frontmatter structural validation are packaging-domain rules shared
# with scripts/packaging/package-skills.sh; both platform scripts delegate to the
# single canonical Python implementation in scripts/packaging/package_domain/ (see
# scripts/packaging/package_adapt.py) instead of restating the rules here.
function Test-SkillFrontmatter {
  param(
    [string]$SkillMdPath,
    [string]$ExpectedName
  )
  & $pythonCommand $packageAdapt validate-frontmatter $SkillMdPath $ExpectedName
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Adapt-SharedLinks {
  param([string]$FilePath)
  & $pythonCommand $packageAdapt adapt-shared-links $FilePath
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Adapt-MetadataPaths {
  param([string]$MetadataPath)
  & $pythonCommand $packageAdapt adapt-metadata-paths $MetadataPath
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# Stamps the staged SKILL.md with the release authority's version (the newest
# `## vX.Y.Z` heading in CHANGELOG.md); fails closed when there is none.
function Set-ReleaseVersion {
  param([string]$SkillMdPath)
  & $pythonCommand $packageAdapt stamp-release-version $SkillMdPath (Join-Path $repoRoot "CHANGELOG.md")
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
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
  $stageDir = Join-Path $treesRoot $skillName
  $archivePath = Join-Path $distDir $archiveName

  if (-not (Test-Path $skillSrc -PathType Container)) {
    Write-Error "required Skill directory missing: skills/$SkillName"
    exit 1
  }
  & $pythonCommand $metadataValidator $skillSrc --containment-root $repoRoot
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  # Only ever clean our own controlled tree/output location, and only
  # ever write generated content under dist/.
  if (Test-Path $stageDir) {
    Remove-Item -Recurse -Force $stageDir
  }
  New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

  $entries = @($packageManifest.shared_files) + @($skill.files)
  foreach ($entry in $entries) {
    $sourcePath = Join-Path $repoRoot $entry.source
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
      Write-Error "required package source missing: $($entry.source)"
      exit 1
    }
    $destPath = Join-Path $stageDir $entry.destination
    New-Item -ItemType Directory -Path (Split-Path -Parent $destPath) -Force | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $destPath
  }

  # Normalize line endings/BOM first, so a CRLF checkout (e.g. Windows
  # autocrlf) validates and stamps identically to an LF one.
  & $pythonCommand $packageAdapt normalize-tree $stageDir
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  # Adapt relative links into shared/ across every packaged Markdown
  # file (skill-local links like ../SKILL.md or runbooks/... need no
  # change, since skill-internal relative depth is unchanged).
  Get-ChildItem -Path $stageDir -Filter "*.md" -Recurse | ForEach-Object {
    Adapt-SharedLinks -FilePath $_.FullName
  }
  Adapt-MetadataPaths -MetadataPath (Join-Path $stageDir "metadata/skill.yaml")
  Set-ReleaseVersion -SkillMdPath (Join-Path $stageDir "SKILL.md")

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

  # Make the tree deterministic and distribution-conformant (LF, no BOM,
  # normalized modes, built-tree-only metadata.version), then validate it
  # against the Agent Skills spec and for self-containment. The zip is
  # built from, and verified against, this exact tree (the same Python
  # implementation as package-skills.sh, so both produce identical bytes).
  & $pythonCommand $packageAdapt finalize-tree $stageDir $SkillName
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  & $pythonCommand $packageAdapt build-archive $stageDir $archivePath
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  & $pythonCommand $packageAdapt verify-archive $stageDir $archivePath
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

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

  $script:builtSkills += $SkillName
  Write-Host "Skill tree built at: $stageDir"
  Write-Host "Archive created at: $archivePath"
}

$script:builtSkills = @()
Write-Host "Repository root: $repoRoot"
New-Item -ItemType Directory -Path $distDir, $treesRoot -Force | Out-Null

if ($Skill -eq "local" -or $Skill -eq "all") {
  Package-Skill -PackageTarget "local"
}

if ($Skill -eq "github" -or $Skill -eq "all") {
  Package-Skill -PackageTarget "github"
}

& $pythonCommand $packageAdapt write-tree-manifest $distDir @($script:builtSkills)
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
