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

# Synthetic ordering contract: these events are explicit sentinels, not timers
# and not real Aegis tool invocations.
function Run-Maintenance([string]$targetOwner, [bool]$explicitMaintain, [string[]]$operations) {
    $events = [Collections.Generic.List[string]]::new()
    $events.Add('CHEAP_SCOPE_GATE')
    $decision = if ($explicitMaintain -and $targetOwner -eq 'OLYMPUS') { 'ACCEPTED' } else { 'REJECTED' }
    $counts = [ordered]@{ implementation=0; qualification=0; subagents=0; git=0 }
    if ($decision -eq 'REJECTED') {
        return [pscustomobject]@{ decision=$decision; events=$events.ToArray(); counts=$counts }
    }
    foreach ($operation in $operations) {
        $events.Add("EXPENSIVE_WORK_MARKER:$operation")
        switch ($operation) {
            'IMPLEMENTATION' { $counts.implementation++ }
            'QUALIFICATION' { $counts.qualification++ }
            'SUBAGENT' { $counts.subagents++ }
            { $_ -in @('COMMIT','PUSH') } { $counts.git++ }
        }
    }
    [pscustomobject]@{ decision=$decision; events=$events.ToArray(); counts=$counts }
}

function Try-LateReclassification($scope, [bool]$newMaterialEvidence, [string]$evidence,
                                 [string]$newTargetOwner = '') {
    if ($scope.decision -ne 'ACCEPTED') { return $scope }
    if (-not $newMaterialEvidence -or [string]::IsNullOrWhiteSpace($evidence) -or $newTargetOwner -ne 'USER_PROJECT') {
        return [pscustomobject]@{ decision='ACCEPTED'; reclassified=$false; evidence='' }
    }
    [pscustomobject]@{ decision='REJECTED'; reclassified=$true; evidence=$evidence }
}

function Normal-ProjectWrite([string]$target) {
    if ($target -eq 'olympus/roles/nox.md') {
        return [pscustomobject]@{ allowed=$false; aegisStarted=$false; state='OLYMPUS_OWNED_TARGET_BLOCKED' }
    }
    [pscustomobject]@{ allowed=$true; aegisStarted=$false; state='NORMAL_PROJECT_SCOPE' }
}

