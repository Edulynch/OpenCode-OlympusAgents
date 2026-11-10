[CmdletBinding()]
param(
    [string]$SourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..')),
    [int]$TimeoutSeconds = 45,
    [switch]$NativeToolRead
)

# The default smoke validates V2's permission engine without a model or GUI.
# NativeToolRead additionally uses a loopback-only, deterministic fake model
# to exercise the real read tool; no paid provider or user approval is involved.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$run = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('opencode/oa121-native-api-' + [guid]::NewGuid().ToString('N'))
$configRoot = Join-Path $run 'xdg-config/opencode'
$appRoot = Join-Path $run 'app'
$allowedRoot = Join-Path $run 'allowed'
$forbiddenRoot = Join-Path $run 'forbidden'
$envNames = @('OPENCODE_CONFIG_DIR', 'OPENCODE_CONFIG_CONTENT', 'OPENCODE_CONFIG',
    'OPENCODE_SERVER_PASSWORD', 'OPENCODE_SERVER_USERNAME',
    'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME')
$previous = @{}
$serverProcess = $null
$modelJob = $null
$client = $null
$sessionId = ''
$base = ''
$completed = $false
foreach ($name in $envNames) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }

function Fail([string]$Reason) { throw "OA121_NATIVE_PERMISSION_API_BLOCKED: $Reason" }

function JsonContent($Value) {
    $json = $Value | ConvertTo-Json -Depth 15 -Compress
    return [Net.Http.StringContent]::new($json, [Text.Encoding]::UTF8, 'application/json')
}

function Get-Json([Net.Http.HttpClient]$Client, [string]$Uri) {
    $reply = $Client.GetAsync($Uri).GetAwaiter().GetResult()
    if (-not $reply.IsSuccessStatusCode) { Fail "GET $Uri returned HTTP $([int]$reply.StatusCode)." }
    $text = $reply.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    return ConvertFrom-Json -InputObject $text -Depth 40
}

function PermissionRecords($Response) {
    if ($null -eq $Response) { return @() }
    $items = if ('data' -in @($Response.PSObject.Properties.Name)) { $Response.data } else { $Response }
    return @($items)
}

function PermissionOutcome($Response, [string]$Label) {
    # Native V2 evaluates a request immediately. An ASK returns its request ID
    # and remains in the pending list until the client replies separately.
    if ($null -eq $Response) { Fail "$Label returned no permission outcome." }
    $outcome = if ('data' -in @($Response.PSObject.Properties.Name)) { $Response.data } else { $Response }
    if ($null -eq $outcome -or
        'effect' -notin @($outcome.PSObject.Properties.Name) -or
        'id' -notin @($outcome.PSObject.Properties.Name)) {
        Fail "$Label did not return the native permission ID and effect."
    }
    return $outcome
}

