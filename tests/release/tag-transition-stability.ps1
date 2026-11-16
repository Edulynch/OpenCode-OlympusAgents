[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$genericUrl = 'https://github.com/Edulynch/OpenCode-OlympusAgents/releases/latest/download/install-olympus.ps1'
$installCommand = "& ([scriptblock]::Create((irm '$genericUrl')))"

function Read-ReleaseDocs {
    $paths = @('install.ps1','README.md','CHANGELOG.md','docs/INSTALLATION.md','docs/DEVELOPMENT.md',
        'docs/ROADMAP.md','docs/WORKFLOWS.md','docs/HARNESS-CAPABILITIES.md','olympus/harnesses/capabilities.toml')
    foreach ($action in @('install','uninstall')) {
        foreach ($scope in @('project','global')) {
            foreach ($harness in @('opencode','codex','all')) { $paths += "$action/$scope/$harness.ps1" }
        }
    }
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
    if (-not (Test-ReadmeCommands $Docs['README.md'] $Version)) { $issues.Add('DOC_README_IMMUTABLE_ENTRYPOINT_INVALID') }
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
    foreach ($action in @('install','uninstall')) {
        foreach ($scope in @('project','global')) {
            foreach ($harness in @('opencode','codex','all')) {
                $wrapper = $Docs["$action/$scope/$harness.ps1"]
                if ($scope -eq 'global' -and $harness -eq 'opencode') {
                    $valid = if ($action -eq 'install') { $wrapper.Contains($genericUrl) }
                        else { $wrapper.Contains('uninstall --execute') }
                    if (-not $valid -or $wrapper -match '-Target|Get-Location|/master/') {
                        $issues.Add('DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID')
                    }
                } else {
                    $tokens = $null
                    $errors = $null
                    $ast = [Management.Automation.Language.Parser]::ParseInput($wrapper, [ref]$tokens, [ref]$errors)
                    if ($errors.Count -or $ast.EndBlock.Statements.Count -ne 1 -or
                        $ast.EndBlock.Statements[0] -isnot [Management.Automation.Language.ThrowStatementAst] -or
                        $wrapper -notmatch 'PUBLIC_(?:UN)?INSTALL_ROUTE_UNSUPPORTED') {
                        $issues.Add('DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID')
                    }
                }
            }
        }
    }
    # Keep the existing shared capability and frozen-gap gates.
    $states = @{}
    foreach ($harness in @('opencode','codex')) {
        $body = [regex]::Match($Docs['olympus/harnesses/capabilities.toml'],
            '(?ms)^\[' + $harness + '\]\s*\r?\n(?<body>.*?)(?=^\[|\z)').Groups['body'].Value
        $states[$harness] = @{}
        foreach ($match in [regex]::Matches($body, '(?m)^\s*(?<name>[A-Z0-9_]+)\s*=\s*"(?<value>SUPPORTED|ADAPTABLE|PARTIAL|GAP|NOT_NEEDED)"')) {
            $states[$harness][$match.Groups['name'].Value] = $match.Groups['value'].Value
        }
    }
    $rows = @([regex]::Matches($Docs['docs/HARNESS-CAPABILITIES.md'], '(?m)^\| `(?<name>[A-Z0-9_]+)` \| (?<oc>[A-Z_]+) \| (?<cx>[A-Z_]+) \|'))
    if ($states.opencode.Count -eq 0 -or $rows.Count -ne $states.opencode.Count -or
        $states.codex.Count -ne $states.opencode.Count) { $issues.Add('DOC_GLOBAL_DISCOVERY_CONTRACT_MISMATCH') }
    foreach ($name in $states.opencode.Keys) {
        $row = @($rows | Where-Object { $_.Groups['name'].Value -ceq $name })
        if ($row.Count -ne 1 -or $row[0].Groups['oc'].Value -cne $states.opencode[$name] -or
            $row[0].Groups['cx'].Value -cne $states.codex[$name]) { $issues.Add('DOC_GLOBAL_DISCOVERY_CONTRACT_MISMATCH') }
    }
    foreach ($claim in @('issue #1 remains OPEN',
        '[#10](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/10) are CLOSED',
        'Codex DENY and contextual Olympus maintenance remain explicit frozen GAPs')) {
        if (-not $Docs['docs/ROADMAP.md'].Contains($claim)) { $issues.Add('DOC_KNOWN_CAPABILITY_GAP_MISSING') }
    }
    $roadmap = $Docs['docs/ROADMAP.md']
    if ($roadmap -notmatch '(?i)corrective.{0,120}v0\.4\.2' -or
        $roadmap -notmatch '(?i)v0\.4\.0.{0,500}(?:no\s+GitHub\s+Release|no\s+release\s+was\s+created)' -or
        $roadmap -notmatch '(?i)v0\.4\.1.{0,500}(?:no\s+GitHub\s+Release|no\s+release\s+was\s+created)') {
        $issues.Add('DOC_ROADMAP_RELEASE_HISTORY')
    }
    if ($roadmap -notmatch '(?i)\b(?:global[ \t]+discovery|issue)[ \t]+#7\b') { $issues.Add('DOC_KNOWN_CAPABILITY_GAP_MISSING') }
    $openCodeClaim = '(?i)OpenCode V2[^\r\n]*GLOBAL_RUNTIME_DISCOVERY\s*=\s*`?' +
        [regex]::Escape([string]$states.opencode['GLOBAL_RUNTIME_DISCOVERY']) + '`?'
    $codexClaim = '(?i)Codex remains\s+`?' +
        [regex]::Escape([string]$states.codex['GLOBAL_RUNTIME_DISCOVERY']) + '`?\s+on separately supplied evidence'
    $workflow = $Docs['docs/WORKFLOWS.md']
    if ($roadmap -notmatch $openCodeClaim -or $roadmap -notmatch $codexClaim -or
        ($workflow -match '(?i)OpenCode supports the current contextual maintenance workflow') -ne
            ($states.opencode['CONTEXTUAL_OLYMPUS_MAINTENANCE'] -eq 'SUPPORTED') -or
        ($workflow -match '(?i)Codex currently declares it a capability gap') -ne
            ($states.codex['CONTEXTUAL_OLYMPUS_MAINTENANCE'] -eq 'GAP')) {
        $issues.Add('DOC_GLOBAL_DISCOVERY_CONTRACT_MISMATCH')
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
    "$installCommand -Harness codex",
    "$installCommand`n$installCommand"
)) {
    $bad = $docs.Clone()
    $bad['README.md'] = $bad['README.md'].Replace($installCommand, $replacement)
    Assert-Rejected $bad $version 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID'
}
$bad = $docs.Clone()
$bad['README.md'] += "`n## Fast Extra`n"
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
$bad['install/project/codex.ps1'] += "`nInvoke-WebRequest 'https://example.invalid/unsafe.ps1'"
Assert-Rejected $bad $version 'DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID'
$bad = $docs.Clone()
$bad['docs/INSTALLATION.md'] = $bad['docs/INSTALLATION.md'].Replace('pending_uninstall','omitted')
Assert-Rejected $bad $version 'DOC_INSTALLATION_SAFETY_INCOMPLETE'
$bad = $docs.Clone()
$bad['docs/DEVELOPMENT.md'] = $bad['docs/DEVELOPMENT.md'].Replace('**before publishing**', 'after publishing')
Assert-Rejected $bad $version 'DOC_ASSET_PUBLICATION_PREREQUISITE_MISSING'
$bad = $docs.Clone()
$bad['README.md'] += "`nPrepared for a future release.`n"
Assert-Rejected $bad $version 'DOC_STALE_PUBLICATION_WARNING'
$bad = $docs.Clone()
$bad['docs/HARNESS-CAPABILITIES.md'] = $bad['docs/HARNESS-CAPABILITIES.md'].Replace(
    '| `CONTEXTUAL_OLYMPUS_MAINTENANCE` | SUPPORTED | GAP |',
    '| `CONTEXTUAL_OLYMPUS_MAINTENANCE` | GAP | GAP |')
Assert-Rejected $bad $version 'DOC_GLOBAL_DISCOVERY_CONTRACT_MISMATCH'
Write-Output 'TAG-TRANSITION-STABILITY QUALIFICATION: PASS (static source/docs only; no release or endpoint availability claim)'
