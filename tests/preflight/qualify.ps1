[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$kael = [IO.File]::ReadAllText((Join-Path $root 'olympus/harnesses/opencode/agent-prompts/kael.md'))
$kovan = [IO.File]::ReadAllText((Join-Path $root 'olympus/harnesses/opencode/agent-prompts/kovan.md'))
$nox = [IO.File]::ReadAllText((Join-Path $root 'olympus/harnesses/opencode/agent-prompts/nox.md'))
$maintenance = [IO.File]::ReadAllText((Join-Path $root 'olympus/policies/maintenance-context.md'))
$routing = [IO.File]::ReadAllText((Join-Path $root 'olympus/policies/routing.md'))
$orchestration = [IO.File]::ReadAllText((Join-Path $root 'olympus/policies/orchestration.toml'))
$models = [IO.File]::ReadAllText((Join-Path $root 'olympus/core/models.toml'))
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
function Subsection([string]$Text, [string]$Heading) {
    $match = [regex]::Match($Text, '(?ms)^### ' + [regex]::Escape($Heading) + '\s*\r?\n(.*?)(?=^### |^## |\z)')
    if (-not $match.Success) { throw "Missing subsection: $Heading" }
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
    $kaelMetadata = Frontmatter ([IO.File]::ReadAllText((Join-Path $root 'olympus/harnesses/opencode/agent-metadata/kael.md')))
    $noxMetadata = Frontmatter ([IO.File]::ReadAllText((Join-Path $root 'olympus/harnesses/opencode/agent-metadata/nox.md')))
    $discovery = Section $kael 'Task-scoped, progressive discovery'
    $mission = Section $kael 'Mission and routing'
    $repositoryPreflight = Subsection $kael 'OpenCode repository preflight'

    Check ORDER ($mission.IndexOf('Capability Preflight') -ge 0 -and
        $mission.IndexOf('Capability Preflight') -lt $mission.IndexOf('choose DIRECT') -and
        $kael.IndexOf('## Capability Preflight') -lt $kael.IndexOf('Use the delegation gate'))
    Check PREFLIGHT ($preflight -match 'actual outcome and required\s+capabilities' -and
        $preflight -match 'target identity' -and $preflight -match 'role permissions' -and
        $preflight -match 'If a root,\s+identity, ownership, or manifest fact is missing, route the smallest necessary' -and
        $preflight -match 'Kael does\s+not inspect the repository or run tools to decide feasibility')
    Check KAEL_PREFLIGHT_HAS_NO_DIRECT_REPOSITORY_TOOLS ($repositoryPreflight -match 'Kael never runs `git rev-parse`, shell, or repository read/search tools' -and
        $repositoryPreflight -match 'Reuse an\s+explicit root and identity only from native session context' -and
        $repositoryPreflight -match 'an\s+Atlas\s+handoff, or Veyra''s bounded evidence' -and
        $repositoryPreflight -notmatch 'run `git rev-parse --show-toplevel` alone' -and
        $maintenance -match 'Kael never probes the root or reads repository files')
    Check IDENTITY_OWNERSHIP_PREFLIGHT_RETAINED ($repositoryPreflight -match 'canonical root, independent project identity, exact\s+target ownership' -and
        $repositoryPreflight -match 'exact\s+target ownership' -and
        $repositoryPreflight -match 'applicable installer/manifest checks' -and
        $maintenance -match 'all three canonical Core markers' -and
        $maintenance -match 'independent project identity' -and
        $maintenance -match 'positive ownership evidence for the exact target' -and
        $maintenance -match 'applicable installer/manifest and protected-path checks' -and
        $authority -match 'plus\s+applicable `.opencode/orchestrator-install.json`' -and
        $authority -match 'Olympus installer ownership\s+evidence when present')
    Check CAPABILITY_ROUTE_ORDER ($preflight -match 'INTENT → TARGET_REPOSITORY → REQUIRED_CAPABILITY → ROLE →\s+EFFECTIVE_AUTHORITY → NATIVE_ROUTE → ROUTE/BLOCK' -and
        $preflight -match 'scope against effective native permission, user constraints,\s+ownership, and policy boundaries' -and
        $preflight -match 'Kael never reads/searches repositories, runs\s+shell/Git/tests, implements, or executes technical validation' -and
        $preflight -match 'selected specialist can be invoked under the effective `subagent` permission')
    Check SPECIALIST_ROUTE ($preflight -match 'Route bounded\s+reproduction, tests, runtime validation, and measurement to Nox' -and
        $preflight -match 'implementation or explicitly authorized Git mutations to Kovan' -and
        $preflight -match 'Every product-source edit\s+uses one scoped Kovan writer' -and
        $preflight -match 'Nox may perform only read-only Git\s+integrity checks' -and
        $routing -match 'Kovan may run focused checks while implementing' -and
        $preflight -match 'Check whether native delegation is actually available to this session' -and
        $preflight -match 'allowlist or role definition alone does not prove' -and
        $preflight -match 'exact scope, and\s+child-result reconciliation lifecycle')
    Check WRITER_BOUNDARY ($kael -match 'Every known exact small source edit uses\s+\*\*one Kovan writer\*\*' -and
        $kael -match 'one mutative writer per worktree' -and
        $kael -match 'Parallel writers require\s+isolated worktrees plus non-conflicting refs and shared resources')
    Check DELEGATION_BLOCKERS ($preflight -match 'BLOCKED_DELEGATION_UNAVAILABLE' -and
        $preflight -match 'Do not claim an\s+attempt that did not happen' -and
        $preflight -match 'A user prohibition or effective native DENY means\s+do not invoke' -and
        $preflight -match 'rejection or cancellation means stop without a\s+retry or role substitution' -and
        $preflight -match 'Trivial requests still use the direct-answer path with zero children')
    Check EVIDENCE_EVALUATION_NOT_REDUNDANT_READBACK ($kael -match 'consume the terminal result, evaluate supplied evidence against the\s+acceptance criteria' -and
        $kael -notmatch 'read back relevant targets')
    Check DIRECT_ANSWER_NO_RENDER_EXCEPTION (
        $mission -match 'DIRECT only when the answer is available from existing context without tools' -and
        $kael -match 'A direct answer from existing context uses zero tools and children' -and
        $kael -notmatch 'explicitly requested render with no runtime effect'
    )
    Check NATIVE_ASK_PRESERVED ($preflight -match 'For effective native ASK, preserve the\s+exact current-task grant' -and
        $authority -match 'effective OpenCode ASK rule' -and
        $authority -match '(?s)permission_mode: NATIVE_ASK.*?lifetime: current_task' -and
        $authority -match 'exact current-task grant' -and
        $authority -match 'Native ASK is the human-consent point' -and
        $authority -match 'do not send a duplicate Kael\s+QUESTION' -and
        $authority -match 'rejection/cancellation stops it with no retry or\s+bypass' -and
        $authority -match 'If denied, keep work stopped')
    Check NO_DELEGATION ($preflight -match 'If a root,\s+identity, ownership, or manifest fact is missing, route the smallest necessary\s+read-only evidence task to Atlas or Veyra' -and
        $preflight -notmatch 'Orin to decide the plane' -and
        $preflight -match 'Trivial requests still use the direct-answer path with zero children')
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
        $maintenance -match 'all three canonical Core markers' -and
        $maintenance -match 'olympus/core/models\.toml' -and
        $maintenance -match 'olympus/core/identities\.toml' -and
        $maintenance -match 'olympus/policies/routing\.md' -and
        $maintenance -match 'independent project identity' -and
        $maintenance -match 'A directory name, a request mentioning Olympus, or an isolated matching file is insufficient' -and
        $maintenance -match 'If identity, ownership, or target is unclear or conflicting, stop dependent work' -and
        $maintenance -match 'For a different user project, work only on that project' -and
        $maintenance -match 'Do not reach into a separate OlympusAgents checkout' -and
        $maintenance -match 'manifest-owned files')
    Check KAEL_NATIVE_PERMISSION ($kaelMetadata -notmatch '(?m)^  - action: external_directory\b' -and
        $kaelMetadata -match '(?m)^  - action: shell\r?\n    resource: "\*"\r?\n    effect: deny(?:\r?\n|$)' -and
        $kaelMetadata -notmatch '(?ms)^  - action: shell\r?\n    resource: [^\r\n]+\r?\n    effect: allow$' -and
        $kaelMetadata -match '(?m)^  - action: read\r?\n    resource: "\*"\r?\n    effect: deny(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: glob\r?\n    resource: "\*"\r?\n    effect: deny(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: grep\r?\n    resource: "\*"\r?\n    effect: deny(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: list\r?\n    resource: "\*"\r?\n    effect: deny(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: lsp\r?\n    resource: "\*"\r?\n    effect: deny(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: edit\r?\n    resource: "\*"\r?\n    effect: deny(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: serena_\*\r?\n    resource: "\*"\r?\n    effect: deny(?:\r?\n|$)' -and
        $kaelMetadata -notmatch '(?ms)^  - action: serena_[^\r\n]*\r?\n    resource: [^\r\n]+\r?\n    effect: allow$' -and
        $kaelMetadata -match '(?m)^  - action: subagent\r?\n    resource: "\*"\r?\n    effect: deny(?:\r?\n|$)' -and
        $kaelMetadata -match '(?m)^  - action: subagent\r?\n    resource: nox\r?\n    effect: allow(?:\r?\n|$)')
    $expectedKaelChildren = @('veyra','kovan','nox','vera','talos','helios','thales')
    $actualKaelChildren = @([regex]::Matches($kaelMetadata, '(?m)^  - action: subagent\r?\n    resource: ([^\r\n]+)\r?\n    effect: allow\r?$') |
        ForEach-Object { $_.Groups[1].Value.Trim('"') })
    Check KAEL_SPECIALIST_ALLOWLIST_UNCHANGED (($actualKaelChildren -join ',') -ceq ($expectedKaelChildren -join ',') -and
        $kaelMetadata -match '(?m)^mode: primary\r?$' -and
        $kaelMetadata -match 'model: "\{\{opencode_model\}\}#\{\{effort\}\}"')
    Check NOX_NATIVE_SHELL ($noxMetadata -match '(?m)^  - action: shell\r?\n    resource: "\*"\r?\n    effect: allow(?:\r?\n|$)' -and
        $nox -match 'normally source-read-\s*only' -and $nox -match 'execute validation relevant to the task contract')

    # Controlled small fixture: localized cart target, related test, unrelated auth module.
    Check FIXTURE ((Test-Path (Join-Path $fixture 'src/cart.ts')) -and
        ([IO.File]::ReadAllText((Join-Path $fixture 'src/cart.ts')) -match 'function calculateTotal') -and
        ([IO.File]::ReadAllText((Join-Path $fixture 'tests/cart.test.ts')) -match 'calculateTotal') -and
        (Test-Path (Join-Path $fixture 'src/auth.ts')))
    Check TARGETED ($discovery -match 'Fix calculateTotal in src/cart.ts' -and
        $discovery -match 'Veyra gathers targeted file, symbol, nearby-reference, and relevant\s+test evidence' -and
        $discovery -match 'not a\s+project survey' -and $discovery -match 'Level 1: Veyra gathers targeted')
    Check PROGRESSIVE ($discovery -match 'Level 0:' -and $discovery -match 'Level 2: Veyra gathers' -and
        $discovery -match 'Level 3:' -and $discovery -match 'Widen only if' -and
        $discovery -match 'observed evidence shows broader impact')
    Check RESEARCH_PROPORTIONALITY ($discovery -match 'Kael does not explore repositories or conduct technical research' -and
        $discovery -match 'Before widening research or delegating an adjacent conceptual or external\s+consultation' -and
        $discovery -match 'goal-relevant uncertainty it would resolve and what\s+decision, hypothesis, or verification could change' -and
        $discovery -match 'Start with the closest\s+supplied or user-observed behavior, code, and evidence' -and
        $discovery -match 'Deepen only when evidence shows a\s+dependency, technical contradiction, persistent failure, material risk,\s+security or permission condition \(including an observed access-denied result\),\s+a required gate, or the user explicitly asks for the investigation' -and
        $discovery -match 'route\s+relevant technical documentation research to Veyra or another eligible evidence\s+worker when it can resolve such uncertainty' -and
        $discovery -match 'Stop when supplied evidence is\s+sufficient to act or conclude' -and
        $discovery -match 'Keep this judgment silent for trivial tasks')
    Check BROAD_ALLOWED ($discovery -match 'Refactor authentication across\s+all services' -and
        $discovery -match 'audit these 40 independent\s+modules' -and $discovery -match 'repository-wide analysis')
    # Admitted Olympus Git work uses administrative rather than source-first policy.
    Check CONTEXTUAL_MAINTENANCE ($maintenance -match 'Kael is the only root orchestrator' -and
        $maintenance -match 'Kael never probes the root or reads repository files' -and
        $maintenance -match 'all three canonical Core markers' -and
        $maintenance -match 'positive ownership evidence for the exact target' -and
        $maintenance -match 'A native `/goal` surface remains opt-in')
    Check INVARIANTS ($orchestration -match '(?m)^max_children = 4\r?$' -and
        $kael.Contains('MAX_ACTIVE_CHILDREN = {{max_children}}') -and
        $models -match '(?ms)^\[roles\.kael\]\s+family = "sol"\s+effort = "high"')
    Write-Output 'PREFLIGHT / SCOPED DISCOVERY QUALIFICATION: PASS (static policy contracts + fixture only; no live delegation or native permission behavior executed)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'PREFLIGHT / SCOPED DISCOVERY QUALIFICATION: FAIL'
    exit 1
}
