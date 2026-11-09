[CmdletBinding()]
param([ValidateSet('Both','Offline','Runtime')][string]$QualificationSlice = 'Both')

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$WorkRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'tests/.phase4c-work'))
$Bootstrap = Join-Path $RepoRoot 'scripts/bootstrap.ps1'
$Utf8 = [Text.UTF8Encoding]::new($false)
$RunId = [Guid]::NewGuid().ToString('N')
$RunRoot = Join-Path $WorkRoot ('run-' + $RunId)
$Results = [System.Collections.Generic.List[object]]::new()
$OriginalPath = [Environment]::GetEnvironmentVariable('PATH','Process')
$MockBin = $null
$ManagedPaths = @(
    'opencode.jsonc',
    '.opencode/agents/kael.md', '.opencode/agents/veyra.md',
    '.opencode/agents/orin.md', '.opencode/agents/kovan.md',
    '.opencode/agents/nox.md', '.opencode/agents/vera.md',
    '.opencode/agents/thales.md', '.opencode/agents/atlas.md', '.opencode/agents/argus.md', '.opencode/agents/talos.md', '.opencode/agents/helios.md',
    '.opencode/plugins/olympus-activity/activity.ts', '.opencode/plugins/olympus-activity/tui.tsx',
    '.opencode/scripts/worktree-setup.ps1',
    '.opencode/orchestrator-install.json'
)

$ReparseTagCache = @{}

function Assert-Condition {
    param([bool]$Condition, [string]$Message, [string]$Classification = 'HARNESS_BUG')
    if (-not $Condition) { throw ($Classification + '|' + $Message) }
}

