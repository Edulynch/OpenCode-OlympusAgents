[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$pwsh = Join-Path $PSHOME 'pwsh.exe'
$run = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('opencode\olympus-worktree-activation-' + [guid]::NewGuid().ToString('N'))
$main = Join-Path $run 'main'
$treeRoot = Join-Path $run 'trees'
$baselineSource = Join-Path $run 'v0.4.4-source'
$baselineArchive = Join-Path $run 'v0.4.4.zip'
$first = Join-Path $treeRoot 'checkout-b'
$second = Join-Path $treeRoot 'checkout-c'
$negative = Join-Path $treeRoot 'checkout-negative'
$mockBin = Join-Path $run 'mock-bin'
$originalPath = [Environment]::GetEnvironmentVariable('PATH','Process')
$originalBase = [Environment]::GetEnvironmentVariable('OPENCODE_WORKTREE_BASE','Process')
$originalTarget = [Environment]::GetEnvironmentVariable('OPENCODE_WORKTREE_PATH','Process')
$utf8 = [Text.UTF8Encoding]::new($false)

function Check([string]$Id, [bool]$Condition, [string]$Evidence = '') {
    if (-not $Condition) {
        if ($Evidence) { throw "$Id FAIL`n$Evidence" }
        throw "$Id FAIL"
    }
    Write-Output "$Id PASS"
}

function Run-Git([string]$Directory, [string[]]$Arguments) {
    $output = @(& git -C $Directory @Arguments 2>&1)
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "GIT_FIXTURE_FAILED: git $($Arguments -join ' ') in $Directory`n$($output | Out-String)" }
    return $output
}

function Run-Script([string]$Path, [string[]]$Arguments = @()) {
    $output = @(& $pwsh -NoProfile -File $Path @Arguments 2>&1)
    $code = $LASTEXITCODE
    return [pscustomobject]@{ Code=$code; Text=($output | Out-String) }
}

