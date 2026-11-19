#!/usr/bin/env pwsh
# Setup implementation plan for a feature

[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$Help,
    # Capture extra positional arguments to match Bash/Python behavior.
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = 'Stop'

# Show help if requested
if ($Help) {
    Write-Output "Usage: ./setup-plan.ps1 [-Json] [-Help]"
    Write-Output "  -Json     Output results in JSON format"
    Write-Output "  -Help     Show this help message"
    exit 0
}

if ($RemainingArgs.Count -gt 0) {
    [Console]::Error.WriteLine("ERROR: Unknown option '$($RemainingArgs[0])'")
    exit 1
}

# Load common functions
. "$PSScriptRoot/common.ps1"

# Get all paths and variables from common functions
$paths = Get-FeaturePathsEnv -ReturnNullOnError
if (-not $paths) {
    [Console]::Error.WriteLine("ERROR: Failed to resolve feature paths")
    exit 1
}

# Ensure the feature directory exists
[System.IO.Directory]::CreateDirectory($paths.FEATURE_DIR) | Out-Null

# Copy plan template if plan doesn't already exist
$planAlreadyExists = Test-Path -LiteralPath $paths.IMPL_PLAN -PathType Leaf
$templateMissing = $false
if (-not $planAlreadyExists) {
    $content = Resolve-TemplateContent -TemplateName 'plan-template' -RepoRoot $paths.REPO_ROOT
    $templateMissing = $null -eq $content
    if ($templateMissing) {
        $content = ''
    }

    # Stage beside the target, then move without replacement so a concurrent
    # plan creation cannot be overwritten or observed partially written.
    $temporaryPlan = Join-Path $paths.FEATURE_DIR (".plan.md.$([Guid]::NewGuid().ToString('N')).tmp")
    $temporaryPlanOwned = $false
    try {
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        $bytes = $utf8NoBom.GetBytes($content)
        $stream = [System.IO.File]::Open(
            $temporaryPlan,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        $temporaryPlanOwned = $true
        try {
            $stream.Write($bytes, 0, $bytes.Length)
        } finally {
            $stream.Dispose()
        }

        try {
            [System.IO.File]::Move($temporaryPlan, $paths.IMPL_PLAN)
            $temporaryPlan = $null
        } catch [System.IO.IOException] {
            $errorCode = $_.Exception.HResult -band 0xFFFF
            if (($errorCode -in @(80, 183)) -and [System.IO.File]::Exists($paths.IMPL_PLAN)) {
                $planAlreadyExists = $true
            } else {
                throw
            }
        }
    } finally {
        if ($temporaryPlanOwned -and $temporaryPlan -and [System.IO.File]::Exists($temporaryPlan)) {
            [System.IO.File]::Delete($temporaryPlan)
        }
    }
}

if ($planAlreadyExists) {
    if ($Json) {
        [Console]::Error.WriteLine("Plan already exists at $($paths.IMPL_PLAN), skipping template copy")
    } else {
        Write-Output "Plan already exists at $($paths.IMPL_PLAN), skipping template copy"
    }
} elseif (-not $templateMissing) {
    # Emit the copy status like the bash twin (setup-plan.sh); route to stderr
    # in -Json mode so stdout stays pure JSON, matching the sibling messages.
    if ($Json) {
        [Console]::Error.WriteLine("Copied plan template to $($paths.IMPL_PLAN)")
    } else {
        Write-Output "Copied plan template to $($paths.IMPL_PLAN)"
    }
} else {
    # Keep JSON stdout pure and leave the fallback plan empty when no template exists.
    if ($Json) {
        [Console]::Error.WriteLine("Warning: Plan template not found")
    } else {
        Write-Output "Warning: Plan template not found"
    }
}

# Output results
if ($Json) {
    $result = [PSCustomObject]@{
        FEATURE_SPEC = $paths.FEATURE_SPEC
        IMPL_PLAN = $paths.IMPL_PLAN
        FEATURE_DIR = $paths.FEATURE_DIR
        BRANCH = $paths.CURRENT_BRANCH
    }
    $result | ConvertTo-Json -Compress
} else {
    Write-Output "FEATURE_SPEC: $($paths.FEATURE_SPEC)"
    Write-Output "IMPL_PLAN: $($paths.IMPL_PLAN)"
    Write-Output "FEATURE_DIR: $($paths.FEATURE_DIR)"
    Write-Output "BRANCH: $($paths.CURRENT_BRANCH)"
}
