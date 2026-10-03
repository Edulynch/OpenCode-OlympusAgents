[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))

function Text([string]$path) {
    [IO.File]::ReadAllText((Join-Path $root $path))
}

function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}

# In-memory contract qualification only; it does not inspect or emulate a live
# OpenCode session. Field values remain opaque text, including numeric-looking values.
function Parse-Fields([string]$payload) {
    $fields = [System.Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    $duplicates = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $malformed = [System.Collections.Generic.List[string]]::new()

    foreach ($line in ($payload -split '\r?\n')) {
        if ($line.Length -eq 0) { continue }
        $match = [regex]::Match($line, '^(?<name>[^:\r\n]+):[ \t]?(?<value>.*)$')
        if (-not $match.Success) {
            $malformed.Add($line)
            continue
        }

        $name = $match.Groups['name'].Value
        if ($fields.ContainsKey($name)) {
            [void]$duplicates.Add($name)
            continue
        }
        $fields.Add($name, $match.Groups['value'].Value)
    }

    [pscustomobject]@{ Fields=$fields; Duplicates=$duplicates; Malformed=$malformed }
}

function Validate-RequiredFields([string]$payload, [string[]]$required) {
    $parsed = Parse-Fields $payload
    if ($parsed.Malformed.Count -gt 0) {
        return [pscustomobject]@{ Status='STRUCTURED_RESULT_INCOMPLETE'; Reason='MALFORMED_FIELD'; Fields=$parsed.Fields }
    }
    foreach ($name in $required) {
        if (-not $parsed.Fields.ContainsKey($name)) {
            return [pscustomobject]@{ Status='STRUCTURED_RESULT_INCOMPLETE'; Reason="MISSING:$name"; Fields=$parsed.Fields }
        }
        if ($parsed.Duplicates.Contains($name)) {
            return [pscustomobject]@{ Status='STRUCTURED_RESULT_INCOMPLETE'; Reason="DUPLICATE:$name"; Fields=$parsed.Fields }
        }
    }
    $status = if ($required.Count -eq 0) { 'COMPACT_RESULT_ACCEPTED' } else { 'STRUCTURED_RESULT_COMPLETE' }
    [pscustomobject]@{ Status=$status; Reason=''; Fields=$parsed.Fields }
}

function Consume-Original($assignment, [string]$payload, [string[]]$required) {
    if ($assignment.Consumed) {
        return [pscustomobject]@{ Action='IGNORE_DUPLICATE'; Validation=$null }
    }
    $assignment.Consumed = $true
    $assignment.ConsumedCount++
    $validation = Validate-RequiredFields $payload $required
    [pscustomobject]@{ Action='CONSUME_ORIGINAL'; Validation=$validation }
}

try {
    $maintenanceFields = @('STATUS','PROBE_MARKER','EXACT_ID','EXACT_COUNT','EXACT_PATH','DECISION')
    $maintenanceResult = @'
STATUS: SUCCESS
SUMMARY: Maintenance probe completed; keep the result.
PROBE_MARKER: OLYMPUS_MAINTENANCE_FIDELITY_FINAL
EXACT_ID: MNT-FINAL-42
EXACT_COUNT: 37
EXACT_PATH: docs/maintenance-fidelity-probe.md
DECISION: KEEP
'@
    $normalResult = @'
STATUS: SUCCESS
SUMMARY: Normal child result completed.
PROBE_MARKER: OLYMPUS_RESULT_FIDELITY_001
EXACT_ID: RSLT-7F29-A1
EXACT_COUNT: 37
EXACT_PATH: docs/result-fidelity-probe.md
DECISION: KEEP
'@

    # A. Ordinary compact output has no new mandatory-field requirement.
    $compactPayload = "STATUS: SUCCESS`nSUMMARY: Ordinary completion.`nCHANGES: none"
    $compact = Validate-RequiredFields $compactPayload @()
    Check 'CASE_A_ORDINARY_COMPACT_UNCHANGED' ($compact.Status -eq 'COMPACT_RESULT_ACCEPTED' -and
        $compact.Fields['STATUS'] -ceq 'SUCCESS' -and $compact.Fields['SUMMARY'] -ceq 'Ordinary completion.')

    # B. Previously observed ordinary child exact-field probe remains valid.
    $normal = Validate-RequiredFields $normalResult $maintenanceFields
    Check 'CASE_B_NORMAL_CHILD_EXACT_FIELDS_PASS' ($normal.Status -eq 'STRUCTURED_RESULT_COMPLETE' -and
        $normal.Fields['PROBE_MARKER'] -ceq 'OLYMPUS_RESULT_FIDELITY_001' -and
        $normal.Fields['EXACT_ID'] -ceq 'RSLT-7F29-A1' -and
        $normal.Fields['EXACT_COUNT'] -ceq '37' -and
        $normal.Fields['EXACT_PATH'] -ceq 'docs/result-fidelity-probe.md' -and
        $normal.Fields['DECISION'] -ceq 'KEEP')

    # C/D. Maintenance-specific exact fields survive the modeled Kael validation unchanged.
    $validated = Validate-RequiredFields $maintenanceResult $maintenanceFields
    $allExact = $validated.Status -eq 'STRUCTURED_RESULT_COMPLETE'
    foreach ($name in $maintenanceFields) {
        if (-not [string]::Equals($validated.Fields[$name], (Parse-Fields $maintenanceResult).Fields[$name], [StringComparison]::Ordinal)) {
            $allExact = $false
        }
    }
    Check 'CASE_C_MAINTENANCE_REQUIRED_FIELDS' ($validated.Status -eq 'STRUCTURED_RESULT_COMPLETE')
    Check 'CASE_D_KAEL_RETAINS_EXACT_NAMES_AND_VALUES' $allExact

    # E. Prose can be included, or absent; it never substitutes for exact fields.
    Check 'CASE_E_SUMMARY_COEXISTS' ($validated.Fields.ContainsKey('SUMMARY') -and
        $validated.Fields['SUMMARY'] -ceq 'Maintenance probe completed; keep the result.')
    $noSummary = [regex]::Replace($maintenanceResult, '(?m)^SUMMARY:.*\r?\n', '')
    Check 'CASE_E_SUMMARY_OPTIONAL' ((Validate-RequiredFields $noSummary $maintenanceFields).Status -eq 'STRUCTURED_RESULT_COMPLETE')

    # F/G. Missing and renamed requested fields fail closed; summary is not a substitute.
    $missingPayload = [regex]::Replace($maintenanceResult, '(?m)^EXACT_COUNT:.*\r?\n', '')
    $missing = Validate-RequiredFields $missingPayload $maintenanceFields
    Check 'CASE_F_MISSING_FIELD_INCOMPLETE' ($missing.Status -eq 'STRUCTURED_RESULT_INCOMPLETE' -and
        $missing.Reason -eq 'MISSING:EXACT_COUNT')
    $renamedPayload = [regex]::Replace($maintenanceResult, '(?m)^EXACT_ID:', 'RENAMED_ID:')
    $renamed = Validate-RequiredFields $renamedPayload $maintenanceFields
    Check 'CASE_G_RENAMED_FIELD_NOT_SATISFIED' ($renamed.Status -eq 'STRUCTURED_RESULT_INCOMPLETE' -and
        $renamed.Reason -eq 'MISSING:EXACT_ID')

    # H. Unrequested fields are additive and do not affect required exact values.
    $extra = Validate-RequiredFields ($maintenanceResult + "`nFUTURE_EXTRA: allowed") $maintenanceFields
    Check 'CASE_H_EXTRA_FIELDS_ALLOWED' ($extra.Status -eq 'STRUCTURED_RESULT_COMPLETE' -and
        $extra.Fields['FUTURE_EXTRA'] -ceq 'allowed')

    # I/K. Consume the original terminal result once, even when incomplete; never replace it.
    $assignment = [pscustomobject]@{ Consumed=$false; ConsumedCount=0; ReplacementCount=0 }
    $first = Consume-Original $assignment $missingPayload $maintenanceFields
    $duplicate = Consume-Original $assignment $missingPayload $maintenanceFields
    Check 'CASE_I_DUPLICATE_CONSUMED_ONCE' ($first.Action -eq 'CONSUME_ORIGINAL' -and
        $first.Validation.Status -eq 'STRUCTURED_RESULT_INCOMPLETE' -and
        $duplicate.Action -eq 'IGNORE_DUPLICATE' -and $assignment.ConsumedCount -eq 1)
    Check 'CASE_K_NO_BLIND_RETRY' ($assignment.ReplacementCount -eq 0 -and
        $first.Validation.Status -ne 'FAILED' -and $first.Validation.Status -ne 'CONFIRMED_NOT_STARTED')

    # J. Issue #1's missing-result rule remains separate from structured-field validation.
    $lifecycle = Text 'olympus/policies/result-lifecycle.md'
    Check 'CASE_J_ISSUE1_MISSING_RESULT_SEMANTICS' ($lifecycle -match 'Missing output is not failure' -and
        $lifecycle -match 'do not replace it' -and $lifecycle -match 'Never retry an unknown or live original')

    # D/M. Canonical Aegis and Kael maintenance handoff sources both state the contract.
    $maintenancePolicy = Text 'olympus/policies/maintenance-plane.md'
    $kaelPrompt = Text 'olympus/harnesses/opencode/agent-prompts/kael.md'
    Check 'CASE_M_MAINTENANCE_HANDOFF_CONTRACT' ($maintenancePolicy -match 'EXPECTED_OUTPUT' -and
        $maintenancePolicy -match 'preserve each required field name and its produced value' -and
        $kaelPrompt -match 'STRUCTURED_RESULT_INCOMPLETE' -and
        $kaelPrompt -match 'consume the original result once' -and
        $kaelPrompt -match 'internal fidelity does not require dumping every field')

    Write-Output 'MAINTENANCE RESULT-FIDELITY QUALIFICATION: PASS (synthetic contract + canonical source checks; live handoff separate)'
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'MAINTENANCE RESULT-FIDELITY QUALIFICATION: FAIL'
    exit 1
}
