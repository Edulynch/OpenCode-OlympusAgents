[CmdletBinding()]
param(
    [ValidateSet('opencode')]
    [string]$Harness = 'opencode',
    [string]$SourceVersion = 'local',
    [string]$ProjectTarget = (Get-Location).Path,
    [switch]$VerifyOnly,
    [switch]$DryRun,
    [switch]$Uninstall,
    [switch]$Update
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$SourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$ManifestRelative = 'olympus/orchestrator-install.json'
$OpenCodeConfigRelative = 'opencode.jsonc'
$DefaultAgentReceiptProperty = 'default_agent_receipt'
$OpenCodeGuardIntentRelative = 'olympus/opencode-guard-pending.json'
$GlobalApplyScratch = '.olympus-cli-config-apply'
. (Join-Path $PSScriptRoot 'target-writer-lock.ps1')
$script:ProjectOverrideDetected = $false
$script:ModifiedManagedAgents = @()
$script:ConfirmedModifiedAgentPaths = @()

function Fail([string]$Code, [string]$Message) { throw "$Code`: $Message" }

function Normalize-Relative([string]$Path) {
    $value = $Path.Replace('\','/')
    if (-not $value -or [IO.Path]::IsPathRooted($value) -or $value -match '(^|/)\.\.(/|$)' -or $value -match '(^|/)\.(?:/|$)') {
        Fail 'GLOBAL_MANIFEST_INVALID' "Unsafe managed resource path: $Path"
    }
    return $value.TrimStart('/')
}

function Get-ExistingItemOrNull([string]$Path) {
    try { return Get-Item -LiteralPath $Path -Force -ErrorAction Stop }
    catch {
        if ($_.Exception -is [Management.Automation.ItemNotFoundException] -and
            $_.FullyQualifiedErrorId -like 'PathNotFound,*') { return $null }
        Fail 'GLOBAL_PATH_INSPECTION_FAILED' "Cannot inspect path '$Path': $($_.Exception.Message)"
    }
}

function Assert-SafeDestination([string]$Root, [string]$Relative) {
    $relative = Normalize-Relative $Relative
    $base = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\','/'))
    $full = [IO.Path]::GetFullPath((Join-Path $base ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)))
    $prefix = $base + [IO.Path]::DirectorySeparatorChar
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        Fail 'GLOBAL_PATH_UNSAFE' "Managed destination escapes its configuration root: $Relative"
    }
    $cursor = $base
    foreach ($part in ($relative -split '/')) {
        $cursor = Join-Path $cursor $part
        $item = Get-ExistingItemOrNull $cursor
        if ($null -ne $item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            Fail 'GLOBAL_PATH_UNSAFE' "Managed destination traverses a reparse point: $Relative"
        }
    }
    return $full
}

function Assert-SafeGlobalRoot([string]$Root) {
    if (-not [IO.Path]::IsPathFullyQualified($Root)) { Fail 'GLOBAL_PATH_INVALID' 'Resolved global root is not absolute.' }
    $full = [IO.Path]::GetFullPath($Root)
    $volume = [IO.Path]::GetPathRoot($full)
    if ($full.TrimEnd([char[]]@('\','/')) -ceq $volume.TrimEnd([char[]]@('\','/'))) {
        Fail 'GLOBAL_PATH_INVALID' 'A filesystem root cannot be a global configuration root.'
    }
    $cursor = $volume
    foreach ($part in ($full.Substring($volume.Length) -split '[\\/]+' | Where-Object { $_ })) {
        $cursor = Join-Path $cursor $part
        $item = Get-ExistingItemOrNull $cursor
        if ($null -ne $item -and (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            -not $item.PSIsContainer)) {
            Fail 'GLOBAL_PATH_UNSAFE' 'Global root traverses a reparse point or non-directory component.'
        }
    }
    return $full
}

function Assert-NoPendingGlobalCliTransaction([string]$Root) {
    foreach ($relative in @($GlobalApplyScratch, '.olympus-cli-edit')) {
        $path = Assert-SafeDestination $Root $relative
        $item = Get-ExistingItemOrNull $path
        if ($null -ne $item) {
            Fail 'GLOBAL_APPLY_RECOVERY_PENDING' 'A global apply/source-edit journal is pending; recover it explicitly before using the global installer.'
        }
    }
}

function Get-TextHash([string]$Text) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($sha.ComputeHash($Utf8NoBom.GetBytes($Text)))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Get-FileHashText([string]$Path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($Path)))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Get-OpenCodeRoot {
    if ($env:OPENCODE_CONFIG_DIR) {
        return [IO.Path]::GetFullPath($env:OPENCODE_CONFIG_DIR)
    }
    $opencodeCommands = @(Get-Command opencode -CommandType Application -ErrorAction SilentlyContinue)
    if ($opencodeCommands.Count -eq 0) { Fail 'OPENCODE_UNAVAILABLE' 'OpenCode CLI is required to resolve its current global configuration directory.' }
    $opencode = $opencodeCommands[0]
    $oldLocation = (Get-Location).Path
    try {
        $probeLocation = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        Set-Location -LiteralPath $probeLocation
        $lines = @(& $opencode.Source debug paths 2>&1)
        $exitCode = $LASTEXITCODE
    } finally { Set-Location -LiteralPath $oldLocation }
    if ($exitCode -ne 0) { Fail 'OPENCODE_PATH_DISCOVERY_FAILED' 'opencode debug paths failed outside the project target.' }
    $matches = @($lines | ForEach-Object {
        $match = [regex]::Match([string]$_, '^\s*config\s{2,}(?<path>.+?)\s*$')
        if ($match.Success) { $match.Groups['path'].Value.Trim() }
    } | Where-Object { $_ })
    if ($matches.Count -ne 1 -or -not [IO.Path]::IsPathFullyQualified($matches[0])) {
        Fail 'OPENCODE_PATH_DISCOVERY_FAILED' 'Current OpenCode CLI did not provide exactly one absolute global config path.'
    }
    return [IO.Path]::GetFullPath($matches[0])
}

function Add-GeneratedOutput([System.Collections.IDictionary]$Outputs, [string]$Relative, [string]$SourcePath) {
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) { Fail 'SOURCE_FILE_MISSING' "Generated global resource is missing: $SourcePath" }
    $text = [IO.File]::ReadAllText($SourcePath)
    if ($text -notmatch 'GENERATED BY scripts/render_harnesses\.py') { Fail 'SOURCE_INVALID' "Not a generated Harness Core output: $SourcePath" }
    $Outputs[$Relative] = $text
}

function Get-GlobalOutputs([string]$SelectedHarness) {
    if ($SelectedHarness -cne 'opencode') { Fail 'HARNESS_INVALID' "Unsupported harness '$SelectedHarness'." }
    $outputs = [ordered]@{}
    $agentRoot = Join-Path $SourceRoot '.opencode/agents'
    foreach ($file in @(Get-ChildItem -LiteralPath $agentRoot -Filter '*.md' -File | Sort-Object Name)) {
        Add-GeneratedOutput $outputs ('agents/' + $file.Name) $file.FullName
    }
    $pluginRoot = Join-Path $SourceRoot '.opencode/plugins/olympus-activity'
    foreach ($file in @(Get-ChildItem -LiteralPath $pluginRoot -File -Recurse | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($pluginRoot.Length + 1).Replace('\','/')
        Add-GeneratedOutput $outputs ('plugins/olympus-activity/' + $relative) $file.FullName
    }
    if ($outputs.Count -ne 13) { Fail 'SOURCE_INVALID' "Unexpected OpenCode global resource inventory: $($outputs.Count)." }
    return ,$outputs
}

function Get-OlympusUserConfigPath {
    if ($env:OLYMPUS_CONFIG_FILE) { return [IO.Path]::GetFullPath($env:OLYMPUS_CONFIG_FILE) }
    if ($env:OLYMPUS_CONFIG_HOME) { return Join-Path ([IO.Path]::GetFullPath($env:OLYMPUS_CONFIG_HOME)) 'config.json' }
    $appData = if ($env:APPDATA) { $env:APPDATA } else { [Environment]::GetFolderPath([Environment+SpecialFolder]::ApplicationData) }
    return Join-Path $appData 'Olympus/config.json'
}

function Get-RenderedKaelPrompt([int]$MaxChildren) {
    $pythonExecutable = $env:OLYMPUS_PYTHON
    if (-not $pythonExecutable) {
        $python = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -eq $python) {
            $python = Get-Command python -CommandType Application -ErrorAction SilentlyContinue |
                Select-Object -First 1
        }
        if ($null -ne $python) { $pythonExecutable = $python.Source }
    }
    if (-not $pythonExecutable) { Fail 'PYTHON_UNAVAILABLE' 'A Python 3.11+ executable is required to render a non-default Kael ceiling.' }
    $renderer = Join-Path $SourceRoot 'scripts/render_harnesses.py'
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $pythonExecutable
    $start.UseShellExecute = $false
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
    $start.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
    foreach ($argument in @('-B', $renderer, 'kael', '--root', $SourceRoot,
            '--max-children', [string]$MaxChildren)) {
        $start.ArgumentList.Add([string]$argument)
    }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { Fail 'SOURCE_RENDERER_FAILED' 'Could not start the canonical renderer.' }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $text = $stdout.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) {
            Fail 'SOURCE_RENDERER_FAILED' "The canonical renderer rejected the global Kael ceiling: $($stderr.GetAwaiter().GetResult())"
        }
        return $text
    } catch {
        if ($_.Exception.Message -match 'PYTHON_UNAVAILABLE|SOURCE_RENDERER_FAILED') { throw }
        Fail 'SOURCE_RENDERER_FAILED' 'The canonical renderer could not produce a cap-specific Kael prompt.'
    } finally {
        $process.Dispose()
    }
}

