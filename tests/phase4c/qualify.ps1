[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$WorkRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'tests/.phase4c-work'))
$Bootstrap = Join-Path $RepoRoot 'scripts/bootstrap.ps1'
$Utf8 = [Text.UTF8Encoding]::new($false)
$RunId = [Guid]::NewGuid().ToString('N')
$RunRoot = Join-Path $WorkRoot ('run-' + $RunId)
$Results = [System.Collections.Generic.List[object]]::new()
$ManagedPaths = @(
    'opencode.jsonc',
    '.opencode/agents/kael.md', '.opencode/agents/veyra.md',
    '.opencode/agents/orin.md', '.opencode/agents/kovan.md',
    '.opencode/agents/nox.md', '.opencode/agents/vera.md',
    '.opencode/agents/sorin.md', '.opencode/agents/maintenance.md',
    '.opencode/commands/maintain.md', '.opencode/orchestrator-install.json'
)
$SafeGit = @(
    'git status', 'git status --short', 'git status --porcelain', 'git status --porcelain=v2',
    'git diff', 'git diff --check', 'git diff --cached', 'git diff --cached --check',
    'git diff --name-only', 'git diff --raw', 'git rev-parse HEAD', 'git ls-files'
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

function Get-NoxRules([string]$Repo) {
    $text = [IO.File]::ReadAllText((Join-Path $Repo '.opencode/agents/nox.md'))
    $first = $text.IndexOf('---')
    $second = if ($first -ge 0) { $text.IndexOf('---', $first + 3) } else { -1 }
    Assert-Condition ($first -ge 0 -and $second -gt $first) 'Tester frontmatter is missing.' 'BOOTSTRAP_BUG'
    $front = $text.Substring($first + 3, $second - ($first + 3))
    $lines = $front -split '\r?\n'
    $rules = [System.Collections.Generic.List[object]]::new()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i].Trim() -ne '- action: shell') { continue }
        Assert-Condition ($i + 2 -lt $lines.Count) 'Truncated Tester shell rule.' 'BOOTSTRAP_BUG'
        $resourceLine = $lines[$i + 1].Trim()
        $effectLine = $lines[$i + 2].Trim()
        if ($resourceLine -match '^resource:\s*"(.*)"$') { $resource = $Matches[1] }
        elseif ($resourceLine -match '^resource:\s*''(.*)''$') { $resource = $Matches[1] }
        else { throw ('HARNESS_BUG|Cannot parse Tester resource: ' + $resourceLine) }
        if ($effectLine -notmatch '^effect:\s*(allow|deny|ask)$') { throw ('HARNESS_BUG|Cannot parse Tester effect: ' + $effectLine) }
        $rules.Add([pscustomobject]@{ Resource = $resource; Effect = $Matches[1] })
        $i += 2
    }
    return ,@($rules)
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
        'kael' = @('gpt-6-sol', 'high', 'primary')
        'sorin' = @('gpt-6-sol', 'xhigh', 'subagent')
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
    $diagnostics = Get-OpenCodeDiagnostics $Repo
    Assert-ModelMapping $diagnostics.Agents
    return $diagnostics
}

function Get-ToolRules([string]$Repo) {
    $rules = Get-NoxRules $Repo
    return @($rules | Where-Object { $_.Effect -eq 'allow' } | ForEach-Object { $_.Resource })
}

