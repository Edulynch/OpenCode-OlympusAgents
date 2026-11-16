# Process-only backstops for installer fixtures; never persist a user PATH.
function Enter-OlympusInstallerTestEnvironment([string]$Root) {
    $root = [IO.Path]::GetFullPath($Root)
    $previous = @{}
    $directories = @{
        USERPROFILE='profile'; HOME='profile'; APPDATA='appdata'; LOCALAPPDATA='localappdata'
        XDG_CONFIG_HOME='xdg'; OPENCODE_CONFIG_DIR='opencode-global'; CODEX_HOME='codex'
        TEMP='temp'; TMP='temp'; TMPDIR='temp'; OLYMPUS_CLI_ROOT='cli'
    }
    foreach ($name in $directories.Keys) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        $value = Join-Path $root $directories[$name]
        [IO.Directory]::CreateDirectory($value) | Out-Null
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
    foreach ($name in @('OLYMPUS_CLI_PATH_STORE','OLYMPUS_CONFIG_FILE','PYTHONDONTWRITEBYTECODE')) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }
    $env:OLYMPUS_CLI_PATH_STORE = Join-Path $root 'cli/path-store.txt'
    $env:OLYMPUS_CONFIG_FILE = Join-Path $root 'olympus/config.json'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    return $previous
}

function Exit-OlympusInstallerTestEnvironment([hashtable]$Previous) {
    foreach ($name in $Previous.Keys) {
        [Environment]::SetEnvironmentVariable($name, $Previous[$name], 'Process')
    }
}