function Apply-OpenCodeUserOverrides([System.Collections.IDictionary]$Outputs) {
    $configPath = Get-OlympusUserConfigPath
    if (-not (Test-Path -LiteralPath $configPath)) { return }
    if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) { Fail 'USER_CONFIG_INVALID' 'Olympus user configuration is not a file.' }
    try { $config = [IO.File]::ReadAllText($configPath) | ConvertFrom-Json -AsHashtable -Depth 100 -ErrorAction Stop }
    catch { Fail 'USER_CONFIG_INVALID' 'Olympus user configuration is not valid JSON.' }
    if ($config -isnot [System.Collections.IDictionary] -or $config.schema_version -ne 1 -or
        $config.overrides -isnot [System.Collections.IDictionary] -or
        @($config.Keys | Where-Object { $_ -cnotin @('schema_version','overrides','orchestration') }).Count -gt 0) {
        Fail 'USER_CONFIG_INVALID' 'Olympus user configuration must use schema_version 1 and an overrides object.'
    }
    $maxChildren = 4
    if ($config.Contains('orchestration')) {
        $orchestration = $config['orchestration']
        if ($orchestration -isnot [System.Collections.IDictionary] -or
            @($orchestration.Keys | Where-Object { $_ -cne 'max_children' }).Count -gt 0 -or
            @($orchestration.Keys | Where-Object { $_ -ceq 'max_children' }).Count -ne 1) {
            Fail 'USER_CONFIG_INVALID' 'Global orchestration may contain only max_children.'
        }
        $maxChildren = $orchestration['max_children']
        if (($maxChildren -isnot [int] -and $maxChildren -isnot [long]) -or
            $maxChildren -lt 1 -or $maxChildren -gt 8) {
            Fail 'USER_CONFIG_INVALID' 'Global max_children must be an integer from 1 to 8.'
        }
        if ($maxChildren -ne 4) {
            $kael = Get-RenderedKaelPrompt ([int]$maxChildren)
            if ([string]$Outputs['agents/kael.md'] -match "`r`n") {
                $kael = $kael.Replace("`n", "`r`n")
            }
            $Outputs['agents/kael.md'] = $kael
        }
    }
    $catalogPath = Join-Path $SourceRoot 'olympus/core/models-dev.json'
    if (-not (Test-Path -LiteralPath $catalogPath -PathType Leaf)) { Fail 'SOURCE_FILE_MISSING' 'The offline Models.dev catalog is missing.' }
    try { $catalog = [IO.File]::ReadAllText($catalogPath) | ConvertFrom-Json -AsHashtable -Depth 30 -ErrorAction Stop }
    catch { Fail 'SOURCE_INVALID' 'The offline Models.dev catalog is invalid JSON.' }
    foreach ($role in $config.overrides.Keys) {
        $override = $config.overrides[$role]
        $relative = "agents/$role.md"
        if ($role -notmatch '^[a-z][a-z0-9_-]*$' -or $override -isnot [System.Collections.IDictionary] -or
            $relative -notin $Outputs.Keys -or @($override.Keys | Where-Object { $_ -notin @('model','effort') }).Count -gt 0) {
            Fail 'USER_CONFIG_INVALID' "Olympus user configuration has an unsupported override for '$role'."
        }
        $modelLine = [regex]::Match([string]$Outputs[$relative], '(?m)^model:\s*(?:"(?<quoted>[^"]+)"|(?<plain>[^\r\n]+))\s*$')
        if (-not $modelLine.Success) { Fail 'SOURCE_INVALID' "The generated OpenCode agent has no single model field: $role." }
        $current = if ($modelLine.Groups['quoted'].Success) { $modelLine.Groups['quoted'].Value } else { $modelLine.Groups['plain'].Value.Trim() }
        $separator = $current.LastIndexOf('#')
        if ($separator -lt 1) { Fail 'SOURCE_INVALID' "The generated OpenCode agent model is malformed: $role." }
        $model = if ($override.Contains('model')) { $override['model'] } else { $current.Substring(0, $separator) }
        $effort = if ($override.Contains('effort')) { $override['effort'] } else { $current.Substring($separator + 1) }
        if ($model -isnot [string] -or $model -notmatch '^[A-Za-z0-9][A-Za-z0-9._:-]*/[A-Za-z0-9][A-Za-z0-9._:/-]*$' -or
            $effort -isnot [string] -or $effort -notmatch '^[A-Za-z][A-Za-z0-9_-]*$') {
            Fail 'USER_CONFIG_INVALID' "Olympus user configuration has an invalid model or effort for '$role'."
        }
        $modelInfo = $catalog.models[$model]
        if ($null -eq $modelInfo) {
            # Honor an explicit provider/model pair without claiming catalog support.
            Write-Warning "Models.dev does not list $model; model and effort compatibility are unverified."
        } elseif ($modelInfo.tool_call -ne $true -or $modelInfo.reasoning -ne $true -or
                  $effort -notin @($modelInfo.efforts)) {
            Fail 'USER_CONFIG_INVALID' "Models.dev does not declare tool, reasoning, and '$effort' support for '$model'."
        }
        $replacement = 'model: "' + $model + '#' + $effort + '"'
        $Outputs[$relative] = [regex]::Replace([string]$Outputs[$relative], '(?m)^model:\s*(?:"[^"]+"|[^\r\n]+)\s*$',
            [System.Text.RegularExpressions.MatchEvaluator]{ param($match) $replacement }, 1)
    }
}