function Normalize-Path([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    if (-not [string]::Equals($full, $root, [StringComparison]::OrdinalIgnoreCase)) {
        $full = $full.TrimEnd([char[]]@('\','/'))
    }
    return $full
}

function Get-ReparseTag([string]$Path) {
    $full = Normalize-Path $Path
    if ($ReparseTagCache.ContainsKey($full)) { return [uint32]$ReparseTagCache[$full] }
    $fsutil = Get-Command fsutil.exe -ErrorAction SilentlyContinue
    if (-not $fsutil) { throw ('REPARSE_PATH_UNVERIFIABLE: fsutil.exe is unavailable for ' + $full) }
    $output = & $fsutil.Source reparsepoint query $full 2>&1
    $exitCode = $LASTEXITCODE
    $match = [regex]::Match(($output | Out-String), '(?i)0x([0-9a-f]{8})')
    if ($exitCode -ne 0 -or -not $match.Success) {
        throw ('REPARSE_PATH_UNVERIFIABLE: cannot read the reparse tag for ' + $full)
    }
    $tag = [Convert]::ToUInt32($match.Groups[1].Value, 16)
    $ReparseTagCache[$full] = $tag
    return $tag
}

function Resolve-PhysicalPath([string]$Path) {
    $full = Normalize-Path $Path
    $volumeRoot = [IO.Path]::GetPathRoot($full)
    $parts = $full.Substring($volumeRoot.Length).Split(
        [char[]]@([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar),
        [StringSplitOptions]::RemoveEmptyEntries)
    $current = $volumeRoot
    for ($i = 0; $i -lt $parts.Count; $i++) {
        $next = Join-Path $current $parts[$i]
        $entry = Get-Item -LiteralPath $next -Force -ErrorAction SilentlyContinue
        if ($null -eq $entry) {
            $remaining = @()
            for ($j = $i; $j -lt $parts.Count; $j++) { $remaining += $parts[$j] }
            $current = Join-Path $current ($remaining -join [IO.Path]::DirectorySeparatorChar)
            break
        }
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $tag = Get-ReparseTag $next
            if (($tag -band [uint32]0x20000000) -ne 0) {
                try { $resolved = $entry.ResolveLinkTarget($true) }
                catch { throw ('REPARSE_PATH_UNVERIFIABLE: cannot resolve ' + $next + ': ' + $_.Exception.Message) }
                if ($null -eq $resolved) { throw ('REPARSE_PATH_UNVERIFIABLE: no redirect target for ' + $next) }
                $current = Normalize-Path $resolved.FullName
            } else {
                # Cloud Files and other non-name-surrogate reparse tags annotate files;
                # they do not redirect path traversal.
                $current = Normalize-Path $entry.FullName
            }
        } else {
            $current = Normalize-Path $entry.FullName
        }
    }
    return Normalize-Path $current
}

function Test-PhysicalWithin([string]$Candidate, [string]$Base, [switch]$AllowEqual) {
    $candidatePath = Resolve-PhysicalPath $Candidate
    $basePath = Resolve-PhysicalPath $Base
    if ([string]::Equals($candidatePath, $basePath, [StringComparison]::OrdinalIgnoreCase)) { return [bool]$AllowEqual }
    $prefix = if ($basePath.EndsWith([IO.Path]::DirectorySeparatorChar)) { $basePath } else { $basePath + [IO.Path]::DirectorySeparatorChar }
    return $candidatePath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)
}

function Full-Path([string]$Path) { return Normalize-Path $Path }

function Assert-Descendant([string]$Candidate, [string]$Base, [string]$Classification = 'HARNESS_BUG') {
    Assert-Condition (Test-PhysicalWithin $Candidate $Base) ('Path is not physically inside the authorized base: ' + (Resolve-PhysicalPath $Candidate)) $Classification
}

function Invoke-Git {
    param([string]$Repo, [string[]]$GitArgs)
    $output = & git -C $Repo @GitArgs 2>&1
    $code = $LASTEXITCODE
    $text = ($output | Out-String).Trim()
    if ($code -ne 0) { throw ('HARNESS_BUG|Fixture Git command failed (' + ($GitArgs -join ' ') + '): ' + $text) }
    return $text
}

function New-ScenarioHome([string]$Name) {
    $scenarioDir = Join-Path $RunRoot $Name
    Assert-Descendant $scenarioDir $RunRoot
    Assert-Condition (-not (Test-Path -LiteralPath $scenarioDir)) ('Scenario path already exists: ' + $scenarioDir)
    [IO.Directory]::CreateDirectory($scenarioDir) | Out-Null
    [IO.File]::WriteAllText((Join-Path $scenarioDir '.phase4c-owner'), $RunId, $Utf8)
    return $scenarioDir
}

function New-CleanRepo {
    param([string]$ScenarioHome, [string]$RepoName, [System.Collections.IDictionary]$Files)
    $repo = Join-Path $ScenarioHome $RepoName
    Assert-Descendant $repo $ScenarioHome
    [IO.Directory]::CreateDirectory($repo) | Out-Null
    if (-not $Files.Contains('.gitignore')) {
        $Files['.gitignore'] = '.serena/' + [Environment]::NewLine
    } elseif ([string]$Files['.gitignore'] -notmatch '(?m)^[.]serena/?$') {
        $Files['.gitignore'] = [string]$Files['.gitignore'] + [Environment]::NewLine + '.serena/' + [Environment]::NewLine
    }
    foreach ($relative in $Files.Keys) {
        $relativePath = [string]$relative
        Assert-Condition (-not [IO.Path]::IsPathRooted($relativePath)) ('Fixture path must be relative: ' + $relativePath)
        Assert-Condition ($relativePath -notmatch '(^|[\\/])\.\.([\\/]|$)') ('Fixture traversal rejected: ' + $relativePath)
        $path = Join-Path $repo ($relativePath -replace '/', [IO.Path]::DirectorySeparatorChar)
        Assert-Descendant $path $repo
        [IO.Directory]::CreateDirectory((Split-Path -Parent $path)) | Out-Null
        [IO.File]::WriteAllText($path, [string]$Files[$relative], $Utf8)
    }
    [void](Invoke-Git $repo @('init', '--quiet'))
    [void](Invoke-Git $repo @('config', 'user.name', 'Phase 4C Qualification'))
    [void](Invoke-Git $repo @('config', 'user.email', 'phase4c-qualification@example.invalid'))
    $addArgs = @('add', '--') + @($Files.Keys | ForEach-Object { [string]$_ })
    [void](Invoke-Git $repo $addArgs)
    [void](Invoke-Git $repo @('commit', '--quiet', '-m', 'qualification fixture'))
    $status = Invoke-Git $repo @('status', '--porcelain', '--untracked-files=all')
    Assert-Condition (-not $status) ('Fixture repository is not clean after commit: ' + $status)
    return $repo
}

function Invoke-Bootstrap {
    param([string]$Target, [switch]$DryRun)
    $pwsh = Get-Command pwsh -ErrorAction Stop
    $cliArgs = @('-NoLogo', '-NoProfile', '-File', $Bootstrap, '-Target', $Target)
    if ($DryRun) { $cliArgs += '-DryRun' }
    Push-Location $RepoRoot
    try {
        $output = & $pwsh.Source @cliArgs 2>&1
        $code = $LASTEXITCODE
    } finally { Pop-Location }
    [pscustomobject]@{ ExitCode = $code; Text = ($output | Out-String) }
}

function Assert-BootstrapError {
    param($Result, [string]$Code)
    Assert-Condition ($Result.ExitCode -ne 0) ('Expected bootstrap error ' + $Code + ', got exit 0. Output: ' + $Result.Text) 'BOOTSTRAP_BUG'
    Assert-Condition ($Result.Text -match [regex]::Escape($Code)) ('Expected bootstrap error ' + $Code + '. Output: ' + $Result.Text) 'BOOTSTRAP_BUG'
}

function Assert-NoInstallFiles([string]$Repo) {
    foreach ($relative in $ManagedPaths) {
        $path = Join-Path $Repo ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
        Assert-Condition (-not (Test-Path -LiteralPath $path)) ('Unexpected bootstrap write: ' + $relative) 'BOOTSTRAP_BUG'
    }
}

function Get-Hash([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($Path)))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Get-Agent($Agents, [string]$Id) {
    $matches = @($Agents | Where-Object { $_.id -eq $Id })
    Assert-Condition ($matches.Count -eq 1) ('Expected exactly one effective agent: ' + $Id) 'BOOTSTRAP_BUG'
    return $matches[0]
}

function Has-Rule($Agent, [string]$Action, [string]$Resource, [string]$Effect) {
    return @($Agent.permissions | Where-Object { $_.action -eq $Action -and $_.resource -eq $Resource -and $_.effect -eq $Effect }).Count -gt 0
}

function Get-OpenCodeDiagnostics([string]$Repo) {
    Push-Location $Repo
    try {
        $configOutput = & opencode debug config 2>&1
        $configCode = $LASTEXITCODE
        $agentOutput = & opencode debug agents 2>&1
        $agentCode = $LASTEXITCODE
    } finally { Pop-Location }
    $configText = ($configOutput | Out-String)
    $agentText = ($agentOutput | Out-String)
    Assert-Condition ($configCode -eq 0) ('opencode debug config failed: ' + $configText) 'OPENCODE_RUNTIME_ISSUE'
    Assert-Condition ($agentCode -eq 0) ('opencode debug agents failed: ' + $agentText) 'OPENCODE_RUNTIME_ISSUE'
    try { $agents = $agentText | ConvertFrom-Json -Depth 100 }
    catch { throw ('OPENCODE_RUNTIME_ISSUE|debug agents did not return JSON: ' + $_.Exception.Message) }
    try { $configEntries = $configText | ConvertFrom-Json -Depth 100 }
    catch { throw ('OPENCODE_RUNTIME_ISSUE|debug config output is not JSON: ' + $_.Exception.Message) }
    $expectedConfig = Full-Path (Join-Path $Repo 'opencode.jsonc')
    $configPaths = @($configEntries | ForEach-Object { if ($_.path) { Full-Path ([string]$_.path) } })
    $matchingConfig = @($configPaths | Where-Object { [string]::Equals($_, $expectedConfig, [StringComparison]::OrdinalIgnoreCase) })
    Assert-Condition ($matchingConfig.Count -gt 0) 'debug config did not load the installed target project config.' 'BOOTSTRAP_BUG'
    return [pscustomobject]@{ Config = $configText; AgentText = $agentText; Agents = @($agents) }
}

function Assert-ModelMapping($Agents) {
    $expected = [ordered]@{
        'kael' = @('gpt-6.1-sol', 'high', 'primary')
        'thales' = @('gpt-6.1-sol', 'xhigh', 'subagent')
        'veyra' = @('gpt-6-luna', 'max', 'subagent')
        'orin' = @('gpt-6-luna', 'max', 'subagent')
        'kovan' = @('gpt-6-luna', 'max', 'subagent')
        'nox' = @('gpt-6-luna', 'max', 'subagent')
        'vera' = @('gpt-6-luna', 'max', 'subagent')
    }
    foreach ($id in $expected.Keys) {
        $agent = Get-Agent $Agents $id
        $model = $expected[$id][0]; $variant = $expected[$id][1]; $mode = $expected[$id][2]
        Assert-Condition ($agent.model.id -eq $model -and $agent.model.variant -eq $variant -and $agent.mode -eq $mode) ('Effective model/mode mismatch for ' + $id) 'BOOTSTRAP_BUG'
    }
}

function Assert-Installed([string]$Repo, [string]$ExpectedStatus) {
    $result = Invoke-Bootstrap $Repo
    Assert-Condition ($result.ExitCode -eq 0) ('Bootstrap failed: ' + $result.Text) 'BOOTSTRAP_BUG'
    Assert-Condition ($result.Text -match ('(?m)^' + [regex]::Escape($ExpectedStatus) + '\s*$')) ('Expected status ' + $ExpectedStatus + '. Output: ' + $result.Text) 'BOOTSTRAP_BUG'
    if ($QualificationSlice -eq 'Offline') { return $null }
    $diagnostics = Get-OpenCodeDiagnostics $Repo
    Assert-ModelMapping $diagnostics.Agents
    return $diagnostics
}

function Enable-OfflineOpenCodeStub {
    $script:MockBin = Join-Path $RunRoot 'mock-opencode'
    [IO.Directory]::CreateDirectory($script:MockBin) | Out-Null
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'tests/release/fixtures/opencode.ps1') -Destination (Join-Path $script:MockBin 'opencode.ps1')
    $pwsh = Join-Path $PSHOME 'pwsh.exe'
    $wrapper = "@echo off`r`n`"$pwsh`" -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
    [IO.File]::WriteAllText((Join-Path $script:MockBin 'opencode.cmd'), $wrapper, [Text.Encoding]::ASCII)
    $windowsApps = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'
    $parts = @($OriginalPath -split [regex]::Escape([IO.Path]::PathSeparator) | Where-Object {
        $_ -and $_.Trim('"') -ine $windowsApps -and $_.Trim('"') -ine $PSHOME
    })
    $env:PATH = (@($script:MockBin,$PSHOME) + $parts) -join [IO.Path]::PathSeparator
}

function Run-Scenario([string]$Id, [scriptblock]$Body) {
    $runtimeScenarios = @('P4C-2','P4C-11','P4C-12','P4C-14',
        'M-CONTEXTUAL-MAINTENANCE', 'M-CLEAN-BREAK-RETIREMENT')
    if ($QualificationSlice -eq 'Runtime' -and $Id -notin $runtimeScenarios) { return }
    try {
        & $Body
        $Results.Add([pscustomobject]@{ Id = $Id; Status = 'PASS'; Classification = ''; Evidence = '' })
    } catch {
        $message = $_.Exception.Message
        $classification = 'HARNESS_BUG'; $evidence = $message
        if ($message -match '^(BOOTSTRAP_BUG|HARNESS_BUG|ENVIRONMENT_LIMITATION|OPENCODE_RUNTIME_ISSUE|TEST_EXPECTATION_BUG)\|(.*)$') {
            $classification = $Matches[1]; $evidence = $Matches[2]
        }
        $Results.Add([pscustomobject]@{ Id = $Id; Status = 'FAIL'; Classification = $classification; Evidence = $evidence })
    }
}

try {
    Assert-Condition ([IO.File]::Exists($Bootstrap)) 'scripts/bootstrap.ps1 is missing.'
    Assert-Condition ($null -ne (Get-Command git -ErrorAction SilentlyContinue)) 'Git is unavailable.' 'ENVIRONMENT_LIMITATION'
    if ($QualificationSlice -ne 'Offline') {
        Assert-Condition ($null -ne (Get-Command opencode -ErrorAction SilentlyContinue)) 'OpenCode is unavailable.' 'ENVIRONMENT_LIMITATION'
    }
    Assert-Condition ($null -ne (Get-Command pwsh -ErrorAction SilentlyContinue)) 'PowerShell 7 is unavailable.' 'ENVIRONMENT_LIMITATION'
    $gitRoot = Full-Path (Invoke-Git $RepoRoot @('rev-parse', '--show-toplevel'))
    Assert-Condition ([string]::Equals($gitRoot, (Full-Path $RepoRoot), [StringComparison]::OrdinalIgnoreCase)) 'Harness is not running in the orchestrator Git repository.'
    Assert-Descendant $WorkRoot $RepoRoot
    [IO.Directory]::CreateDirectory($WorkRoot) | Out-Null
    Assert-Descendant $WorkRoot $RepoRoot
    [IO.Directory]::CreateDirectory($RunRoot) | Out-Null
    Assert-Descendant $RunRoot $WorkRoot
    if ($QualificationSlice -eq 'Offline') { Enable-OfflineOpenCodeStub }

    Run-Scenario 'P4C-1' {
        $scenarioDir = New-ScenarioHome 'p4c-01'
        $files = [ordered]@{ 'README.md' = 'dry-run fixture' + [Environment]::NewLine; 'package.json' = '{"packageManager":"npm@10","scripts":{"test":"node test.js"}}' + [Environment]::NewLine; 'package-lock.json' = '{}' + [Environment]::NewLine }
        $repo = New-CleanRepo $scenarioDir 'target' $files
        $result = Invoke-Bootstrap $repo -DryRun
        Assert-Condition ($result.ExitCode -eq 0) ('Dry run failed: ' + $result.Text) 'BOOTSTRAP_BUG'
        Assert-Condition ($result.Text -match '(?m)^DRY_RUN_READY\s*$') 'Dry-run status missing.' 'BOOTSTRAP_BUG'
        Assert-Condition ($result.Text -match '(?m)^node\s*$') 'Node stack not reported.' 'BOOTSTRAP_BUG'
        Assert-Condition ($result.Text -match 'npm test') 'Relevant Node command not planned.' 'BOOTSTRAP_BUG'
        Assert-Condition ($result.Text -match 'opencode\.jsonc') 'Planned file list missing.' 'BOOTSTRAP_BUG'
        Assert-NoInstallFiles $repo
        $dirty = Invoke-Git $repo @('status', '--porcelain', '--untracked-files=all')
        Assert-Condition (-not $dirty) ('Dry run modified target Git state: ' + $dirty) 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-2' {
        $scenarioDir = New-ScenarioHome 'p4c-02'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'fresh install fixture' + [Environment]::NewLine })
        [void](Assert-Installed $repo 'READY')
        if ($QualificationSlice -ne 'Runtime') {
        foreach ($relative in $ManagedPaths) { Assert-Condition (Test-Path -LiteralPath (Join-Path $repo ($relative -replace '/', [IO.Path]::DirectorySeparatorChar))) ('Installed file missing: ' + $relative) 'BOOTSTRAP_BUG' }
        }
    }

    Run-Scenario 'P4C-3' {
        $scenarioDir = New-ScenarioHome 'p4c-03'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'idempotency fixture' + [Environment]::NewLine })
        $first = Invoke-Bootstrap $repo
        Assert-Condition ($first.ExitCode -eq 0 -and $first.Text -match '(?m)^READY\s*$') ('Initial install failed: ' + $first.Text) 'BOOTSTRAP_BUG'
        $before = @{}
        foreach ($relative in $ManagedPaths) { $before[$relative] = Get-Hash (Join-Path $repo ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)) }
        $second = Invoke-Bootstrap $repo
        Assert-Condition ($second.ExitCode -eq 0 -and $second.Text -match '(?m)^NO_CHANGES\s*$') ('Second run was not NO_CHANGES: ' + $second.Text) 'BOOTSTRAP_BUG'
        foreach ($relative in $ManagedPaths) { Assert-Condition ($before[$relative] -eq (Get-Hash (Join-Path $repo ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)))) ('Idempotent run changed ' + $relative) 'BOOTSTRAP_BUG' }
        $nox = [IO.File]::ReadAllText((Join-Path $repo '.opencode/agents/nox.md'))
        Assert-Condition ($nox -eq [IO.File]::ReadAllText((Join-Path $RepoRoot '.opencode/agents/nox.md'))) 'Nox template was modified by bootstrap.' 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-4' {
        $scenarioDir = New-ScenarioHome 'p4c-04'
        $package = '{"packageManager":"npm@10","scripts":{"test":"node test.js","lint":"eslint .","build":"node build.js","deploy":"node deploy.js"}}' + [Environment]::NewLine
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'node scripts fixture' + [Environment]::NewLine; 'package.json' = $package; 'package-lock.json' = '{}' + [Environment]::NewLine })
        $result = Invoke-Bootstrap $repo
        Assert-Condition ($result.ExitCode -eq 0 -and $result.Text -match '(?m)^READY\s*$') ('Node install failed: ' + $result.Text) 'BOOTSTRAP_BUG'
        foreach ($expected in @('npm test', 'npm run lint', 'npm run build')) { Assert-Condition ($result.Text.Contains($expected)) ('Expected Node suggestion missing: ' + $expected) 'BOOTSTRAP_BUG' }
        $manifest = [IO.File]::ReadAllText((Join-Path $repo '.opencode/orchestrator-install.json')) | ConvertFrom-Json
        Assert-Condition (@($manifest.validation_commands).Count -eq 3 -and @($manifest.validation_commands | Where-Object { $_ -eq 'npm run deploy' }).Count -eq 0) 'Node validation suggestions are incorrect.' 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-5' {
        $scenarioDir = New-ScenarioHome 'p4c-05'
        $caseA = New-CleanRepo $scenarioDir 'case-a' ([ordered]@{ 'README.md' = 'pnpm case' + [Environment]::NewLine; 'package.json' = '{"scripts":{"test":"node test.js"}}' + [Environment]::NewLine; 'pnpm-lock.yaml' = 'lockfileVersion: 9' + [Environment]::NewLine })
        $resultA = Invoke-Bootstrap $caseA
        Assert-Condition ($resultA.ExitCode -eq 0 -and $resultA.Text -match '(?m)^READY\s*$') ('Clear package manager case failed: ' + $resultA.Text) 'BOOTSTRAP_BUG'
        Assert-Condition ($resultA.Text -match '(?m)^pnpm\s*$') 'pnpm lockfile was not selected.' 'BOOTSTRAP_BUG'
        if (Get-Command pnpm -ErrorAction SilentlyContinue) { Assert-Condition ($resultA.Text.Contains('pnpm test')) 'pnpm test was not suggested.' 'BOOTSTRAP_BUG' }
        else { Assert-Condition ($resultA.Text -match 'VALIDATION_TOOL_UNAVAILABLE: pnpm') 'Missing pnpm was not reported.' 'BOOTSTRAP_BUG' }
        $caseB = New-CleanRepo $scenarioDir 'case-b' ([ordered]@{ 'README.md' = 'conflicting lockfiles' + [Environment]::NewLine; 'package.json' = '{"packageManager":"npm@10","scripts":{"test":"node test.js"}}' + [Environment]::NewLine; 'package-lock.json' = '{}' + [Environment]::NewLine; 'pnpm-lock.yaml' = 'lockfileVersion: 9' + [Environment]::NewLine })
        $resultB = Invoke-Bootstrap $caseB
        Assert-BootstrapError $resultB 'AMBIGUOUS_PACKAGE_MANAGER'
        Assert-NoInstallFiles $caseB
    }

    Run-Scenario 'P4C-6' {
        $scenarioDir = New-ScenarioHome 'p4c-06'
        $files = [ordered]@{ 'README.md' = 'multi-stack fixture' + [Environment]::NewLine; 'package.json' = '{"packageManager":"npm@10","scripts":{"test":"node test.js","publish":"node publish.js"}}' + [Environment]::NewLine; 'package-lock.json' = '{}' + [Environment]::NewLine; 'pyproject.toml' = '[tool.pytest.ini_options]' + [Environment]::NewLine + 'testpaths = ["tests"]' + [Environment]::NewLine }
        $repo = New-CleanRepo $scenarioDir 'target' $files
        $result = Invoke-Bootstrap $repo
        Assert-Condition ($result.ExitCode -eq 0 -and $result.Text -match '(?m)^READY\s*$') ('Multi-stack install failed: ' + $result.Text) 'BOOTSTRAP_BUG'
        Assert-Condition ($result.Text -match '(?m)^node\s*$' -and $result.Text -match '(?m)^python\s*$') 'Both stacks were not detected.' 'BOOTSTRAP_BUG'
        if (Get-Command npm -ErrorAction SilentlyContinue) { Assert-Condition ($result.Text.Contains('npm test')) 'Node validation missing from union.' 'BOOTSTRAP_BUG' }
        else { Assert-Condition ($result.Text -match 'VALIDATION_TOOL_UNAVAILABLE: npm') 'Unavailable npm not reported.' 'BOOTSTRAP_BUG' }
        if (Get-Command pytest -ErrorAction SilentlyContinue) { Assert-Condition ($result.Text.Contains('pytest')) 'Python validation missing from union.' 'BOOTSTRAP_BUG' }
        else { Assert-Condition ($result.Text -match 'VALIDATION_TOOL_UNAVAILABLE: pytest') 'Unavailable pytest not reported.' 'BOOTSTRAP_BUG' }
        $manifest = [IO.File]::ReadAllText((Join-Path $repo '.opencode/orchestrator-install.json')) | ConvertFrom-Json
        Assert-Condition (@($manifest.validation_commands | Where-Object { $_ -eq 'npm run publish' }).Count -eq 0) 'Unrelated script entered default validation suggestions.' 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-7' {
        $scenarioDir = New-ScenarioHome 'p4c-07'
        $foreign = '{"default_agent":"build","foreign":true}' + [Environment]::NewLine
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'conflict fixture' + [Environment]::NewLine; 'opencode.json' = $foreign })
        $path = Join-Path $repo 'opencode.json'; $before = Get-Hash $path
        $result = Invoke-Bootstrap $repo
        Assert-BootstrapError $result 'INSTALL_CONFLICT'
        Assert-Condition ((Get-Hash $path) -eq $before) 'Foreign configuration was overwritten.' 'BOOTSTRAP_BUG'
        Assert-NoInstallFiles $repo
    }

    Run-Scenario 'P4C-8' {
        $scenarioDir = New-ScenarioHome 'p4c-08'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'clean fixture' + [Environment]::NewLine })
        $userFile = Join-Path $repo 'README.md'
        [IO.File]::AppendAllText($userFile, 'uncommitted change' + [Environment]::NewLine, $Utf8)
        $before = Get-Hash $userFile
        $result = Invoke-Bootstrap $repo
        Assert-Condition ($result.ExitCode -eq 0 -and $result.Text -match '(?m)^READY\s*$') ('Dirty target install failed: ' + $result.Text) 'BOOTSTRAP_BUG'
        Assert-Condition ((Get-Hash $userFile) -eq $before) 'Unrelated modified file was altered.' 'BOOTSTRAP_BUG'
        Assert-Condition ((Invoke-Git $repo @('status','--porcelain=v1','--','README.md')) -eq 'M README.md') 'Unrelated Git modification was normalized.' 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-9' {
        $scenarioDir = New-ScenarioHome 'p4c-09'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'unsafe path fixture' + [Environment]::NewLine })
        $relative = [IO.Path]::GetRelativePath($RepoRoot, $repo)
        Assert-Condition (-not [IO.Path]::IsPathFullyQualified($relative)) 'Unsafe probe is not relative.'
        $result = Invoke-Bootstrap $relative
        Assert-BootstrapError $result 'UNSAFE_TARGET'
        Assert-NoInstallFiles $repo

        $outside = Join-Path $scenarioDir 'redirect-target'
        Assert-Descendant $outside $scenarioDir
        [IO.Directory]::CreateDirectory($outside) | Out-Null
        $link = Join-Path $repo '.opencode'
        Assert-Condition (-not (Test-Path -LiteralPath $link)) 'Redirect fixture destination already exists.'
        $junction = New-Item -ItemType Junction -Path $link -Target $outside -ErrorAction Stop
        Assert-Condition ($junction.Attributes -band [IO.FileAttributes]::ReparsePoint) 'Redirect fixture is not a reparse point.'
        $redirectResult = Invoke-Bootstrap $repo
        Assert-BootstrapError $redirectResult 'UNSAFE_TARGET_PATH'
        Assert-NoInstallFiles $repo
    }

    Run-Scenario 'P4C-10' {
        $scenarioDir = New-ScenarioHome 'p4c-10'
        $candidate = @(
            [pscustomobject]@{ Name = 'pyright'; File = 'pyproject.toml'; Content = '[tool.pyright]' + [Environment]::NewLine; Warning = 'VALIDATION_TOOL_UNAVAILABLE: pyright'; Commands = @('pyright') }
            [pscustomobject]@{ Name = 'cargo'; File = 'Cargo.toml'; Content = '[package]' + [Environment]::NewLine + 'name = "p4c_unavailable"' + [Environment]::NewLine + 'version = "0.1.0"' + [Environment]::NewLine + 'edition = "2021"' + [Environment]::NewLine; Warning = 'VALIDATION_TOOL_UNAVAILABLE: cargo'; Commands = @('cargo check', 'cargo test') }
            [pscustomobject]@{ Name = 'go'; File = 'go.mod'; Content = 'module example.invalid/p4c' + [Environment]::NewLine + 'go 1.22' + [Environment]::NewLine; Warning = 'VALIDATION_TOOL_UNAVAILABLE: go'; Commands = @('go test ./...') }
        )
        $missing = @($candidate | Where-Object { -not (Get-Command $_.Name -ErrorAction SilentlyContinue) } | Select-Object -First 1)
        Assert-Condition ($missing.Count -eq 1) 'No supported validation tool is unavailable in this environment.' 'ENVIRONMENT_LIMITATION'
        $fixture = $missing[0]
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'unavailable tool fixture' + [Environment]::NewLine; $fixture.File = $fixture.Content })
        $result = Invoke-Bootstrap $repo
        Assert-Condition ($result.ExitCode -eq 0 -and $result.Text -match '(?m)^READY\s*$') ('Unavailable-tool project install failed: ' + $result.Text) 'BOOTSTRAP_BUG'
        Assert-Condition ($result.Text.Contains($fixture.Warning)) ('Unavailable tool was not reported: ' + $fixture.Name) 'BOOTSTRAP_BUG'
        $manifest = [IO.File]::ReadAllText((Join-Path $repo '.opencode/orchestrator-install.json')) | ConvertFrom-Json
        foreach ($command in $fixture.Commands) { Assert-Condition (@($manifest.validation_commands | Where-Object { $_ -eq $command }).Count -eq 0) ('Unavailable command was suggested: ' + $command) 'BOOTSTRAP_BUG' }
        $source = [IO.File]::ReadAllText($Bootstrap)
        Assert-Condition ($source -notmatch '(?im)^\s*&\s*(npm|pnpm|yarn|bun|pip|uv|cargo|mvn|gradle)\s+(install|i|add|update|uninstall|remove)\b') 'Bootstrap contains a dependency-install invocation.' 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-11' {
        $scenarioDir = New-ScenarioHome 'p4c-11'
        $files = [ordered]@{ 'README.md' = 'policy fixture' + [Environment]::NewLine; 'package.json' = '{"packageManager":"npm@10","scripts":{"test":"node test.js","deploy":"node deploy.js"}}' + [Environment]::NewLine; 'package-lock.json' = '{}' + [Environment]::NewLine }
        $repo = New-CleanRepo $scenarioDir 'target' $files
        $result = Invoke-Bootstrap $repo
        Assert-Condition ($result.ExitCode -eq 0) ('Policy target install failed: ' + $result.Text) 'BOOTSTRAP_BUG'
        if ($QualificationSlice -ne 'Offline') {
        $diagnostics = Get-OpenCodeDiagnostics $repo
        $nox = Get-Agent $diagnostics.Agents 'nox'
        Assert-Condition (Has-Rule $nox 'shell' '*' 'allow' -and -not (Has-Rule $nox 'shell' '*' 'ask')) 'Trusted-project Tester shell allow missing or ASK present.' 'BOOTSTRAP_BUG'
        }
        if ($QualificationSlice -ne 'Runtime') {
        $manifest = [IO.File]::ReadAllText((Join-Path $repo '.opencode/orchestrator-install.json')) | ConvertFrom-Json
        Assert-Condition (@($manifest.validation_commands | Where-Object { $_ -eq 'npm test' }).Count -eq 1) 'Relevant test suggestion missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (@($manifest.validation_commands | Where-Object { $_ -eq 'npm run deploy' }).Count -eq 0) 'Default suggestions include unrelated script.' 'BOOTSTRAP_BUG'
        Assert-Condition ([IO.File]::ReadAllText((Join-Path $repo '.opencode/agents/nox.md')) -eq [IO.File]::ReadAllText((Join-Path $RepoRoot '.opencode/agents/nox.md'))) 'Bootstrap generated a command ACL.' 'BOOTSTRAP_BUG'
        }
    }

    Run-Scenario 'P4C-12' {
        $scenarioDir = New-ScenarioHome 'p4c-12'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'diagnostics fixture' + [Environment]::NewLine })
        $diagnostics = Assert-Installed $repo 'READY'
        if ($QualificationSlice -ne 'Offline') {
        Assert-ModelMapping $diagnostics.Agents
        }
    }

    Run-Scenario 'P4C-13' {
        $scenarioDir = New-ScenarioHome 'p4c-13'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'drift fixture' + [Environment]::NewLine })
        $first = Invoke-Bootstrap $repo
        Assert-Condition ($first.ExitCode -eq 0) ('Initial drift fixture install failed: ' + $first.Text) 'BOOTSTRAP_BUG'
        $managed = Join-Path $repo '.opencode/agents/vera.md'
        [IO.File]::AppendAllText($managed, '# manually changed by qualification' + [Environment]::NewLine, $Utf8)
        $changedHash = Get-Hash $managed
        $second = Invoke-Bootstrap $repo
        Assert-BootstrapError $second 'MANAGED_FILE_DRIFT'
        Assert-Condition ((Get-Hash $managed) -eq $changedHash) 'Drifted managed file was overwritten.' 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-14' {
        $scenarioDir = New-ScenarioHome 'p4c-14'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'security fixture' + [Environment]::NewLine; 'package.json' = '{"packageManager":"npm@10","scripts":{"test":"node test.js"}}' + [Environment]::NewLine; 'package-lock.json' = '{}' + [Environment]::NewLine })
        $diagnostics = Assert-Installed $repo 'READY'
        if ($QualificationSlice -ne 'Offline') {
        $agents = $diagnostics.Agents
        foreach ($id in @('kael', 'thales', 'atlas', 'argus', 'talos', 'helios', 'veyra', 'orin', 'vera')) {
            $agent = Get-Agent $agents $id
            Assert-Condition (Has-Rule $agent 'edit' '*' 'deny') ($id + ' edit DENY missing.') 'BOOTSTRAP_BUG'
            Assert-Condition (Has-Rule $agent 'shell' '*' 'deny') ($id + ' shell DENY missing.') 'BOOTSTRAP_BUG'
            Assert-Condition (Has-Rule $agent 'subagent' '*' 'deny') ($id + ' subagent DENY missing.') 'BOOTSTRAP_BUG'
        }
        $kael = Get-Agent $agents 'kael'
        $allowedChildren = @($kael.permissions | Where-Object { $_.action -eq 'subagent' -and $_.effect -eq 'allow' } | ForEach-Object { $_.resource } | Select-Object -Unique)
        $expectedChildren = @('veyra', 'orin', 'kovan', 'nox', 'vera', 'thales', 'atlas', 'argus', 'talos', 'helios')
        Assert-Condition ($allowedChildren.Count -eq $expectedChildren.Count -and @($allowedChildren | Where-Object { $_ -notin $expectedChildren }).Count -eq 0 -and @($expectedChildren | Where-Object { $allowedChildren -notcontains $_ }).Count -eq 0) 'Kael delegation allowlist mismatch.' 'BOOTSTRAP_BUG'
        }
        if ($QualificationSlice -ne 'Runtime') {
        $thalesPrompt = [IO.File]::ReadAllText((Join-Path $repo '.opencode/agents/thales.md'))
        Assert-Condition ($thalesPrompt -match 'invoked only through the Diagnostic Gate') 'Thales Diagnostic Gate requirement missing.' 'BOOTSTRAP_BUG'
        }
        if ($QualificationSlice -ne 'Offline') {
        $thales = Get-Agent $agents 'thales'
        Assert-Condition (Has-Rule $thales 'subagent' '*' 'deny') 'Thales subagent DENY missing.' 'BOOTSTRAP_BUG'
        $kovan = Get-Agent $agents 'kovan'
        Assert-Condition (Has-Rule $kovan 'edit' '*' 'allow') 'Kovan repository-local edit allow missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (-not (Has-Rule $kovan 'edit' '*' 'deny')) 'Kovan blanket edit DENY blocks scoped native ASK rules.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $kovan 'shell' '*' 'allow') 'Kovan shell ALLOW missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $kovan 'subagent' '*' 'deny') 'Kovan subagent DENY missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (@($kovan.permissions | Where-Object { $_.action -eq 'external_directory' }).Count -eq 0) 'Kovan must inherit project external-directory rules without overriding a specific DENY.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $kovan 'edit' '.opencode/**' 'ask' -and Has-Rule $kovan 'edit' '.opencode/plugins/**' 'ask') 'Project-owned protected-adjacent edit ASK missing.' 'BOOTSTRAP_BUG'
        foreach ($resource in @('.git', '.git/*', '.opencode', '.opencode/agents/**',
            '.opencode/plugins/olympus-activity/**',
            '.opencode/orchestrator-install.json', '.opencode/opencode.json', '.opencode/opencode.jsonc',
            'opencode.json', 'opencode.jsonc', '*.env', '*.env.*')) {
            Assert-Condition (Has-Rule $kovan 'edit' $resource 'deny') ('Kovan protected edit path missing: ' + $resource) 'BOOTSTRAP_BUG'
        }
        Assert-Condition (Has-Rule $kovan 'edit' '*.env.example' 'allow') 'Documented env-example exception missing.' 'BOOTSTRAP_BUG'
        }
        if ($QualificationSlice -ne 'Runtime') {
        $nativeConfig = [IO.File]::ReadAllText((Join-Path $repo 'opencode.jsonc'))
        Assert-Condition ($nativeConfig -match '(?s)"action":\s*"edit"\s*,\s*"resource":\s*"\*"\s*,\s*"effect":\s*"ask"' -and
            $nativeConfig -match '(?s)"action":\s*"external_directory"\s*,\s*"resource":\s*"\*"\s*,\s*"effect":\s*"ask"') 'Global native edit/external_directory ASK defaults missing.' 'BOOTSTRAP_BUG'
        }
        if ($QualificationSlice -ne 'Offline') {
        $nox = Get-Agent $agents 'nox'
        Assert-Condition (Has-Rule $nox 'edit' '*' 'deny') 'Nox edit DENY missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $nox 'shell' '*' 'allow') 'Nox shell ALLOW missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $nox 'subagent' '*' 'deny') 'Nox subagent DENY missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (@($nox.permissions | Where-Object { $_.action -eq 'external_directory' }).Count -eq 0) 'Nox must inherit project external-directory rules without overriding a specific DENY.' 'BOOTSTRAP_BUG'
        $shellRules = @($nox.permissions | Where-Object { $_.action -eq 'shell' })
        Assert-Condition (@($shellRules | Where-Object effect -eq 'ask').Count -eq 0) 'Effective Nox shell ASK exists.' 'BOOTSTRAP_BUG'
        Assert-Condition (@($shellRules | Where-Object { $_.effect -eq 'allow' -and $_.resource -eq '*' }).Count -gt 0) 'Effective Nox broad shell allow missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $nox 'read' '*' 'allow') 'Nox source-read permission missing.' 'BOOTSTRAP_BUG'
        }
    }

    Run-Scenario 'M-CONTEXTUAL-MAINTENANCE' {
        $scenarioDir = New-ScenarioHome 'contextual-maintenance'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'contextual maintenance fixture' + [Environment]::NewLine })
        $diagnostics = Assert-Installed $repo 'READY'
        $policy = [IO.File]::ReadAllText((Join-Path $RepoRoot 'olympus/policies/maintenance-context.md'))
        $kaelPrompt = [IO.File]::ReadAllText((Join-Path $repo '.opencode/agents/kael.md'))
        $manifest = [IO.File]::ReadAllText((Join-Path $repo '.opencode/orchestrator-install.json')) | ConvertFrom-Json -Depth 100
        Assert-Condition ($policy -match 'Kael is the only root orchestrator' -and
            $policy -match 'There is no separate maintenance role, command' -and
            $policy -match 'A native `/goal` surface remains opt-in' -and
            $kaelPrompt.Contains($policy.Trim())) 'Contextual maintenance policy is not delivered through Kael.' 'BOOTSTRAP_BUG'
        Assert-Condition (-not (Test-Path (Join-Path $repo '.opencode/agents/aegis.md')) -and
            -not (Test-Path (Join-Path $repo '.opencode/commands/maintain.md')) -and
            @($manifest.managed_files).Count -eq ($ManagedPaths.Count - 1)) 'Fresh project install retained a retired maintenance route or wrong manifest inventory.' 'BOOTSTRAP_BUG'
        if ($QualificationSlice -ne 'Offline') {
            Assert-Condition (@($diagnostics.Agents).Count -eq 11 -and
                @($diagnostics.Agents | Where-Object id -eq 'aegis').Count -eq 0) 'Effective OpenCode roster is not the single-Kael 11-role roster.' 'BOOTSTRAP_BUG'
        }
    }

    Run-Scenario 'M-CLEAN-BREAK-RETIREMENT' {
        $legacyBaseline = 'bbb503cfed16867acc5f04020262174a4166e6dd'
        $oldAgentText = (& git -C $RepoRoot show "${legacyBaseline}:.opencode/agents/aegis.md" | Out-String)
        $agentCode = $LASTEXITCODE
        $oldCommandText = (& git -C $RepoRoot show "${legacyBaseline}:.opencode/commands/maintain.md" | Out-String)
        $commandCode = $LASTEXITCODE
        Assert-Condition ($agentCode -eq 0 -and $oldAgentText -match 'GENERATED BY scripts/render_harnesses\.py' -and
            $commandCode -eq 0 -and $oldCommandText -match 'agent: aegis') 'Cannot load the pinned generated legacy route fixture.' 'HARNESS_BUG'

        $scenarioDir = New-ScenarioHome 'clean-break-retirement'
        $ownedRepo = New-CleanRepo $scenarioDir 'owned' ([ordered]@{ 'README.md' = 'owned legacy route' + [Environment]::NewLine })
        [void](Assert-Installed $ownedRepo 'READY')
        $ownedManifestPath = Join-Path $ownedRepo '.opencode/orchestrator-install.json'
        $ownedManifest = [IO.File]::ReadAllText($ownedManifestPath) | ConvertFrom-Json -Depth 100
        $ownedLegacy = @(
            @{ path='.opencode/agents/aegis.md'; text=$oldAgentText },
            @{ path='.opencode/commands/maintain.md'; text=$oldCommandText }
        )
        foreach ($entry in $ownedLegacy) {
            $file = Join-Path $ownedRepo $entry.path
            [IO.Directory]::CreateDirectory((Split-Path -Parent $file)) | Out-Null
            [IO.File]::WriteAllText($file, $entry.text, $Utf8)
            $ownedManifest.managed_files += [pscustomobject]@{ path=$entry.path; sha256=(Get-Hash $file) }
        }
        [IO.File]::WriteAllText($ownedManifestPath, (($ownedManifest | ConvertTo-Json -Depth 100) + "`n"), $Utf8)
        $upgrade = Invoke-Bootstrap $ownedRepo
        Assert-Condition ($upgrade.ExitCode -eq 0 -and $upgrade.Text -match '(?m)^READY\s*$' -and
            -not (Test-Path (Join-Path $ownedRepo '.opencode/agents/aegis.md')) -and
            -not (Test-Path (Join-Path $ownedRepo '.opencode/commands/maintain.md'))) 'Verified owned legacy route was not retired.' 'BOOTSTRAP_BUG'
        $newManifest = [IO.File]::ReadAllText($ownedManifestPath) | ConvertFrom-Json -Depth 100
        Assert-Condition (@($newManifest.managed_files).Count -eq ($ManagedPaths.Count - 1) -and
            @($newManifest.managed_files | Where-Object path -match 'aegis|commands/maintain').Count -eq 0) 'Retired paths remain in the updated ownership manifest.' 'BOOTSTRAP_BUG'

        $modifiedRepo = New-CleanRepo $scenarioDir 'modified' ([ordered]@{ 'README.md' = 'modified legacy route' + [Environment]::NewLine })
        [void](Assert-Installed $modifiedRepo 'READY')
        $modifiedManifestPath = Join-Path $modifiedRepo '.opencode/orchestrator-install.json'
        $modifiedManifest = [IO.File]::ReadAllText($modifiedManifestPath) | ConvertFrom-Json -Depth 100
        $modifiedAgent = Join-Path $modifiedRepo '.opencode/agents/aegis.md'
        [IO.File]::WriteAllText($modifiedAgent, $oldAgentText, $Utf8)
        $modifiedManifest.managed_files += [pscustomobject]@{ path='.opencode/agents/aegis.md'; sha256=(Get-Hash $modifiedAgent) }
        [IO.File]::WriteAllText((Join-Path $modifiedRepo '.opencode/commands/maintain.md'), $oldCommandText, $Utf8)
        $modifiedCommand = Join-Path $modifiedRepo '.opencode/commands/maintain.md'
        $modifiedManifest.managed_files += [pscustomobject]@{ path='.opencode/commands/maintain.md'; sha256=(Get-Hash $modifiedCommand) }
        [IO.File]::WriteAllText($modifiedManifestPath, (($modifiedManifest | ConvertTo-Json -Depth 100) + "`n"), $Utf8)
        [IO.File]::AppendAllText($modifiedAgent, "`nuser modification`n", $Utf8)
        $agentHash = Get-Hash $modifiedAgent; $manifestHash = Get-Hash $modifiedManifestPath
        $modifiedUpgrade = Invoke-Bootstrap $modifiedRepo
        Assert-BootstrapError $modifiedUpgrade 'MANAGED_FILE_DRIFT'
        Assert-Condition ((Get-Hash $modifiedAgent) -eq $agentHash -and
            (Get-Hash $modifiedManifestPath) -eq $manifestHash -and
            (Test-Path (Join-Path $modifiedRepo '.opencode/commands/maintain.md'))) 'Modified owned legacy route was destructively changed.' 'BOOTSTRAP_BUG'

        $unownedRepo = New-CleanRepo $scenarioDir 'unowned' ([ordered]@{ 'README.md' = 'unowned legacy route' + [Environment]::NewLine })
        [void](Assert-Installed $unownedRepo 'READY')
        $unownedAgent = Join-Path $unownedRepo '.opencode/agents/aegis.md'
        $unownedCommand = Join-Path $unownedRepo '.opencode/commands/maintain.md'
        [IO.File]::WriteAllText($unownedAgent, 'user-owned agent' + "`n", $Utf8)
        [IO.File]::WriteAllText($unownedCommand, 'user-owned command' + "`n", $Utf8)
        $unownedAgentHash = Get-Hash $unownedAgent; $unownedCommandHash = Get-Hash $unownedCommand
        $unownedUpgrade = Invoke-Bootstrap $unownedRepo
        Assert-BootstrapError $unownedUpgrade 'INSTALL_CONFLICT'
        Assert-Condition ((Get-Hash $unownedAgent) -eq $unownedAgentHash -and
            (Get-Hash $unownedCommand) -eq $unownedCommandHash) 'Unowned legacy-name files were destructively changed.' 'BOOTSTRAP_BUG'
    }

    Write-Output 'CONTEXTUAL_MAINTENANCE_RUNTIME_ASSERTION: not applicable — no separate maintenance command or role exists.'

    $failed = @($Results | Where-Object Status -eq 'FAIL')
    foreach ($result in $Results) {
        Write-Output ($result.Id + '   ' + $result.Status)
        if ($result.Status -eq 'FAIL') { Write-Output ('CLASSIFICATION: ' + $result.Classification); Write-Output ('EVIDENCE: ' + $result.Evidence) }
    }
    if ($failed.Count -eq 0) {
        Write-Output ('WORKSPACES_RETAINED: ' + $RunRoot)
        if ($QualificationSlice -eq 'Runtime') {
            Write-Output 'PHASE 4C RUNTIME QUALIFICATION: PASS (runtime-boundary scenarios; no separate maintenance command exists)'
        } elseif ($QualificationSlice -eq 'Offline') {
            Write-Output 'PHASE 4C OFFLINE QUALIFICATION: PASS (local bootstrap/history assertions; effective OpenCode queries not run)'
        } else {
            Write-Output 'PHASE 4C QUALIFICATION: PASS'
        }
        exit 0
    }
    Write-Output ('WORKSPACES_RETAINED: ' + $RunRoot)
    Write-Output 'PHASE 4C QUALIFICATION: FAIL'
    exit 1
} catch {
    $message = $_.Exception.Message
    $classification = 'HARNESS_BUG'; $evidence = $message
    if ($message -match '^(BOOTSTRAP_BUG|HARNESS_BUG|ENVIRONMENT_LIMITATION|OPENCODE_RUNTIME_ISSUE|TEST_EXPECTATION_BUG)\|(.*)$') { $classification = $Matches[1]; $evidence = $Matches[2] }
    Write-Output ('CLASSIFICATION: ' + $classification)
    Write-Output ('EVIDENCE: ' + $evidence)
    if (Test-Path -LiteralPath $RunRoot) { Write-Output ('WORKSPACES_RETAINED: ' + $RunRoot) }
    Write-Output 'PHASE 4C QUALIFICATION: FAIL'
    exit 1
} finally {
    [Environment]::SetEnvironmentVariable('PATH',$OriginalPath,'Process')
}
