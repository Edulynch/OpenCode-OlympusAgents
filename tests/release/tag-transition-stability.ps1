[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$genericUrl = 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1'
$installCommand = "& ([scriptblock]::Create((irm '$genericUrl')))"
$latestReleaseUrl = 'https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest'

function Read-ReleaseDocs {
    $paths = @('install.ps1','README.md','CHANGELOG.md','docs/INSTALLATION.md','docs/DEVELOPMENT.md',
        'docs/HARNESSES.md','docs/HARNESS-CAPABILITIES.md','olympus/harnesses/capabilities.toml')
    $docs = @{}
    foreach ($path in $paths) { $docs[$path] = [IO.File]::ReadAllText((Join-Path $source $path)) }
    return $docs
}

function Get-PowerShellStatements([string]$Markdown) {
    foreach ($block in [regex]::Matches($Markdown, '(?ims)^```(?:powershell|pwsh|ps1)[ \t]*\r?\n(?<body>.*?)^```[ \t]*\r?$')) {
        $tokens = $null
        $errors = $null
        $ast = [Management.Automation.Language.Parser]::ParseInput($block.Groups['body'].Value, [ref]$tokens, [ref]$errors)
        if ($errors.Count) { throw 'DOC_POWERSHELL_PARSE_ERROR' }
        foreach ($statement in $ast.EndBlock.Statements) { $statement }
    }
}

function Test-ReadmeCommands([string]$Readme, [string]$Version) {
    try {
        $pinnedCommand = "& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$Version/install.ps1')))"
        foreach ($action in @('Install','Uninstall')) {
            $section = [regex]::Matches($Readme, '(?ms)^## Fast ' + $action + '[ \t]*\r?\n(?<body>.*?)(?=^## |\z)')
            if ($section.Count -ne 1) { return $false }
            $statements = @(Get-PowerShellStatements $section[0].Groups['body'].Value)
            $expected = if ($action -eq 'Install') { $installCommand } else { 'olympus uninstall' }
            if ($statements.Count -ne 1 -or $statements[0].Extent.Text.Trim() -cne $expected) { return $false }
        }
        if ([regex]::Matches($Readme, '(?m)^## Fast ').Count -ne 2) { return $false }
        $pinnedSection = [regex]::Matches($Readme, '(?ms)^## Install a specific version[ \t]*\r?\n(?<body>.*?)(?=^## |\z)')
        if ($pinnedSection.Count -ne 1) { return $false }
        $pinnedStatements = @(Get-PowerShellStatements $pinnedSection[0].Groups['body'].Value)
        if ($pinnedStatements.Count -ne 1 -or $pinnedStatements[0].Extent.Text.Trim() -cne $pinnedCommand) { return $false }
        $remoteCount = 0
        foreach ($statement in @(Get-PowerShellStatements $Readme)) {
            $commands = @($statement.FindAll({ param($node)
                $node -is [Management.Automation.Language.CommandAst]
            }, $true))
            foreach ($command in $commands) {
                $name = [string]$command.GetCommandName()
                if ($name -match '^(?i:irm|iwr|curl(?:\.exe)?|wget(?:\.exe)?|Invoke-RestMethod|Invoke-WebRequest|iex|Invoke-Expression)$') {
                    if ($statement.Extent.Text.Trim() -cnotin @($installCommand, $pinnedCommand) -or $name -cne 'irm') { return $false }
                    $remoteCount++
                }
                if ($name -match '^(?i:pwsh(?:\.exe)?|powershell(?:\.exe)?|Start-Process)$' -and
                    $statement.Extent.Text -match '(?:un)?install.*\.ps1') { return $false }
                if ($name -match '(?i)(?:^|[\\/])(?:un)?install(?:-olympus)?\.ps1$') { return $false }
            }
        }
        return $remoteCount -eq 2
    } catch { return $false }
}

function Get-ChangelogSection([string]$Text, [string]$Version) {
    $heading = [regex]::Match($Text, '(?m)^## ' + [regex]::Escape($Version) + '[ \t]*\r?$')
    if (-not $heading.Success) { return '' }
    $tail = $Text.Substring($heading.Index + $heading.Length)
    $next = [regex]::Match($tail, '(?m)^## v[0-9]+\.[0-9]+\.[0-9]+')
    return $(if ($next.Success) { $tail.Substring(0, $next.Index) } else { $tail })
}

function Normalize-Documentation([string]$Text) {
    return [regex]::Replace($Text, '\s+', ' ').Trim()
}

function Get-DocumentationErrors([hashtable]$Docs, [string]$Version) {
    $issues = [Collections.Generic.List[string]]::new()
    $installer = $Docs['install.ps1']
    $default = [regex]::Match($installer, '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''')
    $marker = [regex]::Match($installer, '(?m)^\s*\$ReleaseVersion\s*=\s*''([^'']+)''')
    if ($Version -notmatch '\Av(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\z' -or
        -not $default.Success -or -not $marker.Success -or
        $default.Groups[1].Value -cne $Version -or $marker.Groups[1].Value -cne $Version) {
        $issues.Add('DOC_ACTIVE_RELEASE_IDENTITY_MISMATCH')
    }
    $section = Get-ChangelogSection $Docs['CHANGELOG.md'] $Version
    foreach ($heading in @('### Highlights','### Capability limits','## Installation','## Verify installation')) {
        if (-not $section.Contains($heading)) { $issues.Add('DOC_RELEASE_SECTION_INCOMPLETE') }
    }
    if ($Docs['CHANGELOG.md'] -notmatch '\A# Release notes\s+## \[Unreleased\]') {
        $issues.Add('DOC_UNRELEASED_SECTION_MISSING')
    }
    # Static release notes must not encode ephemeral tag state.
    if ($section -match '(?i)is not tagged|is already tagged|is already published|do not publish|old v0\.3\.0-beta\.5') {
        $issues.Add('DOC_EPHEMERAL_RELEASE_STATE')
    }
    $readme = $Docs['README.md']
    if (-not (Test-ReadmeCommands $readme $Version) -or
        -not $readme.Contains('published, immutable') -or
        $readme -notmatch '(?i)global and OpenCode-only' -or
        $readme.Contains("/$Version/install-olympus.ps1") -or
        $readme.Contains("/$Version/uninstall-olympus.ps1")) {
        $issues.Add('DOC_README_IMMUTABLE_ENTRYPOINT_INVALID')
    }
    foreach ($token in @('**draft**', '**before publishing**', 'verify its bytes match the tag', 'immutability enabled')) {
        if (-not $Docs['docs/DEVELOPMENT.md'].Contains($token)) {
            $issues.Add('DOC_ASSET_PUBLICATION_PREREQUISITE_MISSING')
        }
    }
    foreach ($path in @('README.md','docs/INSTALLATION.md')) {
        if ($Docs[$path] -match '(?i)future release|not a currently working endpoint|not available from v0\.7\.0') {
            $issues.Add('DOC_STALE_PUBLICATION_WARNING')
        }
    }
    foreach ($token in @('immutable=true','draft=false','prerelease=false','published_at','tag_name',
        'time-zone-aware','five minutes in the future','exact tag archive','matching version and release markers',
        'no mutable-branch or older-launcher fallback','does not independently verify a signature',
        'pending_set','committed','pending_uninstall','default_agent_receipt','VerifyOnly')) {
        if (-not $Docs['docs/INSTALLATION.md'].Contains($token)) { $issues.Add('DOC_INSTALLATION_SAFETY_INCOMPLETE') }
    }
    $installationGuide = $Docs['docs/INSTALLATION.md']
    $pinnedCommand = "& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$Version/install.ps1')))"
    if (-not $installationGuide.Contains($installCommand) -or
        -not $installationGuide.Contains('olympus uninstall') -or
        -not $installationGuide.Contains($Version) -or
        -not $installationGuide.Contains($latestReleaseUrl) -or
        -not $installationGuide.Contains($pinnedCommand) -or
        $installationGuide.Contains("/$Version/install-olympus.ps1") -or
        $installationGuide.Contains("/$Version/uninstall-olympus.ps1")) {
        $issues.Add('DOC_INSTALLATION_ENTRYPOINT_CONTRACT_INCOMPLETE')
    }
    $installationContract = Normalize-Documentation ($Docs['docs/INSTALLATION.md'] + ' ' + $Docs['docs/HARNESSES.md'])
    foreach ($phrase in @(
        '`schema_version=1`',
        '`scope=project`',
        '`installed_harnesses=["opencode"]`',
        'nonempty `installed_version` and `installed_from_commit`',
        'current 15-path managed inventory',
        '`scope=global`, exactly OpenCode',
        '`installed_version=local` or a release tag',
        'nonempty `installed_from_commit`',
        '`default_agent_receipt`',
        '15 base resources are managed',
        '16 resources are managed',
        'Both are valid current formats.',
        'The two namespaced command files are global-only',
        'exact, hash-verified v0.10.0 global 13/14-path inventories',
        '`VerifyOnly`, global doctor, and global config apply report that an update is required',
        'New command destinations that already exist without current manifest ownership are collisions',
        'An incomplete or unsupported format is rejected without automatic conversion, adoption, or deletion',
        'If an older unsupported installation needs removal, use the release that owns it'
    )) {
        if ($installationContract.IndexOf($phrase, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
            $issues.Add('DOC_INSTALLATION_FORMAT_CONTRACT_INCOMPLETE')
        }
    }
    foreach ($phrase in @(
        'The receipt states `pending_set`, `committed`, and `pending_uninstall`',
        '`VerifyOnly` never writes or approves a pending state',
        'A missing file means empty',
        'precedence is project override, global override, then Core defaults'
    )) {
        if ($installationContract.IndexOf($phrase, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
            $issues.Add('DOC_INSTALLATION_RECOVERY_CONTRACT_INCOMPLETE')
        }
    }
    $capabilitySections = @([regex]::Matches($Docs['olympus/harnesses/capabilities.toml'], '(?m)^\[(?<name>[^\]]+)\][ \t]*\r?$'))
    $states = @{}
    if ($capabilitySections.Count -ne 1) {
        $issues.Add('DOC_OPENCODE_CAPABILITY_CONTRACT_MISMATCH')
    } elseif ($capabilitySections[0].Groups['name'].Value -cne 'opencode') {
        $issues.Add('DOC_OPENCODE_CAPABILITY_CONTRACT_MISMATCH')
    }
    foreach ($match in [regex]::Matches($Docs['olympus/harnesses/capabilities.toml'],
        '(?m)^\s*(?<name>[A-Z0-9_]+)\s*=\s*"(?<value>SUPPORTED|ADAPTABLE|PARTIAL|GAP|NOT_NEEDED)"[ \t]*\r?$')) {
        $name = $match.Groups['name'].Value
        if ($states.ContainsKey($name)) { $issues.Add('DOC_OPENCODE_CAPABILITY_CONTRACT_MISMATCH') }
        $states[$name] = $match.Groups['value'].Value
    }
    $capabilityDoc = $Docs['docs/HARNESS-CAPABILITIES.md']
    $rows = @([regex]::Matches($capabilityDoc, '(?m)^\| `(?<name>[A-Z0-9_]+)` \| (?<state>[A-Z_]+) \|[ \t]*\r?$'))
    if ($states.Count -eq 0 -or $rows.Count -ne $states.Count -or
        [regex]::Matches($capabilityDoc, '(?m)^\| Capability \| OpenCode \|[ \t]*\r?$').Count -ne 1) {
        $issues.Add('DOC_OPENCODE_CAPABILITY_CONTRACT_MISMATCH')
    }
    foreach ($name in $states.Keys) {
        $row = @($rows | Where-Object { $_.Groups['name'].Value -ceq $name })
        if ($row.Count -ne 1) {
            $issues.Add('DOC_OPENCODE_CAPABILITY_CONTRACT_MISMATCH')
            continue
        }
        if ($row[0].Groups['state'].Value -cne $states[$name]) {
            $issues.Add('DOC_OPENCODE_CAPABILITY_CONTRACT_MISMATCH')
        }
    }
    return @($issues | Sort-Object -Unique)
}

function Assert-Rejected([hashtable]$Docs, [string]$Version, [string]$Expected) {
    $issues = @(Get-DocumentationErrors $Docs $Version)
    if ($Expected -notin $issues) { throw "REGRESSION_MUTATION_NOT_REJECTED: expected=$Expected actual=$($issues -join ',')" }
    Write-Output "REGRESSION_REJECTS_$Expected PASS"
}

$docs = Read-ReleaseDocs
$version = [regex]::Match($docs['install.ps1'], '(?m)^\s*\[string\]\$Version\s*=\s*''([^'']+)''').Groups[1].Value
$pinnedCommand = "& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/$version/install.ps1')))"
foreach ($tagState in @('PRE_TAG','SIMULATED_POST_TAG')) {
    $issues = @(Get-DocumentationErrors $docs $version)
    if ($issues.Count) { throw "${tagState}_SEMANTIC_VALIDATION_FAIL: $($issues -join ',')" }
    Write-Output "${tagState}_SEMANTIC_VALIDATION: PASS"
}
foreach ($replacement in @(
    "& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install-olympus.ps1')))",
    "& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.6.1/install-olympus.ps1')))",
    "irm $genericUrl | iex",
    "$installCommand -Harness opencode",
    "$installCommand`n$installCommand"
)) {
    $bad = $docs.Clone()
    $bad['README.md'] = $bad['README.md'].Replace($installCommand, $replacement)
    Assert-Rejected $bad $version 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID'
}
$bad = $docs.Clone()
$bad['README.md'] = $bad['README.md'].Replace(
    $installCommand,
    $installCommand + "`n" + 'pwsh -NoProfile -File .\install-olympus.ps1 -Project -Here -Harness all')
Assert-Rejected $bad $version 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID'
$bad = $docs.Clone()
$bad['README.md'] += "`n## Alternative setup`n`n" + '```powershell' + "`n" +
    'pwsh -NoProfile -File .\install-olympus.ps1 -Project -Here -Harness all' + "`n" + '```' + "`n"
Assert-Rejected $bad $version 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID'
$bad = $docs.Clone()
$bad['README.md'] += "`n## Alternative setup`n`n" + '```powershell' + "`n" +
    "& ([scriptblock]::Create((irm '$genericUrl'))) -Global -Harness all" + "`n" + '```' + "`n"
Assert-Rejected $bad $version 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID'
$bad = $docs.Clone()
$bad['README.md'] = $bad['README.md'].Replace(
    $installCommand,
    "& ([scriptblock]::Create((irm 'https://example.invalid/install-olympus.ps1')))")
Assert-Rejected $bad $version 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID'
$readmeWithLf = $docs.Clone()
$readmeWithLf['README.md'] = $readmeWithLf['README.md'].Replace("`r`n", "`n")
$readmeWithCrLf = $docs.Clone()
$readmeWithCrLf['README.md'] = $readmeWithLf['README.md'].Replace("`n", "`r`n")
foreach ($candidate in @($readmeWithLf, $readmeWithCrLf)) {
    $issues = @(Get-DocumentationErrors $candidate $version)
    if ($issues.Count) { throw "REGRESSION_README_LINE_ENDINGS_REJECTED: $($issues -join ',')" }
}
Write-Output 'REGRESSION_README_ACCEPTS_LF_AND_CRLF PASS'
$readmeWithProseAndComments = $docs.Clone()
$readmeWithProseAndComments['README.md'] += "`n## Command references`n`nThe example ``irm $genericUrl | iex`` is descriptive only; see [installer reference](https://example.invalid/install-olympus.ps1).`n`n## Commented example`n`n" +
    '```powershell' + "`n# irm https://example.invalid/install-olympus.ps1 | iex`n" + '```' + "`n"
$issues = @(Get-DocumentationErrors $readmeWithProseAndComments $version)
if ($issues.Count) { throw "REGRESSION_README_PROSE_LINKS_OR_COMMENTS_REJECTED: $($issues -join ',')" }
Write-Output 'REGRESSION_README_IGNORES_PROSE_LINKS_AND_COMMENTS PASS'
$bad = $docs.Clone()
$bad['README.md'] += "`n## Fast Extra`n"
Assert-Rejected $bad $version 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID'
$bad = $docs.Clone()
$bad['README.md'] += "`r`n## Fast Extra`r`n"
Assert-Rejected $bad $version 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID'
$bad = $docs.Clone()
$bad['README.md'] += "`n## Alternative`n" + '```powershell' + "`n$installCommand`n" + '```'
Assert-Rejected $bad $version 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID'
foreach ($replacement in @(
    $pinnedCommand.Replace("/$version/", '/master/'),
    $pinnedCommand.Replace('/install.ps1', '/install-olympus.ps1'),
    "$pinnedCommand -Version '$version'",
    '# missing pinned installer'
)) {
    $bad = $docs.Clone()
    $bad['README.md'] = $bad['README.md'].Replace($pinnedCommand, $replacement)
    Assert-Rejected $bad $version 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID'
}
$bad = $docs.Clone()
$bad['install.ps1'] = $bad['install.ps1'].Replace("`$ReleaseVersion = '$version'", "`$ReleaseVersion = 'v9.9.9'")
Assert-Rejected $bad $version 'DOC_ACTIVE_RELEASE_IDENTITY_MISMATCH'
$bad = $docs.Clone()
$bad['CHANGELOG.md'] = $bad['CHANGELOG.md'].Replace("## $version", "## $version`n$version is not tagged; do not publish.")
Assert-Rejected $bad $version 'DOC_EPHEMERAL_RELEASE_STATE'
$bad = $docs.Clone()
$bad['docs/INSTALLATION.md'] = $bad['docs/INSTALLATION.md'].Replace('pending_uninstall','omitted')
Assert-Rejected $bad $version 'DOC_INSTALLATION_SAFETY_INCOMPLETE'
$bad = $docs.Clone()
$bad['docs/INSTALLATION.md'] = $bad['docs/INSTALLATION.md'].Replace($latestReleaseUrl, 'https://example.invalid/releases/latest')
Assert-Rejected $bad $version 'DOC_INSTALLATION_ENTRYPOINT_CONTRACT_INCOMPLETE'
$bad = $docs.Clone()
$bad['docs/DEVELOPMENT.md'] = $bad['docs/DEVELOPMENT.md'].Replace('**before publishing**', 'after publishing')
Assert-Rejected $bad $version 'DOC_ASSET_PUBLICATION_PREREQUISITE_MISSING'
$bad = $docs.Clone()
$bad['README.md'] += "`nPrepared for a future release.`n"
Assert-Rejected $bad $version 'DOC_STALE_PUBLICATION_WARNING'
$bad = $docs.Clone()
$bad['docs/INSTALLATION.md'] = $bad['docs/INSTALLATION.md'] -replace 'Both are valid current\s+formats\.', 'Both are legacy formats.'
if ($bad['docs/INSTALLATION.md'] -ceq $docs['docs/INSTALLATION.md']) {
    throw 'REGRESSION_MUTATION_NOT_APPLIED: installation format contract'
}
Assert-Rejected $bad $version 'DOC_INSTALLATION_FORMAT_CONTRACT_INCOMPLETE'
$bad = $docs.Clone()
$bad['docs/HARNESS-CAPABILITIES.md'] = $bad['docs/HARNESS-CAPABILITIES.md'].Replace(
    '| `CONTEXTUAL_OLYMPUS_MAINTENANCE` | SUPPORTED |',
    '| `CONTEXTUAL_OLYMPUS_MAINTENANCE` | GAP |')
Assert-Rejected $bad $version 'DOC_OPENCODE_CAPABILITY_CONTRACT_MISMATCH'
Write-Output 'TAG-TRANSITION-STABILITY QUALIFICATION: PASS (static source/docs only; no release or endpoint availability claim)'
