param(
  [Parameter(Mandatory = $true)]
  [string]$PackPath,

  [ValidateSet("Junction", "Copy")]
  [string]$Mode = "Junction",

  [string]$CodexHome = "",

  [switch]$DryRun,
  [switch]$Force,
  [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"

function Resolve-UnderRoot {
  param([string]$Path, [string]$Root)
  $resolvedPath = [System.IO.Path]::GetFullPath($Path)
  $resolvedRoot = [System.IO.Path]::GetFullPath($Root)
  if (-not $resolvedRoot.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
    $resolvedRoot = $resolvedRoot + [System.IO.Path]::DirectorySeparatorChar
  }
  if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to operate outside root. Path=$resolvedPath Root=$resolvedRoot"
  }
  return $resolvedPath
}

$adapterRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pack = Resolve-Path -LiteralPath $PackPath
$pack = $pack.Path

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
  if ($env:CODEX_HOME) {
    $CodexHome = $env:CODEX_HOME
  } else {
    $CodexHome = Join-Path $HOME ".codex"
  }
}

$skillRoot = Join-Path $CodexHome "skills"
$stateRoot = Join-Path $CodexHome "agent-launch-framework"
$manifestPath = Join-Path $stateRoot "installed-packs.json"

if (-not $SkipValidation) {
  $validator = Join-Path $adapterRoot "validate_agent_pack.py"
  Write-Host "Validating pack: $pack"
  python $validator $pack
}

$skillsDir = Join-Path $pack "skills"
if (-not (Test-Path -LiteralPath $skillsDir)) {
  throw "Pack has no skills directory: $skillsDir"
}

$skills = Get-ChildItem -LiteralPath $skillsDir -Directory
if ($skills.Count -eq 0) {
  throw "Pack has no skill folders: $skillsDir"
}

if ($DryRun) {
  Write-Host "DRY RUN: no filesystem changes will be made."
} else {
  New-Item -ItemType Directory -Force -Path $skillRoot | Out-Null
  New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
}

$installRecords = @()

foreach ($skill in $skills) {
  $skillFile = Join-Path $skill.FullName "SKILL.md"
  if (-not (Test-Path -LiteralPath $skillFile)) {
    throw "Missing SKILL.md for skill: $($skill.Name)"
  }

  $target = Join-Path $skillRoot $skill.Name
  $safeTarget = Resolve-UnderRoot -Path $target -Root $skillRoot
  Write-Host "Skill: $($skill.Name)"
  Write-Host "  Source: $($skill.FullName)"
  Write-Host "  Target: $safeTarget"

  if (Test-Path -LiteralPath $safeTarget) {
    if (-not $Force) {
      throw "Target already exists. Use -Force only after verifying it is safe: $safeTarget"
    }
    if ($DryRun) {
      Write-Host "  DRY RUN: would remove existing target because -Force was provided."
    } else {
      Resolve-UnderRoot -Path $safeTarget -Root $skillRoot | Out-Null
      Remove-Item -LiteralPath $safeTarget -Recurse -Force
    }
  }

  if ($DryRun) {
    Write-Host "  DRY RUN: would install with mode $Mode."
  } elseif ($Mode -eq "Copy") {
    Copy-Item -LiteralPath $skill.FullName -Destination $safeTarget -Recurse
  } else {
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
      New-Item -ItemType Junction -Path $safeTarget -Target $skill.FullName | Out-Null
    } else {
      New-Item -ItemType SymbolicLink -Path $safeTarget -Target $skill.FullName | Out-Null
    }
  }

  $installRecords += [ordered]@{
    pack = (Split-Path -Leaf $pack)
    skill = $skill.Name
    source = $skill.FullName
    target = $safeTarget
    mode = $Mode
  }
}

if (-not $DryRun) {
  $existing = @()
  if (Test-Path -LiteralPath $manifestPath) {
    $existing = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($null -eq $existing) { $existing = @() }
    if ($existing -isnot [System.Array]) { $existing = @($existing) }
  }
  $combined = @($existing) + @($installRecords)
  $combined | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
  Write-Host "Manifest updated: $manifestPath"
}

Write-Host "RESULT: install preflight completed for $($skills.Count) skill(s)."
