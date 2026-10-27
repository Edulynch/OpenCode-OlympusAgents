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
    Check AC8 ($kael -match 'Only DISJOINT file scopes' -and $kael -match 'OVERLAPPING:.*denied' -and
        $kael -match 'AMBIGUOUS:.*denied' -and
        $kael -match 'overlapping Git\s+mutations on the same repository/ref conflict')
    Check AC9 ($kael -match '## Diagnostic Gate' -and $kael -match 'default limit is one Thales consultation' -and $kael -match 'materially new evidence' -and $kael -match 'FAST never overrides.*Thales Diagnostic Gate')
    Check AC10 ($hud -match 'active\(\)\.slice\(0, 4\)' -and $hud -match 'context\.data\.session\.status' -and $activity -match 'current\.parentID != null' -and $activity -match 'status\(session\.id\) === "running"' -and $hud -notmatch 'setInterval|setTimeout|spawn|schedule')
    $modifierSection = [regex]::Match($kael, '(?ms)^### Optional task modifiers \(OpenCode only\)\r?\n(?<body>.*?)(?=^## |^### |\z)')
    $modifierBody = $modifierSection.Groups['body'].Value
    Check 'MODE_TERMINAL_MARKER_CONTRACT' ($modifierSection.Success -and
        $modifierBody -match 'exact, case-sensitive markers' -and
        $modifierBody -match 'own unquoted, unfenced,\s+unbulleted line' -and
        $modifierBody -match 'final contiguous marker block' -and
        $modifierBody -match 'last nonblank content' -and
        $modifierBody -match 'any subset and order' -and
        $modifierBody -match 'prose, citations,\s+documentation, quoted/pasted text, code, fenced examples')
    Check 'MODE_COMBINATIONS_AND_ORDERS' ($modifierBody -match 'any subset and order' -and
        $modifierBody -match 'Modifiers compose without precedence or authority changes' -and
        $modifierBody -match 'long-mode` does not imply approval' -and
        $modifierBody -match 'fast-mode` does not bypass dependencies or\s+completion' -and
        $modifierBody -match 'surgical-mode` does not omit necessary tests')
    Check 'MODE_ORDINARY_MENTIONS_DO_NOT_ACTIVATE' ($modifierBody -match 'Do not scan earlier turns or activate from prose, citations,\s+documentation, quoted/pasted text, code, fenced examples, or nonterminal mentions' -and
        $modifierBody -match 'If placement or intent is ambiguous, apply no optional modifier')
    Check 'MODE_NORMAL_FALLBACK_AND_NO_PERSISTENCE' ($modifierBody -match 'If placement or intent is ambiguous, apply no optional modifier' -and
        $modifierBody -match 'preserve the existing NORMAL behavior' -and $modifierBody -match 'never persist into another task')
    Check 'MODE_FAST_REUSES_POLICY' ($modifierBody -match '`fast-mode`\*\* selects the existing FAST profile' -and
        $modifierBody -match 'effective\s+concurrency ceiling' -and $modifierBody -match 'at most four active children' -and
        $modifierBody -match 'writer ownership' -and $modifierBody -match 'dependency ordering' -and
        $modifierBody -match 'completion gates' -and $modifierBody -match 'adds no\s+scheduler')
    $modes = [regex]::Match($readme, '(?ms)^##[^\r\n]*NORMAL vs FAST[^\r\n]*\r?\n(?<body>.*?)(?=^##\s|\z)')
    $modeDocs = $modes.Groups['body'].Value

    # Match each mode's own rendered Markdown line, whether a table row or a
    # readable paragraph. Test semantics, not one historical README phrasing.
    $normal = [regex]::Match($modeDocs, '(?im)^[ \t]*(?:\|[ \t]*)?\*{0,2}NORMAL\b[^\r\n]*')
    $fast = [regex]::Match($modeDocs, '(?im)^[ \t]*(?:\|[ \t]*)?\*{0,2}FAST\b[^\r\n]*')
    $fastChecksPreserved = $fast.Value -match '(?i)\b(?:keeps?|preserves?)\b.{0,40}\b(?:required\s+)?checks\b|\b(?:does not|never)\s+skips?\s+checks\b'
    $fastDependenciesSequential = $fast.Value -match '(?i)\b(?:does not|never)\b.{0,80}\b(?:parallelize|parallelizes|run)\b.{0,35}\bdependent\s+tasks\b'
    Check DOC ($modes.Success -and $normal.Success -and $fast.Success -and
        $normal.Value -match '(?i)\bdefault\b' -and
        $normal.Value -match '(?i)\bparallel\b' -and
        $normal.Value -match '(?i)\b(?:only|useful|fits)\b' -and
        $fast.Value -match '(?i)\bexplicit\b' -and
        $fast.Value -match '(?i)\bup\s+to\s+four\b.{0,30}\bagents\b' -and
        $fastChecksPreserved -and $fastDependenciesSequential)
    Check 'MODE_DOCS_OPEN_CODE_AND_MARKERS' ($readme -match '(?s)Optional OpenCode task modifiers.*?`long-mode`.*?`fast-mode`.*?`surgical-mode`' -and
        $readme -match 'not a parser or a runtime guarantee')
    Write-Output 'ADAPTIVE CONCURRENCY QUALIFICATION: PASS (static; interactive selection and fan-out pending)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'ADAPTIVE CONCURRENCY QUALIFICATION: FAIL'
    exit 1
}
