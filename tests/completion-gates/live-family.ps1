# Historical launcher: manual integration test only; never invoke its default
# launch mode from an Olympus agent session. SchemaSmoke/InspectSession are
# read-only v2.0.18 infrastructure modes and launch no agent scenario.
# Original OpenCode v2.0.15: session.list supports search (exact title verified locally)
# and parentID (native direct-child filter); root sessions omit parentID entirely.
# List/get/message objects have different optional properties. CLI JSON events
# and session.get provide independent ID evidence, but not family completion.
# The root CLI returning, an assistant message, or absence from /active alone
# NEVER proves that the whole family has completed. No DB access is used.
[CmdletBinding()]
param(
    [string]$Fixture = 'C:\Users\eduma\AppData\Local\Temp\opencode\olympus-live-completion-fixture-1b63b53aaa96',
    [ValidateRange(60,7200)][int]$TimeoutSeconds = 1200,
    [ValidateRange(2,120)][int]$PollSeconds = 8,
    [switch]$SmallProbe,
    [switch]$ParserTests,
    [switch]$SchemaSmoke,
    [string]$SmokeSession,
    [string]$InspectSession,
    [ValidateSet('A','B')][string]$InspectCase = 'A'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$t0 = [DateTimeOffset]::UtcNow
$deadline = $t0.AddSeconds($TimeoutSeconds)
$jobs = @()
$issues = [Collections.Generic.List[string]]::new()
$roots = @()
$schemaError = $false

function Has($obj, [string]$name) {
    return ($null -ne $obj -and $null -ne $obj.PSObject.Properties[$name])
}
function Optional($obj, [string]$name) {
    if (Has $obj $name) { return $obj.PSObject.Properties[$name].Value }
    return $null
}
function Schema([string]$reason) { throw "HARNESS_SCHEMA_ERROR: $reason" }
function Require-ID($obj, [string]$where) {
    $id = Optional $obj 'id'
    if ($id -isnot [string] -or $id -notmatch '^ses_') { Schema "$where has no session id; properties: $(if ($null -ne $obj) { @($obj.PSObject.Properties.Name) -join ',' } else { '<null>' })" }
    return $id
}

function Api([string]$path, [string[]]$parameters = @()) {
    # For method/path requests v2.0.15 ignores --param query arguments.
    # Put query parameters in the URL so pagination and parentID really apply.
    if ($parameters.Count) {
        $query = @($parameters | ForEach-Object {
            $pair = $_.Split('=', 2)
            if ($pair.Count -ne 2) { throw "Invalid API query parameter: $_" }
            [uri]::EscapeDataString($pair[0]) + '=' + [uri]::EscapeDataString($pair[1])
        }) -join '&'
        $path += "?$query"
    }
    $raw = & opencode api GET $path 2>&1
    if ($LASTEXITCODE -ne 0) { throw "OpenCode API $path failed: $($raw -join ' ')" }
    $reply = ($raw -join "`n") | ConvertFrom-Json
    if (-not (Has $reply 'data') -or $null -eq $reply.data) { Schema "No data in $path" }
    return $reply
}
function Listed([string[]]$parameters) {
    $found = @(); $cursor = $null
    for ($page = 0; $page -lt 50; $page++) {
        $p = @($parameters)
        if (-not @($p | Where-Object { $_ -like 'limit=*' }).Count) { $p += 'limit=100' }
        if ($cursor) { $p += "cursor=$cursor" }
        $reply = Api '/api/session' $p
        if ($reply.data -isnot [array]) { Schema "session.list data is not an array: $($reply.data.GetType().FullName)" }
        $parentFilter = @($parameters | Where-Object { $_ -like 'parentID=*' })
        foreach ($item in $reply.data) {
            $null = Require-ID $item 'session.list item'
            if ($parentFilter.Count -eq 1 -and (Optional $item 'parentID') -cne $parentFilter[0].Substring(9)) {
                Schema 'Session list did not respect parentID filter (or child has no parentID)'
            }
        }
        $found += @($reply.data)
        $next = $null
        $next = Optional (Optional $reply 'cursor') 'next'
        if (-not $next) { return $found }
        if ($next -eq $cursor) { throw 'Session list cursor did not advance' }
        $cursor = $next
    }
    throw 'Session list exceeded 50 pages; family membership unconfirmed'
}
function Session([string]$id) {
    $item = (Api "/api/session/$id").data
    if ($item -isnot [pscustomobject]) { Schema "session.get data is not an object for $id" }
    if ((Require-ID $item 'session.get') -cne $id) { Schema "session.get identity mismatch for $id" }
    return $item
}
function Messages([string]$id) {
    $items = (Api "/api/session/$id/message").data
    if ($items -isnot [array]) { Schema "session.message.list data is not an array for $id" }
    return @($items)
}
function Inbox([string]$id) {
    $items = (Api "/api/session/$id/inbox").data
    if ($items -isnot [array]) { Schema "session.inbox.list data is not an array for $id" }
    return @($items)
}
function TextOf($message) {
    return ((@(Optional $message 'content') | Where-Object { (Optional $_ 'type') -eq 'text' } | ForEach-Object { Optional $_ 'text' }) -join "`n").Trim()
}
function Mark([long]$ms) { if ($ms -gt 0) { return [DateTimeOffset]::FromUnixTimeMilliseconds($ms).ToString('o') }; return '-' }
function Parse-Result([string]$text, [string]$expected) {
    # Count every marker-like line, including malformed values, before accepting one.
    # Only the actual child's assistant text is passed here, never the root synthesis.
    $lines = [regex]::Matches($text, '(?m)^[ \t]*OLYMPUS_RESULT\b[^\r\n]*')
    $valid = [regex]::Matches($text, '(?m)^OLYMPUS_RESULT:[ \t]*(RESULT-\d{2})[ \t]*\r?$')
    $value = if ($lines.Count -eq 1 -and $valid.Count -eq 1) { $valid[0].Groups[1].Value } else { '' }
    $reason = if ($lines.Count -ne 1) { "marker count $($lines.Count), expected 1" }
              elseif ($valid.Count -ne 1) { 'malformed marker' }
              elseif ($value -cne $expected) { "wrong value $value, expected $expected" }
              else { '' }
    return [pscustomobject]@{ Count=$lines.Count; Value=$value; Valid=($reason -eq ''); Reason=$reason }
}

if ($ParserTests) {
    $cases = @(
        @{ Name='A prose plus marker'; Text="I found it.`nOLYMPUS_RESULT: RESULT-01"; Pass=$true },
        @{ Name='B missing marker'; Text='RESULT-01'; Pass=$false },
        @{ Name='C wrong unit'; Text='OLYMPUS_RESULT: RESULT-02'; Pass=$false },
        @{ Name='D duplicate marker'; Text="OLYMPUS_RESULT: RESULT-01`nOLYMPUS_RESULT: RESULT-01"; Pass=$false },
        @{ Name='E malformed marker'; Text='OLYMPUS_RESULT: RESULT-01 and RESULT-02'; Pass=$false },
        @{ Name='F prose only'; Text='Some prose mentioning RESULT-01 but no marker'; Pass=$false }
    )
    $errors = 0
    foreach ($case in $cases) {
        $result = Parse-Result $case.Text 'RESULT-01'
        $ok = $result.Valid -eq $case.Pass
        if (-not $ok) { $errors++ }
        Write-Host "$($case.Name): $(if ($ok) { 'PASS' } else { 'FAIL' }) marker count=$($result.Count) parsed=$($result.Value) reason=$($result.Reason)"
    }
    Write-Host "PARSER TEST ERRORS: $errors"
    if ($errors) { exit 1 }
    exit 0
}

# Read-only infrastructure check; never launches an agent or a root. Reuses the
# native observer parser and API calls rather than certifying from CLI exit/idle.
if ($SchemaSmoke) {
    try {
        $version = (& opencode --version | Out-String).Trim()
        if ($LASTEXITCODE -ne 0 -or $version -notmatch '^opencode v2\.0\.18$') { Schema "Version not inspected: $version" }
        $active = (Api '/api/session/active').data
        if ($active -isnot [pscustomobject]) { Schema 'session.active is not an object' }
        $none = @(Listed @('search=olympus-phase3-schema-smoke-unlikely-49391'))
        if ($none.Count) { Schema 'Exact search unexpectedly matched' }
        $parents = @(Listed @('parentID=ses_nonexistent_phase3_smoke'))
        if ($parents.Count) { Schema 'Nonexistent parentID returned children' }
        if (-not $SmokeSession -or $SmokeSession -notmatch '^ses_') { Schema 'Provide -SmokeSession for an existing root session' }
        $id = $SmokeSession
        $root = Session $id
        if (Optional $root 'parentID') { Schema 'Smoke root unexpectedly has parentID' }
        $messages = @(Messages $id)
        $inbox = @(Inbox $id)
        if (-not (Has $root 'time') -or -not (Has $root 'outcome') -or
            -not ($messages | Where-Object { (Optional $_ 'type') -eq 'assistant' })) {
            Schema 'Root/outcome/message observation fields missing'
        }
        $search = @(Listed @("search=$(Optional $root 'title')", 'limit=2'))
        if (-not ($search | Where-Object { (Optional $_ 'id') -eq $id })) { Schema 'Search did not find exact root' }
        $direct = @(Listed @("parentID=$id", 'limit=2'))
        # Listed checks every parentID and walks cursor.next up to 50 pages.
        $terminalObserved = $false; $continuationObserved = $false
        foreach ($child in $direct) {
            $info = Session (Require-ID $child 'smoke child')
            if ((Optional $info 'parentID') -cne $id) { Schema 'Child get parentID mismatch' }
            $childMessages = @(Messages $child.id)
            $null = @(Inbox $child.id)
            if ((Optional $info 'outcome') -eq 'succeeded' -and (Optional (Optional $info 'time') 'idle') -and
                @($childMessages | Where-Object { (Optional $_ 'type') -eq 'assistant' -and (TextOf $_) }).Count) {
                $terminalObserved = $true
            }
            if (@($childMessages | Where-Object { (Optional $_ 'type') -eq 'assistant' -and (TextOf $_) }).Count -ge 2) {
                $continuationObserved = $true
            }
        }
        $continuations = @($messages | Where-Object { (Optional $_ 'type') -eq 'assistant' -and (TextOf $_) }).Count
        if (-not $terminalObserved -or -not $continuationObserved -or $continuations -lt 2 -or
            (Optional $root 'outcome') -ne 'succeeded' -or -not (Optional (Optional $root 'time') 'idle')) {
            Schema 'Historical terminal/root-response/same-session-continuation fields not observable'
        }
        Write-Host "SCHEMA SMOKE PASS: $version root=$id rootMessages=$($messages.Count) assistantResponses=$continuations directChildren=$($direct.Count) inbox=$($inbox.Count) terminalChild=$terminalObserved continuedChild=$continuationObserved search=$($search.Count) activeKeys=$(@($active.PSObject.Properties).Count)"
        Write-Host 'No live Phase 3 scenarios executed; historical messages validate only observer shape, not new policy behavior.'
        $wait = & opencode api experimental.session.wait --param "sessionID=$($direct | Where-Object { (Optional (Session $_.id) 'outcome') -eq 'succeeded' } | Select-Object -First 1 -ExpandProperty id)" 2>&1
        if ($LASTEXITCODE -ne 0) { Schema "experimental.session.wait unavailable: $($wait -join ' ')" }
        Write-Host 'Completed child experimental.session.wait PASS (wait/idle is not a completion signal).'
        exit 0
    } catch { Write-Host "SCHEMA SMOKE FAIL: $($_.Exception.Message)"; exit 1 }
}

# Inspection mode for user-run Phase 3 roots. This does not launch agents. A
# returning CLI, first root reply, or idle child never establishes completion.
if ($InspectSession) {
    try {
        if ($InspectSession -notmatch '^ses_') { Schema 'Provide an exact root session ID' }
        $root = Session $InspectSession
        if ((Optional $root 'parentID') -or (Optional $root 'agent') -ne 'kael') { Schema 'Not a Kael root' }
        $seen = @{}; $complete = $false
        do {
            $root = Session $InspectSession
            $active = (Api '/api/session/active').data
            if ($active -isnot [pscustomobject]) { Schema 'session.active is not an object' }
            $direct = @(Listed @("parentID=$InspectSession"))
            $all = @{}; $queue = [Collections.Generic.Queue[object]]::new()
            foreach ($child in $direct) { $queue.Enqueue($child) }
            while ($queue.Count) {
                $child = $queue.Dequeue()
                if ($all.ContainsKey($child.id)) { continue }
                $all[$child.id] = $child
                foreach ($nested in @(Listed @("parentID=$($child.id)"))) { $queue.Enqueue($nested) }
            }
            $pending = 0; $unknown = 0; $terminal = @{}
            foreach ($child in $all.Values) {
                $id = Require-ID $child 'Phase 3 child'
                $info = Session $id; $cm = @(Messages $id); $inbox = @(Inbox $id)
                if ((Optional $info 'parentID') -ne $InspectSession) { Schema "Nested/invalid parent: $id" }
                $texts = @($cm | Where-Object { (Optional $_ 'type') -eq 'assistant' -and (TextOf $_) })
                if (Has $active $id) { $pending++; continue }
                $wait = & opencode api experimental.session.wait --param "sessionID=$id" 2>&1
                if ($LASTEXITCODE -ne 0) { Schema "wait failed for $id : $($wait -join ' ')" }
                if (-not (Optional $info 'outcome') -or -not (Optional (Optional $info 'time') 'idle') -or
                    -not $texts.Count -or $inbox.Count) { $unknown++; continue }
                $terminal[$id] = [pscustomobject]@{ Info=$info; Messages=$cm; Texts=$texts; Final=TextOf $texts[-1] }
                $seen[$id] = $terminal[$id]
            }
            $rootInbox = @(Inbox $InspectSession); $rm = @(Messages $InspectSession)
            $responses = @($rm | Where-Object { (Optional $_ 'type') -eq 'assistant' -and (TextOf $_) })
            $complete = $pending -eq 0 -and $unknown -eq 0 -and $rootInbox.Count -eq 0 -and
                $terminal.Count -eq $all.Count -and $responses.Count -gt 0 -and
                (Optional $root 'outcome') -eq 'succeeded' -and (Optional (Optional $root 'time') 'idle') -and
                -not (Has $active $InspectSession)
            if ($complete) {
                $last = [long](Optional (Optional $responses[-1] 'time') 'completed')
                foreach ($entry in $terminal.GetEnumerator()) {
                    if ($last -lt [long](Optional (Optional $entry.Value.Info 'time') 'idle')) { $complete = $false }
                }
                if ($complete) {
                    $again = @(Listed @("parentID=$InspectSession"))
                    if ($again.Count -ne $direct.Count -or @($again | Where-Object { -not $terminal.ContainsKey($_.id) }).Count) { $complete = $false }
                    foreach ($child in $again) { if (@(Listed @("parentID=$($child.id)")).Count) { $complete = $false } }
                }
            }
            if ($complete -or [DateTimeOffset]::UtcNow -ge $deadline) { break }
            Start-Sleep -Seconds $PollSeconds
        } while ($true)
        $sorin = @($terminal.GetEnumerator() | Where-Object { (Optional $_.Value.Info 'agent') -eq 'sorin' })
        $workers = @($terminal.GetEnumerator() | Where-Object { (Optional $_.Value.Info 'agent') -in @('veyra','orin','nox','vera','kovan') })
        $lastRoot = if ($responses.Count) { TextOf $responses[-1] } else { '' }
        $ok = $complete -and $all.Count -eq $terminal.Count -and $lastRoot
        if ($InspectCase -eq 'A') {
            $ok = $ok -and $sorin.Count -eq 1 -and $workers.Count -eq 1 -and
                $sorin[0].Value.Texts.Count -ge 2 -and $sorin[0].Value.Final -match 'STATUS:\s*ADVICE' -and
                @($sorin[0].Value.Texts | Where-Object { (TextOf $_) -match 'STATUS:\s*EVIDENCE_REQUEST' }).Count -ge 1 -and
                $lastRoot.Contains($sorin[0].Key) -and $lastRoot.Contains($workers[0].Key)
        } else { $ok = $ok -and $sorin.Count -eq 0 -and $workers.Count -ge 1 }
        Write-Host "PHASE3 INSPECT case=$InspectCase root=$InspectSession complete=$complete children=$($all.Count) terminal=$($terminal.Count) pending=$pending unknown=$unknown sorinSessions=$($sorin.Count) workers=$($workers.Count) rootResponses=$($responses.Count)"
        foreach ($item in $terminal.GetEnumerator()) {
            Write-Host "CHILD=$($item.Key) AGENT=$(Optional $item.Value.Info 'agent') PARENT=$InspectSession OUTCOME=$(Optional $item.Value.Info 'outcome') RESPONSES=$($item.Value.Texts.Count)"
        }
        Write-Host 'Inspect raw session messages for actual tool chronology, request fields, consultation count, role purity, exact evidence and Kael consumption; do not infer these from session counts.'
        Write-Host "PHASE3 OBSERVER: $(if ($ok) { 'STRUCTURAL_PASS_REVIEW_REQUIRED' } else { 'FAIL_OR_UNCONFIRMED' })"
        if (-not $ok) { exit 1 }; exit 0
    } catch { Write-Host "PHASE3 OBSERVER FAIL: $($_.Exception.Message)"; exit 1 }
}

try {
    if (-not (Test-Path -LiteralPath $Fixture -PathType Container)) { throw 'Fixture missing' }
    if (-not (Test-Path -LiteralPath (Join-Path $Fixture 'opencode.jsonc') -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $Fixture '.opencode/agents/kael.md') -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $Fixture '.opencode/agents/veyra.md') -PathType Leaf)) {
        throw 'Fixture lacks required OpenCode configuration or agents'
    }
    $Fixture = [IO.Path]::GetFullPath($Fixture)
    $expectedNumbers = if ($SmallProbe) { @(1) } else { @(1..6) }
    foreach ($n in $expectedNumbers) {
        $file = Join-Path $Fixture ('validation/unit-{0:D2}.txt' -f $n)
        if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or
            (Get-Content -LiteralPath $file -TotalCount 1) -cne ('RESULT-{0:D2}' -f $n)) {
            throw "Fixture first line mismatch: $file"
        }
    }
    if (-not (Get-Command opencode -ErrorAction SilentlyContinue)) { throw 'opencode unavailable' }
    if ((& opencode --version | Out-String) -notmatch '2\.0\.15') { throw 'Requires inspected OpenCode v2.0.15 interfaces; recheck version first' }
    # A successful read is required before any roots are launched.
        $null = Api '/api/session/active'
        # Fail before launching anything if list/search/parent metadata is unparseable.
        $null = @(Listed @('search=external-family-schema-preflight-unlikely-42'))
    $nonce = [guid]::NewGuid().ToString('N')
    $specs = if ($SmallProbe) {
        @([pscustomobject]@{ Label='A'; Numbers=@(1) })
    } else {
        @([pscustomobject]@{ Label='A'; Numbers=@(1,2) },
          [pscustomobject]@{ Label='B'; Numbers=@(3,4) },
          [pscustomobject]@{ Label='C'; Numbers=@(5,6) })
    }
    foreach ($spec in $specs) {
        $label = $spec.Label; $numbers = @($spec.Numbers)
        $title = "external-family-$nonce-$label"
        $assignments = @($numbers | ForEach-Object { 'validation/unit-{0:D2}.txt' -f $_ })
        $delegations = @($assignments | ForEach-Object { "one for $_" }) -join ' and '
        $countWord = if ($SmallProbe) { 'ONE' } else { 'TWO' }
        $prompt = @"
External read-only family-completion qualification, root $label. Work ONLY in this disposable fixture.
Delegate EXACTLY $countWord independent Veyra child session(s), $delegations. Give each child a prompt naming only its assigned file and instructing it: After inspecting your assigned file, include exactly one line in your response:
OLYMPUS_RESULT: <value found in the file>
The marker MUST occupy its own separate line starting in column 1. Do not put it on the SUMMARY line or after any heading, bullet, label, indentation, or code fence; put it between paragraphs if using a report format. Do not emit more than one OLYMPUS_RESULT line. Normal prose outside this line is allowed. Each child must read ONLY its assigned file. Do not run shell, edit files, subdelegate from children, invoke Kovan or Maintenance, or discover unrelated paths.
You must collect all children and validate their exact values against the assigned files before declaring complete. Verify each child's own final response contains exactly one standalone line `OLYMPUS_RESULT: RESULT-XX` for its assigned file; a value embedded in prose or your own root synthesis is insufficient. If a child omits or malforms the marker, ask that SAME child for a corrected final response with one standalone marker before you declare completion. An early root response must be labeled IN PROGRESS and must NOT claim completion. On true completion your final response must say FAMILY COMPLETE and include all exact child session IDs and their exact RESULT-XX values. If a child fails or is unknown, report that explicitly; do NOT claim FAMILY COMPLETE.
"@
        # Jobs run independent CLI processes; this is EXTERNAL controller parallelism,
        # not Maintenance routing or Kael's internal MAX_ACTIVE_CHILDREN.
        $launched = [DateTimeOffset]::UtcNow
        $job = Start-Job -ScriptBlock {
            param($dir,$title,$prompt)
            Set-Location -LiteralPath $dir
            & opencode run --agent kael --title $title --format json $prompt 2>&1
            if ($LASTEXITCODE -ne 0) { throw "opencode run exit $LASTEXITCODE for $title" }
        } -ArgumentList $Fixture,$title,$prompt
        $jobs += $job
        $roots += [pscustomobject]@{Label=$label; Title=$title; Numbers=$numbers; Job=$job; Launched=$launched; ID=''; ResponseAt=0L; Response=''; CompleteAt=0L; Children=@{}; Seen=@{}; Problem=''; Running=0; Unknown=1; ErrorRepeats=0; ErrorKey='' }
        Write-Host "T1 ROOT $label launched $($launched.ToString('o')); job=$($job.Id); title=$title (session ID pending discovery)"
    }

    do {
        foreach ($root in $roots) {
            try {
                $root.Unknown = $(if ($root.ID) { $root.Numbers.Count - [math]::Min($root.Numbers.Count,$root.Children.Count) } else { 1 })
                if (-not $root.ID) {
                    # JSON CLI events report sessionID as soon as a step begins.
                    # Use that direct identity first; native search is the fallback
                    # if the job has not yet delivered any JSON event to the parent.
                    $eventIDs = @((Receive-Job -Job $root.Job -Keep -ErrorAction SilentlyContinue | ForEach-Object {
                        if ($_ -is [string] -and $_ -like '{*') {
                            try {
                                $event = $_ | ConvertFrom-Json
                                if (Has $event 'sessionID') { $event.sessionID }
                            } catch { } # Non-JSON diagnostic output is not a session record.
                        }
                    }) | Select-Object -Unique)
                    if ($eventIDs.Count -gt 1) { Schema "CLI job emitted multiple root session IDs for $($root.Title)" }
                    $candidates = if ($eventIDs.Count) { @(Session $eventIDs[0]) } else {
                        @(Listed @("search=$($root.Title)") | ForEach-Object { Session (Require-ID $_ 'search result') })
                    }
                    $matches = @($candidates | ForEach-Object {
                        $candidate = $_
                        if ((Optional $candidate 'title') -ceq $root.Title -and
                            -not (Optional $candidate 'parentID') -and
                            (Optional $candidate 'agent') -eq 'kael' -and
                            (Optional (Optional $candidate 'location') 'directory') -ieq $Fixture) { $candidate }
                    })
                    if ($eventIDs.Count -and $matches.Count -ne 1) { Schema "CLI root ID metadata mismatch for $($root.Title)" }
                    if ($matches.Count -gt 1) { Schema "Duplicate exact title $($root.Title)" }
                    if (-not $matches.Count -and $root.Job.State -eq 'Completed') {
                        Schema "CLI finished without a discoverable root session for $($root.Title)"
                    }
                    if ($matches.Count -eq 1) {
                        $root.ID = $matches[0].id
                        Write-Host "ROOT $($root.Label) SESSION $($root.ID) START $($root.Launched.ToString('o'))"
                    }
                }
                if (-not $root.ID) { continue }
                $session = Session $root.ID
                if ((Optional $session 'parentID') -or (Optional $session 'agent') -ne 'kael' -or
                    (Optional (Optional $session 'location') 'directory') -ine $Fixture) {
                    throw "Root metadata mismatch $($root.ID)"
                }
                $rootMessages = @(Messages $root.ID)
                $responses = @($rootMessages | Where-Object {
                    (Optional $_ 'type') -eq 'assistant' -and (Optional $_ 'agent') -eq 'kael' -and
                    (Optional (Optional $_ 'time') 'completed') -and (TextOf $_)
                } | Sort-Object { Optional (Optional $_ 'time') 'completed' })
                if ($responses.Count) {
                    if (-not $root.ResponseAt) {
                        $root.ResponseAt = [long](Optional (Optional $responses[0] 'time') 'completed')
                        Write-Host "T2 ROOT $($root.Label) response available $(Mark $root.ResponseAt) (NOT family complete)"
                    }
                    $root.Response = TextOf $responses[-1]
                }
                $direct = @(Listed @("parentID=$($root.ID)"))
                $all = @{}
                $queue = [Collections.Generic.Queue[object]]::new()
                foreach ($child in $direct) { $queue.Enqueue($child) }
                while ($queue.Count -gt 0) {
                    $child = $queue.Dequeue()
                    if ($all.ContainsKey($child.id)) { continue }
                    $all[$child.id] = $child
                    foreach ($nested in @(Listed @("parentID=$($child.id)"))) { $queue.Enqueue($nested) }
                }
                $root.Children = $all
                if ($direct.Count -gt $root.Numbers.Count -or $all.Count -gt $root.Numbers.Count) { $root.Problem = 'More than assigned children or nested delegation' }
                $active = (Api '/api/session/active').data
                if ($active -isnot [pscustomobject]) { Schema 'session.active data is not an object' }
                $root.Running = 0; $root.Unknown = 0
                if ($all.Count -lt $root.Numbers.Count) { $root.Unknown = $root.Numbers.Count - $all.Count }
                foreach ($child in $all.Values) {
                    if (-not $root.Seen.ContainsKey($child.id)) {
                        $root.Seen[$child.id] = [pscustomobject]@{ Discovered=[DateTimeOffset]::UtcNow; ResultAt=0L; TerminalIdle=0L; Result=''; Parsed=''; MarkerCount=0; Validated=$false; File=''; Status='UNKNOWN' }
                        Write-Host "T3 ROOT $($root.Label) CHILD $($child.id) discovered $($root.Seen[$child.id].Discovered.ToString('o'))"
                    }
                    $record = $root.Seen[$child.id]
                    $info = Session $child.id
                    if ((Optional $info 'parentID') -ne $root.ID -or (Optional $info 'agent') -ne 'veyra' -or
                        (Optional (Optional $info 'location') 'directory') -ine $Fixture) {
                        $root.Problem = "Unexpected child metadata: $($child.id)"
                    }
                    $cm = @(Messages $child.id)
                    $user = @($cm | Where-Object type -eq 'user' | Select-Object -Last 1)
                    $assigned = @($root.Numbers | Where-Object {
                        $user.Count -eq 1 -and (Optional $user[0] 'text') -match ('validation/unit-{0:D2}\.txt' -f $_)
                    })
                    if ($assigned.Count -eq 1) { $record.File = ('unit-{0:D2}.txt' -f $assigned[0]) }
                    if ($assigned.Count -gt 1) { $root.Problem = "Child assigned multiple files: $($child.id)" }
                    $texts = @($cm | Where-Object { (Optional $_ 'type') -eq 'assistant' -and (Optional $_ 'agent') -eq 'veyra' -and (Optional (Optional $_ 'time') 'completed') -and (TextOf $_) } | Sort-Object { Optional (Optional $_ 'time') 'completed' })
                    if ($texts.Count) { $record.Result = TextOf $texts[-1] }
                    $pending = @(Inbox $child.id)
                    $outcome = Optional $info 'outcome'
                    $idle = Optional (Optional $info 'time') 'idle'
                    if ($outcome -and $outcome -ne 'succeeded') {
                        $record.Status = 'FAILED'; $root.Problem = "Child failure: $($child.id): $outcome"
                    } elseif (Has $active $child.id) {
                        $record.Status = 'RUNNING'; $root.Running++
                    } elseif ($outcome -eq 'succeeded' -and $idle -and $texts.Count -and $pending.Count -eq 0) {
                        $record.Status = 'TERMINAL'
                        if (-not $record.ResultAt) {
                            $record.ResultAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
                            $record.TerminalIdle = [long]$idle
                            Write-Host "T4 CHILD $($child.id) terminal/result observed $(Mark $record.ResultAt): $($record.Result)"
                        }
                    } else { $record.Status = 'UNKNOWN'; $root.Unknown++ }
                }
                if ($all.Count -eq $root.Numbers.Count -and -not $root.Problem) {
                    $files = @($root.Seen.Values | ForEach-Object File)
                    if (@($files | Select-Object -Unique).Count -ne $root.Numbers.Count -or @($files | Where-Object { -not $_ }).Count) {
                        # Until user prompts are available, leave membership unknown.
                        $root.Unknown++
                    } else {
                        foreach ($record in $root.Seen.Values) {
                            $expected = 'RESULT-' + ($record.File -replace '^unit-(\d\d)\.txt$','$1')
                            if ($record.Status -eq 'TERMINAL') {
                                $parsed = Parse-Result $record.Result $expected
                                $record.Parsed = $parsed.Value
                                $record.MarkerCount = $parsed.Count
                                $record.Validated = $parsed.Valid
                                if (-not $parsed.Valid) {
                                    $root.Problem = "Invalid child result for $($record.File): $($parsed.Reason)"
                                }
                            }
                        }
                    }
                }
                $rootInbox = @(Inbox $root.ID)
                $collected = @($root.Seen.Values | Where-Object Status -eq 'TERMINAL')
                $consumed = $root.Response -match 'FAMILY COMPLETE' -and $root.Response -notmatch 'IN PROGRESS'
                foreach ($record in $root.Seen.GetEnumerator()) {
                    if (-not $root.Response.Contains($record.Key) -or -not $record.Value.Validated -or
                        -not $root.Response.Contains($record.Value.Parsed)) { $consumed = $false }
                }
                if ($all.Count -eq $root.Numbers.Count -and $collected.Count -eq $root.Numbers.Count -and -not $root.Unknown -and
                     -not $root.Problem -and $rootInbox.Count -eq 0 -and (Optional $session 'outcome') -eq 'succeeded' -and
                     (Optional (Optional $session 'time') 'idle') -and -not (Has $active $root.ID) -and $consumed -and
                     $responses.Count -and [long](Optional (Optional $responses[-1] 'time') 'completed') -ge [long](@($root.Seen.Values | ForEach-Object TerminalIdle | Measure-Object -Maximum).Maximum)) {
                    # Re-enumerate after the joins; a newly spawned descendant invalidates PASS.
                    $again = @(Listed @("parentID=$($root.ID)"))
                    $nestedAgain = @($again | ForEach-Object { Listed @("parentID=$($_.id)") })
                    if ($again.Count -eq $root.Numbers.Count -and $nestedAgain.Count -eq 0 -and
                        @($again | Where-Object { -not $all.ContainsKey($_.id) }).Count -eq 0) {
                        if (-not $root.CompleteAt) {
                            $root.CompleteAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
                            Write-Host "T5 ROOT $($root.Label) FAMILY COMPLETE $(Mark $root.CompleteAt)"
                        }
                    } else { $root.CompleteAt = 0L }
                } else { $root.CompleteAt = 0L }
                $root.ErrorRepeats = 0
                $root.ErrorKey = ''
            } catch {
                $issue = "ROOT $($root.Label): $($_.Exception.Message)"
                if (-not $issues.Contains($issue)) { $issues.Add($issue) }
                $root.CompleteAt = 0L
                if ($_.Exception.Message -like '*HARNESS_SCHEMA_ERROR:*') { $schemaError = $true; break }
                if ($root.ErrorKey -ne $issue) { $root.ErrorKey = $issue; $root.ErrorRepeats = 0 }
                $root.ErrorRepeats++
                if ($root.ErrorRepeats -ge 3) {
                    $schemaError = $true
                    $issues.Add("HARNESS_SCHEMA_ERROR: repeated API/parser failure for root $($root.Label) ($($root.ErrorRepeats) polls)")
                    break
                }
            }
        }
        if ($schemaError) { break }
        if (@($roots | Where-Object { -not $_.CompleteAt -or $_.Job.State -notin @('Completed','Failed','Stopped') }).Count -eq 0) { break }
        # Terminal CLI jobs cannot deliver a further child correction. Report the
        # invalid result rather than spending the entire timeout pretending it may pass.
        if (@($roots | Where-Object { $_.Job.State -notin @('Completed','Failed','Stopped') }).Count -eq 0 -and
            @($roots | Where-Object { $_.Problem }).Count -gt 0) { break }
        if ([DateTimeOffset]::UtcNow -ge $deadline) { break }
        Start-Sleep -Seconds $PollSeconds
    } while ($true)
} catch {
    if ($_.Exception.Message -like '*HARNESS_SCHEMA_ERROR:*') { $schemaError = $true }
    $issues.Add("SETUP/LAUNCH: $($_.Exception.Message)")
}
finally {
    # Do not stop live jobs at timeout; unresolved sessions are reported explicitly.
    foreach ($root in $roots) {
        if ($root.Job.State -in @('Completed','Failed','Stopped')) {
            $null = Receive-Job -Job $root.Job -ErrorAction SilentlyContinue
            if ($root.Job.State -ne 'Completed') { $issues.Add("ROOT $($root.Label) CLI job $($root.Job.Id) failed: $($root.Job.ChildJobs[0].JobStateInfo.Reason)") }
        }
    }
}
$t6 = [DateTimeOffset]::UtcNow
$values = @($roots | ForEach-Object { $_.Seen.Values | Where-Object { $_.Status -eq 'TERMINAL' -and $_.Validated } | ForEach-Object Parsed })
$parsedValues = @($roots | ForEach-Object { $_.Seen.Values | Where-Object { $_.Status -eq 'TERMINAL' -and $_.Parsed } | ForEach-Object Parsed })
$expected = @($expectedNumbers | ForEach-Object { 'RESULT-{0:D2}' -f $_ })
$valid = @($values | Where-Object { $_ -cin $expected } | Select-Object -Unique)
$missing = @($expected | Where-Object { $_ -cnotin $valid })
$duplicates = @($parsedValues | Group-Object | Where-Object Count -gt 1 | ForEach-Object { $_.Count - 1 } | Measure-Object -Sum).Sum
if (-not $duplicates) { $duplicates = 0 }
$unexpected = @($parsedValues | Where-Object { $_ -cnotin $expected })
$unresolved = @($roots | ForEach-Object {
    if (-not $_.CompleteAt) { if ($_.ID) { $_.ID } else { "ROOT-$($_.Label):job-$($_.Job.Id):ID-UNKNOWN" } }
    if ($_.Job.State -notin @('Completed','Failed','Stopped')) { "ROOT-$($_.Label):job-$($_.Job.Id):$($_.Job.State)" }
    $_.Seen.GetEnumerator() | Where-Object { $_.Value.Status -ne 'TERMINAL' } | ForEach-Object Key
} | Select-Object -Unique)
$rows = @($roots | ForEach-Object {
    $root = $_
    $validated = @($root.Seen.Values | Where-Object {
        $record = $_
        $record.Status -eq 'TERMINAL' -and $record.Validated
    }).Count
    [pscustomobject]@{ ROOT=$root.Label; ROOT_SESSION=$root.ID; ROOT_RESPONSE=$(if ($root.ResponseAt) { 'YES' } else { 'NO' });
        EXPECTED_CHILDREN=$root.Numbers.Count; CHILDREN_DISCOVERED=$root.Children.Count; RESULTS_VALIDATED=$validated;
        RUNNING=$root.Running; UNKNOWN=$root.Unknown; FAILED=@($root.Seen.Values | Where-Object Status -eq 'FAILED').Count;
        FAMILY_COMPLETE=$(if ($root.CompleteAt) { 'YES' } else { 'UNCONFIRMED' }) }
})
$rows | Format-Table -AutoSize | Out-String -Width 240 | Write-Host
Write-Host "T0 CONTROLLER: $($t0.ToString('o'))"
foreach ($root in $roots) {
    Write-Host "ROOT $($root.Label): T1=$($root.Launched.ToString('o')) T2=$(Mark $root.ResponseAt) T5=$(Mark $root.CompleteAt) problem=$($root.Problem)"
    foreach ($entry in $root.Seen.GetEnumerator()) {
        Write-Host "  CHILD=$($entry.Key) AGENT=veyra PARENT=$($root.ID) T3=$($entry.Value.Discovered.ToString('o')) T4=$(Mark $entry.Value.ResultAt) FILE=$($entry.Value.File) STATUS=$($entry.Value.Status) MARKERS=$($entry.Value.MarkerCount) PARSED=$($entry.Value.Parsed) VALIDATED=$($entry.Value.Validated)"
    }
    if ($root.ResponseAt -and @($root.Seen.Values | Where-Object { -not $_.ResultAt -or $_.ResultAt -gt $root.ResponseAt }).Count) {
        Write-Host "ROOT $($root.Label): root response preceded at least one child's terminal result: YES"
    }
}
Write-Host "EXPECTED RESULTS: $($expected.Count)`nVALID RESULTS: $($values.Count)`nMISSING: $($missing.Count)`nDUPLICATES: $duplicates`nUNEXPECTED: $($unexpected.Count)`nSCHEMA ERRORS: $(if ($schemaError) { 1 } else { 0 })"
Write-Host "UNRESOLVED SESSIONS: $(if ($unresolved.Count) { $unresolved -join ', ' } else { 'none' })"
foreach ($issue in $issues) { Write-Host "ISSUE: $issue" }
$timedOut = $t6 -ge $deadline -and $unresolved.Count -gt 0
$failed = @($roots | Where-Object Problem).Count -gt 0 -or $duplicates -gt 0 -or $unexpected.Count -gt 0 -or
    @($issues | Where-Object { $_ -match '^(SETUP/LAUNCH:|ROOT [ABC] CLI job .*failed:)' }).Count -gt 0
