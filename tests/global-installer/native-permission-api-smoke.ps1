[CmdletBinding()]
param(
    [string]$SourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..')),
    [int]$TimeoutSeconds = 45
)

# This optional native API smoke has no model calls or human approval prompts.
# It validates V2's permission request/rejection machinery, not a tool read.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$run = Join-Path ([IO.Path]::GetFullPath([IO.Path]::GetTempPath())) ('opencode/oa121-native-api-' + [guid]::NewGuid().ToString('N'))
$configRoot = Join-Path $run 'config'
$appRoot = Join-Path $run 'app'
$allowedRoot = Join-Path $run 'allowed'
$forbiddenRoot = Join-Path $run 'forbidden'
$envNames = @('OPENCODE_CONFIG_DIR', 'OPENCODE_CONFIG_CONTENT', 'OPENCODE_CONFIG',
    'OPENCODE_SERVER_PASSWORD', 'OPENCODE_SERVER_USERNAME',
    'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME')
$previous = @{}
$serverProcess = $null
$client = $null
$askTask = $null
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

    # Keep the tested global config and all ordinary XDG state in unique roots.
    $env:OPENCODE_CONFIG_DIR = $configRoot
    Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
    Remove-Item Env:OPENCODE_CONFIG -ErrorAction SilentlyContinue
    $env:XDG_CONFIG_HOME = Join-Path $run 'xdg-config'
    $env:XDG_DATA_HOME = Join-Path $run 'xdg-data'
    $env:XDG_CACHE_HOME = Join-Path $run 'xdg-cache'
    $env:XDG_STATE_HOME = Join-Path $run 'xdg-state'
    $env:OPENCODE_SERVER_USERNAME = 'opencode'
    $password = [guid]::NewGuid().ToString('N')
    $env:OPENCODE_SERVER_PASSWORD = $password

    # A global-only Olympus install is the subject of this test. No project
    # Olympus assets or user-global settings are installed or mutated.
    $installer = Join-Path $SourceRoot 'scripts/global-install.ps1'
    $installText = (& pwsh -NoProfile -File $installer -Harness opencode -SourceVersion local -ProjectTarget $appRoot 2>&1 | Out-String)
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
    $askRequest = @{ action='external_directory'; resources=@($allowedPattern); save=@($allowedPattern) }
    # A native ASK leaves an outstanding request; the script itself sends the
    # explicit reject and never asks a human to inspect an ambiguous dialog.
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $askTask = $client.PostAsync("$base/api/session/$sessionId/permission", (JsonContent $askRequest))
    $pendingId = ''
    while ([DateTime]::UtcNow -lt $deadline -and -not $pendingId) {
        $pending = @(PermissionRecords (Get-Json $client "$base/api/session/$sessionId/permission"))
        foreach ($request in $pending) {
            if ($null -eq $request -or 'action' -notin @($request.PSObject.Properties.Name)) { continue }
            if ($request.action -eq 'external_directory' -and $allowedPattern -in @($request.resources)) {
                $pendingId = [string]$request.id
                break
            }
        }
        if (-not $pendingId -and $askTask.IsCompleted) { Fail 'Permission request completed without an observable native ASK.' }
        if (-not $pendingId) { Start-Sleep -Milliseconds 150 }
    }
    if (-not $pendingId) { Fail 'Timed out without observing the native ASK request.' }
    $reject = Post-Json $client "$base/api/session/$sessionId/permission/$pendingId/reply" @{ decision='reject' }
    if (-not $askTask.Wait([TimeSpan]::FromSeconds(5))) { Fail 'The rejected permission call did not finish.' }
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
    $denyResponse = $client.PostAsync("$base/api/session/$sessionId/permission", (JsonContent @{
        action='external_directory'; resources=@($forbiddenPattern); save=@($forbiddenPattern)
    })).GetAwaiter().GetResult()
    $denyPending = @(PermissionRecords (Get-Json $client "$base/api/session/$sessionId/permission"))
    if ($denyResponse.IsSuccessStatusCode -or @($denyPending | Where-Object { $null -ne $_ -and 'resources' -in @($_.PSObject.Properties.Name) -and $forbiddenPattern -in @($_.resources) }).Count) {
        Fail 'Specific DENY was not an automatic native rejection.'
    }
    Write-Output 'NATIVE_PERMISSION_API_SPECIFIC_DENY: AUTOMATIC'
    Write-Output 'NATIVE_TOOL_READ_ATTEMPTED: NO'
    Write-Output 'NATIVE_FILE_CONTENT_EXPOSURE: NOT_TESTED'
    Write-Output 'OA121_NATIVE_PERMISSION_API: PASS (engine-only; no model or GUI)'
    $completed = $true
} finally {
    if ($null -ne $client) { $client.Dispose() }
    if ($null -ne $serverProcess) {
        if (-not $serverProcess.HasExited) { Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue }
        $serverProcess.Dispose()
    }
    foreach ($name in $envNames) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    # Delete only this invocation's GUID-named fixture after success. Failed
    # fixtures remain available for debugging and are never promoted to global.
    if ($completed -and (Test-Path -LiteralPath $run)) { Remove-Item -LiteralPath $run -Recurse -Force }
}
