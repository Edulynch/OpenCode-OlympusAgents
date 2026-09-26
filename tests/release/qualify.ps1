[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$run = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('olympus-release-qualification-' + [guid]::NewGuid().ToString('N'))
$utf8 = [Text.UTF8Encoding]::new($false)
function Check([string]$id, [bool]$valid) {
    if (-not $valid) { throw "$id FAIL" }
    Write-Output "$id PASS"
}
function Install([string]$target) {
    $output = (& pwsh -NoProfile -File $installer -Version v0.2.0 -Target $target -SourceRoot $source 2>&1 | Out-String)
    [pscustomobject]@{ Text=$output; Code=$LASTEXITCODE }
}
try {
    [IO.Directory]::CreateDirectory($run) | Out-Null
    $target = Join-Path $run 'fresh-git-project'
    [IO.Directory]::CreateDirectory($target) | Out-Null
    [IO.File]::WriteAllText((Join-Path $target 'user-notes.txt'), "preserve me`n", $utf8)
    & git -C $target init --quiet
    & git -C $target -c user.name=Qualification -c user.email=qualification@example.invalid add -- user-notes.txt
    & git -C $target -c user.name=Qualification -c user.email=qualification@example.invalid commit --quiet -m 'qualification fixture'
    Check 'R0_GIT_FIXTURE' ($LASTEXITCODE -eq 0)

    $first = Install $target
    Check 'R1_FRESH_INSTALL' ($first.Code -eq 0 -and $first.Text -match '(?m)^READY\s*$' -and $first.Text -match 'OLYMPUS_INSTALL: v0.2.0 READY_OR_NO_CHANGES')
    $paths = @('opencode.jsonc', '.opencode/orchestrator-install.json', '.opencode/commands/maintain.md',
        '.opencode/plugins/olympus-activity/activity.ts', '.opencode/plugins/olympus-activity/tui.tsx')
    $paths += @('kael','veyra','orin','kovan','nox','vera','thales','maintenance' | ForEach-Object { ".opencode/agents/$_.md" })
    Check 'R2_ASSETS' (@($paths | Where-Object { -not (Test-Path -LiteralPath (Join-Path $target $_) -PathType Leaf) }).Count -eq 0)
    $manifest = Get-Content -LiteralPath (Join-Path $target '.opencode/orchestrator-install.json') -Raw | ConvertFrom-Json
    Check 'R2_MANIFEST_OWNERSHIP' ($manifest.schema_version -eq 1 -and $manifest.managed_files.Count -eq 12)

    Push-Location $target
    try {
        $agents = (& opencode debug agents 2>&1 | Out-String) | ConvertFrom-Json -Depth 100
        Check 'R3_EFFECTIVE_AGENTS' ($LASTEXITCODE -eq 0 -and @($agents | Where-Object { $_.id -in @('kael','veyra','orin','kovan','nox','vera','thales','maintenance') }).Count -eq 8)
        $plugins = (& opencode plugin list 2>&1 | Out-String)
        Check 'R9_HUD_DISCOVERY' ($LASTEXITCODE -eq 0 -and $plugins -match 'olympus-activity')
    } finally { Pop-Location }
    $expected = @{
        kael=@('gpt-6-sol','high','primary'); thales=@('gpt-6-sol','xhigh','subagent'); maintenance=@('gpt-6-sol','high','subagent')
        veyra=@('gpt-6-luna','max','subagent'); orin=@('gpt-6-luna','max','subagent'); kovan=@('gpt-6-luna','max','subagent')
        nox=@('gpt-6-luna','max','subagent'); vera=@('gpt-6-luna','max','subagent')
    }
    foreach ($id in $expected.Keys) {
        $agent = @($agents | Where-Object id -eq $id)
        Check "R5_MODEL_$id" ($agent.Count -eq 1 -and $agent[0].model.id -eq $expected[$id][0] -and
            $agent[0].model.variant -eq $expected[$id][1] -and $agent[0].mode -eq $expected[$id][2])
    }
    $m = @($agents | Where-Object id -eq maintenance)[0]
    Check 'R4_MAINTENANCE_HIDDEN' ($m.mode -eq 'subagent' -and $m.hidden -eq $true)
    $k = @($agents | Where-Object id -eq kovan)[0]
    $n = @($agents | Where-Object id -eq nox)[0]
    function Perm($a, [string]$action, [string]$effect) {
        @($a.permissions | Where-Object { $_.action -eq $action -and $_.resource -eq '*' -and $_.effect -eq $effect }).Count -gt 0
    }
    Check 'R10_TRUSTED_AUTONOMY' ((Perm $k shell allow) -and (Perm $k edit allow) -and
        (Perm $n shell allow) -and (Perm $n edit deny))
    $kaelText = [IO.File]::ReadAllText((Join-Path $target '.opencode/agents/kael.md'))
    Check 'R11_FAST_POLICY' ($kaelText -match 'MAX_ACTIVE_CHILDREN = 4' -and $kaelText -match 'minimum useful parallelism' -and
        $kaelText -match 'FAST' -and $kaelText -match 'balanced shards: 20 items / 4 workers = 5/5/5/5')

    $second = Install $target
    Check 'R6_REINSTALL' ($second.Code -eq 0 -and $second.Text -match '(?m)^NO_CHANGES\s*$')
    Check 'R12_UNRELATED_USER_FILE' ([IO.File]::ReadAllText((Join-Path $target 'user-notes.txt')) -eq "preserve me`n")
    $changed = Join-Path $target '.opencode/agents/kovan.md'
    [IO.File]::AppendAllText($changed, "`n# local drift`n", $utf8)
    $hash = (Get-FileHash -LiteralPath $changed -Algorithm SHA256).Hash
    $drift = Install $target
    Check 'R7_DRIFT_REFUSED' ($drift.Code -ne 0 -and $drift.Text -match 'MANAGED_FILE_DRIFT' -and
        (Get-FileHash -LiteralPath $changed -Algorithm SHA256).Hash -eq $hash)
    Check 'R12_UNRELATED_STILL_PRESERVED' ([IO.File]::ReadAllText((Join-Path $target 'user-notes.txt')) -eq "preserve me`n")
    $root = [IO.Path]::GetPathRoot($target)
    $unsafe = Install $root
    Check 'R8_FILESYSTEM_ROOT_REJECTED' ($unsafe.Code -ne 0 -and $unsafe.Text -match 'UNSAFE_TARGET|TARGET_NOT_GIT')
    Write-Output 'R8_REDIRECTS_CLOUD_CONTAINMENT: covered by Phase 4C target-security cases (run separately)'
    Write-Output 'RELEASE QUALIFICATION: PASS (local source fixture; remote tag and interactive UI not tested)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'RELEASE QUALIFICATION: FAIL'
    exit 1
} finally {
    if ($run -and (Test-Path -LiteralPath $run)) {
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop; break }
            catch {
                if ($attempt -eq 10) {
                    Write-Output 'CLEANUP_DEFERRED: OpenCode/Windows still holds the disposable fixture; remove after handles close.'
                    break
                }
                Start-Sleep -Milliseconds 500
            }
        }
    }
}