function Run-Scenario([string]$Id, [scriptblock]$Body) {
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
    Assert-Condition ($null -ne (Get-Command opencode -ErrorAction SilentlyContinue)) 'OpenCode is unavailable.' 'ENVIRONMENT_LIMITATION'
    Assert-Condition ($null -ne (Get-Command pwsh -ErrorAction SilentlyContinue)) 'PowerShell 7 is unavailable.' 'ENVIRONMENT_LIMITATION'
    Assert-Condition ([IO.Directory]::Exists((Join-Path $RepoRoot '.git'))) 'Harness is not running in the orchestrator Git repository.'
    Assert-Descendant $WorkRoot $RepoRoot
    [IO.Directory]::CreateDirectory($WorkRoot) | Out-Null
    Assert-Descendant $WorkRoot $RepoRoot
    [IO.Directory]::CreateDirectory($RunRoot) | Out-Null
    Assert-Descendant $RunRoot $WorkRoot

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
        foreach ($relative in $ManagedPaths) { Assert-Condition (Test-Path -LiteralPath (Join-Path $repo ($relative -replace '/', [IO.Path]::DirectorySeparatorChar))) ('Installed file missing: ' + $relative) 'BOOTSTRAP_BUG' }
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
        $duplicateRules = @(Get-NoxRules $repo | Group-Object Resource, Effect | Where-Object Count -gt 1)
        Assert-Condition ($duplicateRules.Count -eq 0) 'Tester policy contains duplicate shell rules.' 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-4' {
        $scenarioDir = New-ScenarioHome 'p4c-04'
        $package = '{"packageManager":"npm@10","scripts":{"test":"node test.js","lint":"eslint .","build":"node build.js","deploy":"node deploy.js"}}' + [Environment]::NewLine
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'node scripts fixture' + [Environment]::NewLine; 'package.json' = $package; 'package-lock.json' = '{}' + [Environment]::NewLine })
        $result = Invoke-Bootstrap $repo
        Assert-Condition ($result.ExitCode -eq 0 -and $result.Text -match '(?m)^READY\s*$') ('Node install failed: ' + $result.Text) 'BOOTSTRAP_BUG'
        $allows = Get-ToolRules $repo
        foreach ($expected in @('npm test', 'npm run lint', 'npm run build')) { Assert-Condition ($allows -contains $expected) ('Expected Node command missing: ' + $expected) 'BOOTSTRAP_BUG' }
        Assert-Condition ($allows -notcontains 'npm run deploy' -and $allows -notcontains 'npm run test') 'An unapproved or unused script command was authorized.' 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-5' {
        $scenarioDir = New-ScenarioHome 'p4c-05'
        $caseA = New-CleanRepo $scenarioDir 'case-a' ([ordered]@{ 'README.md' = 'pnpm case' + [Environment]::NewLine; 'package.json' = '{"scripts":{"test":"node test.js"}}' + [Environment]::NewLine; 'pnpm-lock.yaml' = 'lockfileVersion: 9' + [Environment]::NewLine })
        $resultA = Invoke-Bootstrap $caseA
        Assert-Condition ($resultA.ExitCode -eq 0 -and $resultA.Text -match '(?m)^READY\s*$') ('Clear package manager case failed: ' + $resultA.Text) 'BOOTSTRAP_BUG'
        Assert-Condition ($resultA.Text -match '(?m)^pnpm\s*$') 'pnpm lockfile was not selected.' 'BOOTSTRAP_BUG'
        if (Get-Command pnpm -ErrorAction SilentlyContinue) { Assert-Condition ((Get-ToolRules $caseA) -contains 'pnpm test') 'pnpm test was not selected.' 'BOOTSTRAP_BUG' }
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
        $allows = Get-ToolRules $repo
        if (Get-Command npm -ErrorAction SilentlyContinue) { Assert-Condition ($allows -contains 'npm test') 'Node validation missing from union.' 'BOOTSTRAP_BUG' }
        else { Assert-Condition ($result.Text -match 'VALIDATION_TOOL_UNAVAILABLE: npm') 'Unavailable npm not reported.' 'BOOTSTRAP_BUG' }
        if (Get-Command pytest -ErrorAction SilentlyContinue) { Assert-Condition ($allows -contains 'pytest') 'Python validation missing from union.' 'BOOTSTRAP_BUG' }
        else { Assert-Condition ($result.Text -match 'VALIDATION_TOOL_UNAVAILABLE: pytest') 'Unavailable pytest not reported.' 'BOOTSTRAP_BUG' }
        Assert-Condition ($allows -notcontains 'npm run publish') 'Unapproved package script entered policy.' 'BOOTSTRAP_BUG'
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
        [IO.File]::AppendAllText((Join-Path $repo 'README.md'), 'uncommitted change' + [Environment]::NewLine, $Utf8)
        $result = Invoke-Bootstrap $repo
        Assert-BootstrapError $result 'TARGET_WORKTREE_DIRTY'
        Assert-NoInstallFiles $repo
        Assert-Condition ([IO.File]::ReadAllText((Join-Path $repo 'README.md')).Contains('uncommitted change')) 'Dirty target change was altered.' 'BOOTSTRAP_BUG'
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
        $allows = Get-ToolRules $repo
        foreach ($command in $fixture.Commands) { Assert-Condition ($allows -notcontains $command) ('Unavailable command was authorized: ' + $command) 'BOOTSTRAP_BUG' }
        $source = [IO.File]::ReadAllText($Bootstrap)
        Assert-Condition ($source -notmatch '(?im)^\s*&\s*(npm|pnpm|yarn|bun|pip|uv|cargo|mvn|gradle)\s+(install|i|add|update|uninstall|remove)\b') 'Bootstrap contains a dependency-install invocation.' 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-11' {
        $scenarioDir = New-ScenarioHome 'p4c-11'
        $files = [ordered]@{ 'README.md' = 'policy fixture' + [Environment]::NewLine; 'package.json' = '{"packageManager":"npm@10","scripts":{"test":"node test.js","deploy":"node deploy.js"}}' + [Environment]::NewLine; 'package-lock.json' = '{}' + [Environment]::NewLine }
        $repo = New-CleanRepo $scenarioDir 'target' $files
        $result = Invoke-Bootstrap $repo
        Assert-Condition ($result.ExitCode -eq 0) ('Policy target install failed: ' + $result.Text) 'BOOTSTRAP_BUG'
        $rules = Get-NoxRules $repo
        $allows = @($rules | Where-Object Effect -eq 'allow' | ForEach-Object Resource)
        Assert-Condition (@($rules | Where-Object { $_.Resource -eq '*' -and $_.Effect -eq 'deny' }).Count -gt 0) 'Tester shell wildcard DENY fallback missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (@($rules | Where-Object Effect -eq 'ask').Count -eq 0) 'Tester shell ASK rule found.' 'BOOTSTRAP_BUG'
        Assert-Condition (@($rules | Where-Object { $_.Effect -eq 'allow' -and $_.Resource -match '[*?]' }).Count -eq 0) 'Nox wildcard shell ALLOW found.' 'BOOTSTRAP_BUG'
        foreach ($command in $SafeGit) { Assert-Condition ($allows -contains $command) ('Safe Git baseline missing: ' + $command) 'BOOTSTRAP_BUG' }
        Assert-Condition ($allows -contains 'npm test') 'Relevant test command missing.' 'BOOTSTRAP_BUG'
        Assert-Condition ($allows -notcontains 'npm run deploy' -and $allows -notcontains 'npm run banana') 'Unknown package script authorized.' 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'P4C-12' {
        $scenarioDir = New-ScenarioHome 'p4c-12'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'diagnostics fixture' + [Environment]::NewLine })
        $diagnostics = Assert-Installed $repo 'READY'
        Assert-ModelMapping $diagnostics.Agents
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
        $agents = $diagnostics.Agents
        foreach ($id in @('kael', 'sorin', 'veyra', 'orin', 'vera')) {
            $agent = Get-Agent $agents $id
            Assert-Condition (Has-Rule $agent 'edit' '*' 'deny') ($id + ' edit DENY missing.') 'BOOTSTRAP_BUG'
            Assert-Condition (Has-Rule $agent 'shell' '*' 'deny') ($id + ' shell DENY missing.') 'BOOTSTRAP_BUG'
            Assert-Condition (Has-Rule $agent 'subagent' '*' 'deny') ($id + ' subagent DENY missing.') 'BOOTSTRAP_BUG'
        }
        $kael = Get-Agent $agents 'kael'
        $allowedChildren = @($kael.permissions | Where-Object { $_.action -eq 'subagent' -and $_.effect -eq 'allow' } | ForEach-Object { $_.resource } | Select-Object -Unique)
        $expectedChildren = @('veyra', 'orin', 'kovan', 'nox', 'vera', 'sorin')
        Assert-Condition ($allowedChildren.Count -eq $expectedChildren.Count -and @($allowedChildren | Where-Object { $_ -notin $expectedChildren }).Count -eq 0 -and @($expectedChildren | Where-Object { $allowedChildren -notcontains $_ }).Count -eq 0) 'Kael delegation allowlist mismatch.' 'BOOTSTRAP_BUG'
        $sorinPrompt = [IO.File]::ReadAllText((Join-Path $repo '.opencode/agents/sorin.md'))
        Assert-Condition ($sorinPrompt -match 'invoked only through the Diagnostic Gate') 'Sorin Diagnostic Gate requirement missing.' 'BOOTSTRAP_BUG'
        $sorin = Get-Agent $agents 'sorin'
        Assert-Condition (Has-Rule $sorin 'subagent' '*' 'deny') 'Sorin subagent DENY missing.' 'BOOTSTRAP_BUG'
        $kovan = Get-Agent $agents 'kovan'
        Assert-Condition (Has-Rule $kovan 'edit' '*' 'allow') 'Kovan repository-local edit allow missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $kovan 'shell' '*' 'deny') 'Kovan shell DENY missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $kovan 'subagent' '*' 'deny') 'Kovan subagent DENY missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $kovan 'external_directory' '*' 'deny') 'Kovan external-directory DENY missing.' 'BOOTSTRAP_BUG'
        foreach ($resource in @('.git', '.git/*', '.opencode', '.opencode/*', 'opencode.json', 'opencode.jsonc', '*.env', '*.env.*')) {
            Assert-Condition (Has-Rule $kovan 'edit' $resource 'deny') ('Kovan protected edit path missing: ' + $resource) 'BOOTSTRAP_BUG'
        }
        Assert-Condition (Has-Rule $kovan 'edit' '*.env.example' 'allow') 'Documented env-example exception missing.' 'BOOTSTRAP_BUG'
        $nox = Get-Agent $agents 'nox'
        Assert-Condition (Has-Rule $nox 'edit' '*' 'deny') 'Nox edit DENY missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $nox 'shell' '*' 'deny') 'Nox shell DENY fallback missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $nox 'subagent' '*' 'deny') 'Nox subagent DENY missing.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $nox 'external_directory' '*' 'deny') 'Nox external-directory DENY missing.' 'BOOTSTRAP_BUG'
        $shellRules = @($nox.permissions | Where-Object { $_.action -eq 'shell' })
        Assert-Condition (@($shellRules | Where-Object effect -eq 'ask').Count -eq 0) 'Effective Nox shell ASK exists.' 'BOOTSTRAP_BUG'
        Assert-Condition (@($shellRules | Where-Object { $_.effect -eq 'allow' -and $_.resource -match '[*?]' }).Count -eq 0) 'Effective Nox wildcard shell ALLOW exists.' 'BOOTSTRAP_BUG'
        Assert-Condition (@($shellRules | Where-Object { $_.effect -eq 'allow' -and $_.resource -eq 'npm test' }).Count -gt 0) 'Effective target validation command is not allowed.' 'BOOTSTRAP_BUG'
        Assert-Condition (@($shellRules | Where-Object { $_.effect -eq 'allow' -and $_.resource -eq 'npm run deploy' }).Count -eq 0) 'Unapproved script is allowed effectively.' 'BOOTSTRAP_BUG'
        Assert-Condition (Has-Rule $nox 'read' '*' 'allow') 'Nox source-read permission missing.' 'BOOTSTRAP_BUG'
    }

    # Maintainer Plane extension: static/bootstrap assertions only. The interactive
    # command callback, parent session identity and permission-prompt behavior must
    # be checked in a normal Kael UI session; this harness does not emulate them.
    Run-Scenario 'M1-M4-M6-STATIC_BOOTSTRAP_ASSERTION' {
        $scenarioDir = New-ScenarioHome 'maintainer-static'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'maintainer fixture' + [Environment]::NewLine })
        $diagnostics = Assert-Installed $repo 'READY'
        $agent = Get-Agent $diagnostics.Agents 'maintenance'
        Assert-Condition ($agent.mode -eq 'subagent' -and $agent.hidden -eq $true -and $agent.model.providerID -eq 'openai' -and $agent.model.id -eq 'gpt-6-sol' -and $agent.model.variant -eq 'high') 'M1/M6: maintenance mode, hidden status, or model mismatch.' 'BOOTSTRAP_BUG'
        foreach ($action in @('read', 'glob', 'grep', 'list', 'lsp', 'shell', 'edit', 'external_directory')) {
            Assert-Condition (Has-Rule $agent $action '*' 'allow') ('M2: maintenance ' + $action + ' allow missing.') 'BOOTSTRAP_BUG'
        }
        Assert-Condition (Has-Rule $agent 'subagent' '*' 'deny' -and -not (Has-Rule $agent 'subagent' '*' 'allow')) 'M2: maintenance child deny missing.' 'BOOTSTRAP_BUG'
        $kael = Get-Agent $diagnostics.Agents 'kael'
        $children = @($kael.permissions | Where-Object { $_.action -eq 'subagent' -and $_.effect -eq 'allow' } | ForEach-Object resource | Select-Object -Unique)
        $normal = @('veyra', 'orin', 'kovan', 'nox', 'vera', 'sorin')
        Assert-Condition (Has-Rule $kael 'subagent' '*' 'deny' -and $children.Count -eq $normal.Count -and @($children | Where-Object { $_ -notin $normal }).Count -eq 0 -and @($normal | Where-Object { $children -notcontains $_ }).Count -eq 0) 'M3/M6: Kael delegation boundary changed.' 'BOOTSTRAP_BUG'
        $kaelPrompt = [IO.File]::ReadAllText((Join-Path $repo '.opencode/agents/kael.md'))
        $lifecycle = [regex]::Match($kaelPrompt, '(?s)## User-facing lifecycle communication\s*(.*?)(?=\r?\n## |\z)').Groups[1].Value
        $handoff = [regex]::Match($kaelPrompt, '(?s)## Explicit maintenance result handoff\s*(.*?)(?=\r?\n## |\z)').Groups[1].Value
        Assert-Condition ($lifecycle -match '(?i)final response|overall request' -and $lifecycle -match '(?i)finished|complete' -and $lifecycle -match '(?is)nothing.*running') 'Kael completion visibility policy missing.' 'BOOTSTRAP_BUG'
        Assert-Condition ($lifecycle -match '(?i)orchestration work|required children' -and $lifecycle -match '(?i)still running|in progress' -and $lifecycle -match '(?i)next step|follow-up') 'Kael remaining-work visibility policy missing.' 'BOOTSTRAP_BUG'
        Assert-Condition ($lifecycle -match '(?i)internal coordination' -and $lifecycle -match '(?i)raw orchestration' -and $lifecycle -match '(?i)relay-only') 'Kael human-facing, non-raw relay policy missing.' 'BOOTSTRAP_BUG'
        Assert-Condition ($handoff -match '(?i)already finished' -and $handoff -match '(?is)present.*directly' -and $handoff -match '(?i)never\s+merely prepend' -and $handoff -match '(?i)remains running') 'Kael natural Maintenance handoff policy missing.' 'BOOTSTRAP_BUG'
        Assert-Condition ($lifecycle -match '(?i)lead the final response with' -and $lifecycle -match '(?i)scan-friendly' -and $lifecycle -match '(?i)passed checks' -and $lifecycle -match '(?i)intentionally\s+unperformed actions' -and $lifecycle -match '(?i)one concrete "Next:"') 'Kael compact, outcome-first engineering summary policy missing.' 'BOOTSTRAP_BUG'
        Assert-Condition ($lifecycle -match '(?is)optional smoke.*COMPLETE\s+and idle' -and $lifecycle -match '(?i)required validation is pending' -and $lifecycle -match '(?i)if it failed or a blocker exists' -and $lifecycle -match '(?i)required workers remain active') 'Kael finished-versus-unverified or active-work policy missing.' 'BOOTSTRAP_BUG'
        Assert-Condition ($lifecycle -match '(?i)surrounding user-facing conversation' -and $lifecycle -match '(?i)pasted technical specifications' -and $lifecycle -match '(?i)current direct request' -and $lifecycle -match '(?i)do not translate commands') 'Kael conversational-language policy missing.' 'BOOTSTRAP_BUG'
        Assert-Condition ($handoff -match '(?i)normal user-facing style' -and $handoff -match '(?i)reproduce its prose as a relay' -and $handoff -match '(?i)idle, not in progress') 'Kael Maintenance result consumption policy missing.' 'BOOTSTRAP_BUG'
        $command = [IO.File]::ReadAllText((Join-Path $repo '.opencode/commands/maintain.md'))
        Assert-Condition ($command -match '(?m)^agent: maintenance\s*$' -and $command -match '(?m)^subagent: true\s*$' -and $command.Contains('$ARGUMENTS') -and $command -match '(?m)^description:') 'M4: installed project command frontmatter or argument forwarding missing.' 'BOOTSTRAP_BUG'
        $manifest = [IO.File]::ReadAllText((Join-Path $repo '.opencode/orchestrator-install.json')) | ConvertFrom-Json -Depth 100
        Assert-Condition (@($manifest.managed_files).Count -eq ($ManagedPaths.Count - 1)) 'Managed asset count mismatch.' 'BOOTSTRAP_BUG'
        foreach ($path in @('.opencode/agents/kael.md', '.opencode/agents/maintenance.md', '.opencode/commands/maintain.md')) {
            $entry = @($manifest.managed_files | Where-Object path -eq $path)
            Assert-Condition ($entry.Count -eq 1 -and $entry[0].sha256 -eq (Get-Hash (Join-Path $repo $path))) ('Manifest does not own/hash ' + $path) 'BOOTSTRAP_BUG'
        }
        $again = Invoke-Bootstrap $repo
        Assert-Condition ($again.ExitCode -eq 0 -and $again.Text -match '(?m)^NO_CHANGES\s*$') ('Maintenance reinstall is not idempotent: ' + $again.Text) 'BOOTSTRAP_BUG'
    }

    Run-Scenario 'M7-MANAGED_DRIFT' {
        foreach ($path in @('.opencode/agents/kael.md', '.opencode/agents/maintenance.md', '.opencode/commands/maintain.md')) {
            $scenarioDir = New-ScenarioHome ('maintainer-drift-' + [IO.Path]::GetFileNameWithoutExtension($path))
            $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'drift fixture' + [Environment]::NewLine })
            [void](Assert-Installed $repo 'READY')
            $file = Join-Path $repo $path
            [IO.File]::AppendAllText($file, '# changed by qualification' + [Environment]::NewLine, $Utf8)
            $hash = Get-Hash $file
            $result = Invoke-Bootstrap $repo
            Assert-BootstrapError $result 'MANAGED_FILE_DRIFT'
            Assert-Condition ((Get-Hash $file) -eq $hash) ('Drift was overwritten: ' + $path) 'BOOTSTRAP_BUG'
        }
    }

    Run-Scenario 'M-LEGACY-MANAGED-UPGRADE' {
        $scenarioDir = New-ScenarioHome 'maintainer-upgrade'
        $repo = New-CleanRepo $scenarioDir 'target' ([ordered]@{ 'README.md' = 'legacy fixture' + [Environment]::NewLine })
        [void](Assert-Installed $repo 'READY')
        $newPaths = @('.opencode/agents/maintenance.md', '.opencode/commands/maintain.md')
        $manifestPath = Join-Path $repo '.opencode/orchestrator-install.json'
        $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json -Depth 100
        $manifest.managed_files = @($manifest.managed_files | Where-Object { $_.path -notin $newPaths })
        [IO.File]::WriteAllText($manifestPath, (($manifest | ConvertTo-Json -Depth 100) + "`n"), $Utf8)
        foreach ($path in $newPaths) { [IO.File]::Delete((Join-Path $repo $path)) }
        $upgrade = Invoke-Bootstrap $repo
        Assert-Condition ($upgrade.ExitCode -eq 0 -and $upgrade.Text -match '(?m)^READY\s*$') ('Managed legacy upgrade failed: ' + $upgrade.Text) 'BOOTSTRAP_BUG'
        [void](Assert-Installed $repo 'NO_CHANGES')

        $conflictRepo = New-CleanRepo $scenarioDir 'conflict' ([ordered]@{ 'README.md' = 'legacy conflict fixture' + [Environment]::NewLine })
        [void](Assert-Installed $conflictRepo 'READY')
        $conflictManifestPath = Join-Path $conflictRepo '.opencode/orchestrator-install.json'
        $conflictManifest = [IO.File]::ReadAllText($conflictManifestPath) | ConvertFrom-Json -Depth 100
        $conflictManifest.managed_files = @($conflictManifest.managed_files | Where-Object { $_.path -notin $newPaths })
        [IO.File]::WriteAllText($conflictManifestPath, (($conflictManifest | ConvertTo-Json -Depth 100) + "`n"), $Utf8)
        $foreign = Join-Path $conflictRepo $newPaths[0]
        [IO.File]::Delete((Join-Path $conflictRepo $newPaths[1]))
        $before = Get-Hash $foreign
        $conflict = Invoke-Bootstrap $conflictRepo
        Assert-BootstrapError $conflict 'INSTALL_CONFLICT'
        Assert-Condition ((Get-Hash $foreign) -eq $before -and -not (Test-Path (Join-Path $conflictRepo $newPaths[1]))) 'Unowned maintenance path was overwritten or new path installed.' 'BOOTSTRAP_BUG'
    }

    Write-Output 'M5-RUNTIME_INTERACTION_ASSERTION: NOT AUTOMATED — run the documented two-command smoke from a normal Kael UI session; static/bootstrap assertions are not a runtime PASS.'

    $failed = @($Results | Where-Object Status -eq 'FAIL')
    foreach ($result in $Results) {
        Write-Output ($result.Id + '   ' + $result.Status)
        if ($result.Status -eq 'FAIL') { Write-Output ('CLASSIFICATION: ' + $result.Classification); Write-Output ('EVIDENCE: ' + $result.Evidence) }
    }
    if ($failed.Count -eq 0) {
        Write-Output ('WORKSPACES_RETAINED: ' + $RunRoot)
        Write-Output 'PHASE 4C QUALIFICATION: PASS'
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
}