try {
    $core = Text 'olympus/policies/maintenance-plane.md'
    $aegis = Text '.opencode/agents/aegis.md'
    $command = Text '.opencode/commands/maintain.md'
    $kael = Text '.opencode/agents/kael.md'
    $aegisSource = Text 'olympus/harnesses/opencode/agent-prompts/aegis.md'
    $commandSource = Text 'olympus/harnesses/opencode/maintain.md'
    $kaelSource = Text 'olympus/harnesses/opencode/agent-prompts/kael.md'
    # Renderer output is canonical UTF-8/LF; normalize Git's Windows checkout
    # line endings before comparing embedded policy text.
    $canonicalPolicy = ($core -replace '\r\n?', "`n").Trim()
    $canonicalAegis = $aegis -replace '\r\n?', "`n"
    $canonicalCommand = $command -replace '\r\n?', "`n"

    Check 'CORE_POLICY_HAS_EARLY_GATE_AND_OWNER_CLASSIFICATION' (
        $core -match 'Cheap scope gate — before any other work' -and
        $core -match 'primarily by \*\*what target is being changed and who owns it\*\*' -and
        $core -match 'AEGIS_SCOPE: ACCEPTED.*?AEGIS_SCOPE: REJECTED' -and
        $core -match 'Do not perform broad repository exploration or expensive searches')
    Check 'CORE_POLICY_ACCEPTED_SCOPE_STICKY_WITH_NEW_EVIDENCE_EXCEPTION' (
        $core -match 'After scope is accepted, retain that execution.s Olympus-scope ownership' -and
        $core -match 'genuinely new, material evidence' -and
        $core -match 'identify the exact new evidence')
    Check 'CORE_POLICY_OPERATION_DOES_NOT_SET_PLANE' (
        $core -match 'Implementation, tests, qualification, documentation, commit, push' -and
        $core -match 'Ordinary user-project work, including status/diff, stage, commit, push' -and
        $core -match 'does not elevate a user-project target')
    Check 'CORE_POLICY_NORMAL_PROJECT_CANNOT_EDIT_GLOBAL_NOX' (
        $core -match 'normal project workflow must not modify an Olympus-owned target' -and
        $core -match 'change Olympus.s global Nox policy' -and
        $core -match 'do not edit it from the project task' -and
        $core -match 'automatically invoke Aegis' -and
        $core -match 'Do not provide a ready-made `/maintain` reroute')
    Check 'OPENCODE_AEGIS_AND_MAINTAIN_DERIVE_CANONICAL_POLICY' (
        $aegisSource.Contains('{{maintenance_plane_policy}}') -and
        $commandSource.Contains('{{maintenance_plane_policy}}') -and
        $canonicalAegis.Contains($canonicalPolicy) -and $canonicalCommand.Contains($canonicalPolicy))
    Check 'OPENCODE_KAEL_DERIVES_TARGET_BOUNDARY_FROM_CORE' (
        $kaelSource.Contains('{{maintenance_target_boundary}}') -and
        $kael -match 'Classify the plane primarily by \*\*what target is being changed and who owns it\*\*' -and
        $kael -match 'do not edit it from the project task' -and $kael -match 'automatically invoke Aegis')

    $gateIndex = $aegis.IndexOf('## Cheap scope gate — before any other work', [StringComparison]::Ordinal)
    $fastPathIndex = $aegis.IndexOf('## Olympus administrative fast path', [StringComparison]::Ordinal)
    $adminCheckIndex = $aegis.IndexOf('After the Olympus-only scope check', [StringComparison]::Ordinal)
    Check 'EXPENSIVE_WORK_SENTINEL_POLICY_ORDER' ($gateIndex -ge 0 -and $fastPathIndex -gt $gateIndex -and $adminCheckIndex -gt $gateIndex)
    Check 'MAINTAIN_COMMAND_SCOPE_GATE_BEFORE_CONTINUATION' (
        $command.IndexOf('## Cheap scope gate — before any other work', [StringComparison]::Ordinal) -ge 0 -and
        $command.IndexOf('AEGIS_SCOPE: ACCEPTED', [StringComparison]::Ordinal) -lt $command.IndexOf('Perform exactly the maintenance task described above.', [StringComparison]::Ordinal))

    # CASE A — clear ordinary project implementation: gate first, then stop.
    $a = Run-Maintenance 'USER_PROJECT' $true @('IMPLEMENTATION','QUALIFICATION','SUBAGENT')
    Check 'CASE_A_REJECTS_BEFORE_EXPENSIVE_WORK' ($a.decision -eq 'REJECTED' -and
        $a.events.Count -eq 1 -and $a.events[0] -eq 'CHEAP_SCOPE_GATE' -and
        $a.counts.implementation -eq 0 -and $a.counts.qualification -eq 0 -and $a.counts.subagents -eq 0)

    # CASE B — an Olympus-owned policy target is accepted and work may proceed.
    $b = Run-Maintenance 'OLYMPUS' $true @('TARGETED_FRAMEWORK_INSPECTION')
    Check 'CASE_B_ACCEPTS_OLYMPUS_TARGET_AND_CONTINUES' ($b.decision -eq 'ACCEPTED' -and
        $b.events.Count -eq 2 -and $b.events[0] -eq 'CHEAP_SCOPE_GATE' -and
        $b.events[1] -eq 'EXPENSIVE_WORK_MARKER:TARGETED_FRAMEWORK_INSPECTION')

    # CASE C — operation mix cannot reclassify an authorized Olympus target.
    $c = Run-Maintenance 'OLYMPUS' $true @('IMPLEMENTATION','TESTS','QUALIFICATION','COMMIT','PUSH')
    Check 'CASE_C_OLYMPUS_OPERATIONS_STAY_ACCEPTED' ($c.decision -eq 'ACCEPTED' -and
        $c.events[0] -eq 'CHEAP_SCOPE_GATE' -and $c.events.Count -eq 6 -and
        $c.counts.implementation -eq 1 -and $c.counts.qualification -eq 1 -and $c.counts.git -eq 2)

    # CASE D — no new facts means no late rejection.
    $d = Try-LateReclassification $c $false ''
    Check 'CASE_D_NO_LATE_REJECTION_WITHOUT_NEW_EVIDENCE' ($d.decision -eq 'ACCEPTED' -and -not $d.reclassified)

    # CASE E — only specific, newly learned ownership evidence permits reclassification.
    $evidence = 'New target resolution: workspace/coffee-shop/src/foo.ts is the actual user-owned edit target; it is not an Olympus source or Olympus-owned generated resource.'
    $e = Try-LateReclassification $c $true $evidence 'USER_PROJECT'
    Check 'CASE_E_MATERIAL_NEW_EVIDENCE_ALLOWS_RECLASSIFICATION' ($e.decision -eq 'REJECTED' -and
        $e.reclassified -and $e.evidence -ceq $evidence)
    $eUnproven = Try-LateReclassification $c $true 'New qualification request discovered; target unchanged.' 'OLYMPUS'
    Check 'CASE_E_REQUIRES_EVIDENCE_OF_USER_PROJECT_OWNERSHIP' ($eUnproven.decision -eq 'ACCEPTED' -and -not $eUnproven.reclassified)

    # CASE F — a normal project cannot turn a request for global Nox into a project write.
    $f = Normal-ProjectWrite 'olympus/roles/nox.md'
    Check 'CASE_F_NORMAL_PROJECT_CANNOT_MODIFY_OLYMPUS_NOX' (-not $f.allowed -and
        -not $f.aegisStarted -and $f.state -eq 'OLYMPUS_OWNED_TARGET_BLOCKED')

    # Deterministic ordering sentinel for every admitted path: scope gate precedes
    # its first expensive marker; no elapsed-time assertion is used.
    foreach ($accepted in @($b,$c)) {
        $firstMarker = [Array]::FindIndex([string[]]$accepted.events, [Predicate[string]]{ param($event) $event.StartsWith('EXPENSIVE_WORK_MARKER:', [StringComparison]::Ordinal) })
        Check 'EXPENSIVE_WORK_SENTINEL_GATE_PRECEDES_FIRST_MARKER' ($accepted.decision -eq 'ACCEPTED' -and
            $accepted.events[0] -eq 'CHEAP_SCOPE_GATE' -and $firstMarker -gt 0)
    }

    Write-Output 'MAINTENANCE SCOPE QUALIFICATION: PASS (static Core/adapter contracts + deterministic synthetic ordering; no agent/runtime execution)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'MAINTENANCE SCOPE QUALIFICATION: FAIL'
    exit 1
}