function Assert-OpenCodeUserGuard([string]$Path) {
    # Inspect the effective fallback, not merely the presence of a permission
    # entry. V2 uses the last matching rule, and otherwise ALLOWs external paths.
    $options = [Text.Json.JsonDocumentOptions]::new()
    $options.CommentHandling = [Text.Json.JsonCommentHandling]::Skip
    $options.AllowTrailingCommas = $true
    $document = $null
    try {
        $document = [Text.Json.JsonDocument]::Parse([IO.File]::ReadAllText($Path), $options)
        if ($document.RootElement.ValueKind -ne [Text.Json.JsonValueKind]::Object) {
            Fail 'GLOBAL_EXTERNAL_GUARD_UNSAFE' 'Global OpenCode config must contain a JSON object.'
        }
        $rules = $document.RootElement.GetProperty('permissions')
        if ($rules.ValueKind -ne [Text.Json.JsonValueKind]::Array) {
            Fail 'GLOBAL_EXTERNAL_GUARD_UNSAFE' 'Global OpenCode permissions must be an ordered V2 array.'
        }
        $fallback = 'allow'
        foreach ($rule in $rules.EnumerateArray()) {
            $action = $rule.GetProperty('action').GetString()
            $resource = $rule.GetProperty('resource').GetString()
            $effect = $rule.GetProperty('effect').GetString()
            if (-not $action -or -not $resource -or $effect -cnotin @('allow', 'ask', 'deny')) {
                Fail 'GLOBAL_EXTERNAL_GUARD_UNSAFE' 'Malformed OpenCode V2 global permission rule.'
            }
            # V2 patterns support * and ? only; PowerShell -like also accepts
            # bracket expressions, which would produce a false safety PASS.
            $actionPattern = '\A' + [regex]::Escape($action).Replace('\*', '.*').Replace('\?', '.') + '\z'
            # Repeated wildcards and drive-agnostic patterns (including **,
            # ?*, */**, and ?:/**) can cover effectively every external path.
            # Treat an unanchored ALLOW as a fallback override; only an ALLOW
            # rooted at an explicit drive, Unix directory, UNC share, or home
            # may count as a deliberately scoped user exception.
            $normalizedResource = $resource.Replace('\', '/')
            $scoped = $normalizedResource -match '^[A-Za-z]:/' -or
                $normalizedResource -match '^/[^/*?]+' -or
                $normalizedResource -match '^//[^/*?]+/[^/*?]+' -or
                $normalizedResource -match '^(~/|\$HOME/)'
            # Only pure '*' wildcards match *every* possible resource. A lone
            # '?' DENY matches one character and cannot repair a prior ALLOW.
            $universal = $resource -match '^\*+$'
            if ('external_directory' -cmatch $actionPattern -and
                ($universal -or ($effect -ceq 'allow' -and -not $scoped))) {
                $fallback = $effect
            }
        }
        if ($fallback -notin @('ask', 'deny')) {
            Fail 'GLOBAL_EXTERNAL_GUARD_UNSAFE' 'Global OpenCode config does not end with an ASK or DENY fallback for external_directory. Put {"action":"external_directory","resource":"*","effect":"ask"} before any narrower exceptions, or use DENY.'
        }
    } catch {
        if ($_.Exception.Message -match 'GLOBAL_EXTERNAL_GUARD_UNSAFE') { throw }
        Fail 'GLOBAL_EXTERNAL_GUARD_UNSAFE' 'Cannot validate the existing OpenCode global JSONC permissions; refusing installation without modifying user configuration.'
    } finally {
        if ($null -ne $document) { $document.Dispose() }
    }
}

function Add-OpenCodeGlobalGuard([string]$Root, [System.Collections.IDictionary]$OldEntries,
    [System.Collections.IDictionary]$Outputs, $OldManifest) {
    $json = Assert-SafeDestination $Root 'opencode.json'
    $jsonc = Assert-SafeDestination $Root $OpenCodeConfigRelative
    $hasJson = Test-Path -LiteralPath $json
    $hasJsonc = Test-Path -LiteralPath $jsonc
    if ($hasJson -and $hasJsonc) {
        Fail 'GLOBAL_EXTERNAL_GUARD_UNSAFE' 'Both OpenCode global config formats exist; cannot establish which permissions win. Resolve this before global installation.'
    }
    if ($null -ne (Read-OpenCodeGuardIntent $Root)) {
        if ($hasJson) { Fail 'GLOBAL_GUARD_RECOVERY_CONFLICT' 'A user opencode.json conflicts with pending Olympus guard recovery.' }
        if ($hasJsonc -and (Get-FileHashText $jsonc) -cne (Get-TextHash (Get-OpenCodeDefaultGuard)) -and
            (Get-FileHashText $jsonc) -cne (Get-TextHash (Get-OpenCodeDefaultConfig))) {
            Fail 'GLOBAL_GUARD_RECOVERY_CONFLICT' 'Pending global guard differs from the recorded Olympus source; preserve the file for manual review.'
        }
    }

    $receipt = if ($null -ne $OldManifest) { $OldManifest._validated_default_agent_receipt } else { $null }
    if ($null -ne $receipt -and $receipt.state -ceq 'pending_uninstall') {
        Fail 'GLOBAL_DEFAULT_AGENT_RECOVERY_PENDING' 'An interrupted global uninstall must be resumed before installing or updating.'
    }
    $script:DefaultAgentReceipt = $null
    $script:DefaultAgentConfigPath = $null
    $script:DefaultAgentConfigManagedPath = $null
    $script:DefaultAgentNeedsSet = $false
    $script:DefaultAgentPreserveUserChange = $false

    if ($hasJson -or $hasJsonc) {
        $configPath = if ($hasJson) { $json } else { $jsonc }
        $configRelative = if ($hasJson) { 'opencode.json' } else { $OpenCodeConfigRelative }
        if ($null -eq $OldManifest -and $null -eq (Read-OpenCodeGuardIntent $Root) -and
            $configRelative -ceq $OpenCodeConfigRelative -and
            (Get-FileHashText $configPath) -ceq (Get-TextHash (Get-OpenCodeDefaultGuard))) {
            Fail 'GLOBAL_GUARD_RECOVERY_CONFLICT' 'An unowned OpenCode guard exists without a valid transaction intent; refusing receiptless adoption.'
        }
        if ($OldEntries.ContainsKey($OpenCodeConfigRelative) -and $hasJson) {
            Fail 'GLOBAL_EXTERNAL_GUARD_UNSAFE' 'An unmanaged opencode.json now conflicts with the Olympus-managed opencode.jsonc.'
        }
        if ($null -ne $receipt -and $receipt.config_path -cne $configRelative) {
            if ($receipt.state -ceq 'pending_set') {
                Fail 'GLOBAL_DEFAULT_AGENT_RECOVERY_CONFLICT' 'The recorded OpenCode config format changed during pending default_agent setup.'
            }
            # A deleted/replaced user config is not recreated or adopted under
            # a different filename; leave its new format untouched.
            $script:DefaultAgentReceipt = $receipt
            $script:DefaultAgentPreserveUserChange = $true
            if ($OldEntries.ContainsKey($OpenCodeConfigRelative)) {
                $Outputs[$OpenCodeConfigRelative] = Get-OpenCodeDefaultConfig
                $script:DefaultAgentConfigManagedPath = $OpenCodeConfigRelative
            }
            return
        }
        Assert-OpenCodeUserGuard $configPath
        $snapshot = Read-OpenCodeConfig $configPath
        if ($null -ne $receipt) {
            if ($receipt.state -ceq 'pending_set') {
                $alreadyKael = $snapshot.DefaultPresent -and $snapshot.DefaultValue -ceq 'kael'
                $stillPrevious = if ($receipt.previous_present) {
                    $snapshot.DefaultPresent -and $snapshot.DefaultRaw -ceq $receipt.previous_value_json
                } else { -not $snapshot.DefaultPresent }
                if (-not $alreadyKael -and -not $stillPrevious) {
                    Fail 'GLOBAL_DEFAULT_AGENT_RECOVERY_CONFLICT' 'Pending default_agent set found a third value; preserve the config and reconcile manually.'
                }
                $script:DefaultAgentNeedsSet = -not $alreadyKael
            } elseif (-not ($snapshot.DefaultPresent -and $snapshot.DefaultValue -ceq 'kael')) {
                $script:DefaultAgentPreserveUserChange = $true
            }
            $script:DefaultAgentReceipt = $receipt
        } else {
            if ($snapshot.DefaultPresent -and $snapshot.DefaultValue -ceq 'kael') {
                if ($null -eq $OldManifest -or -not $OldEntries.ContainsKey('agents/kael.md') -or
                    'kael' -in $script:ModifiedManagedAgents) {
                    Fail 'GLOBAL_DEFAULT_AGENT_OWNERSHIP_UNKNOWN' 'Existing default_agent is already kael but no intact old Olympus Kael agent proves ownership; refusing adoption.'
                }
                $script:DefaultAgentReceipt = New-DefaultAgentReceipt $configRelative $true $snapshot.DefaultRaw
            } else {
                $script:DefaultAgentReceipt = New-DefaultAgentReceipt $configRelative $snapshot.DefaultPresent $snapshot.DefaultRaw
                $script:DefaultAgentNeedsSet = $true
            }
        }
        $script:DefaultAgentConfigPath = $configPath
        $recoverGuardIntent = $null -ne (Read-OpenCodeGuardIntent $Root) -and
            $configRelative -ceq $OpenCodeConfigRelative -and
            (Get-FileHashText $configPath) -in @(
                (Get-TextHash (Get-OpenCodeDefaultGuard)),
                (Get-TextHash (Get-OpenCodeDefaultConfig))
            )
        if ($OldEntries.ContainsKey($OpenCodeConfigRelative) -or $recoverGuardIntent) {
            $Outputs[$OpenCodeConfigRelative] = Get-OpenCodeDefaultConfig
            $script:DefaultAgentConfigManagedPath = $OpenCodeConfigRelative
        }
        return
    }

    if ($null -ne $receipt) {
        if ($receipt.state -ceq 'pending_set' -and $OldEntries.ContainsKey($receipt.config_path)) {
            $Outputs[$receipt.config_path] = Get-OpenCodeDefaultConfig
            $script:DefaultAgentReceipt = $receipt
            $script:DefaultAgentConfigPath = Assert-SafeDestination $Root $receipt.config_path
            $script:DefaultAgentConfigManagedPath = $receipt.config_path
            $script:DefaultAgentNeedsSet = $true
            return
        }
        if ($receipt.state -ceq 'pending_set') {
            Fail 'GLOBAL_DEFAULT_AGENT_RECOVERY_CONFLICT' 'The recorded OpenCode config disappeared during pending default_agent setup; it will not be recreated.'
        }
        # The user may delete a previously unowned global config. Keep the
        # receipt for safe uninstall, but never recreate that configuration.
        $script:DefaultAgentReceipt = $receipt
        $script:DefaultAgentPreserveUserChange = $true
        return
    }
    if ($OldEntries.ContainsKey($OpenCodeConfigRelative)) {
        Fail 'GLOBAL_MANAGED_FILE_DRIFT' 'The Olympus-owned OpenCode config disappeared; it will not be recreated.'
    }

    $Outputs[$OpenCodeConfigRelative] = Get-OpenCodeDefaultConfig
    $script:DefaultAgentReceipt = New-DefaultAgentReceipt $OpenCodeConfigRelative $false $null
    $script:DefaultAgentConfigPath = $jsonc
    $script:DefaultAgentConfigManagedPath = $OpenCodeConfigRelative
    $script:DefaultAgentNeedsSet = $true
}

function Read-OpenCodeGuardIntent([string]$Root) {
    $path = Assert-SafeDestination $Root $OpenCodeGuardIntentRelative
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Fail 'GLOBAL_GUARD_RECOVERY_CONFLICT' 'Pending guard intent is not a regular file.'
    }
    try { $intent = [IO.File]::ReadAllText($path) | ConvertFrom-Json -Depth 10 -ErrorAction Stop }
    catch { Fail 'GLOBAL_GUARD_RECOVERY_CONFLICT' 'Pending guard intent is incomplete or invalid; preserve it for manual review.' }
    $expectedHash = Get-TextHash (Get-OpenCodeDefaultGuard)
    if ($intent.schema_version -ne 1 -or $intent.harness -cne 'opencode' -or
        $intent.resource -cne $OpenCodeConfigRelative -or $intent.sha256 -cne $expectedHash) {
        Fail 'GLOBAL_GUARD_RECOVERY_CONFLICT' 'Pending guard intent does not match the expected Olympus guard; refusing recovery.'
    }
    return $intent
}

function Write-OpenCodeGuardIntent([string]$Root) {
    $path = Assert-SafeDestination $Root $OpenCodeGuardIntentRelative
    $intent = ([ordered]@{
        schema_version = 1
        harness = 'opencode'
        resource = $OpenCodeConfigRelative
        sha256 = (Get-TextHash (Get-OpenCodeDefaultGuard))
    } | ConvertTo-Json -Depth 5) + "`n"
    [IO.Directory]::CreateDirectory((Split-Path -Parent $path)) | Out-Null
    # CreateNew means a concurrent or pre-existing marker is never overwritten.
    # Flush the ownership intent before any write to the actual guard begins.
    $stream = [IO.FileStream]::new($path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
        [IO.FileShare]::None, 4096, [IO.FileOptions]::WriteThrough)
    try {
        $bytes = $Utf8NoBom.GetBytes($intent)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
}

function Get-OpenCodeDefaultGuard {
    $source = Join-Path $SourceRoot 'olympus/harnesses/opencode/global-permissions.jsonc'
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        Fail 'SOURCE_FILE_MISSING' 'OpenCode global guard template is missing.'
    }
    # Use the same source bytes as the read-only Python CLI expects, so a
    # manifest-owned guard is verifiable without rewriting user configuration.
    Assert-OpenCodeUserGuard $source
    return [IO.File]::ReadAllText($source)
}

