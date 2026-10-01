[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
function Text([string]$path) { [IO.File]::ReadAllText((Join-Path $root $path)) }
function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}

# Policy model: distinguishes normal project Git from Olympus administration.
function Route([string]$purpose, [string]$operation, [bool]$explicitMaintain = $false,
               [bool]$explicitOlympusEscape = $false, [bool]$highImpact = $false,
               [bool]$authorized = $false) {
    $olympus = $purpose -eq 'olympus' -or $explicitOlympusEscape
    if ($explicitMaintain) {
        return [pscustomobject]@{ plane='AEGIS'; action='ADMIT'; confirmation=$false }
    }
    if ($purpose -eq 'user-project') {
        $confirmation = $highImpact -and -not $authorized
        return [pscustomobject]@{ plane='NORMAL'; action=$(if ($confirmation) { 'NEEDS_EXPLICIT_AUTHORIZATION' } else { 'ALLOW' }); confirmation=$confirmation }
    }
    [pscustomobject]@{ plane='NORMAL'; action='ALLOW'; confirmation=$false }
}

function Scoped-Work([string]$constraint, [string]$kind) {
    if ($constraint -eq 'no-kovan') { return [pscustomobject]@{ allowed=$false; role='NONE' } }
    if ($constraint -eq 'no-implementation' -and $kind -eq 'implementation') { return [pscustomobject]@{ allowed=$false; role='NONE' } }
    if ($constraint -eq 'no-production' -and $kind -eq 'production') { return [pscustomobject]@{ allowed=$false; role='NONE' } }
    $role = switch ($kind) {
        'implementation' { 'kovan' }
        'docs' { 'kovan' }
        'tests' { 'kovan' }
        'planning' { 'kael-or-atlas' }
        default { 'normal-plane-role' }
    }
    [pscustomobject]@{ allowed=$true; role=$role }
}

function Question-Decision([bool]$determined, [bool]$materialAmbiguity) {
    [pscustomobject]@{ count=$(if (-not $determined -and $materialAmbiguity) { 1 } else { 0 }); allowed=(-not $determined -and $materialAmbiguity) }
}
function Git-Contract([string]$taskType, [string]$writeScope, [string]$gitScope) {
    if ($taskType -eq 'GIT_ONLY') { return ($writeScope -eq 'NOT_APPLICABLE' -and -not [string]::IsNullOrWhiteSpace($gitScope)) }
    if ($taskType -eq 'MIXED') { return (-not [string]::IsNullOrWhiteSpace($writeScope) -and -not [string]::IsNullOrWhiteSpace($gitScope)) }
    if ($taskType -eq 'FILE_WRITE') { return (-not [string]::IsNullOrWhiteSpace($writeScope)) }
    $false
}

