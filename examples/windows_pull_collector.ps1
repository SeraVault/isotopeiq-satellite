# IsotopeIQ Windows Pull Collector
# Checks whether windows_collector.exe is installed and up to date by comparing
# the local SHA-256 against the server's /api/agents/<file>/info endpoint.
# Downloads and verifies the binary only when missing or outdated, then runs it.
#
# Compatible with PowerShell 3.0+ (Windows 7 SP1 + WMF 3.0, Windows 8+)
#
# Placeholders substituted by IsotopeIQ before deployment:
#   {{SATELLITE_URL}}  - base URL of the Satellite server, e.g. http://10.0.0.1:8000

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$SATELLITE_URL = "{{SATELLITE_URL}}"

$INSTALL_DIR  = "$env:ProgramData\IsotopeIQ"
$EXE_NAME     = "windows_collector.exe"
$EXE_PATH     = "$INSTALL_DIR\$EXE_NAME"
$HASH_CACHE   = "$INSTALL_DIR\windows_collector.sha256"
$INFO_URL     = "$SATELLITE_URL/api/agents/$EXE_NAME/info"
$DOWNLOAD_URL = "$SATELLITE_URL/api/agents/$EXE_NAME"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Get-FileSHA256([string]$FilePath) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($FilePath)
    try {
        $bytes = $sha.ComputeHash($stream)
    } finally {
        $stream.Close()
        $sha.Dispose()
    }
    return ($bytes | ForEach-Object { $_.ToString('x2') }) -join ''
}

function Get-ServerInfo {
    try {
        $wc = New-Object System.Net.WebClient
        $json = $wc.DownloadString($INFO_URL)
        # ConvertFrom-Json is built into PowerShell 3.0+ — no assembly needed
        return ConvertFrom-Json $json
    } catch {
        Write-Warning "Could not reach server info endpoint: $_"
        return $null
    }
}

function Install-Collector([string]$ExpectedSHA256) {
    if (-not (Test-Path $INSTALL_DIR)) {
        New-Item -ItemType Directory -Path $INSTALL_DIR | Out-Null
    }
    $tmpPath = "$INSTALL_DIR\$EXE_NAME.tmp"
    try {
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($DOWNLOAD_URL, $tmpPath)
    } catch {
        if (Test-Path $tmpPath) { Remove-Item $tmpPath -Force }
        Write-Error "Download failed: $_"
        exit 1
    }
    # Verify integrity before replacing the live binary
    $actualHash = Get-FileSHA256 $tmpPath
    if ($actualHash -ne $ExpectedSHA256) {
        Remove-Item $tmpPath -Force
        Write-Error "Integrity check failed. Expected $ExpectedSHA256, got $actualHash. Aborting."
        exit 1
    }
    # Atomic-ish replace: rename tmp over the existing exe
    if (Test-Path $EXE_PATH) { Remove-Item $EXE_PATH -Force }
    Rename-Item -Path $tmpPath -NewName $EXE_NAME
    # Persist the verified hash so the next run skips the download
    Set-Content -Path $HASH_CACHE -Value $actualHash -Encoding ASCII
    Write-Verbose "Collector installed/updated. SHA256: $actualHash"
}

# ---------------------------------------------------------------------------
# 1. Determine whether an install or update is needed
# ---------------------------------------------------------------------------

$serverInfo = Get-ServerInfo

$needInstall = $false

if (-not (Test-Path $EXE_PATH)) {
    # Not installed at all
    $needInstall = $true
} elseif ($serverInfo -ne $null) {
    $serverHash = $serverInfo.sha256
    # Use cached hash if available (avoids re-hashing a large binary every run)
    if (Test-Path $HASH_CACHE) {
        $localHash = (Get-Content $HASH_CACHE -Raw).Trim()
    } else {
        $localHash = Get-FileSHA256 $EXE_PATH
        Set-Content -Path $HASH_CACHE -Value $localHash -Encoding ASCII
    }
    if ($serverHash -and ($serverHash -ne $localHash)) {
        Write-Verbose "Server has a newer build (local: $localHash  server: $serverHash). Updating."
        $needInstall = $true
    }
    # If $serverInfo is null (server unreachable) we silently proceed with whatever is installed.
}

if ($needInstall) {
    if ($serverInfo -eq $null) {
        Write-Error "Collector is not installed and the server is unreachable. Cannot continue."
        exit 1
    }
    Install-Collector -ExpectedSHA256 $serverInfo.sha256
}

# ---------------------------------------------------------------------------
# 2. Run the collector and write output to stdout
# ---------------------------------------------------------------------------

& $EXE_PATH
exit $LASTEXITCODE

