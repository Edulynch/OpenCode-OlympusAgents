[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$kael = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/kael.md'))
$kovan = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/kovan.md'))
$nox = [IO.File]::ReadAllText((Join-Path $root '.opencode/agents/nox.md'))
$maintenance = [IO.File]::ReadAllText((Join-Path $root 'olympus/policies/maintenance-context.md'))
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
function Frontmatter([string]$Text) {
    $match = [regex]::Match($Text, '\A---\r?\n(?<frontmatter>.*?)\r?\n---[ \t]*(?:\r?\n|\z)', [Text.RegularExpressions.RegexOptions]::Singleline)
    if (-not $match.Success) { throw 'Generated agent metadata frontmatter is missing or malformed' }
    return $match.Groups['frontmatter'].Value
}

try {
    $preflight = Section $kael 'Capability Preflight — before research'
    $authority = Section $kael 'Task-scoped Authority Grants and native permission outcomes'
    $kaelMetadata = Frontmatter $kael
    $noxMetadata = Frontmatter $nox
    $discovery = Section $kael 'Task-scoped, progressive discovery'
    $mission = Section $kael 'Mission and routing'

    Check ORDER ($mission.IndexOf('Capability Preflight') -ge 0 -and
        $mission.IndexOf('Capability Preflight') -lt $mission.IndexOf('choose DIRECT') -and
        $kael.IndexOf('## Capability Preflight') -lt $kael.IndexOf('Use the delegation gate'))
    Check PREFLIGHT ($preflight -match 'actual outcome' -and $preflight -match 'required capabilities' -and
        $preflight -match 'target-repository\s+identity' -and $preflight -match 'role permissions' -and
        $preflight -match 'is any repository discovery\s+needed' -and
        $preflight -match 'not a research phase')
    Check CAPABILITY_ROUTE_ORDER ($preflight -match 'INTENT → TARGET_REPOSITORY → REQUIRED_CAPABILITY → ROLE →\s+EFFECTIVE_AUTHORITY → NATIVE_ROUTE → EXECUTE/BLOCK' -and
        $preflight -match 'scope against that role''s effective native permission, user constraints,\s+ownership, and policy boundaries' -and
        $preflight -match 'selected specialist can be invoked under the effective `subagent` permission')
    Check SPECIALIST_ROUTE ($preflight -match 'read-only `git status --short` to\s+Nox as one bounded child assignment' -and
        $preflight -match '`SCOPE: read-only git status --short`\s+and `REPOSITORY_ROOT: <the identified trusted repository root>`' -and
        $preflight -match 'Reconcile and consume that original child''s terminal result' -and
        $preflight -match 'including\s+its directly observed command outcome' -and
        $preflight -match 'an absent\s+or unresolved result does not authorize a retry' -and
        $preflight -match 'scoped tests\s+to Nox and\s+implementation or explicitly authorized Git mutations to Kovan' -and
        $preflight -match 'Check whether native delegation is actually available to this session' -and
        $preflight -match 'allowlist or role definition alone does not prove' -and
        $preflight -match 'exact scope, and\s+child-result reconciliation lifecycle')
    Check DELEGATION_BLOCKERS ($preflight -match 'BLOCKED_DELEGATION_UNAVAILABLE' -and
        $preflight -match 'Do not claim an\s+attempt that did not happen' -and
        $preflight -match 'A user prohibition or effective native DENY means\s+do not invoke' -and
        $preflight -match 'rejection or cancellation means stop without a\s+retry or role substitution' -and
        $preflight -match 'Trivial requests still use the direct-answer path with zero children')
    Check NATIVE_ASK_PRESERVED ($preflight -match 'For effective native ASK, preserve the\s+exact current-task grant' -and
        $authority -match 'effective OpenCode ASK rule' -and
        $authority -match '(?s)permission_mode: NATIVE_ASK.*?lifetime: current_task' -and
        $authority -match 'exact current-task grant' -and
        $authority -match 'Native ASK is the human-consent point' -and
        $authority -match 'do not send a duplicate Kael\s+QUESTION' -and
        $authority -match 'rejection/cancellation stops it with no retry or\s+bypass' -and
        $authority -match 'If denied, keep work stopped')
    Check NO_DELEGATION ($preflight -match 'Do not invoke Veyra to decide\s+whether Olympus has permission' -and
        $preflight -match 'Orin to decide the plane' -and
        $preflight -match 'inspect the project\s+to confirm an already-known boundary')
    Check NORMAL_GIT_ROUTING ($preflight -match 'Ordinary Git work in a trusted project belongs to Kael''s normal workflow' -and
        $preflight -match 'Kovan is the normal-plane Git writer' -and
        $preflight -match 'Nox may perform only read-only Git\s+integrity checks' -and
        $kael -match 'TASK_TYPE: GIT_ONLY or\s+MIXED' -and
        $kovan -match 'For GIT_ONLY, WRITE_SCOPE must be exactly' -and
        $kovan -match 'exact task-owned paths/refs')
    # A second known normal-plane blocker must precede optional discovery.
    Check CAPABILITY_BLOCKED ($preflight -match 'external action has no\s+available authorized path' -and
        $preflight -match 'explain the blocker before optional research')
    Check BOUNDARY ($maintenance -match 'Kael is the only root orchestrator' -and
        $maintenance -match 'There is no separate maintenance role, command' -and
        $maintenance -match 'canonical Olympus Core files' -and
        $maintenance -match 'olympus/core/models\.toml' -and
        $maintenance -match 'olympus/core/identities\.toml' -and
        $maintenance -match 'olympus/policies/routing\.md' -and
        $maintenance -match 'independent project-identity evidence identifies OlympusAgents' -and
        $maintenance -match 'A directory name, a request mentioning Olympus, or an isolated matching file is not sufficient evidence' -and
        $maintenance -match 'If identity or target is unclear, do not perform dependent writes' -and
        $maintenance -match 'For a different user project, work only on that project' -and
        $maintenance -match 'Do not reach into a separate OlympusAgents checkout' -and
        $maintenance -match 'manifest-owned files' -and
        $kael -notmatch '(?i)Aegis|/maintain')
    Check KAEL_NATIVE_PERMISSION ($kaelMetadata -match '(?m)^  - action: external_directory\r?\n    resource: "\*"\r?\n    effect: ask(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: shell\r?\n    resource: "\*"\r?\n    effect: ask(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: shell\r?\n    resource: "git status \*"\r?\n    effect: allow(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: subagent\r?\n    resource: "\*"\r?\n    effect: deny(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: subagent\r?\n    resource: nox\r?\n    effect: allow(?:\r?\n|$)')
    Check NOX_NATIVE_SHELL ($noxMetadata -match '(?m)^  - action: shell\r?\n    resource: "\*"\r?\n    effect: allow(?:\r?\n|$)' -and
        $nox -match 'Source-read-only trusted-project validation specialist with practical shell')

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
    Check RESEARCH_PROPORTIONALITY ($discovery -match 'Before widening research or delegating an adjacent conceptual or external\s+consultation' -and
        $discovery -match 'goal-relevant uncertainty it would resolve and what\s+decision, hypothesis, or verification could change' -and
        $discovery -match 'Start with the closest\s+observed behavior, code, and evidence' -and
        $discovery -match 'Deepen only when evidence shows a\s+dependency, technical contradiction, persistent failure, material risk,\s+security or permission condition \(including an observed access-denied result\),\s+a required gate, or the user explicitly asks for the investigation' -and
        $discovery -match 'consult\s+relevant technical documentation when it can\s+resolve such uncertainty' -and
        $discovery -match 'Stop when evidence is sufficient to act or conclude' -and
        $discovery -match 'Keep this judgment silent for trivial tasks')
    Check BROAD_ALLOWED ($discovery -match 'Refactor authentication across\s+all services' -and
        $discovery -match 'audit these 40 independent\s+modules' -and $discovery -match 'repository-wide analysis')
    # Admitted Olympus Git work uses administrative rather than source-first policy.
    Check CONTEXTUAL_MAINTENANCE ($maintenance -match 'canonical Olympus Core files' -and
        $maintenance -match 'project-identity evidence' -and
        $maintenance -match 'do not perform dependent writes' -and
        $maintenance -match 'A native `/goal` surface remains opt-in')
    Check INVARIANTS ($kael -match 'MAX_ACTIVE_CHILDREN = 4' -and
        $kael -match 'model: "openai/gpt-6.1-sol#high"' -and
        $kael -notmatch 'Luna Fast|project-context\.json')
    Write-Output 'PREFLIGHT / SCOPED DISCOVERY QUALIFICATION: PASS (static policy contracts + fixture only; no live delegation or native permission behavior executed)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'PREFLIGHT / SCOPED DISCOVERY QUALIFICATION: FAIL'
    exit 1
}
