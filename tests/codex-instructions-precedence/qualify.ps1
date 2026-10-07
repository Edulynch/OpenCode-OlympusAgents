[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$run = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('olympus-codex-instructions-' + [guid]::NewGuid().ToString('N'))
$originalPath = $env:PATH
$utf8 = [Text.UTF8Encoding]::new($false)

function Check([string]$id, [bool]$condition) {
    if (-not $condition) { throw "$id FAIL" }
    Write-Output "$id PASS"
}

function New-Target([string]$name) {
    $target = Join-Path $run $name
    [IO.Directory]::CreateDirectory($target) | Out-Null
    & git -C $target init --quiet
    if ($LASTEXITCODE -ne 0) { throw "GIT_FIXTURE_INIT_FAIL: $name" }
    return $target
}

function Write-Fixture([string]$target, [string]$relative, [string]$contents) {
    $path = Join-Path $target $relative
    [IO.File]::WriteAllText($path, $contents, $utf8)
    return $path
}

function Hash-File([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }

function Snapshot([string]$target) {
    $root = (Resolve-Path -LiteralPath $target).Path.TrimEnd([char[]]@('\','/'))
    $prefix = $root + [IO.Path]::DirectorySeparatorChar
    @(
        Get-ChildItem -LiteralPath $root -Force -Recurse | Sort-Object FullName | ForEach-Object {
            $relative = $_.FullName.Substring($prefix.Length)
            if ($_.PSIsContainer) { $relative + ':DIRECTORY' }
            else { $relative + ':SHA256:' + (Hash-File $_.FullName) }
        }
    ) -join "`n"
}

function Run-Installer([string]$target, [string[]]$arguments) {
    $args = @('-NoProfile', '-File', $installer, '-SourceRoot', $source, '-Target', $target) + $arguments
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = (& pwsh @args 2>&1 | Out-String)
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousErrorActionPreference }
    return [pscustomobject]@{ Text=$output; Code=$code }
}

try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $mockBin = Join-Path $run 'mock-bin'
    [IO.Directory]::CreateDirectory($mockBin) | Out-Null
    Copy-Item -LiteralPath (Join-Path $source 'tests/release/fixtures/opencode.ps1') -Destination (Join-Path $mockBin 'opencode.ps1')
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), "@echo off`r`npwsh -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n", [Text.Encoding]::ASCII)
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $env:PATH

    # No root AGENTS file: Codex installs and verifies normally without a warning.
    $clean = New-Target 'no-agents'
    $cleanInstall = Run-Installer $clean @('-Harness', 'codex')
    $cleanSnapshot = Snapshot $clean
    $cleanVerify = Run-Installer $clean @('-Harness', 'codex', '-VerifyOnly')
    Check 'NO_AGENTS_INSTALL_AND_VERIFY_CONTRACT' ($cleanInstall.Code -eq 0 -and
        $cleanInstall.Text -match 'OLYMPUS_INSTALL: .* READY_OR_NO_CHANGES' -and
        $cleanInstall.Text -notmatch 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING' -and
        $cleanVerify.Code -eq 0 -and $cleanVerify.Text -match '(?m)^OLYMPUS_VERIFY: .* PASS\s*$' -and
        $cleanVerify.Text -notmatch 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING' -and (Snapshot $clean) -ceq $cleanSnapshot)

    # An empty override is ignored, so a non-empty AGENTS.md is still the active
    # higher-precedence root instruction. Both user files remain byte-for-byte intact.
    $agents = New-Target 'agents-md'
    $agentsFile = Write-Fixture $agents 'AGENTS.md' "# User project instructions`nKeep the existing workflow.`n"
    $emptyOverride = Write-Fixture $agents 'AGENTS.override.md' " `t`r`n"
    $agentsHash = Hash-File $agentsFile
    $emptyOverrideHash = Hash-File $emptyOverride
    $agentsInstall = Run-Installer $agents @('-Harness', 'codex')
    $agentsAfterInstall = (Hash-File $agentsFile) -ceq $agentsHash -and (Hash-File $emptyOverride) -ceq $emptyOverrideHash
    $agentsSnapshot = Snapshot $agents
    $agentsVerify = Run-Installer $agents @('-Harness', 'codex', '-VerifyOnly')
    Check 'AGENTS_MD_WARNING_NON_FATAL_AND_VERIFY_READ_ONLY' ($agentsInstall.Code -eq 0 -and
        $agentsInstall.Text -match 'OLYMPUS_INSTALL: .* READY_OR_NO_CHANGES' -and
        $agentsInstall.Text -match 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING: Codex gives non-empty root AGENTS\.md precedence over CODEX\.md' -and
        $agentsAfterInstall -and $agentsVerify.Code -eq 0 -and
        $agentsVerify.Text -match 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING: Codex gives non-empty root AGENTS\.md precedence over CODEX\.md' -and
        $agentsVerify.Text -match '(?m)^OLYMPUS_VERIFY: .* PASS\s*$' -and
        (Snapshot $agents) -ceq $agentsSnapshot -and
        (Hash-File $agentsFile) -ceq $agentsHash -and (Hash-File $emptyOverride) -ceq $emptyOverrideHash)

    # With both files non-empty, AGENTS.override.md wins; all also receives the
    # warning while retaining the normal dual-harness install/VerifyOnly result.
    $override = New-Target 'agents-override-md'
    $agentsFile = Write-Fixture $override 'AGENTS.md' "# Lower-priority user instructions`n"
    $overrideFile = Write-Fixture $override 'AGENTS.override.md' "# User override instructions`n"
    $agentsHash = Hash-File $agentsFile
    $overrideHash = Hash-File $overrideFile
    $overrideInstall = Run-Installer $override @('-Harness', 'all')
    $overrideSnapshot = Snapshot $override
    $overrideVerify = Run-Installer $override @('-Harness', 'all', '-VerifyOnly')
    Check 'AGENTS_OVERRIDE_PRECEDENCE_AND_ALL_CONTRACT' ($overrideInstall.Code -eq 0 -and
        $overrideInstall.Text -match 'OLYMPUS_INSTALL: .* READY_OR_NO_CHANGES' -and
        $overrideInstall.Text -match 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING: Codex gives non-empty root AGENTS\.override\.md precedence over CODEX\.md' -and
        $overrideInstall.Text -notmatch 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING: Codex gives non-empty root AGENTS\.md' -and
        $overrideVerify.Code -eq 0 -and $overrideVerify.Text -match '(?m)^OLYMPUS_VERIFY: .* PASS\s*$' -and
        $overrideVerify.Text -match 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING: Codex gives non-empty root AGENTS\.override\.md precedence over CODEX\.md' -and
        (Snapshot $override) -ceq $overrideSnapshot -and
        (Hash-File $agentsFile) -ceq $agentsHash -and (Hash-File $overrideFile) -ceq $overrideHash)

    # Empty root instruction files are omitted and do not trigger a warning.
    $empty = New-Target 'empty-agents'
    [void](Write-Fixture $empty 'AGENTS.md' '')
    [void](Write-Fixture $empty 'AGENTS.override.md' "`r`n`t ")
    $emptyInstall = Run-Installer $empty @('-Harness', 'codex')
    $emptyVerify = Run-Installer $empty @('-Harness', 'codex', '-VerifyOnly')
    Check 'EMPTY_AGENTS_FILES_OMITTED' ($emptyInstall.Code -eq 0 -and
        $emptyInstall.Text -notmatch 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING' -and
        $emptyVerify.Code -eq 0 -and $emptyVerify.Text -notmatch 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING' -and
        $emptyVerify.Text -match '(?m)^OLYMPUS_VERIFY: .* PASS\s*$')

    # OpenCode-only does not run the Codex precedence warning, even when a
    # non-empty AGENTS.md is present in the project root.
    $openCode = New-Target 'opencode-only'
    $openAgents = Write-Fixture $openCode 'AGENTS.md' "# User-owned OpenCode project instructions`n"
    $openAgentsHash = Hash-File $openAgents
    $openInstall = Run-Installer $openCode @('-Harness', 'opencode')
    $openSnapshot = Snapshot $openCode
    $openVerify = Run-Installer $openCode @('-Harness', 'opencode', '-VerifyOnly')
    Check 'OPENCODE_ONLY_NO_CODEX_WARNING' ($openInstall.Code -eq 0 -and
        $openInstall.Text -match 'OLYMPUS_INSTALL: .* READY_OR_NO_CHANGES' -and
        $openInstall.Text -notmatch 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING' -and
        $openVerify.Code -eq 0 -and $openVerify.Text -match '(?m)^OLYMPUS_VERIFY: .* PASS\s*$' -and
        $openVerify.Text -notmatch 'OLYMPUS_CODEX_INSTRUCTIONS_WARNING' -and
        (Snapshot $openCode) -ceq $openSnapshot -and (Hash-File $openAgents) -ceq $openAgentsHash)

    Write-Output 'CODEX INSTRUCTIONS PRECEDENCE QUALIFICATION: PASS (isolated project fixtures; managed-file VerifyOnly remains read-only)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'CODEX INSTRUCTIONS PRECEDENCE QUALIFICATION: FAIL'
    exit 1
} finally {
    $env:PATH = $originalPath
    if ($run -and (Test-Path -LiteralPath $run)) {
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop; break }
            catch {
                if ($attempt -eq 10) { Write-Output "CLEANUP_DEFERRED: $run"; break }
                Start-Sleep -Milliseconds 500
            }
        }
    }
}
