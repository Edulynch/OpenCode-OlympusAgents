[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$run = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('thales-qualification-' + [guid]::NewGuid().ToString('N'))
$old = Join-Path $run 'v020-source'
$target = Join-Path $run 'target'
function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}
function Install([string]$root, [string]$repo, [switch]$DryRun) {
    $args = @('-NoProfile','-File',(Join-Path $root 'install.ps1'),'-SourceRoot',$root,'-Target',$repo)
    if ($DryRun) { $args += '-DryRun' }
    $output = (& pwsh @args 2>&1 | Out-String)
    [pscustomobject]@{ Code=$LASTEXITCODE; Output=$output }
}
function Digest([string]$p) { (Get-FileHash -LiteralPath (Join-Path $target $p) -Algorithm SHA256).Hash }
function Snapshot {
    $paths = @('src/modified.txt','docs/staged.txt','notes.txt','.serena/project.yml','.opencode/user-note.txt')
    $hashes = @($paths | ForEach-Object { Digest $_ }) -join ','
    $index = (& git -C $target diff --cached --binary | Out-String)
    $status = (& git -C $target status --porcelain=v1 -uall -- @($paths) | Out-String)
    "$hashes`n$index`n$status"
}
try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $kael = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/kael.md'))
    $thales = [IO.File]::ReadAllText((Join-Path $source '.opencode/agents/thales.md'))
    Check 'TH1_TH2_TH17_SINGLE_IDENTITY' ((Test-Path (Join-Path $source '.opencode/agents/thales.md')) -and
        -not (Test-Path (Join-Path $source '.opencode/agents/sorin.md')))
    Check 'TH3_TH4_ROUTING' ($kael -match 'resource: thales' -and $kael -notmatch '(?i)\bsorin\b' -and
        $kael -match 'Only veyra, orin, kovan, nox, vera, and thales are valid child role IDs')
    Check 'TH5_TH8_MODEL_PERMISSIONS' ($thales -match 'model: openai/gpt-6-sol#xhigh' -and
        @(@('shell','edit','subagent') | ForEach-Object { $thales -match ('(?s)action: ' + $_ + '\s+resource: "?\*"?\s+effect: deny') }) -notcontains $false)
    Check 'TH9_GATE' ($kael -match '## Diagnostic Gate' -and $kael -match 'evidence-backed condition' -and
        $kael -match 'Do not invoke Thales merely because a task is large, complex, or important')
    Check 'TH10_TH16_BUDGET_NEGATIVE' ($kael -match 'No third automatic consultation' -and
        $kael -match 'explicit user authorization' -and $kael -match 'not by itself a reason to invoke Thales')
    Check 'TH11_TH13_ITERATION' ($kael -match 'SAME native Thales session' -and
        $kael -match 'Topology: USER/ROOT → Kael → Thales → EVIDENCE_REQUEST → Kael → worker' -and
        $thales -match 'STATUS: EVIDENCE_REQUEST' -and $thales -match 'EXPECTED_DISCRIMINATION')
    Check 'TH14_TH15_BOUNDARIES' ($kael -match 'PENDING_OR_INDETERMINATE' -and $kael -match 'COMPLETION_UNCONFIRMED' -and
        $kael -match 'Kael → Maintenance remains DENIED' -and $thales -match '(?s)Never directly invoke.*?Maintenance')
    Check 'TH20_TH22_MODELS_CONCURRENCY' ($kael -match 'MAX_ACTIVE_CHILDREN = 4' -and
        $kael -match 'fan out up to four useful children' -and $kael -notmatch 'gpt-6-luna#fast')
    & git -C $source worktree add --detach $old 'v0.2.0^{commit}' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'v0.2.0 fixture checkout failed' }
    Check 'TH_ROLE_SEMANTICS' ($thales -match 'DO YOUR ROLE. DO NOT ABSORB ANOTHER ROLE TO SAVE A HANDOFF' -and
        $thales -match 'Reasoning is more than repeating worker summaries' -and
        $thales -match 'STATUS: ADVICE \| INCONCLUSIVE \| BLOCKED' -and
        $thales -match 'same native session')
    [IO.Directory]::CreateDirectory($target) | Out-Null
    & git -C $target init --quiet
    foreach ($path in @('src/modified.txt','docs/staged.txt')) {
        $file = Join-Path $target $path
        [IO.Directory]::CreateDirectory((Split-Path -Parent $file)) | Out-Null
        [IO.File]::WriteAllText($file,"original $path`n")
    }
    & git -C $target add -- src docs
    & git -C $target -c user.name=Qualification -c user.email=qualify@example.invalid commit --quiet -m fixture
    $installed = Install $old $target
    Check 'TH_UPGRADE_BASELINE' ($installed.Code -eq 0 -and
        (Test-Path (Join-Path $target '.opencode/agents/sorin.md')))
    [IO.File]::WriteAllText((Join-Path $target 'src/modified.txt'),"modified work`n")
    [IO.File]::WriteAllText((Join-Path $target 'docs/staged.txt'),"staged work`n")
    & git -C $target add -- docs/staged.txt
    foreach ($p in @('notes.txt','.serena/project.yml','.opencode/user-note.txt')) {
        $file = Join-Path $target $p
        [IO.Directory]::CreateDirectory((Split-Path -Parent $file)) | Out-Null
        [IO.File]::WriteAllText($file,"user owned $p`n")
    }
    $before = Snapshot
    $dry = Install $source $target -DryRun
    Check 'TH18_DRY_RUN' ($dry.Code -eq 0 -and $dry.Output -match 'FILES_TO_REMOVE:' -and
        $dry.Output -match '\.opencode/agents/sorin.md' -and (Test-Path (Join-Path $target '.opencode/agents/sorin.md')))
    $upgrade = Install $source $target
    if ($upgrade.Code -ne 0) { Write-Output $upgrade.Output }
    $manifest = [IO.File]::ReadAllText((Join-Path $target '.opencode/orchestrator-install.json')) | ConvertFrom-Json
    Check 'TH18_UPGRADE_OWNED_REMOVAL' ($upgrade.Code -eq 0 -and
        -not (Test-Path (Join-Path $target '.opencode/agents/sorin.md')) -and
        (Test-Path (Join-Path $target '.opencode/agents/thales.md')) -and
        'thales' -in @($manifest.managed_files | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_.path) }) -and
        'sorin' -notin @($manifest.managed_files | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_.path) }))
    Check 'TH19_UNRELATED_INDEX_AND_BYTES' ((Snapshot) -ceq $before)
    $again = Install $source $target
    Check 'TH_IDEMPOTENT' ($again.Code -eq 0 -and $again.Output -match '(?m)^NO_CHANGES\s*$')
    $fresh = Join-Path $run 'fresh'
    [IO.Directory]::CreateDirectory($fresh) | Out-Null
    & git -C $fresh init --quiet
    $freshResult = Install $source $fresh
    # The CLI must be queried from the installed project, not this source checkout.
    Push-Location $fresh
    try { $effective = (& opencode debug agents 2>$null | Out-String) }
    finally { Pop-Location }
    $agents = $effective | ConvertFrom-Json -Depth 100
    Check 'TH_FRESH_INSTALL' ($freshResult.Code -eq 0 -and
        (Test-Path (Join-Path $fresh '.opencode/agents/thales.md')) -and
        -not (Test-Path (Join-Path $fresh '.opencode/agents/sorin.md')) -and
        @($agents | Where-Object id -eq 'sorin').Count -eq 0 -and
        @($agents | Where-Object { $_.id -eq 'thales' -and $_.model.id -eq 'gpt-6-sol' -and $_.model.variant -eq 'xhigh' }).Count -eq 1)

    $drift = Join-Path $run 'drift'
    [IO.Directory]::CreateDirectory($drift) | Out-Null
    & git -C $drift init --quiet
    $oldResult = Install $old $drift
    Check 'TH_DRIFT_BASELINE' ($oldResult.Code -eq 0)
    $sorinPath = Join-Path $drift '.opencode/agents/sorin.md'
    [IO.File]::AppendAllText($sorinPath,"`n# user modification`n")
    $modifiedHash = (Get-FileHash -LiteralPath $sorinPath -Algorithm SHA256).Hash
    $blocked = Install $source $drift
    Check 'TH_DRIFT_REFUSED' ($blocked.Code -ne 0 -and $blocked.Output -match 'MANAGED_FILE_DRIFT' -and
        -not (Test-Path (Join-Path $drift '.opencode/agents/thales.md')) -and
        (Get-FileHash -LiteralPath $sorinPath -Algorithm SHA256).Hash -eq $modifiedHash)
    $foreign = Join-Path $run 'foreign'
    [IO.Directory]::CreateDirectory((Join-Path $foreign '.opencode/agents')) | Out-Null
    & git -C $foreign init --quiet
    $foreignSorin = Join-Path $foreign '.opencode/agents/sorin.md'
    [IO.File]::WriteAllText($foreignSorin,"user-owned historical file`n")
    $foreignResult = Install $source $foreign
    Check 'TH_UNOWNED_SORIN_REFUSED' ($foreignResult.Code -ne 0 -and $foreignResult.Output -match 'INSTALL_CONFLICT' -and
        (Test-Path $foreignSorin) -and -not (Test-Path (Join-Path $foreign '.opencode/agents/thales.md')))
    Write-Output 'THALES MIGRATION: PASS'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'THALES MIGRATION: FAIL'
    exit 1
} finally {
    if (Test-Path -LiteralPath $old) { & git -C $source worktree remove --force $old 2>$null | Out-Null }
    if (Test-Path -LiteralPath $run) {
        try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop }
        catch { Write-Output "CLEANUP_DEFERRED: $run" }
    }
}
