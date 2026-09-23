[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$installer = Join-Path $source 'install.ps1'
$run = Join-Path (Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) 'opencode') ('olympus-dirty-worktree-' + [guid]::NewGuid().ToString('N'))
$utf8 = [Text.UTF8Encoding]::new($false)
function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}
function Write-Fixture([string]$repo, [string]$path, [string]$text) {
    $full = Join-Path $repo $path
    [IO.Directory]::CreateDirectory((Split-Path -Parent $full)) | Out-Null
    [IO.File]::WriteAllText($full, $text, $utf8)
}
function Hash([string]$repo, [string]$path) { (Get-FileHash -LiteralPath (Join-Path $repo $path) -Algorithm SHA256).Hash }
function Fixture-Git([string]$repo, [string[]]$gitArgs) {
    $out = (& git -C $repo @gitArgs 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "Fixture git $($gitArgs -join ' ') failed: $out" }
    return $out
}
function New-Target([string]$name, [string[]]$committed = @()) {
    $repo = Join-Path $run $name
    [IO.Directory]::CreateDirectory($repo) | Out-Null
    Write-Fixture $repo 'baseline.txt' "baseline`n"
    foreach ($p in $committed) { Write-Fixture $repo $p "committed $p`n" }
    [void](Fixture-Git $repo @('init','--quiet'))
    [void](Fixture-Git $repo @('add','--','.'))
    [void](Fixture-Git $repo @('-c','user.name=Qualification','-c','user.email=qualification@example.invalid','commit','--quiet','-m','fixture'))
    return $repo
}
function Install([string]$repo, [string]$root = $source) {
    $out = (& pwsh -NoProfile -File (Join-Path $root 'install.ps1') -SourceRoot $root -Target $repo 2>&1 | Out-String)
    [pscustomobject]@{ Code=$LASTEXITCODE; Text=$out }
}
function Ready($result) { $result.Code -eq 0 -and $result.Text -match '(?m)^READY\s*$' -and $result.Text -match 'OLYMPUS_INSTALL: v0.1.2 READY_OR_NO_CHANGES' }
function Untracked([string]$repo, [string]$path) { (Fixture-Git $repo @('status','--porcelain=v1','-uall','--',$path)).Trim() -eq "?? $path" }
try {
    [IO.Directory]::CreateDirectory($run) | Out-Null

    $serena = New-Target 'serena'
    Write-Fixture $serena '.serena/.gitignore' "# local tool configuration`n"
    Write-Fixture $serena '.serena/project.yml' "project: local`n"
    $s1 = Hash $serena '.serena/.gitignore'; $s2 = Hash $serena '.serena/project.yml'
    Check 'D1_UNTRACKED_SERENA_FIXTURE' ((Untracked $serena '.serena/.gitignore') -and (Untracked $serena '.serena/project.yml'))
    $installed = Install $serena
    if (-not (Ready $installed)) { Write-Output "D1_INSTALL_OUTPUT (exit $($installed.Code)): $($installed.Text)" }
    Check 'D1_UNTRACKED_SERENA_ALLOWED' ((Ready $installed) -and (Hash $serena '.serena/.gitignore') -eq $s1 -and
        (Hash $serena '.serena/project.yml') -eq $s2 -and (Untracked $serena '.serena/.gitignore') -and
        (Untracked $serena '.serena/project.yml') -and (Test-Path (Join-Path $serena '.opencode/orchestrator-install.json')))

    $tracked = New-Target 'tracked' @('src/example.txt')
    Write-Fixture $tracked 'src/example.txt' "local modified source`n"
    $before = Hash $tracked 'src/example.txt'
    Check 'D2_UNRELATED_TRACKED_DIRTY_ALLOWED' ((Ready (Install $tracked)) -and (Hash $tracked 'src/example.txt') -eq $before -and
        (Fixture-Git $tracked @('status','--porcelain=v1','--','src/example.txt')).TrimEnd() -eq ' M src/example.txt')

    $staged = New-Target 'staged' @('docs/example.txt')
    Write-Fixture $staged 'docs/example.txt' "local staged document`n"
    [void](Fixture-Git $staged @('add','--','docs/example.txt'))
    $before = Hash $staged 'docs/example.txt'; $diff = Fixture-Git $staged @('diff','--cached','--binary','--','docs/example.txt')
    Check 'D3_UNRELATED_STAGED_ALLOWED' ((Ready (Install $staged)) -and (Hash $staged 'docs/example.txt') -eq $before -and
        $diff -eq (Fixture-Git $staged @('diff','--cached','--binary','--','docs/example.txt')) -and
        (Fixture-Git $staged @('status','--porcelain=v1','--','docs/example.txt')).Trim() -eq 'M  docs/example.txt')

    $untracked = New-Target 'untracked'
    Write-Fixture $untracked 'LOCAL_NOTES.txt' "private notes`n"
    $before = Hash $untracked 'LOCAL_NOTES.txt'
    Check 'D4_UNRELATED_UNTRACKED_ALLOWED' ((Ready (Install $untracked)) -and
        (Hash $untracked 'LOCAL_NOTES.txt') -eq $before -and (Untracked $untracked 'LOCAL_NOTES.txt'))

    $mixed = New-Target 'mixed' @('src/example.txt','docs/example.txt')
    Write-Fixture $mixed 'src/example.txt' "modified`n"
    Write-Fixture $mixed 'docs/example.txt' "staged`n"
    Write-Fixture $mixed 'LOCAL_NOTES.txt' "untracked`n"
    Write-Fixture $mixed '.opencode/user-note.txt' "personal opencode data`n"
    [void](Fixture-Git $mixed @('add','--','docs/example.txt'))
    $paths = @('src/example.txt','docs/example.txt','LOCAL_NOTES.txt','.opencode/user-note.txt')
    $hashes = @($paths | ForEach-Object { Hash $mixed $_ })
    $beforeStatus = Fixture-Git $mixed (@('status','--porcelain=v1','-uall','--') + $paths)
    $beforeIndex = Fixture-Git $mixed @('diff','--cached','--binary','--','docs/example.txt')
    Check 'D5_UNRELATED_STATE_PRESERVED' ((Ready (Install $mixed)) -and
        (@($paths | ForEach-Object { Hash $mixed $_ }) -join ',') -eq ($hashes -join ',') -and
        (Fixture-Git $mixed (@('status','--porcelain=v1','-uall','--') + $paths)) -eq $beforeStatus -and
        (Fixture-Git $mixed @('diff','--cached','--binary','--','docs/example.txt')) -eq $beforeIndex)
    $again = Install $mixed
    Check 'D8_REINSTALL_WITH_UNRELATED_DIRT_PASS' ($again.Code -eq 0 -and $again.Text -match '(?m)^NO_CHANGES\s*$' -and
        (@($paths | ForEach-Object { Hash $mixed $_ }) -join ',') -eq ($hashes -join ',') -and
        (Fixture-Git $mixed (@('status','--porcelain=v1','-uall','--') + $paths)) -eq $beforeStatus -and
        (Fixture-Git $mixed @('diff','--cached','--binary','--','docs/example.txt')) -eq $beforeIndex)

    $conflict = New-Target 'conflict'
    Write-Fixture $conflict '.opencode/agents/kael.md' "unowned agent`n"
    $before = Hash $conflict '.opencode/agents/kael.md'; $blocked = Install $conflict
    Check 'D6_MANAGED_DESTINATION_CONFLICT_BLOCKED' ($blocked.Code -ne 0 -and $blocked.Text -match 'INSTALL_CONFLICT' -and
        (Hash $conflict '.opencode/agents/kael.md') -eq $before -and -not (Test-Path (Join-Path $conflict '.opencode/orchestrator-install.json')))
    foreach ($config in @('opencode.json','.opencode/opencode.json','.opencode/opencode.jsonc')) {
        $target = New-Target ('foreign-' + ($config -replace '[./]','-'))
        Write-Fixture $target $config "foreign config`n"
        $before = Hash $target $config; $blocked = Install $target
        Check ('D6_FOREIGN_CONFIG_' + ($config -replace '[./]','_')) ($blocked.Code -ne 0 -and $blocked.Text -match 'INSTALL_CONFLICT' -and
            (Hash $target $config) -eq $before)
    }

    Write-Fixture $mixed '.opencode/agents/kovan.md' "managed drift`n"
    $before = Hash $mixed '.opencode/agents/kovan.md'; $blocked = Install $mixed
    Check 'D7_MANAGED_DRIFT_BLOCKED' ($blocked.Code -ne 0 -and $blocked.Text -match 'MANAGED_FILE_DRIFT' -and
        (Hash $mixed '.opencode/agents/kovan.md') -eq $before -and
        (@($paths | ForEach-Object { Hash $mixed $_ }) -join ',') -eq ($hashes -join ',') -and
        (Fixture-Git $mixed (@('status','--porcelain=v1','-uall','--') + $paths)) -eq $beforeStatus -and
        (Fixture-Git $mixed @('diff','--cached','--binary','--','docs/example.txt')) -eq $beforeIndex)

    # A local source copy simulates a newer managed asset without creating a release tag.
    $updateTarget = $staged
    $localSource = Join-Path $run 'update-source'
    foreach ($p in @('install.ps1','scripts/bootstrap.ps1')) {
        $dest = Join-Path $localSource $p
        [IO.Directory]::CreateDirectory((Split-Path -Parent $dest)) | Out-Null
        [IO.File]::Copy((Join-Path $source $p), $dest)
    }
    $manifest = [IO.File]::ReadAllText((Join-Path $updateTarget '.opencode/orchestrator-install.json')) | ConvertFrom-Json
    foreach ($entry in $manifest.managed_files) {
        $dest = Join-Path $localSource $entry.path
        [IO.Directory]::CreateDirectory((Split-Path -Parent $dest)) | Out-Null
        [IO.File]::Copy((Join-Path $source $entry.path), $dest)
    }
    [IO.File]::AppendAllText((Join-Path $localSource '.opencode/agents/kovan.md'), "`n# local update fixture`n", $utf8)
    $before = Hash $updateTarget 'docs/example.txt'
    $diff = Fixture-Git $updateTarget @('diff','--cached','--binary','--','docs/example.txt')
    $update = Install $updateTarget $localSource
    Check 'D9_UPDATE_WITH_UNRELATED_DIRT_PASS' ((Ready $update) -and
        (Hash $updateTarget 'docs/example.txt') -eq $before -and
        (Fixture-Git $updateTarget @('diff','--cached','--binary','--','docs/example.txt')) -eq $diff -and
        (Hash $updateTarget '.opencode/agents/kovan.md') -eq (Hash $localSource '.opencode/agents/kovan.md'))
    Write-Output 'DIRTY WORKTREE QUALIFICATION: PASS (disposable local-source installer fixtures)'
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'DIRTY WORKTREE QUALIFICATION: FAIL'
    exit 1
} finally {
    if (Test-Path -LiteralPath $run) {
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            try { Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop; break }
            catch {
                if ($attempt -eq 10) { Write-Output "CLEANUP_DEFERRED: $run"; break }
                Start-Sleep -Milliseconds 500
            }
        }
    }
}