function Sha-File([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-InstalledManifest([string]$Directory) {
    $manifestPath = Join-Path $Directory '.opencode/orchestrator-install.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { return $false }
    $manifest = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json -Depth 100
    foreach ($entry in @($manifest.managed_files)) {
        $path = Join-Path $Directory ([string]$entry.path -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
            (Sha-File $path) -cne ([string]$entry.sha256).ToLowerInvariant()) { return $false }
    }
    return $true
}

function Get-Effective-Agent-Ids([string]$Directory) {
    Push-Location -LiteralPath $Directory
    try {
        $json = (& opencode debug agents 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) { throw "OPENCode_AGENT_DISCOVERY_FAILED: $Directory`n$json" }
        return @($json | ConvertFrom-Json -Depth 100 | ForEach-Object { [string]$_.id })
    } finally { Pop-Location }
}

function Invoke-Worktree-Setup([string]$Target) {
    $env:OPENCODE_WORKTREE_BASE = $main
    $env:OPENCODE_WORKTREE_PATH = $Target
    $scriptPath = Join-Path $main '.opencode/scripts/worktree-setup.ps1'
    return Run-Script $scriptPath
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'PLATFORM_UNQUALIFIED: OpenCode V2 worktree startup qualification is Windows-only.'
    }
    [IO.Directory]::CreateDirectory($run) | Out-Null
    [IO.Directory]::CreateDirectory($treeRoot) | Out-Null
    [IO.Directory]::CreateDirectory($mockBin) | Out-Null

    [IO.Directory]::CreateDirectory($main) | Out-Null
    Run-Git $main @('init','--quiet') | Out-Null
    Run-Git $main @('config','user.name','Olympus Worktree Test') | Out-Null
    Run-Git $main @('config','user.email','olympus-worktree-test@example.invalid') | Out-Null
    [IO.File]::WriteAllText((Join-Path $main 'README.md'), "Disposable worktree fixture.`n", $utf8)
    Run-Git $main @('add','README.md') | Out-Null
    Run-Git $main @('commit','--quiet','-m','fixture') | Out-Null

    Copy-Item -LiteralPath (Join-Path $root 'tests/release/fixtures/opencode.ps1') -Destination (Join-Path $mockBin 'opencode.ps1')
    $wrapper = "@echo off`r`n`"$pwsh`" -NoProfile -File `"%~dp0opencode.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
    [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'), $wrapper, [Text.Encoding]::ASCII)
    $env:PATH = $mockBin + [IO.Path]::PathSeparator + $originalPath

    [IO.Directory]::CreateDirectory($baselineSource) | Out-Null
    Run-Git $root @('archive','--format=zip','--output',$baselineArchive,'v0.4.4') | Out-Null
    Expand-Archive -LiteralPath $baselineArchive -DestinationPath $baselineSource -Force
    $baselineInstall = Run-Script (Join-Path $baselineSource 'install.ps1') @('-Target',$main,'-Harness','opencode','-SourceRoot',$baselineSource)
    Check 'V044_MAIN_PROJECT_INSTALL' ($baselineInstall.Code -eq 0 -and $baselineInstall.Text -match 'OLYMPUS_INSTALL: v0.4.4') $baselineInstall.Text
    $sourceManifestPath = Join-Path $main '.opencode/orchestrator-install.json'
    Check 'V044_MANIFEST_OWNS_PROJECT_FILES' ((Get-Content -LiteralPath $sourceManifestPath -Raw | ConvertFrom-Json).managed_files.Count -gt 0 -and
        (Get-Content -LiteralPath $sourceManifestPath -Raw | ConvertFrom-Json).managed_files.path -notcontains '.opencode/scripts/worktree-setup.ps1')

    Run-Git $main @('worktree','add','--quiet','-b','worktree-activation-b',$first,'HEAD') | Out-Null
    Run-Git $main @('worktree','add','--quiet','-b','worktree-activation-c',$second,'HEAD') | Out-Null
    Check 'LINKED_WORKTREE_GIT_FILE' ((Get-Item -LiteralPath (Join-Path $first '.git') -Force).PSIsContainer -eq $false -and
        (Get-Item -LiteralPath (Join-Path $second '.git') -Force).PSIsContainer -eq $false)

    Check 'V044_REPRODUCES_MISSING_WORKTREE_INSTALL' (-not (Test-Path (Join-Path $first 'opencode.jsonc')) -and
        -not (Test-Path (Join-Path $first '.opencode/agents/kael.md')) -and
        -not (Test-Path (Join-Path $first '.opencode/orchestrator-install.json')) -and
        -not (Test-Path (Join-Path $second 'opencode.jsonc')) -and
        -not (Test-Path (Join-Path $second '.opencode/agents/kael.md')) -and
        -not (Test-Path (Join-Path $second '.opencode/orchestrator-install.json')))
    Check 'MISSING_RESOURCES_MEAN_NO_KAEL_DISCOVERY' (@(Get-Effective-Agent-Ids $first).Count -eq 0)

    # Upgrade the project checkout from the immutable stable baseline to the
    # candidate installer before using its opted-in native startup hook.
    $candidateUpgrade = Run-Script (Join-Path $root 'install.ps1') @('-Target',$main,'-Harness','opencode','-SourceRoot',$root,'-Version','v0.4.4')
    Check 'V044_TO_CANDIDATE_UPGRADE' ($candidateUpgrade.Code -eq 0 -and
        (Get-Content -LiteralPath $sourceManifestPath -Raw | ConvertFrom-Json).managed_files.path -contains '.opencode/scripts/worktree-setup.ps1') $candidateUpgrade.Text

    $userOwnedFile = Join-Path $first '.opencode/user-owned.md'
    [IO.Directory]::CreateDirectory((Split-Path -Parent $userOwnedFile)) | Out-Null
    [IO.File]::WriteAllText($userOwnedFile, "Preserve this user-owned file.`n", $utf8)
    $userOwnedHash = Sha-File $userOwnedFile
    $setupB = Invoke-Worktree-Setup $first
    Check 'WORKTREE_B_PROVISIONED' ($setupB.Code -eq 0 -and $setupB.Text -match 'OLYMPUS_WORKTREE_SETUP: PASS') $setupB.Text
    Check 'WORKTREE_B_MANIFEST_HASHES_AND_KAEL' ((Assert-InstalledManifest $first) -and
        ((Get-Content -LiteralPath (Join-Path $first 'opencode.jsonc') -Raw) -match '"default_agent":\s*"kael"') -and
        ('kael' -in @(Get-Effective-Agent-Ids $first)))
    Check 'WORKTREE_B_USER_FILE_PRESERVED' ((Sha-File $userOwnedFile) -ceq $userOwnedHash)

    [IO.File]::WriteAllText((Join-Path $first 'checkout-only.txt'), 'B', $utf8)
    [IO.File]::WriteAllText((Join-Path $second 'checkout-only.txt'), 'C', $utf8)
    $setupC = Invoke-Worktree-Setup $second
    Check 'WORKTREE_C_PROVISIONED' ($setupC.Code -eq 0 -and $setupC.Text -match 'OLYMPUS_WORKTREE_SETUP: PASS') $setupC.Text
    Check 'WORKTREE_C_MANIFEST_HASHES_AND_KAEL' ((Assert-InstalledManifest $second) -and
        ((Get-Content -LiteralPath (Join-Path $second 'opencode.jsonc') -Raw) -match '"default_agent":\s*"kael"') -and
        ('kael' -in @(Get-Effective-Agent-Ids $second)))
    Check 'WORKTREE_FILES_AND_USER_ASSETS_STAY_ISOLATED' ((Get-Content (Join-Path $first 'checkout-only.txt') -Raw) -ceq 'B' -and
        (Get-Content (Join-Path $second 'checkout-only.txt') -Raw) -ceq 'C' -and
        -not (Test-Path (Join-Path $second '.opencode/user-owned.md')))

    $idempotent = Invoke-Worktree-Setup $first
    Check 'REPEATED_PROVISIONING_IS_READ_ONLY' ($idempotent.Code -eq 0 -and $idempotent.Text -match 'created=0') $idempotent.Text

    $missingKael = Join-Path $second '.opencode/agents/kael.md'
    [IO.File]::Delete($missingKael)
    $conflictConfig = Join-Path $second 'opencode.jsonc'
    [IO.File]::WriteAllText($conflictConfig, "{`"user_owned`": true}`n", $utf8)
    $conflictHash = Sha-File $conflictConfig
    $conflict = Invoke-Worktree-Setup $second
    Check 'USER_CONFLICT_BLOCKS_WITHOUT_PARTIAL_COPY' ($conflict.Code -ne 0 -and $conflict.Text -match 'WORKTREE_SETUP_CONFLICT' -and
        -not (Test-Path -LiteralPath $missingKael) -and (Sha-File $conflictConfig) -ceq $conflictHash) $conflict.Text

    $firstAgent = Join-Path $main '.opencode/agents/kael.md'
    $originalAgentBytes = [IO.File]::ReadAllBytes($firstAgent)
    try {
        [IO.File]::AppendAllText($firstAgent, "`n# intentional drift probe`n", $utf8)
        $drift = Invoke-Worktree-Setup $first
        Check 'SOURCE_DRIFT_BLOCKS_SETUP' ($drift.Code -ne 0 -and $drift.Text -match 'WORKTREE_SETUP_SOURCE_DRIFT') $drift.Text
    } finally { [IO.File]::WriteAllBytes($firstAgent, $originalAgentBytes) }


    # Exercise manifest and config negatives against a fresh linked checkout:
    # a failed preflight must not copy even one managed file.
    Run-Git $main @('worktree','add','--quiet','--detach',$negative,'HEAD') | Out-Null
    $negativeMarker = Join-Path $negative 'keep-user-file.txt'
    [IO.File]::WriteAllText($negativeMarker, 'unchanged', $utf8)
    $negativeMarkerHash = Sha-File $negativeMarker
    $originalManifestBytes = [IO.File]::ReadAllBytes($sourceManifestPath)
    $unexpectedSource = Join-Path $main '.opencode/agents/unexpected.md'
    try {
        # A missing managed agent must fail despite every supplied hash being valid.
        $missingManifest = [Text.Encoding]::UTF8.GetString($originalManifestBytes) | ConvertFrom-Json -Depth 100
        $missingManifest.managed_files = @($missingManifest.managed_files | Where-Object { $_.path -ne '.opencode/agents/kael.md' })
        [IO.File]::WriteAllText($sourceManifestPath, ($missingManifest | ConvertTo-Json -Depth 100), $utf8)
        $missing = Invoke-Worktree-Setup $negative
        Check 'INCOMPLETE_INVENTORY_REJECTED_WITHOUT_WRITES' ($missing.Code -ne 0 -and
            $missing.Text -match 'WORKTREE_SETUP_MANIFEST_INVALID' -and
            -not (Test-Path -LiteralPath (Join-Path $negative 'opencode.jsonc')) -and
            -not (Test-Path -LiteralPath (Join-Path $negative '.opencode/orchestrator-install.json')) -and
            (Sha-File $negativeMarker) -ceq $negativeMarkerHash) $missing.Text

        # A real extra source asset with a matching SHA previously passed.
        [IO.File]::WriteAllBytes($unexpectedSource, [IO.File]::ReadAllBytes((Join-Path $main '.opencode/agents/kael.md')))
        $extraManifest = [Text.Encoding]::UTF8.GetString($originalManifestBytes) | ConvertFrom-Json -Depth 100
        $extraManifest.managed_files = @($extraManifest.managed_files) +
            @([pscustomobject]@{ path='.opencode/agents/unexpected.md'; sha256=(Sha-File $unexpectedSource) })
        [IO.File]::WriteAllText($sourceManifestPath, ($extraManifest | ConvertTo-Json -Depth 100), $utf8)
        $extra = Invoke-Worktree-Setup $negative
        Check 'FOREIGN_MANAGED_ENTRY_REJECTED_WITHOUT_WRITES' ($extra.Code -ne 0 -and
            $extra.Text -match 'WORKTREE_SETUP_MANIFEST_INVALID' -and
            -not (Test-Path -LiteralPath (Join-Path $negative 'opencode.jsonc')) -and
            -not (Test-Path -LiteralPath (Join-Path $negative '.opencode/orchestrator-install.json')) -and
            (Sha-File $negativeMarker) -ceq $negativeMarkerHash) $extra.Text
    } finally {
        [IO.File]::WriteAllBytes($sourceManifestPath, $originalManifestBytes)
        if (Test-Path -LiteralPath $unexpectedSource) { [IO.File]::Delete($unexpectedSource) }
    }

    # Match the bootstrap's three conflicting config locations.
    foreach ($alternative in @('opencode.json', '.opencode/opencode.json', '.opencode/opencode.jsonc')) {
        $alternativePath = Join-Path $negative ($alternative -replace '/', [IO.Path]::DirectorySeparatorChar)
        [IO.Directory]::CreateDirectory((Split-Path -Parent $alternativePath)) | Out-Null
        [IO.File]::WriteAllText($alternativePath, "{`"user_owned`": true}`n", $utf8)
        try {
            $blocked = Invoke-Worktree-Setup $negative
            $label = 'ALTERNATE_CONFIG_' + ($alternative -replace '[^a-zA-Z0-9]', '_')
            Check ($label + '_REJECTED_WITHOUT_WRITES') ($blocked.Code -ne 0 -and
                $blocked.Text -match 'WORKTREE_SETUP_CONFLICT' -and
                -not (Test-Path -LiteralPath (Join-Path $negative 'opencode.jsonc')) -and
                -not (Test-Path -LiteralPath (Join-Path $negative '.opencode/orchestrator-install.json')) -and
                (Sha-File $negativeMarker) -ceq $negativeMarkerHash) $blocked.Text
        } finally {
            if (Test-Path -LiteralPath $alternativePath) { [IO.File]::Delete($alternativePath) }
        }
    }

    $negativeValid = Invoke-Worktree-Setup $negative
    Check 'VALID_ROSTER_AFTER_NEGATIVE_PROBES' ($negativeValid.Code -eq 0 -and
        (Assert-InstalledManifest $negative) -and (Sha-File $negativeMarker) -ceq $negativeMarkerHash) $negativeValid.Text

    Write-Output 'WORKTREE ACTIVATION QUALIFICATION: PASS (linked worktrees; strict inventory and config conflicts; no live model request)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'WORKTREE ACTIVATION QUALIFICATION: FAIL'
    exit 1
} finally {
    [Environment]::SetEnvironmentVariable('PATH',$originalPath,'Process')
    if ($null -eq $originalBase) { Remove-Item Env:OPENCODE_WORKTREE_BASE -ErrorAction SilentlyContinue }
    else { [Environment]::SetEnvironmentVariable('OPENCODE_WORKTREE_BASE',$originalBase,'Process') }
    if ($null -eq $originalTarget) { Remove-Item Env:OPENCODE_WORKTREE_PATH -ErrorAction SilentlyContinue }
    else { [Environment]::SetEnvironmentVariable('OPENCODE_WORKTREE_PATH',$originalTarget,'Process') }
    if ($run -and (Test-Path -LiteralPath $run)) {
        if (Test-Path -LiteralPath $main -PathType Container) {
            foreach ($tree in @($negative, $second, $first)) {
                if (Test-Path -LiteralPath $tree -PathType Container) {
                    & git -C $main worktree remove --force $tree 2>$null | Out-Null
                }
            }
        }
        Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction SilentlyContinue
    }
}
