[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$kael = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/kael.md'))
$maintenance = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/maintenance.md'))
$fixture = Join-Path $PSScriptRoot 'fixtures'

function Check([string]$Id, [bool]$Condition) {
    if (-not $Condition) { throw "$Id FAIL" }
    Write-Output "$Id PASS"
}
function Section([string]$Text, [string]$Heading) {
    $match = [regex]::Match($Text, '(?ms)^## ' + [regex]::Escape($Heading) + '\s*\r?\n(.*?)(?=^## |\z)')
    if (-not $match.Success) { throw "Missing section: $Heading" }
    return $match.Groups[1].Value
}

try {
    $preflight = Section $kael 'Capability Preflight — before research'
    $discovery = Section $kael 'Task-scoped, progressive discovery'
    $admin = Section $maintenance 'Administrative fast path'
    $mission = Section $kael 'Mission and routing'
    $handoff = Section $kael 'Explicit maintenance result handoff'

    Check ORDER ($mission.IndexOf('Capability Preflight') -ge 0 -and
        $mission.IndexOf('Capability Preflight') -lt $mission.IndexOf('choose DIRECT') -and
        $kael.IndexOf('## Capability Preflight') -lt $kael.IndexOf('Use the delegation gate'))
    Check PREFLIGHT ($preflight -match 'actual outcome' -and $preflight -match 'required capabilities' -and
        $preflight -match 'known Olympus' -and $preflight -match 'is any repository discovery needed' -and
        $preflight -match 'not a research phase')
    Check NO_DELEGATION ($preflight -match 'Do not invoke Veyra' -and $preflight -match 'Orin to decide the plane' -and
        $preflight -match 'no Veyra, Orin,' -and $preflight -match 'no repository inspection')
    # Semantic regression: "Rewrite all Git history using this name/email and push it".
    # This is a policy assertion, NOT evidence of actual child/session activity.
    Check GIT_HISTORY_REDIRECT ($preflight -match 'rewrite all\s+Git history using this name/email and push it' -and
        $preflight -match 'Stop the normal path immediately' -and
        $preflight -match '/maintain <task>' -and $preflight -match 'include them in the handoff')
    # A second known normal-plane blocker must precede optional discovery.
    Check CAPABILITY_BLOCKED ($preflight -match 'external action has no\s+available authorized path' -and
        $preflight -match 'explain the blocker before optional research')
    Check BOUNDARY ($preflight -match 'Kael → Maintenance remains DENIED' -and
        $preflight -match 'only an explicit user' -and $handoff -match 'cannot invoke or delegate to maintenance' -and
        $kael -notmatch '(?m)^\s*- action: subagent\s*\r?\n\s*resource: maintenance\s*\r?\n\s*effect: allow')

    # Controlled small fixture: localized cart target, related test, unrelated auth module.
    Check FIXTURE ((Test-Path (Join-Path $fixture 'src/cart.ts')) -and
        ([IO.File]::ReadAllText((Join-Path $fixture 'src/cart.ts')) -match 'function calculateTotal') -and
        ([IO.File]::ReadAllText((Join-Path $fixture 'tests/cart.test.ts')) -match 'calculateTotal') -and
        (Test-Path (Join-Path $fixture 'src/auth.ts')))
    Check TARGETED ($discovery -match 'Fix calculateTotal in src/cart.ts' -and
        $discovery -match 'relevant references/tests' -and
        $discovery -match 'not a\s+project survey' -and $discovery -match 'Level 1: targeted')
    Check PROGRESSIVE ($discovery -match 'Level 0:' -and $discovery -match 'Level 2:' -and
        $discovery -match 'Level 3:' -and $discovery -match 'Widen only if' -and
        $discovery -match 'observed evidence shows broader impact')
    Check BROAD_ALLOWED ($discovery -match 'Refactor authentication across\s+all services' -and
        $discovery -match 'audit these 40 independent\s+modules' -and $discovery -match 'repository-wide analysis')
    # Same Git request through /maintain: assert administrative rather than source-first policy.
    Check MAINTENANCE_ADMIN ($admin -match 'distinguish repository administration' -and
        $admin -match 'start with administrative context only' -and
        $admin -match 'Do not first inventory source' -and $admin -match 'history\s+rewrite plus push' -and
        $admin -match 'non-mutating' -and $admin -match 'not definitive remote write')
    Check MAINTENANCE_BOUNDARY ($maintenance -match 'explicit `/maintain` invocation' -and
        $maintenance -match '(?s)action: subagent\s+resource: "\*"\s+effect: deny')
    Check INVARIANTS ($kael -match 'MAX_ACTIVE_CHILDREN = 4' -and
        $kael -match 'model: "openai/gpt-6-sol#high"' -and
        $maintenance -match 'model: openai/gpt-6-sol#high' -and
        $kael -notmatch 'Luna Fast|project-context\.json' -and $maintenance -notmatch 'project-context\.json')
    Write-Output 'PREFLIGHT / SCOPED DISCOVERY QUALIFICATION: PASS (static policy + fixture only; interactive sequencing and child counts NOT VERIFIED)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'PREFLIGHT / SCOPED DISCOVERY QUALIFICATION: FAIL'
    exit 1
}
