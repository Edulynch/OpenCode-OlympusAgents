[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$run = Join-Path ([IO.Path]::GetTempPath()) ('opencode/olympus-installer-ux-' + [guid]::NewGuid().ToString('N'))
. (Join-Path $PSScriptRoot '../installer-test-environment.ps1')
$previousEnvironment = Enter-OlympusInstallerTestEnvironment $run
$originalPath = $env:PATH
$script:downloads = @()
$script:dispatches = @()
$script:metadataCalls = 0
$script:installerText = "[string]`$Version = 'v9.8.7'`n`$ReleaseVersion = 'v9.8.7'`n"
$script:legacyLauncher = $false

function Check([string]$Id, [bool]$Condition, [string]$Evidence = '') {
    if (-not $Condition) { throw "$Id FAIL`n$Evidence" }
    Write-Output "$Id PASS"
}

function New-Release {
    return @{ tag_name='v9.8.7'; immutable=$true; draft=$false; prerelease=$false; published_at='2026-10-01T12:00:00Z' }
}

function Invoke-RestMethod {
    [CmdletBinding()]
    param([string]$Uri, [hashtable]$Headers)
    $script:metadataCalls++
    if ($Uri -cne 'https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest') {
        throw "UNEXPECTED_METADATA_URL: $Uri"
    }
    return $script:release
}

function Invoke-WebRequest {
    [CmdletBinding()]
    param([string]$Uri, [string]$OutFile, [hashtable]$Headers)
    $script:downloads += $Uri
    if ($Uri -eq 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1') {
        Copy-Item (Join-Path $source 'install-olympus.ps1') $OutFile
    } elseif ($Uri -eq 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v9.8.7/scripts/launch-latest.ps1') {
        if ($script:legacyLauncher) { [IO.File]::WriteAllText($OutFile, '# obsolete launcher') }
        else { Copy-Item (Join-Path $source 'scripts/launch-latest.ps1') $OutFile }
    } elseif ($Uri -eq 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v9.8.7/install.ps1') {
        [IO.File]::WriteAllText($OutFile, $script:installerText)
    } else { throw "UNEXPECTED_DOWNLOAD: $Uri" }
}

function Read-Host { throw 'PUBLIC_INSTALL_MUST_NOT_PROMPT' }

# Native process dispatch is recorded, never executed by this UX fixture.
function Get-Command {
    param([string]$Name, $CommandType, $ErrorAction)
    if ($Name -in @('pwsh','olympus')) {
        return [pscustomobject]@{ Source=(Join-Path $run ($Name + '.cmd')) }
    }
    return Microsoft.PowerShell.Core\Get-Command @PSBoundParameters
}

function Invoke-Subject([string]$Relative, [hashtable]$Arguments = @{}) {
    $script:downloads = @()
    $script:metadataCalls = 0
    $before = if (Test-Path (Join-Path $run 'dispatch.txt')) { [IO.File]::ReadAllText((Join-Path $run 'dispatch.txt')) } else { '' }
    $global:LASTEXITCODE = 0
    try {
        $subject = [scriptblock]::Create([IO.File]::ReadAllText((Join-Path $source $Relative)))
        $text = (& $subject @Arguments 2>&1 | Out-String)
        $code = $LASTEXITCODE
    } catch {
        $text = $_.Exception.Message
        $code = 1
    }
    $after = if (Test-Path (Join-Path $run 'dispatch.txt')) { [IO.File]::ReadAllText((Join-Path $run 'dispatch.txt')) } else { '' }
    return [pscustomobject]@{ Code=$code; Text=$text; Dispatched=($after -cne $before); Dispatch=$after }
}

try {
    $env:OLYMPUS_UX_DISPATCH = Join-Path $run 'dispatch.txt'
    foreach ($name in @('pwsh','olympus')) {
        [IO.File]::WriteAllText((Join-Path $run "$name.cmd"),
            "@echo off`r`n>>`"%OLYMPUS_UX_DISPATCH%`" echo $name %*`r`nexit /b 0`r`n", [Text.Encoding]::ASCII)
    }
    $script:release = New-Release
    foreach ($action in @('install','uninstall')) {
        $entry = "$action-olympus.ps1"
        $result = Invoke-Subject $entry
        Check "PUBLIC_${action}_FIXED_GLOBAL_NO_PROMPT" (
            $result.Code -eq 0 -and $result.Dispatched -and
            $result.Dispatch.Contains("-Action $action") -and
            $result.Dispatch -notmatch '-Target|-Harness|-Scope' -and
            $script:metadataCalls -eq 1 -and $script:downloads.Count -eq 1
        ) $result.Text
        foreach ($selection in @(
            @{ Project=$true }, @{ Global=$true }, @{ Here=$true },
            @{ ProjectPath='C:\not-used' }, @{ Harness='codex' }, @{ Scope='project' },
            @{ Target='C:\not-used' }, @{ Version='v9.8.7' }
        )) {
            $rejected = Invoke-Subject $entry $selection
            Check "PUBLIC_${action}_REJECTS_$(@($selection.Keys)[0])_BEFORE_EFFECTS" (
                $rejected.Code -ne 0 -and -not $rejected.Dispatched -and
                $script:metadataCalls -eq 0 -and $script:downloads.Count -eq 0
            ) $rejected.Text
        }
    }

    foreach ($entry in @(
        @('install/global/opencode.ps1','install'),
        @('uninstall/global/opencode.ps1','uninstall')
    )) {
        $result = Invoke-Subject $entry[0]
        Check "CURRENT_GLOBAL_OPENCODE_ALIAS_$($entry[1].ToUpperInvariant())" (
            $result.Code -eq 0 -and $result.Dispatched -and
            $result.Dispatch.Contains($entry[1]) -and
            $result.Dispatch -notmatch '-Harness|-Scope|-Target'
        ) $result.Text
    }
    foreach ($selection in @(@{Scope='project'}, @{Harness='codex'}, @{Harness='all'}, @{Target='C:\not-used'})) {
        $parameters = @{ SourceRoot='C:\must-not-be-read' }
        foreach ($key in $selection.Keys) { $parameters[$key] = $selection[$key] }
        $result = Invoke-Subject 'install.ps1' $parameters
        Check "ROOT_INSTALLER_REJECTS_$(@($selection.Values)[0])_BEFORE_EFFECTS" (
            $result.Code -ne 0 -and -not $result.Dispatched -and
            $script:metadataCalls -eq 0 -and $script:downloads.Count -eq 0
        ) $result.Text
    }

    foreach ($action in @('install','uninstall')) {
        $result = Invoke-Subject 'scripts/launch-latest.ps1' @{ Action=$action }
        Check "LAUNCHER_${action}_TAG_IDENTITY_AND_FIXED_TARGET" (
            $result.Code -eq 0 -and $result.Dispatched -and
            $result.Dispatch.Contains('-Scope global -Harness opencode') -and
            $result.Dispatch.Contains('-Version v9.8.7') -and $result.Dispatch -notmatch '-Target' -and
            $result.Text.Contains('OLYMPUS_RELEASE_EXECUTED: tag=v9.8.7 exit_code=0')
        ) $result.Text
        foreach ($selection in @(@{Scope='project'}, @{Harness='codex'}, @{Target='C:\not-used'}, @{Version='v9.8.7'})) {
            $parameters = @{ Action=$action }
            foreach ($key in $selection.Keys) { $parameters[$key] = $selection[$key] }
            $result = Invoke-Subject 'scripts/launch-latest.ps1' $parameters
            Check "LAUNCHER_${action}_REJECTS_$(@($selection.Keys)[0])_BEFORE_EFFECTS" (
                $result.Code -ne 0 -and -not $result.Dispatched -and
                $script:downloads.Count -eq 0 -and $script:metadataCalls -eq 0
            ) $result.Text
        }
    }
    $dry = Invoke-Subject 'scripts/launch-latest.ps1' @{Action='install'; DryRun=$true}
    Check 'LAUNCHER_DRYRUN_FORWARDED' ($dry.Code -eq 0 -and $dry.Dispatch.Contains('-DryRun')) $dry.Text

    $invalidMetadata = @(
        @{ Field='immutable'; Value=$false; Reason='LATEST_RELEASE_MUTABLE' },
        @{ Field='draft'; Value=$true; Reason='LATEST_RELEASE_NOT_PUBLISHED' },
        @{ Field='prerelease'; Value=$true; Reason='LATEST_RELEASE_NOT_PUBLISHED' },
        @{ Field='tag_name'; Value='master'; Reason='LATEST_RELEASE_INVALID' },
        @{ Field='tag_name'; Value="v9.8.7`n"; Reason='LATEST_RELEASE_INVALID' },
        @{ Field='tag_name'; Value='v9.8.7-rc.1'; Reason='LATEST_RELEASE_METADATA_INCONSISTENT' },
        @{ Field='published_at'; Value=$null; Reason='LATEST_RELEASE_NOT_PUBLISHED' },
        @{ Field='published_at'; Value='not-a-date'; Reason='LATEST_RELEASE_METADATA_INVALID' },
        @{ Field='published_at'; Value='2026-10-01T12:00:00'; Reason='LATEST_RELEASE_METADATA_INVALID' },
        @{ Field='published_at'; Value=[DateTimeOffset]::UtcNow.AddMinutes(10); Reason='LATEST_RELEASE_METADATA_INVALID' }
    )
    foreach ($relative in @('install-olympus.ps1','uninstall-olympus.ps1','scripts/launch-latest.ps1')) {
        $arguments = if ($relative -eq 'scripts/launch-latest.ps1') { @{Action='install'} } else { @{} }
        foreach ($case in $invalidMetadata) {
            $script:release = New-Release
            $script:release[$case.Field] = $case.Value
            $result = Invoke-Subject $relative $arguments
            Check "METADATA_${relative}_$($case.Field)_$($case.Reason)" (
                $result.Code -ne 0 -and $result.Text.Contains($case.Reason) -and
                -not $result.Dispatched -and $script:downloads.Count -eq 0
            ) $result.Text
        }
        $script:release = New-Release
        $script:release.Remove('immutable')
        $result = Invoke-Subject $relative $arguments
        Check "METADATA_${relative}_MISSING_FIELD" (
            $result.Code -ne 0 -and $result.Text.Contains('LATEST_RELEASE_METADATA_INCOMPLETE') -and
            -not $result.Dispatched -and $script:downloads.Count -eq 0
        ) $result.Text
        foreach ($value in @(
            '2026-10-01T12:00:00Z',
            '2026-10-01T15:00:00+03:00',
            [DateTime]::Parse('2026-10-01T12:00:00Z', $null, [Globalization.DateTimeStyles]::RoundtripKind),
            [DateTimeOffset]::Parse('2026-10-01T15:00:00+03:00')
        )) {
            $script:release = New-Release
            $script:release.published_at = $value
            $result = Invoke-Subject $relative $arguments
            Check "METADATA_${relative}_ZONED_TIMESTAMP" ($result.Code -eq 0 -and $result.Dispatched) $result.Text
        }
    }
    $script:release = New-Release
    foreach ($identity in @(
        "[string]`$Version = 'v9.8.6'`n`$ReleaseVersion = 'v9.8.6'`n",
        "[string]`$Version = 'v9.8.7'`n`$ReleaseVersion = 'v9.8.6'`n",
        '# no installer identity'
    )) {
        $script:installerText = $identity
        $result = Invoke-Subject 'scripts/launch-latest.ps1' @{Action='install'}
        Check 'MISMATCHED_INSTALLER_NEVER_EXECUTED' (
            $result.Code -ne 0 -and $result.Text.Contains('LATEST_RELEASE_IDENTITY_MISMATCH') -and -not $result.Dispatched
        ) $result.Text
    }
    $script:legacyLauncher = $true
    $result = Invoke-Subject 'install-olympus.ps1'
    Check 'NO_OLDER_LAUNCHER_FALLBACK' (
        $result.Code -ne 0 -and $result.Text.Contains('LAUNCHER_BOOTSTRAP_CONTRACT_MISSING') -and -not $result.Dispatched
    ) $result.Text
    Write-Output 'INSTALLER UX QUALIFICATION: PASS (controlled metadata and native dispatch fixture; not a live endpoint test)'
} finally {
    $env:PATH = $originalPath
    Exit-OlympusInstallerTestEnvironment $previousEnvironment
    Remove-Item Env:OLYMPUS_UX_DISPATCH -ErrorAction SilentlyContinue
    if (Test-Path $run) { Remove-Item $run -Recurse -Force }
}