$passed = $roots.Count -eq $specs.Count -and @($roots | Where-Object { $_.CompleteAt }).Count -eq $specs.Count -and
    @($rows | Where-Object { $_.EXPECTED_CHILDREN -ne $_.CHILDREN_DISCOVERED -or
        $_.RESULTS_VALIDATED -ne $_.EXPECTED_CHILDREN -or $_.RUNNING -ne 0 -or $_.UNKNOWN -ne 0 -or $_.FAILED -ne 0 -or $_.FAMILY_COMPLETE -ne 'YES' }).Count -eq 0 -and
    @($roots | Where-Object { $_.Job.State -ne 'Completed' }).Count -eq 0 -and
    $expected.Count -eq $(if ($SmallProbe) { 1 } else { 6 }) -and $values.Count -eq $expected.Count -and
    $valid.Count -eq $expected.Count -and $missing.Count -eq 0 -and $duplicates -eq 0 -and $unexpected.Count -eq 0 -and
    -not $failed -and $issues.Count -eq 0 -and
    $unresolved.Count -eq 0 -and [long]$t6.ToUnixTimeMilliseconds() -gt [long](@($roots | ForEach-Object CompleteAt | Measure-Object -Maximum).Maximum)
$status = if ($schemaError) { 'HARNESS_SCHEMA_ERROR' } elseif ($passed) { 'PASS' } elseif ($failed) { 'FAIL' } elseif ($timedOut) { 'SESSION_TIMEOUT' } else { 'PARTIAL' }
Write-Host "T6 CONTROLLER FINAL: $($t6.ToString('o'))`nFINAL STATUS: $status"
if (-not $passed) { exit 1 }
