[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$')]
    [string]$Version,
    [Parameter(Mandatory)]
    [ValidatePattern('^(?:[0-9a-f]{40}|[0-9a-f]{64})$')]
    [string]$ExpectedCommit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repositoryUrl = 'https://github.com/Edulynch/OpenCode-OlympusAgents.git'
$checkout = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$head = (& git -C $checkout rev-parse HEAD 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $head -cne $ExpectedCommit) {
    throw 'TAG_QUALIFICATION_CHECKOUT_MISMATCH: checkout must be the exact workflow SHA.'
}

$tagRef = "refs/tags/$Version"
$localRef = "refs/olympus/verify-tags/$Version"
& git -C $checkout show-ref --verify --quiet $localRef
if ($LASTEXITCODE -eq 0) { throw 'TAG_QUALIFICATION_REF_COLLISION' }
& git -C $checkout fetch --no-tags $repositoryUrl "${tagRef}:${localRef}"
if ($LASTEXITCODE -ne 0) { throw 'TAG_QUALIFICATION_FETCH_FAILED' }
$type = (& git -C $checkout cat-file -t $localRef 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $type -cne 'tag') {
    throw 'TAG_QUALIFICATION_NOT_ANNOTATED'
}
$tagObject = @(& git -C $checkout cat-file -p $localRef)
if ($LASTEXITCODE -ne 0) { throw 'TAG_QUALIFICATION_OBJECT_UNAVAILABLE' }
$separator = [Array]::IndexOf($tagObject, '')
if ($separator -lt 0) { throw 'TAG_QUALIFICATION_OBJECT_MALFORMED' }
$headers = @($tagObject[0..($separator - 1)])
$messageLines = if ($separator + 1 -lt $tagObject.Count) {
    @($tagObject[($separator + 1)..($tagObject.Count - 1)])
} else { @() }
$message = ($messageLines -join "`n") + "`n"
$target = (& git -C $checkout rev-parse "$localRef^{commit}" 2>&1 | Out-String).Trim()
$objects = @($headers | Where-Object { $_ -match '^object [0-9a-f]{40,64}$' })
$types = @($headers | Where-Object { $_ -ceq 'type commit' })
$names = @($headers | Where-Object { $_ -ceq "tag $Version" })
$taggers = @($headers | Where-Object {
    $_ -match '^tagger github-actions\[bot\] <41898282\+github-actions\[bot\]@users\.noreply\.github\.com> [0-9]+ \+0000$'
})
$expectedMessage = "Olympus automatic release`nversion: $Version`ncommit: $ExpectedCommit`n"
if ($LASTEXITCODE -ne 0 -or $target -cne $ExpectedCommit -or
    $objects.Count -ne 1 -or $objects[0] -cne "object $ExpectedCommit" -or
    $types.Count -ne 1 -or $names.Count -ne 1 -or $taggers.Count -ne 1 -or
    $message -cne $expectedMessage) {
    throw 'TAG_QUALIFICATION_IDENTITY_MISMATCH: remote annotated tag does not name the exact promotion commit.'
}

$runRoot = Join-Path ([IO.Path]::GetFullPath($env:RUNNER_TEMP)) ('opencode/tag-qualification-' + [guid]::NewGuid().ToString('N'))
$archive = Join-Path $runRoot 'tag-source.zip'
$tagSource = Join-Path $runRoot 'source'
# Keep Git fixtures at the shallower runner temp root; Windows Git also traverses longer .git metadata paths.
$processTemp = [IO.Path]::GetFullPath($env:RUNNER_TEMP)
[IO.Directory]::CreateDirectory($tagSource) | Out-Null
[IO.Directory]::CreateDirectory($processTemp) | Out-Null
& git -C $checkout archive --format=zip --output=$archive $localRef
if ($LASTEXITCODE -ne 0) { throw 'TAG_QUALIFICATION_ARCHIVE_FAILED' }
Expand-Archive -LiteralPath $archive -DestinationPath $tagSource
$qualifier = Join-Path $tagSource 'tests/release/qualify.ps1'
if (-not (Test-Path -LiteralPath $qualifier -PathType Leaf)) {
    throw 'TAG_QUALIFICATION_TEST_SOURCE_MISSING'
}

$previousTemp = @{}
foreach ($name in @('TEMP', 'TMP', 'TMPDIR')) {
    $previousTemp[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    [Environment]::SetEnvironmentVariable($name, $processTemp, 'Process')
}
try {
    $output = @(& pwsh -NoProfile -File $qualifier -MockOpenCode -ExpectedVersion $Version 2>&1)
    $code = $LASTEXITCODE
    $output | Out-Host
    if ($code -ne 0) { throw "TAG_QUALIFICATION_FAILED: exact-tag release qualifier exited $code." }
} finally {
    foreach ($name in $previousTemp.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousTemp[$name], 'Process')
    }
}

Write-Output "TAGGED_SOURCE_QUALIFICATION: $Version PASS (exact annotated tag archive; isolated Windows fixtures; mocked OpenCode)"
Write-Output 'PUBLIC_INSTALL_LIFECYCLE: PENDING (tag qualification is not a public latest-endpoint install/VerifyOnly/uninstall smoke)'
