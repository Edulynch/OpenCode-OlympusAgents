[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$kael = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/kael.md'))
$readme = [IO.File]::ReadAllText((Join-Path $root 'README.md'))
$hud = [IO.File]::ReadAllText((Join-Path $root '.opencode/plugins/olympus-activity/tui.tsx'))
$activity = [IO.File]::ReadAllText((Join-Path $root '.opencode/plugins/olympus-activity/activity.ts'))
function Check([string]$Id, [bool]$Ok) {
    if (-not $Ok) { throw "$Id FAIL" }
    Write-Output "$Id PASS"
}
try {
    Check AC1 ($kael -match 'MAX_ACTIVE_CHILDREN = 4' -and $kael -notmatch 'simultaneous children to two')
    Check AC2 ($kael -match 'Four is a ceiling, never a target')
    Check AC3 ($kael -match '(?s)NORMAL.*minimum useful parallelism')
    Check AC4 ($kael -match 'explicit user-selected' -and $kael -match 'quoted\s+documents, code blocks, source files')
    Check AC5 ($kael -match 'repetitive independent items or sources' -and $kael -match 'Source sharding is valid')
    Check AC6 ($kael -match 'balanced shards: 20 items / 4 workers = 5/5/5/5; 7 / 4 = 2/2/2/1' -and $kael -match 'exactly one owner')
    Check AC7 ($kael -match 'FAST never overrides writer ownership' -and $kael -match 'bypass dependencies')
    Check AC8 ($kael -match 'Only DISJOINT writers may run concurrently' -and $kael -match 'OVERLAPPING:.*denied' -and $kael -match 'AMBIGUOUS:.*denied')
    Check AC9 ($kael -match '## Diagnostic Gate' -and $kael -match 'default limit is one Sorin consultation' -and $kael -match 'materially new evidence' -and $kael -match 'FAST never overrides.*Sorin Diagnostic Gate')
    Check AC10 ($hud -match 'active\(\)\.slice\(0, 4\)' -and $hud -match 'context\.data\.session\.status' -and $activity -match 'current\.parentID != null' -and $activity -match 'status\(session\.id\) === "running"' -and $hud -notmatch 'setInterval|setTimeout|spawn|schedule')
    $modes = [regex]::Match($readme, '(?ms)^##[^\r\n]*NORMAL vs FAST[^\r\n]*\r?\n(?<body>.*?)(?=^##\s|\z)')
    $modeDocs = $modes.Groups['body'].Value
    Check DOC ($modes.Success -and
        $modeDocs -match '(?is)\bNORMAL\b.{0,40}\bdefault\b' -and
        $modeDocs -match '(?is)\bNORMAL\b.{0,140}\bonly\b.{0,80}\bparallel\b.{0,80}\buseful\b' -and
        $modeDocs -match '(?is)\bexplicit(?:ly)?\b.{0,40}\b(?:ask|request)\b.{0,40}\bFAST\b' -and
        $modeDocs -match '(?is)\bup to\b.{0,20}\bfour\b.{0,20}\bagents\b' -and
        $modeDocs -match '(?is)\bFAST\b.{0,100}\b(?:does not|doesn''t|never)\s+skip\s+checks\b' -and
        $modeDocs -match '(?is)\b(?:does not|doesn''t|never)\b.{0,70}\bdependent\s+tasks\b.{0,30}\bparallel\b')
    Write-Output 'ADAPTIVE CONCURRENCY QUALIFICATION: PASS (static; interactive selection and fan-out pending)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'ADAPTIVE CONCURRENCY QUALIFICATION: FAIL'
    exit 1
}
