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

$sol = [ordered]@{
    kael   = @('gpt-6.1-sol', 'high',  'primary')
    thales = @('gpt-6.1-sol', 'xhigh', 'subagent')
    atlas  = @('gpt-6.1-sol', 'high',  'subagent')
    argus  = @('gpt-6.1-sol', 'high',  'subagent')
    talos  = @('gpt-6.1-sol', 'high',  'subagent')
    helios = @('gpt-6.1-sol', 'high',  'subagent')
}
$luna = [ordered]@{
    veyra = @('gpt-6-luna', 'max', 'subagent')
    orin  = @('gpt-6-luna', 'max', 'subagent')
    kovan = @('gpt-6-luna', 'max', 'subagent')
    nox   = @('gpt-6-luna', 'max', 'subagent')
    vera  = @('gpt-6-luna', 'max', 'subagent')
    aegis = @('gpt-6-luna', 'max', 'subagent')
}

$agentsRoot = Join-Path $root '.opencode/agents'
$agentFiles = @(Get-ChildItem -LiteralPath $agentsRoot -Filter '*.md' -File)
$expectedIds = @($sol.Keys) + @($luna.Keys)
$actualIds = @($agentFiles | ForEach-Object BaseName)
Check 'ROSTER_12_ROLES' ($agentFiles.Count -eq 12 -and
    [string]::Join(',', @($actualIds | Sort-Object)) -ceq [string]::Join(',', @($expectedIds | Sort-Object)))

foreach ($set in @(@{ Name='SOL'; Roles=$sol }, @{ Name='LUNA'; Roles=$luna })) {
    foreach ($name in $set.Roles.Keys) {
        $spec = Model-Spec ".opencode/agents/$name.md"
        $wanted = $set.Roles[$name]
        Check ("$($set.Name)_$($name.ToUpperInvariant())") ($null -ne $spec -and
            $spec.Id -ceq $wanted[0] -and $spec.Effort -ceq $wanted[1] -and $spec.Mode -ceq $wanted[2])
    }
}

$config = Text 'opencode.jsonc'
Check 'ROOT_DEFAULT_GPT61_SOL' ($config -match '(?m)^\s*"model"\s*:\s*"openai/gpt-6\.1-sol"\s*,?\s*$')

$installer = Text 'scripts/bootstrap.ps1'
$installerMapValid = $true
foreach ($set in @($sol, $luna)) {
    foreach ($name in $set.Keys) {
        $wanted = $set[$name]
        $expectedEntry = '(?m)^\s*"' + [regex]::Escape($name) + '"=@\("' +
            [regex]::Escape($wanted[0]) + '","' + [regex]::Escape($wanted[1]) + '","' +
            [regex]::Escape($wanted[2]) + '"\)\s*$'
        if ($installer -notmatch $expectedEntry) { $installerMapValid = $false }
    }
}
Check 'INSTALLER_EFFECTIVE_ROLE_MAP' $installerMapValid
Check 'INSTALLER_MODEL_DISCOVERY' ($installer -match 'openai/gpt-6\.1-sol' -and
    $installer -match 'openai/gpt-6-luna' -and $installer -notmatch 'openai/gpt-6-sol')

$fixture = Text 'tests/release/fixtures/opencode.ps1'
Check 'RELEASE_MODEL_FIXTURE_CURRENT_AND_STABLE' ($fixture -match "openai/gpt-6\.1-sol" -and
    $fixture -match "openai/gpt-6-sol" -and $fixture -match "openai/gpt-6-luna" -and
    $fixture -match 'stable v0\.2\.0 installer')

$trackedTests = @(& git -C $root ls-files -- 'tests')
if ($LASTEXITCODE -ne 0) { throw 'GIT_TEST_INVENTORY_FAILED' }
$currentSources = @('opencode.jsonc', 'scripts/bootstrap.ps1') +
    @($agentFiles | ForEach-Object { $_.FullName }) +
    @($trackedTests | Where-Object {
        [IO.Path]::GetExtension($_) -in @('.ps1', '.md') -and
        $_ -cnotin @('tests/model-migration/qualify.ps1', 'tests/release/fixtures/opencode.ps1')
    })
$legacyReferences = @($currentSources | Where-Object {
    $path = if ([IO.Path]::IsPathRooted($_)) { $_ } else { Join-Path $root $_ }
    [IO.File]::ReadAllText($path) -match 'gpt-6-sol'
})
Check 'NO_LEGACY_SOL_LIVE_ASSIGNMENTS_OR_TEST_ASSERTIONS' ($legacyReferences.Count -eq 0)

Write-Output 'MODEL_MIGRATION_QUALIFICATION: PASS'
