# IsotopeIQ Windows Pull Collector
# Downloads windows_collector.exe from Satellite if not present, runs it,
# and writes the canonical JSON output to stdout for the caller to collect.
#
# Compatible with PowerShell 3.0+ (Windows 7 SP1 with WMF 3.0, Windows 8+)
#
# Placeholders substituted by IsotopeIQ before deployment:
#   {{SATELLITE_URL}}  - base URL of the Satellite server, e.g. http://10.0.0.1:8000

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$SATELLITE_URL = "{{SATELLITE_URL}}"

$INSTALL_DIR   = "$env:ProgramData\IsotopeIQ"
$EXE_PATH      = "$INSTALL_DIR\windows_collector.exe"
$DOWNLOAD_URL  = "$SATELLITE_URL/api/agents/windows_collector.exe"

# ---------------------------------------------------------------------------
# 1. Ensure collector is installed
# ---------------------------------------------------------------------------

if (-not (Test-Path $EXE_PATH)) {
    if (-not (Test-Path $INSTALL_DIR)) {
        New-Item -ItemType Directory -Path $INSTALL_DIR | Out-Null
    }
    try {
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($DOWNLOAD_URL, $EXE_PATH)
    } catch {
        Write-Error "Failed to download collector: $_"
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 2. Run the collector and write output to stdout
# ---------------------------------------------------------------------------

& $EXE_PATH
exit $LASTEXITCODE
