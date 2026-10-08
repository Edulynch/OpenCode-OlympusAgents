[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$utf8 = [Text.UTF8Encoding]::new($false)

function Read-ReleaseDocs {
    $paths = @('install.ps1', 'CHANGELOG.md', 'README.md', 'docs/ROADMAP.md')
    $paths += @(Get-ChildItem -LiteralPath (Join-Path $source 'docs') -Filter '*.md' -File -Recurse |
        ForEach-Object { $_.FullName.Substring($source.Length + 1).Replace('\', '/') } | Sort-Object -Unique)
    $docs = [ordered]@{}
    foreach ($relative in @($paths | Sort-Object -Unique)) {
        $path = Join-Path $source ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "DOC_FILE_MISSING: $relative" }
        $docs[$relative] = [IO.File]::ReadAllText($path)
    }
    return ,$docs
}

function Copy-ReleaseDocs($Docs) {
    $copy = [ordered]@{}
    foreach ($key in $Docs.Keys) { $copy[$key] = [string]$Docs[$key] }
    return ,$copy
}

function Get-DocsHash($Docs) {
    $content = [Text.StringBuilder]::new()
    foreach ($key in @($Docs.Keys | Sort-Object)) {
        [void]$content.Append($key).Append("`0").Append([string]$Docs[$key]).Append("`0")
    }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($utf8.GetBytes($content.ToString())))).Replace('-', '') }
    finally { $sha.Dispose() }
}

function Get-ChangelogSection([string]$Text, [string]$Version) {
    $heading = [regex]::Match($Text, '(?m)^##[ \t]+' + [regex]::Escape($Version) + '[ \t]*\r?$')
    if (-not $heading.Success) { return $null }
    $tail = $Text.Substring($heading.Index + $heading.Length)
    $next = [regex]::Match($tail, '(?m)^##[ \t]+v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-(?:alpha|beta|rc)\.(?:0|[1-9][0-9]*))?(?:[ \t]+[^\r\n]*)?\r?$')
    if ($next.Success) { return $tail.Substring(0, $next.Index) }
    return $tail
}

function Get-PrimaryReadmeInstallSection([string]$Readme) {
    return [regex]::Match($Readme, '(?ms)^(?<heading>##[ \t]+[^\r\n]*\bInstall[ \t]*\r?\n)(?<body>.*?)(?=^##[ \t]+|\z)')
}

function Set-ReadmeInstallCommand($Docs, [string]$OldCommand, [string]$NewCommand) {
    $readme = [string]$Docs['README.md']
    $section = Get-PrimaryReadmeInstallSection $readme
    if (-not $section.Success) { throw 'REGRESSION_MUTATION_SETUP_FAILED: README Install section was not found.' }
    $bodyGroup = $section.Groups['body']
    $body = $bodyGroup.Value
    $index = $body.IndexOf($OldCommand, [StringComparison]::Ordinal)
    if ($index -lt 0) { throw "REGRESSION_MUTATION_SETUP_FAILED: Install command was not found: $OldCommand" }
    $updatedBody = $body.Substring(0, $index) + $NewCommand + $body.Substring($index + $OldCommand.Length)
    $Docs['README.md'] = $readme.Substring(0, $bodyGroup.Index) + $updatedBody + $readme.Substring($bodyGroup.Index + $bodyGroup.Length)
}

function Add-ReadmeInstallCommand($Docs, [string]$Command) {
    $readme = [string]$Docs['README.md']
    $section = Get-PrimaryReadmeInstallSection $readme
    if (-not $section.Success) { throw 'REGRESSION_MUTATION_SETUP_FAILED: README Install section was not found.' }
    $bodyGroup = $section.Groups['body']
    $insertAt = $bodyGroup.Index + $bodyGroup.Length
    $Docs['README.md'] = $readme.Substring(0, $insertAt) + $Command + "`n" + $readme.Substring($insertAt)
}

