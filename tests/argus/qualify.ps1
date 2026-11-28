[CmdletBinding()]
param([ValidateSet('Both','Offline','Runtime')][string]$QualificationSlice = 'Both')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))

function Text([string]$path) {
    [IO.File]::ReadAllText((Join-Path $source $path))
}

function Read-SubagentAllows([string]$metadata) {
    @([regex]::Matches($metadata, '(?ms)^\s{2}- action:\s*subagent\s*\r?\n\s{4}resource:\s*"?(?<resource>[^"\r\n]+)"?\s*\r?\n\s{4}effect:\s*allow\s*$') |
        ForEach-Object { $_.Groups['resource'].Value.Trim() })
}

function Has-DefaultSubagentDeny([string]$metadata) {
    $metadata -match '(?ms)^\s{2}- action:\s*subagent\s*\r?\n\s{4}resource:\s*"\*"\s*\r?\n\s{4}effect:\s*deny\s*$'
}

function Check([string]$id, [bool]$ok) {
    if (-not $ok) { throw "$id FAIL" }
    Write-Output "$id PASS"
}

try {
    $identities = Text 'olympus/core/identities.toml'
    $models = Text 'olympus/core/models.toml'
    $renderer = Text 'scripts/render_harnesses.py'
    $kaelMetadata = Text 'olympus/harnesses/opencode/agent-metadata/kael.md'
    $atlasMetadata = Text 'olympus/harnesses/opencode/agent-metadata/atlas.md'
    $argusSourcePaths = @(
        'olympus/roles/argus.md',
        'olympus/harnesses/opencode/agent-metadata/argus.md',
        'olympus/harnesses/opencode/agent-prompts/argus.md'
    )
    $argusSourcePresent = @($argusSourcePaths | Where-Object {
        Test-Path -LiteralPath (Join-Path $source $_) -PathType Leaf
    })
    $rendererUsesCanonicalRoster = $renderer.Contains('def role_ids(') -and
        $renderer.Contains('model_roles = set(models.get("roles", {}))') -and
        $renderer.Contains('metadata_roles != roles or prompt_roles != roles') -and
        $renderer.Contains('for role in sorted(roles):')

    Check 'AR_RETIRED_ROLE_HAS_NO_CANONICAL_ALIAS' (
        $identities -notmatch '(?m)^\[roles\.argus\]\s*$' -and
        $models -notmatch '(?m)^\[roles\.argus\]\s*$' -and
        $argusSourcePresent.Count -eq 0 -and
        $rendererUsesCanonicalRoster
    )

    $expectedKaelChildren = @('veyra','kovan','nox','vera','helios','talos','thales')
    $kaelChildren = @(Read-SubagentAllows $kaelMetadata)
    Check 'AR_RETIRED_ROLE_AND_ATLAS_NOT_KAEL_CHILDREN' (
        (Has-DefaultSubagentDeny $kaelMetadata) -and
        $kaelChildren.Count -eq $expectedKaelChildren.Count -and
        @($expectedKaelChildren | Where-Object { $_ -notin $kaelChildren }).Count -eq 0 -and
        @($kaelChildren | Where-Object { $_ -notin $expectedKaelChildren }).Count -eq 0 -and
        @('argus','orin','atlas' | Where-Object { $_ -in $kaelChildren }).Count -eq 0
    )

    $expectedAtlasChildren = @('veyra','helios','talos','thales')
    $atlasChildren = @(Read-SubagentAllows $atlasMetadata)
    Check 'AR_ATLAS_REMAINS_SEPARATE_WITH_BOUNDED_DELEGATION' (
        $atlasMetadata -match '(?m)^mode:\s*primary\s*$' -and
        (Has-DefaultSubagentDeny $atlasMetadata) -and
        $atlasChildren.Count -eq $expectedAtlasChildren.Count -and
        @($expectedAtlasChildren | Where-Object { $_ -notin $atlasChildren }).Count -eq 0 -and
        @($atlasChildren | Where-Object { $_ -notin $expectedAtlasChildren }).Count -eq 0 -and
        @('argus','orin','kael','atlas' | Where-Object { $_ -in $atlasChildren }).Count -eq 0
    )

    if ($QualificationSlice -eq 'Runtime') {
        Write-Output 'ARGUS RUNTIME QUALIFICATION: NOT RUN (retired role; no native agent invoked)'
    } elseif ($QualificationSlice -eq 'Offline') {
        Write-Output 'ARGUS OFFLINE QUALIFICATION: PASS (static retirement and delegation checks; no native agent invoked)'
    } else {
        Write-Output 'ARGUS RETIREMENT QUALIFICATION: PASS (static retirement and delegation checks; no native agent invoked)'
    }
    exit 0
} catch {
    Write-Output ('EVIDENCE: ' + $_.Exception.Message)
    Write-Output 'ARGUS RETIREMENT QUALIFICATION: FAIL'
    exit 1
}
