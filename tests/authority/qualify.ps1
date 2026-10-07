[CmdletBinding()]
param([ValidateSet('Both','Offline','Runtime')][string]$QualificationSlice = 'Both')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
function Text([string]$path) { [IO.File]::ReadAllText((Join-Path $root $path)) }
function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}

function Covers([string]$scope, [string]$path) {
    $s = $scope.Replace('\','/').TrimEnd('/')
    $p = $path.Replace('\','/').TrimStart('/')
    if ($s.EndsWith('/**')) { return $p.StartsWith($s.Substring(0, $s.Length - 2), [StringComparison]::OrdinalIgnoreCase) }
    return $p.Equals($s, [StringComparison]::OrdinalIgnoreCase)
}

function Is-OlympusOwned([string]$path, [string[]]$manifestPaths = @()) {
    $p = $path.Replace('\','/').TrimStart('/').ToLowerInvariant()
    $fixed = @('.opencode/agents/', '.opencode/commands/maintain.md',
        '.opencode/plugins/olympus-activity/', '.opencode/orchestrator-install.json',
        '.opencode/opencode.json', '.opencode/opencode.jsonc', '.codex/', 'CODEX.md',
        'olympus/', 'scripts/render_harnesses.py', 'opencode.jsonc', 'opencode.json')
    if (@($fixed | Where-Object { $p.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) }).Count -gt 0) { return $true }
    foreach ($entry in $manifestPaths) {
        $declared = $entry.Replace('\','/').TrimStart('/').ToLowerInvariant()
        if ($p -eq $declared -or $p.StartsWith($declared.TrimEnd('/') + '/', [StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Decide([string]$agent, [string]$operation, [string]$path, [string]$normalScope,
                 [string]$repositoryRoot, $grant, [bool]$taskActive = $true,
                 [bool]$projectOwned = $true, [bool]$explicitProhibition = $false,
                 [string[]]$manifestPaths = @(), [string]$nativeDecision = 'ALLOW') {
    if ($explicitProhibition) { return [pscustomobject]@{ decision='DENY'; question=0; reason='USER_PROHIBITION' } }
    if (Is-OlympusOwned $path $manifestPaths) { return [pscustomobject]@{ decision='DENY'; question=0; reason='OLYMPUS_OWNED' } }
    if (-not $projectOwned) { return [pscustomobject]@{ decision='DENY'; question=0; reason='OWNERSHIP_UNPROVEN' } }
    $normal = Covers $normalScope $path
    $valid = $false
    if ($null -ne $grant) {
        $valid = $taskActive -and $grant.agent -ceq $agent -and $grant.operation -ceq $operation -and
            $grant.repository_root -ceq $repositoryRoot -and $grant.lifetime -ceq 'current_task' -and
            $grant.task_id -ceq 'task-7' -and $grant.permission_mode -in @('ALLOW','NATIVE_ASK') -and
            (Covers $grant.scope $path)
    }
    if ($normal -and $nativeDecision -eq 'ALLOW') {
        return [pscustomobject]@{ decision='ALLOW'; question=0; reason='NORMAL_SCOPE' }
    }
    if ($nativeDecision -eq 'DENY') { return [pscustomobject]@{ decision='DENY'; question=0; reason='NATIVE_DENY' } }
    if ($valid) {
        if ($grant.permission_mode -eq 'NATIVE_ASK' -and $nativeDecision -eq 'ASK') {
            return [pscustomobject]@{ decision='NATIVE_ASK'; question=0; reason='EXACT_NATIVE_ASK_GRANT' }
        }
        if ($grant.permission_mode -eq 'ALLOW' -and $nativeDecision -eq 'ALLOW') {
            return [pscustomobject]@{ decision='ALLOW'; question=0; reason='EXACT_ALLOW_GRANT' }
        }
        return [pscustomobject]@{ decision='DENY'; question=0; reason='GRANT_PERMISSION_MODE_MISMATCH' }
    }
    if ($null -ne $grant -and (-not $taskActive -or $grant.lifetime -ne 'current_task' -or $grant.task_id -ne 'task-7')) {
        return [pscustomobject]@{ decision='DENY'; question=0; reason='GRANT_EXPIRED_OR_WRONG_TASK' }
    }
    [pscustomobject]@{ decision='NEED_AUTHORITY'; question=0; reason='SCOPE_NOT_DELEGATED' }
}

function New-Grant([string]$agent, [string]$operation, [string]$scope, [string]$rootPath,
                    [string]$permissionMode = 'ALLOW', [string]$lifetime = 'current_task') {
    [pscustomobject]@{ agent=$agent; operation=$operation; scope=$scope; repository_root=$rootPath;
        permission_mode=$permissionMode; lifetime=$lifetime; task_id='task-7' }
}

function Synthetic-ToolFlow([string]$decision, [string]$nativeOutcome = 'NONE') {
    # Deterministic policy model only: it does not invoke OpenCode or assert that a UI appeared.
    if ($decision -eq 'ALLOW') {
        return [pscustomobject]@{ attempted=$true; pending=$false; executed=$true; continue=$true; question=0; fallback=$false; retry=$false }
    }
    if ($decision -eq 'NATIVE_ASK') {
        if ($nativeOutcome -eq 'APPROVE_ONCE') {
            return [pscustomobject]@{ attempted=$true; pending=$false; executed=$true; continue=$true; question=0; fallback=$false; retry=$false }
        }
        if ($nativeOutcome -in @('REJECT','CANCEL')) {
            return [pscustomobject]@{ attempted=$true; pending=$false; executed=$false; continue=$false; question=0; fallback=$false; retry=$false }
        }
        return [pscustomobject]@{ attempted=$true; pending=$true; executed=$false; continue=$false; question=0; fallback=$false; retry=$false }
    }
    [pscustomobject]@{ attempted=$false; pending=$false; executed=$false; continue=$false; question=0; fallback=$false; retry=$false }
}

function Classify-NewScope([string]$nativeDecision, [bool]$projectOwned = $true,
                           [bool]$explicitProhibition = $false, [bool]$roleAllowed = $true,
                           [bool]$destructive = $false) {
    if ($explicitProhibition -or -not $projectOwned -or -not $roleAllowed -or $destructive -or $nativeDecision -eq 'DENY') { return 'DENY' }
    if ($nativeDecision -eq 'ASK') { return 'NATIVE_ASK' }
    if ($nativeDecision -eq 'ALLOW') { return 'ALLOW' }
    'DENY'
}

function Read-NativeRules([string]$agentText, [object[]]$globalRules) {
    $header = [regex]::Match($agentText, '(?s)\A---\r?\n(.*?)\r?\n---').Groups[1].Value
    $rules = [Collections.Generic.List[object]]::new()
    foreach ($m in [regex]::Matches($header, '(?ms)^\s{2}- action:\s*(?<action>[^\r\n]+)\r?\n\s{4}resource:\s*"?(?<resource>[^"\r\n]+)"?\r?\n\s{4}effect:\s*(?<effect>allow|ask|deny)\s*$')) {
        $rules.Add([pscustomobject]@{ action=$m.Groups['action'].Value.Trim(); resource=$m.Groups['resource'].Value.Trim(); effect=$m.Groups['effect'].Value.Trim() })
    }
    return @($globalRules) + @($rules.ToArray())
}

function Matches-Glob([string]$pattern, [string]$resource) {
    $regex = [regex]::Escape($pattern).Replace('\*', '.*').Replace('\?', '.')
    return [regex]::IsMatch($resource, '^' + $regex + '$', [Text.RegularExpressions.RegexOptions]::IgnoreCase)
}

function Native-Decision([object[]]$rules, [string]$action, [string]$resource,
                         [bool]$explicitProhibition = $false) {
    if ($explicitProhibition) { return 'DENY' }
    $decision = 'ALLOW'
    # OpenCode permission patterns use last matching rule; agent rules follow and
    # take precedence over global configuration.
    foreach ($rule in $rules) {
        if (($rule.action -eq $action -or $rule.action -eq '*') -and (Matches-Glob $rule.resource $resource)) {
            $decision = $rule.effect.ToUpperInvariant()
        }
    }
    return $decision
}

function Write-Decision([string]$nativeDecision, [string]$approval = 'NONE') {
    if ($nativeDecision -eq 'ALLOW') { return $true }
    if ($nativeDecision -eq 'DENY') { return $false }
    return $approval -eq 'APPROVE_ONCE'
}

function New-PermissionReport([bool]$attempted, [string]$execution, [string]$toolResult,
                              [string]$uiObservation = 'NOT_OBSERVABLE',
                              [string]$permissionDecision = 'NOT_OBSERVABLE',
                              [string]$externalObservation = 'NONE') {
    # Reporting records only supplied evidence; execution result never infers UI or human action.
    [pscustomobject]@{
        TOOL_ATTEMPT = $(if ($attempted) { 'ATTEMPTED' } else { 'NOT_ATTEMPTED' })
        TOOL_EXECUTION = $execution
        TOOL_RESULT = $toolResult
        NATIVE_PERMISSION_UI = $uiObservation
        NATIVE_PERMISSION_DECISION = $permissionDecision
        USER_CONFIRMED_EXTERNAL_OBSERVATION = $externalObservation
    }
}

function Compact-Evidence([string]$value) {
    if ([string]::IsNullOrWhiteSpace($value)) { return '<empty>' }
    $compact = ($value -replace '\s+', ' ').Trim()
    if ($compact.Length -gt 240) { $compact = $compact.Substring(0, 240) + '...' }
    return $compact
}

function Inspect-EffectiveRules([object]$runtimeExit, [string]$runtimeJson,
                                [string]$runtimeStderr = '', [string]$invocationError = '') {
    $failures = [Collections.Generic.List[string]]::new()
    $runtimeAgents = @()
    $runtimeJsonParseable = $false
    $runtimeJsonParseError = ''
    $runtimeJsonRootType = 'UNAVAILABLE'
    $runtimeJsonRootIsArray = $false
    try {
        $runtimeDocument = ConvertFrom-Json -InputObject $runtimeJson -Depth 100 -NoEnumerate -ErrorAction Stop
        $runtimeJsonParseable = $true
        if ($null -eq $runtimeDocument) {
            $runtimeJsonRootType = 'null'
        } else {
            $runtimeJsonRootType = $runtimeDocument.GetType().FullName
        }
        if ($runtimeDocument -is [array]) {
            $runtimeAgents = $runtimeDocument
            $runtimeJsonRootIsArray = $true
        }
    } catch {
        $runtimeJsonParseError = $_.Exception.Message
    }

    if (-not [string]::IsNullOrWhiteSpace($invocationError)) {
        $failures.Add('runtime_invocation_error=' + (Compact-Evidence $invocationError))
    }
    if ($null -eq $runtimeExit) {
        $failures.Add('runtime_exit=<unavailable>')
    } elseif ([int]$runtimeExit -ne 0) {
        $failures.Add("runtime_exit=$runtimeExit")
    }
    if (-not $runtimeJsonParseable) {
        $failures.Add('json_parseable=false; json_error=' + (Compact-Evidence $runtimeJsonParseError))
    } elseif (-not $runtimeJsonRootIsArray) {
        $failures.Add("json_root=$runtimeJsonRootType (expected array)")
    }

    $kovanMatches = [Collections.Generic.List[object]]::new()
    if ($runtimeJsonRootIsArray) {
        foreach ($candidate in $runtimeAgents) {
            if ($null -eq $candidate) { continue }
            $idProperty = $candidate.PSObject.Properties['id']
            if ($null -ne $idProperty -and $idProperty.Value -eq 'kovan') {
                $kovanMatches.Add($candidate)
            }
        }
    }
    $kovanCount = $kovanMatches.Count
    if ($kovanCount -eq 0) {
        $failures.Add('kovan=missing (matches=0)')
    } elseif ($kovanCount -gt 1) {
        $failures.Add("kovan=duplicated (matches=$kovanCount)")
    }

    $permissionEvidence = 'not evaluated'
    if ($kovanCount -eq 1) {
        # Index only after proving there is exactly one match.
        $effectiveKovan = $kovanMatches[0]
        $permissionsProperty = $effectiveKovan.PSObject.Properties['permissions']
        if ($null -eq $permissionsProperty) {
            $failures.Add('kovan_permissions=missing')
        } else {
            try {
                $permissions = @($permissionsProperty.Value)
                $editWildcardDeny = @($permissions | Where-Object {
                    $_.action -eq 'edit' -and $_.resource -eq '*' -and $_.effect -eq 'deny'
                }).Count
                $editPluginsAsk = @($permissions | Where-Object {
                    $_.action -eq 'edit' -and $_.resource -eq '.opencode/plugins/**' -and $_.effect -eq 'ask'
                }).Count
                $activityDeny = @($permissions | Where-Object {
                    $_.action -eq 'edit' -and $_.resource -eq '.opencode/plugins/olympus-activity/**' -and $_.effect -eq 'deny'
                }).Count
                $externalAsk = @($permissions | Where-Object {
                    $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'ask'
                }).Count
                $externalAllow = @($permissions | Where-Object {
                    $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'allow'
                }).Count
                $permissionEvidence = "edit_*_deny=$editWildcardDeny/0, edit_plugins_ask=$editPluginsAsk/1, activity_deny=$activityDeny/1, external_ask=$externalAsk/>0, external_allow=$externalAllow/0"
                if ($editWildcardDeny -ne 0 -or $editPluginsAsk -ne 1 -or $activityDeny -ne 1 -or
                    $externalAsk -le 0 -or $externalAllow -ne 0) {
                    $failures.Add('effective_permission_rules_mismatch (' + $permissionEvidence + ')')
                }
            } catch {
                $permissionEvidence = 'evaluation_error=' + (Compact-Evidence $_.Exception.Message)
                $failures.Add('effective_permission_rules_unreadable (' + $permissionEvidence + ')')
            }
        }
    }

    $runtimeExitEvidence = if ($null -eq $runtimeExit) { '<unavailable>' } else { [string]$runtimeExit }
    $failureEvidence = if ($failures.Count -eq 0) { 'none' } else { $failures -join ', ' }
    $evidence = "runtime_exit=$runtimeExitEvidence; json_parseable=$runtimeJsonParseable; json_root=$runtimeJsonRootType; kovan_matches=$kovanCount; permission_rules=$permissionEvidence; stderr=$(Compact-Evidence $runtimeStderr); failures=$failureEvidence"
    [pscustomobject]@{ passed=($failures.Count -eq 0); evidence=$evidence }
}

function Test-AuthorityPathWithin([string]$Path, [string]$Base) {
    $separators = [char[]]@([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar)
    $candidate = [IO.Path]::GetFullPath($Path).TrimEnd($separators)
    $basePath = [IO.Path]::GetFullPath($Base).TrimEnd($separators)
    return $candidate.Equals($basePath,[StringComparison]::OrdinalIgnoreCase) -or
        $candidate.StartsWith($basePath + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)
}

function Assert-AuthorityNoReparsePoints([string]$Path, [switch]$Recursive) {
    $full = [IO.Path]::GetFullPath($Path)
    $volumeRoot = [IO.Path]::GetPathRoot($full)
    $parts = $full.Substring($volumeRoot.Length).Split(
        [char[]]@([IO.Path]::DirectorySeparatorChar,[IO.Path]::AltDirectorySeparatorChar),
        [StringSplitOptions]::RemoveEmptyEntries)
    $current = $volumeRoot
    foreach ($part in $parts) {
        $current = Join-Path $current $part
        if (-not (Test-Path -LiteralPath $current)) { continue }
        $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw ('AUTHORITY_FIXTURE_REPARSE_POINT: ' + $item.FullName)
        }
    }
    if ($Recursive -and (Test-Path -LiteralPath $full -PathType Container)) {
        foreach ($item in @(Get-ChildItem -LiteralPath $full -Force -Recurse -ErrorAction Stop)) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw ('AUTHORITY_FIXTURE_REPARSE_POINT: ' + $item.FullName)
            }
        }
    }
}

function Get-AuthorityPython311 {
    foreach ($name in @('python3.11','python3','python')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -eq $command) { continue }
        try {
            $probe = @(& $command.Source -B -c 'import json,sys; print(json.dumps({"executable":sys.executable,"version":list(sys.version_info[:3])}))' 2>$null)
            $probeExit = $LASTEXITCODE
            if ($probeExit -ne 0 -or $probe.Count -eq 0) { continue }
            $details = ($probe -join "`n") | ConvertFrom-Json -Depth 5 -ErrorAction Stop
            $version = @($details.version | ForEach-Object { [int]$_ })
            if ($version.Count -lt 2 -or $version[0] -lt 3 -or ($version[0] -eq 3 -and $version[1] -lt 11)) { continue }
            $executable = [IO.Path]::GetFullPath([string]$details.executable)
            if (Test-Path -LiteralPath $executable -PathType Leaf) { return $executable }
        } catch { }
    }
    throw 'AUTHORITY_RUNTIME_SETUP_FAILED: Python 3.11+ executable could not be resolved before process isolation.'
}

function Get-AuthorityOpenCodeExecutable {
    $applications = @(Get-Command 'opencode.exe' -CommandType Application -ErrorAction SilentlyContinue)
    if ($applications.Count -gt 0) { return [IO.Path]::GetFullPath($applications[0].Source) }

    $command = Get-Command opencode -ErrorAction Stop
    $wrapperRoot = Split-Path -Parent $command.Source
    if ([IO.Path]::GetExtension($command.Source) -in @('.ps1','.cmd','.bat')) {
        $bundledExe = Join-Path $wrapperRoot 'node_modules/@opencode/cli/bin/opencode.exe'
        if (Test-Path -LiteralPath $bundledExe -PathType Leaf) { return [IO.Path]::GetFullPath($bundledExe) }
    }
    if ($command.CommandType -eq [Management.Automation.CommandTypes]::Application -and
        [IO.Path]::GetExtension($command.Source) -ieq '.exe') { return [IO.Path]::GetFullPath($command.Source) }
    throw 'AUTHORITY_RUNTIME_CLI_UNRESOLVED: Could not resolve the real OpenCode executable.'
}

function Set-AuthorityChildEnvironment(
    [Diagnostics.ProcessStartInfo]$StartInfo,
    [string]$Root,
    [string]$MockBin = '',
    [switch]$MockBootstrap,
    [string]$GitConfig = '',
    [string]$GitTemplate = '',
    [string]$OpenCodePassword = ''
) {
    $homePath = Join-Path $Root 'home'
    $isolatedTemp = Join-Path $Root 'temp'
    $xdgConfig = Join-Path $Root 'xdg-config'
    $xdgData = Join-Path $Root 'xdg-data'
    $xdgCache = Join-Path $Root 'xdg-cache'
    $xdgState = Join-Path $Root 'xdg-state'
    $appData = Join-Path $homePath 'AppData/Roaming'
    $localAppData = Join-Path $homePath 'AppData/Local'
    foreach ($path in @($homePath,$isolatedTemp,$xdgConfig,$xdgData,$xdgCache,$xdgState,$appData,$localAppData)) {
        [IO.Directory]::CreateDirectory($path) | Out-Null
    }

    $preserved = [ordered]@{}
    foreach ($key in @('PATH','SystemRoot','WINDIR','COMSPEC','PATHEXT')) {
        $value = [Environment]::GetEnvironmentVariable($key,'Process')
        if (-not [string]::IsNullOrWhiteSpace($value)) { $preserved[$key] = $value }
    }
    if (-not $preserved.Contains('PATH') -or -not $preserved.Contains('SystemRoot')) {
        throw 'AUTHORITY_RUNTIME_ENVIRONMENT_INVALID: PATH and SystemRoot are required on Windows.'
    }

    $StartInfo.Environment.Clear()
    foreach ($key in $preserved.Keys) { $StartInfo.Environment[$key] = [string]$preserved[$key] }
    $drive = [IO.Path]::GetPathRoot($homePath).TrimEnd([char[]]@('\','/'))
    $StartInfo.Environment['HOME'] = [IO.Path]::GetFullPath($homePath)
    $StartInfo.Environment['USERPROFILE'] = [IO.Path]::GetFullPath($homePath)
    $StartInfo.Environment['HOMEDRIVE'] = $drive
    $StartInfo.Environment['HOMEPATH'] = $homePath.Substring($drive.Length)
    $StartInfo.Environment['APPDATA'] = [IO.Path]::GetFullPath($appData)
    $StartInfo.Environment['LOCALAPPDATA'] = [IO.Path]::GetFullPath($localAppData)
    $StartInfo.Environment['XDG_CONFIG_HOME'] = [IO.Path]::GetFullPath($xdgConfig)
    $StartInfo.Environment['XDG_DATA_HOME'] = [IO.Path]::GetFullPath($xdgData)
    $StartInfo.Environment['XDG_CACHE_HOME'] = [IO.Path]::GetFullPath($xdgCache)
    $StartInfo.Environment['XDG_STATE_HOME'] = [IO.Path]::GetFullPath($xdgState)
    $StartInfo.Environment['TEMP'] = [IO.Path]::GetFullPath($isolatedTemp)
    $StartInfo.Environment['TMP'] = [IO.Path]::GetFullPath($isolatedTemp)
    if ($MockBootstrap) {
        $StartInfo.Environment['PATH'] = [IO.Path]::GetFullPath($MockBin) + [IO.Path]::PathSeparator + [string]$preserved['PATH']
    }
    if ($GitConfig) {
        $StartInfo.Environment['GIT_CONFIG_NOSYSTEM'] = '1'
        $StartInfo.Environment['GIT_CONFIG_GLOBAL'] = [IO.Path]::GetFullPath($GitConfig)
    }
    if ($GitTemplate) { $StartInfo.Environment['GIT_TEMPLATE_DIR'] = [IO.Path]::GetFullPath($GitTemplate) }
    if (-not [string]::IsNullOrWhiteSpace($OpenCodePassword)) {
        $StartInfo.Environment['OPENCODE_PASSWORD'] = $OpenCodePassword
    }
}

function Invoke-AuthorityCapturedProcess(
    [string]$Executable,
    [string[]]$Arguments,
    [string]$WorkingDirectory,
    [string]$Root,
    [switch]$MockBootstrap,
    [string]$MockBin = '',
    [string]$GitConfig = '',
    [string]$GitTemplate = '',
    [string]$OpenCodePassword = ''
) {
    $startInfo = [Diagnostics.ProcessStartInfo]::new([IO.Path]::GetFullPath($Executable))
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.WorkingDirectory = [IO.Path]::GetFullPath($WorkingDirectory)
    foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add([string]$argument) }
    Set-AuthorityChildEnvironment $startInfo $Root $MockBin -MockBootstrap:$MockBootstrap -GitConfig $GitConfig -GitTemplate $GitTemplate `
        -OpenCodePassword $OpenCodePassword
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        [void]$process.Start()
        $startedUtc = $process.StartTime.ToUniversalTime()
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(120000)) {
            try { $process.Kill($true) }
            catch {
                if (-not $process.HasExited) {
                    throw ('AUTHORITY_RUNTIME_PROCESS_CLEANUP_FAILED: timed-out process could not be killed (pid=' +
                        $process.Id + '; executable=' + $Executable + '; kill_error=' + (Compact-Evidence $_.Exception.Message) + ')')
                }
            }
            if (-not $process.HasExited -and -not $process.WaitForExit(30000)) {
                throw ('AUTHORITY_RUNTIME_PROCESS_CLEANUP_FAILED: timed-out process tree remained active after kill (pid=' +
                    $process.Id + '; executable=' + $Executable + ')')
            }
            throw ('AUTHORITY_RUNTIME_PROCESS_TIMEOUT: ' + $Executable + ' ' + ($Arguments -join ' '))
        }
        $process.WaitForExit()
        $completedUtc = $process.ExitTime.ToUniversalTime()
        return [pscustomobject]@{
            ExitCode=$process.ExitCode
            Stdout=$stdoutTask.GetAwaiter().GetResult()
            Stderr=$stderrTask.GetAwaiter().GetResult()
            Pid=$process.Id
            WorkingDirectory=$startInfo.WorkingDirectory
            StartedUtc=$startedUtc
            CompletedUtc=$completedUtc
        }
    } finally { $process.Dispose() }
}

function Assert-AuthorityNoOpenCodeChild([object]$Invocation, [string]$Executable) {
    try {
        $children = @(Get-CimInstance Win32_Process -Filter ("ParentProcessId = {0}" -f [int]$Invocation.Pid) -ErrorAction Stop)
    } catch {
        throw ('AUTHORITY_RUNTIME_CHILD_PROCESS_CHECK_FAILED: parent_pid=' + $Invocation.Pid +
            '; query_error=' + (Compact-Evidence $_.Exception.Message))
    }
    $expectedExecutable = [IO.Path]::GetFullPath($Executable)
    $lingering = [Collections.Generic.List[string]]::new()
    foreach ($child in $children) {
        if ([string]::IsNullOrWhiteSpace([string]$child.ExecutablePath)) {
            throw ('AUTHORITY_RUNTIME_CHILD_PROCESS_CHECK_FAILED: direct child path unavailable (parent_pid=' +
                $Invocation.Pid + '; child_pid=' + $child.ProcessId + ')')
        }
        $childExecutable = [IO.Path]::GetFullPath([string]$child.ExecutablePath)
        if (-not [string]::Equals($childExecutable,$expectedExecutable,[StringComparison]::OrdinalIgnoreCase)) { continue }
        if ($null -eq $child.CreationDate) {
            throw ('AUTHORITY_RUNTIME_CHILD_PROCESS_CHECK_FAILED: OpenCode child creation time unavailable (parent_pid=' +
                $Invocation.Pid + '; child_pid=' + $child.ProcessId + ')')
        }
        $childCreatedUtc = ([datetime]$child.CreationDate).ToUniversalTime()
        if ($childCreatedUtc -ge $Invocation.StartedUtc.AddSeconds(-1) -and
            $childCreatedUtc -le $Invocation.CompletedUtc.AddSeconds(1)) {
            $lingering.Add(([string]$child.ProcessId) + '@' + $childExecutable)
        }
    }
    if ($lingering.Count -gt 0) {
        throw ('AUTHORITY_RUNTIME_CHILD_PROCESS_REMAINS: parent_pid=' + $Invocation.Pid +
            '; children=' + ($lingering -join ', '))
    }
    Write-Output ('AUTHORITY_RUNTIME_CHILD_PROCESS_CHECK: PASS (parent_pid=' + $Invocation.Pid + '; direct_OpenCode_children=0)')
}

function Assert-AuthorityOwnedServer([object]$Server, [string]$RegistryPath) {
    if ($Server.Process.HasExited) {
        throw ('AUTHORITY_RUNTIME_SERVER_NOT_ALIVE: owned_pid=' + $Server.Process.Id + '; url=' + $Server.Url)
    }
    if (-not (Test-Path -LiteralPath $RegistryPath -PathType Leaf)) {
        throw ('AUTHORITY_RUNTIME_SERVER_REGISTRY_MISSING: ' + $RegistryPath)
    }
    try {
        $registry = [IO.File]::ReadAllText($RegistryPath) | ConvertFrom-Json -Depth 20 -ErrorAction Stop
    } catch {
        throw ('AUTHORITY_RUNTIME_SERVER_REGISTRY_INVALID: ' + (Compact-Evidence $_.Exception.Message))
    }
    $pidProperty = $registry.PSObject.Properties['pid']
    $urlProperty = $registry.PSObject.Properties['url']
    $versionProperty = $registry.PSObject.Properties['version']
    $passwordProperty = $registry.PSObject.Properties['password']
    if ($null -eq $pidProperty -or $null -eq $urlProperty -or $null -eq $versionProperty -or $null -eq $passwordProperty -or
        [int]$pidProperty.Value -ne [int]$Server.Process.Id -or
        -not [string]::Equals([string]$urlProperty.Value,[string]$Server.Url,[StringComparison]::OrdinalIgnoreCase) -or
        [string]::IsNullOrWhiteSpace([string]$versionProperty.Value) -or
        [string]::IsNullOrWhiteSpace([string]$passwordProperty.Value)) {
        throw ('AUTHORITY_RUNTIME_SERVER_REGISTRY_MISMATCH: expected_pid=' + $Server.Process.Id + '; expected_url=' + $Server.Url +
            '; registry_pid=' + $(if ($null -eq $pidProperty) { '<missing>' } else { [string]$pidProperty.Value }) +
            '; registry_url=' + $(if ($null -eq $urlProperty) { '<missing>' } else { [string]$urlProperty.Value }))
    }
    try {
        $ownedListeners = @(Get-NetTCPConnection -ErrorAction Stop | Where-Object {
            [int]$_.OwningProcess -eq [int]$Server.Process.Id -and
            $_.State -eq 'Listen' -and
            [string]::Equals([string]$_.LocalAddress,'127.0.0.1',[StringComparison]::OrdinalIgnoreCase) -and
            [int]$_.LocalPort -eq [int]$Server.Port
        })
    } catch {
        throw ('AUTHORITY_RUNTIME_SERVER_LISTENER_CHECK_FAILED: ' + (Compact-Evidence $_.Exception.Message))
    }
    if ($ownedListeners.Count -eq 0) {
        throw ('AUTHORITY_RUNTIME_SERVER_LISTENER_MISMATCH: expected_pid=' + $Server.Process.Id +
            '; expected_url=' + $Server.Url + '; expected_port=' + $Server.Port)
    }
    Write-Output ('AUTHORITY_RUNTIME_SERVER_REGISTRY: PASS (pid=' + $Server.Process.Id + '; url=' + $Server.Url + '; version/password=present)')
    Write-Output ('AUTHORITY_RUNTIME_SERVER_LISTENER: PASS (pid=' + $Server.Process.Id + '; address=127.0.0.1; port=' + $Server.Port + ')')
}

function Stop-AuthorityOwnedServer([object]$Server) {
    $process = $Server.Process
    $processId = [int]$process.Id
    $failures = [Collections.Generic.List[string]]::new()
    $processExited = $false
    $processExitCode = $null
    try {
        if (-not $process.HasExited) {
            try { $process.Kill($true) }
            catch {
                if (-not $process.HasExited) { $failures.Add('owned process-tree kill_error=' + (Compact-Evidence $_.Exception.Message)) }
            }
        }
        if (-not $process.WaitForExit(30000)) {
            $failures.Add('owned server process remained active after bounded wait')
        } elseif ($process.HasExited) {
            $processExited = $true
            $processExitCode = [int]$process.ExitCode
        } else { $failures.Add('owned server process exit could not be confirmed') }
    } catch { $failures.Add($_.Exception.Message) }

    $streamResults = [ordered]@{ readiness='not_started'; stdout='not_started'; stderr='not_started' }
    $streamsDrained = $true
    foreach ($stream in @(
        @{ Name='readiness'; Task=$Server.ReadinessTask },
        @{ Name='stdout'; Task=$Server.StdoutTailTask },
        @{ Name='stderr'; Task=$Server.StderrTask }
    )) {
        if ($null -eq $stream.Task) { continue }
        try {
            if (-not $stream.Task.Wait(10000)) {
                $streamResults[$stream.Name] = 'timeout'
                $streamsDrained = $false
                $failures.Add($stream.Name + ' stream did not close after process exit')
            } else {
                $null = $stream.Task.GetAwaiter().GetResult()
                $streamResults[$stream.Name] = 'drained'
            }
        } catch {
            $streamResults[$stream.Name] = 'error'
            $streamsDrained = $false
            $failures.Add($stream.Name + '_drain_error=' + (Compact-Evidence $_.Exception.Message))
        }
    }

    Write-Output ('AUTHORITY_RUNTIME_SERVER_STOP: pid=' + $processId + '; process_exited=' + $processExited +
        '; exit_code=' + $(if ($null -eq $processExitCode) { '<unavailable>' } else { [string]$processExitCode }) +
        '; readiness=' + $streamResults.readiness + '; stdout=' + $streamResults.stdout + '; stderr=' + $streamResults.stderr)
    try { $process.Dispose() } catch { $failures.Add('process_dispose_error=' + (Compact-Evidence $_.Exception.Message)) }
    if ($failures.Count -gt 0) {
        throw ('AUTHORITY_RUNTIME_SERVER_CLEANUP_FAILED: pid=' + $processId + '; failures=' + ($failures -join '; '))
    }
    Write-Output ('AUTHORITY_RUNTIME_SERVER_CLEANUP: PASS (owned_pid=' + $processId +
        '; process_exit_confirmed=YES; streams=drained)')
}

function Get-AuthorityResolvedPaths([string]$Text) {
    $paths = [ordered]@{}
    foreach ($line in ($Text -split "`r?`n")) {
        $match = [regex]::Match([string]$line,'^\s*(?<name>[A-Za-z][A-Za-z0-9_-]*)\s{2,}(?<path>.+?)\s*$')
        if (-not $match.Success) { continue }
        $name = $match.Groups['name'].Value.ToLowerInvariant()
        $value = $match.Groups['path'].Value.Trim()
        if (-not [IO.Path]::IsPathFullyQualified($value)) { throw "AUTHORITY_RUNTIME_PATHS_FAILED: $name is not an absolute path: $value" }
        if ($paths.Contains($name)) { throw "AUTHORITY_RUNTIME_PATHS_FAILED: duplicate path entry $name." }
        $paths[$name] = [IO.Path]::GetFullPath($value)
    }
    return ,$paths
}

function Invoke-IsolatedAuthorityRuntime {
    $qualificationBase = 'C:\Users\Public\olympus-authority-qualification'
    $fixtureId = [guid]::NewGuid().ToString('N')
    $fixtureRoot = Join-Path $qualificationBase $fixtureId
    $rootCreated = $false
    $primaryFailure = ''
    $cleanupFailure = ''
    $ownedServer = $null
    $serverCleanupFailed = $false
    try {
        if (-not (Test-Path -LiteralPath 'C:\Users\Public' -PathType Container)) {
            throw 'AUTHORITY_RUNTIME_SETUP_FAILED: C:\Users\Public is unavailable.'
        }
        Assert-AuthorityNoReparsePoints $qualificationBase
        [IO.Directory]::CreateDirectory($qualificationBase) | Out-Null
        Assert-AuthorityNoReparsePoints $qualificationBase
        if (Test-Path -LiteralPath $fixtureRoot) { throw 'AUTHORITY_RUNTIME_SETUP_FAILED: generated fixture ID already exists.' }
        [IO.Directory]::CreateDirectory($fixtureRoot) | Out-Null
        $rootCreated = $true
        Assert-AuthorityNoReparsePoints $fixtureRoot

        $sourceRoot = Join-Path $fixtureRoot 'source'
        $projectRoot = Join-Path $fixtureRoot 'project'
        $mockBin = Join-Path $fixtureRoot 'bootstrap-mock-bin'
        $homePath = Join-Path $fixtureRoot 'home'
        $isolatedTemp = Join-Path $fixtureRoot 'temp'
        $xdgConfig = Join-Path $fixtureRoot 'xdg-config'
        $xdgData = Join-Path $fixtureRoot 'xdg-data'
        $xdgCache = Join-Path $fixtureRoot 'xdg-cache'
        $xdgState = Join-Path $fixtureRoot 'xdg-state'
        $mockLog = Join-Path $fixtureRoot 'bootstrap-opencode.log'
        $gitTemplate = Join-Path $fixtureRoot 'empty-git-template'
        $gitConfig = Join-Path $fixtureRoot 'empty-gitconfig'
        foreach ($path in @($sourceRoot,$projectRoot,$mockBin,$gitTemplate)) { [IO.Directory]::CreateDirectory($path) | Out-Null }
        [IO.File]::WriteAllText($gitConfig,'', [Text.UTF8Encoding]::new($false))
        Assert-AuthorityNoReparsePoints $fixtureRoot -Recursive

        $canonicalSources = Join-Path $root 'olympus'
        $rendererSource = Join-Path $root 'scripts/render_harnesses.py'
        $bootstrapSource = Join-Path $root 'scripts/bootstrap.ps1'
        $mockSource = Join-Path $root 'tests/release/fixtures/opencode.ps1'
        foreach ($sourcePath in @($canonicalSources,$rendererSource,$bootstrapSource,$mockSource)) {
            if (-not (Test-Path -LiteralPath $sourcePath)) { throw ('AUTHORITY_RUNTIME_SETUP_FAILED: required local source is missing: ' + $sourcePath) }
        }
        Copy-Item -LiteralPath $canonicalSources -Destination (Join-Path $sourceRoot 'olympus') -Recurse -Force -ErrorAction Stop
        $stagedScripts = Join-Path $sourceRoot 'scripts'
        [IO.Directory]::CreateDirectory($stagedScripts) | Out-Null
        Copy-Item -LiteralPath $rendererSource -Destination (Join-Path $stagedScripts 'render_harnesses.py') -Force -ErrorAction Stop
        Copy-Item -LiteralPath $bootstrapSource -Destination (Join-Path $stagedScripts 'bootstrap.ps1') -Force -ErrorAction Stop
        Copy-Item -LiteralPath $mockSource -Destination (Join-Path $mockBin 'opencode-fixture.ps1') -Force -ErrorAction Stop

        $pwsh = Join-Path $PSHOME 'pwsh.exe'
        if (-not (Test-Path -LiteralPath $pwsh -PathType Leaf)) { $pwsh = (Get-Command pwsh -CommandType Application -ErrorAction Stop).Source }
        $wrapper = "@echo off`r`n>>`"$mockLog`" echo %*`r`n`"$pwsh`" -NoProfile -File `"%~dp0opencode-fixture.ps1`" %*`r`nexit /b %ERRORLEVEL%`r`n"
        [IO.File]::WriteAllText((Join-Path $mockBin 'opencode.cmd'),$wrapper,[Text.Encoding]::ASCII)
        Assert-AuthorityNoReparsePoints $fixtureRoot -Recursive

        $python = Get-AuthorityPython311
        $renderer = Join-Path $stagedScripts 'render_harnesses.py'
        $renderOutput = @(& $python -B $renderer render --harness opencode --root $sourceRoot 2>&1)
        $renderExit = [int]$LASTEXITCODE
        if ($renderExit -ne 0) {
            throw ('AUTHORITY_RUNTIME_RENDER_FAILED: exit=' + $renderExit + '; output=' + (Compact-Evidence ($renderOutput -join "`n")))
        }

        $gitCommand = Get-Command 'git.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $gitCommand) { throw 'AUTHORITY_RUNTIME_SETUP_FAILED: git.exe is unavailable.' }
        $gitResult = Invoke-AuthorityCapturedProcess $gitCommand.Source @('-C',$projectRoot,'init','--quiet') $projectRoot $fixtureRoot `
            -GitConfig $gitConfig -GitTemplate $gitTemplate
        if ($gitResult.ExitCode -ne 0) {
            throw ('AUTHORITY_RUNTIME_GIT_INIT_FAILED: exit=' + $gitResult.ExitCode + '; stderr=' + (Compact-Evidence $gitResult.Stderr))
        }

        $gitRootResult = Invoke-AuthorityCapturedProcess $gitCommand.Source @('-C',$projectRoot,'rev-parse','--show-toplevel') $projectRoot $fixtureRoot `
            -GitConfig $gitConfig -GitTemplate $gitTemplate
        if ($gitRootResult.ExitCode -ne 0 -or
            -not [string]::Equals([IO.Path]::GetFullPath($gitRootResult.Stdout.Trim()),[IO.Path]::GetFullPath($projectRoot),[StringComparison]::OrdinalIgnoreCase)) {
            throw ('AUTHORITY_RUNTIME_GIT_ROOT_FAILED: expected=' + $projectRoot + '; actual=' + (Compact-Evidence $gitRootResult.Stdout))
        }
        Assert-AuthorityNoReparsePoints $fixtureRoot -Recursive

        $bootstrap = Join-Path $stagedScripts 'bootstrap.ps1'
        $bootstrapResult = Invoke-AuthorityCapturedProcess $pwsh @('-NoProfile','-File',$bootstrap,'-Target',$projectRoot,'-Harness','opencode') `
            $projectRoot $fixtureRoot -MockBootstrap -MockBin $mockBin -GitConfig $gitConfig -GitTemplate $gitTemplate
        $stubCalls = @()
        if (Test-Path -LiteralPath $mockLog -PathType Leaf) { $stubCalls = @([IO.File]::ReadAllLines($mockLog)) }
        $mockConfigCalls = @($stubCalls | Where-Object { $_.Trim() -eq 'debug config' }).Count
        $mockAgentCalls = @($stubCalls | Where-Object { $_.Trim() -eq 'debug agents' }).Count
        if ($bootstrapResult.ExitCode -ne 0 -or $mockConfigCalls -ne 1 -or $mockAgentCalls -ne 1) {
            throw ('AUTHORITY_RUNTIME_BOOTSTRAP_FAILED: exit=' + $bootstrapResult.ExitCode + '; mock_calls=' + ($stubCalls -join ',') +
                '; output=' + (Compact-Evidence ($bootstrapResult.Stdout + "`n" + $bootstrapResult.Stderr)))
        }
        Write-Output ('AUTHORITY_RUNTIME_SETUP: PASS (renderer=local Python ' + $python + '; bootstrap=local source; project=' + $projectRoot +
            '; git_root=' + $projectRoot + '; mock_stub=' + (Join-Path $mockBin 'opencode.cmd') +
            '; mock_calls=' + ($stubCalls -join ',') + '; real_OpenCode_calls=0)')

        Assert-AuthorityNoReparsePoints $fixtureRoot -Recursive
        $expectedProjectConfig = [IO.Path]::GetFullPath((Join-Path $projectRoot 'opencode.jsonc'))
        if (-not (Test-Path -LiteralPath $expectedProjectConfig -PathType Leaf)) {
            throw ('AUTHORITY_RUNTIME_CONFIG_CONTEXT_FAILED: staged project config is missing: ' + $expectedProjectConfig)
        }
        $realOpenCode = Get-AuthorityOpenCodeExecutable
        Write-Output ('AUTHORITY_RUNTIME_FIXTURE: root=' + $fixtureRoot + '; source=' + $sourceRoot + '; project=' + $projectRoot +
            '; checkout_generated_agents_used=NO; checkout_opencode_tree_copied=NO; runtime_cli=' + $realOpenCode)

        $pathProbe = $null
        $pathInvocationError = ''
        try { $pathProbe = Invoke-AuthorityCapturedProcess $realOpenCode @('debug','paths') $projectRoot $fixtureRoot }
        catch { $pathInvocationError = $_.Exception.Message }
        if ($null -eq $pathProbe) {
            Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug paths pid=<unavailable>; cwd=' + $projectRoot + '; exit=<unavailable>')
            throw ('AUTHORITY_RUNTIME_PATHS_FAILED: invocation_error=' + (Compact-Evidence $pathInvocationError))
        }
        Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug paths pid=' + $pathProbe.Pid + '; cwd=' + $pathProbe.WorkingDirectory + '; exit=' + $pathProbe.ExitCode)
        Assert-AuthorityNoOpenCodeChild $pathProbe $realOpenCode
        if ($pathProbe.ExitCode -ne 0) {
            throw ('AUTHORITY_RUNTIME_PATHS_FAILED: exit=' + $pathProbe.ExitCode + '; stderr=' + (Compact-Evidence $pathProbe.Stderr))
        }
        $resolvedPaths = Get-AuthorityResolvedPaths $pathProbe.Stdout
        $requiredPathRoots = [ordered]@{
            home=$homePath
            config=$xdgConfig
            data=$xdgData
            cache=$xdgCache
            state=$xdgState
            tmp=$isolatedTemp
        }
        foreach ($name in $requiredPathRoots.Keys) {
            if (-not $resolvedPaths.Contains($name)) { throw "AUTHORITY_RUNTIME_PATHS_FAILED: missing required path '$name'." }
            if (-not (Test-AuthorityPathWithin $resolvedPaths[$name] $requiredPathRoots[$name])) {
                throw ("AUTHORITY_RUNTIME_PATHS_FAILED: $name resolved outside its isolated root: " + $resolvedPaths[$name])
            }
        }
        $allIsolatedRoots = @($homePath,$projectRoot,$xdgConfig,$xdgData,$xdgCache,$xdgState,$isolatedTemp)
        foreach ($name in $resolvedPaths.Keys) {
            if (@($allIsolatedRoots | Where-Object { Test-AuthorityPathWithin $resolvedPaths[$name] $_ }).Count -eq 0) {
                throw ("AUTHORITY_RUNTIME_PATHS_FAILED: $name resolved outside fixture/isolation roots: " + $resolvedPaths[$name])
            }
        }
        Write-Output ('AUTHORITY_RUNTIME_PATHS: PASS (home=' + $resolvedPaths.home + '; config=' + $resolvedPaths.config +
            '; data=' + $resolvedPaths.data + '; cache=' + $resolvedPaths.cache + '; state=' + $resolvedPaths.state +
            '; tmp=' + $resolvedPaths.tmp + ')')

        $serverStartInfo = [Diagnostics.ProcessStartInfo]::new([IO.Path]::GetFullPath($realOpenCode))
        $serverStartInfo.UseShellExecute = $false
        $serverStartInfo.CreateNoWindow = $true
        $serverStartInfo.RedirectStandardOutput = $true
        $serverStartInfo.RedirectStandardError = $true
        $serverStartInfo.WorkingDirectory = [IO.Path]::GetFullPath($projectRoot)
        foreach ($argument in @('serve','--service','--hostname','127.0.0.1','--port','0')) {
            $serverStartInfo.ArgumentList.Add([string]$argument)
        }
        Set-AuthorityChildEnvironment $serverStartInfo $fixtureRoot
        $serverProcess = [Diagnostics.Process]::new()
        $serverProcess.StartInfo = $serverStartInfo
        $ownedServer = [pscustomobject]@{
            Process=$serverProcess
            Started=$false
            StartedUtc=$null
            ReadinessTask=$null
            StdoutTailTask=$null
            StderrTask=$null
            Url=$null
            Port=$null
            ReadinessLine=$null
        }
        [void]$serverProcess.Start()
        $ownedServer.Started = $true
        $ownedServer.StartedUtc = $serverProcess.StartTime.ToUniversalTime()
        $ownedServer.StderrTask = $serverProcess.StandardError.ReadToEndAsync()
        $ownedServer.ReadinessTask = $serverProcess.StandardOutput.ReadLineAsync()
        if (-not $ownedServer.ReadinessTask.Wait(30000)) {
            throw 'AUTHORITY_RUNTIME_SERVER_START_FAILED: readiness line timed out after 30 seconds.'
        }
        $ownedServer.ReadinessLine = $ownedServer.ReadinessTask.GetAwaiter().GetResult()
        $readinessMatch = [regex]::Match([string]$ownedServer.ReadinessLine,
            '^server listening on (?<url>http://127\.0\.0\.1:(?<port>[0-9]+))\s*$',
            [Text.RegularExpressions.RegexOptions]::IgnoreCase)
        if (-not $readinessMatch.Success) {
            $startupStderr = if ($ownedServer.StderrTask.IsCompleted) { $ownedServer.StderrTask.GetAwaiter().GetResult() } else { '<still streaming>' }
            throw ('AUTHORITY_RUNTIME_SERVER_START_FAILED: unexpected readiness line=' +
                (Compact-Evidence ([string]$ownedServer.ReadinessLine)) + '; stderr=' + (Compact-Evidence $startupStderr))
        }
        $ownedServer.Port = [int]$readinessMatch.Groups['port'].Value
        $ownedServer.Url = $readinessMatch.Groups['url'].Value
        if ($ownedServer.Port -lt 1 -or $ownedServer.Port -gt 65535) {
            throw ('AUTHORITY_RUNTIME_SERVER_START_FAILED: invalid loopback port ' + $ownedServer.Port)
        }
        if ($serverProcess.HasExited) {
            $startupStderr = if ($ownedServer.StderrTask.IsCompleted) { $ownedServer.StderrTask.GetAwaiter().GetResult() } else { '<unavailable>' }
            throw ('AUTHORITY_RUNTIME_SERVER_START_FAILED: server exited after readiness; stderr=' + (Compact-Evidence $startupStderr))
        }
        $ownedServer.StdoutTailTask = $serverProcess.StandardOutput.ReadToEndAsync()
        Write-Output ('AUTHORITY_RUNTIME_SERVER: READY (pid=' + $serverProcess.Id + '; cwd=' + $serverStartInfo.WorkingDirectory +
            '; url=' + $ownedServer.Url + '; command=serve --service --hostname 127.0.0.1 --port 0)')
        $serviceRegistry = Join-Path (Join-Path $xdgState 'opencode') 'service.json'
        Assert-AuthorityOwnedServer $ownedServer $serviceRegistry

        $configProbe = $null
        $configInvocationError = ''
        try { $configProbe = Invoke-AuthorityCapturedProcess $realOpenCode @('debug','config') $projectRoot $fixtureRoot }
        catch { $configInvocationError = $_.Exception.Message }
        if ($null -eq $configProbe) {
            Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug config pid=<unavailable>; cwd=' + $projectRoot + '; exit=<unavailable>')
            throw ('AUTHORITY_CONFIG_CONTEXT FAIL: opencode debug config invocation failed (runtime_exit=<unavailable>; stderr=<unavailable>; invocation_error=' +
                (Compact-Evidence $configInvocationError) + ')')
        }
        Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug config pid=' + $configProbe.Pid + '; cwd=' + $configProbe.WorkingDirectory + '; exit=' + $configProbe.ExitCode)
        Assert-AuthorityNoOpenCodeChild $configProbe $realOpenCode
        Assert-AuthorityOwnedServer $ownedServer $serviceRegistry
        if ($configProbe.ExitCode -ne 0) {
            throw ('AUTHORITY_CONFIG_CONTEXT FAIL: opencode debug config returned nonzero (runtime_exit=' +
                [string]$configProbe.ExitCode + '; stderr=' + (Compact-Evidence $configProbe.Stderr) +
                '; output=' + (Compact-Evidence $configProbe.Stdout) + ')')
        }
        try {
            $configDocument = ConvertFrom-Json -InputObject $configProbe.Stdout -Depth 100 -NoEnumerate -ErrorAction Stop
            if ($configDocument -isnot [array]) { throw 'debug config JSON root is not an array' }
            $configPaths = @($configDocument | ForEach-Object {
                if ($null -eq $_.path -or -not [string]$_.path) { throw 'config entry has no path' }
                if (-not [IO.Path]::IsPathFullyQualified([string]$_.path)) { throw ('config entry path is not absolute: ' + [string]$_.path) }
                [IO.Path]::GetFullPath([string]$_.path)
            })
        } catch {
            throw ('AUTHORITY_CONFIG_CONTEXT FAIL: opencode debug config returned invalid JSON or path (runtime_exit=0; json_error=' +
                (Compact-Evidence $_.Exception.Message) + '; stderr=' + (Compact-Evidence $configProbe.Stderr) +
                '; output=' + (Compact-Evidence $configProbe.Stdout) + ')')
        }
        $globalConfigRoot = Join-Path $xdgConfig 'opencode'
        $unexpectedConfigPaths = @($configPaths | Where-Object {
            -not (Test-AuthorityPathWithin $_ $projectRoot) -and -not (Test-AuthorityPathWithin $_ $globalConfigRoot)
        })
        $matchingProjectConfig = @($configPaths | Where-Object {
            [string]::Equals($_,$expectedProjectConfig,[StringComparison]::OrdinalIgnoreCase)
        })
        if ($matchingProjectConfig.Count -eq 0 -or $unexpectedConfigPaths.Count -gt 0) {
            throw ('AUTHORITY_CONFIG_CONTEXT FAIL: expected fixture config missing or unexpected external config loaded (expected=' +
                $expectedProjectConfig + '; discovered_paths=' + (Compact-Evidence ($configPaths -join ', ')) +
                '; unexpected_paths=' + (Compact-Evidence ($unexpectedConfigPaths -join ', ')) +
                '; stderr=' + (Compact-Evidence $configProbe.Stderr) + ')')
        }
        Write-Output ('AUTHORITY_CONFIG_CONTEXT: PASS (isolated project config matched=' + $expectedProjectConfig +
            '; allowed_global_config=' + $globalConfigRoot + '; discovered=' + (Compact-Evidence ($configPaths -join ', ')) + ')')

        Assert-AuthorityOwnedServer $ownedServer $serviceRegistry
        try {
            $activationRegistration = [IO.File]::ReadAllText($serviceRegistry) | ConvertFrom-Json -Depth 20 -ErrorAction Stop
            $activationPassword = [string]$activationRegistration.password
        } catch {
            throw ('AUTHORITY_PLUGIN_ACTIVATION_CONTEXT_FAILED: isolated service registration is invalid: ' +
                (Compact-Evidence $_.Exception.Message))
        }
        if ([string]::IsNullOrWhiteSpace($activationPassword)) {
            throw 'AUTHORITY_PLUGIN_ACTIVATION_CONTEXT_FAILED: isolated service registration has no password.'
        }
        $directoryHeader = 'x-opencode-directory:' + [Uri]::EscapeDataString($projectRoot)
        $activationArguments = @('api','--server',$ownedServer.Url,'--header',$directoryHeader,'GET','/api/integration')
        $activationProbe = $null
        $activationInvocationError = ''
        try {
            $activationProbe = Invoke-AuthorityCapturedProcess $realOpenCode $activationArguments $projectRoot $fixtureRoot `
                -OpenCodePassword $activationPassword
        } catch { $activationInvocationError = $_.Exception.Message }
        $activationPassword = $null
        if ($null -eq $activationProbe) {
            Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode api GET /api/integration pid=<unavailable>; cwd=' + $projectRoot + '; exit=<unavailable>')
            throw ('AUTHORITY_PLUGIN_ACTIVATION FAIL: invocation failed (invocation_error=' +
                (Compact-Evidence $activationInvocationError) + ')')
        }
        Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode api GET /api/integration pid=' + $activationProbe.Pid +
            '; cwd=' + $activationProbe.WorkingDirectory + '; exit=' + $activationProbe.ExitCode)
        Assert-AuthorityNoOpenCodeChild $activationProbe $realOpenCode
        Assert-AuthorityOwnedServer $ownedServer $serviceRegistry
        if ($activationProbe.ExitCode -ne 0) {
            throw ('AUTHORITY_PLUGIN_ACTIVATION FAIL: GET /api/integration returned nonzero (runtime_exit=' +
                [string]$activationProbe.ExitCode + '; stderr=' + (Compact-Evidence $activationProbe.Stderr) +
                '; output=' + (Compact-Evidence $activationProbe.Stdout) + ')')
        }
        try {
            $activationDocument = ConvertFrom-Json -InputObject $activationProbe.Stdout -Depth 60 -NoEnumerate -ErrorAction Stop
            if ($null -eq $activationDocument.location -or $null -eq $activationDocument.location.directory) {
                throw 'response has no location.directory'
            }
            if ($activationDocument.data -isnot [array]) { throw 'response data is not an integration array' }
            $effectiveLocation = [string]$activationDocument.location.directory
            if (-not [IO.Path]::IsPathFullyQualified($effectiveLocation)) {
                throw ('effective location.directory is not absolute: ' + $effectiveLocation)
            }
            $effectiveLocation = [IO.Path]::GetFullPath($effectiveLocation)
        } catch {
            throw ('AUTHORITY_PLUGIN_ACTIVATION FAIL: GET /api/integration returned invalid context (json_error=' +
                (Compact-Evidence $_.Exception.Message) + '; stderr=' + (Compact-Evidence $activationProbe.Stderr) +
                '; output=' + (Compact-Evidence $activationProbe.Stdout) + ')')
        }
        if (-not [string]::Equals($effectiveLocation,[IO.Path]::GetFullPath($projectRoot),[StringComparison]::OrdinalIgnoreCase)) {
            throw ('AUTHORITY_PLUGIN_ACTIVATION FAIL: endpoint resolved an unexpected directory (expected=' +
                $projectRoot + '; actual=' + $effectiveLocation + ')')
        }
        Write-Output ('AUTHORITY_PLUGIN_ACTIVATION: PASS (endpoint=GET /api/integration; pid=' + $activationProbe.Pid +
            '; effective_location=' + $effectiveLocation + '; integrations=' + $activationDocument.data.Count + ')')

        $runtimeProbe = $null
        $runtimeInvocationError = ''
        try { $runtimeProbe = Invoke-AuthorityCapturedProcess $realOpenCode @('debug','agents') $projectRoot $fixtureRoot }
        catch { $runtimeInvocationError = $_.Exception.Message }
        if ($null -eq $runtimeProbe) {
            Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug agents pid=<unavailable>; cwd=' + $projectRoot + '; exit=<unavailable>')
            $runtimeExit = $null
            $runtimeJson = ''
            $runtimeStderr = ''
        } else {
            Write-Output ('AUTHORITY_RUNTIME_QUERY: opencode debug agents pid=' + $runtimeProbe.Pid + '; cwd=' + $runtimeProbe.WorkingDirectory + '; exit=' + $runtimeProbe.ExitCode)
            Assert-AuthorityNoOpenCodeChild $runtimeProbe $realOpenCode
            Assert-AuthorityOwnedServer $ownedServer $serviceRegistry
            $runtimeExit = $runtimeProbe.ExitCode
            $runtimeJson = $runtimeProbe.Stdout
            $runtimeStderr = $runtimeProbe.Stderr
        }
        $runtimeInspection = Inspect-EffectiveRules $runtimeExit $runtimeJson $runtimeStderr $runtimeInvocationError
        Write-Output ('AUTH14_EVIDENCE: ' + $runtimeInspection.evidence)
        if (-not $runtimeInspection.passed) {
            throw ('AUTH14_OPENCODE_EFFECTIVE_RULES FAIL: ' + $runtimeInspection.evidence)
        }
        Write-Output 'AUTH14_OPENCODE_EFFECTIVE_RULES PASS'
    } catch {
        $primaryFailure = $_.Exception.Message
    } finally {
        if ($null -ne $ownedServer) {
            if ($ownedServer.Started) {
                try { Stop-AuthorityOwnedServer $ownedServer }
                catch {
                    $serverCleanupFailed = $true
                    $cleanupFailure = $_.Exception.Message
                    Write-Output ('AUTHORITY_RUNTIME_SERVER_CLEANUP: FAIL (' + $cleanupFailure + ')')
                }
            } else {
                try { $ownedServer.Process.Dispose() }
                catch {
                    $serverCleanupFailed = $true
                    $cleanupFailure = 'process_dispose_error=' + $_.Exception.Message
                    Write-Output ('AUTHORITY_RUNTIME_SERVER_CLEANUP: FAIL (' + $cleanupFailure + ')')
                }
            }
        }
        if ($rootCreated) {
            if ($serverCleanupFailed) {
                Write-Output ('AUTHORITY_RUNTIME_CLEANUP: FAIL (fixture retained because owned server cleanup failed: ' + $fixtureRoot + ')')
            } else {
                try {
                    $resolvedBase = [IO.Path]::GetFullPath($qualificationBase).TrimEnd([char[]]@('\','/'))
                    $resolvedTarget = [IO.Path]::GetFullPath($fixtureRoot)
                    if (-not [string]::Equals((Split-Path -Parent $resolvedTarget),$resolvedBase,[StringComparison]::OrdinalIgnoreCase) -or
                        -not [string]::Equals((Split-Path -Leaf $resolvedTarget),$fixtureId,[StringComparison]::OrdinalIgnoreCase) -or
                        -not (Test-AuthorityPathWithin $resolvedTarget $resolvedBase)) {
                        throw ('AUTHORITY_RUNTIME_CLEANUP_TARGET_INVALID: ' + $resolvedTarget)
                    }
                    Assert-AuthorityNoReparsePoints $resolvedTarget -Recursive
                    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force -ErrorAction Stop
                    if (Test-Path -LiteralPath $resolvedTarget) { throw ('fixture still exists after removal: ' + $resolvedTarget) }
                    Write-Output ('AUTHORITY_RUNTIME_CLEANUP: PASS (removed=' + $resolvedTarget + ')')
                } catch {
                    $cleanupFailure = $_.Exception.Message
                    Write-Output ('AUTHORITY_RUNTIME_CLEANUP: FAIL (' + $cleanupFailure + ')')
                }
            }
        }
    }
    if ($primaryFailure -or $cleanupFailure) {
        Write-Output 'AUTHORITY_RUNTIME_ISOLATION: FAIL'
        throw ('AUTHORITY_RUNTIME_ISOLATION FAIL: primary=' + $(if ($primaryFailure) { $primaryFailure } else { 'none' }) +
            '; cleanup=' + $(if ($cleanupFailure) { $cleanupFailure } else { 'PASS' }))
    }
    Write-Output 'AUTHORITY_RUNTIME_ISOLATION: PASS (clean process environments; isolated project config; owned loopback backend; setup stub separated; cleanup verified)'
}

try {
    if ($QualificationSlice -ne 'Runtime') {
    $kael = Text '.opencode/agents/kael.md'
    $kovan = Text '.opencode/agents/kovan.md'
    $docs = Text 'docs/DEVELOPMENT.md'
    $configText = (Text 'opencode.jsonc') -replace '(?m)^\s*//.*(?:\r?\n|$)', ''
    $config = $configText | ConvertFrom-Json -Depth 100
    $nativeRules = Read-NativeRules $kovan @($config.permissions)
    $kaelNativeRules = Read-NativeRules $kael @($config.permissions)
    $rootPath = 'C:\fixture\project'
    $operation = 'WRITE_SCOPE:create-or-update'
    $grant = New-Grant 'kovan' $operation '.opencode/plugins/project-owned/**' $rootPath 'NATIVE_ASK'

    Check 'AUTH0_NATIVE_DEFAULTS_ASK_NOT_DENY' (@($config.permissions | Where-Object {
        $_.action -eq 'edit' -and $_.resource -eq '*' -and $_.effect -eq 'ask'
    }).Count -eq 1 -and @($config.permissions | Where-Object {
        $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'ask'
    }).Count -eq 1 -and @($config.permissions | Where-Object {
        $_.action -in @('edit','external_directory') -and $_.resource -eq '*' -and $_.effect -eq 'deny'
    }).Count -eq 0)

    Check 'AUTH0B_KOVAN_NO_BLANKET_EDIT_DENY' (@($nativeRules | Where-Object {
        $_.action -eq 'edit' -and $_.resource -eq '*' -and $_.effect -eq 'deny'
    }).Count -eq 0 -and @($nativeRules | Where-Object {
        $_.action -eq 'edit' -and $_.resource -eq '*' -and $_.effect -eq 'allow'
    }).Count -eq 1)

    Check 'AUTH1_NORMAL_IN_SCOPE_NO_QUESTION' ($kael -match 'Normal in-scope project work proceeds directly when the effective native\s+permission is ALLOW' -and
        (Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null).decision -eq 'ALLOW' -and
        (Native-Decision $nativeRules 'edit' 'src/cart.ts') -eq 'ALLOW' -and
        (Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null).question -eq 0)

    $need = Decide 'kovan' $operation 'docs/release.md' 'src/**' $rootPath $null
    Check 'AUTH2_OUT_OF_SCOPE_NEED_AUTHORITY' ($need.decision -eq 'NEED_AUTHORITY' -and
        $kovan -match 'STATUS: NEED_AUTHORITY' -and $kovan -match 'OPERATION:' -and
        $kovan -match 'MINIMUM_SCOPE:' -and $kovan -match 'REPOSITORY_ROOT:' -and
        $kovan -match 'TASK_BLOCKED:')

    $approved = Decide 'kovan' $operation '.opencode/plugins/project-owned/index.ts' 'src/**' $rootPath $grant $true $true $false @() 'ASK'
    Check 'AUTH3_EXACT_SCOPE_NATIVE_ASK_GRANT' ($approved.decision -eq 'NATIVE_ASK' -and $approved.reason -eq 'EXACT_NATIVE_ASK_GRANT' -and
        $grant.agent -eq 'kovan' -and $grant.scope -ceq '.opencode/plugins/project-owned/**' -and
        $grant.repository_root -ceq $rootPath -and $grant.permission_mode -ceq 'NATIVE_ASK' -and
        $grant.lifetime -ceq 'current_task' -and $grant.task_id -ceq 'task-7')

    $sibling = Decide 'kovan' $operation '.opencode/plugins/sibling/index.ts' 'src/**' $rootPath $grant $true $true $false @() 'ASK'
    Check 'AUTH4_SIBLING_SCOPE_NEEDS_NEW_AUTHORITY' ($sibling.decision -eq 'NEED_AUTHORITY' -and
        -not (Synthetic-ToolFlow $sibling.decision).attempted)

    $expired = Decide 'kovan' $operation '.opencode/plugins/foo/index.ts' 'src/**' $rootPath $grant $false
    Check 'AUTH5_CURRENT_TASK_EXPIRY' ($expired.decision -eq 'DENY' -and $expired.reason -eq 'GRANT_EXPIRED_OR_WRONG_TASK' -and
        $kael -match 'A grant expires with this task')

    $prohibited = Decide 'kovan' $operation '.opencode/plugins/project-owned/index.ts' 'src/**' $rootPath $grant $true $true $true
    Check 'AUTH6_EXPLICIT_PROHIBITION_DENY_NO_QUESTION' ($prohibited.decision -eq 'DENY' -and $prohibited.question -eq 0 -and
        -not (Synthetic-ToolFlow $prohibited.decision).attempted -and
        $kael -match '(?s)Explicit user prohibitions.*?override every other outcome' -and $kael -match 'do not modify \.opencode')

    $ownedByManifest = Decide 'kovan' $operation '.opencode/plugins/vendor/loader.ts' 'src/**' $rootPath $grant $true $true $false @('.opencode/plugins/vendor')
    Check 'AUTH7_OLYMPUS_OWNED_GRANT_UNAVAILABLE' ($ownedByManifest.decision -eq 'DENY' -and $ownedByManifest.question -eq 0 -and
        -not (Synthetic-ToolFlow $ownedByManifest.decision).attempted -and
        $kael -match '\.opencode/agents/\*\*' -and $kael -match 'Every manifest-declared\s+Olympus-managed resource is protected')

    $pluginResource = '.opencode/plugins/project-owned/index.ts'
    $pluginNative = Native-Decision $nativeRules 'edit' $pluginResource
    $protectedAdjacent = Native-Decision $nativeRules 'edit' '.opencode/commands/project-owned.md'
    $approvedWrite = Write-Decision $pluginNative 'APPROVE_ONCE'
    $rejectedWrite = Write-Decision $pluginNative 'REJECT'
    $pluginNotOwned = Decide 'kovan' $operation $pluginResource 'src/**' $rootPath $null $true $false
    Check 'AUTH8_PROJECT_PLUGIN_NATIVE_ASK_AND_ONE_SHOT' ($pluginNative -eq 'ASK' -and
        $protectedAdjacent -eq 'ASK' -and $approvedWrite -and -not $rejectedWrite -and
        $pluginNotOwned.decision -eq 'DENY' -and $approved.decision -eq 'NATIVE_ASK' -and
        $kovan -match '\.opencode/plugins/\*\*"\s+effect: ask' -and
        $kovan -match '\.opencode/\*\*"\s+effect: ask')

    $siblingPlugin = Native-Decision $nativeRules 'edit' '.opencode/plugins/sibling/index.ts'
    Check 'AUTH8B_ONE_SHOT_APPROVAL_NOT_SIBLING' ($siblingPlugin -eq 'ASK' -and
        -not (Write-Decision $siblingPlugin 'NONE') -and $approvedWrite)

    $activityPath = '.opencode/plugins/olympus-activity/activity.ts'
    $activity = Decide 'kovan' $operation $activityPath 'src/**' $rootPath $grant
    Check 'AUTH9_ACTIVITY_PLUGIN_DENIED' ($activity.decision -eq 'DENY' -and $activity.reason -eq 'OLYMPUS_OWNED' -and
        (Native-Decision $nativeRules 'edit' $activityPath) -eq 'DENY' -and
        $kael -match '\.opencode/plugins/olympus-activity/\*\*')

    foreach ($path in @('.opencode/agents/kovan.md','.opencode/commands/maintain.md',
        '.opencode/orchestrator-install.json','.opencode/opencode.json','.opencode/opencode.jsonc',
        '.codex/agents/kovan.toml','.codex/config.toml','CODEX.md','olympus/core/models.toml',
        'olympus/roles/kael.md','olympus/policies/authority.md','scripts/render_harnesses.py',
        'opencode.json','opencode.jsonc')) {
        Check ('AUTH9_NATIVE_DENY_' + ($path -replace '[^A-Za-z0-9]','_')) ((Native-Decision $nativeRules 'edit' $path) -eq 'DENY')
    }
    $normalAgents = @(Get-ChildItem -LiteralPath (Join-Path $root '.opencode/agents') -Filter '*.md' -File | Where-Object BaseName -ne 'aegis')
    $coreProtectionValid = @($normalAgents | Where-Object {
        $agentRules = Read-NativeRules ([IO.File]::ReadAllText($_.FullName)) @($config.permissions)
        @('olympus/core/models.toml','olympus/roles/kael.md','olympus/policies/authority.md',
          '.codex/config.toml','CODEX.md','scripts/render_harnesses.py' | Where-Object {
            (Native-Decision $agentRules 'edit' $_) -ne 'DENY'
        }).Count -gt 0
    }).Count -eq 0
    Check 'AUTH9_CORE_AND_GENERATOR_PROTECTED_FOR_NORMAL_AGENTS' $coreProtectionValid
    $managedPaths = @('opencode.jsonc', 'CODEX.md', '.opencode/orchestrator-install.json',
        '.codex/orchestrator-install.json')
    foreach ($surface in @('.opencode', '.codex')) {
        $managedPaths += @(Get-ChildItem -LiteralPath (Join-Path $root $surface) -File -Recurse | ForEach-Object {
            $_.FullName.Substring(([IO.Path]::GetFullPath($root).TrimEnd([char[]]@('\','/')).Length + 1)).Replace('\','/')
        })
    }
    Check 'AUTH9B_EVERY_INSTALLER_MANAGED_PATH_HAS_NATIVE_DENY' (@($managedPaths | Where-Object {
        (Native-Decision $nativeRules 'edit' $_) -ne 'DENY'
    }).Count -eq 0)

    $siblingRepoPath = 'C:\workspace\unrelated-sibling\src\cart.ts'
    $externalDecision = Native-Decision $nativeRules 'external_directory' $siblingRepoPath
    $kaelExternalDecision = Native-Decision $kaelNativeRules 'external_directory' $siblingRepoPath
    Check 'AUTH10_EXTERNAL_SIBLING_REQUIRES_ASK' ($externalDecision -eq 'ASK' -and $kaelExternalDecision -eq 'ASK' -and
        @($nativeRules | Where-Object { $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'allow' }).Count -eq 0)

    Check 'AUTH10B_EXPLICIT_PROHIBITION_OVERRIDES_NATIVE_ASK' ((Native-Decision $nativeRules 'edit' $pluginResource $true) -eq 'DENY' -and
        -not (Write-Decision 'DENY' 'APPROVE_ONCE') -and $kael -match '(?s)Explicit user prohibitions.*?override every other outcome')

    $workerPaths = @('.opencode/agents/argus.md','.opencode/agents/atlas.md','.opencode/agents/helios.md',
        '.opencode/agents/kovan.md','.opencode/agents/nox.md','.opencode/agents/orin.md',
        '.opencode/agents/talos.md','.opencode/agents/thales.md','.opencode/agents/vera.md','.opencode/agents/veyra.md')
    $workerTexts = @($workerPaths | ForEach-Object { Text $_ })
    $directAskBlocked = @($workerPaths | Where-Object { $file = Text $_; $file -notmatch '(?s)action: question\s+resource: "?\*"?\s+effect: deny' }).Count -eq 0 -and
        @($workerTexts | Where-Object { $_ -notmatch 'Never ask the user' }).Count -eq 0
    Check 'AUTH10_CHILD_DIRECT_QUESTION_DENIED' $directAskBlocked

    $childSelfRoutes = @($workerPaths | Where-Object { $file = Text $_; $file -notmatch '(?s)action: subagent\s+resource: "?\*"?\s+effect: deny' }).Count
    Check 'AUTH11_CHILD_SELF_ESCALATION_DENIED' ($childSelfRoutes -eq 0 -and
        @($workerTexts | Where-Object { $_ -notmatch 'never (?:ask the user, grant|grant)\s+or infer your own authority' }).Count -eq 0 -and
        $kael -match 'Only veyra, orin, kovan, nox, vera, thales, atlas, argus, talos, and helios are valid child role IDs' -and
        $kael -match 'Kael → Aegis remains DENIED')

    $needs = @(
        [pscustomobject]@{ root=$rootPath; operation='WRITE_SCOPE'; scope='src/one/**' },
        [pscustomobject]@{ root=$rootPath; operation='WRITE_SCOPE'; scope='src/two/**' }
    )
    $compatible = @($needs | Where-Object { $_.root -ceq $rootPath -and $_.operation -ceq 'WRITE_SCOPE' }).Count -eq $needs.Count
    $questionCount = if ($compatible) { 1 } else { $needs.Count }
    $consolidationPolicy = $kael -match '(?s)If multiple needs share the same root and operation.*?consolidate them into one precise user QUESTION'
    $documentedPolicy = $docs -match '(?s)If no applicable native ASK exists.*?compatible needs may be consolidated into\s+one precise Kael QUESTION'
    Check 'AUTH12_COMPATIBLE_NEEDS_CONSOLIDATED' ($questionCount -eq 1 -and $consolidationPolicy -and $documentedPolicy)

    Check 'AUTH13_NATIVE_ASK_NO_DUPLICATE_QUESTION' ($kael -match 'do not send a duplicate Kael\s+QUESTION' -and
        $kovan -match 'Do not open QUESTION, demand textual\s+approval' -and
        $kael -match 'permission_mode: NATIVE_ASK' -and $docs -match 'Kael must not also send a duplicate QUESTION')

    $normalToolDecision = Decide 'kovan' $operation 'src/cart.ts' 'src/**' $rootPath $null
    $normalToolFlow = Synthetic-ToolFlow $normalToolDecision.decision
    Check 'AUTH16_ALLOW_TOOL_EXECUTES_WITHOUT_PREAUTH' ($normalToolDecision.decision -eq 'ALLOW' -and
        $normalToolFlow.attempted -and $normalToolFlow.executed -and $normalToolFlow.continue -and
        $normalToolFlow.question -eq 0 -and $kovan -match 'invoke the required tool\s+directly, without textual pre-authorization')

    $pendingFlow = Synthetic-ToolFlow $approved.decision
    Check 'AUTH17_NATIVE_ASK_ATTEMPT_NOT_BLOCKED' ($approved.decision -eq 'NATIVE_ASK' -and
        $pendingFlow.attempted -and $pendingFlow.pending -and -not $pendingFlow.executed -and
        $pendingFlow.question -eq 0 -and $kovan -match 'Do not open QUESTION, demand textual\s+approval, or report BLOCKED before that tool attempt')

    Check 'AUTH18_NATIVE_ASK_NO_KAEL_QUESTION' ($pendingFlow.question -eq 0 -and
        $kovan -match 'Never ask the user' -and
        $kael -match 'Do not ask when native ASK can obtain the exact required human\s+consent' -and
        $kael -match 'do not send a duplicate Kael\s+QUESTION')

    Check 'AUTH19_NATIVE_ASK_EXACT_SCOPE_AND_TASK_LIFETIME' ($grant.agent -ceq 'kovan' -and
        $grant.operation -ceq $operation -and $grant.scope -ceq '.opencode/plugins/project-owned/**' -and
        $grant.repository_root -ceq $rootPath -and $grant.permission_mode -ceq 'NATIVE_ASK' -and
        $grant.lifetime -ceq 'current_task' -and $grant.task_id -ceq 'task-7' -and
        $kael -match 'same exact scope in WRITE_SCOPE' -and $kael -match 'current task identity')

    $deniedFlow = Synthetic-ToolFlow 'NATIVE_ASK' 'REJECT'
    Check 'AUTH20_NATIVE_DENIAL_NO_FALLBACK_OR_BYPASS' ($deniedFlow.attempted -and
        -not $deniedFlow.pending -and -not $deniedFlow.executed -and -not $deniedFlow.continue -and
        -not $deniedFlow.fallback -and -not $deniedFlow.retry -and
        $kovan -match 'rejection/cancellation without\s+retry, fallback, or bypass')

    $approvedFlow = Synthetic-ToolFlow 'NATIVE_ASK' 'APPROVE_ONCE'
    Check 'AUTH21_NATIVE_APPROVAL_CONTINUES' ($approvedFlow.attempted -and $approvedFlow.executed -and
        $approvedFlow.continue -and -not $approvedFlow.fallback -and
        $kovan -match 'continue only if approved')

    $newScopeNeed = Decide 'kovan' $operation 'docs/release.md' 'src/**' $rootPath $null
    Check 'AUTH22_NEW_SCOPE_NEED_AUTHORITY_TO_KAEL' ($newScopeNeed.decision -eq 'NEED_AUTHORITY' -and
        -not (Synthetic-ToolFlow $newScopeNeed.decision).attempted -and
        $kovan -match '(?s)For otherwise legitimate project\s+work outside the assigned scope.*?STATUS: NEED_AUTHORITY' -and
        $kovan -match 'MINIMUM_SCOPE:' -and $kovan -match 'REPOSITORY_ROOT:')

    $newMinimumScope = '.opencode/plugins/authority-smoke/**'
    $newMode = Classify-NewScope (Native-Decision $nativeRules 'edit' '.opencode/plugins/authority-smoke/index.ts')
    $redelegated = New-Grant 'kovan' $operation $newMinimumScope $rootPath $newMode
    $redelegatedDecision = Decide 'kovan' $operation '.opencode/plugins/authority-smoke/index.ts' 'src/**' $rootPath $redelegated $true $true $false @() 'ASK'
    Check 'AUTH23_KAEL_REDELEGATES_NATIVE_ASK_NO_DUPLICATE_CONSENT' ($newMode -eq 'NATIVE_ASK' -and
        $redelegatedDecision.decision -eq 'NATIVE_ASK' -and $redelegated.scope -ceq $newMinimumScope -and
        $redelegated.permission_mode -ceq 'NATIVE_ASK' -and $redelegated.lifetime -ceq 'current_task' -and
        $redelegated.task_id -ceq 'task-7' -and
        $kael -match 'Kael may delegate only that task to the exact\s+agent' -and
        $kael -match 'Do not ask when native ASK can obtain the exact required human\s+consent')

    $ownedFlow = Synthetic-ToolFlow $ownedByManifest.decision
    Check 'AUTH24_OLYMPUS_OWNED_DENY_BEFORE_TOOL' ($ownedByManifest.decision -eq 'DENY' -and
        -not $ownedFlow.attempted -and $ownedByManifest.reason -eq 'OLYMPUS_OWNED')

    $prohibitionFlow = Synthetic-ToolFlow $prohibited.decision
    Check 'AUTH25_EXPLICIT_PROHIBITION_DENY_BEFORE_TOOL' ($prohibited.decision -eq 'DENY' -and
        -not $prohibitionFlow.attempted -and $prohibited.reason -eq 'USER_PROHIBITION' -and
        (Classify-NewScope 'ASK' $true $true) -eq 'DENY')

    $validRuntimeFixture = '[{"id":"kovan","permissions":[{"action":"edit","resource":"*","effect":"allow"},{"action":"edit","resource":".opencode/plugins/**","effect":"ask"},{"action":"edit","resource":".opencode/plugins/olympus-activity/**","effect":"deny"},{"action":"external_directory","resource":"*","effect":"ask"}]}]'
    $failedRuntimeProbe = Inspect-EffectiveRules 17 $validRuntimeFixture 'fixture runtime error'
    Check 'AUTH14_RUNTIME_COMMAND_FAILURE_HAS_EVIDENCE' (-not $failedRuntimeProbe.passed -and
        $failedRuntimeProbe.evidence -match 'runtime_exit=17' -and $failedRuntimeProbe.evidence -match 'stderr=fixture runtime error')
    $malformedRuntimeProbe = Inspect-EffectiveRules 0 '{malformed json'
    Check 'AUTH14_MALFORMED_JSON_HAS_EVIDENCE' (-not $malformedRuntimeProbe.passed -and
        $malformedRuntimeProbe.evidence -match 'json_parseable=False' -and $malformedRuntimeProbe.evidence -match 'json_error=')
    $missingKovanProbe = Inspect-EffectiveRules 0 '[]'
    Check 'AUTH14_MISSING_KOVAN_HAS_EVIDENCE' (-not $missingKovanProbe.passed -and
        $missingKovanProbe.evidence -match 'json_parseable=True' -and $missingKovanProbe.evidence -match 'kovan=missing')
    $duplicateKovanProbe = Inspect-EffectiveRules 0 '[{"id":"kovan","permissions":[]},{"id":"kovan","permissions":[]}]'
    Check 'AUTH14_DUPLICATE_KOVAN_HAS_EVIDENCE' (-not $duplicateKovanProbe.passed -and
        $duplicateKovanProbe.evidence -match 'kovan=duplicated \(matches=2\)')
    $singleKovanProbe = Inspect-EffectiveRules 0 $validRuntimeFixture
    Check 'AUTH14_SINGLE_KOVAN_EVALUATES_EFFECTIVE_RULES' ($singleKovanProbe.passed -and
        $singleKovanProbe.evidence -match 'kovan_matches=1' -and $singleKovanProbe.evidence -match 'edit_plugins_ask=1/1')
    $badPermissionProbe = Inspect-EffectiveRules 0 '[{"id":"kovan","permissions":[{"action":"edit","resource":"*","effect":"deny"}]}]'
    Check 'AUTH14_SINGLE_KOVAN_RULE_MISMATCH_FAILS' (-not $badPermissionProbe.passed -and
        $badPermissionProbe.evidence -match 'edit_\*_deny=1/0')
    }

    if ($QualificationSlice -ne 'Offline') {
        Invoke-IsolatedAuthorityRuntime
    }

    if ($QualificationSlice -ne 'Runtime') {
    $normalizedDocs = $docs -replace '\s+', ' '
    $reportingPolicy = $normalizedDocs -match '(?is)TOOL_ATTEMPT.*?TOOL_EXECUTION.*?NATIVE_PERMISSION_UI.*?USER_CONFIRMED_EXTERNAL_OBSERVATION.*?NOT_OBSERVABLE.*?Tool success does not establish that ASK was\s+absent.*?tool failure/denial alone does not establish a human rejection'
    Check 'AUTH15_NATIVE_PERMISSION_OBSERVABILITY_POLICY' ($reportingPolicy -and
        $kael -match '(?is)TOOL_ATTEMPT.*?TOOL_EXECUTION.*?NATIVE_PERMISSION_UI.*?NATIVE_PERMISSION_DECISION.*?NOT_OBSERVABLE.*?Tool success does not prove ASK was absent.*?failed\s+or denied tool result does not by itself prove a human rejected.*?USER_CONFIRMED_EXTERNAL_OBSERVATION.*?external/manual evidence' -and
        $kovan -match '(?is)TOOL_ATTEMPT.*?TOOL_EXECUTION.*?NATIVE_PERMISSION_UI.*?NATIVE_PERMISSION_DECISION.*?NOT_OBSERVABLE.*?success never implies\s+`OBSERVED_NO_ASK`.*?USER_CONFIRMED_EXTERNAL_OBSERVATION')

    $uiHiddenSuccess = New-PermissionReport $true 'SUCCESS' 'write completed'
    Check 'AUTH26_PERMISSION_UI_UNOBSERVABLE' ($uiHiddenSuccess.NATIVE_PERMISSION_UI -eq 'NOT_OBSERVABLE' -and
        $uiHiddenSuccess.NATIVE_PERMISSION_DECISION -eq 'NOT_OBSERVABLE' -and $uiHiddenSuccess.TOOL_ATTEMPT -eq 'ATTEMPTED')

    $successNoAskInference = New-PermissionReport $true 'SUCCESS' 'write completed'
    Check 'AUTH27_SUCCESS_DOES_NOT_INFER_ASK_ABSENT' ($successNoAskInference.TOOL_EXECUTION -eq 'SUCCESS' -and
        $successNoAskInference.NATIVE_PERMISSION_UI -eq 'NOT_OBSERVABLE' -and
        $successNoAskInference.NATIVE_PERMISSION_UI -ne 'OBSERVED_NO_ASK' -and
        $successNoAskInference.NATIVE_PERMISSION_DECISION -eq 'NOT_OBSERVABLE')

    $failedNoHumanDecision = New-PermissionReport $true 'FAILED' 'tool returned a permission-related error'
    $deniedNoHumanDecision = New-PermissionReport $true 'NOT_EXECUTED' 'tool denied without an explicit human decision result'
    Check 'AUTH28_FAILURE_OR_DENIAL_DOES_NOT_INVENT_HUMAN_DECISION' ($failedNoHumanDecision.TOOL_EXECUTION -eq 'FAILED' -and
        $failedNoHumanDecision.NATIVE_PERMISSION_UI -eq 'NOT_OBSERVABLE' -and
        $failedNoHumanDecision.NATIVE_PERMISSION_DECISION -eq 'NOT_OBSERVABLE' -and
        $deniedNoHumanDecision.TOOL_EXECUTION -eq 'NOT_EXECUTED' -and
        $deniedNoHumanDecision.NATIVE_PERMISSION_UI -eq 'NOT_OBSERVABLE' -and
        $deniedNoHumanDecision.NATIVE_PERMISSION_DECISION -eq 'NOT_OBSERVABLE')

    $manualConfirmation = New-PermissionReport $true 'SUCCESS' 'write completed' 'NOT_OBSERVABLE' 'NOT_OBSERVABLE' `
        'USER_REPORTED: user saw the native prompt and approved it'
    Check 'AUTH29_LATER_USER_CONFIRMATION_IS_EXTERNAL_EVIDENCE' ($manualConfirmation.NATIVE_PERMISSION_UI -eq 'NOT_OBSERVABLE' -and
        $manualConfirmation.NATIVE_PERMISSION_DECISION -eq 'NOT_OBSERVABLE' -and
        $manualConfirmation.USER_CONFIRMED_EXTERNAL_OBSERVATION -match '^USER_REPORTED:' -and
        $manualConfirmation.USER_CONFIRMED_EXTERNAL_OBSERVATION -match 'saw the native prompt and approved')
    }

    Write-Output 'NATIVE_AUTHORITY_ASK_RUNTIME: NOT ASSESSED BY STATIC QUALIFICATION (report interactive event evidence separately)'
    if ($QualificationSlice -eq 'Runtime') {
        Write-Output 'AUTHORITY RUNTIME QUALIFICATION: PASS (effective OpenCode rules; native ASK UI/decision not assessed)'
    } elseif ($QualificationSlice -eq 'Offline') {
        Write-Output 'AUTHORITY OFFLINE QUALIFICATION: PASS (static contracts and deterministic scope/approval cases; OpenCode query not run)'
    } else {
        Write-Output 'AUTHORITY QUALIFICATION: PASS (static contracts, native/effective rules, and deterministic scope/approval cases; interactive outcome not asserted)'
    }
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'AUTHORITY QUALIFICATION: FAIL'
    exit 1
}
