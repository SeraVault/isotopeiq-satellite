# IsotopeIQ Windows Push Collector
# Downloads windows_collector.exe from Satellite if not present, runs it,
# and pushes the canonical JSON output back to Satellite.
#
# Compatible with PowerShell 3.0+ (Windows 7 SP1 with WMF 3.0, Windows 8+)
#
# Required placeholders (substituted by IsotopeIQ before deployment):
#   {{SATELLITE_URL}}  - base URL of the Satellite server, e.g. http://10.0.0.1:8000
#   {{PUSH_TOKEN}}     - device push token from the IsotopeIQ device record

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$SATELLITE_URL = "{{SATELLITE_URL}}"
$PUSH_TOKEN    = "{{PUSH_TOKEN}}"

$INSTALL_DIR   = "$env:ProgramData\IsotopeIQ"
$EXE_PATH      = "$INSTALL_DIR\windows_collector.exe"
$DOWNLOAD_URL  = "$SATELLITE_URL/api/agents/windows_collector.exe"
$PUSH_URL      = "$SATELLITE_URL/api/push/data/"

# ---------------------------------------------------------------------------
# 1. Ensure collector is installed
# ---------------------------------------------------------------------------

if (-not (Test-Path $EXE_PATH)) {
    Write-Host "IsotopeIQ collector not found. Downloading from $DOWNLOAD_URL ..."
    if (-not (Test-Path $INSTALL_DIR)) {
        New-Item -ItemType Directory -Path $INSTALL_DIR | Out-Null
    }
    try {
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($DOWNLOAD_URL, $EXE_PATH)
        Write-Host "Downloaded to $EXE_PATH"
    } catch {
        Write-Error "Failed to download collector: $_"
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 2. Run the collector
# ---------------------------------------------------------------------------

Write-Host "Running collector ..."
try {
    $output = & $EXE_PATH 2>&1
    $json_output = $output | Out-String
} catch {
    Write-Error "Collector failed: $_"
    exit 1
}

# Validate that the output looks like JSON before sending
if ($json_output.Trim() -notmatch '^\{') {
    Write-Error "Collector output does not appear to be JSON:`n$json_output"
    exit 1
}

# Parse to ensure it is valid JSON (requires PS 3.0+)
try {
    $parsed = $json_output | ConvertFrom-Json
} catch {
    Write-Error "Collector output is not valid JSON: $_"
    exit 1
}

# ---------------------------------------------------------------------------
# 3. Push to Satellite
# ---------------------------------------------------------------------------

Write-Host "Sending data to $PUSH_URL ..."
$body = @{ canonical_data = $parsed } | ConvertTo-Json -Depth 20 -Compress

try {
    $headers = @{
        'Content-Type' = 'application/json'
        'X-Push-Token' = $PUSH_TOKEN
    }
    $response = Invoke-RestMethod -Uri $PUSH_URL -Method Post -Headers $headers -Body $body
    Write-Host "Success. job_id=$($response.job_id) result_id=$($response.result_id)"
} catch {
    Write-Error "Push failed: $_"
    exit 1
}
