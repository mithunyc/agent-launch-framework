param(
  [Parameter(Mandatory = $true)]
  [string]$PackId,

  [string]$CodexHome = "",

  [switch]$DryRun
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

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
  if ($env:CODEX_HOME) {
    $CodexHome = $env:CODEX_HOME
  } else {
    $CodexHome = Join-Path $HOME ".codex"
  }
}

$skillRoot = Join-Path $CodexHome "skills"
$manifestPath = Join-Path $CodexHome "agent-launch-framework\installed-packs.json"

if (-not (Test-Path -LiteralPath $manifestPath)) {
  Write-Host "No install manifest found: $manifestPath"
  exit 0
}

$records = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($null -eq $records) { $records = @() }
if ($records -isnot [System.Array]) { $records = @($records) }

$remove = @($records | Where-Object { $_.pack -eq $PackId })
$keep = @($records | Where-Object { $_.pack -ne $PackId })

if ($remove.Count -eq 0) {
  Write-Host "No installed records found for pack: $PackId"
  exit 0
}

foreach ($record in $remove) {
  $target = Resolve-UnderRoot -Path $record.target -Root $skillRoot
  Write-Host "Remove skill target: $target"
  if ($DryRun) {
    Write-Host "  DRY RUN: would remove target."
    continue
  }
  if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
  }
}

if (-not $DryRun) {
  $keep | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8
  Write-Host "Manifest updated: $manifestPath"
}

Write-Host "RESULT: uninstall completed for pack $PackId."
