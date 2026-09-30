[CmdletBinding()]
param(
    [string]$Version = '',
    # Contract fixture input is used by release qualification; normal gate use
    # omits it and inspects the published GitHub Release body with gh.
    [string]$ReleaseBody
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-ReleaseNotes([string]$Body, [string]$Tag) {
    $installationHeading = [regex]::Matches($Body, '(?im)^##[ \t]+Installation[ \t]*\r?$')
    if ($installationHeading.Count -eq 0) {
        throw 'RELEASE_NOTES_INSTALLATION_MISSING: Required Installation heading is absent.'
    }
    $verificationHeading = [regex]::Matches($Body, '(?im)^##[ \t]+Verify installation[ \t]*\r?$')
    if ($verificationHeading.Count -eq 0) {
        throw 'RELEASE_NOTES_VERIFY_MISSING: Required Verify installation heading is absent.'
    }
    if ($installationHeading.Count -ne 1 -or $verificationHeading.Count -ne 1) {
        throw 'RELEASE_NOTES_SECTION_AMBIGUOUS: Installation sections must be unique.'
    }
    function Heading-Body([string]$Text, $Heading) {
        $start = $Heading.Index + $Heading.Length
        $remaining = $Text.Substring($start)
        $nextHeading = [regex]::Match($remaining, '(?m)^#{1,2}[ \t]+')
        if ($nextHeading.Success) { return $remaining.Substring(0, $nextHeading.Index) }
        return $remaining
    }
    $installationBody = Heading-Body $Body $installationHeading[0]
    $verificationBody = Heading-Body $Body $verificationHeading[0]
    $base = 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/' + $Tag + '/install.ps1'
    $install = "irm $base | iex"
    $verify = "& ([scriptblock]::Create((irm '$base'))) -Version '$Tag' -Target (Get-Location).Path -VerifyOnly"
    if (-not $installationBody.Contains($install)) {
        throw 'RELEASE_NOTES_INSTALL_PIN_MISMATCH: Installation command must use the exact release tag.'
    }
    if (-not $verificationBody.Contains($verify)) {
        throw 'RELEASE_NOTES_VERIFY_PIN_MISMATCH: Verify command must use the same exact release tag and -VerifyOnly.'
    }
    if ($Tag -cne 'v0.3.0-beta.4') {
        $codexInstall = "& ([scriptblock]::Create((irm '$base'))) -Harness codex"
        $allInstall = "& ([scriptblock]::Create((irm '$base'))) -Harness all"
        $opencodeVerify = "& ([scriptblock]::Create((irm '$base'))) -Harness opencode -Version '$Tag' -Target (Get-Location).Path -VerifyOnly"
        $codexVerify = "& ([scriptblock]::Create((irm '$base'))) -Harness codex -Version '$Tag' -Target (Get-Location).Path -VerifyOnly"
        $allVerify = "& ([scriptblock]::Create((irm '$base'))) -Harness all -Version '$Tag' -Target (Get-Location).Path -VerifyOnly"
        foreach ($command in @($codexInstall, $allInstall)) {
            if (-not $installationBody.Contains($command)) {
                throw 'RELEASE_NOTES_HARNESS_INSTALL_MISSING: Installation section must publish Codex and all-harness commands.'
            }
        }
        foreach ($command in @($opencodeVerify, $codexVerify, $allVerify)) {
            if (-not $verificationBody.Contains($command)) {
                throw 'RELEASE_NOTES_HARNESS_VERIFY_MISSING: Verify section must publish OpenCode, Codex, and all subset checks.'
            }
        }
    }
    if ($Body -match '(?i)raw\.githubusercontent\.com/Edulynch/OpenCode-OlympusAgents/master/install\.ps1') {
        throw 'RELEASE_NOTES_MASTER_SOURCE: A mutable master installer is not a canonical release source.'
    }
}

try {
    if (-not $Version) {
        $installerPath = Join-Path $PSScriptRoot '../../install.ps1'
        if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
            throw 'RELEASE_VERSION_UNAVAILABLE: The candidate installer could not be found.'
        }
        $installerText = [IO.File]::ReadAllText($installerPath)
        $defaultVersion = [regex]::Match($installerText, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''')
        $releaseVersion = [regex]::Match($installerText, '(?m)^\s*\$ReleaseVersion\s*=\s*''([^'']+)''')
        if (-not $defaultVersion.Success -or -not $releaseVersion.Success -or
            $defaultVersion.Groups[1].Value -cne $releaseVersion.Groups[1].Value) {
            throw 'RELEASE_VERSION_UNAVAILABLE: Installer default and release marker do not agree.'
        }
        $Version = $defaultVersion.Groups[1].Value
    }
    if ($Version -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?$') {
        throw 'RELEASE_VERSION_INVALID: Requested release version is malformed.'
    }
    if ($PSBoundParameters.ContainsKey('ReleaseBody')) {
        Assert-ReleaseNotes $ReleaseBody $Version
        Write-Output "RELEASE_NOTES_CONTRACT: $Version PASS (fixture body)"
        exit 0
    }

    $gh = Get-Command gh -CommandType Application -ErrorAction SilentlyContinue
    if (-not $gh) { throw 'GITHUB_RELEASE_UNAVAILABLE: gh CLI is required to inspect the published release.' }
    $json = (& $gh.Source release view $Version --repo Edulynch/OpenCode-OlympusAgents --json tagName,isPrerelease,body 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "GITHUB_RELEASE_UNAVAILABLE: Cannot read release '$Version'. $($json.Trim())" }
    try { $release = $json | ConvertFrom-Json -Depth 20 }
    catch { throw 'GITHUB_RELEASE_UNAVAILABLE: GitHub Release response is not valid JSON.' }
    if ([string]$release.tagName -cne $Version) { throw 'GITHUB_RELEASE_TAG_MISMATCH: GitHub Release tag differs from the requested tag.' }
    Assert-ReleaseNotes ([string]$release.body) $Version
    Write-Output "GITHUB_RELEASE_NOTES: $Version PASS"
} catch {
    $message = $_.Exception.Message
    $reason = if ($message -match '^([A-Z][A-Z0-9_]+):') { $Matches[1] } else { 'RELEASE_NOTES_GATE_FAILED' }
    Write-Output "GITHUB_RELEASE_NOTES: $Version FAIL"
    Write-Output "GITHUB_RELEASE_NOTES_REASON: $reason"
    Write-Output "GITHUB_RELEASE_NOTES_DETAIL: $message"
    exit 1
}