function Skip-JsoncTrivia([string]$Text, [ref]$Index) {
    while ($Index.Value -lt $Text.Length) {
        if ([char]::IsWhiteSpace($Text[$Index.Value])) { $Index.Value++; continue }
        if ($Index.Value + 1 -lt $Text.Length -and $Text[$Index.Value] -ceq '/' -and $Text[$Index.Value + 1] -ceq '/') {
            $Index.Value += 2
            while ($Index.Value -lt $Text.Length -and $Text[$Index.Value] -notin @("`r", "`n")) { $Index.Value++ }
            continue
        }
        if ($Index.Value + 1 -lt $Text.Length -and $Text[$Index.Value] -ceq '/' -and $Text[$Index.Value + 1] -ceq '*') {
            $end = $Text.IndexOf('*/', $Index.Value + 2, [StringComparison]::Ordinal)
            if ($end -lt 0) { Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode JSONC contains an unterminated block comment.' }
            $Index.Value = $end + 2
            continue
        }
        break
    }
}

function Get-JsoncStringEnd([string]$Text, [int]$Start) {
    if ($Start -ge $Text.Length -or $Text[$Start] -cne '"') {
        Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode JSONC contains an invalid object key.'
    }
    $escaped = $false
    for ($index = $Start + 1; $index -lt $Text.Length; $index++) {
        $char = $Text[$index]
        if ($escaped) { $escaped = $false; continue }
        if ($char -ceq '\') { $escaped = $true; continue }
        if ($char -ceq '"') { return ($index + 1) }
    }
    Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode JSONC contains an unterminated string.'
}

function Get-JsoncValueEnd([string]$Text, [int]$Start) {
    if ($Start -ge $Text.Length) { Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode JSONC is missing a property value.' }
    if ($Text[$Start] -ceq '"') { return (Get-JsoncStringEnd $Text $Start) }
    if ($Text[$Start] -cin @('{', '[')) {
        $stack = [System.Collections.Generic.List[char]]::new()
        $stack.Add($Text[$Start])
        for ($index = $Start + 1; $index -lt $Text.Length; $index++) {
            $char = $Text[$index]
            if ($char -ceq '"') { $index = (Get-JsoncStringEnd $Text $index) - 1; continue }
            if ($index + 1 -lt $Text.Length -and $char -ceq '/' -and $Text[$index + 1] -ceq '/') {
                $index += 2
                while ($index -lt $Text.Length -and $Text[$index] -notin @("`r", "`n")) { $index++ }
                continue
            }
            if ($index + 1 -lt $Text.Length -and $char -ceq '/' -and $Text[$index + 1] -ceq '*') {
                $end = $Text.IndexOf('*/', $index + 2, [StringComparison]::Ordinal)
                if ($end -lt 0) { Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode JSONC contains an unterminated block comment.' }
                $index = $end + 1
                continue
            }
            if ($char -cin @('{', '[')) { $stack.Add($char); continue }
            if ($char -cin @('}', ']')) {
                if ($stack.Count -eq 0 -or
                    ($char -ceq '}' -and $stack[$stack.Count - 1] -cne '{') -or
                    ($char -ceq ']' -and $stack[$stack.Count - 1] -cne '[')) {
                    Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode JSONC contains mismatched object or array delimiters.'
                }
                $stack.RemoveAt($stack.Count - 1)
                if ($stack.Count -eq 0) { return ($index + 1) }
            }
        }
        Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode JSONC contains an incomplete object or array value.'
    }
    $index = $Start
    while ($index -lt $Text.Length) {
        if ([char]::IsWhiteSpace($Text[$index]) -or $Text[$index] -cin @(',', '}', ']')) { break }
        if ($index + 1 -lt $Text.Length -and $Text[$index] -ceq '/' -and $Text[$index + 1] -cin @('/', '*')) { break }
        $index++
    }
    if ($index -eq $Start) { Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode JSONC contains an invalid property value.' }
    return $index
}

function Get-JsoncRootMembers([string]$Text) {
    $options = [Text.Json.JsonDocumentOptions]::new()
    $options.CommentHandling = [Text.Json.JsonCommentHandling]::Skip
    $options.AllowTrailingCommas = $true
    $document = $null
    try {
        $document = [Text.Json.JsonDocument]::Parse($Text, $options)
        if ($document.RootElement.ValueKind -ne [Text.Json.JsonValueKind]::Object) {
            Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode global configuration must be a JSON object.'
        }
        $seen = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($property in $document.RootElement.EnumerateObject()) {
            if (-not $seen.Add($property.Name)) {
                Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode global configuration has a duplicate root key.'
            }
        }
    } catch {
        if ($_.Exception.Message -match 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID') { throw }
        Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode global configuration is not valid JSONC.'
    } finally {
        if ($null -ne $document) { $document.Dispose() }
    }

    $index = 0
    Skip-JsoncTrivia $Text ([ref]$index)
    if ($index -ge $Text.Length -or $Text[$index] -cne '{') {
        Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode global configuration must start with an object.'
    }
    $index++
    $members = [System.Collections.Generic.List[object]]::new()
    $commaBefore = -1
    $trailingComma = -1
    Skip-JsoncTrivia $Text ([ref]$index)
    while ($index -lt $Text.Length -and $Text[$index] -cne '}') {
        $keyStart = $index
        $keyEnd = Get-JsoncStringEnd $Text $keyStart
        $keyTokenEnd = $keyEnd
        $keyDocument = [Text.Json.JsonDocument]::Parse($Text.Substring($keyStart, $keyEnd - $keyStart))
        try { $name = $keyDocument.RootElement.GetString() } finally { $keyDocument.Dispose() }
        Skip-JsoncTrivia $Text ([ref]$keyEnd)
        if ($keyEnd -ge $Text.Length -or $Text[$keyEnd] -cne ':') {
            Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode global configuration has a malformed root property.'
        }
        $valueStart = $keyEnd + 1
        Skip-JsoncTrivia $Text ([ref]$valueStart)
        $valueEnd = Get-JsoncValueEnd $Text $valueStart
        $afterValue = $valueEnd
        Skip-JsoncTrivia $Text ([ref]$afterValue)
        $commaAfter = -1
        $hasTrailingComma = $false
        if ($afterValue -lt $Text.Length -and $Text[$afterValue] -ceq ',') {
            $commaAfter = $afterValue
            $index = $afterValue + 1
            Skip-JsoncTrivia $Text ([ref]$index)
            if ($index -lt $Text.Length -and $Text[$index] -ceq '}') {
                $trailingComma = $commaAfter
                $hasTrailingComma = $true
            }
        } elseif ($afterValue -lt $Text.Length -and $Text[$afterValue] -ceq '}') {
            $index = $afterValue
        } else {
            Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode global configuration has malformed root separators.'
        }
        $members.Add([pscustomobject]@{
            Name=$name; KeyStart=$keyStart; ValueStart=$valueStart; ValueEnd=$valueEnd
            KeyEnd=$keyTokenEnd; ColonIndex=$keyEnd
            CommaBefore=$commaBefore; CommaAfter=$commaAfter
        })
        if ($hasTrailingComma) { break }
        if ($commaAfter -lt 0) { break }
        $commaBefore = $commaAfter
        if ($trailingComma -ge 0) { break }
    }
    if ($trailingComma -ge 0) {
        $index = $Text.IndexOf('}', $index)
    }
    if ($index -ge $Text.Length -or $Text[$index] -cne '}') {
        Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode global configuration has no closing object delimiter.'
    }
    $default = @($members | Where-Object { $_.Name -ceq 'default_agent' })
    $value = $null
    $rawValue = $null
    if ($default.Count -eq 1) {
        $member = $default[0]
        $rawValue = $Text.Substring($member.ValueStart, $member.ValueEnd - $member.ValueStart)
        $valueDocument = $null
        try {
            $valueDocument = [Text.Json.JsonDocument]::Parse($rawValue)
            if ($valueDocument.RootElement.ValueKind -ne [Text.Json.JsonValueKind]::String) {
                Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode default_agent must be a string when present.'
            }
            $value = $valueDocument.RootElement.GetString()
        } catch {
            if ($_.Exception.Message -match 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID') { throw }
            Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode default_agent must be a valid string value.'
        } finally {
            if ($null -ne $valueDocument) { $valueDocument.Dispose() }
        }
    }
    return [pscustomobject]@{
        Text=$Text; Members=@($members.ToArray()); CloseIndex=$index; TrailingComma=$trailingComma
        DefaultPresent=($default.Count -eq 1); DefaultValue=$value; DefaultRaw=$rawValue
    }
}

function Read-OpenCodeConfig([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'The recorded OpenCode global config is not a regular file.'
    }
    try { $bytes = [IO.File]::ReadAllBytes($Path) }
    catch { Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'Cannot read the existing OpenCode global config.' }
    $encoding = $null
    $preamble = [byte[]]@()
    $offset = 0
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $encoding = [Text.UTF8Encoding]::new($false, $true); $preamble = [byte[]]@(0xEF,0xBB,0xBF); $offset = 3
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
        $encoding = [Text.UnicodeEncoding]::new($false, $false, $true); $preamble = [byte[]]@(0xFF,0xFE); $offset = 2
    } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
        $encoding = [Text.UnicodeEncoding]::new($true, $false, $true); $preamble = [byte[]]@(0xFE,0xFF); $offset = 2
    } else {
        $encoding = [Text.UTF8Encoding]::new($false, $true)
    }
    try { $text = $encoding.GetString($bytes, $offset, $bytes.Length - $offset) }
    catch { Fail 'GLOBAL_DEFAULT_AGENT_CONFIG_INVALID' 'OpenCode global config has an unsupported or invalid encoding.' }
    $parsed = Get-JsoncRootMembers $text
    return [pscustomobject]@{
        Path=$Path; Bytes=$bytes; Encoding=$encoding; Preamble=$preamble
        Text=$text; Members=$parsed.Members; CloseIndex=$parsed.CloseIndex
        TrailingComma=$parsed.TrailingComma; DefaultPresent=$parsed.DefaultPresent
        DefaultValue=$parsed.DefaultValue; DefaultRaw=$parsed.DefaultRaw
    }
}

function Get-OpenCodeDefaultConfig {
    $guard = Get-OpenCodeDefaultGuard
    $open = $guard.IndexOf('{')
    if ($open -lt 0) { Fail 'SOURCE_INVALID' 'The OpenCode permissions template is not an object.' }
    return ($guard.Substring(0, $open + 1) + "`n  `"default_agent`": `"kael`"," + $guard.Substring($open + 1))
}

function Get-OpenCodeConfigUpdatedText($Snapshot, [string]$RawValue, [switch]$Remove) {
    $snapshot = $Snapshot
    $member = @($snapshot.Members | Where-Object { $_.Name -ceq 'default_agent' })
    $text = $snapshot.Text
    if ($member.Count -eq 1) {
        $entry = $member[0]
        if ($Remove) {
            # Remove tokens only; comments/trivia around an existing field are user bytes.
            $spans = @(
                @{ Start=$entry.KeyStart; Length=($entry.KeyEnd - $entry.KeyStart) },
                @{ Start=$entry.ColonIndex; Length=1 },
                @{ Start=$entry.ValueStart; Length=($entry.ValueEnd - $entry.ValueStart) }
            )
            $comma = if ($entry.CommaAfter -ge 0) { $entry.CommaAfter } else { $entry.CommaBefore }
            if ($comma -ge 0) { $spans += @{ Start=$comma; Length=1 } }
            foreach ($span in @($spans | Sort-Object { $_.Start } -Descending)) {
                $text = $text.Remove($span.Start, $span.Length)
            }
        } elseif ($snapshot.DefaultRaw -cne $RawValue) {
            $text = $text.Substring(0, $entry.ValueStart) + $RawValue + $text.Substring($entry.ValueEnd)
    } else { return $snapshot.Text }
    } elseif (-not $Remove) {
        # Insert no trivia: removing this member later restores the user's bytes.
        $position = $snapshot.CloseIndex
        $addition = '"default_agent":' + $RawValue
        if ($snapshot.Members.Count) {
            $position = $snapshot.Members[0].KeyStart
            $addition += ','
        }
        $text = $text.Insert($position, $addition)
    } else { return $text }
    return $text
}

function Assert-OpenCodeConfigFieldState($Snapshot, [bool]$ExpectedPresent, [string]$ExpectedRaw) {
    if ($Snapshot.DefaultPresent -ne $ExpectedPresent -or
        ($ExpectedPresent -and $Snapshot.DefaultRaw -cne $ExpectedRaw)) {
        Fail 'GLOBAL_DEFAULT_AGENT_RECOVERY_CONFLICT' 'OpenCode default_agent changed after it was accepted; the current user choice was not overwritten.'
    }
}

function Write-OpenCodeConfigField([string]$Path, [string]$RawValue,
    [bool]$ExpectedPresent, [string]$ExpectedRaw, [switch]$Remove) {
    $snapshot = Read-OpenCodeConfig $Path
    Assert-OpenCodeConfigFieldState $snapshot $ExpectedPresent $ExpectedRaw
    $text = Get-OpenCodeConfigUpdatedText $snapshot $RawValue -Remove:$Remove
    if ($text -ceq $snapshot.Text) { return $false }
    [void](Get-JsoncRootMembers $text)
    $encoded = $snapshot.Encoding.GetBytes($text)
    $newBytes = [byte[]]::new($snapshot.Preamble.Length + $encoded.Length)
    if ($snapshot.Preamble.Length) { [Array]::Copy($snapshot.Preamble, 0, $newBytes, 0, $snapshot.Preamble.Length) }
    [Array]::Copy($encoded, 0, $newBytes, $snapshot.Preamble.Length, $encoded.Length)
    $parent = Split-Path -Parent $Path
    $temporary = Join-Path $parent ('.olympus-default-agent-' + [guid]::NewGuid().ToString('N') + '.tmp')
    $item = Get-Item -LiteralPath $Path -Force
    $acl = Get-Acl -LiteralPath $Path
    try {
        $stream = [IO.FileStream]::new($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
            [IO.FileShare]::None, 4096, [IO.FileOptions]::WriteThrough)
        try { $stream.Write($newBytes, 0, $newBytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
        Set-Acl -LiteralPath $temporary -AclObject $acl
        [IO.File]::SetAttributes($temporary, ($item.Attributes -band (-bnot [IO.FileAttributes]::ReparsePoint)))
        # PowerShell coerces $null to ""; Replace requires an actual null backup.
        [IO.File]::Replace($temporary, $Path, [System.Management.Automation.Language.NullString]::Value)
    } catch {
        Fail 'GLOBAL_DEFAULT_AGENT_WRITE_FAILED' 'Could not atomically update the OpenCode default_agent field while preserving file permissions.'
    } finally {
        if (Test-Path -LiteralPath $temporary) { [IO.File]::Delete($temporary) }
    }
    return $true
}

function Get-DefaultAgentReceipt($Manifest) {
    if ($null -eq $Manifest) { return $null }
    $properties = @($Manifest.PSObject.Properties | ForEach-Object Name)
    if ($DefaultAgentReceiptProperty -notin $properties) { return $null }
    $receipt = $Manifest.$DefaultAgentReceiptProperty
    $expectedProperties = @('version','state','config_path','installed_value','previous_present','previous_value_json','restore_action')
    if ($receipt -isnot [System.Management.Automation.PSCustomObject] -or
        @($receipt.PSObject.Properties | ForEach-Object Name | Where-Object { $_ -notin $expectedProperties }).Count -gt 0 -or
        @($expectedProperties | Where-Object { $_ -notin @($receipt.PSObject.Properties | ForEach-Object Name) }).Count -gt 0 -or
        ($receipt.version -isnot [int] -and $receipt.version -isnot [long]) -or $receipt.version -ne 1 -or
        $receipt.state -cnotin @('pending_set','committed','pending_uninstall') -or
        $receipt.config_path -cnotin @('opencode.json','opencode.jsonc') -or
        $receipt.installed_value -cne 'kael' -or $receipt.previous_present -isnot [bool] -or
        $receipt.restore_action -cnotin @('set','remove')) {
        Fail 'GLOBAL_DEFAULT_AGENT_RECEIPT_INVALID' 'OpenCode default_agent receipt is malformed or unsupported.'
    }
    if ($receipt.previous_present) {
        if ($receipt.previous_value_json -isnot [string]) {
            Fail 'GLOBAL_DEFAULT_AGENT_RECEIPT_INVALID' 'OpenCode default_agent receipt has no actual prior value.'
        }
        $previous = $null
        try {
            $previous = [Text.Json.JsonDocument]::Parse([string]$receipt.previous_value_json)
            if ($previous.RootElement.ValueKind -ne [Text.Json.JsonValueKind]::String) {
                Fail 'GLOBAL_DEFAULT_AGENT_RECEIPT_INVALID' 'OpenCode default_agent receipt prior value is not a string.'
            }
            $priorValue = $previous.RootElement.GetString()
        } catch {
            if ($_.Exception.Message -match 'GLOBAL_DEFAULT_AGENT_RECEIPT_INVALID') { throw }
            Fail 'GLOBAL_DEFAULT_AGENT_RECEIPT_INVALID' 'OpenCode default_agent receipt prior value is invalid.'
        } finally {
            if ($null -ne $previous) { $previous.Dispose() }
        }
        $expectedRestore = if ($priorValue -ceq 'kael') { 'remove' } else { 'set' }
        if ($receipt.restore_action -cne $expectedRestore) {
            Fail 'GLOBAL_DEFAULT_AGENT_RECEIPT_INVALID' 'OpenCode default_agent receipt restore action contradicts its recorded prior value.'
        }
    } elseif ($null -ne $receipt.previous_value_json -or $receipt.restore_action -cne 'remove') {
        Fail 'GLOBAL_DEFAULT_AGENT_RECEIPT_INVALID' 'OpenCode default_agent receipt has inconsistent prior absence data.'
    }
    return $receipt
}

function New-DefaultAgentReceipt([string]$ConfigPath, [bool]$Present, [string]$RawValue,
                                [string]$State = 'pending_set') {
    $prior = $null
    if ($Present) {
        $document = [Text.Json.JsonDocument]::Parse($RawValue)
        try { $prior = $document.RootElement.GetString() } finally { $document.Dispose() }
    }
    $restore = if (-not $Present -or $prior -ceq 'kael') { 'remove' } else { 'set' }
    return [ordered]@{
        version=1; state=$State; config_path=$ConfigPath; installed_value='kael'
        previous_present=$Present; previous_value_json=$(if ($Present) { $RawValue } else { $null })
        restore_action=$restore
    }
}

function Set-DefaultAgentReceiptState([object]$Receipt, [string]$State) {
    $copy = [ordered]@{}
    foreach ($key in @('version','state','config_path','installed_value','previous_present','previous_value_json','restore_action')) {
        $value = if ($Receipt -is [System.Collections.IDictionary]) { $Receipt[$key] } else { $Receipt.$key }
        $copy[$key] = if ($key -ceq 'state') { $State } else { $value }
    }
    return $copy
}

function Get-ManifestForWrite($Manifest, [System.Collections.IDictionary]$Entries, $Receipt,
    [string]$Version, [string]$Commit) {
    $files = foreach ($relative in @($Entries.Keys | Sort-Object)) {
        [ordered]@{ path=$relative; sha256=([string]$Entries[$relative].sha256).ToLowerInvariant() }
    }
    $record = [ordered]@{
        schema_version=1; scope='global'; installed_harnesses=@('opencode')
        installed_version=$(if ($Version) { $Version } else { [string]$Manifest.installed_version })
        installed_from_commit=$(if ($Commit) { $Commit } else { [string]$Manifest.installed_from_commit })
        managed_files=@($files)
    }
    if ($null -ne $Receipt) { $record[$DefaultAgentReceiptProperty] = $Receipt }
    return $record
}

function Restore-OpenCodeDefaultAgent([string]$Root, $Receipt) {
    if ($null -eq $Receipt) { return 'not_managed' }
    $json = Assert-SafeDestination $Root 'opencode.json'
    $jsonc = Assert-SafeDestination $Root $OpenCodeConfigRelative
    $hasJson = Test-Path -LiteralPath $json
    $hasJsonc = Test-Path -LiteralPath $jsonc
    if ($hasJson -and $hasJsonc) {
        Fail 'GLOBAL_EXTERNAL_GUARD_UNSAFE' 'Both OpenCode global config formats exist; refusing default_agent restoration.'
    }
    $path = if ($Receipt.config_path -ceq 'opencode.json') { $json } else { $jsonc }
    $other = if ($Receipt.config_path -ceq 'opencode.json') { $jsonc } else { $json }
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        if (Test-Path -LiteralPath $other) { return 'preserved_replaced_config' }
        return 'preserved_deleted_config'
    }
    $snapshot = Read-OpenCodeConfig $path
    $alreadyRestored = if ($Receipt.restore_action -ceq 'remove') {
        -not $snapshot.DefaultPresent
    } else {
        $snapshot.DefaultPresent -and $snapshot.DefaultRaw -ceq $Receipt.previous_value_json
    }
    if ($Receipt.state -ceq 'pending_uninstall' -and $alreadyRestored) {
        return 'already_restored'
    }
    if (-not $snapshot.DefaultPresent) {
        return $(if ($Receipt.restore_action -ceq 'set') { 'preserved_user_change' } else { 'already_restored' })
    }
    if ($snapshot.DefaultValue -cne 'kael') { return 'preserved_user_change' }
    if ($Receipt.restore_action -ceq 'remove') {
        [void](Write-OpenCodeConfigField $path '' $true $snapshot.DefaultRaw -Remove)
        return 'removed_owned_default'
    }
    [void](Write-OpenCodeConfigField $path ([string]$Receipt.previous_value_json) $true $snapshot.DefaultRaw)
    return 'restored_previous_default'
}

function Assert-OpenCodeDefaultAgentCommitted([string]$Root, $Receipt) {
    if ($null -eq $Receipt) {
        Fail 'GLOBAL_DEFAULT_AGENT_RECEIPT_MISSING' 'Global OpenCode default_agent ownership is not recorded; run a normal install/update before VerifyOnly.'
    }
    if ($Receipt.state -cne 'committed') {
        Fail 'GLOBAL_DEFAULT_AGENT_RECOVERY_PENDING' "Default-agent receipt is $($Receipt.state); a regular install or uninstall must reconcile it."
    }
    $json = Assert-SafeDestination $Root 'opencode.json'
    $jsonc = Assert-SafeDestination $Root $OpenCodeConfigRelative
    if ((Test-Path -LiteralPath $json) -and (Test-Path -LiteralPath $jsonc)) {
        Fail 'GLOBAL_EXTERNAL_GUARD_UNSAFE' 'Both OpenCode global config formats exist; default_agent verification is ambiguous.'
    }
    $path = Assert-SafeDestination $Root $Receipt.config_path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        Fail 'GLOBAL_DEFAULT_AGENT_DRIFT' 'The recorded OpenCode global config is missing; VerifyOnly will not recreate it.'
    }
    $snapshot = Read-OpenCodeConfig $path
    if (-not $snapshot.DefaultPresent -or $snapshot.DefaultValue -cne 'kael') {
        Fail 'GLOBAL_DEFAULT_AGENT_DRIFT' 'OpenCode global default_agent is no longer kael; the user value was preserved.'
    }
}

function Write-GlobalManifestObject([string]$Path, [System.Collections.IDictionary]$Manifest) {
    $text = ($Manifest | ConvertTo-Json -Depth 30) + "`n"
    Write-GlobalManifest $Path $text
}

function Test-ManagedDefaultConfigChange([string]$Path) {
    try { $snapshot = Read-OpenCodeConfig $Path } catch { return $false }
    if ($snapshot.DefaultPresent) {
        if ($snapshot.DefaultValue -ceq 'kael') { return $false }
        $normalized = Get-OpenCodeConfigUpdatedText $snapshot '"kael"'
        return $normalized -ceq (Get-OpenCodeDefaultConfig)
    }
    return $snapshot.Text -ceq (Get-OpenCodeDefaultGuard)
}

function Read-GlobalManifest([string]$Root, [string]$Harness, [switch]$Required,
    [System.Collections.IDictionary]$RecoverOutputs = $null, [switch]$AllowModifiedAgents,
    [System.Collections.IDictionary]$ExpectedOutputs = $null) {
    if ($Harness -cne 'opencode') { Fail 'GLOBAL_MANIFEST_INVALID' "Unsupported harness '$Harness'." }
    $script:ModifiedManagedAgents = @()
    $script:DefaultAgentManagedUserChange = $false
    $path = Assert-SafeDestination $Root $ManifestRelative
    if (-not (Test-Path -LiteralPath $path)) {
        if ($Required) { Fail 'GLOBAL_MANIFEST_MISSING' "No Olympus global ownership manifest exists for $Harness." }
        return $null
    }
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { Fail 'GLOBAL_MANIFEST_CONFLICT' 'Global manifest path is not a file.' }
    try {
        $manifestText = [IO.File]::ReadAllText($path)
        $manifest = $manifestText | ConvertFrom-Json -Depth 100 -ErrorAction Stop
        $document = [Text.Json.JsonDocument]::Parse($manifestText)
        try {
            if ($document.RootElement.ValueKind -ne [Text.Json.JsonValueKind]::Object) {
                Fail 'GLOBAL_MANIFEST_INVALID' 'Global ownership manifest must be a JSON object.'
            }
            $rootKeys = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
            $receiptElement = $null
            foreach ($property in $document.RootElement.EnumerateObject()) {
                if (-not $rootKeys.Add($property.Name)) {
                    Fail 'GLOBAL_MANIFEST_INVALID' 'Global ownership manifest contains duplicate root keys.'
                }
                if ($property.Name -ceq $DefaultAgentReceiptProperty) { $receiptElement = $property.Value }
            }
            if ($null -ne $receiptElement) {
                if ($receiptElement.ValueKind -ne [Text.Json.JsonValueKind]::Object) {
                    Fail 'GLOBAL_DEFAULT_AGENT_RECEIPT_INVALID' 'OpenCode default_agent receipt must be an object.'
                }
                $receiptKeys = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
                foreach ($property in $receiptElement.EnumerateObject()) {
                    if (-not $receiptKeys.Add($property.Name)) {
                        Fail 'GLOBAL_DEFAULT_AGENT_RECEIPT_INVALID' 'OpenCode default_agent receipt contains duplicate fields.'
                    }
                }
            }
        } finally { $document.Dispose() }
    }
    catch {
        if ($_.Exception.Message -match 'GLOBAL_DEFAULT_AGENT_RECEIPT_INVALID|GLOBAL_MANIFEST_INVALID') { throw }
        Fail 'GLOBAL_MANIFEST_INVALID' 'Global ownership manifest is invalid JSON.'
    }
    if ($manifest.schema_version -ne 1 -or $manifest.scope -cne 'global' -or
        $manifest.installed_harnesses -isnot [System.Collections.IList] -or
        @($manifest.installed_harnesses).Count -ne 1 -or [string]$manifest.installed_harnesses[0] -cne 'opencode' -or
        $manifest.installed_version -isnot [string] -or [string]::IsNullOrWhiteSpace($manifest.installed_version) -or
        $manifest.installed_from_commit -isnot [string] -or [string]::IsNullOrWhiteSpace($manifest.installed_from_commit) -or
        $manifest.managed_files -isnot [System.Collections.IList]) {
        Fail 'GLOBAL_MANIFEST_INVALID' 'Current global schema v1 metadata is incomplete or unsupported.'
    }
    $receipt = Get-DefaultAgentReceipt $manifest
    if ($null -eq $receipt) {
        Fail 'GLOBAL_DEFAULT_AGENT_RECEIPT_MISSING' 'A current OpenCode global manifest must include a valid default_agent receipt.'
    }
    $baseOutputs = if ($null -ne $ExpectedOutputs) { $ExpectedOutputs } else { Get-GlobalOutputs 'opencode' }
    $expectedBasePaths = @($baseOutputs.Keys)
    $entries = @($manifest.managed_files)
    if ($entries.Count -notin @($expectedBasePaths.Count, ($expectedBasePaths.Count + 1))) {
        Fail 'GLOBAL_MANIFEST_INVALID' 'Global managed_files is not the current 13-resource base inventory or its owned-guard form.'
    }
    $ownsGuard = $entries.Count -eq ($expectedBasePaths.Count + 1)
    if ($ownsGuard -and $receipt.config_path -cne $OpenCodeConfigRelative) {
        Fail 'GLOBAL_MANIFEST_INVALID' 'An owned global guard requires a receipt for opencode.jsonc.'
    }
    $manifest | Add-Member -NotePropertyName '_validated_default_agent_receipt' -NotePropertyValue $receipt -Force
    $seen = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($entry in $entries) {
        $relative = Normalize-Relative ([string]$entry.path)
        if (-not $seen.Add($relative)) { Fail 'GLOBAL_MANIFEST_INVALID' "Duplicate global resource path: $relative" }
        if ($relative -cnotin $expectedBasePaths -and
            -not ($ownsGuard -and $relative -ceq $OpenCodeConfigRelative)) {
            Fail 'GLOBAL_MANIFEST_INVALID' "Managed path is not in the current global inventory: $relative"
        }
        if ([string]$entry.sha256 -notmatch '^(?i:[0-9a-f]{64})$') {
            Fail 'GLOBAL_MANIFEST_INVALID' "Invalid SHA-256 for global resource: $relative"
        }
        $full = Assert-SafeDestination $Root $relative
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
            $pendingOwnedConfig = $null -ne $receipt -and
                (($receipt.state -ceq 'pending_uninstall') -or
                 ($receipt.state -ceq 'pending_set' -and $relative -ceq $receipt.config_path))
            if ($pendingOwnedConfig) { continue }
            Fail 'GLOBAL_MANAGED_FILE_DRIFT' "Managed global file is missing: $relative"
        }
        if ((Get-FileHashText $full) -cne ([string]$entry.sha256).ToLowerInvariant()) {
            if ($AllowModifiedAgents -and $Harness -ceq 'opencode' -and $relative -match '^agents/(?<role>[a-z][a-z0-9_-]*)\.md$') {
                $script:ModifiedManagedAgents += $Matches.role
                continue
            }
            # Only during a pending, hash-verified guard install may a retry
            # roll forward an agent already written from this exact source.
            # Unknown edits still block without touching the user's bytes.
            $recoverDefaultConfig = $null -ne $receipt -and $relative -ceq $receipt.config_path -and
                $receipt.state -in @('pending_set','pending_uninstall') -and
                (Get-FileHashText $full) -ceq (Get-TextHash (Get-OpenCodeDefaultGuard))
            $preservedDefaultConfig = $null -ne $receipt -and $relative -ceq $receipt.config_path -and
                $receipt.state -in @('committed','pending_uninstall') -and
                (Test-ManagedDefaultConfigChange $full)
            if ($preservedDefaultConfig) { $script:DefaultAgentManagedUserChange = $true }
            if (-not $recoverDefaultConfig -and -not $preservedDefaultConfig -and
                ($null -eq $RecoverOutputs -or -not $RecoverOutputs.Contains($relative) -or
                 (Get-FileHashText $full) -cne (Get-TextHash ([string]$RecoverOutputs[$relative])))) {
                Fail 'GLOBAL_MANAGED_FILE_DRIFT' "Managed global file changed: $relative"
            }
        }
    }
    if (@($expectedBasePaths | Where-Object { -not $seen.Contains($_) }).Count -ne 0) {
        Fail 'GLOBAL_MANIFEST_INVALID' 'Global managed_files must include every resource in the current 13-resource base inventory.'
    }
    return $manifest
}

function Confirm-ModifiedManagedAgents {
    $roles = @($script:ModifiedManagedAgents | Sort-Object -Unique)
    if ($roles.Count -eq 0) { return }
    if (-not $Update) { Fail 'GLOBAL_MANAGED_FILE_DRIFT' 'A managed OpenCode agent was changed; no file was overwritten.' }
    $names = @($roles | ForEach-Object {
        $parts = $_ -split '[-_]'
        ($parts | ForEach-Object { if ($_.Length) { $_.Substring(0,1).ToUpperInvariant() + $_.Substring(1) } }) -join ' '
    })
    Write-Host "Hay $($names.Count) agentes de Olympus modificados en este proyecto:"
    foreach ($name in $names) { Write-Host "- $name" }
    $readHost = Get-Command Read-Host -ErrorAction SilentlyContinue
    $mockedPrompt = $null -ne $readHost -and $readHost.CommandType -eq 'Function'
    $nonInteractiveHost = @([Environment]::GetCommandLineArgs() | Where-Object { $_ -match '^(?i:-NonInteractive|-noni)$' }).Count -gt 0
    if ((-not [Environment]::UserInteractive -or [Console]::IsInputRedirected -or $nonInteractiveHost) -and -not $mockedPrompt) {
        Fail 'MODIFIED_AGENT_CONFIRMATION_REQUIRED' 'Managed agents changed; rerun olympus update in an interactive PowerShell 7 terminal to confirm.'
    }
    $answer = Read-Host '¿Quieres sobrescribirlos con la versión nueva? [y/N]'
    if ($answer -notmatch '^(?i:y|yes)$') {
        Fail 'MODIFIED_AGENT_UPDATE_DECLINED' 'Update cancelled; modified agents were preserved.'
    }
    $script:ConfirmedModifiedAgentPaths = @($roles | ForEach-Object { "agents/$_.md" })
}

function Get-ManifestEntryMap($Manifest) {
    $result = @{}
    if ($null -ne $Manifest) { foreach ($entry in @($Manifest.managed_files)) { $result[(Normalize-Relative ([string]$entry.path))] = $entry } }
    return $result
}

function Write-GlobalResource([string]$Path, [string]$Content) {
    $parent = Split-Path -Parent $Path
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    [IO.File]::WriteAllText($Path, $Content, $Utf8NoBom)
}

function Write-NewOpenCodeGuard([string]$Path, [string]$Content) {
    # The earlier preflight cannot reserve this name. CreateNew prevents a
    # user config appearing during installation from ever being truncated.
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
        [IO.FileShare]::None, 4096, [IO.FileOptions]::WriteThrough)
    try {
        $bytes = $Utf8NoBom.GetBytes($Content)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
}

function Assert-NoOpenCodeConfigCollision([string]$Root) {
    # Either supported config format may be user-owned. Recheck both names
    # around publication even when Olympus did not create a managed guard.
    $json = Assert-SafeDestination $Root 'opencode.json'
    $jsonc = Assert-SafeDestination $Root $OpenCodeConfigRelative
    if ((Test-Path -LiteralPath $json) -and (Test-Path -LiteralPath $jsonc)) {
        Fail 'GLOBAL_EXTERNAL_GUARD_UNSAFE' 'Both global OpenCode config formats now exist; preserve both for manual reconciliation.'
    }
}

function Write-GlobalManifest([string]$Path, [string]$Content) {
    $parent = Split-Path -Parent $Path
    [IO.Directory]::CreateDirectory($parent) | Out-Null
    $staged = Join-Path $parent ('.olympus-manifest-' + [guid]::NewGuid().ToString('N') + '.tmp')
    # Flush a complete manifest in the same directory before replacing the
    # ownership record. An interruption must never leave half a JSON manifest.
    $stream = [IO.FileStream]::new($staged, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write,
        [IO.FileShare]::None, 4096, [IO.FileOptions]::WriteThrough)
    try {
        $bytes = $Utf8NoBom.GetBytes($Content)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
    try { [IO.File]::Move($staged, $Path, $true) }
    finally { if (Test-Path -LiteralPath $staged) { [IO.File]::Delete($staged) } }
}

function Get-ProjectOverride([string]$GlobalVersion) {
    $gitCommands = @(Get-Command git -CommandType Application -ErrorAction SilentlyContinue)
    if ($gitCommands.Count -eq 0 -or -not (Test-Path -LiteralPath $ProjectTarget -PathType Container)) { return }
    # Windows PATH may expose multiple Git shims. Invoke exactly one binary.
    $git = $gitCommands[0]
    $projectRoot = (& $git.Source -C $ProjectTarget rev-parse --show-toplevel 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $projectRoot) { return }
    $manifestPath = Join-Path $projectRoot '.opencode/orchestrator-install.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { return }
    try {
        $local = [IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json -Depth 100
        if ($local.schema_version -ne 1 -or $local.scope -cne 'project' -or
            $local.installed_version -isnot [string] -or [string]::IsNullOrWhiteSpace($local.installed_version) -or
            $local.installed_from_commit -isnot [string] -or [string]::IsNullOrWhiteSpace($local.installed_from_commit) -or
            $local.installed_harnesses -isnot [System.Collections.IList] -or
            @($local.installed_harnesses).Count -ne 1 -or [string]$local.installed_harnesses[0] -cne 'opencode') {
            throw 'Current OpenCode project manifest metadata is incomplete or unsupported.'
        }
        $script:ProjectOverrideDetected = $true
        $localVersion = [string]$local.installed_version
        $isDrifted = $false
        foreach ($entry in @($local.managed_files)) {
            $relative = Normalize-Relative ([string]$entry.path)
            $full = Join-Path $projectRoot ($relative -replace '/', [IO.Path]::DirectorySeparatorChar)
            if (-not (Test-Path -LiteralPath $full -PathType Leaf) -or (Get-FileHashText $full) -cne ([string]$entry.sha256).ToLowerInvariant()) { $isDrifted = $true; break }
        }
        $status = if ($isDrifted) { 'modified local resources; preserved' } elseif ($localVersion -cne $GlobalVersion) { "version $localVersion differs from global $GlobalVersion; preserved" } else { "version $localVersion remains a project-local override" }
        Write-Output "PROJECT_LOCAL_OVERRIDE: opencode $status ($projectRoot)"
    } catch {
        Write-Output "PROJECT_LOCAL_OVERRIDE: opencode manifest/path is invalid; preserved at $manifestPath"
    }
}

function Invoke-OneHarness([string]$SelectedHarness, [switch]$LockHeld, [string]$ExpectedRoot) {
    $script:ProjectOverrideDetected = $false
    if ($SelectedHarness -cne 'opencode') { Fail 'HARNESS_INVALID' "Unsupported harness '$SelectedHarness'." }
    $resolvedRoot = Get-OpenCodeRoot
    $root = Assert-SafeGlobalRoot $resolvedRoot
    if (-not $DryRun -and -not $VerifyOnly -and -not $LockHeld) {
        if ($Uninstall -and -not (Test-Path -LiteralPath $root -PathType Container)) {
            Fail 'GLOBAL_INSTALL_CONFLICT' 'Cannot uninstall because the resolved global root does not exist.'
        }
        if (-not $Uninstall) { [IO.Directory]::CreateDirectory($root) | Out-Null }
        $root = Assert-SafeGlobalRoot $root
        $targetLock = $null
        try {
            $targetLock = Enter-OlympusTargetWriterLock $root
            Assert-NoPendingGlobalCliTransaction $root
            Invoke-OneHarness $SelectedHarness -LockHeld -ExpectedRoot $root
        } finally {
            if ($null -ne $targetLock) { Exit-OlympusTargetWriterLock $targetLock }
        }
        return
    }
    if (-not $DryRun -and -not $VerifyOnly -and $LockHeld -and
        -not [string]::Equals($root, $ExpectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Fail 'GLOBAL_PATH_CHANGED' 'Resolved global root changed after the stable target lock was acquired.'
    }
    if ($LockHeld) { Assert-NoPendingGlobalCliTransaction $root }
    $manifestPath = Assert-SafeDestination $root $ManifestRelative
    $guardIntent = if ($SelectedHarness -eq 'opencode') { Read-OpenCodeGuardIntent $root } else { $null }

    if ($Uninstall) {
        if ($null -ne $guardIntent) {
            Fail 'GLOBAL_GUARD_RECOVERY_PENDING' 'Complete the interrupted OpenCode global install before uninstalling its managed resources.'
        }
        $manifest = Read-GlobalManifest $root $SelectedHarness -Required
        $entryMap = Get-ManifestEntryMap $manifest
        $receipt = $manifest._validated_default_agent_receipt
        if ($DryRun) {
            Write-Output "GLOBAL_UNINSTALL_DRY_RUN: $SelectedHarness"
            if ($null -ne $receipt) { Write-Output "RESTORE_DEFAULT_AGENT: $($receipt.state) $($receipt.config_path)" }
            foreach ($relative in @($entryMap.Keys | Sort-Object)) { Write-Output "REMOVE: $relative" }
            Write-Output "REMOVE: $ManifestRelative"
            return
        }
        $restoreResult = 'not_managed'
        if ($null -ne $receipt) {
            $pending = Set-DefaultAgentReceiptState $receipt 'pending_uninstall'
            Write-GlobalManifestObject $manifestPath (Get-ManifestForWrite $manifest $entryMap $pending)
            # An intact wholly-owned config is removed as a file. Rewriting it
            # first would create unrecorded hash drift if uninstall is interrupted.
            $restoreResult = if ($entryMap.ContainsKey($receipt.config_path) -and
                -not $script:DefaultAgentManagedUserChange) { 'remove_owned_config' }
                else { Restore-OpenCodeDefaultAgent $root $pending }
            Write-Output "GLOBAL_DEFAULT_AGENT: $restoreResult"
        }
        $preserveChangedDefaultConfig = $null -ne $receipt -and
            $restoreResult -ceq 'preserved_user_change'
        foreach ($relative in @($entryMap.Keys | Sort-Object)) {
            if ($preserveChangedDefaultConfig -and $relative -ceq $receipt.config_path) {
                Write-Output "PRESERVE_USER_CONFIG: $relative"
                continue
            }
            $full = Assert-SafeDestination $root $relative
            [IO.File]::Delete($full)
        }
        [IO.File]::Delete($manifestPath)
        Write-Output "OLYMPUS_GLOBAL_UNINSTALL: $SelectedHarness REMOVED_MANAGED_RESOURCES_ONLY"
        return
    }

    $outputs = Get-GlobalOutputs $SelectedHarness
    if ($SelectedHarness -eq 'opencode') {
        Apply-OpenCodeUserOverrides $outputs
    }
    $recoverOutputs = if ($null -ne $guardIntent -and -not $VerifyOnly) { $outputs } else { $null }
    $allowModifiedAgents = $Update -and $SelectedHarness -eq 'opencode'
    $manifest = Read-GlobalManifest $root $SelectedHarness -Required:$VerifyOnly `
        -RecoverOutputs $recoverOutputs -AllowModifiedAgents:$allowModifiedAgents -ExpectedOutputs $outputs
    Confirm-ModifiedManagedAgents
    $oldEntries = Get-ManifestEntryMap $manifest
    if ($SelectedHarness -eq 'opencode') {
        Add-OpenCodeGlobalGuard $root $oldEntries $outputs $manifest
    }
    $newEntries = @{}
    $create = [System.Collections.Generic.List[string]]::new()
    $update = [System.Collections.Generic.List[string]]::new()
    $remove = [System.Collections.Generic.List[string]]::new()

    foreach ($relative in @($outputs.Keys | Sort-Object)) {
        $full = Assert-SafeDestination $root $relative
        if ($SelectedHarness -eq 'opencode' -and $script:DefaultAgentPreserveUserChange -and
            $relative -ceq $script:DefaultAgentConfigManagedPath -and $oldEntries.ContainsKey($relative)) {
            $newEntries[$relative] = $oldEntries[$relative]
            continue
        }
        $newEntries[$relative] = [ordered]@{ path=$relative; sha256=Get-TextHash ([string]$outputs[$relative]) }
        if (-not (Test-Path -LiteralPath $full)) { $create.Add($relative); continue }
        if ($oldEntries.ContainsKey($relative)) {
            $pendingDefaultGuard = $SelectedHarness -eq 'opencode' -and
                $null -ne $script:DefaultAgentReceipt -and
                $script:DefaultAgentReceipt.state -ceq 'pending_set' -and
                $relative -ceq $script:DefaultAgentReceipt.config_path -and
                (Get-FileHashText $full) -ceq (Get-TextHash (Get-OpenCodeDefaultGuard))
            if ((Get-FileHashText $full) -cne ([string]$oldEntries[$relative].sha256).ToLowerInvariant()) {
                $confirmedAgent = $relative -in $script:ConfirmedModifiedAgentPaths
                if (-not $pendingDefaultGuard -and -not $confirmedAgent -and
                    ($null -eq $recoverOutputs -or (Get-FileHashText $full) -cne (Get-TextHash ([string]$outputs[$relative])))) {
                    Fail 'GLOBAL_MANAGED_FILE_DRIFT' "Refusing to overwrite modified managed global resource: $relative"
                }
            }
            if ((Get-FileHashText $full) -cne (Get-TextHash ([string]$outputs[$relative]))) { $update.Add($relative) }
        } elseif ((Get-FileHashText $full) -cne (Get-TextHash ([string]$outputs[$relative]))) {
            $pendingGuardCreate = $SelectedHarness -eq 'opencode' -and $relative -ceq $OpenCodeConfigRelative -and
                $null -ne $guardIntent -and
                (Get-FileHashText $full) -ceq (Get-TextHash (Get-OpenCodeDefaultGuard))
            if (-not $pendingGuardCreate) {
                Fail 'GLOBAL_INSTALL_CONFLICT' "User-owned global destination differs from Olympus output: $relative"
            }
            $update.Add($relative)
        }
    }
    foreach ($relative in @($oldEntries.Keys)) { if (-not $newEntries.ContainsKey($relative)) { $remove.Add($relative) } }
    foreach ($relative in $remove) { [void](Assert-SafeDestination $root $relative) }

    if ($VerifyOnly) {
        if ($null -ne $guardIntent) {
            Fail 'GLOBAL_GUARD_RECOVERY_PENDING' 'Pending OpenCode guard ownership must be reconciled by a regular install.'
        }
        if ($SelectedHarness -eq 'opencode') {
            Assert-OpenCodeDefaultAgentCommitted $root $manifest._validated_default_agent_receipt
        }
        if ($null -ne $manifest -and [string]$manifest.installed_version -cne $SourceVersion) {
            Fail 'GLOBAL_VERSION_DRIFT' "Global manifest records '$($manifest.installed_version)'; requested '$SourceVersion'."
        }
        if ($create.Count -or $update.Count -or $remove.Count) {
            Fail 'GLOBAL_MANAGED_FILE_DRIFT' "Global $SelectedHarness installation differs from the requested source (create=$($create.Count), update=$($update.Count), remove=$($remove.Count))."
        }
        Write-Output "OLYMPUS_GLOBAL_VERIFY: $SelectedHarness $SourceVersion PASS (read-only; $($outputs.Count) managed resources)"
        return
    }
    if ($DryRun) {
        Write-Output "GLOBAL_INSTALL_DRY_RUN: $SelectedHarness"
        foreach ($relative in $create) { Write-Output "CREATE: $relative" }
        foreach ($relative in $update) { Write-Output "UPDATE: $relative" }
        foreach ($relative in $remove) { Write-Output "REMOVE: $relative" }
        if ($SelectedHarness -eq 'opencode' -and $script:DefaultAgentNeedsSet) {
            Write-Output 'SET_DEFAULT_AGENT: kael'
        } elseif ($SelectedHarness -eq 'opencode' -and $script:DefaultAgentPreserveUserChange) {
            Write-Output 'PRESERVE_DEFAULT_AGENT: user value or deletion'
        }
        return
    }

    $commit = (& git -C $SourceRoot rev-parse HEAD 2>$null | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $commit) { $commit = 'unknown' }
    $receiptToCommit = Set-DefaultAgentReceiptState $script:DefaultAgentReceipt 'committed'
    $writeRecord = Get-ManifestForWrite $manifest $newEntries $receiptToCommit $SourceVersion $commit
    $manifestText = ($writeRecord | ConvertTo-Json -Depth 30) + "`n"
    $manifestHash = Get-TextHash $manifestText
    $manifestChanged = -not (Test-Path -LiteralPath $manifestPath) -or (Get-FileHashText $manifestPath) -cne $manifestHash
    if ($SelectedHarness -eq 'opencode' -and $null -eq $guardIntent -and $OpenCodeConfigRelative -in $create) {
        # A crash between writing an unowned config and the manifest used to
        # orphan the guard. This durable intent makes that state recoverable.
        Write-OpenCodeGuardIntent $root
        $guardIntent = Read-OpenCodeGuardIntent $root
    }
    foreach ($relative in $remove) { [IO.File]::Delete((Assert-SafeDestination $root $relative)) }
    foreach ($relative in @($outputs.Keys | Sort-Object)) {
        if ($relative -in $create -or $relative -in $update) {
            if ($SelectedHarness -eq 'opencode' -and $script:DefaultAgentNeedsSet -and
                $relative -ceq $script:DefaultAgentConfigManagedPath) { continue }
            $destination = Assert-SafeDestination $root $relative
            if ($SelectedHarness -eq 'opencode' -and $relative -ceq $OpenCodeConfigRelative -and $relative -in $create) {
                Write-NewOpenCodeGuard $destination ([string]$outputs[$relative])
            } else {
                Write-GlobalResource $destination ([string]$outputs[$relative])
            }
        }
    }
    if ($SelectedHarness -eq 'opencode' -and $script:DefaultAgentNeedsSet) {
        $pendingReceipt = Set-DefaultAgentReceiptState $script:DefaultAgentReceipt 'pending_set'
        $pendingRecord = Get-ManifestForWrite $manifest $newEntries $pendingReceipt $SourceVersion $commit
        Write-GlobalManifestObject $manifestPath $pendingRecord
        $configPath = Assert-SafeDestination $root $pendingReceipt.config_path
        if ($script:DefaultAgentConfigManagedPath) {
            if ($pendingReceipt.config_path -in $create) {
                Write-NewOpenCodeGuard $configPath ([string]$outputs[$pendingReceipt.config_path])
            } else {
                Assert-OpenCodeConfigFieldState (Read-OpenCodeConfig $configPath) `
                    $pendingReceipt.previous_present $pendingReceipt.previous_value_json
                Write-GlobalResource $configPath ([string]$outputs[$pendingReceipt.config_path])
            }
        } elseif (Test-Path -LiteralPath $configPath -PathType Leaf) {
            [void](Write-OpenCodeConfigField $configPath '"kael"' `
                $pendingReceipt.previous_present $pendingReceipt.previous_value_json)
        } else {
            Fail 'GLOBAL_DEFAULT_AGENT_RECOVERY_CONFLICT' 'The recorded user config disappeared before default_agent could be set; it was not recreated.'
        }
        Assert-NoOpenCodeConfigCollision $root
        Write-GlobalManifestObject $manifestPath $writeRecord
    } elseif ($manifestChanged) {
        Write-GlobalManifestObject $manifestPath $writeRecord
    }
    if ($SelectedHarness -eq 'opencode') {
        Assert-NoOpenCodeConfigCollision $root
    }
    if ($null -ne $guardIntent) {
        # Manifest ownership is now durable; the recovery marker is redundant.
        [IO.File]::Delete((Assert-SafeDestination $root $OpenCodeGuardIntentRelative))
    }
    Get-ProjectOverride $SourceVersion
    $status = if (-not ($create.Count -or $update.Count -or $remove.Count -or $manifestChanged)) { 'NO_CHANGES' } else { 'READY' }
    Write-Output "OLYMPUS_GLOBAL_INSTALL: OPENCODE $SourceVersion $status ($($outputs.Count) managed resources; root=$root)"
    if ($script:ProjectOverrideDetected) { Write-Output 'OLYMPUS_GLOBAL_MIGRATION: GLOBAL_INSTALLED PROJECT_LOCAL_REMAINS_AS_OVERRIDE' }
    Write-Output 'GLOBAL_DEFAULT_AGENT: kael selected on first install; later user choices and deletions preserved.'
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { Fail 'PLATFORM_UNQUALIFIED' 'Global installation currently requires Windows; Unix path layouts are documented but not installer-qualified.' }
    if ($VerifyOnly -and $DryRun) { Fail 'VERIFY_MODE_INVALID' '-VerifyOnly and -DryRun cannot be combined.' }
    if ($VerifyOnly -and $Uninstall) { Fail 'VERIFY_MODE_INVALID' '-VerifyOnly and -Uninstall cannot be combined.' }
    $selected = @('opencode')
    $failures = [System.Collections.Generic.List[string]]::new()
    foreach ($name in $selected) {
        try { Invoke-OneHarness $name }
        catch { $failures.Add("$name`: $($_.Exception.Message)"); Write-Output "GLOBAL_HARNESS_FAILED: $name $($_.Exception.Message)" }
    }
    if ($failures.Count) { throw ('GLOBAL_INSTALL_PARTIAL_OR_FAILED: ' + ($failures -join ' | ')) }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
