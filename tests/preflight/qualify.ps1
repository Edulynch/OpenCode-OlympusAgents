[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$kael = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/kael.md'))
$aegis = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/aegis.md'))
$kovan = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/kovan.md'))
$nox = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/nox.md'))
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
    $admin = Section $aegis 'Olympus administrative fast path'
    $mission = Section $kael 'Mission and routing'
    $handoff = Section $kael 'Explicit Aegis result handoff'
    $maintenanceBoundary = Section $kael 'Target ownership and project-plane boundary'

    Check ORDER ($mission.IndexOf('Capability Preflight') -ge 0 -and
        $mission.IndexOf('Capability Preflight') -lt $mission.IndexOf('choose DIRECT') -and
        $kael.IndexOf('## Capability Preflight') -lt $kael.IndexOf('Use the delegation gate'))
    Check PREFLIGHT ($preflight -match 'actual outcome' -and $preflight -match 'required capabilities' -and
        $preflight -match 'known Olympus' -and $preflight -match 'is any repository discovery needed' -and
        $preflight -match 'not a research phase')
    Check NO_DELEGATION ($preflight -match 'Do not invoke Veyra to decide\s+whether Olympus has permission' -and
        $preflight -match 'Orin to decide the plane' -and
        $preflight -match 'inspect the project\s+to confirm an already-known boundary')
    Check NORMAL_GIT_ROUTING ($preflight -match 'Ordinary Git work in a trusted user project belongs to the normal plane' -and
        $preflight -match 'Kovan is the normal-plane Git writer' -and
        $preflight -match 'Nox may perform only read-only Git\s+integrity checks' -and
        $preflight -match 'do not\s+require Aegis solely because they are Git' -and
        $kael -match 'TASK_TYPE: GIT_ONLY or\s+MIXED' -and
        $kovan -match 'For GIT_ONLY, WRITE_SCOPE must be exactly' -and
        $kovan -match 'exact task-owned paths/refs')
    # A second known normal-plane blocker must precede optional discovery.
    Check CAPABILITY_BLOCKED ($preflight -match 'external action has no\s+available authorized path' -and
        $preflight -match 'explain the blocker before optional research')
    Check BOUNDARY ($maintenanceBoundary -match 'Kael → Aegis remains DENIED' -and
        $maintenanceBoundary -match 'only the\s+user.s explicit `/maintain` invocation' -and
        $handoff -match 'cannot invoke or' -and $handoff -match 'delegate to Aegis' -and
        $kael -notmatch '(?m)^\s*- action: subagent\s*\r?\n\s*resource: aegis\s*\r?\n\s*effect: allow')

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
    # Admitted Olympus Git work uses administrative rather than source-first policy.
    Check MAINTENANCE_ADMIN ($admin -match 'After the Olympus-only scope check' -and
        $admin -match 'start with administrative\s+context only' -and
        $admin -match 'Do not first\s+inventory source' -and $admin -match 'history\s+rewrite plus push' -and
        $admin -match 'non-mutating' -and $admin -match 'not definitive remote write')
    Check MAINTENANCE_BOUNDARY ($aegis -match 'explicit `/maintain` invocation' -and
        $aegis -match 'Target ownership and project-plane boundary' -and
        $aegis -match 'Cheap scope gate — before any other work' -and $aegis -match 'OUT_OF_SCOPE' -and
        $aegis -match 'no project administration' -and
        $aegis -match '(?s)action: subagent\s+resource: "\*"\s+effect: deny')
    Check INVARIANTS ($kael -match 'MAX_ACTIVE_CHILDREN = 4' -and
        $kael -match 'model: "openai/gpt-6.1-sol#high"' -and
        $aegis -match 'model: openai/gpt-6-luna#max' -and
        $kael -notmatch 'Luna Fast|project-context\.json' -and $aegis -notmatch 'project-context\.json')
    Write-Output 'PREFLIGHT / SCOPED DISCOVERY QUALIFICATION: PASS (static policy + fixture only; interactive sequencing and child counts NOT VERIFIED)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'PREFLIGHT / SCOPED DISCOVERY QUALIFICATION: FAIL'
    exit 1
}
