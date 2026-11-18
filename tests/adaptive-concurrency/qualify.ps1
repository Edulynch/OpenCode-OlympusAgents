[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$kael = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/kael.md'))
$readme = [IO.File]::ReadAllText((Join-Path $root 'README.md'))
$workflows = [IO.File]::ReadAllText((Join-Path $root 'docs/WORKFLOWS.md'))
$ultra = [IO.File]::ReadAllText((Join-Path $root '.opencode/commands/olympus.ultra.md'))
$performance = [IO.File]::ReadAllText((Join-Path $root '.opencode/commands/olympus.performance.md'))
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
    Check AC4 ($kael -match 'Exact OpenCode task commands' -and
        $kael -match 'only the namespaced `/olympus\.ultra <prompt>` and\s+`/olympus\.performance <prompt>`' -and
        $kael -notmatch 'FAST is an explicit user-selected|fast-mode|long-mode|surgical-mode|FAST:')
    Check AC5 ($ultra -match '(?s)^---\s+description:.*?agent: kael\s+subagent: false.*?---' -and
        $ultra -match '\$ARGUMENTS' -and $ultra -match 'empty or contains only whitespace' -and
        $ultra -match 'Do not call tools or launch agents')
    Check AC6 ($ultra -match 'MAX_ACTIVE_CHILDREN' -and $ultra -match 'Do not add filler' -and
        $ultra -match 'completion gates' -and $ultra -match 'zero is correct for trivial or dependent work')
    Check 'ULTRA_NATIVE_BATCH_DISPATCH' (
        $kael -match 'launch them\s+together in one native parallel tool-call batch' -and
        $kael -match 'Do not serialize ready launches across separate model turns' -and
        $ultra -match 'same native parallel tool-call batch' -and
        $ultra -match 'Do not spend a separate model turn between ready launches' -and
        $ultra -match 'do not add a scheduler or invent a wrapper')
    Check AC7 ($performance -match '\$ARGUMENTS' -and
        $performance -match 'explicit optimization request' -and
        $performance -match 'human approval before implementation' -and
        $performance -match 'before/after/delta/target measurements' -and
        $performance -match 'does not select `/olympus\.ultra`')
    Check AC8 ($kael -match 'Only DISJOINT file scopes' -and $kael -match 'OVERLAPPING:.*denied' -and
        $kael -match 'AMBIGUOUS:.*denied' -and
        $kael -match 'overlapping Git\s+mutations on the same repository/ref conflict')
    Check AC9 ($kael -match '## Diagnostic Gate' -and $kael -match 'default limit is one Thales consultation' -and
        $kael -match 'materially new evidence' -and $ultra -match 'Do not.*bypass.*gates')
    Check AC10 ($hud -match 'active\(\)\.slice\(0, 4\)' -and $hud -match 'context\.data\.session\.status' -and $activity -match 'current\.parentID != null' -and $activity -match 'status\(session\.id\) === "running"' -and $hud -notmatch 'setInterval|setTimeout|spawn|schedule')
    Check 'DOC' ($readme -match '(?s)## 🧭 Task Parallelism.*?/olympus\.ultra <prompt>.*?configured prompt ceiling.*?/olympus\.performance <prompt>' -and
        $readme -match 'no bare `/ultra` or `/performance` aliases' -and
        $workflows -match 'There are no bare `/ultra` or `/performance` aliases')
    Check 'COMMAND_DOCS_STATE_PROMPT_LEVEL_ARGUMENT_GUARD' (
        $readme -match 'Blank-argument usage is a prompt-level guard, not deterministic native argument validation' -and
        $workflows -match 'not deterministic runtime enforcement')
    Check 'RETIRED_USER_MODES' (
        $readme -notmatch 'NORMAL vs FAST|fast-mode|long-mode|surgical-mode|FAST:' -and
        $workflows -notmatch 'Optional OpenCode task modifiers|fast-mode|long-mode|surgical-mode|FAST:'
    )
    Write-Output 'ADAPTIVE CONCURRENCY QUALIFICATION: PASS (static; interactive selection and fan-out pending)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'ADAPTIVE CONCURRENCY QUALIFICATION: FAIL'
    exit 1
}