try {
    $kael = Text '.opencode/agents/kael.md'
    $kovan = Text '.opencode/agents/kovan.md'
    $nox = Text '.opencode/agents/nox.md'
    $aegis = Text '.opencode/agents/aegis.md'
    $command = Text '.opencode/commands/maintain.md'
    $readme = Text 'README.md'
    $docs = Text 'docs/DEVELOPMENT.md'

    Check 'POLICY_ORDINARY_GIT_NORMAL' ($kael -match 'Ordinary Git work in a trusted user project belongs to the normal plane' -and
        $kovan -match 'Kovan is the normal-plane Git writer for an explicitly requested operation' -and
        $aegis -match 'Kael remains the recommended normal workflow' -and
        $readme -match 'project releases.*belongs to the normal Kael plane')
    Check 'POLICY_AEGIS_ANY_REPOSITORY' ($aegis -match 'in any repository, including ordinary user projects' -and
        $command -match 'MAINTENANCE_AUTH: VALID' -and $command -match 'AEGIS_SCOPE: ACCEPTED')
    Check 'POLICY_GIT_IMPACT_NOT_PLANE' ($kael -match '(?s)Destructive or high-impact Git\s+operations require explicit, proportionate user authorization, but still do not\s+require Aegis solely because they are Git' -and
        $kovan -match '(?s)History rewrites, force-pushes.*operations require explicit user authority.*proportionate preflight')
    Check 'POLICY_GIT_ONLY_OWNERSHIP' ($kael -match 'TASK_TYPE: GIT_ONLY or\s+MIXED' -and
        $kael -match 'WRITE_SCOPE to `NOT_APPLICABLE' -and $kael -match 'GIT_SCOPE naming the trusted repository' -and
        $kovan -match 'TASK_TYPE: FILE_WRITE \| GIT_ONLY \| MIXED' -and
        $kovan -match 'For GIT_ONLY, WRITE_SCOPE must be exactly' -and
        $kovan -match 'GIT_SCOPE must identify the trusted current repository' -and
        $kovan -match 'Stage only\s+GIT_SCOPE-owned task paths' -and
        $nox -match 'Git access is read-only validation' -and $nox -match 'never stage, commit, push')
    Check 'POLICY_CONSTRAINT_SEMANTICS' ($kael -match '(?s)“Do not use Kovan for\s+implementation” prohibits Kovan implementation assignments' -and
        $kael -match '(?s)“Do not modify production code” prohibits production-code\s+writes' -and
        $kael -match '“Do not invoke Kovan” prohibits Kovan completely')
    Check 'POLICY_NO_REDUNDANT_QUESTIONS' ($kael -match 'Do not ask the user to repeat or waive an outcome already\s+determined' -and
        $kael -match 'Deterministic outcomes have QUESTION COUNT = 0' -and
        $kael -match 'materially ambiguous decision' -and
        $kael -match 'Native ASK is the human-consent point' -and
        $kael -match 'do not send a duplicate Kael\s+QUESTION')
    $nativeConfig = Text 'opencode.jsonc'
    Check 'POLICY_NATIVE_AUTHORITY_ASK' ($nativeConfig -match '(?s)"action":\s*"edit"\s*,\s*"resource":\s*"\*"\s*,\s*"effect":\s*"ask"' -and
        $nativeConfig -match '(?s)"action":\s*"external_directory"\s*,\s*"resource":\s*"\*"\s*,\s*"effect":\s*"ask"' -and
        $kovan -match '\.opencode/plugins/\*\*"\s+effect: ask' -and
        $kovan -match '\.opencode/agents/\*\*"\s+effect: deny' -and
        $kovan -match '(?s)action: external_directory\s+resource: "?\*"?\s+effect: ask')

    $normalCommit = Route 'user-project' 'commit'
    $normalPush = Route 'user-project' 'push'
    $normalStage = Route 'user-project' 'stage-task-owned'
    $normalRead = Route 'user-project' 'status-diff'
    $normalRefs = Route 'user-project' 'branch-tag-release'
    $olympus = Route 'olympus' 'framework-maintenance' $true
    $escape = Route 'framework-gap' 'escape-hatch' $true $true
    $highImpact = Route 'user-project' 'force-push' $false $false $true $false
    $highImpactAuthorized = Route 'user-project' 'force-push' $false $false $true $true
    $ordinaryMaintain = Route 'user-project' 'commit' $true
    Check 'ROUTE_NORMAL_COMMIT' ($normalCommit.plane -eq 'NORMAL' -and $normalCommit.action -eq 'ALLOW')
    Check 'ROUTE_NORMAL_PUSH' ($normalPush.plane -eq 'NORMAL' -and $normalPush.action -eq 'ALLOW')
    Check 'ROUTE_NORMAL_STAGE_OWNED' ($normalStage.plane -eq 'NORMAL' -and $normalStage.action -eq 'ALLOW' -and
        $kovan -match 'Stage only\s+GIT_SCOPE-owned task paths')
    Check 'ROUTE_NORMAL_STATUS_DIFF' ($normalRead.plane -eq 'NORMAL' -and $normalRead.action -eq 'ALLOW')
    Check 'ROUTE_NORMAL_BRANCH_TAG_RELEASE' ($normalRefs.plane -eq 'NORMAL' -and $normalRefs.action -eq 'ALLOW')
    Check 'ROUTE_OLYMPUS_MAINTENANCE_AEGIS' ($olympus.plane -eq 'AEGIS' -and $olympus.action -eq 'ADMIT')
    Check 'ROUTE_EXPLICIT_OLYMPUS_ESCAPE_AEGIS' ($escape.plane -eq 'AEGIS' -and $escape.action -eq 'ADMIT')
    Check 'ROUTE_HIGH_IMPACT_AUTH_NOT_AEGIS' ($highImpact.plane -eq 'NORMAL' -and
        $highImpact.action -eq 'NEEDS_EXPLICIT_AUTHORIZATION' -and $highImpact.confirmation)
    Check 'ROUTE_HIGH_IMPACT_EXPLICIT_STAYS_NORMAL' ($highImpactAuthorized.plane -eq 'NORMAL' -and $highImpactAuthorized.action -eq 'ALLOW')
    Check 'ROUTE_EXPLICIT_PROJECT_MAINTAIN_ACCEPTED' ($ordinaryMaintain.plane -eq 'AEGIS' -and $ordinaryMaintain.action -eq 'ADMIT')

    Check 'SCOPE_GIT_ONLY_AND_MIXED_TASK_CONTRACTS' ( (Git-Contract 'GIT_ONLY' 'NOT_APPLICABLE' 'repo:trusted; operation:commit; paths:owned') -and
        (Git-Contract 'MIXED' 'src/task-owned' 'repo:trusted; operation:stage-commit; paths:src/task-owned') -and
        -not (Git-Contract 'GIT_ONLY' '' 'repo:trusted; operation:commit') -and
        -not (Git-Contract 'MIXED' 'src/task-owned' ''))

    $docOnly = Scoped-Work 'no-implementation' 'docs'
    $testsOnly = Scoped-Work 'no-implementation' 'tests'
    $planNoProduction = Scoped-Work 'no-production' 'planning'
    $docsNoProduction = Scoped-Work 'no-production' 'docs'
    $forbiddenImplementation = Scoped-Work 'no-implementation' 'implementation'
    $kovanProhibited = Scoped-Work 'no-kovan' 'tests'
    Check 'SCOPE_IMPLEMENTATION_PROHIBITED_DOCS_ALLOWED' ($docOnly.allowed -and $testsOnly.allowed -and $docOnly.role -eq 'kovan')
    Check 'SCOPE_PRODUCTION_PROHIBITED_NONPRODUCTION_ALLOWED' ($planNoProduction.allowed -and $docsNoProduction.allowed)
    Check 'SCOPE_EXPLICIT_KOVAN_PROHIBITION_DENIED' (-not $kovanProhibited.allowed -and $kovanProhibited.role -eq 'NONE' -and
        -not $forbiddenImplementation.allowed)

    $determined = Question-Decision $true $false
    $ambiguous = Question-Decision $false $true
    Check 'QUESTION_DETERMINISTIC_ZERO' ($determined.count -eq 0 -and -not $determined.allowed)
    Check 'QUESTION_MATERIAL_AMBIGUITY_ALLOWED' ($ambiguous.count -eq 1 -and $ambiguous.allowed)

    Write-Output 'ROUTING / CONSTRAINT QUALIFICATION: PASS (static contracts + deterministic policy cases)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'ROUTING / CONSTRAINT QUALIFICATION: FAIL'
    exit 1
}
