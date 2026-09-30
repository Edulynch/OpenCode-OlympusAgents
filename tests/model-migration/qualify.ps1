[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))

function Text([string]$path) {
    [IO.File]::ReadAllText((Join-Path $root $path))
}
function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}
function Model-Spec([string]$path) {
    $content = Text $path
    $modelLine = @($content -split "`r?`n" | Where-Object { $_ -match '^model:\s*' } | Select-Object -First 1)
    $modeLine = @($content -split "`r?`n" | Where-Object { $_ -match '^mode:\s*' } | Select-Object -First 1)
    if (-not $modelLine -or -not $modeLine) { return $null }
    $model = ($modelLine[0] -replace '^model:\s*', '').Trim().Trim('"').Trim("'")
    $mode = ($modeLine[0] -replace '^mode:\s*', '').Trim()
    $parts = $model -split '#', 2
    [pscustomobject]@{
        Id = ($parts[0] -split '/')[-1]
        Effort = if ($parts.Count -gt 1) { $parts[1] } else { '' }
        Mode = $mode
        Raw = $model
    }
}

$modelsText = Text 'olympus/core/models.toml'
$models = [ordered]@{}
foreach ($match in [regex]::Matches($modelsText, '(?ms)^\[roles\.(?<role>[a-z]+)\]\s*\r?\nfamily\s*=\s*"(?<family>[^"]+)"\s*\r?\neffort\s*=\s*"(?<effort>[^"]+)"')) {
    $familyBlock = [regex]::Match($modelsText, '(?ms)^\[families\.' + [regex]::Escape($match.Groups['family'].Value) + '\]\s*\r?\nopencode\s*=\s*"(?<model>[^"]+)"')
    if (-not $familyBlock.Success) { throw "MODEL_FAMILY_MISSING: $($match.Groups['family'].Value)" }
    $name = $match.Groups['role'].Value
    $modelId = ($familyBlock.Groups['model'].Value -split '/')[-1]
    $mode = if ($name -ceq 'kael') { 'primary' } else { 'subagent' }
    $models[$name] = @($modelId, $match.Groups['effort'].Value, $mode)
}
$expectedIds = @($models.Keys)
Check 'MODEL_SOURCE_CANONICAL_ROSTER' ($expectedIds.Count -eq 12 -and $modelsText -match '(?m)^\[families\.sol\]\r?$' -and $modelsText -match '(?m)^\[families\.luna\]\r?$')

$agentsRoot = Join-Path $root '.opencode/agents'
$agentFiles = @(Get-ChildItem -LiteralPath $agentsRoot -Filter '*.md' -File)
$actualIds = @($agentFiles | ForEach-Object BaseName)
Check 'ROSTER_12_ROLES' ($agentFiles.Count -eq 12 -and
    [string]::Join(',', @($actualIds | Sort-Object)) -ceq [string]::Join(',', @($expectedIds | Sort-Object)))

foreach ($name in $models.Keys) {
    $spec = Model-Spec ".opencode/agents/$name.md"
    $wanted = $models[$name]
    Check ("CORE_MODEL_$($name.ToUpperInvariant())") ($null -ne $spec -and
        $spec.Id -ceq $wanted[0] -and $spec.Effort -ceq $wanted[1] -and $spec.Mode -ceq $wanted[2])
}

$config = Text 'opencode.jsonc'
Check 'ROOT_DEFAULT_MODEL_FROM_CORE' ($config -match '(?m)^\s*"model"\s*:\s*"openai/gpt-6\.1-sol"\s*,?\s*$' -and
    $models['kael'][0] -ceq 'gpt-6.1-sol')

$installer = Text 'scripts/bootstrap.ps1'
Check 'INSTALLER_DERIVES_MODELS_FROM_GENERATED_ROLES' ($installer -match 'function Get-Expected-Agents' -and
    $installer -match 'Join-Path.*\.opencode/agents' -and $installer -match '\(\?m\)\^model:' -and
    $installer -notmatch '(?m)^\s*"(?:kael|thales|atlas|argus|talos|helios|veyra|orin|kovan|nox|vera|aegis)"=@\(')
Check 'INSTALLER_MODEL_DISCOVERY' ($installer -notmatch '(?m)^\s*"(?:kael|thales|atlas|argus|talos|helios|veyra|orin|kovan|nox|vera|aegis)"=@\(')

$fixture = Text 'tests/release/fixtures/opencode.ps1'
Check 'RELEASE_MODEL_FIXTURE_CURRENT_AND_STABLE' ($fixture -match "openai/gpt-6\.1-sol" -and
    $fixture -match "openai/gpt-6-sol" -and $fixture -match "openai/gpt-6-luna" -and
    $fixture -match 'stable v0\.2\.0 installer')

$currentSources = @('opencode.jsonc', 'CODEX.md', '.codex/config.toml') +
    @($agentFiles | ForEach-Object { $_.FullName }) +
    @(Get-ChildItem -LiteralPath (Join-Path $root '.codex/agents') -Filter '*.toml' -File | ForEach-Object { $_.FullName })
$legacyReferences = @($currentSources | Where-Object {
    $path = if ([IO.Path]::IsPathRooted($_)) { $_ } else { Join-Path $root $_ }
    [IO.File]::ReadAllText($path) -match 'gpt-6-sol'
})
Check 'NO_LEGACY_SOL_LIVE_ASSIGNMENTS_OR_TEST_ASSERTIONS' ($legacyReferences.Count -eq 0)

Write-Output 'MODEL_MIGRATION_QUALIFICATION: PASS'
