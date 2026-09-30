param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Command)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Command.Count -eq 1 -and $Command[0] -eq '--version') {
    Write-Output 'OpenCode qualification stub 2.0'
    exit 0
}
if ($Command.Count -eq 1 -and $Command[0] -eq 'models') {
    # The stable v0.2.0 installer still validates its historical Sol ID.
    # Current Olympus roles use GPT-6.1 Sol; keep both for cross-version tests.
    Write-Output 'openai/gpt-6.1-sol'
    Write-Output 'openai/gpt-6-sol'
    Write-Output 'openai/gpt-6-luna'
    exit 0
}
if ($Command.Count -ge 2 -and $Command[0] -eq 'debug' -and $Command[1] -eq 'config') {
    Write-Output '{}'
    exit 0
}
if ($Command.Count -ge 2 -and $Command[0] -eq 'debug' -and $Command[1] -eq 'agents') {
    $agents = foreach ($file in Get-ChildItem -LiteralPath (Join-Path (Get-Location).Path '.opencode/agents') -Filter '*.md' -File -ErrorAction SilentlyContinue) {
        $text = [IO.File]::ReadAllText($file.FullName)
        $modelLine = @($text -split "`r?`n" | Where-Object { $_ -match '^model:\s*' } | Select-Object -First 1)
        $modeLine = @($text -split "`r?`n" | Where-Object { $_ -match '^mode:\s*' } | Select-Object -First 1)
        if (-not $modelLine -or -not $modeLine) { continue }
        $model = ($modelLine[0] -replace '^model:\s*', '').Trim().Trim('"').Trim("'")
        $mode = ($modeLine[0] -replace '^mode:\s*', '').Trim()
        $parts = $model -split '#', 2
        $modelId = ($parts[0] -split '/')[-1]
        $permissions = foreach ($match in [regex]::Matches($text, '(?m)^[ \t]*-[ \t]+action:[ \t]*(?<action>[^\r\n]+)\r?\n[ \t]+resource:[ \t]*(?<resource>[^\r\n]+)\r?\n[ \t]+effect:[ \t]*(?<effect>[^\r\n]+)')) {
            [pscustomobject]@{
                action = $match.Groups['action'].Value.Trim().Trim('"').Trim("'")
                resource = $match.Groups['resource'].Value.Trim().Trim('"').Trim("'")
                effect = $match.Groups['effect'].Value.Trim().Trim('"').Trim("'")
            }
        }
        [pscustomobject]@{
            id = $file.BaseName
            model = [pscustomobject]@{ id=$modelId; variant=$(if ($parts.Count -gt 1) { $parts[1] } else { '' }) }
            mode = $mode
            hidden = ($text -match '(?m)^hidden:\s*true\s*$')
            permissions = @($permissions)
        }
    }
    ConvertTo-Json -InputObject @($agents) -Depth 10 -Compress
    exit 0
}
if ($Command.Count -ge 2 -and $Command[0] -eq 'plugin' -and $Command[1] -eq 'list') {
    Write-Output 'olympus-activity'
    exit 0
}

[Console]::Error.WriteLine('Unsupported OpenCode qualification stub command: ' + ($Command -join ' '))
exit 2