function Post-Json([Net.Http.HttpClient]$Client, [string]$Uri, $Body) {
    $reply = $Client.PostAsync($Uri, (JsonContent $Body)).GetAwaiter().GetResult()
    if (-not $reply.IsSuccessStatusCode) { Fail "POST $Uri returned HTTP $([int]$reply.StatusCode)." }
    $text = $reply.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }
    return ConvertFrom-Json -InputObject $text -Depth 40
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { Fail 'Windows V2 runtime is required.' }
    if ($TimeoutSeconds -lt 15 -or $TimeoutSeconds -gt 180) { Fail 'TimeoutSeconds must be between 15 and 180.' }
    $opencode = (opencode --version | Out-String).Trim()
    $latest = (npm view @opencode/cli version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $opencode -cne "opencode v$latest") {
        Fail "Latest stable OpenCode V2 gate failed (native=$opencode; published=$latest)."
    }
    foreach ($directory in @($configRoot, $appRoot, $allowedRoot, $forbiddenRoot)) {
        [IO.Directory]::CreateDirectory($directory) | Out-Null
    }
    & git -C $appRoot init --quiet
    if ($LASTEXITCODE -ne 0) { Fail 'Cannot initialize the temporary project.' }

    # Model the standard global XDG directory, not an additional custom config
    # directory: V2 may discover agents differently in the two locations.
    Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
    Remove-Item Env:OPENCODE_CONFIG -ErrorAction SilentlyContinue
    $env:XDG_CONFIG_HOME = Join-Path $run 'xdg-config'
    $env:XDG_DATA_HOME = Join-Path $run 'xdg-data'
    $env:XDG_CACHE_HOME = Join-Path $run 'xdg-cache'
    $env:XDG_STATE_HOME = Join-Path $run 'xdg-state'
    $env:OPENCODE_SERVER_USERNAME = 'opencode'
    $password = [guid]::NewGuid().ToString('N')
    $env:OPENCODE_SERVER_PASSWORD = $password

    if ($NativeToolRead) {
        # A canned local provider issues exactly one read call. A real model
        # could choose a different tool, which would weaken the security test.
        $sentinelFile = Join-Path $forbiddenRoot 'smoke/forbidden.txt'
        [IO.Directory]::CreateDirectory((Split-Path -Parent $sentinelFile)) | Out-Null
        $sentinel = 'OA121_NATIVE_DENY_' + [guid]::NewGuid().ToString('N')
        [IO.File]::WriteAllText($sentinelFile, $sentinel)
        $modelListener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
        try {
            $modelListener.Start()
            $modelPort = $modelListener.LocalEndpoint.Port
        } finally { $modelListener.Stop() }
        $modelJob = Start-Job -ArgumentList @($modelPort, $sentinelFile) -ScriptBlock {
            param($Port, $SentinelPath)
            $ErrorActionPreference = 'Stop'
            $http = [Net.HttpListener]::new()
            $http.Prefixes.Add("http://127.0.0.1:$Port/")
            try {
                $http.Start()
                $turn = 0
                while ($turn -lt 2) {
                    $context = $http.GetContext()
                    $route = $context.Request.Url.AbsolutePath
                    if ($route -eq '/health') {
                        $context.Response.StatusCode = 200
                        $context.Response.Close()
                        continue
                    }
                    if ($route -eq '/shutdown') {
                        # End the listener through its own loop so normal
                        # failures do not leave a blocked background job.
                        $context.Response.StatusCode = 200
                        $context.Response.Close()
                        break
                    }
                    if ($route -ne '/v1/chat/completions' -or $context.Request.HttpMethod -ne 'POST') {
                        $context.Response.StatusCode = 404
                        $context.Response.Close()
                        continue
                    }
                    # Read the entire request before responding, avoiding a
                    # premature TCP close that some HTTP clients treat as reset.
                    $reader = [IO.StreamReader]::new($context.Request.InputStream)
                    $null = $reader.ReadToEnd()
                    $reader.Dispose()
                    $turn++
                    $delta = if ($turn -eq 1) {
                        $argsJson = @{ filePath=$SentinelPath } | ConvertTo-Json -Compress
                        @{ role='assistant'; tool_calls=@(@{
                            index=0; id='call_oa121_read'; type='function'
                            function=@{ name='read'; arguments=$argsJson }
                        }) }
                    } else {
                        @{ role='assistant'; content='OA121 completed without file content.' }
                    }
                    $finish = if ($turn -eq 1) { 'tool_calls' } else { 'stop' }
                    $frame = @{
                        id="chatcmpl-oa121-$turn"; object='chat.completion.chunk'
                        created=0; model='reader'
                        choices=@(@{ index=0; delta=$delta; finish_reason=$null })
                    } | ConvertTo-Json -Depth 15 -Compress
                    $endFrame = @{
                        id="chatcmpl-oa121-$turn"; object='chat.completion.chunk'
                        created=0; model='reader'
                        choices=@(@{ index=0; delta=@{}; finish_reason=$finish })
                    } | ConvertTo-Json -Depth 15 -Compress
                    $events = "data: $frame`n`ndata: $endFrame`n`ndata: [DONE]`n`n"
                    $bytes = [Text.Encoding]::UTF8.GetBytes($events)
                    $context.Response.ContentType = 'text/event-stream'
                    $context.Response.ContentLength64 = $bytes.Length
                    $context.Response.OutputStream.Write($bytes, 0, $bytes.Length)
                    $context.Response.Close()
                }
            } finally {
                $http.Stop()
                $http.Close()
            }
        }
        # Only the disposable server sees this provider declaration. The
        # installed global guard remains independently discoverable.
        $env:OPENCODE_CONFIG_CONTENT = (@{
            providers=@{
                oa121local=@{
                    name='OA121 isolated fake model'
                    package='@opencode/ai/providers/openai-compatible'
                    settings=@{ baseURL="http://127.0.0.1:$modelPort/v1"; apiKey='fixture-only' }
                    models=@{
                        reader=@{
                            modelID='reader'; capabilities=@{ tools=$true; input=@('text'); output=@('text') }
                            limit=@{ context=32768; output=4096 }
                        }
                    }
                }
            }
        } | ConvertTo-Json -Depth 15 -Compress)
    }

    # Never install into a real home directory if this OpenCode build ignores
    # XDG_CONFIG_HOME. Verify the exact native path before touching a target.
    $debugPaths = @(opencode debug paths)
    if ($LASTEXITCODE -ne 0) { Fail 'Cannot inspect native global configuration path.' }
    $nativeRoots = @($debugPaths | ForEach-Object {
        $match = [regex]::Match([string]$_, '^\s*config\s{2,}(?<path>.+?)\s*$')
        if ($match.Success) { $match.Groups['path'].Value.Trim() }
    } | Where-Object { $_ })
    if ($nativeRoots.Count -ne 1 -or
        -not [IO.Path]::GetFullPath($nativeRoots[0]).Equals([IO.Path]::GetFullPath($configRoot), [StringComparison]::OrdinalIgnoreCase)) {
        Fail 'Native default global config path is not the isolated XDG root; refusing installation.'
    }
    Write-Output 'NATIVE_GLOBAL_XDG_ROOT: ISOLATED'

    # A global-only Olympus install is the subject of this test. No project
    # Olympus assets or user-global settings are installed or mutated.
    $installer = Join-Path $SourceRoot 'scripts/global-install.ps1'
    # The installer override pins the already-verified root only for the copy.
    # The server itself runs WITHOUT this override to exercise true global mode.
    $env:OPENCODE_CONFIG_DIR = $configRoot
    $installText = (& pwsh -NoProfile -File $installer -Harness opencode -SourceVersion local -ProjectTarget $appRoot 2>&1 | Out-String)
    Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -ne 0) { Fail "Isolated global installation failed: $installText" }
    $manifest = Get-Content -LiteralPath (Join-Path $configRoot 'olympus/orchestrator-install.json') -Raw | ConvertFrom-Json
    if (@($manifest.managed_files).Count -ne 14) { Fail 'Global-only manifest does not own 14 expected resources.' }

    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    try {
        $listener.Start()
        $port = $listener.LocalEndpoint.Port
    } finally { $listener.Stop() }
    $base = "http://127.0.0.1:$port"
    $serverProcess = Start-Process -FilePath (Get-Process -Id $PID).Path `
        -WorkingDirectory $appRoot -ArgumentList @('-NoProfile', '-Command', "opencode serve --hostname 127.0.0.1 --port $port") `
        -RedirectStandardOutput (Join-Path $run 'server.out') -RedirectStandardError (Join-Path $run 'server.err') -PassThru

    $handler = [Net.Http.HttpClientHandler]::new()
    $handler.UseProxy = $false
    $client = [Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
    $credentials = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("opencode:$password"))
    $client.DefaultRequestHeaders.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new('Basic', $credentials)
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $ready = $false
    $lastReadinessStatus = 'not_reached'
    while ([DateTime]::UtcNow -lt $deadline) {
        if ($serverProcess.HasExited) { Fail 'Isolated OpenCode server exited during startup.' }
        try {
            # /api/location is a documented V2 readiness route; the legacy
            # /api/health path is not part of the current V2 API contract.
            $health = $client.GetAsync("$base/api/location").GetAwaiter().GetResult()
            $lastReadinessStatus = [string][int]$health.StatusCode
            if ($health.IsSuccessStatusCode) { $ready = $true; break }
        } catch [Net.Http.HttpRequestException] { $lastReadinessStatus = 'connection_pending' }
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) { Fail "Isolated OpenCode server did not become ready (last HTTP status=$lastReadinessStatus)." }
    # Establish that the native server actually discovered the isolated global
    # guard. Merely creating the file via the installer is insufficient.
    $configEntries = @(PermissionRecords (Get-Json $client "$base/api/config"))
    $guardDocuments = @($configEntries | Where-Object {
        $null -ne $_ -and 'path' -in @($_.PSObject.Properties.Name) -and
        ([string]$_.path).Replace('\', '/') -like '*/opencode.jsonc'
    })
    if ($guardDocuments.Count -ne 1) {
        Fail "Native config discovery did not identify exactly one isolated global guard (found=$($guardDocuments.Count))."
    }
    $guardRules = @($guardDocuments[0].info.permissions)
    if (@($guardRules | Where-Object {
        $_.action -eq 'external_directory' -and $_.resource -eq '*' -and $_.effect -eq 'ask'
    }).Count -ne 1) {
        Fail 'The native config document does not expose the required external-directory ASK fallback.'
    }
    Write-Output 'NATIVE_GLOBAL_GUARD_DOCUMENT: DISCOVERED'
    # Agent registration can finish after the location endpoint becomes ready.
    # Observe the actual catalog, and fail with IDs only if Kovan never appears.
    $agentDeadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $agent = $null
    $registeredAgentIds = @()
    while ([DateTime]::UtcNow -lt $agentDeadline) {
        $agents = @(PermissionRecords (Get-Json $client "$base/api/agent"))
        $registeredAgentIds = @($agents | Where-Object { $null -ne $_ } | ForEach-Object { [string]$_.id })
        $matches = @($agents | Where-Object { $null -ne $_ -and $_.id -eq 'kovan' })
        if ($matches.Count -eq 1) { $agent = $matches[0]; break }
        Start-Sleep -Milliseconds 500
    }
    if ($null -eq $agent) {
        Fail "Native Kovan missing from the agent catalog (registered IDs=$($registeredAgentIds -join ','))."
    }
    if ($null -eq $agent -or 'permissions' -notin @($agent.PSObject.Properties.Name)) {
        Fail 'Native Kovan agent is not registered with a readable permission ruleset.'
    }
    $nativeExternalRules = @($agent.permissions | Where-Object {
        $null -ne $_ -and $_.action -in @('*', 'external_directory')
    })
    $nativeRuleSummary = (@($nativeExternalRules | ForEach-Object {
        "$($_.action):$($_.resource):$($_.effect)"
    }) -join ',')
    Write-Output "NATIVE_KOVAN_EXTERNAL_RULES: $nativeRuleSummary"
    $session = Post-Json $client "$base/api/session" @{ title='OA121 isolated global permission API' }
    if ($null -eq $session) { Fail 'Session creation returned an empty response.' }
    $sessionKeys = @($session.PSObject.Properties.Name)
    $sessionObject = $session
    if ('data' -in $sessionKeys) { $sessionObject = $session.data }
    elseif ('session' -in $sessionKeys) { $sessionObject = $session.session }
    elseif ('info' -in $sessionKeys) { $sessionObject = $session.info }
    $sessionObjectKeys = if ($null -ne $sessionObject) { @($sessionObject.PSObject.Properties.Name) } else { @() }
    if ('id' -notin $sessionObjectKeys) {
        # Field names suffice to diagnose API envelopes without logging any
        # credentials or session content from the disposable host.
        Fail "Session creation did not expose an ID (keys=$($sessionKeys -join ','); nested=$($sessionObjectKeys -join ','))."
    }
    $sessionId = [string]$sessionObject.id
    if (-not $sessionId) { Fail 'Session creation returned a blank ID.' }

    $allowedPattern = $allowedRoot.Replace('\', '/').TrimEnd('/') + '/*'
    $forbiddenPattern = $forbiddenRoot.Replace('\', '/').TrimEnd('/') + '/*'
    $askRequest = @{ agent='kovan'; action='external_directory'; resources=@($allowedPattern); save=@($allowedPattern) }
    # A native ASK returns immediately; its ID must then be present among
    # pending requests. Reject through the official API without a GUI prompt.
    $askOutcome = PermissionOutcome (Post-Json $client "$base/api/session/$sessionId/permission" $askRequest) 'Global ASK'
    if ($askOutcome.effect -cne 'ask') { Fail "Global request resolved to '$($askOutcome.effect)' instead of ASK." }
    $pendingId = [string]$askOutcome.id
    $pending = @(PermissionRecords (Get-Json $client "$base/api/session/$sessionId/permission"))
    $matching = @($pending | Where-Object {
        $null -ne $_ -and 'id' -in @($_.PSObject.Properties.Name) -and
        $_.id -eq $pendingId -and $_.action -eq 'external_directory' -and
        $allowedPattern -in @($_.resources)
    })
    if ($matching.Count -ne 1) { Fail 'Native ASK outcome did not create the expected pending request.' }
    $null = Post-Json $client "$base/api/session/$sessionId/permission/$pendingId/reply" @{ decision='reject' }
    $remaining = @(PermissionRecords (Get-Json $client "$base/api/session/$sessionId/permission"))
    if (@($remaining | Where-Object { $null -ne $_ -and 'id' -in @($_.PSObject.Properties.Name) -and $_.id -eq $pendingId }).Count -ne 0) {
        Fail 'Rejected native permission request is still pending.'
    }
    Write-Output 'NATIVE_PERMISSION_API_ASK_OBSERVED: YES'
    Write-Output 'NATIVE_PERMISSION_API_REJECTION: PROGRAMMATIC (not user-observed)'

    # A narrower session-level DENY follows the global wildcard ASK and must
    # reject without creating another pending permission request.
    $denyJson = JsonContent @{ permissions=@(@{ action='external_directory'; resource=$forbiddenPattern; effect='deny' }) }
    $denyUpdate = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Patch, "$base/api/session/$sessionId")
    $denyUpdate.Content = $denyJson
    $updateResponse = $client.SendAsync($denyUpdate).GetAwaiter().GetResult()
    if (-not $updateResponse.IsSuccessStatusCode) { Fail 'Cannot set the isolated session-specific DENY.' }
    $denyOutcome = PermissionOutcome (Post-Json $client "$base/api/session/$sessionId/permission" @{
        agent='kovan'; action='external_directory'; resources=@($forbiddenPattern); save=@($forbiddenPattern)
    }) 'Specific DENY'
    $denyPending = @(PermissionRecords (Get-Json $client "$base/api/session/$sessionId/permission"))
    if ($denyOutcome.effect -cne 'deny' -or @($denyPending | Where-Object { $null -ne $_ -and 'resources' -in @($_.PSObject.Properties.Name) -and $forbiddenPattern -in @($_.resources) }).Count) {
        Fail 'Specific DENY was not an automatic native rejection.'
    }
    Write-Output 'NATIVE_PERMISSION_API_SPECIFIC_DENY: AUTOMATIC'
    if ($NativeToolRead) {
        $readyModel = $false
        $modelDeadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
        while ([DateTime]::UtcNow -lt $modelDeadline) {
            if ($modelJob.State -in @('Failed', 'Stopped')) { Fail 'Local model fixture exited before the read.' }
            try {
                $reply = $client.GetAsync("http://127.0.0.1:$modelPort/health").GetAwaiter().GetResult()
                if ($reply.IsSuccessStatusCode) { $readyModel = $true; break }
            } catch [Net.Http.HttpRequestException] { }
            Start-Sleep -Milliseconds 200
        }
        if (-not $readyModel) { Fail 'The isolated fake-model server did not become ready.' }
        # Select the fake provider explicitly: Kovan's normal model must not
        # call a network service or consume any configured API credentials.
        $null = Post-Json $client "$base/api/session/$sessionId/model" @{
            model=@{ providerID='oa121local'; id='reader' }
        }
        $null = Post-Json $client "$base/api/session/$sessionId/agent" @{ agent='kovan' }
        $null = Post-Json $client "$base/api/session/$sessionId/prompt" @{
            text='Read the specified synthetic file using the native read tool only.'
        }
        $readObserved = $false
        $deniedRead = $false
        $readDeadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
        while ([DateTime]::UtcNow -lt $readDeadline) {
            $messages = @(PermissionRecords (Get-Json $client "$base/api/session/$sessionId/message"))
            $encoded = $messages | ConvertTo-Json -Depth 40 -Compress
            if ($encoded.Contains($sentinel)) { Fail 'The forbidden synthetic content appeared in native session output.' }
            foreach ($message in $messages) {
                $info = if ('info' -in @($message.PSObject.Properties.Name)) { $message.info } else { $message }
                if ($null -eq $info -or 'content' -notin @($info.PSObject.Properties.Name)) { continue }
                foreach ($part in @($info.content)) {
                    if ($null -eq $part -or $part.type -ne 'tool' -or $part.name -ne 'read') { continue }
                    $readObserved = $true
                    $status = [string]$part.state.status
                    if ($status -eq 'completed') { Fail 'Native read completed despite the specific DENY.' }
                    if ($status -eq 'error') {
                        $errorText = $part.state | ConvertTo-Json -Depth 15 -Compress
                        if ($errorText -match 'permission\.rejected|Permission denied: external_directory') {
                            $deniedRead = $true
                        } else {
                            # Report only the structured error category. Keep
                            # filenames and any tool content out of CI logs.
                            $errorType = @([string]$part.state.error.type, [string]$part.state.error._tag) |
                                Where-Object { $_ } | Select-Object -First 1
                            $errorKind = if ($errorType) { [string]$errorType } else { 'unspecified' }
                            $errorKeys = @($part.state.error.PSObject.Properties.Name) -join ','
                            $details = ([string]$part.state.error.message).Replace($run, '[isolated-root]').Replace($sentinel, '[redacted]')
                            if ($details.Length -gt 240) { $details = $details.Substring(0, 240) }
                            Fail "Native read was not confirmed denied (error kind=$errorKind; keys=$errorKeys; detail=$details)."
                        }
                    }
                }
            }
            if ($deniedRead) { break }
            Start-Sleep -Milliseconds 200
        }
        if (-not $readObserved -or -not $deniedRead) { Fail 'No rejected native read tool call was recorded.' }
        Write-Output 'NATIVE_TOOL_READ_ATTEMPTED: YES (real V2 read; deterministic local model)'
        Write-Output 'NATIVE_TOOL_READ_DENIED: YES (specific external_directory DENY)'
        Write-Output 'NATIVE_FILE_CONTENT_EXPOSURE: NO'
        Write-Output 'OA121_NATIVE_READ_E2E: PASS (mock provider; no human prompt)'
    } else {
        Write-Output 'NATIVE_TOOL_READ_ATTEMPTED: NO'
        Write-Output 'NATIVE_FILE_CONTENT_EXPOSURE: NOT_TESTED'
        Write-Output 'OA121_NATIVE_PERMISSION_API: PASS (engine-only; no model or GUI)'
    }
    $completed = $true
} finally {
    if ($null -ne $client) { $client.Dispose() }
    if ($null -ne $modelJob) {
        if ($modelJob.State -eq 'Running') {
            $shutdown = $null
            try {
                $shutdown = [Net.Http.HttpClient]::new()
                $shutdown.Timeout = [TimeSpan]::FromSeconds(2)
                $null = $shutdown.GetAsync("http://127.0.0.1:$modelPort/shutdown").GetAwaiter().GetResult()
            } catch { } finally {
                if ($null -ne $shutdown) { $shutdown.Dispose() }
            }
            $null = Wait-Job -Job $modelJob -Timeout 3
            if ($modelJob.State -eq 'Running') { Stop-Job -Job $modelJob -ErrorAction SilentlyContinue }
        }
        Remove-Job -Job $modelJob -Force -ErrorAction SilentlyContinue
    }
    if ($null -ne $serverProcess) {
        if (-not $serverProcess.HasExited) {
            # The launched PowerShell hosts a child opencode.exe. Stopping only
            # its shell leaves that child holding the temporary Git directory.
            # Terminate this invocation's exact process tree, never a broad name.
            $null = & taskkill.exe /PID $serverProcess.Id /T /F 2>&1
            if ($LASTEXITCODE -ne 0 -and -not $serverProcess.HasExited) {
                Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
            }
        }
        $null = $serverProcess.WaitForExit(5000)
        $serverProcess.Dispose()
    }
    foreach ($name in $envNames) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    # Delete only this invocation's GUID-named fixture after success. Failed
    # fixtures remain available for debugging and are never promoted to global.
    if ($completed -and (Test-Path -LiteralPath $run)) {
        # Windows can release child process handles shortly after taskkill
        # returns. Retry only this known GUID fixture for a bounded interval.
        for ($attempt = 0; $attempt -lt 10; $attempt++) {
            try {
                Remove-Item -LiteralPath $run -Recurse -Force -ErrorAction Stop
                break
            } catch [IO.IOException] {
                Start-Sleep -Milliseconds 300
            } catch [UnauthorizedAccessException] {
                Start-Sleep -Milliseconds 300
            }
        }
        if (Test-Path -LiteralPath $run) { Fail 'Native test passed, but temporary fixture cleanup remains locked.' }
    }
}
