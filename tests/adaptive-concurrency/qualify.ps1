[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$kael = [IO.File]::ReadAllText((Join-Path $root 'olympus/harnesses/opencode/agent-prompts/kael.md'))
$routing = [IO.File]::ReadAllText((Join-Path $root 'olympus/policies/routing.md'))
$orchestration = [IO.File]::ReadAllText((Join-Path $root 'olympus/policies/orchestration.toml'))
$readme = [IO.File]::ReadAllText((Join-Path $root 'README.md'))
$workflows = [IO.File]::ReadAllText((Join-Path $root 'docs/WORKFLOWS.md'))
$ultra = [IO.File]::ReadAllText((Join-Path $root 'olympus/harnesses/opencode/commands/olympus.ultra.md'))
$performance = [IO.File]::ReadAllText((Join-Path $root 'olympus/harnesses/opencode/commands/olympus.performance.md'))
$performanceUltra = [IO.File]::ReadAllText((Join-Path $root 'olympus/harnesses/opencode/commands/olympus.performance-ultra.md'))
$hud = [IO.File]::ReadAllText((Join-Path $root '.opencode/plugins/olympus-activity/tui.tsx'))
$activity = [IO.File]::ReadAllText((Join-Path $root '.opencode/plugins/olympus-activity/activity.ts'))
function Check([string]$Id, [bool]$Ok) {
    if (-not $Ok) { throw "$Id FAIL" }
    Write-Output "$Id PASS"
}
try {
    Check AC1 ($orchestration -match '(?m)^max_children = 4$' -and
        $kael.Contains('MAX_ACTIVE_CHILDREN = {{max_children}}'))
    Check AC2 ($kael -match 'never a target' -and $kael -match 'effective ceiling may be 1–8 per root')
    Check AC3 ($routing -match 'TARGET_ACTIVE = min\(ULTRA_CEILING, READY_WORKSTREAMS\)' -and
        $kael -match 'TARGET_ACTIVE = min\(ULTRA_CEILING, READY_WORKSTREAMS\)' -and
        $kael -match 'Dispatch ready slots promptly and\s+refill as soon as slots become available')
    Check AC4 ($kael -match 'Exact OpenCode task commands' -and
        $kael -match '(?s)only the namespaced `/olympus\.ultra <prompt>`.*?/olympus\.performance-ultra <prompt>`' -and
        $kael -notmatch 'FAST is an explicit user-selected|fast-mode|long-mode|surgical-mode|FAST:')
    $ultraMetadata = [regex]::Match($ultra, '\A---\r?\n(?<metadata>.*?)\r?\n---[ \t]*(?:\r?\n|\z)', [Text.RegularExpressions.RegexOptions]::Singleline).Groups['metadata'].Value
    Check AC5 ($ultraMetadata -match '(?m)^subagent: false$' -and
        $ultraMetadata -notmatch '(?m)^(agent|model|template):' -and
        $ultra -match '\$ARGUMENTS' -and $ultra -match 'empty or contains only whitespace' -and
        $ultra -match 'Do not call tools or launch agents' -and
        $ultra -match 'If it is neither Kael nor Atlas')
    Check AC6 ($ultra -match 'ULTRA_CEILING' -and $ultra -match 'READY_WORKSTREAMS' -and
        $ultra -match 'TARGET_ACTIVE' -and $ultra -match 'CURRENT_ACTIVE' -and
        $ultra -match 'UNDERFILL_REASON' -and $kael -match 'PEAK_ACTIVE_CHILDREN')
    Check 'ADAPTIVE_READY_SLOT_DISPATCH' (
        $routing -match 'Dispatch ready slots promptly and refill as slots become available' -and
        $routing -match 'no one-batch or wave is required' -and
        $kael -match 'Dispatch ready slots promptly and\s+refill as soon as slots become available' -and
        $kael -match 'there is no one-batch or wave\s+obligation' -and
        $kael -match 'Never wait for a previous child before dispatching already-ready\s+independent work' -and
        $ultra -match 'keep filling available slots as work becomes ready' -and
        $ultra -match 'Do not wait for a whole wave')
    Check 'ULTRA_WRITER_OWNERSHIP_AND_RECONCILIATION' (
        $routing -match 'one mutative writer per worktree' -and
        $routing -match 'isolated worktrees and non-conflicting refs/shared resources' -and
        $kael -match 'one mutative writer per worktree' -and
        $kael -match 'disjoint file\s+paths in the same worktree are not enough' -and
        $kael -match 'consume each result' -and
        $kael -match 'reconciles its\s+original result' -and
        $ultra -match 'one-mutative-writer-per-worktree' -and
        $ultra -match 'shared-resource conflicts')
    Check AC7 ($performance -match '\$ARGUMENTS' -and
        $performance -match 'explicit optimization intent' -and
        $performance -match 'approval for any concrete unsettled direction before implementation' -and
        $performance -match 'before/after/delta/target measurements' -and
        $performance -match 'does not select `/olympus\.ultra`')
    Check 'PERFORMANCE_ULTRA_COMBINES_MODES' (
        $performanceUltra -match 'DOMAIN_MODE: PERFORMANCE' -and
        $performanceUltra -match 'EXECUTION_MODE: ULTRA' -and
        $performanceUltra -match 'explicit optimization intent' -and
        $performanceUltra -match 'approval of a concrete unsettled direction' -and
        $performanceUltra -match 'before/after/delta/target measurements plus correctness validation')
    Check AC8 ($routing -match 'one mutative writer per worktree' -and
        $routing -match 'Parallel writers require isolated worktrees and non-conflicting refs/shared resources' -and
        $routing -notmatch 'Only DISJOINT file scopes')
    Check AC9 ($kael -match '## Diagnostic Gate' -and $kael -match 'default limit is one Thales consultation' -and
        $kael -match 'materially new evidence' -and
        $ultra -match 'follow the current primary.s canonical role, authority, ownership, validation, result, and completion rules')
    Check AC10 ($activity -match 'active:\s*activeRows\.length' -and
        $activity -match 'visibleRows:\s*activeRows\.slice\(0, 4\)' -and
        $hud -match '\{activity\(\)\.active\} active · showing \{activity\(\)\.visibleRows\.length\}' -and
        $hud -match 'context\.data\.session\.status' -and $activity -match 'current\.parentID != null' -and
        $activity -match 'status\(session\.id\) === "running"' -and $hud -notmatch 'setInterval|setTimeout|spawn|schedule')
    $commandDocs = [regex]::Match($readme, '(?ms)^<a id="task-parallelism"></a>\s+^## [^\r\n]+\r?\n(?<body>.*?)(?=^## |\z)').Groups['body'].Value
    Check 'DOC' ($commandDocs -match '(?s)/olympus\.ultra <prompt>.*?prompt-level ceiling.*?/olympus\.performance <prompt>.*?/olympus\.performance-ultra <prompt>' -and
        $readme -match 'There are no bare aliases' -and
        $workflows -match 'There are no bare aliases')
    Check 'COMMAND_DOCS_STATE_PROMPT_LEVEL_ARGUMENT_GUARD' (
        $readme -match 'Empty/whitespace arguments or an unsupported primary return usage or primary guidance without tools or agents' -and
        $workflows -match 'This is a\s+prompt guard, not deterministic native argument enforcement')
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