function Get-DocumentationErrors($Docs, [string]$Version, [ValidateSet('PRE_TAG', 'POST_TAG')][string]$TagState) {
    $errors = [System.Collections.Generic.List[string]]::new()
    $versionRegex = [regex]::Escape($Version)
    if ($Version -notmatch '^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$') {
        $errors.Add('DOC_TARGET_NOT_STABLE_VERSION')
    }

    $installer = [string]$Docs['install.ps1']
    $default = [regex]::Match($installer, "(?m)^\s*\[string\]\`$Version\s*=\s*'([^']+)'")
    $release = [regex]::Match($installer, "(?m)^\`$ReleaseVersion\s*=\s*'([^']+)'")
    if (-not $default.Success -or -not $release.Success -or
        $default.Groups[1].Value -cne $Version -or $release.Groups[1].Value -cne $Version) {
        $errors.Add('DOC_ACTIVE_RELEASE_IDENTITY_MISMATCH')
    }

    $changelog = [string]$Docs['CHANGELOG.md']
    if ($changelog -notmatch '(?s)\A# Release notes\s+## \[Unreleased\]') {
        $errors.Add('DOC_UNRELEASED_SECTION_MISSING')
    }
    $section = Get-ChangelogSection $changelog $Version
    if ($null -eq $section) {
        $errors.Add('DOC_RELEASE_SECTION_MISSING')
        $section = ''
    }
    if ($section -notmatch '(?im)^### Highlights\s*$' -or
        $section -notmatch '(?im)^### Capability limits\s*$' -or
        $section -notmatch '(?im)^## Installation\s*$' -or
        $section -notmatch '(?im)^## Verify installation\s*$') {
        $errors.Add('DOC_RELEASE_SECTION_INCOMPLETE')
    }
    if ($section -match '(?i)v0\.3\.0-beta\.5') { $errors.Add('DOC_TARGET_IDENTIFIED_AS_OLD_BETA') }

    $ephemeralPattern = '(?i)\b(?:future|upcoming|planned|pending|not\s+(?:yet\s+)?(?:tagged|merged|publishable|published|released)|(?:do|must)\s+not\s+(?:tag|publish|release)|not\s+publishable|awaiting\s+(?:a\s+)?(?:tag|release)|tag\s+(?:creation|publication)\s+(?:is\s+)?pending|release\s+(?:creation|publication)\s+(?:is\s+)?pending)\b'
    $tagAbsentPattern = '(?i)\b(?:not\s+(?:yet\s+)?tagged|tag\s+(?:is\s+)?(?:absent|pending)|not\s+(?:yet\s+)?published|not\s+(?:yet\s+)?released|no\s+GitHub\s+Release|release\s+not\s+(?:yet\s+)?created|publication\s+pending)\b'
    $tagPresentPattern = '(?i)\b(?:tagged|tag\s+(?:exists|was\s+created|has\s+been\s+created)|already\s+published|release\s+published|was\s+released)\b'
    foreach ($relative in $Docs.Keys) {
        if ($relative -notmatch '\.md$') { continue }
        foreach ($line in ([string]$Docs[$relative] -split '\r?\n')) {
            if ($line -notmatch $versionRegex) { continue }
            if ($line -match $ephemeralPattern -or $line -match $tagAbsentPattern -or $line -match $tagPresentPattern) {
                $errors.Add('DOC_EPHEMERAL_RELEASE_STATE')
            }
            if ($TagState -eq 'PRE_TAG' -and $line -match $tagPresentPattern) {
                $errors.Add('DOC_PRE_TAG_CLAIMS_TAGGED')
            }
            if ($TagState -eq 'POST_TAG' -and $line -match $tagAbsentPattern) {
                $errors.Add('DOC_POST_TAG_CLAIMS_UNTAGGED')
            }
        }
    }

    foreach ($relative in $Docs.Keys) {
        if ($relative -notmatch '\.md$') { continue }
        foreach ($line in ([string]$Docs[$relative] -split '\r?\n')) {
            if ($line -match '(?i)v0\.4\.0' -and $line -match '(?i)\b(?:unmerged|not\s+merged|not\s+integrated|integration\s+pending|not\s+on\s+master|not\s+tagged)\b') {
                $errors.Add('DOC_FOUNDATION_CLAIMED_UNMERGED')
            }
        }
    }

    $readme = [string]$Docs['README.md']
    $installSection = Get-PrimaryReadmeInstallSection $readme
    $readmeInstallInvalid = -not $installSection.Success
    if ($installSection.Success) {
        $installBody = $installSection.Groups['body'].Value
        $publicCommandPattern = '^[ \t]*irm[ \t]+https://raw\.githubusercontent\.com/Edulynch/OpenCode-OlympusAgents/master/install/(?:project|global)/(?:opencode|codex|all)\.ps1[ \t]*\|[ \t]*iex[ \t]*$'
        $requiredEntrypoints = @(
            'project/opencode', 'project/codex', 'project/all',
            'global/opencode', 'global/codex', 'global/all'
        )
        foreach ($entrypoint in $requiredEntrypoints) {
            $command = 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/' + $entrypoint + '.ps1 | iex'
            if (-not [regex]::IsMatch($installBody, '(?m)^[ \t]*' + [regex]::Escape($command) + '[ \t]*\r?$')) {
                $readmeInstallInvalid = $true
            }
        }

        foreach ($line in ($installBody -split '\r?\n')) {
            if ($line -match '(?i)^[ \t]*(?:irm|iwr|invoke-restmethod|invoke-webrequest|iex|invoke-expression)\b') {
                if (-not [regex]::IsMatch($line, $publicCommandPattern)) { $readmeInstallInvalid = $true }
            }
        }
    }
    if ($readme -notmatch 'https://github\.com/Edulynch/OpenCode-OlympusAgents/releases' -or
        $readmeInstallInvalid -or $readme -match 'v0\.4\.[012]') {
        $errors.Add('DOC_README_VERSION_NEUTRAL_INSTALL')
    }

    $roadmap = [string]$Docs['docs/ROADMAP.md']
    if ($roadmap -notmatch '(?i)corrective.{0,120}v0\.4\.2' -or
        $roadmap -notmatch '(?i)v0\.4\.0.{0,500}(?:no\s+GitHub\s+Release|no\s+release\s+was\s+created)' -or
        $roadmap -notmatch '(?i)v0\.4\.1.{0,500}(?:no\s+GitHub\s+Release|no\s+release\s+was\s+created)') {
        $errors.Add('DOC_ROADMAP_RELEASE_HISTORY')
    }
    foreach ($required in @('issue #1 remains OPEN', 'discovery #7 remains OPEN',
            '[#10](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/10) are CLOSED',
            'OpenCode global runtime discovery is a known GAP', 'Codex DENY/Aegis remain gaps')) {
        if (-not [regex]::IsMatch($roadmap, [regex]::Escape($required), [Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            $errors.Add('DOC_KNOWN_CAPABILITY_GAP_MISSING')
        }
    }
    return @($errors | Sort-Object -Unique)
}

function Assert-Rejected($Docs, [string]$Version, [string]$TagState, [string]$ExpectedCode, [string]$Case) {
    $errors = @(Get-DocumentationErrors $Docs $Version $TagState)
    if ($errors -notcontains $ExpectedCode) {
        throw "REGRESSION_MUTATION_NOT_REJECTED: $Case expected=$ExpectedCode actual=$($errors -join ',')"
    }
    Write-Output "$Case PASS"
}

function Add-CandidateClaim($Docs, [string]$Version, [string]$Claim) {
    $pattern = '(?m)^##[ \t]+' + [regex]::Escape($Version) + '[ \t]*\r?$'
    $heading = [regex]::new($pattern)
    $Docs['CHANGELOG.md'] = $heading.Replace([string]$Docs['CHANGELOG.md'], "## $Version`n`n$Claim`n", 1)
}

try {
    $docs = Read-ReleaseDocs
    $versionMatch = [regex]::Match([string]$docs['install.ps1'], "(?m)^\s*\[string\]\`$Version\s*=\s*'([^']+)'")
    if (-not $versionMatch.Success) { throw 'DOC_ACTIVE_RELEASE_IDENTITY_MISMATCH: Installer default was not found.' }
    $version = $versionMatch.Groups[1].Value
    $initialHash = Get-DocsHash $docs

    $preErrors = @(Get-DocumentationErrors $docs $version 'PRE_TAG')
    if ($preErrors.Count) { throw "PRE_TAG_SEMANTIC_VALIDATION_FAIL: $($preErrors -join ', ')" }
    Write-Output 'PRE_TAG_SEMANTIC_VALIDATION: PASS'

    $postErrors = @(Get-DocumentationErrors $docs $version 'POST_TAG')
    if ($postErrors.Count) { throw "SIMULATED_POST_TAG_SEMANTIC_VALIDATION_FAIL: $($postErrors -join ', ')" }
    Write-Output 'SIMULATED_POST_TAG_SEMANTIC_VALIDATION: PASS'
    $finalHash = Get-DocsHash $docs
    if ($initialHash -cne $finalHash) { throw 'TAG_TRANSITION_DOC_BYTES_CHANGED' }
    Write-Output "TAG_TRANSITION_STABILITY: PASS (same documentation bytes; SHA256=$initialHash)"

    $badState = Copy-ReleaseDocs $docs
    Add-CandidateClaim $badState $version "**$version is not tagged; do not publish.**"
    Assert-Rejected $badState $version 'PRE_TAG' 'DOC_EPHEMERAL_RELEASE_STATE' 'REGRESSION_REJECTS_EPHEMERAL_RELEASE_STATE'
    Assert-Rejected $badState $version 'POST_TAG' 'DOC_POST_TAG_CLAIMS_UNTAGGED' 'REGRESSION_REJECTS_POST_TAG_UNTAGGED_CLAIM'

    $badPositiveTag = Copy-ReleaseDocs $docs
    Add-CandidateClaim $badPositiveTag $version "**$version is already tagged.**"
    Assert-Rejected $badPositiveTag $version 'PRE_TAG' 'DOC_PRE_TAG_CLAIMS_TAGGED' 'REGRESSION_REJECTS_PRE_TAGGED_CLAIM'

    $badBeta = Copy-ReleaseDocs $docs
    Add-CandidateClaim $badBeta $version 'This target is the old v0.3.0-beta.5 release.'
    Assert-Rejected $badBeta $version 'PRE_TAG' 'DOC_TARGET_IDENTIFIED_AS_OLD_BETA' 'REGRESSION_REJECTS_OLD_BETA_IDENTITY'

    $badFoundation = Copy-ReleaseDocs $docs
    $badFoundation['docs/ROADMAP.md'] = ([string]$badFoundation['docs/ROADMAP.md']) + "`nThe v0.4.0 foundation remains unmerged.`n"
    Assert-Rejected $badFoundation $version 'POST_TAG' 'DOC_FOUNDATION_CLAIMED_UNMERGED' 'REGRESSION_REJECTS_UNMERGED_FOUNDATION_CLAIM'

    $badIdentity = Copy-ReleaseDocs $docs
    $releaseIdentityRegex = [regex]::new("(?m)^\`$ReleaseVersion\s*=\s*'[^']+'")
    $badIdentity['install.ps1'] = $releaseIdentityRegex.Replace([string]$badIdentity['install.ps1'], "`$ReleaseVersion = 'v0.4.1'", 1)
    Assert-Rejected $badIdentity $version 'PRE_TAG' 'DOC_ACTIVE_RELEASE_IDENTITY_MISMATCH' 'REGRESSION_REJECTS_ACTIVE_IDENTITY_MISMATCH'

    $projectOpenCodeCommand = 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/project/opencode.ps1 | iex'
    $badMissingPublicEntrypoint = Copy-ReleaseDocs $docs
    Set-ReadmeInstallCommand $badMissingPublicEntrypoint $projectOpenCodeCommand ''
    Assert-Rejected $badMissingPublicEntrypoint $version 'PRE_TAG' 'DOC_README_VERSION_NEUTRAL_INSTALL' 'REGRESSION_REJECTS_MISSING_PUBLIC_ENTRYPOINT_WITH_UPDATE_DUPLICATE'

    $badWrongPublicEntrypoint = Copy-ReleaseDocs $docs
    Set-ReadmeInstallCommand $badWrongPublicEntrypoint 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/global/all.ps1 | iex' 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/project/all.ps1 | iex'
    Assert-Rejected $badWrongPublicEntrypoint $version 'PRE_TAG' 'DOC_README_VERSION_NEUTRAL_INSTALL' 'REGRESSION_REJECTS_WRONG_PUBLIC_ENTRYPOINT_SCOPE'

    $badPinnedInstaller = Copy-ReleaseDocs $docs
    $pinnedInstallerCommand = 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/' + $version + '/install.ps1 | iex'
    Set-ReadmeInstallCommand $badPinnedInstaller 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/project/codex.ps1 | iex' $pinnedInstallerCommand
    Assert-Rejected $badPinnedInstaller $version 'PRE_TAG' 'DOC_README_VERSION_NEUTRAL_INSTALL' 'REGRESSION_REJECTS_PINNED_DIRECT_INSTALLER_URL'

    $badDirectInstaller = Copy-ReleaseDocs $docs
    Set-ReadmeInstallCommand $badDirectInstaller 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/global/opencode.ps1 | iex' 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install.ps1 | iex'
    Assert-Rejected $badDirectInstaller $version 'PRE_TAG' 'DOC_README_VERSION_NEUTRAL_INSTALL' 'REGRESSION_REJECTS_ROOT_DIRECT_INSTALLER_URL'

    $badForeignInstaller = Copy-ReleaseDocs $docs
    Set-ReadmeInstallCommand $badForeignInstaller 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install/project/all.ps1 | iex' 'irm https://example.invalid/install/project/all.ps1 | iex'
    Assert-Rejected $badForeignInstaller $version 'PRE_TAG' 'DOC_README_VERSION_NEUTRAL_INSTALL' 'REGRESSION_REJECTS_FOREIGN_INSTALLER_URL'

    $badExtraForeignInstaller = Copy-ReleaseDocs $docs
    Add-ReadmeInstallCommand $badExtraForeignInstaller 'irm https://example.invalid/install/project/opencode.ps1 | iex'
    Assert-Rejected $badExtraForeignInstaller $version 'PRE_TAG' 'DOC_README_VERSION_NEUTRAL_INSTALL' 'REGRESSION_REJECTS_EXTRA_FOREIGN_INSTALLER_WITH_VALID_ENTRYPOINTS'

    Write-Output "TAG-TRANSITION-STABILITY QUALIFICATION: PASS ($version; deterministic static semantic checks; no tag or GitHub Release created)"
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'TAG-TRANSITION-STABILITY QUALIFICATION: FAIL'
    exit 1
}
