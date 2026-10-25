[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$utf8 = [Text.UTF8Encoding]::new($false)

function Read-ReleaseDocs {
    $paths = @('install.ps1', 'CHANGELOG.md', 'README.md', 'docs/ROADMAP.md', 'olympus/harnesses/capabilities.toml')
    foreach ($action in @('install','uninstall')) {
        foreach ($scope in @('project','global')) {
            foreach ($harness in @('opencode','codex','all')) {
                $paths += "$action/$scope/$harness.ps1"
            }
        }
    }
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

# Read the canonical per-harness claim instead of hard-coding an old GAP.
function Get-GlobalDiscoveryState([string]$Toml, [ValidateSet('opencode', 'codex')][string]$Harness) {
    $section = [regex]::Match(
        $Toml,
        '(?ms)^\[' + [regex]::Escape($Harness) + '\][ \t]*\r?\n(?<body>.*?)(?=^\[|\z)'
    )
    if (-not $section.Success) { return '' }
    $state = [regex]::Match(
        $section.Groups['body'].Value,
        '(?m)^[ \t]*GLOBAL_RUNTIME_DISCOVERY[ \t]*=[ \t]*"(?<value>SUPPORTED|ADAPTABLE|PARTIAL|GAP|NOT_NEEDED)"[ \t]*\r?$'
    )
    if (-not $state.Success) { return '' }
    return $state.Groups['value'].Value
}

function Get-CanonicalCapabilityStates([string]$Toml, [ValidateSet('opencode', 'codex')][string]$Harness) {
    $section = [regex]::Match(
        $Toml,
        '(?ms)^\[' + [regex]::Escape($Harness) + '\][ \t]*\r?\n(?<body>.*?)(?=^\[|\z)'
    )
    $states = [ordered]@{}
    if (-not $section.Success) { return ,$states }
    foreach ($match in [regex]::Matches(
        $section.Groups['body'].Value,
        '(?m)^[ \t]*(?<name>[A-Z0-9_]+)[ \t]*=[ \t]*"(?<value>SUPPORTED|ADAPTABLE|PARTIAL|GAP|NOT_NEEDED)"[ \t]*\r?$'
    )) {
        $states[$match.Groups['name'].Value] = $match.Groups['value'].Value
    }
    return ,$states
}

function Get-PrimaryReadmeInstallSection([string]$Readme) {
    return [regex]::Match($Readme, '(?ms)^(?<heading>##[ \t]+Fast Install[ \t]*\r?\n)(?<body>.*?)(?=^##[ \t]+|\z)')
}

function Get-PrimaryReadmeUninstallSection([string]$Readme) {
    return [regex]::Match($Readme, '(?ms)^##[ \t]+Fast Uninstall[ \t]*\r?\n(?<body>.*?)(?=^##[ \t]+|\z)')
}

function Get-PowerShellCodeBlocks([string]$Markdown) {
    $blocks = [System.Collections.Generic.List[string]]::new()
    foreach ($block in [regex]::Matches($Markdown, '(?ims)^```(?:powershell|pwsh|ps1)[ \t]*\r?\n(?<body>.*?)^```[ \t]*\r?$')) {
        $blocks.Add($block.Groups['body'].Value)
    }
    return $blocks.ToArray()
}

function Get-PowerShellCodeBlockLines([string]$Markdown) {
    $lines = [System.Collections.Generic.List[string]]::new()
    foreach ($body in @(Get-PowerShellCodeBlocks $Markdown)) {
        foreach ($line in ($body -split '\r?\n')) { $lines.Add($line) }
    }
    return $lines.ToArray()
}

function Get-PowerShellParsedStatements([string]$Markdown) {
    $statements = [System.Collections.Generic.List[object]]::new()
    $hasParseErrors = $false
    foreach ($code in @(Get-PowerShellCodeBlocks $Markdown)) {
        $tokens = $null
        $parseErrors = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseInput($code, [ref]$tokens, [ref]$parseErrors)
        if ($parseErrors.Count -gt 0) { $hasParseErrors = $true }
        foreach ($statement in $ast.EndBlock.Statements) { $statements.Add($statement) }
    }
    return [pscustomobject]@{ Statements = $statements.ToArray(); HasParseErrors = $hasParseErrors }
}

function Test-ExpectedFastBootstrapStatement($Statement, [string]$ExpectedCommand) {
    $tokens = $null
    $parseErrors = $null
    $expectedAst = [System.Management.Automation.Language.Parser]::ParseInput($ExpectedCommand, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count -gt 0 -or $expectedAst.EndBlock.Statements.Count -ne 1 -or
        $Statement -isnot [System.Management.Automation.Language.PipelineAst]) { return $false }
    $expectedPipeline = $expectedAst.EndBlock.Statements[0]
    if ($expectedPipeline -isnot [System.Management.Automation.Language.PipelineAst] -or
        $Statement.Background -or $expectedPipeline.Background -or
        $Statement.PipelineElements.Count -ne 2 -or $expectedPipeline.PipelineElements.Count -ne 2) { return $false }
    for ($index = 0; $index -lt 2; $index++) {
        $actualCommand = $Statement.PipelineElements[$index]
        $expectedCommandAst = $expectedPipeline.PipelineElements[$index]
        if ($actualCommand -isnot [System.Management.Automation.Language.CommandAst] -or
            $expectedCommandAst -isnot [System.Management.Automation.Language.CommandAst] -or
            $actualCommand.GetCommandName() -cne $expectedCommandAst.GetCommandName() -or
            $actualCommand.InvocationOperator -ne [System.Management.Automation.Language.TokenKind]::Unknown -or
            $actualCommand.Redirections.Count -ne 0 -or
            $actualCommand.CommandElements.Count -ne $expectedCommandAst.CommandElements.Count) { return $false }
        for ($element = 0; $element -lt $actualCommand.CommandElements.Count; $element++) {
            $actualValue = $actualCommand.CommandElements[$element]
            $expectedValue = $expectedCommandAst.CommandElements[$element]
            if ($actualValue -isnot [System.Management.Automation.Language.StringConstantExpressionAst] -or
                $expectedValue -isnot [System.Management.Automation.Language.StringConstantExpressionAst] -or
                $actualValue.Value -cne $expectedValue.Value) { return $false }
        }
    }
    return $true
}

function Test-GlobalReadmeInstallerContract([string]$Markdown, [string]$InstallCommand, [string]$UninstallCommand) {
    $parsed = Get-PowerShellParsedStatements $Markdown
    if ($parsed.HasParseErrors) { return $false }
    $remoteNames = '^(?:irm|iwr|curl(?:\.exe)?|wget(?:\.exe)?|invoke-restmethod|invoke-webrequest|iex|invoke-expression)$'
    $launcherNames = '^(?:pwsh(?:\.exe)?|powershell(?:\.exe)?|start-process)$'
    $installerPath = '(?i)(?:^|[\\/])(?:install|uninstall)(?:-olympus)?\.ps1$'
    $installerFileMention = '(?i)(?:install|uninstall)(?:-olympus)?\.ps1\b'
    $remoteStatements = [System.Collections.Generic.List[object]]::new()
    $directInstallerFound = $false
    foreach ($statement in $parsed.Statements) {
        $commands = @($statement.FindAll({ param($node) $node -is [System.Management.Automation.Language.CommandAst] }, $true))
        $hasRemoteCommand = $false
        foreach ($command in $commands) {
            $name = [string]$command.GetCommandName()
            if ($name -match $remoteNames) { $hasRemoteCommand = $true }
            if (($name -match $launcherNames -and $statement.Extent.Text -match $installerFileMention) -or
                $name -match $installerPath) {
                $directInstallerFound = $true
            }
        }
        if ($hasRemoteCommand) { $remoteStatements.Add($statement) }
    }
    if ($directInstallerFound -or $remoteStatements.Count -ne 2) { return $false }
    $installCount = 0
    $uninstallCount = 0
    foreach ($statement in $remoteStatements) {
        if (Test-ExpectedFastBootstrapStatement $statement $InstallCommand) { $installCount++ }
        elseif (Test-ExpectedFastBootstrapStatement $statement $UninstallCommand) { $uninstallCount++ }
        else { return $false }
    }
    return ($installCount -eq 1 -and $uninstallCount -eq 1)
}

function Test-ReadmeFastCommandAllowlist([string]$Readme, [string]$InstallCommand, [string]$UninstallCommand) {
    foreach ($action in @('install', 'uninstall')) {
        $section = if ($action -eq 'install') { Get-PrimaryReadmeInstallSection $Readme } else { Get-PrimaryReadmeUninstallSection $Readme }
        if (-not $section.Success) { return $false }
        $parsed = Get-PowerShellParsedStatements $section.Groups['body'].Value
        if ($parsed.HasParseErrors -or $parsed.Statements.Count -ne 1) { return $false }
        $expected = if ($action -eq 'install') { $InstallCommand } else { $UninstallCommand }
        if (-not (Test-ExpectedFastBootstrapStatement $parsed.Statements[0] $expected)) { return $false }
    }
    return $true
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
    $codeBlock = [regex]::Match($bodyGroup.Value, '(?ims)^```(?:powershell|pwsh|ps1)[ \t]*\r?\n(?<body>.*?)^```[ \t]*\r?$')
    if (-not $codeBlock.Success) { throw 'REGRESSION_MUTATION_SETUP_FAILED: README Fast Install PowerShell block was not found.' }
    $codeBody = $codeBlock.Groups['body']
    $insertAt = $bodyGroup.Index + $codeBody.Index + $codeBody.Length
    $prefix = if ($codeBody.Value.EndsWith("`n") -or $codeBody.Value.EndsWith("`r")) { '' } else { "`n" }
    $Docs['README.md'] = $readme.Substring(0, $insertAt) + $prefix + $Command + "`n" + $readme.Substring($insertAt)
}

function Get-DocumentationErrors($Docs, [string]$Version, [ValidateSet('PRE_TAG', 'POST_TAG')][string]$TagState) {
    $errors = [System.Collections.Generic.List[string]]::new()
    $versionRegex = [regex]::Escape($Version)
    if ($Version -cne 'v0.4.12') { $errors.Add('DOC_TARGET_IDENTITY_NOT_V0412') }
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
    $publicInvalid = $false
    $rawBase = 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/' + $Version + '/'
    $fastInstallCommand = 'irm ' + $rawBase + 'install-olympus.ps1 | iex'
    $fastUninstallCommand = 'irm ' + $rawBase + 'uninstall-olympus.ps1 | iex'
    if ([regex]::Matches($readme, '(?m)^##[ \t]+Fast Install[ \t]*\r?$').Count -ne 1 -or
        [regex]::Matches($readme, '(?m)^##[ \t]+Fast Uninstall[ \t]*\r?$').Count -ne 1) {
        $publicInvalid = $true
    }
    if (-not (Test-ReadmeFastCommandAllowlist $readme $fastInstallCommand $fastUninstallCommand) -or
        -not (Test-GlobalReadmeInstallerContract $readme $fastInstallCommand $fastUninstallCommand)) {
        $publicInvalid = $true
    }
    $versionedBootstrapPattern = '(?i)versioned[ \t]+`?' + $versionRegex + '`?[ \t]+bootstrap'
    $readmeReleaseContractInvalid = (
        -not [regex]::IsMatch($readme, $versionedBootstrapPattern) -or
        $readme -notmatch '(?i)releases/latest.{0,160}metadata.{0,160}published release.{0,80}tag' -or
        $readme -notmatch '(?i)release metadata checks fail closed' -or
        $readme -notmatch '(?i)GitHub.{0,60}immutability flag.{0,80}not independent cryptographic signature verification'
    )
    if ($readme -notmatch 'https://github\.com/Edulynch/OpenCode-OlympusAgents/releases' -or
        $readmeReleaseContractInvalid -or $publicInvalid) {
        $errors.Add('DOC_README_IMMUTABLE_ENTRYPOINT_INVALID')
    }

    $installationGuide = [string]$Docs['docs/INSTALLATION.md']
    $interactivePromptingInvalid = (
        $installationGuide -notmatch '(?i)\binteractive terminal\b[^\r\n.]*\basks for scope and harness\b' -or
        $installationGuide -notmatch '(?i)\bvalid partial selection\b[^\r\n.]*\basks only for the missing values\b'
    )
    $missingInputFailureInvalid = -not [regex]::IsMatch(
        $installationGuide,
        '(?im)^.*\b(?:a required value is missing|incomplete selections?)\b.*\b(?:interactive input is unavailable|other usable interactive input)\b.*\bARGUMENTS_REQUIRED\b.*$'
    )
    $invalidScopeExplanationInvalid = (
        $installationGuide -notmatch '(?i)\b(?:supply|provide|use) `?-Project`? and `?-Here`? together\b' -or
        $installationGuide -notmatch '(?i)\blone\b[^\r\n.]*`-Project`[^\r\n.]*\bor\b[^\r\n.]*`-Here`[^\r\n.]*\binvalid\b' -or
        $installationGuide -notmatch '(?i)\bmutually exclusive\b' -or
        $installationGuide -notmatch '(?i)\bcontradictory\b[^\r\n.]*\breject\w*\b'
    )
    $directOptionsInvalid = (
        $installationGuide -notmatch '(?i)`-Harness` accepts `opencode`, `codex`, or `all`' -or
        $installationGuide -notmatch '(?i)`-Harness`[^\r\n.]*\bno implicit default\b' -or
        $installationGuide -notmatch '(?i)mutually exclusive' -or
        $installationGuide -notmatch '(?i)VerifyOnly' -or
        $installationGuide -notmatch '(?i)read-only' -or
        $interactivePromptingInvalid -or
        $missingInputFailureInvalid -or
        $invalidScopeExplanationInvalid
    )
    foreach ($action in @('install', 'uninstall')) {
        $projectHerePattern = '(?m)^[ \t]*& \$' + $action + ' -Project -Here -Harness (?:opencode|codex|all)[ \t]*\r?$'
        $projectPathPattern = '(?m)^[ \t]*& \$' + $action + ' -ProjectPath ''[^''\r\n]*\s[^''\r\n]*'' -Harness (?:opencode|codex|all)[ \t]*\r?$'
        $globalPattern = '(?m)^[ \t]*& \$' + $action + ' -Global -Harness (?:opencode|codex|all)[ \t]*\r?$'
        if (-not [regex]::IsMatch($installationGuide, $projectHerePattern) -or
            -not [regex]::IsMatch($installationGuide, $projectPathPattern) -or
            -not [regex]::IsMatch($installationGuide, $globalPattern)) {
            $directOptionsInvalid = $true
        }
        foreach ($harness in @('opencode', 'codex', 'all')) {
            $harnessPattern = '(?m)^[ \t]*& \$' + $action + ' [^\r\n]+ -Harness ' + $harness + '[ \t]*\r?$'
            if (-not [regex]::IsMatch($installationGuide, $harnessPattern)) { $directOptionsInvalid = $true }
        }
    }
    $releasePrerequisiteInvalid = (
        -not $installationGuide.Contains($fastInstallCommand) -or
        -not $installationGuide.Contains($fastUninstallCommand) -or
        $installationGuide -notmatch '(?i)https://api\.github\.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest' -or
        $installationGuide -notmatch '(?i)\bimmutable\s*=\s*true\b' -or
        $installationGuide -notmatch '(?i)\bdraft\s*=\s*false\b' -or
        $installationGuide -notmatch '(?i)\bprerelease\s*=\s*false\b' -or
        $installationGuide -notmatch '(?i)published timestamp' -or
        $installationGuide -notmatch '(?i)tag_name' -or
        $installationGuide -notmatch '(?i)scripts/launch-latest\.ps1' -or
        $installationGuide -notmatch '(?i)exact tag archive' -or
        $installationGuide -notmatch '(?i)matching version and release markers' -or
        $installationGuide -notmatch '(?i)no mutable-branch or older-launcher fallback' -or
        $installationGuide -notmatch '(?i)does not independently verify a signature'
    )
    if ($releasePrerequisiteInvalid) {
        $errors.Add('DOC_INSTALLATION_RELEASE_PREREQUISITE_INVALID')
    }
    if ($directOptionsInvalid) { $errors.Add('DOC_INSTALLATION_DIRECT_OPTIONS_INVALID') }

    foreach ($action in @('install','uninstall')) {
        foreach ($scope in @('project','global')) {
            foreach ($harness in @('opencode','codex','all')) {
                $relative = "$action/$scope/$harness.ps1"
                $wrapper = [string]$Docs[$relative]
                $launcherUrl = $rawBase + 'scripts/launch-latest.ps1'
                $externalUrls = [regex]::Matches($wrapper, 'https://raw\.githubusercontent\.com/Edulynch/OpenCode-OlympusAgents/[^\s]+?\.ps1')
                if ($externalUrls.Count -ne 1 -or $externalUrls[0].Value -cne $launcherUrl -or
                    -not $wrapper.Contains("Invoke-WebRequest -Uri '$launcherUrl' -OutFile " + '$launcher' + " -ErrorAction Stop") -or
                    -not $wrapper.Contains("-Action '$action' -Scope '$scope' -Harness '$harness' -Target (Get-Location).Path")) {
                    $errors.Add('DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID')
                }
            }
        }
    }

    $roadmap = [string]$Docs['docs/ROADMAP.md']
    if ($roadmap -notmatch '(?i)corrective.{0,120}v0\.4\.2' -or
        $roadmap -notmatch '(?i)v0\.4\.0.{0,500}(?:no\s+GitHub\s+Release|no\s+release\s+was\s+created)' -or
        $roadmap -notmatch '(?i)v0\.4\.1.{0,500}(?:no\s+GitHub\s+Release|no\s+release\s+was\s+created)') {
        $errors.Add('DOC_ROADMAP_RELEASE_HISTORY')
    }
    foreach ($required in @('issue #1 remains OPEN',
            '[#10](https://github.com/Edulynch/OpenCode-OlympusAgents/issues/10) are CLOSED',
            'Codex DENY/Aegis remain gaps')) {
        if (-not [regex]::IsMatch($roadmap, [regex]::Escape($required), [Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
            $errors.Add('DOC_KNOWN_CAPABILITY_GAP_MISSING')
        }
    }
    if ($roadmap -notmatch '(?i)\b(?:global[ \t]+discovery|issue)[ \t]+#7\b') {
        $errors.Add('DOC_KNOWN_CAPABILITY_GAP_MISSING')
    }

    # Compare the complete published capability matrix with the canonical adapter source.
    $capabilities = [string]$Docs['olympus/harnesses/capabilities.toml']
    $openCodeStates = Get-CanonicalCapabilityStates $capabilities 'opencode'
    $codexStates = Get-CanonicalCapabilityStates $capabilities 'codex'
    $generatedCapabilities = [string]$Docs['docs/HARNESS-CAPABILITIES.md']
    $documentedRows = @([regex]::Matches(
        $generatedCapabilities,
        '(?m)^\| `(?<name>[A-Z0-9_]+)` \| (?<opencode>SUPPORTED|ADAPTABLE|PARTIAL|GAP|NOT_NEEDED) \| (?<codex>SUPPORTED|ADAPTABLE|PARTIAL|GAP|NOT_NEEDED) \|[ \t]*\r?$'
    ))
    $capabilityMismatch = ($openCodeStates.Count -eq 0 -or $openCodeStates.Count -ne $codexStates.Count -or
        $documentedRows.Count -ne $openCodeStates.Count)
    foreach ($name in $openCodeStates.Keys) {
        $row = @($documentedRows | Where-Object { $_.Groups['name'].Value -ceq $name })
        if (-not $codexStates.Contains($name) -or $row.Count -ne 1 -or
            $row[0].Groups['opencode'].Value -cne $openCodeStates[$name] -or
            $row[0].Groups['codex'].Value -cne $codexStates[$name]) {
            $capabilityMismatch = $true
        }
    }
    $openCodeGlobal = $openCodeStates['GLOBAL_RUNTIME_DISCOVERY']
    $codexGlobal = $codexStates['GLOBAL_RUNTIME_DISCOVERY']
    $readmeOpenAegisClaim = $readme -match '(?i)explicit `/maintain` invokes hidden Aegis'
    $readmeCodexAegisClaim = $readme -match '(?i)Codex has no equivalent Aegis capability'
    $roadmapOpenGlobal = '(?i)OpenCode V2[^\r\n]*GLOBAL_RUNTIME_DISCOVERY\s*=\s*`?' + [regex]::Escape([string]$openCodeGlobal) + '`?'
    $roadmapCodexGlobal = '(?i)Codex remains\s+`?' + [regex]::Escape([string]$codexGlobal) + '`?\s+on separately supplied evidence'
    if ($capabilityMismatch -or -not $openCodeGlobal -or -not $codexGlobal -or
        $readmeOpenAegisClaim -ne ($openCodeStates['AEGIS'] -eq 'SUPPORTED') -or
        $readmeCodexAegisClaim -ne ($codexStates['AEGIS'] -eq 'GAP') -or
        -not [regex]::IsMatch($roadmap, $roadmapOpenGlobal) -or
        -not [regex]::IsMatch($roadmap, $roadmapCodexGlobal)) {
        $errors.Add('DOC_GLOBAL_DISCOVERY_CONTRACT_MISMATCH')
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
    Write-Output "R0_RELEASE_IDENTITY: PASS ($version)"

    $postErrors = @(Get-DocumentationErrors $docs $version 'POST_TAG')
    if ($postErrors.Count) { throw "SIMULATED_POST_TAG_SEMANTIC_VALIDATION_FAIL: $($postErrors -join ', ')" }
    Write-Output 'SIMULATED_POST_TAG_SEMANTIC_VALIDATION: PASS'
    Write-Output 'R0_TWO_FAST_COMMANDS_AND_DIRECT_OPTIONS: PASS'
    Write-Output 'R0_LEGACY_WRAPPERS_AND_CAPABILITIES: PASS'
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

    $badPublishedClaim = Copy-ReleaseDocs $docs
    Add-CandidateClaim $badPublishedClaim $version "**$version is already published.**"
    Assert-Rejected $badPublishedClaim $version 'PRE_TAG' 'DOC_EPHEMERAL_RELEASE_STATE' 'REGRESSION_REJECTS_FALSE_PUBLISHED_RELEASE_CLAIM'

    $badBeta = Copy-ReleaseDocs $docs
    Add-CandidateClaim $badBeta $version 'This target is the old v0.3.0-beta.5 release.'
    Assert-Rejected $badBeta $version 'PRE_TAG' 'DOC_TARGET_IDENTIFIED_AS_OLD_BETA' 'REGRESSION_REJECTS_OLD_BETA_IDENTITY'

    $badFoundation = Copy-ReleaseDocs $docs
    $badFoundation['docs/ROADMAP.md'] = ([string]$badFoundation['docs/ROADMAP.md']) + "`nThe v0.4.0 foundation remains unmerged.`n"
    Assert-Rejected $badFoundation $version 'POST_TAG' 'DOC_FOUNDATION_CLAIMED_UNMERGED' 'REGRESSION_REJECTS_UNMERGED_FOUNDATION_CLAIM'

    # Negative controls: this gate must reject contradictory current claims,
    # without requiring OpenCode to remain in its historical GAP state.
    $openCodeState = Get-GlobalDiscoveryState ([string]$docs['olympus/harnesses/capabilities.toml']) 'opencode'
    $codexState = Get-GlobalDiscoveryState ([string]$docs['olympus/harnesses/capabilities.toml']) 'codex'
    if (-not $openCodeState -or -not $codexState) { throw 'REGRESSION_MUTATION_SETUP_FAILED: canonical discovery states missing.' }
    $otherState = if ($openCodeState -eq 'SUPPORTED') { 'GAP' } else { 'SUPPORTED' }
    $correctRow = '| `GLOBAL_RUNTIME_DISCOVERY` | ' + $openCodeState + ' | ' + $codexState + ' |'
    $wrongRow = '| `GLOBAL_RUNTIME_DISCOVERY` | ' + $otherState + ' | ' + $codexState + ' |'
    $badGlobalTable = Copy-ReleaseDocs $docs
    if (-not ([string]$badGlobalTable['docs/HARNESS-CAPABILITIES.md']).Contains($correctRow)) {
        throw 'REGRESSION_MUTATION_SETUP_FAILED: expected capability row missing.'
    }
    $badGlobalTable['docs/HARNESS-CAPABILITIES.md'] = ([string]$badGlobalTable['docs/HARNESS-CAPABILITIES.md']).Replace($correctRow, $wrongRow)
    Assert-Rejected $badGlobalTable $version 'POST_TAG' 'DOC_GLOBAL_DISCOVERY_CONTRACT_MISMATCH' 'REGRESSION_REJECTS_GLOBAL_CAPABILITY_TABLE_MISMATCH'

    $badAegisCapabilityTable = Copy-ReleaseDocs $docs
    $correctAegisRow = '| `AEGIS` | SUPPORTED | GAP |'
    $wrongAegisRow = '| `AEGIS` | GAP | GAP |'
    if (-not ([string]$badAegisCapabilityTable['docs/HARNESS-CAPABILITIES.md']).Contains($correctAegisRow)) {
        throw 'REGRESSION_MUTATION_SETUP_FAILED: expected Aegis capability row missing.'
    }
    $badAegisCapabilityTable['docs/HARNESS-CAPABILITIES.md'] = ([string]$badAegisCapabilityTable['docs/HARNESS-CAPABILITIES.md']).Replace($correctAegisRow, $wrongAegisRow)
    Assert-Rejected $badAegisCapabilityTable $version 'POST_TAG' 'DOC_GLOBAL_DISCOVERY_CONTRACT_MISMATCH' 'REGRESSION_REJECTS_AEGIS_CAPABILITY_TABLE_MISMATCH'

    $correctClaim = '`GLOBAL_RUNTIME_DISCOVERY = ' + $openCodeState + '`'
    $wrongClaim = '`GLOBAL_RUNTIME_DISCOVERY = ' + $otherState + '`'
    $badGlobalRoadmap = Copy-ReleaseDocs $docs
    if (-not ([string]$badGlobalRoadmap['docs/ROADMAP.md']).Contains($correctClaim)) {
        throw 'REGRESSION_MUTATION_SETUP_FAILED: expected roadmap discovery claim missing.'
    }
    $badGlobalRoadmap['docs/ROADMAP.md'] = ([string]$badGlobalRoadmap['docs/ROADMAP.md']).Replace($correctClaim, $wrongClaim)
    Assert-Rejected $badGlobalRoadmap $version 'POST_TAG' 'DOC_GLOBAL_DISCOVERY_CONTRACT_MISMATCH' 'REGRESSION_REJECTS_GLOBAL_ROADMAP_MISMATCH'

    $badKnownCodexGap = Copy-ReleaseDocs $docs
    $codexGapClaim = 'Codex DENY/Aegis remain gaps'
    if (-not ([string]$badKnownCodexGap['docs/ROADMAP.md']).Contains($codexGapClaim)) {
        throw 'REGRESSION_MUTATION_SETUP_FAILED: existing Codex capability gaps missing.'
    }
    $badKnownCodexGap['docs/ROADMAP.md'] = ([string]$badKnownCodexGap['docs/ROADMAP.md']).Replace($codexGapClaim, 'Codex capabilities are unchanged')
    Assert-Rejected $badKnownCodexGap $version 'POST_TAG' 'DOC_KNOWN_CAPABILITY_GAP_MISSING' 'REGRESSION_REJECTS_MISSING_CODEX_GAPS'

    $badIdentity = Copy-ReleaseDocs $docs
    $releaseIdentityRegex = [regex]::new("(?m)^\`$ReleaseVersion\s*=\s*'[^']+'")
    $badIdentity['install.ps1'] = $releaseIdentityRegex.Replace([string]$badIdentity['install.ps1'], "`$ReleaseVersion = 'v0.4.1'", 1)
    Assert-Rejected $badIdentity $version 'PRE_TAG' 'DOC_ACTIVE_RELEASE_IDENTITY_MISMATCH' 'REGRESSION_REJECTS_ACTIVE_IDENTITY_MISMATCH'

    $badTargetIdentity = Copy-ReleaseDocs $docs
    $badTargetIdentity['install.ps1'] = ([string]$badTargetIdentity['install.ps1']).Replace("[string]`$Version = '$version'", "[string]`$Version = 'v0.4.11'").Replace("`$ReleaseVersion = '$version'", "`$ReleaseVersion = 'v0.4.11'")
    Assert-Rejected $badTargetIdentity 'v0.4.11' 'PRE_TAG' 'DOC_TARGET_IDENTITY_NOT_V0412' 'REGRESSION_REJECTS_NON_V0412_TARGET'

    $tagBase = 'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/' + $version + '/'
    $fastInstallCommand = 'irm ' + $tagBase + 'install-olympus.ps1 | iex'
    $fastUninstallCommand = 'irm ' + $tagBase + 'uninstall-olympus.ps1 | iex'
    $badMissingPublicEntrypoint = Copy-ReleaseDocs $docs
    Set-ReadmeInstallCommand $badMissingPublicEntrypoint $fastInstallCommand ''
    Assert-Rejected $badMissingPublicEntrypoint $version 'PRE_TAG' 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID' 'REGRESSION_REJECTS_MISSING_PUBLIC_ENTRYPOINT'

    $badWrongPublicEntrypoint = Copy-ReleaseDocs $docs
    Set-ReadmeInstallCommand $badWrongPublicEntrypoint $fastInstallCommand $fastUninstallCommand
    Assert-Rejected $badWrongPublicEntrypoint $version 'PRE_TAG' 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID' 'REGRESSION_REJECTS_WRONG_PUBLIC_ENTRYPOINT_ACTION'

    $badCodexWithoutSelection = Copy-ReleaseDocs $docs
    $wrapper = 'install/project/codex.ps1'
    $badCodexWithoutSelection[$wrapper] = ([string]$badCodexWithoutSelection[$wrapper]).Replace("-Harness 'codex' ", '')
    Assert-Rejected $badCodexWithoutSelection $version 'PRE_TAG' 'DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID' 'REGRESSION_REJECTS_CODEX_WITHOUT_HARNESS_SELECTION'

    $badMutablePublic = Copy-ReleaseDocs $docs
    Set-ReadmeInstallCommand $badMutablePublic $fastInstallCommand 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/master/install-olympus.ps1 | iex'
    Assert-Rejected $badMutablePublic $version 'PRE_TAG' 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID' 'REGRESSION_REJECTS_MUTABLE_PUBLIC_ENTRYPOINT'

    $badObsoletePublic = Copy-ReleaseDocs $docs
    Set-ReadmeInstallCommand $badObsoletePublic $fastInstallCommand 'irm https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/v0.4.9/install-olympus.ps1 | iex'
    Assert-Rejected $badObsoletePublic $version 'PRE_TAG' 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID' 'REGRESSION_REJECTS_OBSOLETE_PUBLIC_ENTRYPOINT'

    $badMutableLauncher = Copy-ReleaseDocs $docs
    $wrapper = 'install/project/opencode.ps1'
    $badMutableLauncher[$wrapper] = ([string]$badMutableLauncher[$wrapper]).Replace(
        '/' + $version + '/scripts/launch-latest.ps1', '/master/scripts/launch-latest.ps1')
    Assert-Rejected $badMutableLauncher $version 'PRE_TAG' 'DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID' 'REGRESSION_REJECTS_MUTABLE_WRAPPER_LAUNCHER'

    $badWrongWrapperHarness = Copy-ReleaseDocs $docs
    $wrapper = 'install/project/opencode.ps1'
    $badWrongWrapperHarness[$wrapper] = ([string]$badWrongWrapperHarness[$wrapper]).Replace("-Harness 'opencode'","-Harness 'codex'")
    Assert-Rejected $badWrongWrapperHarness $version 'PRE_TAG' 'DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID' 'REGRESSION_REJECTS_WRONG_WRAPPER_HARNESS'

    $badWrongWrapperAction = Copy-ReleaseDocs $docs
    $wrapper = 'install/project/opencode.ps1'
    $badWrongWrapperAction[$wrapper] = ([string]$badWrongWrapperAction[$wrapper]).Replace("-Action 'install'", "-Action 'uninstall'")
    Assert-Rejected $badWrongWrapperAction $version 'PRE_TAG' 'DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID' 'REGRESSION_REJECTS_WRONG_WRAPPER_ACTION'

    $badWrongWrapperScope = Copy-ReleaseDocs $docs
    $wrapper = 'install/project/opencode.ps1'
    $badWrongWrapperScope[$wrapper] = ([string]$badWrongWrapperScope[$wrapper]).Replace("-Scope 'project'", "-Scope 'global'")
    Assert-Rejected $badWrongWrapperScope $version 'PRE_TAG' 'DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID' 'REGRESSION_REJECTS_WRONG_WRAPPER_SCOPE'

    $badForeignWrapperSource = Copy-ReleaseDocs $docs
    $wrapper = 'uninstall/global/codex.ps1'
    $badForeignWrapperSource[$wrapper] = ([string]$badForeignWrapperSource[$wrapper]).Replace(
        'https://raw.githubusercontent.com/Edulynch/OpenCode-OlympusAgents/', 'https://example.invalid/')
    Assert-Rejected $badForeignWrapperSource $version 'PRE_TAG' 'DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID' 'REGRESSION_REJECTS_FOREIGN_WRAPPER_LAUNCHER'

    $badStaleTagLauncher = Copy-ReleaseDocs $docs
    $wrapper = 'uninstall/global/all.ps1'
    $badStaleTagLauncher[$wrapper] = ([string]$badStaleTagLauncher[$wrapper]).Replace(
        '/' + $version + '/scripts/launch-latest.ps1', '/v0.4.6/scripts/launch-latest.ps1')
    Assert-Rejected $badStaleTagLauncher $version 'PRE_TAG' 'DOC_WRAPPER_IMMUTABLE_SOURCE_INVALID' 'REGRESSION_REJECTS_STALE_LAUNCHER_TAG'

    $badForeignInstaller = Copy-ReleaseDocs $docs
    Set-ReadmeInstallCommand $badForeignInstaller $fastInstallCommand 'irm https://example.invalid/install-olympus.ps1 | iex'
    Assert-Rejected $badForeignInstaller $version 'PRE_TAG' 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID' 'REGRESSION_REJECTS_FOREIGN_INSTALLER_URL'

    $badExtraForeignInstaller = Copy-ReleaseDocs $docs
    $extraForeignInstallerCommand = 'irm https://example.invalid/install-olympus.ps1 | iex'
    Add-ReadmeInstallCommand $badExtraForeignInstaller $extraForeignInstallerCommand
    $extraForeignInstallerLines = @(Get-PowerShellCodeBlockLines ([string]$badExtraForeignInstaller['README.md']) |
        Where-Object { $_.Trim() -ceq $extraForeignInstallerCommand })
    if ($extraForeignInstallerLines.Count -ne 1) {
        throw 'REGRESSION_MUTATION_SETUP_FAILED: extra foreign installer was not inserted into a PowerShell code block.'
    }
    Assert-Rejected $badExtraForeignInstaller $version 'PRE_TAG' 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID' 'REGRESSION_REJECTS_EXTRA_FOREIGN_INSTALLER'

    $badExtraExecutable = Copy-ReleaseDocs $docs
    $extraExecutableCommand = 'pwsh -File ./install-olympus.ps1'
    Add-ReadmeInstallCommand $badExtraExecutable $extraExecutableCommand
    $extraExecutableLines = @(Get-PowerShellCodeBlockLines ([string]$badExtraExecutable['README.md']) |
        Where-Object { $_.Trim() -ceq $extraExecutableCommand })
    if ($extraExecutableLines.Count -ne 1) {
        throw 'REGRESSION_MUTATION_SETUP_FAILED: extra executable command was not inserted into a PowerShell code block.'
    }
    Assert-Rejected $badExtraExecutable $version 'PRE_TAG' 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID' 'REGRESSION_REJECTS_EXTRA_EXECUTABLE_COMMAND'

    $badIndirectScriptBlock = Copy-ReleaseDocs $docs
    $indirectScriptBlockCommand = "& ([scriptblock]::Create((irm '$($tagBase)install-olympus.ps1'))) -Global -Harness all"
    Add-ReadmeInstallCommand $badIndirectScriptBlock $indirectScriptBlockCommand
    $indirectScriptBlockLines = @(Get-PowerShellCodeBlockLines ([string]$badIndirectScriptBlock['README.md']) |
        Where-Object { $_.Trim() -ceq $indirectScriptBlockCommand })
    if ($indirectScriptBlockLines.Count -ne 1) {
        throw 'REGRESSION_MUTATION_SETUP_FAILED: indirect ScriptBlock.Create command was not inserted into a PowerShell code block.'
    }
    Assert-Rejected $badIndirectScriptBlock $version 'PRE_TAG' 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID' 'REGRESSION_REJECTS_INDIRECT_SCRIPTBLOCK_BOOTSTRAP'

    $badThirdRemoteExecution = Copy-ReleaseDocs $docs
    $thirdRemoteExecutionCommand = 'iwr https://example.invalid/install-olympus.ps1 | iex'
    $badThirdRemoteExecution['README.md'] = ([string]$badThirdRemoteExecution['README.md']) + "`n## Alternative setup`n`n" + '```powershell' + "`n$thirdRemoteExecutionCommand`n" + '```' + "`n"
    $alternativeSection = [regex]::Match(
        [string]$badThirdRemoteExecution['README.md'],
        '(?ms)^##[ \t]+Alternative setup[ \t]*\r?\n(?<body>.*?)(?=^##[ \t]+|\z)'
    )
    $thirdRemoteExecutionLines = @()
    if ($alternativeSection.Success) {
        $thirdRemoteExecutionLines = @(Get-PowerShellCodeBlockLines $alternativeSection.Groups['body'].Value |
            Where-Object { $_.Trim() -ceq $thirdRemoteExecutionCommand })
    }
    $fastInstallFixture = Get-PrimaryReadmeInstallSection ([string]$badThirdRemoteExecution['README.md'])
    $fastUninstallFixture = Get-PrimaryReadmeUninstallSection ([string]$badThirdRemoteExecution['README.md'])
    $fastSectionContainsThirdRemote = $false
    foreach ($fastFixture in @($fastInstallFixture, $fastUninstallFixture)) {
        if ($fastFixture.Success -and @(Get-PowerShellCodeBlockLines $fastFixture.Groups['body'].Value |
                Where-Object { $_.Trim() -ceq $thirdRemoteExecutionCommand }).Count -gt 0) {
            $fastSectionContainsThirdRemote = $true
        }
    }
    if (-not $alternativeSection.Success -or $thirdRemoteExecutionLines.Count -ne 1 -or $fastSectionContainsThirdRemote) {
        throw 'REGRESSION_MUTATION_SETUP_FAILED: third remote execution must be in a PowerShell block outside both Fast sections.'
    }
    Assert-Rejected $badThirdRemoteExecution $version 'PRE_TAG' 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID' 'REGRESSION_REJECTS_THIRD_REMOTE_EXECUTION_OUTSIDE_FAST'

    $badDirectInstallerOutsideFast = Copy-ReleaseDocs $docs
    $directInstallerOutsideFastCommand = 'pwsh -NoProfile -File ./install-olympus.ps1 -Project -Here -Harness all'
    $badDirectInstallerOutsideFast['README.md'] = ([string]$badDirectInstallerOutsideFast['README.md']) + "`n## Alternative setup`n`n" + '```powershell' + "`n$directInstallerOutsideFastCommand`n" + '```' + "`n"
    $outsideFastSection = [regex]::Match(
        [string]$badDirectInstallerOutsideFast['README.md'],
        '(?ms)^##[ \t]+Alternative setup[ \t]*\r?\n(?<body>.*?)(?=^##[ \t]+|\z)'
    )
    $outsideFastLines = @()
    if ($outsideFastSection.Success) {
        $outsideFastLines = @(Get-PowerShellCodeBlockLines $outsideFastSection.Groups['body'].Value |
            Where-Object { $_.Trim() -ceq $directInstallerOutsideFastCommand })
    }
    if (-not $outsideFastSection.Success -or $outsideFastLines.Count -ne 1) {
        throw 'REGRESSION_MUTATION_SETUP_FAILED: direct installer was not placed in a PowerShell block under another heading.'
    }
    Assert-Rejected $badDirectInstallerOutsideFast $version 'PRE_TAG' 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID' 'REGRESSION_REJECTS_DIRECT_INSTALLER_OUTSIDE_FAST'

    $descriptiveRemoteMention = Copy-ReleaseDocs $docs
    $descriptiveRemoteMention['README.md'] = ([string]$descriptiveRemoteMention['README.md']) + "`n## Command references`n`nThe phrase iwr https://example.invalid/install-olympus.ps1 | iex is a non-executable warning; see [Invoke-WebRequest reference](https://learn.microsoft.com/powershell/module/microsoft.powershell.utility/invoke-webrequest).`n`n## Commented example`n`n" + '```powershell' + "`n# iwr https://example.invalid/install-olympus.ps1 | iex`n" + '```' + "`n"
    if (-not ([string]$descriptiveRemoteMention['README.md']).Contains('non-executable warning') -or
        -not ([string]$descriptiveRemoteMention['README.md']).Contains('[Invoke-WebRequest reference]')) {
        throw 'REGRESSION_MUTATION_SETUP_FAILED: descriptive command and documentation link were not added.'
    }
    $descriptiveRemoteErrors = @(Get-DocumentationErrors $descriptiveRemoteMention $version 'PRE_TAG')
    if ($descriptiveRemoteErrors -contains 'DOC_README_IMMUTABLE_ENTRYPOINT_INVALID') {
        throw 'REGRESSION_FALSE_POSITIVE: descriptive command text was treated as executable PowerShell.'
    }
    Write-Output 'REGRESSION_ACCEPTS_DESCRIPTIVE_REMOTE_COMMAND_MENTION PASS'

    $badDirectOptions = Copy-ReleaseDocs $docs
    $badDirectOptions['docs/INSTALLATION.md'] = ([string]$badDirectOptions['docs/INSTALLATION.md']).Replace('& $install -Global -Harness all', '& $install -Global')
    Assert-Rejected $badDirectOptions $version 'POST_TAG' 'DOC_INSTALLATION_DIRECT_OPTIONS_INVALID' 'REGRESSION_REJECTS_INCOMPLETE_DIRECT_HARNESS_OPTIONS'

    $badMissingInputExplanation = Copy-ReleaseDocs $docs
    $missingInputSentences = @(
        'If a required value is missing and interactive input is unavailable, it exits with `ARGUMENTS_REQUIRED` instead of waiting for input.',
        'Without a terminal or other usable interactive input, incomplete selections fail with `ARGUMENTS_REQUIRED`.'
    )
    $missingInputGuide = [string]$badMissingInputExplanation['docs/INSTALLATION.md']
    foreach ($sentence in $missingInputSentences) {
        if (-not $missingInputGuide.Contains($sentence)) { throw 'REGRESSION_MUTATION_SETUP_FAILED: expected missing-input explanation was not found.' }
        $missingInputGuide = $missingInputGuide.Replace($sentence, '')
    }
    $badMissingInputExplanation['docs/INSTALLATION.md'] = $missingInputGuide
    Assert-Rejected $badMissingInputExplanation $version 'POST_TAG' 'DOC_INSTALLATION_DIRECT_OPTIONS_INVALID' 'REGRESSION_REJECTS_MISSING_INPUT_ARGUMENTS_REQUIRED_EXPLANATION'

    $badInvalidSelectorExplanation = Copy-ReleaseDocs $docs
    $invalidSelectorSentences = @(
        'Supply `-Project` and `-Here` together.',
        '`-ProjectPath`, `-Global`, and the `-Project -Here` pair are mutually exclusive; contradictory choices are rejected. Do not mix those scope selectors.',
        'A lone `-Project` or `-Here` is invalid; use both.',
        'PowerShell also rejects combinations such as `-Global -ProjectPath ...`.'
    )
    $invalidSelectorGuide = [string]$badInvalidSelectorExplanation['docs/INSTALLATION.md']
    foreach ($sentence in $invalidSelectorSentences) {
        if (-not $invalidSelectorGuide.Contains($sentence)) { throw 'REGRESSION_MUTATION_SETUP_FAILED: expected invalid-selector explanation was not found.' }
        $invalidSelectorGuide = $invalidSelectorGuide.Replace($sentence, '')
    }
    $badInvalidSelectorExplanation['docs/INSTALLATION.md'] = $invalidSelectorGuide
    Assert-Rejected $badInvalidSelectorExplanation $version 'POST_TAG' 'DOC_INSTALLATION_DIRECT_OPTIONS_INVALID' 'REGRESSION_REJECTS_INVALID_INCOMPLETE_CONTRADICTORY_SELECTOR_EXPLANATION'

    $badReleaseProvenance = Copy-ReleaseDocs $docs
    $officialReleaseApi = 'https://api.github.com/repos/Edulynch/OpenCode-OlympusAgents/releases/latest'
    $badReleaseProvenance['docs/INSTALLATION.md'] = ([string]$badReleaseProvenance['docs/INSTALLATION.md']).Replace(
        $officialReleaseApi, 'https://api.github.com/repos/example/OtherProject/releases/latest')
    Assert-Rejected $badReleaseProvenance $version 'POST_TAG' 'DOC_INSTALLATION_RELEASE_PREREQUISITE_INVALID' 'REGRESSION_REJECTS_FOREIGN_RELEASE_METADATA_SOURCE'

    Write-Output "TAG-TRANSITION-STABILITY QUALIFICATION: PASS ($version; deterministic static semantic checks; no tag or GitHub Release created)"
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'TAG-TRANSITION-STABILITY QUALIFICATION: FAIL'
    exit 1
}
